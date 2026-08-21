# AI Microservice — Agentic IT Support Copilot

Layanan FastAPI yang menjawab pertanyaan tentang dokumen SOP menggunakan RAG
(*Retrieval-Augmented Generation*) dengan LLM lokal via Ollama. Seluruh
pemrosesan berjalan di mesin sendiri — tidak ada isi dokumen yang dikirim ke
layanan pihak ketiga.

Dua tanggung jawab utamanya:

1. **Ingest** — menerima PDF dari Laravel, mengekstrak teksnya (termasuk OCR
   untuk halaman hasil pindai), memecahnya jadi potongan, lalu menyimpannya
   sebagai vektor di ChromaDB.
2. **Tanya-jawab** — mencari potongan yang relevan lalu menyusun jawaban
   dengan LLM, disertai rujukan halaman sumbernya.

> Rancangan retrieval-nya dijelaskan terpisah di
> [`docs/07-arsitektur-rag-python-ai.md`](../docs/07-arsitektur-rag-python-ai.md).

---

## Prasyarat

| Kebutuhan | Versi | Catatan |
|---|---|---|
| Python | **3.10+** | Kode memakai sintaks `list[int] \| None` |
| [Ollama](https://ollama.com) | terbaru | Mesin LLM & OCR |
| MySQL | 8.0+ | Dipakai bersama `laravel-admin` |
| Redis | 6+ | Broker antrean Celery |

Tesseract **tidak** dibutuhkan. OCR dikerjakan model vision lewat REST API
Ollama (`pdf_processor.py:181`), bukan mesin OCR terpisah.

Tarik dua model Ollama berikut:

```bash
ollama pull qwen2.5:7b      # chat, ekstraksi kata kunci
ollama pull qwen2.5vl:7b    # OCR halaman pindai
```

---

## Pemasangan

```bash
cd python-ai/

python -m venv .venv
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux/WSL

pip install -r requirements.txt

cp .env.example .env              # lalu sesuaikan isinya
```

Butuh environment yang persis sama dengan yang dipakai saat pengujian?
Pakai `requirements.lock.txt` (172 paket, termasuk seluruh dependensi
turunan) sebagai ganti `requirements.txt`.

---

## Konfigurasi

Seluruh pengaturan dibaca dari `.env` oleh `app/config.py`.

| Variabel | Contoh | Keterangan |
|---|---|---|
| `LLM_MODEL_NAME` | `qwen2.5:7b` | Model chat & ekstraksi kata kunci |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Alamat server Ollama |
| `VISION_MODEL_NAME` | `qwen2.5vl` | Model OCR halaman pindai |
| `VISION_TIMEOUT` | `1000` | Detik. OCR di CPU bisa sangat lambat |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-m3` | Diunduh otomatis saat pertama dipakai |
| `CHROMA_PERSIST_DIR` | `./data/chromadb` | Lokasi basis data vektor |
| `MYSQL_HOST` `MYSQL_PORT` | `localhost` `3306` | Basis data bersama Laravel |
| `MYSQL_DATABASE` | `agentic_copilot` | |
| `MYSQL_USER` `MYSQL_PASSWORD` | | |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Antrean tugas |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/1` | |
| `INTERNAL_API_TOKEN` | | Token Bearer untuk seluruh endpoint internal |
| `CHAT_STREAM_REQUIRE_AUTH` | `true` | Penjaga token di `/api/chat/stream`. Setel `false` hanya untuk pengembangan lokal |
| `LLM_MAX_NUM_CTX` | `16384` | Batas atas jendela konteks. Turunkan bila log memuat `failed to allocate buffer` |
| `CORS_ALLOW_ORIGINS` | `http://localhost:5173,...` | Origin yang boleh memanggil dari browser, dipisah koma. Jangan diisi `*` |
| `DEBUG_DUMP_CONTEXT` | `false` | Menulis konteks retrieval ke `debug_context.txt` tiap pertanyaan. Jangan diaktifkan di produksi |
| `GEMINI_API_KEY` | | **Hanya untuk evaluasi RAGAS.** Layanan berjalan normal tanpa ini |

**Kalau pemuatan model embedding terasa lama.** `sentence_transformers`
memeriksa pembaruan ke huggingface.co setiap kali dimuat, walau modelnya
sudah lengkap di cache. Bila jaringan lambat atau diblokir, pemeriksaan itu
habis waktu lalu diulang lima kali dengan jeda menaik — satu sampai dua menit
terbuang setiap skrip mulai, untuk akhirnya memakai berkas yang sejak awal
ada di disk.

Obatnya `HF_HUB_OFFLINE=1` di `.env`. **Sengaja tidak dinyalakan otomatis:**
`transformers` memanggil `model_info()` tanpa syarat saat memeriksa jenis
tokenizer, dan dalam mode luring panggilan itu *melempar* `OfflineModeIsEnabled`
alih-alih dilewati — pemuatan model gagal total, bukan sekadar lambat.
Kegagalan itu tidak muncul di semua mesin, dan setelan yang kadang
menghentikan pekerjaan tidak layak jadi bawaan.

Kalau kamu menyalakannya dan ternyata kena, `get_embedding_model()` menangkap
kegagalan itu, mematikan mode luring, lalu mengulang sekali sambil mencatat
peringatan. Jadi paling buruk kamu kembali ke kecepatan semula, bukan gagal.

> Ganti model embedding berarti **seluruh dokumen harus di-ingest ulang** —
> vektor lama dibuat dengan model berbeda dan tidak sebanding.

---

## Menjalankan

Butuh empat proses. Nyalakan berurutan:

```bash
# 1. Redis
redis-server

# 2. Ollama
ollama serve

# 3. Server API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 4. Pekerja Celery (terminal terpisah)
celery -A app.tasks.process_document worker --loglevel=info --pool=solo
```

Dua catatan penting soal perintah Celery:

- Modulnya **`app.tasks.process_document`**, bukan `app.tasks`.
  `app/tasks/__init__.py` kosong, sehingga `-A app.tasks` tidak akan
  menemukan instance Celery-nya.
- `--pool=solo` diperlukan di Windows. Di Linux boleh dihilangkan.

Setelah jalan:

- API — <http://localhost:8000>
- Dokumentasi interaktif — <http://localhost:8000/docs>
- Health check — <http://localhost:8000/health>

---

## Endpoint

| Metode | Rute | Auth | Fungsi |
|---|---|---|---|
| `POST` | `/api/chat/stream` | Bearer¹ | Tanya-jawab streaming (SSE) untuk widget |
| `POST` | `/api/chat/message` | Bearer | Tanya-jawab sekali balas untuk WhatsApp |
| `GET` | `/api/docs` | Bearer | Daftar seluruh dokumen |
| `GET` | `/api/docs/{id}/status` | Bearer | Status pemrosesan satu dokumen |
| `POST` | `/api/docs/process` | Bearer | Kirim dokumen ke antrean ingest |
| `GET` | `/health` | tidak ada | Health check |

¹ Bisa dimatikan lewat `CHAT_STREAM_REQUIRE_AUTH=false` untuk pengembangan lokal.

Permintaan tanpa header `Authorization` dijawab **401**, bukan 422 — pemanggil
seperti Laravel bisa mengandalkan kode itu untuk membedakan "tidak punya
kredensial" dari "payload-nya salah bentuk".

Bentuk payload dan responsnya ada di
[`docs/04-api_spec_agentic_copilot.md`](../docs/04-api_spec_agentic_copilot.md).

> **Widget di browser tidak boleh memegang `INTERNAL_API_TOKEN`.** Token yang
> sama juga membuka `/api/docs/*`, dan apa pun yang masuk ke JavaScript sisi
> klien bisa dibaca lewat devtools. Jalur yang benar untuk produksi: widget
> memanggil Laravel, Laravel meneruskannya ke layanan ini dengan token yang
> disimpan di sisi server.

---

## Evaluasi mutu jawaban

Ada dua alat, dan keduanya menjawab pertanyaan yang berbeda.

### 1. `evaluasi_sederhana.py` — pencocokan fakta (mulai dari sini)

```bash
python evaluasi_sederhana.py              # nilai jawaban tersimpan, seketika
python evaluasi_sederhana.py --all        # seluruh 26 pertanyaan
python evaluasi_sederhana.py --jalankan   # panggil pipeline RAG (lambat)
python evaluasi_sederhana.py --nilai-ulang # nilai ulang jawaban tersimpan
```

Menanyakan satu hal saja: **apakah fakta yang wajib ada benar-benar muncul di
jawaban?** Kriterianya ditulis di kolom `penilaian` pada
`reference_eval_dataset.json`:

```json
"penilaian": {
  "wajib":   [["395"], ["2025"]],
  "minimal": {"jumlah": 5, "dari": ["Renstra", "Renja", "..."]}
}
```

- `wajib` — tiap kelompok harus terpenuhi; isi kelompok adalah alternatif
  penulisan, salah satu cocok sudah cukup
- `minimal` — untuk pertanyaan terbuka, cukup N item dari daftar

Keluarannya berupa vonis yang langsung terbaca — **BENAR**, **SEBAGIAN**,
**SALAH**, **TIDAK MENJAWAB** — beserta daftar fakta mana yang hilang.
Deterministik, gratis, selesai dalam sekejap, dan tidak mengirim isi dokumen
ke pihak mana pun.

`TIDAK MENJAWAB` sengaja dipisahkan dari `SALAH`: menjawab "tidak ditemukan"
adalah perilaku yang benar ketika konteksnya memang tidak memuat jawaban, dan
menyamakannya dengan halusinasi akan menyesatkan.

> Alat ini pernah menangkap apa yang RAGAS lewatkan: pada q04, jawaban
> menyebut "46 SOP" padahal seharusnya 74 — kurang 28 item. RAGAS memberi
> `factual_correctness = 0.99` untuk jawaban itu, karena 46 item yang ada
> memang semuanya benar dan 28 yang hilang tidak pernah menjadi klaim.

#### Dataset lawan

`reference_eval_dataset.json` berisi pertanyaan yang jawabannya memang ada di
dokumen. Skor tinggi di sana tidak membuktikan sistem tahan ditipu, jadi ada
dataset pasangannya:

```bash
python evaluasi_sederhana.py --dataset reference_eval_lawan.json --all --jalankan
```

Isinya 26 pertanyaan yang menyerang butir bernomor sama dari sisi berlawanan —
kalau yang asli menanyakan SOP Renstra, yang lawan menanyakan Renja; kalau yang
asli menanyakan fakta yang ada, yang lawan menanyakan yang tidak ada. Rinciannya
ada di [`dataset_lawan.md`](dataset_lawan.md). Sumber kebenarannya tetap
`reference_eval_lawan.json` — itulah yang dibaca penilai; berkas markdown
hanya salinan untuk dibaca manusia.

Dataset ini memakai dua kriteria tambahan:

| Kriteria | Arti |
|---|---|
| `terlarang` | Ungkapan yang **tidak boleh** muncul; kemunculannya menggugurkan jawaban walau fakta lain sudah benar. Dipakai menangkap jawaban yang diambil dari SOP yang salah — dua SOP di dokumen ini isinya hampir kembar. |
| `harus_menolak` | Jawaban yang benar adalah **menolak menjawab**, untuk pertanyaan berpremis palsu (mis. "Diktum KEEMPAT" yang tidak ada). |
| `jumlah` | Angka yang harus dinyatakan **sebagai jumlah**, bukan sekadar muncul. Tanpa ini, kriteria `9` ikut cocok dengan penanda daftar `9. Format Renja` — sehingga jawaban yang menyebut jumlah salah tetap dapat nilai. |
| `menolak_premis` | Frasa yang menunjukkan premis palsunya berhasil dibantah. Jawaban yang membantah tapi kurang presisi dinilai SEBAGIAN, tidak disamakan dengan yang mengarang. |

Setiap butir juga menyimpan `jawaban_umpan`: satu jawaban SALAH yang khas untuk
pertanyaan itu. Unit test memastikan kriteria **menjatuhkan** umpan itu, bukan
sekadar meluluskan jawaban yang benar. Uji satu arah saja pernah membiarkan
empat kriteria terlalu longgar lolos — dan baru ketahuan setelah dua jam
eksekusi, saat laporannya menyebut 65% padahal yang sebenarnya 55%.

Jawaban mentah tiap eksekusi disimpan ke `hasil_evaluasi_lawan.jawaban.json`,
sehingga kriteria yang diperbaiki bisa diuji ulang seketika dengan
`--nilai-ulang` tanpa memanggil LLM lagi.

Laporannya ditulis terpisah ke `hasil_evaluasi_lawan.md`, jadi tidak menimpa
hasil dataset utama.

### 2. `test_ragas.py` — RAGAS

Mengukur hal yang tidak bisa ditangkap pencocokan fakta, terutama
**faithfulness** (apakah jawaban mengarang di luar konteks). Model yang
menjawab (`qwen2.5:7b`) sengaja dipisah dari model yang menilai supaya model
tidak menilai jawabannya sendiri.

**Juri bawaannya DeepSeek.** Dua alasan: juri lokal berarti model menilai
jawabannya sendiri sehingga angkanya bukan penilaian independen, dan juri
lokal juga berebut Ollama dengan model yang sedang menjawab — pada mesin
ber-RAM terbatas itu terbukti membuat permintaan menggantung puluhan menit.

> **Kerahasiaan.** Juri di server luar menerima pertanyaan, jawaban, **dan
> seluruh isi konteks dokumen**. Untuk dokumen internal instansi, pastikan itu
> memang diizinkan — atau pakai `--ollama`, satu-satunya pilihan yang tidak
> mengirim apa pun keluar mesin.

```bash
python test_ragas.py --list-models     # lihat model juri yang tersedia
python test_ragas.py --limit 3         # evaluasi 3 pertanyaan
python test_ragas.py --limit 10 --reuse  # pakai ulang jawaban tersimpan
```

| Flag | Fungsi |
|---|---|
| `--limit N` | Jumlah pertanyaan dari `reference_eval_dataset.json` |
| `--deepseek` | Juri DeepSeek — **bawaan**. Butuh `DEEPSEEK_API_KEY` |
| `--gemini` | Juri Gemini. Butuh `GEMINI_API_KEY`. Berjatah harian sempit |
| `--ollama` | Juri lokal. Tidak keluar mesin, tapi bukan penilaian independen |
| `--judge-model=<nama>` | Ganti model juri (jatah gratis dihitung per model per hari) |
| `--reuse` | Pakai ulang jawaban RAG dari cache, hanya ulangi penilaian |
| `--list-models` | Daftar model yang boleh dipakai API key ini |
| `--verbose` | Tampilkan seluruh log |

Hasilnya ditulis ke `hasil_ragas.md`: pertanyaan, jawaban RAG, ground
truth, skor per metrik, **dan seluruh chunk konteks yang dikirim ke LLM**
(terlipat dalam blok `<details>`). Skor rendah nyaris selalu berujung pada
pertanyaan "chunk apa yang sebenarnya diambil?", jadi jawabannya ada di tempat
yang sama dengan skornya — tidak perlu membuka `.ragas_cache_phase1.json`.

Skrip mencetak taksiran jumlah permintaan ke juri sebelum mulai — jatah gratis
Gemini dihitung **per model per hari**, jadi berganti model memberi jatah baru
seketika.

### Membaca `factual_correctness`

Metrik ini memecah jawaban **dan** ground truth menjadi klaim-klaim, lalu
menghitung F1 dari klaim yang saling terverifikasi. Konsekuensinya: **cara
ground truth ditulis ikut dinilai.** Ground truth yang menyelipkan letak
halaman, rujukan ke soal lain, atau kata "misalnya" akan terpecah menjadi klaim
yang tidak mungkin dibuktikan dari jawaban — dan skornya jatuh meski jawabannya
benar. Terukur pada q02: `0.0000` dengan ground truth apa adanya, `1.0000`
dengan ground truth yang sama isinya tetapi ditulis sebagai kalimat fakta biasa.

Keterangan letak dan kejanggalan dokumen punya tempatnya sendiri: kolom
`source_pages` dan `notes` di `reference_eval_dataset.json`. Keduanya **tidak
ikut dinilai** — hanya `ground_truth` yang dikirim ke juri.

Metrik ini juga tidak sepenuhnya stabil. Teks yang persis sama, dinilai tiga
kali, pernah menghasilkan `0.57`, `0.00`, `0.00`. Jangan menyimpulkan regresi
dari selisih kecil pada satu pertanyaan.

---

## Pengujian

```bash
python -m unittest test_rag_units test_api_kontrak    # 147 tes, ~9 detik, tanpa layanan apa pun
```

Dua berkas, dua lapisan berbeda.

**`test_rag_units.py` — 110 tes, logika RAG.** Menguji fungsi tanpa efek
samping: peringkat RRF, filter `where` ChromaDB, deteksi pertanyaan daftar,
pemecahan daftar per batas item, pembacaan konfigurasi, penjaga premis palsu,
pembeda dua SOP yang nyaris kembar, pemulihan penanda daftar yang rontok saat
OCR, serta kriteria penilai evaluasi. Dependensi berat digantikan stub, lalu
stub-nya dibuang lagi dari `sys.modules` supaya berkas tes lain tidak ikut
menerimanya.

Beberapa di antaranya menjaga alat ukurnya sendiri: kriteria dataset lawan
diuji **dua arah** — harus meluluskan ground truth, dan harus menjatuhkan
`jawaban_umpan`. Uji satu arah saja pernah membiarkan empat kriteria terlalu
longgar lolos tanpa ketahuan.

**`test_api_kontrak.py` — 37 tes, lapisan HTTP.** Mengunci apa yang dilihat
pemanggil: kode status, bentuk event SSE, nama kunci, dan header. Ini bagian
yang dipakai Dev 2 (Laravel) dan Dev 3 (React), dan sebelumnya satu-satunya
lapisan tanpa uji sama sekali — padahal di sinilah integrasi paling mungkin
patah.

Yang dikunci antara lain:

- **Bentuk event SSE** — `{"type":"chunk","content":...}`, ditutup
  `{"type":"done"}`. Ini ketidakcocokan nomor 1 di `docs/04` §0; kalau namanya
  berubah, jawaban tidak muncul sama sekali di widget.
- **401 yang konsisten** di seluruh endpoint, termasuk jaminan bahwa
  `CHAT_STREAM_REQUIRE_AUTH=false` **hanya** melonggarkan `/api/chat/stream`
  dan tidak pernah membuka `/api/docs/*`.
- **`{"status":"accepted"}`** pada `POST /api/docs/process` — ketidakcocokan
  nomor 3.
- **Kegagalan tidak membocorkan rincian** — pesan exception, path, dan
  kredensial tidak boleh sampai ke klien, baik lewat event SSE maupun 500.
- **CORS tidak pernah kembali ke `*`.**
- **`/health` membalas 503** saat ada dependensi mati, dan hasilnya di-cache
  5 detik.

Seluruh dependensi (Ollama, ChromaDB, MySQL, Redis, Celery) digantikan tiruan,
jadi berkas ini berjalan tanpa satu pun layanan menyala.

---

## Struktur

```
python-ai/
├── app/
│   ├── main.py               # Aplikasi FastAPI, CORS, health check
│   ├── config.py             # Pembacaan .env
│   ├── database.py           # Koneksi MySQL (SQLAlchemy)
│   ├── schemas.py            # Model request/response Pydantic
│   ├── routers/
│   │   ├── chat.py           # /api/chat/*
│   │   └── documents.py      # /api/docs/*
│   ├── services/
│   │   ├── rag_service.py         # Retrieval + penyusunan jawaban
│   │   ├── embedding_service.py   # Chunking + embedding + ChromaDB
│   │   ├── pdf_processor.py       # Ekstraksi PDF + OCR
│   │   └── document_processor.py  # Deteksi jenis dokumen
│   └── tasks/
│       └── process_document.py    # Tugas Celery untuk ingest
├── data/chromadb/            # Basis data vektor (tidak di-commit)
├── requirements.txt          # Dependensi terkurasi
├── requirements.lock.txt     # Penutupan lengkap, untuk reproduksi persis
└── analisa_dependensi.py     # Pembuat lock file
```

---

## Hal yang perlu diketahui

**`chromadb` wajib tetap di 0.5.x.** Isi `data/chromadb` ditulis dengan
format versi tersebut; chromadb 1.x memakai format berbeda, sehingga
menaikkan versinya berarti seluruh dokumen harus di-ingest ulang.

**`ragas` 0.4.3 tidak bisa di-import begitu saja.** Ia mengimpor
`langchain_community.chat_models.vertexai`, modul yang sudah dihapus dari
langchain-community 0.4.x. Penambalnya sudah ada di `test_ragas.py`
(fungsi `_patch_langchain_community_vertexai`, baris 139) dan berjalan
sebelum ragas di-import. **Skrip evaluasi baru harus memanggil penambal yang
sama.**

**Kebisingan telemetri ChromaDB.** chromadb 0.5.5 memanggil `posthog.capture()`
dengan tiga argumen, sedangkan posthog 7.x hanya menerima satu — hasilnya
setiap operasi ChromaDB menulis baris `Failed to send telemetry event ...`.
Tidak ada dampak fungsional. Peredamnya dipasang di `app/main.py` dan
`test_ragas.py`; skrip baru perlu mengulangnya.

**Menambah dokumen membatalkan indeks pencarian.** Indeks BM25 di-cache di
memori. Kesahihannya ditentukan dua penanda: jumlah vektor di ChromaDB, dan
berkas `data/chromadb/corpus_version.txt` yang ditulis ulang setiap kali ada
ingest atau penghapusan. Penanda kedua itulah yang membuat server API tahu
bahwa pekerja Celery — proses yang berbeda — baru saja mengubah korpus, termasuk
saat jumlah potongannya kebetulan sama seperti sebelumnya.

Berkas penanda ikut terhapus bila `data/chromadb/` dihapus; efeknya hanya satu
kali pembangunan ulang indeks, tidak ada data yang hilang.

**Ollama dan VRAM.** Model chat (4,4 GB) dan model vision (5,6 GB) bertukar
tempat di GPU bila ingest dan chat berjalan bersamaan. Selama keduanya tidak
dipakai serentak, ongkosnya kecil.

**Kehabisan memori saat menjawab.** Bila log memuat
`ggml_backend_cpu_buffer_type_alloc_buffer: failed to allocate buffer`, Ollama
gagal menyiapkan KV cache — RAM sistem, bukan VRAM. Layanan sudah menanganinya
dua lapis: jendela konteks dihitung dari panjang konteks yang sebenarnya
(bukan angka tetap), dan bila alokasi tetap gagal, permintaan diulang otomatis
dengan jendela separuhnya sampai batas 4096. Bila masih sering terjadi,
turunkan `LLM_MAX_NUM_CTX` di `.env`.

Yang membuat gejala ini membingungkan: kegagalannya bergantung pada apa yang
kebetulan sedang berjalan di mesin, jadi pertanyaan yang sama bisa berhasil
sekarang dan gagal lima menit kemudian.

**Halaman SOP yang kehilangan judulnya.** Model vision kadang menjatuhkan baris
`Nama SOP:` saat meng-OCR formulir SOP. Tanpa baris itu, halaman tersebut tidak
mendapat label `[Konteks: SOP ...]` dan praktis tidak bisa ditemukan lewat nama
prosedurnya — tanpa galat apa pun. Ekstraksi kini mendeteksi halaman yang
memuat `Nomor SOP` tetapi kehilangan `Nama SOP`, lalu mengulang OCR halaman itu
sampai dua kali; kalau tetap gagal, kejadiannya dicatat sebagai `ERROR` di log
alih-alih lolos diam-diam.
