# Central RAG Engine as a Service & Admin Management Panel

Platform kecerdasan buatan berbasis *Retrieval-Augmented Generation (RAG)* mandiri untuk pengelolaan basis pengetahuan SOP dan layanan publik Diskominfotik Kota Banda Aceh.

---

## 1. Struktur Proyek

```
agentic-ai/
├── admin-frontend/         # Dashboard Manajemen & RAG Playground (React + Vite + Tailwind)
├── laravel-admin/          # Backend Admin API, Auth Sanctum & API Gateway (Laravel 13)
├── python-ai/              # AI Microservice RAG, Hybrid Search & OCR Extraction (FastAPI + Celery)
├── docs/                   # Spesifikasi teknis, arsitektur, panduan integrasi, dan telemetri
├── start-all.sh            # Skrip peluncur seluruh layanan (Single-command launcher)
└── stop-all.sh             # Skrip penghentian seluruh proses secara bersih
```

---

## 2. Tech Stack

| Komponen | Teknologi | Keterangan |
| :--- | :--- | :--- |
| **Frontend Admin & Playground** | React 19, Vite, Tailwind CSS, GSAP | Single Page Application (SPA), Dark/Light Theme, Sub-pixel Squircle |
| **Backend & API Gateway** | Laravel 13, PHP 8.3+, Sanctum | Manajemen Kunci API, Webhook WhatsApp, Audit Trail Percakapan |
| **AI Microservice** | Python 3.10+, FastAPI, Uvicorn | Hybrid Search, Reciprocal Rank Fusion (RRF), SSE Streaming |
| **LLM Engine (Teks)** | Ollama, model dari konfigurasi | Contoh profil `qwen3:8b` / `qwen2.5:7b`; pengaturan runtime dapat memilih model lain |
| **LLM Engine (Vision/OCR)** | Ollama (`qwen2.5vl:7b`) | Model multimodal ekstraksi dokumen pindaian |
| **Embedding Engine** | Sesuai `EMBEDDING_MODEL_NAME` | Contoh profil: `BAAI/bge-m3` (1024 dimensi); default kode masih MiniLM |
| **Vector Database** | ChromaDB | Penyimpanan embeddings dan metadata chunk dokumen |
| **Lexical Search** | RankBM25 | Pencarian kata kunci istilah kedinasan dan nomor SOP |
| **OCR & Ekstraksi Dokumen** | PyMuPDF, Qwen2.5-VL Vision OCR | Pipeline ekstraksi berjenjang dengan *manual correction* |
| **Task Queue & Broker** | Celery, Redis | Pemrosesan dokumen berat di latar belakang |
| **Relational Database** | MySQL 8.0+ | Database transaksional (`agentic_copilot`) |

---

## 3. Pemetaan Port & Layanan

| Layanan | Host & Port | Keterangan |
| :--- | :--- | :--- |
| **Frontend Admin UI** | `http://localhost:5173` | Panel Dashboard, Kelola Dokumen, dan RAG Playground |
| **Laravel Backend** | `http://localhost:8000` | Autentikasi Sanctum, API Dokumen, dan Public API Gateway (`/api/v1`) |
| **Python AI Microservice** | `http://localhost:8080` | Endpoint Chat Stream (`/api/chat/stream`) & Health (`/api/health`) |
| **Ollama LLM Engine** | `http://localhost:11434` | Server inferensi model lokal |
| **Redis Broker** | `localhost:6379` | Queue worker Celery dan caching |
| **MySQL Database** | `localhost:3306` | Database transaksional |

---

## 4. Cara Menjalankan Sistem

### A. Menjalankan Seluruh Layanan (Rekomendasi)

Cukup jalankan skrip orkestrasi di direktori utama:

```bash
./start-all.sh
```

Skrip ini secara otomatis akan:
1. Menjalankan service MySQL, Redis, dan Ollama.
2. Menghentikan proses gantung (*dangling processes*).
3. Mereset antrean ekstraksi yang tertahan.
4. Menjalankan Python AI Microservice pada Port 8080.
5. Menjalankan Celery Worker untuk antrean OCR.
6. Menjalankan Laravel Backend pada Port 8000.
7. Menjalankan Vite Dev Server pada Port 5173.

### B. Menghentikan Seluruh Layanan

```bash
./stop-all.sh
```

---

## 5. Fitur Utama & Observabilitas RAG

1. **Pengelolaan Korpus Dokumen Mandiri:**
   * Unggah dokumen PDF SOP, ekstraksi teks & tabel otomatis, pemisahan chunk adaptif, dan editor koreksi manual sebelum diindeks ke vektor.
2. **RAG Playground & Prompt Studio:**
   * Uji coba prompt sistem, penyesuaian parameter (*Temperature*, *Top-K*), dan pengujian simulasi obrolan secara *real-time*.
3. **Observabilitas Tiga Tahap (3-Stage Live Pipeline Tracing):**
   * *Stage 1 (Retrieval):* Pencarian vektor dense di ChromaDB dan pencarian leksikal di BM25.
   * *Stage 2 (RRF Ranking):* Penggabungan peringkat Reciprocal Rank Fusion dan deduplikasi potongan teks.
   * *Stage 3 (LLM Inference):* Inferensi model Ollama dengan jendela konteks terhitung.
4. **Telemetri & Explainability Jawaban:**
   * Flag fallback, estimasi token konteks, nama model/profil, jumlah chunk, tautan *Chunk Inspector*, serta durasi total stream.
5. **System Health Indicator:**
   * Indikator kesehatan admin dengan probe ChromaDB/MySQL/Redis/Ollama dan diagnostik hardware; cache serta status dijelaskan pada dokumentasi observabilitas.
6. **Public API Gateway & WhatsApp Bot:**
   * Endpoint publik berotentikasi token (`/api/v1/chat` dan `/api/v1/chat/stream`) untuk integrasi ke kanal eksternal dan bot WhatsApp.

---

## 6. Daftar Dokumentasi Teknis

| Dokumen | Deskripsi |
| :--- | :--- |
| [`docs/01-prd_agentic_copilot.md`](docs/01-prd_agentic_copilot.md) | Kebutuhan produk, kemampuan tersedia, dan pembagian modul |
| [`docs/02-arsitektur_sistem_agentic_copilot.md`](docs/02-arsitektur_sistem_agentic_copilot.md) | Arsitektur, diagram ingest/SSE/fallback/handoff, skema data, dan komunikasi layanan |
| [`docs/03-api_spec_agentic_copilot.md`](docs/03-api_spec_agentic_copilot.md) | Spesifikasi kontrak API terpadu |
| [`docs/04-panduan_kerja_mandiri_dev.md`](docs/04-panduan_kerja_mandiri_dev.md) | Runner lokal, fixture, mock API, dan pemeriksaan integrasi |
| [`docs/05-arsitektur-rag-python-ai.md`](docs/05-arsitektur-rag-python-ai.md) | Arsitektur teknis RAG, Hybrid Search & Chunking |
| [`docs/06-panduan-integrasi-api-dan-rag-gateway.md`](docs/06-panduan-integrasi-api-dan-rag-gateway.md) | Panduan integrasi Public API Gateway & WhatsApp |
| [`docs/07-observabilitas-dan-telemetri-rag.md`](docs/07-observabilitas-dan-telemetri-rag.md) | Panduan teknis observabilitas, pipeline tracing & telemetri |
| [`docs/08-panduan-struktur-kode-dan-pemeliharaan.md`](docs/08-panduan-struktur-kode-dan-pemeliharaan.md) | Batas modul, kontrak integrasi, dan panduan pemeliharaan kode |
| [`docs/09-status-refactor-dan-verifikasi.md`](docs/09-status-refactor-dan-verifikasi.md) | Status refactoring, audit A1/A2, penutupan, bukti uji, dan batas verifikasi UI |

## 7. Berkas lokal

Panduan pengujian yang tersedia berada di
[panduan lokal](docs/04-panduan_kerja_mandiri_dev.md), README setiap aplikasi,
dan [runner integrasi](scripts/integration/README.md). Hasil run serta batas
pengujian dicatat pada dokumentasi status refactoring.

`output/` menyimpan bukti pengujian dan PDF hasil build. `laporan-kkp/` berisi
materi akademik lokal yang dipilih untuk penyerahan terpisah. Keduanya diabaikan
Git, bersama catatan kerja agen dan snapshot browser. Dependensi, konfigurasi
`.env`, serta penyimpanan aplikasi tetap mengikuti aturan ignore masing-masing.
