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
| `INTERNAL_API_TOKEN` | | Token Bearer untuk endpoint internal |
| `GEMINI_API_KEY` | | **Hanya untuk evaluasi RAGAS.** Layanan berjalan normal tanpa ini |

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
| `POST` | `/api/chat/stream` | **tidak ada** | Tanya-jawab streaming (SSE) untuk widget |
| `POST` | `/api/chat/message` | Bearer | Tanya-jawab sekali balas untuk WhatsApp |
| `GET` | `/api/docs` | Bearer | Daftar seluruh dokumen |
| `GET` | `/api/docs/{id}/status` | Bearer | Status pemrosesan satu dokumen |
| `POST` | `/api/docs/process` | Bearer | Kirim dokumen ke antrean ingest |
| `GET` | `/health` | tidak ada | Health check |

Bentuk payload dan responsnya ada di
[`docs/04-api_spec_agentic_copilot.md`](../docs/04-api_spec_agentic_copilot.md).

> **`/api/chat/stream` saat ini tidak terlindung autentikasi**, berbeda dari
> endpoint lain. Selama layanan hanya berjalan di localhost risikonya nol,
> tetapi ini **harus** ditutup sebelum dipasang di jaringan instansi —
> tanpa penjaga, siapa pun yang menjangkau portnya bisa menanyai seluruh isi
> dokumen yang sudah di-ingest.

---

## Evaluasi mutu jawaban

`test_ragas_official.py` mengukur mutu RAG dengan pustaka resmi RAGAS. Model
yang menjawab (`qwen2.5:7b`) sengaja dipisah dari model yang menilai
(Gemini) supaya model tidak menilai jawabannya sendiri.

```bash
python test_ragas_official.py --list-models     # lihat model juri yang tersedia
python test_ragas_official.py --limit 3         # evaluasi 3 pertanyaan
python test_ragas_official.py --limit 10 --reuse  # pakai ulang jawaban tersimpan
```

| Flag | Fungsi |
|---|---|
| `--limit N` | Jumlah pertanyaan dari `reference_eval_dataset.json` |
| `--judge-model=<nama>` | Ganti model juri (jatah gratis dihitung per model per hari) |
| `--reuse` | Pakai ulang jawaban RAG dari cache, hanya ulangi penilaian |
| `--list-models` | Daftar model yang boleh dipakai API key ini |
| `--verbose` | Tampilkan seluruh log |

Hasilnya ditulis ke `hasil_ragas_official.md`. Skrip mencetak taksiran jumlah
permintaan ke juri sebelum mulai — jatah gratis Gemini dihitung **per model
per hari**, jadi berganti model memberi jatah baru seketika.

---

## Pengujian

```bash
pytest                              # semua
pytest test_pdf_processor.py -k "not Integration"   # tes unit saja, ~0,2 detik
```

Tes yang bertanda `Integration` membutuhkan berkas PDF sungguhan di
`test_files/`.

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
langchain-community 0.4.x. Penambalnya sudah ada di `test_ragas_official.py`
(fungsi `_patch_langchain_community_vertexai`, baris 139) dan berjalan
sebelum ragas di-import. **Skrip evaluasi baru harus memanggil penambal yang
sama.**

**Kebisingan telemetri ChromaDB.** chromadb 0.5.5 memanggil `posthog.capture()`
dengan tiga argumen, sedangkan posthog 7.x hanya menerima satu — hasilnya
setiap operasi ChromaDB menulis baris `Failed to send telemetry event ...`.
Tidak ada dampak fungsional. Peredamnya dipasang di `app/main.py` dan
`test_ragas_official.py`; skrip baru perlu mengulangnya.

**Menambah dokumen membatalkan indeks pencarian.** Indeks BM25 di-cache di
memori dan dibangun ulang saat jumlah vektor berubah. Bila dokumen ditimpa
dengan jumlah potongan yang kebetulan sama, cache tidak ikut diperbarui —
restart server API bila hasil pencarian terasa tidak sesuai dokumen terbaru.

**Ollama dan VRAM.** Model chat (4,4 GB) dan model vision (5,6 GB) bertukar
tempat di GPU bila ingest dan chat berjalan bersamaan. Selama keduanya tidak
dipakai serentak, ongkosnya kecil.
