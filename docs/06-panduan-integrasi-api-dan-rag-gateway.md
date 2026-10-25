# Panduan Integrasi Public API dan WhatsApp

Panduan ini berisi langkah konfigurasi dan contoh pemanggilan. Field, bentuk
respons, kode status dan signature webhook mengacu pada
[spesifikasi API](03-api_spec_agentic_copilot.md); topologi dan alur layanan
ada pada [arsitektur sistem](02-arsitektur_sistem_agentic_copilot.md).
Contoh ditujukan untuk lingkungan pengujian dengan kredensial placeholder.

## 1. Menyiapkan API key

Dua endpoint chat publik, `POST /api/v1/chat` dan `POST /api/v1/chat/stream`, memerlukan **Kunci API** aktif. Endpoint webhook kanal bawaan berada di luar middleware API key chat; autentikasi/verifikasi kanal mengikuti kontrak webhook masing-masing.

### Cara Mendapatkan Kunci API:
1. Masuk ke Dashboard Admin -> halaman **Integrasi** (`/integrations`). Rute lama `/settings/api-keys` mengarahkan ke halaman ini.
2. Klik tombol **"Buat Kunci API Baru"**.
3. Masukkan nama identifikasi aplikasi pemanggil (contoh: *"Portal Web Diskominfo"*, *"Server Bot WhatsApp"*).
4. Salin dan simpan token rahasia berformat `sk_live_xxxxxxxxxxxxxxxxxxxxxxxx` yang muncul di layar.
   > **Penting:** Demi alasan keamanan, token lengkap hanya ditampilkan satu kali saat pembuatan.

Kirim API key melalui `Authorization: Bearer <API_KEY>` atau `X-API-Key` sesuai
[kontrak autentikasi publik](03-api_spec_agentic_copilot.md#public-api-gateway-laravel).

## 2. Memilih mode chat dan menerima balasan petugas

Gunakan `POST /api/v1/chat` untuk satu respons JSON dan
`POST /api/v1/chat/stream` untuk SSE. Gunakan `session_id` yang sama untuk
percakapan yang sama; `document_ids` dapat membatasi korpus. Aturan validasi,
flag fallback/takeover dan event stream dirinci pada spesifikasi API.
Base URL contoh adalah `http://localhost:8000`; sesuaikan dengan server tujuan.

Jika AI meneruskan percakapan ke petugas, gunakan `session_id` yang sama pada setiap permintaan. Respons JSON akan memuat `is_human_takeover: true` dan `ticket_id`. Balasan petugas dicatat sebagai tiket di Live Chat & Tiket; agar balasan itu sampai ke aplikasi pemanggil API, atur **Webhook Balasan Tiket** pada menu **Integrasi & API Gateway** untuk API key terkait:

1. Masukkan URL HTTPS milik aplikasi penerima.
2. Buat secret webhook dan simpan secret tersebut di konfigurasi rahasia aplikasi penerima.
3. Aktifkan webhook dan pastikan aplikasi penerima membalas HTTP `2xx`.

Bentuk payload `ticket.reply.created`, header dan rumus HMAC tersedia pada
[kontrak webhook balasan](03-api_spec_agentic_copilot.md#balasan-petugas-melalui-webhook).
Verifikasi signature terhadap body mentah, tolak timestamp terlalu lama dan
cegah pemrosesan ulang `event_id`. Hubungkan `ticket.session_id` dengan
percakapan pemanggil. URL penerima harus dapat dijangkau server SAPA;
`localhost` hanya berlaku pada mesin/server yang sama.

## 3. Contoh kode integrasi

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

### 4. Membaca SSE dengan Fetch

Contoh pembacaan ini dapat dipakai pada aplikasi pemanggil dengan penempatan kredensial yang sesuai. Untuk widget publik, simpan API key pada backend aplikasi dan teruskan stream melalui proxy aplikasi tersebut; alamat proxy ditentukan integrator, bukan endpoint tambahan yang disediakan repo ini. `INTERNAL_API_TOKEN` Python tetap hanya untuk komunikasi server.

Buffer menyimpan sisa baris antar-read dan decoder mempertahankan karakter UTF-8 yang terpotong. Contoh memproses format satu baris JSON `data:` yang dikirim layanan ini; batas paket jaringan tidak dianggap sebagai batas event.
```javascript
async function streamChatbot(query, onChunkReceived) {
  const response = await fetch("http://localhost:8000/api/v1/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": "Bearer sk_live_YOUR_API_KEY",
    },
    body: JSON.stringify({ session_id: "web-stream-123", query }),
  });
  if (!response.ok || !response.body) {
    throw new Error(`Chat stream gagal: HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  const consumeLine = line => {
    if (!line.startsWith("data:")) return false;
    const data = line.slice(5).trim();
    if (!data) return false;
    const event = JSON.parse(data);
    if (event.type === "error") throw new Error(event.content || "Stream gagal");
    if (event.type === "chunk") onChunkReceived(event.content);
    return event.type === "done";
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      pending += done ? decoder.decode() : decoder.decode(value, { stream: true });
      let newline;
      while ((newline = pending.indexOf("\n")) !== -1) {
        const line = pending.slice(0, newline).replace(/\r$/, "");
        pending = pending.slice(newline + 1);
        if (consumeLine(line)) return;
      }
      if (done) {
        if (pending.trim()) consumeLine(pending.replace(/\r$/, ""));
        return;
      }
    }
  } finally {
    try {
      await reader.cancel();
    } catch {
      // Kegagalan cleanup tidak menutupi error request/stream sebelumnya.
    } finally {
      reader.releaseLock();
    }
  }
}
```

---

## 4. Konfigurasi WhatsApp Gateway

Handler webhook menyediakan parsing Meta WhatsApp Cloud API dan field fallback gateway generik. Pengiriman keluar membentuk payload Meta atau gateway generik melalui `WhatsAppGateway`; cocokkan field/auth provider yang dipakai dengan implementasi tersebut, dan uji melalui endpoint penerima pengujian.

### A. Konfigurasi di Menu "Integrasi WhatsApp"
1. Buka Menu **Integrasi WhatsApp** (`/settings/whatsapp`).
2. Aktifkan toggle **"Status Chatbot WhatsApp"**.
3. Masukkan **URL Endpoint API Gateway Pengirim**:
   * Contoh Meta Cloud API: `https://graph.facebook.com/<GRAPH_API_VERSION>/<PHONE_NUMBER_ID>/messages`
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

## 5. Memeriksa hasil integrasi

- Baca status HTTP serta flag JSON sesuai
  [spesifikasi API](03-api_spec_agentic_copilot.md#status-http-public-api).
  HTTP 200 dapat memuat fallback atau handoff; pada SSE tangani event error.
- Gunakan [panduan observabilitas](07-observabilitas-dan-telemetri-rag.md)
  untuk log metadata, analitik dan health. Log Public API bukan transkrip
  percakapan; jalur stream publik tidak membuat `ChatLog` saat ini.
- Uji balasan petugas dan pengiriman kanal pada penerima uji yang ditentukan.
  Pesan tersimpan atau suite unit lulus tidak membuktikan penerimaan eksternal.
