# 👥 Pembagian Modul & Tanggung Jawab Komponen

## Proyek: Agentic IT Support Copilot & Central RAG Hub

---

## 🟦 Modul AI Engine & Microservice (`python-ai/`)

### ✅ Fitur & Deliverables

| No  | Fitur | Status | Keterangan |
| --- | --- | :---: | --- |
| 1   | Arsitektur FastAPI & Middleware | ✅ Selesai | CORS terkonfigurasi, bearer token guard |
| 2   | Chat SSE Streaming (`POST /api/chat/stream`) | ✅ Selesai | Format terpadu `type: chunk, trace, telemetry, sources, done, error` |
| 3   | Chat Synchronous (`POST /api/chat/sync`) | ✅ Selesai | Digunakan untuk webhook WhatsApp & non-streaming client |
| 4   | Ekstraksi PDF Bertahap (Celery + Redis) | ✅ Selesai | Pipeline per halaman dengan jeda, lanjut, simpan cache |
| 5   | Vision OCR Multimodal (`qwen2.5vl:7b`) | ✅ Selesai | Deskewing 0.25° & ekstraksi tabel pindaian via Ollama |
| 6   | Hybrid Retrieval & RRF Fusion ($k=60$) | ✅ Selesai | Gabungan dense vector ChromaDB (BGE-M3) + RankBM25 |
| 7   | Boundary-Aware Parent-Child Splitter | ✅ Selesai | Child 300 char (search) -> Parent 1500 char (LLM context) |
| 8   | Multi-turn Session Memory | ✅ Selesai | Memori percakapan kontekstual dengan TTL |
| 9   | Hallucination Guards & Anti-False Premise | ✅ Selesai | Penjaga konsistensi jawaban terprogram |
| 10  | Cluster Health Check (`GET /health`) | ✅ Selesai | Diagnostik aktif 4 subsistem (FastAPI, Ollama, Chroma, Redis) |

---

## 🟩 Modul Backend & API Gateway (`laravel-admin/`)

### ✅ Fitur & Deliverables

| No  | Fitur | Status | Keterangan |
| --- | --- | :---: | --- |
| 1   | Autentikasi Sanctum & Multi-Role | ✅ Selesai | Login aman untuk Admin Diskominfotik |
| 2   | Public API Gateway (`/api/v1/*`) | ✅ Selesai | Kunci API `Bearer sk_live_xxx` dengan SHA-256 hash |
| 3   | Manajemen Dokumen & Kategori SOP | ✅ Selesai | Upload, status multi-fase, preview & sinkronisasi |
| 4   | Ekstraksi Controller & Job Tracker | ✅ Selesai | Pengendali tahapan ekstraksi, koreksi OCR & embedding |
| 5   | Manajemen Kunci API (API Keys Manager) | ✅ Selesai | CRUD kunci API, kuota laju (rate limit), & audit last used |
| 6   | Telemetri Percakapan (`chat_logs`) | ✅ Selesai | Pencatatan latensi milidetik, token, dan audit trail |
| 7   | Prompt Studio & Settings Controller | ✅ Selesai | Konfigurasi prompt dinamis & pemilih model Ollama |
| 8   | Fast Paths & Direktori Layanan | ✅ Selesai | Pilihan jawaban instan & kontak kedinasan |
| 9   | Graceful Degradation Service | ✅ Selesai | Penanganan fallback saat AI microservice mengalami kendala |

---

## 🟨 Modul Frontend Admin & RAG Playground (`admin-frontend/`)

### ✅ Fitur & Deliverables

| No  | Fitur | Status | Keterangan |
| --- | --- | :---: | --- |
| 1   | SPA React + Vite + Tailwind CSS | ✅ Selesai | Desain modern, responsif, dark/light theme |
| 2   | Dashboard & Analitik Korpus | ✅ Selesai | Ringkasan dokumen, grafik metrik, cluster status |
| 3   | RAG Playground & Live Pipeline Stepper | ✅ Selesai | Uji coba prompt dengan 3-tahap visualisasi pipeline SSE |
| 4   | Editor Koreksi Manual OCR | ✅ Selesai | Tampilan *side-by-side* citra vs teks + deteksi baris |
| 5   | Manajemen Kunci API & Token Copy | ✅ Selesai | UI pembuatan API Key instan & modal salin kunci |
| 6   | Observabilitas & Log Percakapan | ✅ Selesai | Tampilan interaktif riwayat chat, filter kanal, & rating |
| 7   | Konfigurasi Mesin & Prompt Presets | ✅ Selesai | Studio prompt sistem & parameter tuning |
| 8   | Fast Paths & Direktori Manager | ✅ Selesai | CRUD shortcut jawaban cepat |

---

## 🔗 Panduan Berkas Dokumentasi

> - [`docs/01-prd_agentic_copilot.md`](01-prd_agentic_copilot.md) — Product Requirements Document (PRD)
> - [`docs/02-arsitektur_sistem_agentic_copilot.md`](02-arsitektur_sistem_agentic_copilot.md) — Diagram Arsitektur Keseluruhan
> - [`docs/03-rencana_fitur_agentic_copilot.md`](03-rencana_fitur_agentic_copilot.md) — Rencana & Status Fitur
> - [`docs/04-api_spec_agentic_copilot.md`](04-api_spec_agentic_copilot.md) — Spesifikasi API Terpadu (Gateway, Admin, & AI)
> - [`docs/07-arsitektur-rag-python-ai.md`](07-arsitektur-rag-python-ai.md) — Arsitektur Teknis RAG, Hybrid Search & OCR
> - [`docs/09-panduan-integrasi-api-dan-rag-gateway.md`](09-panduan-integrasi-api-dan-rag-gateway.md) — Panduan Integrasi Public API Gateway
> - [`docs/10-observabilitas-dan-telemetri-rag.md`](10-observabilitas-dan-telemetri-rag.md) — Panduan Observabilitas, Tracing & Telemetri

