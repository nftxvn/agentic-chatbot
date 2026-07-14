# Spesifikasi API (API Spec)

Antarmuka komunikasi internal dan eksternal antara Laravel, Python Microservice, dan berbagai channel chat (React Widget untuk testing, WhatsApp untuk produksi).

> **Catatan Arsitektur:** API Chat di Python bersifat *channel-agnostic*. Endpoint yang sama (`POST /api/chat`) melayani React Widget (testing) maupun WhatsApp Webhook (produksi). Tidak ada perubahan kode backend saat berpindah channel.

---

## 1. Komunikasi Laravel -> Python (Manajemen Dokumen)

Saat Admin mengunggah dokumen baru (menimpa yang lama), Laravel menyimpan file ke *storage* lokal (atau *shared storage*) dan memicu proses di Python.

### `POST /api/docs/process` (Internal Network)
**Fungsi:** Memicu proses pembaruan dokumen (OCR + Embedding) ke dalam antrean (Queue) di latar belakang.
- **Base URL:** `http://python-service:8000`
- **Headers:** `Authorization: Bearer <internal_token>`
- **Payload (JSON):**
  ```json
  {
    "document_id": 12,
    "file_path": "/var/www/html/storage/app/public/documents/peraturan_v2.pdf",
    "action": "overwrite"
  }
  ```
- **Response (202 Accepted):**
  ```json
  {
    "status": "processing_started",
    "message": "Dokumen masuk ke antrean pemrosesan AI."
  }
  ```

---

## 2. Komunikasi Python -> MySQL (Update Status Asynchronous)

Untuk menghindari keharusan Laravel menunggu *(timeout)*, Python memproses OCR dan Embedding di latar belakang (bisa memakan waktu 10+ menit untuk 170 halaman di CPU). 

Setelah selesai, Python **secara langsung** mengeksekusi koneksi MySQL untuk memperbarui status di tabel `documents` milik Laravel.

**Query Eksekusi Python (via SQLAlchemy/PyMySQL):**
```sql
UPDATE documents 
SET status = 'completed', updated_at = NOW() 
WHERE id = 12;
```
*(Catatan: Di sisi Dashboard Laravel, Admin bisa dibuatkan fitur "Polling" AJAX / Livewire sederhana setiap 10 detik untuk me-refresh status di tabel jika status masih 'processing', sehingga tulisan berubah hijau saat Python selesai).*

---

## 3. Chat API — Channel-Agnostic (Testing & Produksi)

Endpoint chat yang sama digunakan oleh **React Widget (testing)** maupun **WhatsApp Webhook (produksi)**. Tidak perlu mengubah kode backend saat berpindah channel.

### `POST /api/chat/stream` — Untuk React Widget (Testing/SSE)
**Fungsi:** Mengirim pertanyaan dan menerima respons berformat *Server-Sent Events (SSE)* agar teks muncul mengetik sedikit demi sedikit.
- **Base URL:** `http://localhost:8080` (testing)
- **Headers:** `Content-Type: application/json`
- **Payload (JSON):**
  ```json
  {
    "session_id": "sesi-987-xyz",
    "query": "Apa persyaratan untuk memperpanjang izin?"
  }
  ```
- **Response (200 OK - text/event-stream):**
  ```text
  data: {"chunk": "Untuk "}
  data: {"chunk": "memperpanjang "}
  data: {"chunk": "izin, "}
  data: {"chunk": "Anda "}
  data: {"chunk": "harus..."}
  ...
  data: {"sources": [{"doc_name": "SOP_Perizinan_2026.pdf", "page": 45}]}
  ```

### `POST /api/chat/message` — Untuk WhatsApp Webhook (Produksi)
**Fungsi:** Endpoint non-streaming. Menerima pesan dari WhatsApp Business API webhook, memproses pertanyaan, dan mengembalikan jawaban lengkap dalam satu respons JSON (karena WhatsApp tidak mendukung SSE).
- **Base URL:** `https://api-ai.diskominfotik.go.id`
- **Headers:** `Content-Type: application/json`, `Authorization: Bearer <wa_webhook_token>`
- **Payload (JSON):**
  ```json
  {
    "phone_number": "6281234567890",
    "message": "Apa persyaratan untuk memperpanjang izin?"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "reply": "Untuk memperpanjang izin, Anda harus menyiapkan: 1. Surat permohonan...",
    "sources": [
      {"doc_name": "SOP_Perizinan_2026.pdf", "page": 45}
    ]
  }
  ```
- **Catatan:** Respons JSON ini kemudian dikirim balik ke pengguna WhatsApp oleh middleware/gateway WhatsApp Business API.
