# Spesifikasi API (API Specification)

Dokumen ini merupakan spesifikasi antarmuka komunikasi resmi (*API Specification*) pada platform **Central RAG Hub Layanan Informasi Diskominfotik Kota Banda Aceh**.

Platform ini memiliki tiga kelompok antarmuka:
1. **Public API Gateway (`/api/v1`)** — Disediakan oleh Laravel untuk konsumsi pihak ketiga, Web Widget, dan Bot WhatsApp.
2. **Admin Management API (`/api`)** — Disediakan oleh Laravel untuk aplikasi Single Page Application (SPA) Admin Frontend.
3. **Internal AI Microservice API** — Disediakan oleh Python FastAPI (Port 8080) untuk pemrosesan RAG, ekstraksi dokumen, dan inferensi LLM.

---

## 1. Standar Format Server-Sent Events (SSE)

Seluruh komunikasi *streaming* (baik dari Python AI maupun yang diteruskan oleh Laravel Gateway) mematuhi format event terstandarisasi berupa objek JSON `{"type": ..., "content": ...}`:

```text
data: {"type": "trace", "content": {"stage": 1, "title": "Mencari konteks di ChromaDB & BM25..."}}
data: {"type": "trace", "content": {"stage": 2, "title": "RRF Re-ranking (k=60) & evaluasi guards..."}}
data: {"type": "trace", "content": {"stage": 3, "title": "Mengirim konteks ke Ollama (qwen3:8b)..."}}
data: {"type": "chunk", "content": "Untuk "}
data: {"type": "chunk", "content": "mengajukan permohonan, "}
data: {"type": "chunk", "content": "Anda perlu membawa dokumen..."}
data: {"type": "telemetry", "content": {"latency_ms": 1420, "context_tokens": 820, "grounding": "grounded", "model": "qwen3:8b"}}
data: {"type": "sources", "content": [{"doc_name": "SOP_Layanan_2025.pdf", "document_id": 1, "page": 14}]}
data: {"type": "done", "content": ""}
```

### Tipe Event:
| `type` | Deskripsi |
| :--- | :--- |
| `trace` | Tahapan live pipeline RAG untuk visualisasi progress bar (*Playground*) |
| `chunk` | Potongan teks balasan LLM yang digabungkan berurutan oleh UI |
| `telemetry` | Data diagnostik (latensi milidetik, estimasi token, status grounding) |
| `sources` | Daftar dokumen dan nomor halaman rujukan resmi |
| `done` | Penanda aliran stream selesai secara normal |
| `error` | Penanda terjadinya kesalahan eksekusi di tengah pipeline |

---

## 2. Public API Gateway (Laravel `/api/v1`)

Kanal publik untuk integrasi eksternal. Otentikasi menggunakan **Bearer API Key** (`Authorization: Bearer sk_live_xxx`).

### 2.1 Chat Stream
- **Method:** `POST /api/v1/chat/stream`
- **Headers:**
  - `Authorization: Bearer sk_live_xxxxxxxxxxxxxxxx`
  - `Content-Type: application/json`
  - `Accept: text/event-stream`
- **Request Body:**
  ```json
  {
    "message": "Bagaimana prosedur permohonan subdomain pemko?",
    "session_id": "client-session-12345",
    "document_ids": [1, 2]
  }
  ```
- **Response:** `200 OK` (`text/event-stream` dengan payload SSE standar).

### 2.2 Chat Synchronous (Non-Streaming)
- **Method:** `POST /api/v1/chat`
- **Headers:**
  - `Authorization: Bearer sk_live_xxxxxxxxxxxxxxxx`
  - `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "message": "Bagaimana prosedur permohonan subdomain pemko?",
    "session_id": "client-session-12345"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "status": "success",
    "session_id": "client-session-12345",
    "reply": "Prosedur permohonan subdomain adalah sebagai berikut...",
    "sources": [
      {
        "document_id": 1,
        "doc_name": "SOP_Pengelolaan_Domain_2025.pdf",
        "page": 12
      }
    ],
    "telemetry": {
      "latency_ms": 1250,
      "tokens": 480,
      "grounded": true
    }
  }
  ```

### 2.3 Fast Paths & Direktori Publik
- **`GET /api/v1/fast-paths`** — Mengambil daftar menu pintas / pertanyaan umum yang aktif.
- **`GET /api/v1/directories`** — Mengambil daftar kontak layanan OPD / nomor penting.
- **`GET /api/v1/health`** — Memeriksa status kesehatan gateway dan AI engine.

---

## 3. Admin Management API (Laravel `/api`)

Kanal administrasi untuk SPA Frontend. Otentikasi menggunakan **Sanctum Token** (`Authorization: Bearer <sanctum_token>`).

### 3.1 Autentikasi
- `POST /api/auth/login` — Autentikasi admin (email & password). Mengembalikan auth token & profil user.
- `POST /api/auth/logout` — Mencabut token aktif.
- `GET /api/auth/me` — Mengambil profil admin saat ini.

### 3.2 Manajemen Dokumen & Kategori
- `GET /api/documents` — Mengambil seluruh dokumen dengan filter status & kategori.
- `POST /api/documents` — Unggah file PDF baru (`multipart/form-data`).
- `GET /api/documents/{id}` — Detail dokumen, riwayat log pemrosesan, dan metadata.
- `DELETE /api/documents/{id}` — Menghapus file dan vektor terkait di ChromaDB.
- `GET /api/categories` & `POST /api/categories` — CRUD pengelompokan kategori SOP.

### 3.3 Ekstraksi Bertahap & Koreksi Manual OCR
- `POST /api/ekstraksi/jobs/{document_id}/start` — Memulai tugas ekstraksi berjenjang.
- `POST /api/ekstraksi/jobs/{document_id}/pause` — Mengirim sinyal jeda ekstraksi.
- `POST /api/ekstraksi/jobs/{document_id}/resume` — Melanjutkan ekstraksi dari halaman terakhir.
- `GET /api/ekstraksi/jobs/{document_id}/status` — Status progres, halaman selesai/total.
- `GET /api/ekstraksi/jobs/{document_id}/pages/{page}/preview` — Citra pindaian dan teks hasil OCR.
- `PUT /api/ekstraksi/jobs/{document_id}/pages/{page}/correct` — Menyimpan perbaikan teks manual dari admin.
- `POST /api/ekstraksi/jobs/{document_id}/embed` — Memotong chunk Parent-Child dan mengindeks ke ChromaDB.

### 3.4 Manajemen Kunci API (API Keys)
- `GET /api/api-keys` — Daftar seluruh API Key beserta statistik penggunaan.
- `POST /api/api-keys` — Membuat API Key baru (mengembalikan plain token satu kali).
- `PUT /api/api-keys/{id}` — Mengubah status aktif, kuota rate limit, atau nama kunci.
- `DELETE /api/api-keys/{id}` — Mencabut/menghapus kunci API.

### 3.5 Chat Logs & Telemetri
- `GET /api/chat-logs` — Riwayat tanya-jawab dari semua kanal dengan filter tanggal & kanal.
- `GET /api/chat-logs/metrics` — Agregasi latensi rata-rata, tingkat grounding, dan total token.
- `GET /api/chat-logs/{id}` — Detail log percakapan dan sumber rujukan yang digunakan.

### 3.6 Pengaturan Sistem & Playground
- `GET /api/settings` — Mengambil konfigurasi prompt sistem aktif, model Ollama, dan parameter RAG.
- `POST /api/settings` — Memperbarui pengaturan prompt dan parameter inferensi.
- `GET /api/settings/models` — Mendeteksi model yang tersedia di Ollama lokal.

---

## 4. Internal AI Microservice API (Python FastAPI - Port 8080)

Endpoint backend-to-backend berkecepatan tinggi. Otentikasi menggunakan header internal `Authorization: Bearer <INTERNAL_API_TOKEN>`.

### 4.1 Chat Streaming
- **Method:** `POST /api/chat/stream`
- **Request Body:**
  ```json
  {
    "query": "Apa syarat permohonan sertifikat elektronik?",
    "session_id": "sesi-internal-456",
    "document_ids": null,
    "system_prompt": "Anda adalah asisten cerdas...",
    "temperature": 0.1,
    "top_k": 5
  }
  ```
- **Response:** `200 OK` (`text/event-stream`).

### 4.2 Ekstraksi Dokumen Asinkron
- **Method:** `POST /api/docs/process`
- **Request Body:**
  ```json
  {
    "document_id": 1,
    "file_path": "/storage/documents/sop-2025.pdf",
    "action": "overwrite"
  }
  ```
- **Response:** `202 Accepted` (`{"status": "accepted", "message": "Dokumen sedang diproses di latar belakang."}`).

### 4.3 Health Check Mikroservis
- **Method:** `GET /health` atau `GET /api/health`
- **Response (200 OK):**
  ```json
  {
    "status": "healthy",
    "service": "ai-service",
    "model": "qwen3:8b",
    "checks": {
      "chromadb": {"ok": true, "detail": "120 vektor"},
      "mysql": {"ok": true, "detail": "agentic_copilot"},
      "redis": {"ok": true, "detail": "PONG"},
      "ollama": {"ok": true, "detail": "qwen3:8b"}
    }
  }
  ```

