# 🏗️ Arsitektur Sistem — Agentic IT Support Copilot & Central RAG Hub

Dokumen ini menjelaskan hubungan layanan, penyimpanan dan alur sistem.
Untuk detail modul gunakan [panduan pemeliharaan](08-panduan-struktur-kode-dan-pemeliharaan.md),
untuk algoritme gunakan [arsitektur RAG](05-arsitektur-rag-python-ai.md), dan
untuk payload/status HTTP gunakan [spesifikasi API](03-api_spec_agentic_copilot.md).
Model dan port mengikuti konfigurasi; diagram bukan bukti deployment atau benchmark.

## 1. Diagram Arsitektur Keseluruhan

```mermaid
graph TB
    subgraph Frontend["🌐 Klien & UI (User Interface)"]
        AdminSPA["Admin Frontend SPA (Port 5173)<br/>(Dashboard, RAG Playground, OCR Editor, ApiKeys, Logs)"]
        WebWidget["Portal Web / React Widget<br/>(Layanan Publik)"]
        WAClient["WhatsApp Business / End-User<br/>(Kanal Produksi)"]
    end

    subgraph LaravelGateway["🔧 Laravel Backend & API Gateway (Port 8000)"]
        Auth["Admin Auth (Sanctum)"]
        APIGateway["Public chat /api/v1/chat dan /stream<br/>ApiKey Middleware (sk_live_xxx)"]
        Webhook["Webhook kanal /api/v1/webhook/*<br/>Di luar middleware API key chat"]
        DocManager["Manajemen Dokumen & Kategori"]
        EkstraksiCtrl["Ekstraksi Controller & Job Tracker"]
        Degradation["Graceful Degradation Service"]
        AuditLog["Telemetry & Chat Logger (chat_logs)"]
        SettingsMgr["Prompt & Parameter Manager"]
    end

    subgraph PythonAI["🐍 Python AI Microservice (FastAPI - Port 8080)"]
        API_Chat["POST /api/chat/stream & /api/chat/message"]
        API_Ekstraksi["POST /api/docs/{id}/extraction & /api/docs/process"]
        ToolRouter["Semantic Router & Intent Classifier"]
        SessionMem["Multi-turn Session Memory"]
        RAGChain["Hybrid Search (ChromaDB + BM25 → RRF)"]
        BM25Cache["Cache BM25 per proses dari korpus ChromaDB"]
        ParentChild["Parent-Child Boundary-Aware Chunker"]
        Guards["Penjaga Halusinasi & Anti-Premis Palsu"]
        CeleryWorker["Celery Worker (Queue Ingestion)"]
        VisionOCR["Render halaman + OCR vision Ollama"]
        VectorCleanup["Retry cleanup SQL saat startup / 30 detik"]
    end

    subgraph Storage["💾 Storage Layer"]
        MySQL[("MySQL 8.0+<br/>(Documents, Jobs, Halaman, ApiKeys, Logs, Users)")]
        ChromaDB[("ChromaDB Persisten<br/>(Vector Embeddings BGE-M3)")]
        Redis[("Redis 6.0+<br/>(Task Queue Celery & Session Cache)")]
    end

    subgraph AI["🤖 AI Engine (Ollama Local)"]
        Ollama["Ollama Server (Port 11434)"]
        QwenText["qwen3:8b / qwen2.5:7b<br/>(Penalaran Teks & Jawaban)"]
        QwenVision["qwen2.5vl:7b<br/>(Multimodal Vision OCR)"]
    end

    %% Relasi Frontend & Gateway
    AdminSPA -->|"Sanctum API"| LaravelGateway
    WebWidget -->|"Bearer sk_live_xxx"| APIGateway
    WAClient -->|"Webhook"| Webhook

    %% Gateway ke Python AI
    APIGateway -->|"Forward Query + Injeksi Prompt"| API_Chat
    Webhook -->|"Pesan kanal + bearer internal"| API_Chat
    EkstraksiCtrl -->|"Trigger Ingestion"| API_Ekstraksi
    DocManager -->|"Proxy / Status Check"| PythonAI

    %% Python AI Internal
    API_Chat --> ToolRouter
    ToolRouter --> SessionMem
    SessionMem --> RAGChain
    RAGChain --> ParentChild
    ParentChild --> Guards
    Guards -->|"Inferensi Terpandu"| QwenText
    Ollama --- QwenText
    Ollama --- QwenVision

    %% Celery Ingestion
    API_Ekstraksi -->|"Enqueue Task"| Redis
    Redis -->|"Dequeue"| CeleryWorker
    CeleryWorker --> VisionOCR
    VisionOCR --> QwenVision
    CeleryWorker -->|"Simpan Halaman/Job"| MySQL
    CeleryWorker -->|"Upsert Vektor"| ChromaDB
    DocManager -->|"Fence + outbox cleanup satu transaksi"| MySQL
    MySQL -->|"document_vector_cleanups"| VectorCleanup
    VectorCleanup -->|"Delete scope dokumen/token + retry"| ChromaDB

    %% Storage & Logs
    RAGChain -->|"Dense Query"| ChromaDB
    RAGChain -->|"Sparse Match"| BM25Cache
    AuditLog -->|"Metadata kanal, fallback, latensi"| MySQL
    Degradation -.->|"Fallback saat Python 503"| APIGateway

    style Frontend fill:#1a1a2e,stroke:#3b82f6,color:#fff
    style LaravelGateway fill:#0f3460,stroke:#3b82f6,color:#fff
    style PythonAI fill:#311b92,stroke:#8b5cf6,color:#fff
    style Storage fill:#1b1b2f,stroke:#10b981,color:#fff
    style AI fill:#2d4059,stroke:#f59e0b,color:#fff
```

---

Reverb dapat dipakai sebagai driver broadcast bila dipasang dan dijalankan pada deployment. Frontend live chat saat ini menyelaraskan data lewat polling; diagram tidak menganggap ada subscription Echo/WebSocket pada SPA.

Untuk profil API dan worker terpisah, Chroma pada diagram dijalankan sebagai
satu server bersama dengan `CHROMA_HTTP_HOST`/`CHROMA_HTTP_PORT` yang sama pada
kedua pemanggil. Host kosong tetap mengaktifkan mode embedded lama. Runner
integrasi memakai server sementara; konfigurasi launcher/deployment lama perlu
disesuaikan tersendiri dan tidak diubah otomatis oleh pengujian.

## 2. Alur Kerja Komponen Utama

### A. Alur Ingestion & Ekstraksi Bertahap (Step-by-Step with Manual Correction)

Dua tahap manual adalah pemeriksaan teks serta tindakan simpan korpus. Pratinjau chunk membantu pemilihan parameter; diagram tidak menyatakan bahwa API mewajibkan setiap halaman telah diberi tanda diperiksa.

```mermaid
sequenceDiagram
    participant Admin as Admin (Frontend UI)
    participant Laravel as Laravel Backend
    participant API as Python API
    participant MySQL as MySQL Database
    participant Celery as Celery Worker + Redis
    participant Vision as PyMuPDF + Qwen2.5-VL (Ollama)
    participant Chroma as ChromaDB (BGE-M3)

    Admin->>Laravel: Upload Dokumen PDF SOP
    Laravel->>MySQL: Buat documents pending dan log unggahan
    Laravel->>API: Health dan POST /api/docs/{id}/extraction
    API->>Celery: Daftarkan tugas ekstraksi
    Celery->>MySQL: Siapkan ekstraksi_job dan progres

    loop Per Halaman PDF
        Celery->>Vision: Cek native text vs scanned image
        alt Scan Image
            Vision->>Vision: Vision OCR (qwen2.5vl:7b)
        else Native Digital Text
            Vision->>Vision: Ekstrak teks native halaman
        end
        Vision-->>Celery: Teks halaman
        Celery->>MySQL: Simpan teks ke ekstraksi_halaman
        Celery->>MySQL: Update progres halaman di ekstraksi_job
    end

    Celery->>MySQL: Update status job -> 'menunggu_koreksi'
    Admin->>Laravel: Buka Document Detail & Manual Correction Editor
    Admin->>Laravel: Periksa halaman mencurigakan & edit teks jika perlu
    Admin->>Laravel: Klik "Simpan & Masukkan ke Korpus Vektor"
    Laravel->>API: POST /api/docs/{id}/embed
    API->>Celery: Daftarkan task embedding & chunking
    Celery->>Chroma: Parent-Child chunking + BAAI/bge-m3 embedding
    Celery->>MySQL: Update status job -> 'selesai', status dokumen -> 'completed'
```

Unggah mengikuti format yang diizinkan controller, termasuk PDF serta beberapa
format dokumen/gambar, dengan batas 50 MB. Nama berkas memakai hash UUID, waktu
dan isi; ini bukan deduplikasi berdasarkan isi saja. Render citra untuk OCR dan
editor memiliki batas berbeda, dijelaskan pada
[arsitektur RAG](05-arsitektur-rag-python-ai.md#citra-halaman-untuk-editor-koreksi).

### B. Alur Inferensi RAG dan Streaming

Chat JSON publik memakai `POST /api/v1/chat`; stream publik memakai `/api/v1/chat/stream`. Sandbox admin memakai jalur proxy AI dan dapat meminta metadata debug. Gateway stream publik meneruskan byte SSE tanpa meminta debug serta tidak membuat `ChatLog` pada implementasi saat ini.

```mermaid
sequenceDiagram
    participant Klien as Klien chat
    participant Gateway as Laravel / proxy AI
    participant Python as Router chat Python
    participant Retrieval as ChromaDB + cache BM25
    participant LLM as Ollama

    Klien->>Gateway: Permintaan chat dengan kredensial sesuai route
    Gateway->>Python: Bearer internal + query/session/opsi
    Python->>Python: Routing, memori sesi, dan guard
    alt Routing memilih RAG
        Python->>Retrieval: Dense + BM25, RRF dan reranker
        Retrieval-->>Python: Konteks relevan dan sumber
        Python->>LLM: ChatOllama, model dan parameter efektif
        loop Token respons
            LLM-->>Python: Potongan teks
            Python-->>Gateway: SSE chunk
            Gateway-->>Klien: Byte stream
        end
    else Jawaban terprogram / handoff
        Python-->>Gateway: Respons sesuai hasil routing
        Gateway-->>Klien: JSON atau stream sesuai route
    end
    opt Debug diminta pada jalur yang mendukungnya
        Python-->>Gateway: Event trace/debug/telemetry
        Gateway-->>Klien: Teruskan event
    end
    Python-->>Gateway: SSE done pada stream yang selesai normal
    Gateway-->>Klien: Teruskan done
```

Penyimpanan metadata log JSON/kanal mengikuti pemanggil Laravel. Jenis event dan payload mengacu ke [spesifikasi API](03-api_spec_agentic_copilot.md); trace tiga tahap bukan jaminan bahwa setiap pertanyaan menjalankan model atau retrieval.

---

### C. Fallback ketika AI gagal

```mermaid
flowchart TD
    Request["Public chat JSON"] --> AI{"AI berhasil?"}
    AI -->|Ya| Normal["Jawaban / handoff sesuai hasil AI"]
    AI -->|Tidak| Greeting{"Sapaan lokal cocok?"}
    Greeting -->|Ya| LocalGreeting["Sapaan instansi"]
    Greeting -->|Tidak| FAQ{"Fast path aktif cocok?"}
    FAQ -->|Ya| LocalFAQ["Jawaban FAQ lokal"]
    FAQ -->|Tidak| Directory{"Direktori aktif cocok?"}
    Directory -->|Ya| LocalDirectory["Informasi unit kerja"]
    Directory -->|Tidak| Maintenance["Pesan pemeliharaan dan kontak layanan"]
    LocalGreeting --> Response["Wrapper Public API: HTTP 200, is_fallback=true, degraded_mode=true"]
    LocalFAQ --> Response
    LocalDirectory --> Response
    Maintenance --> Response
```

Diagram menunjukkan jalur kegagalan AI pada Public API JSON. Middleware dan validasi tetap dapat menghasilkan 401/422; ini bukan jaminan bahwa seluruh endpoint selalu membalas 200. Helper fallback lokal memiliki flag hasilnya sendiri, sedangkan wrapper Public API menetapkan flag degradasi. Stream publik memiliki kebijakan fallback berdasarkan byte/error transportnya; webhook kanal mempertahankan kebijakan respons masing-masing.

### D. Handoff dan tindak lanjut petugas

```mermaid
sequenceDiagram
    participant Citizen as Kanal warga / Public API
    participant AI as Python / gateway kanal
    participant Laravel
    participant DB as MySQL
    participant UI as SPA live chat
    actor Agent as Petugas
    AI->>Laravel: Payload handoff dengan bearer internal
    Laravel->>DB: Buat/gunakan tiket, simpan pesan
    Laravel-->>AI: ticket_id dan ticket_number
    AI-->>Citizen: Respons handoff
    loop Polling frontend setiap 5 detik
        UI->>Laravel: GET antrean dan pesan tiket terpilih
        Laravel-->>UI: Data tiket/pesan
    end
    Agent->>UI: Klaim tiket
    UI->>Laravel: POST /api/tickets/{id}/assign
    Laravel->>DB: Penugasan dan status
    Agent->>UI: Kirim balasan / lampiran
    UI->>Laravel: POST /api/tickets/{id}/messages
    Laravel->>DB: Simpan pesan
    Laravel-->>Citizen: Pengiriman kanal / antrean webhook bila berlaku
    Agent->>UI: Selesaikan tiket
    UI->>Laravel: PATCH /api/tickets/{id}/status
    Laravel->>DB: Status dan resolved_at
```

Broadcast event tetap disediakan backend kepada konsumennya. Pembaruan pada SPA mengikuti polling dan event browser lokal `app-tickets-updated`; diagram ini tidak menjanjikan delivery kanal berhasil hanya karena pesan sudah tersimpan.

Penerimaan tiket mempertahankanaturan sesi, kontak, tanggal, status aktif, dan pembukaan ulang. Entity extractor Laravel juga dapat membaca riwayat Redis DB 2 serta memperkaya tiket dari pesan baru. Catatan internal petugas tidak dikirim ke kanal keluar.

---

## 3. Struktur Proyek Terkini

```
agentic-ai/
├── admin-frontend/         # Dashboard Manajemen & RAG Playground (React + Vite + Tailwind)
│   ├── src/
│   │   ├── api/            # Client API (documents, categories, apiKeys, chatLogs, settings, mesin)
│   │   ├── components/     # Layout, Modal, ManualCorrectionEditor, EmbedProgressModal, Settings
│   │   ├── hooks/          # State/workflow tickets, editor dokumen, dan settings
│   │   ├── pages/          # Dashboard, DocumentDetail, Categories, ApiKeys, ChatLogs, Mesin, Settings
│   │   └── services/       # Orkestrasi data live chat dan SSE singleton persisten
│   ├── package.json
│   └── vite.config.js
│
├── laravel-admin/          # Backend Admin API, Auth Sanctum & API Gateway (Laravel 13)
│   ├── app/
│   │   ├── Http/Controllers/Api/
│   │   │   ├── AuthController.php          # Login & Sesi Cookie Sanctum
│   │   │   ├── DocumentController.php      # Upload, Sync, & Manage Documents
│   │   │   ├── EkstraksiController.php     # Multi-step OCR Extraction Endpoints
│   │   │   ├── ApiKeyController.php        # External API Key Management
│   │   │   ├── ChatLogController.php       # Telemetry & Audit Logs
│   │   │   ├── SettingController.php       # Alias kompatibilitas prompt bawaan
│   │   │   ├── Settings/                   # HTTP pengaturan kanal, chatbot, dan diagnostik
│   │   │   ├── FastPathController.php      # Quick Responses / Shortcuts
│   │   │   ├── DirectoryController.php     # Service Directory Lookup
│   │   │   └── V1/                         # Public API Gateway Endpoints
│   │   ├── Http/Middleware/
│   │   │   └── AuthenticateApiKey.php      # Otentikasi Public API Gateway
│   │   ├── Models/
│   │   │   ├── Document.php, DocumentLog.php
│   │   │   ├── EkstraksiJob.php, EkstraksiHalaman.php
│   │   │   ├── ApiKey.php, ChatLog.php
│   │   │   └── ChatbotFastPath.php, ChatbotDirectory.php
│   │   └── Services/
│   │       ├── Documents/                 # Workflow berkas, ekstraksi, opsi kategori, dan format respons
│   │       ├── Tickets/                   # Ingestion, query, lifecycle, reply, delivery
│   │       ├── Entities/                  # Trait normalisasi, parsing, Redis history, enrichment
│   │       ├── Channels/                  # Inbound kanal, polling, profil Telegram, transport AI
│   │       ├── Settings/                  # Persistensi pengaturan dan katalog model
│   │       ├── WhatsAppClient.php         # Konfigurasi kanal dan pengiriman balasan
│   │       ├── WhatsAppGateway.php        # Payload HTTP Meta/gateway generik
│   │       ├── AiMicroserviceClient.php   # Titik masuk kompatibel HTTP dokumen Python
│   │       ├── Ai/                        # Trait DocumentRequests dan StagedExtractionRequests
│   │       └── GracefulDegradationService.php # Fallback Handler saat AI Down
│   ├── routes/
│   │   └── api.php                         # Routing Sanctum, Admin, & V1 Gateway
│   └── database/migrations/                # Skema Database MySQL
│
├── python-ai/              # AI Microservice RAG, Hybrid Search & OCR (FastAPI + Celery)
│   ├── app/
│   │   ├── main.py                         # FastAPI App & Middleware
│   │   ├── config.py                       # Settings & Environment Variables
│   │   ├── celery_app.py                   # Satu instance Celery bersama
│   │   ├── database.py                     # Ekspor query MySQL kompatibel
│   │   ├── repositories/                   # connection, documents, settings, directories, document_logs
│   │   ├── schemas.py                      # Pydantic Schemas
│   │   ├── routers/
│   │   │   ├── chat.py                     # Streaming & Synchronous Chat Endpoints
│   │   │   ├── documents.py                # Direct Document Processing Endpoints
│   │   │   ├── ekstraksi.py                # Granular Page Extraction Endpoints
│   │   │   └── health.py                   # HTTP/cache health publik dan hardware bertoken
│   │   ├── services/
│   │   │   ├── document_operations.py       # Token generasi, cancellation dan lock dokumen
│   │   │   ├── document_workflows/         # Query, lifecycle, citra, prompt, kendali, koreksi, chunk
│   │   │   ├── task_workflows/             # Legacy ingest, ekstraksi, embedding, cleanup
│   │   │   ├── diagnostics/                # Probe health serta pembacaan/estimasi hardware
│   │   │   ├── rag_service.py              # Orkestrasi chat dan titik masuk kompatibel
│   │   │   ├── rag/                        # retrieval, grounding, generation, prompts
│   │   │   ├── backend_client.py           # Handoff tiket ke Laravel
│   │   │   ├── embedding_service.py        # Ekspor embedding/chunking/vektor kompatibel
│   │   │   ├── embeddings/                 # models, chunking, vector_store, corpus
│   │   │   ├── pdf_processor.py            # Ekspor PDF/OCR kompatibel
│   │   │   ├── ocr/                        # pdf_io, prompts, vision, sop, cleanup, pipeline
│   │   │   ├── ekstraksi_bertahap.py       # Ekspor workflow/penyimpanan kompatibel
│   │   │   ├── extraction/                 # contracts, workflow, mysql_storage, memory_storage
│   │   │   ├── session_memory.py           # Multi-turn conversation buffer with TTL
│   │   │   ├── tool_router.py              # Ekspor intent/tool kompatibel
│   │   │   └── routing/                    # dispatch, language, patterns, semantic, citizen, calendar
│   │   └── tasks/
│   │       ├── process_document.py         # Celery Task: Legacy Document Ingestion
│   │       └── ekstraksi.py                # Celery Task: Granular Step Extraction
│   ├── requirements.txt
│   └── reset_jobs.py                       # Pembersih status pekerjaan tertahan
│
├── docs/                   # Spesifikasi Teknis, Arsitektur, Panduan Integrasi, dan Telemetri
├── start-all.sh            # Skrip orkestrasi peluncur seluruh layanan (Single Command)
└── stop-all.sh             # Skrip penghentian seluruh layanan
```

---

## 4. Skema Database Relasional (MySQL)

Diagram berikut adalah subset kolom yang dipakai integrasi saat ini. Migrasi Laravel menjadi sumber kebenaran untuk keseluruhan skema, nullable/default, dan indeks. `documents.status` berupa string setelah migrasi perubahan status; `ekstraksi_halaman` memakai primary key gabungan.

```mermaid
erDiagram
    users {
        bigint id PK
        string name
        string email UK
        string password
    }
    documents {
        bigint id PK
        string title
        string original_name
        string file_path
        string status
        string processing_token
        boolean cancellation_requested
        string pdf_type
        integer total_pages
        integer processed_pages
        integer total_chunks
        bigint category_id FK
        bigint uploaded_by FK
    }
    document_categories {
        bigint id PK
        string name UK
        string vision_model
        longtext vision_prompt
        json prompt_variables
        boolean is_active
    }
    ekstraksi_job {
        bigint document_id PK,FK
        enum status
        boolean jeda_diminta
        integer halaman_total
        integer halaman_selesai
        text petunjuk_format
        text pesan
        timestamp updated_at
    }
    ekstraksi_halaman {
        bigint document_id PK,FK
        integer page_number PK
        longtext text
        boolean diperiksa
        timestamp created_at
    }
    api_keys {
        bigint id PK
        string name
        string key UK
        boolean is_active
        timestamp last_used_at
        text webhook_url
        text webhook_secret
        boolean webhook_enabled
    }
    chat_logs {
        bigint id PK
        string session_id
        string channel
        bigint api_key_id FK
        string sender_identifier
        text query
        longtext answer
        json sources_json
        boolean is_fallback
        integer response_time_ms
        timestamp created_at
    }
    users ||--o{ documents : uploads
    document_categories o|--o{ documents : categorizes
    documents ||--o| ekstraksi_job : tracks
    documents ||--o{ ekstraksi_halaman : contains
    api_keys o|--o{ chat_logs : identifies
```

API key saat ini dicocokkan dengan kolom `key`; hashing, kuota per key, dan permission granular belum tersedia pada model/middleware ini. Secret webhook memakai cast enkripsi Laravel. Public API JSON dan handler kanal menyimpan metadata sesuai kebijakan `ChatLog`; tampilan log tidak menyediakan transkrip atau rating pengguna.

---

## 5. Ringkasan Port dan Komunikasi Antar Servis

| Layanan | Host & Port | Protokol | Autentikasi | Konsumen |
| :--- | :--- | :--- | :--- | :--- |
| **Admin Frontend** | `http://localhost:5173` | HTTP / SSE | Browser Web | Administrator Sistem |
| **Laravel Backend** | `http://localhost:8000` | HTTP REST / JSON | Cookie sesi Sanctum (SPA) | Admin Frontend |
| **Public API Gateway** | `http://localhost:8000/api/v1` | HTTP / SSE | Bearer API Key (`sk_live_xxx`) | Klien chat eksternal: portal, CRM, atau bot mandiri |
| **Python AI Microservice** | `http://localhost:8080` | HTTP REST / SSE | Bearer Internal Secret | Laravel Gateway |
| **Ollama LLM Engine** | `http://localhost:11434` | HTTP REST | Internal Localhost | Python AI Microservice |
| **ChromaDB** | Server bersama melalui `CHROMA_HTTP_HOST` / path embedded satu proses | HTTP client / native Python API | Konfigurasi deployment | Python API dan worker |
| **Redis Broker** | `localhost:6379` | TCP Redis Protocol | Internal Localhost | Celery Worker & FastAPI |
| **MySQL Server** | `localhost:3306` | TCP MySQL Protocol | User / Password | Laravel & Python AI |
