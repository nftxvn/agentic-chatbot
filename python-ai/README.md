# AI Microservice — Agentic IT Support Copilot

Layanan FastAPI yang menjawab pertanyaan tentang dokumen SOP menggunakan RAG
(_Retrieval-Augmented Generation_) dengan LLM lokal via Ollama. Seluruh
pemrosesan berjalan di mesin sendiri — tidak ada isi dokumen yang dikirim ke
layanan pihak ketiga.

Dua tanggung jawab utamanya:

1. **Ingest** — menerima PDF dari Laravel, mengekstrak teksnya (termasuk OCR
   untuk halaman hasil pindai), memecahnya jadi potongan, lalu menyimpannya
   sebagai vektor di ChromaDB.
2. **Tanya-jawab** — mencari potongan yang relevan lalu menyusun jawaban
   dengan LLM, disertai rujukan halaman sumbernya.

> Rancangan retrieval-nya dijelaskan terpisah di
> [`docs/05-arsitektur-rag-python-ai.md`](../docs/05-arsitektur-rag-python-ai.md).

---

## Prasyarat

| Kebutuhan                    | Versi     | Catatan                                  |
| ---------------------------- | --------- | ---------------------------------------- |
| Python                       | **3.10+** | Kode memakai sintaks `list[int] \| None` |
| [Ollama](https://ollama.com) | terbaru   | Mesin LLM & OCR                          |
| MySQL                        | 8.0+      | Dipakai bersama `laravel-admin`          |
| Redis                        | 6+        | Broker antrean Celery                    |

Tesseract **tidak** dibutuhkan. OCR dikerjakan model vision lewat REST API
Ollama (`app/services/ocr/vision.py::vision_extract_general`), bukan mesin OCR terpisah.

Tarik dua model Ollama berikut:

```bash
ollama pull qwen3:8b               # chat, ekstraksi kata kunci
ollama pull qwen2.5vl:7b-q4_K_M    # OCR halaman pindai
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
Mulailah dari `.env.example` — di sana setiap variabel sudah berkomentar, dan
setelan yang bergantung perangkat keras ditandai `[MESIN]`:

```bash
cp .env.example .env
```

> **Isi `LLM_MODEL_NAME`, `VISION_MODEL_NAME`, dan `EMBEDDING_MODEL_NAME` secara
> eksplisit.** Nilai default di `app/config.py` masih menunjuk model lama
> (`qwen2.5:7b`, MiniLM). Pilihan model runtime dapat berbeda melalui `.env` dan pengaturan chatbot di Laravel.

| Variabel                      | Contoh                      | Keterangan                                                                                                                                                                                |
| ----------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `LLM_MODEL_NAME`              | `qwen3:8b`                  | Model chat & ekstraksi kata kunci                                                                                                                                                         |
| `OLLAMA_BASE_URL`             | `http://localhost:11434`    | Alamat server Ollama                                                                                                                                                                      |
| `VISION_MODEL_NAME`           | `qwen2.5vl:7b-q4_K_M`       | Model OCR halaman pindai                                                                                                                                                                  |
| `VISION_TIMEOUT`              | `1000`                      | Detik. OCR di CPU bisa sangat lambat                                                                                                                                                      |
| `EMBEDDING_MODEL_NAME`        | `BAAI/bge-m3`               | Diunduh otomatis saat pertama dipakai. Menggantinya wajib diikuti reindex seluruh dokumen                                                                                                 |
| `EMBEDDING_DEVICE`            | `auto`                      | **[MESIN]** `auto` \| `cpu` \| `cuda`. Setel `cpu` hanya bila VRAM diperebutkan dengan LLM — bge-m3 memakan 2272 MiB                                                                      |
| `CHROMA_PERSIST_DIR`          | `./data/chromadb`           | Lokasi basis data vektor                                                                                                                                                                  |
| `MYSQL_HOST` `MYSQL_PORT`     | `localhost` `3306`          | Basis data bersama Laravel                                                                                                                                                                |
| `MYSQL_DATABASE`              | `agentic_copilot`           |                                                                                                                                                                                           |
| `MYSQL_USER` `MYSQL_PASSWORD` |                             |                                                                                                                                                                                           |
| `CELERY_BROKER_URL`           | `redis://localhost:6379/0`  | Antrean tugas                                                                                                                                                                             |
| `CELERY_RESULT_BACKEND`       | `redis://localhost:6379/1`  |                                                                                                                                                                                           |
| `INTERNAL_API_TOKEN`          |                             | Token Bearer untuk seluruh endpoint internal                                                                                                                                              |
| `CHAT_STREAM_REQUIRE_AUTH`    | `true`                      | Penjaga token di `/api/chat/stream`. Setel `false` hanya untuk pengembangan lokal                                                                                                         |
| `LLM_NUM_CTX`                 | `8192`                      | Jendela konteks LLM (dipatok, sama untuk semua panggilan). Naikkan hanya setelah VRAM bebas + `OLLAMA_KV_CACHE_TYPE=q8_0`                                                                 |
| `LLM_NUM_GPU`                 | `0`                         | **[MESIN]** Jumlah layer dipaksa ke GPU; `0` = auto-fit Ollama. Isi `99` hanya di mesin yang anggaran VRAM-nya sudah diukur — nilai kelewat tinggi tidak memberi galat, tapi memperlambat |
| `CORS_ALLOW_ORIGINS`          | `http://localhost:5173,...` | Origin yang boleh memanggil dari browser, dipisah koma. Jangan diisi `*`                                                                                                                  |
| `DEBUG_DUMP_CONTEXT`          | `false`                     | Menulis konteks retrieval ke `debug_context.txt` tiap pertanyaan. Jangan diaktifkan di produksi                                                                                           |
| `GEMINI_API_KEY`              |                             | **Hanya untuk evaluasi RAGAS.** Layanan berjalan normal tanpa ini                                                                                                                         |

**Kalau pemuatan model embedding terasa lama.** `sentence_transformers`
memeriksa pembaruan ke huggingface.co setiap kali dimuat, walau modelnya
sudah lengkap di cache. Bila jaringan lambat atau diblokir, pemeriksaan itu
habis waktu lalu diulang lima kali dengan jeda menaik — satu sampai dua menit
terbuang setiap skrip mulai, untuk akhirnya memakai berkas yang sejak awal
ada di disk.

Obatnya `HF_HUB_OFFLINE=1` di `.env`. **Sengaja tidak dinyalakan otomatis:**
`transformers` memanggil `model_info()` tanpa syarat saat memeriksa jenis
tokenizer, dan dalam mode luring panggilan itu _melempar_ `OfflineModeIsEnabled`
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# 4. Pekerja Celery (terminal terpisah)
celery -A app.tasks.process_document.celery_app worker --loglevel=info --pool=solo
```

Dua catatan penting soal perintah Celery:

- Path **`app.tasks.process_document.celery_app`** sama dengan launcher dan
  Docker Compose. `app/celery_app.py` membuat instance bersama; impor melalui
  `app.tasks.process_document` sekaligus mendaftarkan ketiga task dokumen.
  Alias `app.tasks.celery` tetap tersedia melalui `app/tasks/__init__.py`.
  Gunakan path worker yang ditulis di atas agar registrasi task ikut dimuat.
- `--pool=solo` diperlukan di Windows. Di Linux boleh dihilangkan.

Setelah jalan:

- API — <http://localhost:8080>
- Dokumentasi interaktif — <http://localhost:8080/docs>
- Health check — <http://localhost:8080/health>

---

## Endpoint

| Metode | Rute                    | Auth      | Fungsi                                   |
| ------ | ----------------------- | --------- | ---------------------------------------- |
| `POST` | `/api/chat/stream`      | Bearer¹   | Tanya-jawab streaming (SSE) untuk widget |
| `POST` | `/api/chat/message`     | Bearer    | Tanya-jawab sekali balas untuk WhatsApp  |
| `GET`  | `/api/docs`             | Bearer    | Daftar seluruh dokumen                   |
| `GET`  | `/api/docs/{id}/status` | Bearer    | Status pemrosesan satu dokumen           |
| `POST` | `/api/docs/{id}/extraction` | Bearer | Mulai atau lanjutkan OCR bertahap |
| `POST` | `/api/docs/{id}/extraction/pause` | Bearer | Minta jeda pada batas halaman |
| `GET` | `/api/docs/{id}/extraction` | Bearer | Status/progres ekstraksi |
| `GET` | `/api/docs/{id}/extraction/stream` | Bearer | Progres ekstraksi melalui SSE |
| `GET` / `PUT` | `/api/docs/{id}/pages` / `/api/docs/{id}/pages/{n}` | Bearer | Baca teks / simpan koreksi |
| `GET` / `POST` | `/api/docs/{id}/chunks/preview` | Bearer | Pratinjau pemotongan |
| `POST` | `/api/docs/{id}/embed` | Bearer | Antrekan embedding hasil koreksi |
| `POST` | `/api/docs/{id}/cancel` | Bearer | Cleanup pembatalan; lihat batas antrean di bawah |
| `GET`  | `/health`               | tidak ada | Health check                             |
| `GET`  | `/api/health`           | tidak ada | Alias health check                       |
| `GET`  | `/api/health/hardware`  | Bearer    | Diagnostik mesin dan estimasi model       |

¹ Bisa dimatikan lewat `CHAT_STREAM_REQUIRE_AUTH=false` untuk pengembangan lokal.

Permintaan tanpa header `Authorization` dijawab **401**, bukan 422 — pemanggil
seperti Laravel bisa mengandalkan kode itu untuk membedakan "tidak punya
kredensial" dari "payload-nya salah bentuk".

Bentuk payload dan responsnya ada di
[`docs/03-api_spec_agentic_copilot.md`](../docs/03-api_spec_agentic_copilot.md).

> **Widget di browser tidak boleh memegang `INTERNAL_API_TOKEN`.** Token yang
> sama juga membuka `/api/docs/*`, dan apa pun yang masuk ke JavaScript sisi
> klien bisa dibaca lewat devtools. Jalur yang benar untuk produksi: widget
> memanggil Laravel, Laravel meneruskannya ke layanan ini dengan token yang
> disimpan di sisi server.

---

## Evaluasi mutu jawaban

Gunakan korpus serta pertanyaan yang sama untuk membandingkan hasil sebelum dan sesudah perubahan model atau algoritme. Skrip yang tersedia untuk merekam jawaban adalah `jawab_rag.py`:

```bash
python jawab_rag.py "Apa persyaratan layanan dalam dokumen ini?" --keluaran hasil_rag.md
python jawab_rag.py --berkas pertanyaan.txt --keluaran hasil_perbandingan.md
```

Satu pertanyaan per baris pada `pertanyaan.txt`; baris kosong dan komentar `#` dilewati. Skrip memanggil pipeline nyata dan menyimpan jawaban beserta durasi, sehingga memerlukan konfigurasi database, Redis, Ollama, serta korpus yang sudah di-ingest. Skrip ini tidak memberikan skor kebenaran otomatis. Cocokkan fakta, jumlah item, halaman sumber, dan penolakan atas informasi yang memang tidak ada dengan dokumen asli.

Dokumen arsitektur masih menyimpan catatan evaluasi pengembangan lama. Berkas `evaluasi_sederhana.py`, `test_ragas.py`, dan dataset `reference_eval_*.json` tidak tersedia pada checkout ini; perintah serta angka hasil lamanya tidak menjadi bukti pengujian versi sekarang.

---

## Pengujian

```bash
python -m unittest discover -s tests
```

Tes yang tersedia pada checkout ini:

- `tests/test_security.py`: bearer token, penolakan kredensial, dan pengaturan autentikasi stream untuk pengembangan lokal.
- `tests/test_backend_client.py`: payload handoff tiket ke Laravel serta penanganan kegagalan pengiriman.
- `tests/test_source_references.py`: format halaman sitasi retrieval, kompatibilitas separator lama, judul dengan tanda hubung, serta resolusi ID yang unik dalam scope dokumen permintaan.
- `tests/test_rag_contract.py`: filter dokumen, RRF, cache BM25, retrieval flat/hierarkis, reranker, penjaga konteks, daftar lengkap, sitasi, riwayat percakapan, fallback alokasi memori, parameter sandbox, dan pembungkus event SSE.
- `tests/test_ocr_regression.py`: prioritas/cache model vision, komposisi prompt, retry HTTP/hasil kosong, kepala SOP/NIP, pemulihan daftar, render PDF tiruan, serta jalur native/gambar tertanam.
- `tests/test_routing_extraction_regression.py`: prioritas handoff/direktori/FAQ/RAG, normalisasi, ekstraksi data warga, cache anchor, kalkulator, simpan-jeda-resume, batas halaman, kegagalan OCR, retry Celery, serta antrean batch lanjutan.
- `tests/test_health_contract.py`: respons HTTP health/hardware, autentikasi sebelum membaca cache, TTL, probe dependensi, parser hardware, serta perhitungan rekomendasi/model-fit.
- `tests/test_database_contract.py`: parameter SQL, opsi engine, metadata dokumen, konversi/fallback pengaturan, cache direktori/FAQ, serta debounce log.
- `tests/test_vector_store_client.py`: pilihan embedded/HTTP, cache client lazy, metadata cosine, serta kegagalan server eksplisit tanpa fallback ke korpus lokal lain.
- `tests/test_document_operations.py`: token operasi persisten, lock satu koneksi, cancel/resume, status/progres generasi lama, serta perlindungan korpus yang telah selesai.
- `tests/test_vector_cancellation.py`: pembatalan saat encoding, otorisasi upsert/delete, callback di luar lock, serta cleanup vektor hanya untuk token yang dibatalkan.
- `tests/test_vector_cleanup.py`: outbox persisten, retry/backoff, rollback fence/cleanup, dokumen terhapus, perlindungan generasi baru, serta reset ekstraksi yang terlambat.
- `tests/test_document_workflows.py`: HTTP dokumen/ekstraksi, prioritas opsi kategori, simpan koreksi, konflik embedding, preview, citra/cache, SSE, urutan cancel, serta retry dan batas worker.
- `tests/test_task_workflows.py`: cleanup lintas halaman sebelum review, retry gambar, dan penghentian penulisan/progres ketika dokumen dihapus.

Dependency jaringan digantikan mock pada tes ini; tidak ada koneksi MySQL, Redis, ChromaDB, unduhan model, atau inferensi Ollama. Paket aplikasi tetap harus terpasang karena modul layanan diimpor. Ini menguji kontrak kode, bukan kualitas jawaban model atau integrasi worker yang berjalan.

Nama lama `test_rag_units.py` dan `test_api_kontrak.py` yang pernah disebut dalam dokumentasi tidak tersedia pada checkout ini. Tes health memeriksa kontrak HTTP dan konfigurasi middleware dengan dependensi tiruan. Pengujian integrasi antarlayanan, CORS melalui browser, probe mesin/database nyata, OCR nyata, dan mutu model perlu dijalankan tersendiri dengan lingkungan yang sesuai.

Smoke test layanan nyata yang terisolasi tersedia di
[`../scripts/integration/README.md`](../scripts/integration/README.md).
Runner memakai instance MySQL/Redis baru, storage/Chroma sementara, dan model
Ollama lokal yang sudah terpasang. Hasilnya dicatat terpisah dari tes unit.

Callback handoff menerima `LARAVEL_BASE_URL`, misalnya
`http://127.0.0.1:8000`. Bila diberikan, callback hanya mencoba instance tersebut;
kegagalan tidak diteruskan ke instance lain. Nilai kosong mempertahankan daftar
discovery Docker/local lama. `.env.example` membiarkannya kosong agar deployment
yang belum mengatur alamat eksplisit tetap memakai perilaku lama.

Sitasi JSON mengenali suffix halaman dari retrieval (` - Halaman ...`) dan
separator em dash lama. Nama hanya dipetakan ke ID jika cocok secara tepat dan
unik dalam `document_ids` permintaan. Judul duplikat, tidak cocok, atau tanpa
scope tetap dapat menghasilkan `document_id: null`; nomor halaman tetap dibaca
bila tersedia. Teks jawaban dan protokol SSE tetap sama.

### Pemeliharaan health dan database

`app/main.py` merakit aplikasi, lifecycle, dan CORS. HTTP serta cache health berada di `app/routers/health.py`; probe dan kalkulasi hardware berada di `app/services/diagnostics/`.

- `/health` dan `/api/health` berbagi cache per proses selama 5 detik, termasuk hasil gagal. Semua probe berhasil menghasilkan HTTP 200/`healthy`; satu kegagalan menghasilkan HTTP 503/`degraded`. Koleksi ChromaDB kosong tetap sehat bila dapat dibaca. Ollama diperiksa terhadap model dari konfigurasi environment.
- Diagnostik hardware selalu memeriksa bearer token sebelum handler/cache. TTL efektifnya 3 detik; `nocache=true` memaksa pembacaan ulang. Pada cache aktif, parameter `model` hanya menghitung ulang `model_fit`, sementara konfigurasi dan rekomendasi tetap berasal dari snapshot tersimpan. Konstanta lama `_MESIN_CACHE_TTL=10` tetap diekspor untuk kompatibilitas, tetapi tidak dipakai kondisi cache.
- Pembacaan NVIDIA memakai GPU pertama. Angka RAM/VRAM dilaporkan dalam MiB; rekomendasi kapasitas merupakan estimasi dengan aturan yang sama seperti sebelum pemisahan modul, bukan hasil benchmark inferensi.

`app/database.py` menyediakan ekspor kompatibilitas; implementasi query berada di `app/repositories/`. `connection.py` memiliki satu engine lazy per proses (`pool_pre_ping=True`, `pool_size=5`, `max_overflow=10`, `pool_recycle=3600`). SQL, parameter, dan transaksi tetap sama. `directories.py` memiliki cache FAQ/direktori terpisah selama 5 detik; bila pembacaan gagal, nilai cache lama tetap dikembalikan tanpa memperbarui timestamp.

`settings.py` mempertahankan fallback seluruh konfigurasi RAG bila query atau konversi nilai gagal. `document_logs.py` mempertahankan debounce 15 detik dan menangani kegagalan query; kegagalan pembuatan engine pada `get_app_setting` dan `record_document_log` tetap dapat diteruskan ke pemanggil.

Saat membuat mock, patch dependency pada modul yang menggunakannya, misalnya `app.repositories.documents.get_engine` atau `app.routers.health._baca_nvidia_smi`. Ekspor lama adalah alias fungsi, bukan salinan engine/cache.

---

## Struktur

```
python-ai/
├── app/
│   ├── main.py               # Perakitan FastAPI, lifecycle, dan CORS
│   ├── config.py             # Pembacaan .env
│   ├── celery_app.py         # Instance Celery bersama; registrasi melalui app.tasks
│   ├── database.py           # Ekspor query MySQL yang kompatibel
│   ├── repositories/
│   │   ├── connection.py     # Engine SQLAlchemy lazy per proses
│   │   ├── documents.py      # Status, metadata, dan nama sitasi
│   │   ├── settings.py       # Pengaturan tunggal dan konfigurasi RAG
│   │   ├── directories.py    # FAQ/direktori beserta cache
│   │   └── document_logs.py  # Log dokumen dan debounce
│   ├── schemas.py            # Model request/response Pydantic
│   ├── routers/
│   │   ├── chat.py           # /api/chat/*
│   │   ├── documents.py      # HTTP daftar/status, chunk, citra, cleanup, prompt
│   │   ├── ekstraksi.py      # Ekstraksi bertahap, koreksi, preview, embedding
│   │   └── health.py         # Health publik, hardware bertoken, cache respons
│   ├── services/
│   │   ├── vector_cleanup.py     # Outbox cleanup SQL, retry background dan CLI
│   │   ├── document_workflows/   # Query/lifecycle/citra/prompt dan kendali/koreksi/chunk
│   │   ├── task_workflows/       # Legacy ingest, OCR bertahap, embedding, cleanup
│   │   ├── diagnostics/
│   │   │   ├── health.py          # Probe ChromaDB, MySQL, Redis, Ollama
│   │   │   └── hardware.py        # Pembacaan mesin dan estimasi kapasitas
│   │   ├── rag_service.py         # Orkestrasi chat, routing, memory, dan ekspor kompatibilitas
│   │   ├── rag/
│   │   │   ├── retrieval.py       # Hybrid search, BM25, reranking, sitasi
│   │   │   ├── grounding.py       # Penjaga konteks, enumerasi, petunjuk perbandingan/waktu
│   │   │   ├── generation.py      # Streaming Ollama dan fallback alokasi memori
│   │   │   └── prompts.py         # Prompt bawaan, tanggal, profil instansi
│   │   ├── backend_client.py      # Handoff tiket ke Laravel
│   │   ├── embedding_service.py   # Ekspor kompatibilitas embedding/chunking/vektor
│   │   ├── embeddings/
│   │   │   ├── models.py          # Encoder, reranker, dan fallback Ollama
│   │   │   ├── chunking.py        # Judul/konteks halaman dan parent-child chunking
│   │   │   ├── vector_store.py    # Koleksi ChromaDB, baca/hapus/upsert vektor
│   │   │   └── corpus.py          # Versi korpus dan invalidasi indeks BM25
│   │   ├── ekstraksi_bertahap.py  # Ekspor kompatibilitas workflow dan penyimpanan
│   │   ├── extraction/
│   │   │   ├── contracts.py       # Status, protokol Penyimpanan, dan Kemajuan
│   │   │   ├── workflow.py        # Ekstraksi per halaman, jeda/resume, flush cache
│   │   │   ├── mysql_storage.py   # Halaman/job MySQL dan progres embedding Redis
│   │   │   └── memory_storage.py  # Penyimpanan CLI satu proses
│   │   ├── pdf_processor.py       # Ekspor kompatibilitas PDF/OCR
│   │   ├── ocr/
│   │   │   ├── pdf_io.py          # Path, render editor, ukuran, deteksi, teks native
│   │   │   ├── prompts.py         # Prompt OCR dan petunjuk kategori/formulir
│   │   │   ├── vision.py          # Pemilihan model, cache autodeteksi, request/retry
│   │   │   ├── sop.py             # Deteksi SOP dan pemeriksaan kepala/NIP
│   │   │   ├── cleanup.py         # Pembersihan teks dan pemulihan penanda daftar
│   │   │   └── pipeline.py        # Gambar tertanam, OCR per halaman, pewarisan petunjuk
│   │   ├── tool_router.py         # Ekspor kompatibilitas intent dan tool
│   │   ├── routing/
│   │   │   ├── dispatch.py        # Urutan pemilihan intent dan payload routing
│   │   │   ├── language.py        # Slang, filler, keyword, penjaga kalimat tanya
│   │   │   ├── patterns.py        # Pola sapaan, handoff, rangkuman, koreksi
│   │   │   ├── semantic.py        # Cache anchor dan klasifikasi semantik
│   │   │   ├── citizen.py         # Ekstraksi nama, instansi, dan kendala
│   │   │   └── calendar.py        # Parsing tanggal/durasi dan hari kerja
│   │   └── document_processor.py  # Deteksi jenis dokumen
│   └── tasks/
│       ├── process_document.py    # Ingest sekali jalan dan registrasi task
│       └── ekstraksi.py           # Task OCR bertahap dan potong/embed
├── data/chromadb/            # Basis data vektor (tidak di-commit)
├── requirements.txt          # Dependensi terkurasi
└── requirements.lock.txt     # Penutupan lengkap, untuk reproduksi persis
```

---

## Batas pipeline dokumen

Pemanggil yang sudah ada tetap memakai `app.services.embedding_service` dan
`app.services.ekstraksi_bertahap`. Modul tersebut meneruskan fungsi, kelas,
dan konstanta ke pemilik implementasinya; jangan membuat salinan cache model
atau koleksi di modul kompatibilitas.

| Bagian | Perilaku yang dipertahankan |
| --- | --- |
| Ekstraksi bertahap | Halaman yang sudah tersimpan dilewati. Hasil OCR dan petunjuk format disimpan sebelum pemeriksaan jeda sesudah halaman. Batas `maks_halaman` dapat menjadwalkan task lanjutan. |
| Penyimpanan | `PenyimpananMySQL` tetap memakai `ekstraksi_job`/`ekstraksi_halaman` dari migrasi Laravel. SQL upsert dan perhitungan progres tetap sama; `PenyimpananMemori` hanya untuk CLI satu proses. |
| Koreksi | Task OCR berhenti pada `menunggu_koreksi`. Pemulihan penanda daftar lintas halaman dilakukan setelah seluruh halaman terkumpul; embedding dijalankan melalui task terpisah setelah tindakan admin. |
| Chunking | Parent 1500/overlap 200, child 300/overlap 50 secara bawaan. Daftar minimal 10 item memakai jalur khusus dengan batas blok 6000 karakter. Judul/label dan opsi custom tetap mengikuti algoritme lama. |
| Embedding | Urutan fallback: Ollama → SentenceTransformer dari cache lokal → unduhan SentenceTransformer sebagai pilihan terakhir. Ukuran batch dan bentuk payload Ollama tetap sama. |
| Vektor | Koleksi `documents` memakai cosine. Parent dan child tetap di-embed; ID `doc_{id}_parent_{index}`/`doc_{id}_child_{index}` serta metadata dan callback progres tetap sama. |
| Invalidasi | Perubahan korpus menulis `corpus_version.txt` pada `CHROMA_PERSIST_DIR` dan membatalkan cache BM25 proses saat ini. Penanda versi tetap diperlukan ketika ingest berjalan di proses Celery. |

Cache encoder/reranker dimiliki `embeddings/models.py`; koleksi ChromaDB
dimiliki `embeddings/vector_store.py`; cache BM25 dimiliki `rag/retrieval.py`.
Ketiganya tetap lazy. `.env` dimuat sebelum dependency model membaca mode
Hugging Face offline. Pemisahan modul tidak memindahkan data, memuat model saat
impor, mengubah prompt OCR, atau mengganti skema database.

Konfigurasi Celery tetap memakai JSON, zona `Asia/Jakarta`, acknowledgment
setelah task selesai, prefetch 1, dan concurrency 1. Nama task tetap
`process_document_task`, `ekstrak_dokumen_task`, serta `potong_dan_embed_task`;
payload dan aturan retry masing-masing task tetap dipertahankan. Modul task
memiliki registrasi/decorator dan meneruskan task instance serta collaborator
ke `services/task_workflows/`; workflow mempertahankan urutan status, retry,
penjadwalan lanjutan, dan penulisan vektor.

Router `documents.py` dan `ekstraksi.py` mempertahankan signature, dependency
autentikasi, dan schema request/response. Metadata OpenAPI cancel menyatakan
pembatalan kooperatif. Implementasi berada
di `services/document_workflows/`: `document_queries`, `document_lifecycle`,
`document_pages`, `document_prompts`, `extraction_control`,
`extraction_corrections`, dan `extraction_chunks`. Helper lookup/storage
ekstraksi dimiliki `extraction_control`; modul koreksi/chunk memakai helper itu.
Saat membuat mock, patch dependency pada modul workflow yang menggunakannya.

Pembatalan sekarang menggunakan `document_operations.py` dengan kolom
`documents.processing_token` dan `cancellation_requested`. Setiap mulai/resume
atau embedding memperoleh token baru; task, retry dan kelanjutan membawa
`_operation_token`. Cancel menandai hanya dokumen tersebut dan mempertahankan
token yang dibatalkan agar cleanup dapat diulang. Tidak ada purge antrean atau
unload model bersama dari endpoint cancel.

OCR/encoding berjalan di luar lock. Penyimpanan halaman, status, audit dan
mutasi vektor memvalidasi token di dalam transaksi yang mengunci baris dokumen.
Hasil operasi lama tidak dapat ditulis setelah cancel atau menggantikan hasil
resume. Panggilan model yang sedang berjalan tidak dibunuh; worker membuang
hasilnya pada batas aman berikutnya. Callback progres berjalan setelah lock
upsert dilepas agar tidak membuka transaksi lain sambil menahan lock yang sama.

Vektor worker diberi metadata `operation_token`. Cleanup menggunakan filter
document ID dan token, dengan lock yang sama, sehingga tidak menghapus generasi
baru atau dokumen lain. Cancel setelah pekerjaan selesai mempertahankan korpus
yang telah selesai; timestamp `processed_at` dibersihkan saat operasi baru
dimulai. Penggantian korpus belum merupakan transaksi atomik lintas MySQL/Chroma:
bila penyimpanan vektor tidak tersedia, fence database tetap berlaku dan cleanup
tetap tercatat pada outbox `document_vector_cleanups`. Resume setelah cancel
parsial boleh membuat token baru; retry cleanup lama tetap memakai token lama.

`services/vector_cleanup.py` memiliki penyimpanan request dan drainer. Laravel
menulis request di transaksi yang sama dengan fence sebelum HTTP Python, dan
Python juga menulisnya saat cancel/delete langsung. Tidak ada FK cascade ke
`documents`: cleanup tetap ada setelah dokumen dihapus. Token kosong berarti
cleanup seluruh dokumen untuk replace/delete, termasuk vektor lama tanpa token.
Mulai/resume/embedding baru ditahan sampai cleanup penuh selesai; handler
mencoba cleanup segera dan mengembalikan HTTP 503 bila masih tertunda. Setelah
layanan pulih, lanjutkan dokumen melalui endpoint yang sudah ada.

Lifespan FastAPI menguras maksimal 10 request saat startup dan setiap 30 detik
melalui thread, tanpa bergantung pada broker Celery. Request gagal tetap ada,
dengan `attempts`, `last_error` (nama kelas exception), dan jadwal retry UTC
30/60/120/240/300 detik. Lock diambil dengan urutan dokumen lalu outbox;
penghapusan Chroma memakai predicate asli, dan acknowledgement SQL dilakukan
setelah operasi vektor serta pemanggilan invalidasi cache. Pengulangan setelah
acknowledgement gagal aman, termasuk ketika vektor sudah tidak ada. Callback
reset ekstraksi pada DELETE memeriksa flag cancellation di bawah lock agar
tidak menghapus halaman dari generasi yang telah dilanjutkan.

Retry manual saat diperlukan, dari direktori `python-ai` dengan konfigurasi
database/Chroma yang sesuai (hanya memproses request yang sudah tercatat):

```bash
venv/bin/python -m app.services.vector_cleanup --limit 100
venv/bin/python -m app.services.vector_cleanup --document-id 42 --limit 100
```

CLI mengabaikan backoff untuk retry eksplisit, mencetak jumlah selesai/gagal/
vektor terhapus, dan keluar nonzero bila ada cleanup yang gagal. Retry otomatis
memerlukan proses FastAPI hidup; worker Celery saja tidak menguras outbox.
Jangan menghapus request tertunda secara manual untuk melewati gate generasi.
Vektor orphan masih dapat berada di Chroma selama outage; outbox memberi
pemulihan eventual, bukan pergantian korpus atomik atau filter retrieval baru.

**Urutan rollout:** migrasi
`2026_10_25_000001_add_document_operation_fences.php` dan
`2026_10_25_000002_create_document_vector_cleanups_table.php` harus tersedia sebelum
API/worker baru dijalankan. Selesaikan/hentikan worker versi lama, jalankan
`php artisan migrate` pada database deployment yang benar, lalu jalankan API dan
worker yang menggunakan protokol token bersama. Task lama yang tidak membawa
token ditolak sebelum akses database/model; mulai ulang dokumennya melalui
endpoint mulai/resume. Jangan melakukan purge antrean bersama untuk migrasi ini.
Pengujian hanya menjalankan migrasi pada database sementara, bukan database
operasional. Pemanggilan helper Python langsung tanpa guard tidak termasuk
koordinasi task; semua entry point worker aplikasi selalu memakai guard.

Kompilasi/import dan perbandingan struktur kode hanya memeriksa susunan modul.
OCR nyata, kualitas embedding, SQL MySQL, progres Redis, serta eksekusi worker
perlu diperiksa tersendiri dengan layanan dan data yang sesuai.

---

## Hal yang perlu diketahui

**Versi ChromaDB saat ini dipatok ke 1.5.9** di `requirements.txt` dan
`requirements.lock.txt`. Sebelum mengubah versi, buat cadangan `data/chromadb`
dan uji indeks yang sudah ada dengan versi target. Bila format penyimpanan tidak
kompatibel, indeks perlu dibangun ulang dari dokumen sumber.

**API dan worker terpisah memakai satu server Chroma.** Pengujian integrasi
menemukan kegagalan query segmen HNSW ketika API membuka koleksi embedded kosong
lalu worker lain menulis indeks pada path yang sama. Gunakan mode HTTP untuk
profil beberapa proses:

```bash
chroma run --path ./data/chromadb --host 127.0.0.1 --port 9090
# .env yang sama untuk FastAPI dan Celery:
# CHROMA_HTTP_HOST=127.0.0.1
# CHROMA_HTTP_PORT=9090
# CHROMA_HTTP_SSL=false
```

Hentikan pemakai embedded sebelum membuka datadir tersebut melalui server.
Host kosong mempertahankan `PersistentClient` lama; host eksplisit memilih
`HttpClient` dan kegagalan koneksi tidak beralih ke database lokal lain.
`CHROMA_PERSIST_DIR` tetap menjadi lokasi penanda versi korpus yang harus
terlihat oleh API dan worker, termasuk ketika database vektor diakses lewat
HTTP. Mode server serta client dijelaskan pada
[dokumentasi resmi Chroma](https://docs.trychroma.com/production/chroma-server/client-server-mode).
Launcher/Compose lama tetap perlu dikonfigurasi untuk profil ini; runner
integrasi melakukannya pada layanan sementara tanpa mengubah `.env` aplikasi.

**Evaluasi RAGAS.** Dependensi evaluasi tercantum dalam requirements, tetapi skrip evaluasi dan penambal kompatibilitas lama tidak tersedia pada checkout ini. Periksa kompatibilitas paket dan ketersediaan dataset sebelum menambahkan alur evaluasi baru.

**Kebisingan telemetri ChromaDB.** `app/main.py` menurunkan level log dari
telemetri ChromaDB dan dependensinya agar kegagalan pengiriman statistik tidak
menutupi log aplikasi. Jangan menyalin konfigurasi itu ke skrip baru tanpa
memastikan skrip tersebut memang perlu menonaktifkan log telemetri.

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
gagal menyiapkan KV cache — RAM sistem, bukan VRAM. `num_ctx` dipatok ke
`LLM_NUM_CTX`; bila alokasi gagal sebelum jawaban mulai mengalir, permintaan
dicoba SEKALI lagi pada 4096 lalu galat dinaikkan. Bila sering terjadi,
turunkan `LLM_NUM_CTX` di `.env`, atau bebaskan VRAM dan aktifkan
`OLLAMA_KV_CACHE_TYPE=q8_0` di systemd Ollama.

**Halaman SOP yang kehilangan judulnya.** Model vision kadang menjatuhkan baris
`Nama SOP:` saat meng-OCR formulir SOP. Tanpa baris itu, halaman tersebut tidak
mendapat label `[Konteks: SOP ...]` dan praktis tidak bisa ditemukan lewat nama
prosedurnya — tanpa galat apa pun. Ekstraksi kini mendeteksi halaman yang
memuat `Nomor SOP` tetapi kehilangan `Nama SOP`, lalu mengulang OCR halaman itu
sampai dua kali; kalau tetap gagal, kejadiannya dicatat sebagai `ERROR` di log
alih-alih lolos diam-diam.

## Batas PDF/OCR dan routing intent

`pdf_processor.py` dan `tool_router.py` tetap menjadi titik masuk bagi router,
worker, adaptor format dokumen, dan RAG. Implementasi di `ocr/` dan `routing/`
mempertahankan signature fungsi, konstanta prompt, aturan, serta bentuk keluaran.

| Bagian | Perilaku yang dipertahankan |
| --- | --- |
| Halaman native | Teks minimal 300 karakter menggunakan jalur native. Gambar tertanam yang memenuhi aturan ukuran/signifikansi tetap dapat dibaca melalui vision. |
| Render editor | `ocr/pdf_io.py::render_halaman` memakai zoom bawaan 2.0; zoom API hanya 1.5/2/3/4. Sisi terpanjang dibatasi 2560 piksel dan JPEG memakai kualitas 80. |
| Render OCR PDF | `ocr/pipeline.py::_ekstrak_halaman` memakai zoom 1.5 dengan batas sisi 2048 piksel dan JPEG kualitas 85. Jalur ini tetap berbeda dari render editor. |
| Pemilihan model | Model eksplisit kategori/payload → pengaturan global vision → autodeteksi Ollama dengan cache 60 detik → fallback konfigurasi. Cache hanya dimiliki `ocr/vision.py`. |
| Prompt | Prompt dasar/custom `dasar` → tambahan kategori → istilah/jabatan → petunjuk format. Alias `{kata_kunci}` dan `{job_titles}` tetap didukung. Petunjuk tabel diwariskan; petunjuk kepala hanya dipakai ketika kepala terlihat. |
| Penjaga SOP | Hasil yang memuat `Nomor SOP` tetapi kehilangan `Nama SOP` atau NIP dapat diulang dua kali lagi. Bila tetap tidak lengkap, hasil terbaik tetap dikembalikan dan kehilangan bagian dicatat sebagai error. |
| Routing | Bentuk hasil tetap `{intent, params, label}`. Urutan rangkuman, handoff, sapaan/follow-up, verifikasi dokumen, kalkulator, direktori, FAQ, dan RAG tetap sama. |
| Classifier | Anchor embedding tetap lazy dan disimpan pada `routing/semantic.py`; ambang handoff 0.80 disertai penjaga kalimat tanya, sedangkan rangkuman/sapaan memakai 0.75. |
| Kalkulator | Perhitungan hari kerja tetap memakai Senin–Jumat, dimulai setelah tanggal awal. Kalender libur nasional/cuti bersama belum dipakai, meskipun teks keluaran lama tetap dipertahankan. |

Logger tetap menggunakan nama `app.services.pdf_processor` dan
`app.services.tool_router` agar konfigurasi penyaringan log lama tetap cocok.
Mengimpor modul tidak menjalankan OCR, memuat model, mengisi cache anchor,
atau meminta daftar model Ollama. Pemanggilan fungsi yang bersangkutan tetap
memerlukan layanan/dependency runtime yang sama seperti sebelumnya.

Helper istilah kategori mempertahankan perilaku lama: bila satu prompt memuat
kedua alias `{kata_kunci}` dan `{job_titles}`, penggantian berhenti pada jenis
alias pertama yang ditemukan menurut urutan pemeriksaan tersebut. Gunakan satu
jenis placeholder dalam prompt bila keduanya dimaksudkan sebagai istilah yang sama.

## Struktur dan verifikasi

- `app/routers/` menangani HTTP; `app/security.py` menyediakan dependency
  autentikasi bearer yang dipakai router.
- `app/services/rag_service.py` tetap menjadi titik masuk `generate_response` dan `invalidate_bm25_cache` bagi router/worker. Implementasi terpisah berada di `app/services/rag/`; cache BM25 hanya dimiliki `retrieval.py`.
- `app/services/embeddings/` memisahkan model, chunking, penyimpanan vektor, dan invalidasi korpus. `embedding_service.py` tetap menyediakan titik masuk lama.
- `app/services/extraction/` memisahkan kontrak, workflow, dan penyimpanan progres. `ekstraksi_bertahap.py` tetap menyediakan kelas dan fungsi pada path lama.
- `app/services/ocr/` memisahkan akses PDF, prompt, komunikasi vision, pemeriksaan SOP, pembersihan teks, dan pipeline halaman. `pdf_processor.py` tetap menyediakan fungsi/konstanta pada path lama, termasuk konstanta prompt yang dibaca endpoint diagnostik.
- `app/services/routing/` memisahkan normalisasi bahasa, pola intent, klasifikasi semantik, data warga, kalkulasi waktu, dan dispatch. `tool_router.py` tetap menyediakan fungsi lama bagi RAG dan session memory.
- Prompt, ambang retrieval, format sitasi, event debug/telemetri, serta urutan penjaga dipertahankan saat pemisahan modul.
- `app/services/backend_client.py` mengirim handoff tiket ke Laravel dan
  membentuk payload kontrak internal.
- `app/celery_app.py` membuat satu instance Celery; `app/tasks/` mendaftarkan task ingestion/ekstraksi dan tetap menjadi titik masuk worker.
- Jaga path HTTP, bentuk JSON/SSE, serta payload yang dipakai Laravel.

Jalankan tes unit tanpa Ollama/MySQL/Redis:

```bash
python -m unittest discover -s tests
```

Panduan batas kontrak dan pemeliharaan lintas aplikasi ada di
[`../docs/08-panduan-struktur-kode-dan-pemeliharaan.md`](../docs/08-panduan-struktur-kode-dan-pemeliharaan.md).
