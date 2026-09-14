# Product Requirements Document (PRD)

## Agentic IT Support Copilot & Central RAG Hub — Knowledge Management System

### 1. Tujuan Produk

Membangun platform kecerdasan buatan berbasis *Retrieval-Augmented Generation (RAG)* mandiri dan terpusat (*Central RAG Hub as a Service*) yang memungkinkan Admin Diskominfotik Kota Banda Aceh untuk mengelola basis pengetahuan (berupa dokumen regulasi dan SOP kedinasan) secara mandiri tanpa modifikasi kode (*No-Code Knowledge Management*). Platform ini melayani tanya-jawab publik dan internal secara cerdas, akurat, dan berbasis bukti (*grounded*) lintas kanal (Dashboard Playground, Public API Gateway, Portal Web, dan WhatsApp Bot).

### 2. Lingkup Proyek (Scope)

- **Frontend Admin & RAG Playground (React + Vite + Tailwind):** Antarmuka SPA untuk manajemen dokumen SOP, editor koreksi OCR per-halaman, RAG Playground dengan pelacakan pipa 3 tahap (*live pipeline tracing*), manajemen kunci API (*API Keys*), audit percakapan (*Chat Logs*), serta konfigurasi mesin AI & jalan pintas (*Fast Paths* & Direktori).
- **Backend & Public API Gateway (Laravel 11):** Manajemen autentikasi Sanctum, manajemen otorisasi kunci API eksternal (*Bearer sk_live_xxx*), webhook WhatsApp, audit logging & telemetri ke MySQL, serta *Graceful Degradation Service* saat layanan AI mengalami gangguan.
- **AI Microservice (Python + FastAPI):** Layanan ekstraksi bertahap (PyMuPDF + Vision OCR via Ollama), *boundary-aware parent-child chunking*, *hybrid search* (ChromaDB dense + RankBM25 sparse) dengan *Reciprocal Rank Fusion (RRF)*, memori percakapan *multi-turn*, penjaga jawaban (*hallucination guards*), serta streaming respons berbasis Server-Sent Events (SSE).
- **Kanal Konsumen Eksternal:** Integrasi *channel-agnostic* melalui Public API Gateway (`/api/v1/chat` dan `/api/v1/chat/stream`) untuk Web Widget, Portal Informasi Pemko, CRM Helpdesk, dan WhatsApp Business API.

### 3. Asumsi & Batasan

- **Infrastruktur:** Dapat dijalankan secara lokal (WSL / Server On-Premise Diskominfotik) dengan optimasi GPU (NVIDIA RTX / CUDA) atau CPU multi-core.
- **Skala Dokumen:** Mampu memproses PDF berskala besar (170+ halaman per file) secara asinkron (*asynchronous background queue*) dengan fitur jeda, lanjut, dan periksa per halaman.
- **Keamanan & Kepatuhan:** Kunci API eksternal terenkripsi hash (*SHA-256*), pembatasan laju (*rate limiting*), dan isolasi token internal backend.
- **Tanpa Training Ulang:** Admin dapat memperbarui pengetahuan bot hanya dengan mengunggah atau mengoreksi dokumen — tanpa *fine-tuning* atau *re-training* model LLM.

### 4. Tech Stack yang Diterapkan

| Komponen | Teknologi | Keterangan |
| :--- | :--- | :--- |
| **Frontend Admin UI** | React 18, Vite, Tailwind CSS, Lucide Icons | Dashboard, RAG Playground, Tracing Stepper |
| **Backend & API Gateway** | Laravel 11, PHP 8.2+, Sanctum | API Gateway, Key Auth, Telemetry Logging |
| **AI Microservice** | Python 3.10+, FastAPI, Uvicorn | RAG Pipeline, Hybrid Retrieval, SSE Stream |
| **LLM Engine (Teks)** | Ollama (`qwen3:8b` / `qwen2.5:7b`) | Model penalaran & penyusun jawaban terpandu |
| **Vision / OCR Engine** | Ollama (`qwen2.5vl:7b`) | Multimodal vision untuk OCR pindaian kompleks |
| **Embedding Engine** | `BAAI/bge-m3` | Dense vector 1024-dim, cosine similarity |
| **Vector Database** | ChromaDB | Database vektor persisten |
| **Lexical Search** | RankBM25 | Pencarian kata kunci & terminologi kedinasan |
| **Task Queue & Broker** | Celery + Redis | Pipeline ekstraksi berjenjang di latar belakang |
| **Relational Database** | MySQL 8.0+ | Data transaksional, log chat, kunci API |

### 5. Alur Pengguna (User Flow)

**Admin Diskominfotik:**
1. Login ke Dashboard Admin.
2. Mengunggah file PDF SOP / Peraturan baru atau menimpa dokumen lama.
3. Memantau progres ekstraksi bertahap di antarmuka; dapat menjeda, melanjutkan, atau memeriksa citra prapemrosesan.
4. Melakukan *koreksi manual OCR* pada halaman-halaman yang ditandai mencurigakan jika diperlukan.
5. Menyetujui dan menyimpan ke dalam korpus vektor ChromaDB (*One-click Vectorization*).
6. Menguji akurasi jawaban di **RAG Playground** dengan melihat transparansi *Live Pipeline Stepper* & *Telemetry Inspector*.
7. Mengelola integrasi kunci API untuk sistem eksternal / bot WhatsApp.

**Pengguna / Sistem Konsumen (Web Portal / WhatsApp / Mobile):**
1. Mengirim pertanyaan melalui Web Widget atau WhatsApp.
2. Permintaan diterima oleh Laravel API Gateway (memvalidasi API Key & menerapkan rate limit).
3. Gateway meneruskan kueri ke Python AI Engine dengan injeksi parameter sistem aktif.
4. AI Engine melakukan *hybrid search*, *RRF re-ranking*, dan inferensi LLM lokal.
5. Jawaban dialirkan secara *real-time* (SSE) ke frontend atau dikirimkan utuh ke webhook WhatsApp beserta rujukan sumber SOP yang valid.
6. Telemetri latensi, penggunaan token, dan status grounding dicatat secara otomatis di tabel `chat_logs`.
