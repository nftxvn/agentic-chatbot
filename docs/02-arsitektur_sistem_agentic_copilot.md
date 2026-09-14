# 🏗️ Arsitektur Sistem — Agentic IT Support Copilot & Central RAG Hub

## 1. Diagram Arsitektur Keseluruhan

```mermaid
graph TB
    subgraph Frontend["🌐 Klien & Antarmuka Pengguna"]
        AdminSPA["Admin Frontend SPA (Port 5173)<br/>(Dashboard, RAG Playground, OCR Editor, ApiKeys, Logs)"]
        WebWidget["Portal Web / React Widget<br/>(Layanan Publik)"]
        WAClient["WhatsApp Business / End-User<br/>(Kanal Produksi)"]
    end

    subgraph LaravelGateway["🔧 Laravel Backend & API Gateway (Port 8000)"]
        Auth["Admin Auth (Sanctum)"]
        APIGateway["Public API Gateway (/api/v1)<br/>ApiKey Middleware (sk_live_xxx)"]
        DocManager["Manajemen Dokumen & Kategori"]
        EkstraksiCtrl["Ekstraksi Controller & Job Tracker"]
        Degradation["Graceful Degradation Service"]
        AuditLog["Telemetry & Chat Logger (chat_logs)"]
        SettingsMgr["Prompt & Parameter Manager"]
    end

    subgraph PythonAI["🐍 Python AI Microservice (FastAPI - Port 8080)"]
        API_Chat["POST /api/chat/stream & /api/chat/sync"]
        API_Ekstraksi["POST /api/ekstraksi/jobs & /api/docs/process"]
        ToolRouter["Semantic Router & Intent Classifier"]
        SessionMem["Multi-turn Session Memory"]
        RAGChain["Hybrid Search (ChromaDB + BM25 → RRF)"]
        ParentChild["Parent-Child Boundary-Aware Chunker"]
        Guards["Penjaga Halusinasi & Anti-Premis Palsu"]
        CeleryWorker["Celery Worker (Queue Ingestion)"]
        VisionOCR["Deskew (0.25°) + Qwen2.5-VL OCR"]
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
    WAClient -->|"Webhook"| APIGateway

    %% Gateway ke Python AI
    APIGateway -->|"Forward Query + Injeksi Prompt"| API_Chat
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

    %% Storage & Logs
    RAGChain -->|"Dense Query"| ChromaDB
    RAGChain -->|"Sparse Match"| MySQL
    AuditLog -->|"Insert Latency & Tokens"| MySQL
    Degradation -.->|"Fallback saat Python 503"| APIGateway

    style Frontend fill:#1a1a2e,stroke:#3b82f6,color:#fff
    style LaravelGateway fill:#0f3460,stroke:#3b82f6,color:#fff
    style PythonAI fill:#311b92,stroke:#8b5cf6,color:#fff
    style Storage fill:#1b1b2f,stroke:#10b981,color:#fff
    style AI fill:#2d4059,stroke:#f59e0b,color:#fff
```

---

## 2. Alur Kerja Komponen Utama

### A. Alur Ingestion & Ekstraksi Bertahap (Step-by-Step with Manual Correction)

```mermaid
sequenceDiagram
    participant Admin as Admin (Frontend UI)
    participant Laravel as Laravel Backend
    participant MySQL as MySQL Database
    participant Celery as Celery Worker + Redis
    participant Vision as PyMuPDF + Qwen2.5-VL (Ollama)
    participant Chroma as ChromaDB (BGE-M3)

    Admin->>Laravel: Upload Dokumen PDF SOP
    Laravel->>MySQL: Buat rekaman dokumen & ekstraksi_job (status='antre')
    Laravel->>Celery: Pemicu tugas ekstraksi berjenjang
    
    loop Per Halaman PDF
        Celery->>Vision: Cek native text vs scanned image
        alt Scan Image
            Vision->>Vision: Deskewing 0.25° precision
            Vision->>Vision: Vision OCR (qwen2.5vl:7b)
        else Native Digital Text
            Vision->>Vision: Ekstrak teks & tabel Markdown murni
        end
        Vision-->>Celery: Teks halaman
        Celery->>MySQL: Simpan teks ke ekstraksi_halaman
        Celery->>MySQL: Update progres halaman di ekstraksi_job
    end

    Celery->>MySQL: Update status job -> 'menunggu_koreksi'
    Admin->>Laravel: Buka Document Detail & Manual Correction Editor
    Admin->>Laravel: Periksa halaman mencurigakan & edit teks jika perlu
    Admin->>Laravel: Klik "Simpan & Masukkan ke Korpus Vektor"
    Laravel->>Celery: Jalankan embedding & chunking
    Celery->>Chroma: Parent-Child chunking + BAAI/bge-m3 embedding
    Celery->>MySQL: Update status job -> 'selesai', status dokumen -> 'completed'
```

### B. Alur Inferensi RAG & Live Pipeline Tracing (Playground & Public API)

```mermaid
sequenceDiagram
    participant Klien as Client (Playground / Widget / WhatsApp)
    participant Gateway as Laravel API Gateway
    participant Python as Python AI Microservice
    participant Hybrid as Hybrid Search (Chroma + BM25)
    participant LLM as Ollama (qwen3:8b)

    Klien->>Gateway: POST /api/v1/chat/stream (Bearer sk_live_xxx)
    Gateway->>Gateway: Validasi API Key & ambil pengaturan prompt aktif
    Gateway->>Python: Forward POST /api/chat/stream
    
    Python-->>Klien: SSE trace stage 1: "Mencari konteks di ChromaDB & BM25..."
    Python->>Hybrid: Retrieval Dense (Cosine) + Sparse (BM25)
    Hybrid-->>Python: Ambil child chunks -> lookup parent chunk utuh
    
    Python-->>Klien: SSE trace stage 2: "RRF Re-ranking (k=60) & deduplikasi konteks..."
    Python->>Python: Hitung skor RRF, filter ambang relevansi & evaluasi guardrails
    
    Python-->>Klien: SSE trace stage 3: "Mengirim konteks ke Ollama (qwen3:8b)..."
    Python->>LLM: Injeksi system prompt + konteks + pertanyaan pengguna
    
    loop Token Streaming
        LLM-->>Python: Token chunk
        Python-->>Klien: SSE type="chunk", content="..."
    end

    Python-->>Klien: SSE type="telemetry", content={latency_ms, context_tokens, grounding}
    Python-->>Klien: SSE type="sources", content=[{doc_name, page, document_id}]
    Python-->>Klien: SSE type="done"
    
    Gateway->>Gateway: Simpan log percakapan, token, & latensi ke tabel chat_logs
```

---

## 3. Struktur Proyek Terkini

```
agentic-ai/
├── admin-frontend/         # Dashboard Manajemen & RAG Playground (React + Vite + Tailwind)
│   ├── src/
│   │   ├── api/            # Client API (documents, categories, apiKeys, chatLogs, settings, mesin)
│   │   ├── components/     # Layout, Modal, ManualCorrectionEditor, EmbedProgressModal, Settings
│   │   ├── pages/          # Dashboard, DocumentDetail, Categories, ApiKeys, ChatLogs, Mesin, Settings
│   │   └── services/       # SSE Stream singleton & persistent tracing state
│   ├── package.json
│   └── vite.config.js
│
├── laravel-admin/          # Backend Admin API, Auth Sanctum & API Gateway (Laravel 11)
│   ├── app/
│   │   ├── Http/Controllers/Api/
│   │   │   ├── AuthController.php          # Login & Admin Token
│   │   │   ├── DocumentController.php      # Upload, Sync, & Manage Documents
│   │   │   ├── EkstraksiController.php     # Multi-step OCR Extraction Endpoints
│   │   │   ├── ApiKeyController.php        # External API Key Management
│   │   │   ├── ChatLogController.php       # Telemetry & Audit Logs
│   │   │   ├── SettingController.php       # LLM Prompts, WhatsApp & System Settings
│   │   │   ├── FastPathController.php      # Quick Responses / Shortcuts
│   │   │   ├── DirectoryController.php     # Service Directory Lookup
│   │   │   └── V1/                         # Public API Gateway Endpoints
│   │   ├── Http/Middleware/
│   │   │   └── ApiKeyMiddleware.php        # Otentikasi Public API Gateway
│   │   ├── Models/
│   │   │   ├── Document.php, DocumentLog.php
│   │   │   ├── EkstraksiJob.php, EkstraksiHalaman.php
│   │   │   ├── ApiKey.php, ChatLog.php
│   │   │   └── ChatbotFastPath.php, ChatbotDirectory.php
│   │   └── Services/
│   │       ├── AiMicroserviceClient.php    # HTTP & SSE Client ke Python
│   │       └── GracefulDegradationService.php # Fallback Handler saat AI Down
│   ├── routes/
│   │   └── api.php                         # Routing Sanctum, Admin, & V1 Gateway
│   └── database/migrations/                # Skema Database MySQL
│
├── python-ai/              # AI Microservice RAG, Hybrid Search & OCR (FastAPI + Celery)
│   ├── app/
│   │   ├── main.py                         # FastAPI App & Middleware
│   │   ├── config.py                       # Settings & Environment Variables
│   │   ├── database.py                     # SQLAlchemy MySQL Connector
│   │   ├── schemas.py                      # Pydantic Schemas
│   │   ├── routers/
│   │   │   ├── chat.py                     # Streaming & Synchronous Chat Endpoints
│   │   │   ├── documents.py                # Direct Document Processing Endpoints
│   │   │   └── ekstraksi.py                # Granular Page Extraction Endpoints
│   │   ├── services/
│   │   │   ├── rag_service.py              # Hybrid Search, RRF, Prompt Assembly & Guards
│   │   │   ├── embedding_service.py        # BGE-M3 Embedder & ChromaDB Manager
│   │   │   ├── pdf_processor.py            # PyMuPDF, Deskewing, & Qwen2.5-VL Vision OCR
│   │   │   ├── ekstraksi_bertahap.py       # Page-by-page pipeline orchestrator
│   │   │   ├── session_memory.py           # Multi-turn conversation buffer with TTL
│   │   │   └── tool_router.py              # Semantic intent & fast-path dispatcher
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

```mermaid
erDiagram
    users {
        bigint id PK
        string name
        string email UK
        string password
        string role "admin"
        timestamp created_at
        timestamp updated_at
    }

    documents {
        bigint id PK
        string title
        string original_name
        string file_path
        enum status "pending | processing | completed | failed"
        enum pdf_type "text | scanned | mixed | unknown"
        text error_message
        integer total_pages
        integer total_chunks
        bigint category_id FK
        timestamp processed_at
        timestamp created_at
        timestamp updated_at
    }

    ekstraksi_job {
        bigint document_id PK
        enum status "antre | berjalan | jeda | menunggu_koreksi | selesai | gagal"
        tinyint jeda_diminta
        integer halaman_total
        integer halaman_selesai
        text petunjuk_format
        text pesan
        timestamp updated_at
    }

    ekstraksi_halaman {
        bigint document_id PK
        integer page_number PK
        longtext text
        tinyint diperiksa
        timestamp created_at
    }

    api_keys {
        bigint id PK
        string name
        string key_hash UK
        string key_preview
        json permissions
        integer rate_limit
        boolean is_active
        timestamp last_used_at
        timestamp expires_at
        timestamp created_at
    }

    chat_logs {
        bigint id PK
        string session_id
        text query
        longtext response
        string channel "widget | whatsapp | playground | api"
        integer latency_ms
        integer prompt_tokens
        integer completion_tokens
        boolean is_grounded
        json source_references
        integer user_rating
        timestamp created_at
    }

    documents ||--|| ekstraksi_job : "tracked by"
    documents ||--o{ ekstraksi_halaman : "contains"
```

---

## 5. Ringkasan Port dan Komunikasi Antar Servis

| Layanan | Host & Port | Protokol | Autentikasi | Konsumen |
| :--- | :--- | :--- | :--- | :--- |
| **Admin Frontend** | `http://localhost:5173` | HTTP / SSE | Browser Web | Administrator Sistem |
| **Laravel Backend** | `http://localhost:8000` | HTTP REST / JSON | Bearer Sanctum Token | Admin Frontend |
| **Public API Gateway** | `http://localhost:8000/api/v1` | HTTP / SSE | Bearer API Key (`sk_live_xxx`) | Portal Web, WhatsApp, CRM |
| **Python AI Microservice** | `http://localhost:8080` | HTTP REST / SSE | Bearer Internal Secret | Laravel Gateway |
| **Ollama LLM Engine** | `http://localhost:11434` | HTTP REST | Internal Localhost | Python AI Microservice |
| **ChromaDB** | Local Embedded Path | Native Python API | Local File Lock | Python AI Microservice |
| **Redis Broker** | `localhost:6379` | TCP Redis Protocol | Internal Localhost | Celery Worker & FastAPI |
| **MySQL Server** | `localhost:3306` | TCP MySQL Protocol | User / Password | Laravel & Python AI |
