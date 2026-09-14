# Panduan Integrasi API & Arsitektur Central RAG Gateway

Dokumen ini merupakan panduan resmi dan referensi teknis bagi pengembang, administrator sistem, dan integrasi pihak ketiga untuk memanfaatkan platform **Central RAG Hub Layanan Informasi Diskominfotik Kota Banda Aceh**.

---

## 1. Gambaran Umum Sistem

Platform ini berfungsi sebagai **Mesin AI & Basis Pengetahuan SOP Terpusat** (*Central RAG Hub as a Service*). Seluruh dokumen SOP kedinasan diunggah, diekstraksi, dan diindeks ke dalam basis data vektor (*ChromaDB*) dan pencarian kata kunci (*BM25*).

Setelah prompt dan parameter inferensi diatur dan diuji coba melalui **RAG Playground**, seluruh sistem lain di lingkungan pemerintah kota (seperti Bot WhatsApp, Portal Web Resmi, Aplikasi Mobile Layanan Publik, dan Helpdesk CRM) dapat mengonsumsi kecerdasan RAG ini melalui **Public API Gateway**.

```
[ KANAL KONSUMEN EKSTERNAL ]
┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐
│      WhatsApp Bot      │  │   Portal Web Resmi     │  │  Aplikasi Mobile / CRM │
└───────────┬────────────┘  └───────────┬────────────┘  └───────────┬────────────┘
            │                           │                           │
            │ Webhook / API Key         │ Bearer API Key            │ Bearer API Key
            ▼                           ▼                           ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                       LARAVEL API GATEWAY (Port 8000)                          │
│  - Otentikasi Kunci Akses (ApiKey Middleware: Bearer sk_live_xxx)              │
│  - Single Source of Truth: Injeksi otomatis prompt & parameter aktif dari DB   │
│  - Audit Trail & Logging Realtime (Tabel chat_logs)                            │
│  - Webhook Handler & Balasan Otomatis WhatsApp                                 │
└───────────────────────────────────────┬────────────────────────────────────────┘
                                        │
                                        │ Forward Query + Active Settings
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│                       PYTHON AI ENGINE (FastAPI - Port 8080)                   │
│  - Hybrid Search (ChromaDB Dense Vector + RankBM25 Sparse Retrieval)           │
│  - Reciprocal Rank Fusion (RRF) Re-ranking & Deduplikasi Konteks               │
│  - Inferensi LLM Lokal (Ollama / Qwen2.5)                                      │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Manajemen Kunci Akses (API Key)

Setiap pemanggilan ke endpoint publik diwajibkan menyertakan **Kunci API** yang sah untuk keperluan otentikasi, pembatasan hak akses, dan pencatatan audit trail.

### Cara Mendapatkan Kunci API:
1. Masuk ke Dashboard Admin -> Menu **Kunci API** (`/settings/api-keys`).
2. Klik tombol **"Buat Kunci API Baru"**.
3. Masukkan nama identifikasi aplikasi pemanggil (contoh: *"Portal Web Diskominfo"*, *"Server Bot WhatsApp"*).
4. Salin dan simpan token rahasia berformat `sk_live_xxxxxxxxxxxxxxxxxxxxxxxx` yang muncul di layar.
   > **Penting:** Demi alasan keamanan, token lengkap hanya ditampilkan satu kali saat pembuatan.

### Header Autentikasi:
Sertakan kunci API pada setiap HTTP Request menggunakan salah satu header berikut:
```http
Authorization: Bearer sk_live_xxxxxxxxxxxxxxxxxxxxxxxx
```
atau
```http
X-API-Key: sk_live_xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 3. Spesifikasi Public API (V1)

Base URL: `http://<domain-server>:8000/api/v1`

---

### A. Endpoint Mode JSON Standar (`POST /api/v1/chat`)

Digunakan untuk integrasi backend-to-backend, bot WhatsApp eksternal, atau aplikasi mobile yang membutuhkan respons lengkap dalam satu objek JSON.

* **URL Endpoint:** `POST /api/v1/chat`
* **Content-Type:** `application/json`
* **Autentikasi:** Wajib (`Bearer <API_KEY>`)

#### Request Body:

| Parameter | Tipe | Wajib | Keterangan |
| :--- | :--- | :--- | :--- |
| `query` | String | **Ya** | Pertanyaan dari pengguna (1 - 2000 karakter). |
| `session_id` | String | Tidak | Identifier sesi percakapan untuk *context tracking*. Default: acak. |
| `document_ids` | Array of Integer | Tidak | Batasi pencarian RAG pada ID dokumen tertentu. Kosongkan untuk seluruh korpus. |

#### Contoh Payload Request:
```json
{
  "session_id": "client-usr-0812345678",
  "query": "Bagaimana prosedur permohonan subdomain acehkota.go.id?",
  "document_ids": null
}
```

#### Format Response (200 OK):
```json
{
  "success": true,
  "session_id": "client-usr-0812345678",
  "query": "Bagaimana prosedur permohonan subdomain acehkota.go.id?",
  "answer": "Berdasarkan SOP Pengelolaan Domain dan Subdomain No. 04 Tahun 2024, prosedur permohonan meliputi:\n1. Mengisi formulir permohonan subdomain resmi.\n2. Melampirkan surat permohonan dari kepala OPD.\n3. Mengirimkan berkas ke Bidang e-Government Diskominfotik Kota Banda Aceh.\nWaktu penyelesaian permohonan adalah 1 (satu) hari kerja.",
  "sources": [
    {
      "document_id": 3,
      "doc_name": "SOP Pengelolaan Domain dan Subdomain.pdf",
      "page": 2
    }
  ],
  "execution_time_ms": 1120
}
```

---

### B. Endpoint Mode Realtime Streaming (`POST /api/v1/chat/stream`)

Digunakan untuk widget website interaktif yang menampilkan efek mengetik kata-per-kata secara langsung (*Server-Sent Events*).

* **URL Endpoint:** `POST /api/v1/chat/stream`
* **Content-Type:** `application/json`
* **Accept:** `text/event-stream`
* **Autentikasi:** Wajib (`Bearer <API_KEY>`)

#### Format Stream Event:
```http
data: {"type": "chunk", "content": "Berdasarkan "}

data: {"type": "chunk", "content": "SOP Pengelolaan "}

data: {"type": "chunk", "content": "Domain..."}

data: {"type": "done", "full_reply": "..."}
```

---

## 4. Contoh Kode Integrasi

### 1. cURL (Command Line)
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk_live_YOUR_API_KEY" \
  -d '{
    "session_id": "user-session-001",
    "query": "Apa persyaratan penerbitan sertifikat elektronik TTE?"
  }'
```

---

### 2. Python (Requests)
```python
import requests

url = "http://localhost:8000/api/v1/chat"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk_live_YOUR_API_KEY"
}
payload = {
    "session_id": "user-session-001",
    "query": "Apa persyaratan penerbitan sertifikat elektronik TTE?"
}

response = requests.post(url, headers=headers, json=payload, timeout=30)
if response.status_code == 200:
    data = response.json()
    print("Jawaban AI:\n", data.get("answer"))
    print("\nSumber Rujukan:", data.get("sources"))
else:
    print("Error:", response.status_code, response.text)
```

---

### 3. JavaScript / Node.js (Fetch JSON)
```javascript
async function askChatbot(query) {
  const response = await fetch("http://localhost:8000/api/v1/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer sk_live_YOUR_API_KEY",
    },
    body: JSON.stringify({
      session_id: "web-session-123",
      query: query,
    }),
  });

  const result = await response.json();
  if (result.success) {
    console.log("Jawaban:", result.answer);
    console.log("Rujukan SOP:", result.sources);
  } else {
    console.error("Gagal:", result.message);
  }
}

askChatbot("Bagaimana alur pengajuan email dinas?");
```

---

### 4. JavaScript Browser (Fetch Server-Sent Events Streaming)
```javascript
async function streamChatbot(query, onChunkReceived) {
  const response = await fetch("http://localhost:8000/api/v1/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer sk_live_YOUR_API_KEY",
    },
    body: JSON.stringify({
      session_id: "web-stream-123",
      query: query,
    }),
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunkStr = decoder.decode(value);
    const lines = chunkStr.split("\n");
    for (const line of lines) {
      if (line.startsWith("data:")) {
        try {
          const json = JSON.parse(line.slice(5).trim());
          if (json.type === "chunk") {
            onChunkReceived(json.content);
          }
        } catch (e) {
          // ignore parsing error for heartbeat / empty data
        }
      }
    }
  }
}
```

---

## 5. Panduan Integrasi WhatsApp Gateway

Sistem dilengkapi handler webhook bawaan yang kompatibel dengan **Meta WhatsApp Cloud API**, **Fonnte**, **Wablas**, atau gateway HTTP lainnya.

### A. Konfigurasi di Menu "Integrasi WhatsApp"
1. Buka Menu **Integrasi WhatsApp** (`/settings/whatsapp`).
2. Aktifkan toggle **"Status Chatbot WhatsApp"**.
3. Masukkan **URL Endpoint API Gateway Pengirim**:
   * Contoh Meta Cloud API: `https://graph.facebook.com/v19.0/<PHONE_NUMBER_ID>/messages`
   * Contoh Fonnte: `https://api.fonnte.com/send`
4. Masukkan **Bearer Access Token Gateway** dan simpan perubahan.

### B. Mendaftarkan Webhook Masuk
Salin URL Webhook berikut dan pasang pada pengaturan webhook Meta / WhatsApp Gateway Anda:
* **Callback URL:** `https://<domain-anda>/api/v1/webhook/whatsapp`
* **Verify Token:** `diskominfo_wa_rag_token` (dapat disesuaikan di menu pengaturan)

### C. Alur Kerja Pesan Masuk WhatsApp:
1. Warga mengirim pesan WhatsApp ke nomor dinas.
2. Gateway meneruskan pesan ke `POST /api/v1/webhook/whatsapp`.
3. Laravel memvalidasi status bot, lalu meneruskan pesan ke RAG Engine Python AI.
4. Jawaban diformat secara rapi dengan menyertakan rujukan dokumen SOP (`*Rujukan Dokumen SOP:* • Nama Dokumen (Hal. X)`).
5. Laravel otomatis memanggil endpoint gateway pengirim untuk membalas pesan ke nomor WhatsApp warga secara instan.

---

## 6. Riwayat Percakapan & Analitik Audit Trail

Seluruh percakapan yang masuk melalui WhatsApp maupun Public API secara otomatis dicatat pada menu **Riwayat & Analitik** (`/chat-logs`).

### Fitur Audit Trail:
* **Metrik KPI:** Total pertanyaan, volume per kanal, dan rasio *fallback* (informasi tidak ditemukan).
* **Evaluasi SOP (Unanswered Inquiries):** Daftar pertanyaan masyarakat yang belum ada jawabannya di dokumen SOP. Fitur ini membantu pengambil kebijakan mengetahui dokumen SOP apa yang perlu dibuat atau diunggah berikutnya.
* **Inspeksi Detail:** Memeriksa pertanyaan utuh, jawaban yang dihasilkan, dan daftar dokumen SOP beserta nomor halaman yang dirujuk.

---

## 7. Referensi Kode Status HTTP

| Status Code | Makna | Solusi / Tindakan |
| :--- | :--- | :--- |
| `200 OK` | Permintaan berhasil diproses. | Ambil data respons `answer` dan `sources`. |
| `401 Unauthorized` | API Key tidak valid, tidak disertakan, atau dinonaktifkan. | Periksa header `Authorization: Bearer <API_KEY>` di menu Kunci API. |
| `422 Unprocessable Entity` | Parameter input tidak valid (misal: field `query` kosong). | Pastikan request body berformat JSON yang benar. |
| `502 Bad Gateway` | Python AI Microservice mengembalikan error inferensi. | Periksa status service Python AI di port 8080. |
| `503 Service Unavailable` | Gagal terhubung ke Python AI (server mati/down). | Pastikan service `python-ai` berjalan via `bash start-all.sh`. |
