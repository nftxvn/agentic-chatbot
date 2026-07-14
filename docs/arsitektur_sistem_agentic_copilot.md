# 🏗️ Arsitektur Sistem — Agentic IT Support Copilot

## 1. Diagram Arsitektur Keseluruhan

```mermaid
graph TB
    subgraph Frontend["🌐 Channel Chat"]
        Widget["React Chat Widget<br/>(Testing/Demo Only)"]
        WAWebhook["WhatsApp Business API<br/>(Produksi)"]
    end

    subgraph Laravel["🔧 Laravel (Dashboard Admin)"]
        Auth["Login Admin"]
        DocManager["Manajemen Dokumen<br/>(Upload, Preview, Overwrite)"]
        StatusMonitor["Status Monitor<br/>(Polling AJAX/Livewire)"]
        FileStorage["File Storage<br/>(PDF Files)"]
    end

    subgraph Python["🐍 Python AI Microservice (FastAPI)"]
        API_Doc["POST /api/docs/process"]
        API_Chat["POST /api/chat/stream"]
        Queue["Celery Worker<br/>(Background Task)"]
        OCR["Tesseract OCR"]
        Chunker["Text Chunker<br/>(LangChain Splitter)"]
        Embedder["Embedding Model<br/>(MiniLM-L12-v2)"]
        RAGChain["RAG Chain<br/>(LangChain)"]
        ToolRouter["Semantic Router<br/>(Tool Calling)"]
    end

    subgraph Storage["💾 Storage Layer"]
        MySQL[("MySQL<br/>(Users, Documents, Status)")]
        ChromaDB[("ChromaDB<br/>(Vector Embeddings)")]
        Redis[("Redis<br/>(Task Queue Broker)")]
    end

    subgraph AI["🤖 AI Engine"]
        Ollama["Ollama Server<br/>(localhost:11434)"]
        Qwen["Qwen2.5-3B/7B<br/>Instruct"]
    end

    %% Admin Flow
    Auth --> DocManager
    DocManager -->|"Save PDF"| FileStorage
    DocManager -->|"POST /api/docs/process"| API_Doc
    API_Doc -->|"Dispatch Task"| Queue
    Queue --> OCR
    OCR --> Chunker
    Chunker --> Embedder
    Embedder -->|"Upsert Vectors"| ChromaDB
    Queue -->|"UPDATE status"| MySQL
    StatusMonitor -->|"SELECT status"| MySQL

    %% Chat Flow (Testing - React Widget)
    Widget -->|"POST /api/chat/stream"| API_Chat
    %% Chat Flow (Produksi - WhatsApp)
    WAWebhook -->|"POST /api/chat/message"| API_Chat
    API_Chat --> ToolRouter
    ToolRouter -->|"Intent: Tanya SOP"| RAGChain
    RAGChain -->|"Similarity Search"| ChromaDB
    RAGChain -->|"Generate Answer"| Ollama
    Ollama --- Qwen
    API_Chat -->|"SSE Stream"| Widget
    API_Chat -->|"JSON Response"| WAWebhook

    %% Queue Broker
    API_Doc -->|"Enqueue"| Redis
    Redis -->|"Dequeue"| Queue

    style Frontend fill:#1a1a2e,stroke:#e94560,color:#fff
    style Laravel fill:#0f3460,stroke:#16213e,color:#fff
    style Python fill:#533483,stroke:#2b2d42,color:#fff
    style Storage fill:#1b1b2f,stroke:#e2e2e2,color:#fff
    style AI fill:#2d4059,stroke:#ea5455,color:#fff
```

---

## 2. Alur Data Detail

### A. Alur Upload & Pemrosesan Dokumen (Admin)

```mermaid
sequenceDiagram
    participant Admin
    participant Laravel
    participant MySQL
    participant FastAPI as Python (FastAPI)
    participant Redis
    participant Celery as Celery Worker
    participant OCR as Tesseract OCR
    participant ChromaDB

    Admin->>Laravel: Upload PDF baru (replace)
    Laravel->>Laravel: Simpan file ke /storage
    Laravel->>MySQL: INSERT/UPDATE documents (status='processing')
    Laravel->>FastAPI: POST /api/docs/process
    FastAPI->>Redis: Enqueue task
    FastAPI-->>Laravel: 202 Accepted ("Sedang diproses")
    Laravel-->>Admin: "Dokumen sedang diproses di latar belakang ✅"

    Note over Admin,Laravel: Admin bebas menutup browser / lanjut kerja

    Redis->>Celery: Dequeue task
    Celery->>Celery: Deteksi PDF (teks / scan gambar?)

    alt PDF Scan Gambar
        Celery->>OCR: Ekstrak teks via OCR
        OCR-->>Celery: Teks hasil OCR
    else PDF Teks Biasa
        Celery->>Celery: Ekstrak teks langsung (PyMuPDF)
    end

    Celery->>Celery: Chunking teks (split per ~500 token)
    Celery->>ChromaDB: DELETE vektor lama (by document_id)
    Celery->>ChromaDB: INSERT vektor baru + metadata
    Celery->>MySQL: UPDATE status='completed'

    Note over Admin,MySQL: Saat Admin buka dashboard lagi...
    Admin->>Laravel: Buka halaman Dokumen
    Laravel->>MySQL: SELECT status
    MySQL-->>Laravel: status='completed'
    Laravel-->>Admin: Badge hijau "✅ Selesai Diproses"
```

### B. Alur Chat — Testing (React Widget)

```mermaid
sequenceDiagram
    participant User as End-User (Browser)
    participant Widget as React Chat Widget
    participant FastAPI as Python (FastAPI)
    participant Router as Semantic Router
    participant ChromaDB
    participant Ollama as Ollama (Qwen2.5)

    User->>Widget: Ketik pertanyaan
    Widget->>FastAPI: POST /api/chat/stream

    FastAPI->>Router: Analisis intent pengguna

    alt Intent: Tanya SOP/Aturan
        Router->>ChromaDB: Similarity search (top-k=5)
        ChromaDB-->>Router: Chunk dokumen relevan
        Router->>Ollama: Prompt = System + Context + Query
        Ollama-->>FastAPI: Token stream (SSE)
    else Intent: Cek Tiket (Fase Selanjutnya)
        Router->>Router: Call fungsi cek_tiket()
        Note over Router: (Belum diimplementasi - MVP)
    end

    loop Setiap Token
        FastAPI-->>Widget: data: {"chunk": "..."}
    end
    FastAPI-->>Widget: data: {"sources": [...]}
    Widget-->>User: Jawaban + sumber dokumen
```

### C. Alur Chat — Produksi (WhatsApp)

```mermaid
sequenceDiagram
    participant User as End-User (HP)
    participant WA as WhatsApp Business API
    participant FastAPI as Python (FastAPI)
    participant Router as Semantic Router
    participant ChromaDB
    participant Ollama as Ollama (Qwen2.5)

    User->>WA: Kirim pesan WhatsApp
    WA->>FastAPI: POST /api/chat/message (webhook)

    FastAPI->>Router: Analisis intent pengguna
    Router->>ChromaDB: Similarity search (top-k=5)
    ChromaDB-->>Router: Chunk dokumen relevan
    Router->>Ollama: Prompt = System + Context + Query
    Ollama-->>FastAPI: Full response

    FastAPI-->>WA: JSON {reply, sources}
    WA-->>User: Pesan balasan otomatis di WhatsApp
```

---

## 3. Struktur Proyek

```
agentic-ai/
├── 📁 laravel-admin/              # Dashboard Admin (Laravel)
│   ├── app/
│   │   ├── Http/Controllers/
│   │   │   ├── AuthController.php
│   │   │   └── DocumentController.php
│   │   ├── Models/
│   │   │   ├── User.php
│   │   │   └── Document.php
│   │   └── Services/
│   │       └── AiMicroserviceClient.php    # HTTP client ke Python
│   ├── resources/views/
│   │   ├── dashboard.blade.php
│   │   └── documents/
│   │       ├── index.blade.php             # Daftar PDF + status badge
│   │       └── show.blade.php              # Preview PDF (PDF.js)
│   ├── routes/
│   │   └── web.php
│   ├── database/migrations/
│   │   └── xxxx_create_documents_table.php
│   ├── .env
│   └── docker/
│       └── Dockerfile
│
├── 📁 python-ai/                  # AI Microservice (FastAPI)
│   ├── app/
│   │   ├── main.py                         # FastAPI entry point
│   │   ├── config.py                       # LLM_MODEL, EMBEDDING_MODEL, dll.
│   │   ├── routers/
│   │   │   ├── documents.py                # POST /api/docs/process
│   │   │   └── chat.py                     # POST /api/chat/stream (SSE)
│   │   ├── services/
│   │   │   ├── pdf_processor.py            # OCR detection + extraction
│   │   │   ├── embedding_service.py        # Chunking + ChromaDB upsert
│   │   │   ├── rag_service.py              # RAG chain (retrieval + LLM)
│   │   │   └── tool_router.py              # Semantic routing / tool calling
│   │   └── tasks/
│   │       └── process_document.py         # Celery async task
│   ├── requirements.txt
│   ├── .env
│   └── docker/
│       └── Dockerfile
│
├── 📁 react-widget/               # Chat Widget — TESTING ONLY (React.js)
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── ChatWidget.jsx
│   │   │   ├── MessageBubble.jsx
│   │   │   └── SourceReference.jsx
│   │   └── hooks/
│   │       └── useStreamChat.js            # SSE stream handler
│   ├── package.json
│   └── vite.config.js
│   ⚠️ Folder ini TIDAK di-deploy ke produksi.
│      Produksi menggunakan WhatsApp Business API webhook.
│
├── 📄 docker-compose.yml          # Orkestrasi semua service
├── 📄 .env.example                # Template environment variables
└── 📄 README.md
```

---

## 4. Skema Database (MySQL — Laravel)

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
        string title "Nama dokumen (SOP Jaringan 2026)"
        string original_filename "file asli yang diupload"
        string storage_path "path di storage Laravel"
        enum status "pending | processing | completed | failed"
        enum pdf_type "text | scanned | mixed | unknown"
        text error_message "nullable - pesan error jika gagal"
        integer total_pages "nullable - jumlah halaman PDF"
        integer total_chunks "nullable - jumlah chunk di ChromaDB"
        bigint uploaded_by FK "FK ke users.id"
        timestamp processed_at "nullable - waktu selesai proses"
        timestamp created_at
        timestamp updated_at
    }

    document_logs {
        bigint id PK
        bigint document_id FK
        enum action "uploaded | processing | ocr_started | embedding_started | completed | failed | replaced"
        text details "nullable - detail log"
        timestamp created_at
    }

    users ||--o{ documents : "uploads"
    documents ||--o{ document_logs : "has logs"
```

### Penjelasan Kolom Penting

| Kolom           | Fungsi                                                                                              |
| --------------- | --------------------------------------------------------------------------------------------------- |
| `status`        | Digunakan Laravel untuk menampilkan badge warna (kuning=processing, hijau=completed, merah=failed)  |
| `pdf_type`      | Diisi Python setelah deteksi, memberi tahu admin apakah PDF nya text murni atau hasil scan          |
| `total_chunks`  | Diisi Python setelah embedding selesai, membantu admin memahami seberapa "besar" dokumen di mata AI |
| `error_message` | Jika proses OCR/embedding gagal, Python menyimpan pesan error agar admin tahu penyebabnya           |
| `document_logs` | Tabel audit trail — mencatat riwayat setiap aksi pada dokumen                                       |

---

## 5. Konfigurasi Environment (`.env`)

### Python AI Microservice (`python-ai/.env`)

```env
# === LLM Configuration ===
# Fase 1 (Testing Lokal): qwen2.5:3b
# Fase 2 (Produksi Server): qwen2.5:7b
LLM_MODEL_NAME=qwen2.5:3b
OLLAMA_BASE_URL=http://localhost:11434

# === Embedding ===
EMBEDDING_MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2

# === Vector DB ===
CHROMA_PERSIST_DIR=./data/chromadb

# === Database (Shared with Laravel) ===
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=agentic_copilot
MYSQL_USER=root
MYSQL_PASSWORD=secret

# === Queue (Celery) ===
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# === Security ===
INTERNAL_API_TOKEN=your-secure-internal-token-here
```

### Laravel Admin (`laravel-admin/.env`)

```env
# === App ===
APP_NAME="Agentic Copilot Admin"
APP_URL=http://localhost:8000

# === Database ===
DB_CONNECTION=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_DATABASE=agentic_copilot
DB_USERNAME=root
DB_PASSWORD=secret

# === Python Microservice ===
AI_SERVICE_URL=http://localhost:8080
AI_SERVICE_TOKEN=your-secure-internal-token-here
```

---

## 6. Tech Stack Summary

| Layer                     | Teknologi                             | Versi / Catatan                  |
| ------------------------- | ------------------------------------- | -------------------------------- |
| **Dashboard Admin**       | Laravel (PHP)                         | v11.x                            |
| **AI Microservice**       | Python + FastAPI                      | Python 3.11+                     |
| **Chat Widget (Testing)** | React.js + Vite                       | v18+ — dev/demo only             |
| **Channel Produksi**      | WhatsApp Business API                 | Webhook → POST /api/chat/message |
| **LLM Runtime**           | Ollama                                | Latest                           |
| **LLM Model**             | Qwen2.5-Instruct                      | 3B (test) → 7B (prod)            |
| **Embedding**             | paraphrase-multilingual-MiniLM-L12-v2 | via SentenceTransformers         |
| **Vector DB**             | ChromaDB                              | Persistent mode                  |
| **OCR**                   | Tesseract OCR                         | v5.x + pytesseract               |
| **PDF Parsing**           | PyMuPDF (fitz)                        | Deteksi teks vs scan             |
| **AI Orchestration**      | LangChain                             | Latest                           |
| **Task Queue**            | Celery + Redis                        | Async background jobs            |
| **Database**              | MySQL                                 | v8.x                             |
| **Containerization**      | Docker Compose                        | Multi-service                    |
