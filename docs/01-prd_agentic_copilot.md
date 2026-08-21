# Product Requirements Document (PRD)

## Agentic IT Support Copilot - Knowledge Management System

### 1. Tujuan Produk

Membangun sistem _chatbot_ berbasis AI lokal yang memungkinkan Admin Diskominfotik untuk mengelola basis pengetahuan (berupa dokumen PDF) secara mandiri tanpa modifikasi kode (_No-Code Knowledge Management_). Bot akan menjawab pertanyaan _end-user_ berdasarkan dokumen yang diunggah.

### 2. Lingkup Proyek (Scope)

- **Dashboard Admin (Laravel):** Antarmuka untuk mengelola, melihat, dan menimpa dokumen PDF.
- **AI Microservice (Python):** Layanan pemrosesan dokumen, ekstraksi teks (termasuk OCR), pembuatan _vector embedding_, dan layanan _chat_ LLM. API bersifat _channel-agnostic_ (bisa dipanggil dari frontend manapun).
- **Chat Widget (React.js):** Antarmuka chat sederhana **hanya untuk testing & demo** selama development.
- **Integrasi WhatsApp (Produksi):** Channel utama _end-user_ di produksi. Python menerima pesan via _webhook_ dari WhatsApp Business API.

### 3. Asumsi & Batasan

- **Infrastruktur:** Mengandalkan CPU (tanpa GPU diskrit) di server lokal Diskominfotik.
- **Skala Dokumen:** Mampu memproses PDF berskala besar (hingga 170+ halaman per file) secara _asynchronous_ (di latar belakang). Tidak ada batasan halaman yang di-hardcode.
- **Integrasi Pihak Ketiga:** Integrasi sistem tiket dikecualikan (_out of scope_) untuk MVP ini dan akan ditambahkan pada iterasi selanjutnya.
- **Tanpa Training Ulang:** Admin dapat memperbarui pengetahuan bot hanya dengan mengganti file PDF — tanpa menyentuh kode atau meng-_training_ ulang model.

### 4. Tech Stack yang Disepakati

| Komponen              | Teknologi                             |
| --------------------- | ------------------------------------- |
| Dashboard Admin       | Laravel (PHP)                         |
| AI Microservice       | Python + FastAPI                      |
| Chat Widget (Testing) | React.js (dev/demo only)              |
| Channel Produksi      | WhatsApp Business API (webhook)       |
| LLM Engine            | Ollama + `qwen2.5:7b` (teks)           |
| Vision / OCR Engine   | Ollama + `qwen2.5vl` (multimodal)      |
| Embedding Model       | `BAAI/bge-m3`                          |
| Vector Database       | ChromaDB                              |
| Pencarian Kata        | `rank_bm25` (hybrid + RRF)             |
| AI Orchestration      | LangChain                             |
| Queue System          | Celery + Redis                        |
| Database Relasional   | MySQL                                 |
| Containerization      | Docker Compose                        |

### 5. Roadmap Deployment

| Fase                               | Keterangan                                                      | Model LLM    |
| ---------------------------------- | --------------------------------------------------------------- | ------------ |
| **Fase 1** — Development & Testing | Berjalan di mesin lokal (WSL). Chat via React Widget (testing). | `qwen2.5:3b` |
| **Fase 2** — Produksi Server       | Deploy ke server Diskominfotik. Chat via WhatsApp.              | `qwen2.5:7b` |

### 6. Alur Pengguna (User Flow)

**Admin Diskominfotik:**

1. Login ke Dashboard Laravel.
2. Melihat daftar "Dokumen Pengetahuan" yang saat ini terintegrasi ke dalam otak bot, lengkap dengan _preview_ PDF.
3. Mengklik tombol "Update/Replace" pada aturan/dokumen yang lama.
4. Mengunggah file PDF terbaru (Sistem otomatis merubah status menjadi "Sedang Diproses").
5. Melanjutkan pekerjaan lain. Setelah proses latar belakang Python selesai, status di Laravel berubah menjadi "Selesai" dan bot langsung menggunakan informasi terbaru.

**End-User (Testing — React Widget):**

1. Membuka halaman testing chat widget.
2. Mengajukan pertanyaan terkait prosedur atau kebijakan.
3. Mendapat jawaban yang bersumber langsung dari PDF terbaru yang relevan.

**End-User (Produksi — WhatsApp):**

1. Mengirim pesan ke nomor WhatsApp resmi Diskominfotik.
2. Mengajukan pertanyaan terkait prosedur atau kebijakan.
3. Mendapat jawaban otomatis dari bot yang bersumber dari PDF terbaru.
4. API endpoint yang sama (`POST /api/chat`) dipanggil oleh WhatsApp webhook.
