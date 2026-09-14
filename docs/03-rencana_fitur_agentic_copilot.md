# Rencana Fitur & Implementasi Sistem

## 1. Modul Frontend Admin & RAG Playground (React + Vite)
- **Autentikasi & Sesi Admin:** Login aman dengan token Sanctum, manajemen sesi persisten.
- **Manajemen Korpus Dokumen (Knowledge Base):**
  - **Tabel Dokumen & Kategori:** Pengelompokan dokumen berdasarkan OPD / kategori SOP.
  - **Status Pemrosesan Multi-Fase:** Indikator visual tahapan ekstraksi (`antre`, `berjalan`, `jeda`, `menunggu_koreksi`, `selesai`, `gagal`).
  - **PDF Viewer & Inspection:** Pratinjau PDF interaktif langsung di peramban.
  - **Editor Koreksi Manual OCR:** Antarmuka berdampingan (*side-by-side*) antara citra pindaian dan teks hasil OCR, dengan deteksi baris mencurigakan (*heuristic check*).
  - **One-Click Vectorization:** Pratinjau potongan Parent-Child sebelum diindeks ke ChromaDB.
- **RAG Playground & Prompt Studio:**
  - Pengujian kueri interaktif dengan *Live 3-Stage Pipeline Stepper* (Retrieval -> RRF Ranking -> LLM Inference).
  - Telemetri inspeksi jawaban (grounding status, context tokens, latency breakdown, chunk inspector).
- **Manajemen Kunci API (API Keys Manager):**
  - Pembuatan kunci akses publik (*Bearer sk_live_xxx*), penetapan batas laju (*rate limit*), granularitas izin (*read/write/chat*), dan pencabutan kunci (*revoke*).
- **Observabilitas & Audit Trail (Chat Logs):**
  - Riwayat percakapan dari seluruh kanal, grafik latensi milidetik, metrik token, dan rating umpan balik pengguna.
- **Konfigurasi Mesin & Jalan Pintas:**
  - Pengaturan prompt sistem, parameter inferensi (*temperature, max tokens, top-k*), serta pembuatan *Fast Paths* & Direktori Layanan.

## 2. Modul Backend & API Gateway (Laravel 11)
- **Public API Gateway (`/api/v1`):**
  - Autentikasi `ApiKeyMiddleware` terenkripsi SHA-256.
  - Endpoint chat streaming (`/api/v1/chat/stream`) & sinkron (`/api/v1/chat`).
  - Rate limiting dinamis per kunci API.
- **Graceful Degradation Service:**
  - Deteksi kegagalan klaster AI dengan pengalihan otomatis ke pesan cadangan informatif saat status mikroservis terdegradasi.
- **Audit Logging & Telemetry Collector:**
  - Menyimpan setiap interaksi, latensi, sumber dokumen, dan token ke MySQL.

## 3. Modul AI Microservice (Python + FastAPI)
- **Asynchronous Task Queue (Celery + Redis):**
  - Ekstraksi PDF berjenjang per halaman dengan kemampuan jeda (*pause*), lanjut (*resume*), dan pembatalan (*cancel*).
- **Smart Text Extraction & Vision OCR:**
  - Deteksi otomatis teks digital (PyMuPDF) vs citra pindaian.
  - Deskewing prapemrosesan presisi 0.25° untuk meluruskan dokumen miring.
  - Ekstraksi visual dokumen kompleks menggunakan `qwen2.5vl:7b` via Ollama.
- **Advanced Chunking & Indexing:**
  - *Boundary-Aware Parent-Child Splitter* (Child: 300 char untuk pencarian presisi, Parent: 1500 char untuk konteks utuh ke LLM).
  - Dense embedding menggunakan `BAAI/bge-m3` (1024-dim, cosine space).
  - Sparse lexical index menggunakan `RankBM25` Okapi.
- **Hybrid Retrieval & RRF Re-ranking:**
  - Reciprocal Rank Fusion ($k=60$) menggabungkan hasil vektor dense dan kata kunci sparse.
  - Multi-query expansion & heuristic hallucination guards.
- **Multi-turn Session Memory:**
  - Manajemen riwayat percakapan berbasis session TTL.

## 4. Stack Model AI Terpasang

```
LLM Teks (Ollama)   : qwen3:8b / qwen2.5:7b   -> Penalaran dan sintesis jawaban
LLM Vision (Ollama) : qwen2.5vl:7b            -> OCR multimodal halaman pindaian
Embedding Model     : BAAI/bge-m3             -> 1024-dim dense representation
Vector Database     : ChromaDB                -> Cosine similarity space
Pencarian Kata      : RankBM25                -> BM25 Okapi lexical match
```


