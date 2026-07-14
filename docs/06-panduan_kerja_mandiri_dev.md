# 🔧 Panduan Kerja Mandiri Antar Dev

## Proyek: Agentic IT Support Copilot

---

## ❓ Masalah

Dev 2 (Laravel) dan Dev 3 (React) **bergantung pada API Python** dari Dev 1.
Jika Dev 1 belum selesai atau sedang offline, Dev 2 & Dev 3 tidak bisa testing.

**Solusinya: Gunakan Mock API** — simulasi response API Python secara lokal.

---

## ✅ Dev 1 — Python AI (Tidak Ada Dependency)

Dev 1 bisa langsung kerja tanpa perlu menunggu siapa pun.

```bash
cd python-ai/
uvicorn main:app --reload
```

Setelah endpoint siap, **share base URL** ke Dev 2 & Dev 3:
```
AI_MICROSERVICE_URL=http://<ip-dev1>:8000
```

---

## 🟩 Dev 2 — Laravel (Mock API Python)

Buat route mock sementara di Laravel untuk simulasi response API Python.

### Langkah 1 — Buat file mock route

Buat file `routes/mock.php`:

```php
<?php
use Illuminate\Support\Facades\Route;

// Mock endpoint: trigger pemrosesan PDF
Route::post('/mock/documents/upload', function () {
    return response()->json([
        'message' => 'Dokumen diterima, sedang diproses',
        'document_id' => rand(1, 100),
        'status' => 'menunggu'
    ]);
});

// Mock endpoint: cek status dokumen
Route::get('/mock/documents/{id}/status', function ($id) {
    return response()->json([
        'document_id' => $id,
        'status' => 'selesai', // bisa diganti: menunggu, diproses, gagal
        'processed_at' => now()->toDateTimeString()
    ]);
});
```

### Langkah 2 — Daftarkan di `bootstrap/app.php` atau `RouteServiceProvider`

```php
Route::middleware('web')->group(base_path('routes/mock.php'));
```

### Langkah 3 — Set `.env` ke mock

```env
AI_MICROSERVICE_URL=http://localhost:8000/mock
```

### Langkah 4 — Saat API Dev 1 sudah siap

Ganti `.env` ke URL asli:
```env
AI_MICROSERVICE_URL=http://<ip-dev1>:8000
```
Hapus atau nonaktifkan `routes/mock.php`.

---

## 🟨 Dev 3 — React Widget (Mock API Python)

### Opsi A — Mock langsung di kode (paling simpel)

Buat file `src/mock/api.js`:

```js
export const mockChatResponse = async (message) => {
  // Simulasi delay seperti API asli
  await new Promise((res) => setTimeout(res, 800));

  return {
    answer: `[MOCK] Jawaban untuk: "${message}"`,
    sources: [
      { title: 'Panduan Layanan 2024.pdf', page: 3 },
    ],
  };
};
```

Gunakan di komponen chat:

```js
import { mockChatResponse } from '../mock/api';

const sendMessage = async (msg) => {
  // const res = await fetch(`${import.meta.env.VITE_API_URL}/api/chat`, ...) // ← pakai ini nanti
  const res = await mockChatResponse(msg); // ← mock dulu
  return res;
};
```

### Opsi B — Gunakan `json-server`

```bash
npm install -D json-server
```

Buat `mock-db.json`:

```json
{
  "chat": [
    {
      "answer": "Untuk mengurus SKCK, silakan kunjungi kantor polisi terdekat.",
      "sources": [{ "title": "Panduan SKCK 2024.pdf", "page": 1 }]
    }
  ]
}
```

Jalankan mock server:

```bash
npx json-server --watch mock-db.json --port 3001
```

Set `.env`:

```env
VITE_API_URL=http://localhost:3001
```

### Langkah — Saat API Dev 1 sudah siap

Hapus import mock, aktifkan kembali `fetch` ke API asli:
```env
VITE_API_URL=http://<ip-dev1>:8000
```

---

## 🔁 Alur Integrasi Bertahap

```
Minggu 1-2:
  Dev 1  → Bangun API Python (FastAPI)
  Dev 2  → Pakai mock route Laravel
  Dev 3  → Pakai mockChatResponse() lokal

Minggu 2-3:
  Dev 1  → API siap & share URL
  Dev 2  → Ganti .env → test integrasi nyata
  Dev 3  → Ganti .env → test integrasi nyata

Minggu 4:
  Semua  → Testing end-to-end bersama → PR ke main
```

---

## 📋 Checklist Sebelum Integrasi ke API Asli

| Cek | Dev 2 (Laravel) | Dev 3 (React) |
|---|---|---|
| ✅ | Ganti `AI_MICROSERVICE_URL` di `.env` | Ganti `VITE_API_URL` di `.env` |
| ✅ | Nonaktifkan `routes/mock.php` | Hapus import `mockChatResponse` |
| ✅ | Test upload PDF → cek status | Test kirim pesan → cek response |
| ✅ | Handle error jika API tidak respond | Handle error & loading state |

---

## 📞 Kontak Antar Dev

> Jika ada perubahan format request/response API, **Dev 1 wajib kabari Dev 2 & Dev 3 segera** via grup tim.
> Acuan format: [`05-api_spec_agentic_copilot.md`](./05-api_spec_agentic_copilot.md)
