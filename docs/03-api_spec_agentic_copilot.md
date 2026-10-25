# Spesifikasi API SAPA

Dokumen ini merangkum kontrak HTTP yang tersedia saat ini. Kontrak yang dipakai aplikasi luar adalah **Public API Gateway Laravel**. API admin dan layanan Python AI adalah antarmuka terpisah.

## Public API Gateway Laravel

Base URL lokal: `http://localhost:8000`
Base URL server: `https://<domain-server>`

Kedua endpoint chat memerlukan API key aktif. Kirim key melalui salah satu header berikut:

```http
Authorization: Bearer <API_KEY>
```

atau:

```http
X-API-Key: <API_KEY>
```

API key dapat dibuat di dashboard **Integrasi**. Nilai lengkap hanya ditampilkan saat key dibuat.

### `POST /api/v1/chat`

Memproses satu pertanyaan dan mengembalikan satu objek JSON.

Header:

```http
Content-Type: application/json
Accept: application/json
Authorization: Bearer <API_KEY>
```

Request:

| Field | Tipe | Wajib | Aturan |
|---|---|---:|---|
| `query` | string | Ya | 1–2000 karakter. |
| `session_id` | string | Tidak | Maksimal 100 karakter. Pakai ID yang sama untuk percakapan yang sama. Jika tidak dikirim, server membuat ID sesi. |
| `document_ids` | array integer | Tidak | Membatasi pencarian ke dokumen yang disebutkan; `null` atau tidak dikirim berarti seluruh korpus yang tersedia. |

Contoh:

```json
{
  "query": "Bagaimana prosedur permohonan subdomain?",
  "session_id": "demo-001",
  "document_ids": null
}
```

Respons normal (`200 OK`):

```json
{
  "success": true,
  "session_id": "demo-001",
  "query": "Bagaimana prosedur permohonan subdomain?",
  "answer": "Jawaban berdasarkan dokumen yang tersedia.",
  "sources": [{"document_id": 42, "doc_name": "Contoh SOP.pdf", "page": 1}],
  "is_fallback": false,
  "is_human_takeover": false,
  "ticket_id": null,
  "ticket_number": null,
  "response_time_ms": 1120
}
```

`sources` berisi rujukan dokumen jika tersedia. Jika AI tidak dapat dijangkau atau mengembalikan respons gagal, gateway tetap mengembalikan fallback dengan status `200`, `is_fallback: true`, dan `degraded_mode: true`. Dalam fallback akibat kegagalan transport/upstream tersebut, `is_human_takeover`, `ticket_id`, dan `ticket_number` tidak disertakan. Respons upstream sukses dengan sumber kosong juga dapat ditandai `is_fallback: true` tanpa `degraded_mode`; flag ini sendiri tidak membuktikan gangguan koneksi.

Sitasi JSON membaca nomor halaman dari format retrieval ` - Halaman ...` dan
format em dash lama. Judul dipetakan ke `document_id` hanya jika cocok tepat dan
unik dalam `document_ids` permintaan. Untuk judul duplikat, tidak cocok, atau
tanpa scope, ID dapat tetap `null`; jangan menebak ID dari teks judul. Nomor
halaman dan nama juga bersifat opsional sesuai schema Python.

Jika sesi memiliki tiket aktif, pesan diteruskan ke petugas. Respons tetap `200`, dengan `is_human_takeover: true`, `ticket_id`, dan jawaban bahwa pesan telah diteruskan. `ticket_number` dapat tersedia pada respons ketika tiket ditemukan setelah pemrosesan AI.

### `POST /api/v1/chat/stream`

Mengirim jawaban secara bertahap menggunakan Server-Sent Events (SSE). Header dan body request sama dengan `/api/v1/chat`, dengan `Accept: text/event-stream`.

```http
Content-Type: application/json
Accept: text/event-stream
Authorization: Bearer <API_KEY>
```

```json
{
  "query": "Bagaimana prosedur permohonan subdomain?",
  "session_id": "demo-stream-001"
}
```

Setiap event dikirim sebagai JSON pada baris `data:`. Bentuk dasar yang perlu ditangani klien:

```text
data: {"type":"chunk","content":"Jawaban bertahap..."}

data: {"type":"done","content":""}
```

Jika sudah ada tiket aktif untuk `session_id` tersebut, gateway mengirim pesan status handoff dalam event `chunk`, lalu event `done`. Jika terjadi masalah saat stream, klien dapat menerima event `error` atau fallback berbentuk `chunk` di dalam stream. Public Gateway tidak meminta metadata debug dari layanan AI.

### Status HTTP Public API

| Status | Arti |
|---|---|
| `200` | Chat berhasil diproses, diteruskan ke petugas, atau menghasilkan fallback. Periksa field `is_fallback` dan `is_human_takeover`. |
| `401` | API key tidak ada, tidak valid, atau dinonaktifkan. |
| `422` | Body request tidak lolos validasi, misalnya `query` tidak ada atau lebih dari 2000 karakter. |

Kesalahan komunikasi dengan layanan AI pada endpoint JSON ditangani sebagai fallback `200`, bukan `502` atau `503` dari Public Gateway.

Contoh error autentikasi (`401 Unauthorized`):

```json
{
  "success": false,
  "message": "Autentikasi gagal: API Key tidak valid atau telah dinonaktifkan."
}
```

Error validasi (`422 Unprocessable Entity`) mengikuti format Laravel, dengan pesan dan daftar error per field:

```json
{
  "message": "The query field is required.",
  "errors": {
    "query": ["The query field is required."]
  }
}
```

### Balasan petugas melalui webhook

Webhook dikonfigurasi per API key melalui dashboard **Integrasi**. Saat petugas mengirim balasan publik pada tiket dari Public API, Laravel mengantrekan event `ticket.reply.created` ke URL penerima. Catatan internal tidak dikirim.

Contoh payload event:

```json
{
  "event": "ticket.reply.created",
  "event_id": "uuid-pengiriman",
  "ticket": {
    "id": 12,
    "number": "TICK-051026-001",
    "session_id": "client-usr-0812345678",
    "status": "in_progress",
    "channel": "api_v1"
  },
  "message": {
    "id": 45,
    "text": "Halo, kami siap membantu.",
    "sender": "Petugas Helpdesk",
    "sent_at": "2026-10-05T12:00:00.000000Z",
    "attachments": []
  },
  "sent_at": "2026-10-05T12:00:00.000000Z"
}
```

Contoh header:

```http
X-SAPA-Event: ticket.reply.created
X-SAPA-Delivery-Id: <event_id>
X-SAPA-Timestamp: <unix_timestamp>
X-SAPA-Signature: sha256=<hex_signature>
```

Tanda tangan adalah HMAC-SHA256 dari teks `{timestamp}.{raw_request_body}` menggunakan secret webhook. Penerima perlu memverifikasi tanda tangan terhadap body mentah sebelum memproses payload, dan sebaiknya mencegah pemrosesan ulang `event_id`. Pengiriman ulang dikelola oleh antrean Laravel.

## API Admin Laravel

Route admin berada di bawah prefix `/api`. Operasi dashboard dilindungi `auth:sanctum`; `POST /api/auth/login`, `POST /api/auth/forgot-password`, dan `POST /api/auth/reset-password` dapat dipanggil sebelum login. Frontend admin memakai sesi cookie Sanctum dan perlindungan CSRF; login tidak mengembalikan bearer token admin.

Kelompok endpoint mencakup autentikasi dan kata sandi, kategori, dokumen dan ekstraksi, API key dan webhook, chat log, fast-path, direktori, pengaturan, serta tiket helpdesk. Daftar route yang benar-benar aktif dapat dilihat dari direktori `laravel-admin` dengan:

```bash
php artisan route:list --path=api
```

Path gambar halaman dan PDF berada pada route `/api/documents/...` yang dilindungi sesi browser. Bentuk request dan response admin mengikuti controller aktif di `laravel-admin/app/Http/Controllers/Api/`.

### Kontrak dokumen dan ekstraksi yang dipertahankan

Upload menggunakan `POST /api/documents` dengan field `title`, `pdf_file`, dan `category_id` opsional. Nama field `pdf_file` tetap dipakai untuk seluruh format yang didukung: PDF, DOCX, XLSX, CSV, TXT, MD, PNG, JPG, JPEG, dan WEBP, dengan batas 50 MB.

| Operasi | Path | Respons normal |
| --- | --- | --- |
| Upload | `POST /api/documents` | `201`, metadata di `data.document`. |
| Ganti berkas | `POST /api/documents/{id}/replace` | `200`, ekstraksi lama dibersihkan dan pemrosesan dimulai ulang. |
| Batalkan / lanjutkan | `POST /api/documents/{id}/cancel` atau `/resume` | `200`, metadata terbaru di `data.document`. |
| Mulai ekstraksi | `POST /api/documents/{id}/extraction` | `202`, hasil antrean AI di `data`. |
| Minta jeda | `POST /api/documents/{id}/extraction/pause` | `202` pada permintaan pertama; `200` bila sudah dijeda atau sudah diminta. |
| Baca progres / halaman | `GET /api/documents/{id}/extraction` atau `/pages` | `200`, data AI atau fallback database lokal. |
| Simpan koreksi | `PUT /api/documents/{id}/pages/{pageNumber}` | `200`; teks dan tanda `diperiksa` diperbarui lokal setelah AI menerima koreksi. |
| Antrekan embedding | `POST /api/documents/{id}/embed` | `202`; penerimaan antrean belum berarti indeks selesai dibuat. |

Respons daftar menggunakan `data.documents`, `data.meta`, `data.stats`, dan `data.has_processing`; respons detail memakai `data.document` beserta log. Alias `original_filename`/`original_name` serta `total_chunks`/`vector_count` dipertahankan. Label status, progres halaman, dan metadata kategori disusun oleh `DocumentPresenter` agar dashboard memperoleh bentuk data yang sama. Bila tersedia, jumlah vektor aktif digunakan untuk jumlah chunk; dokumen selesai juga menyinkronkan nilai itu ke database.

Perilaku kegagalan yang perlu diperhitungkan klien:

- Ketika health check AI gagal saat upload atau resume, respons `503` tetap menyertakan metadata dokumen berstatus `failed`.
- Penolakan antrean saat upload tetap menghasilkan `201`, dengan dokumen dikembalikan ke `pending` dan penjelasan pada `error_message`. Resume mempertahankan respons berhasil setelah health check lolos, meskipun panggilan antrean berikutnya ditolak.
- Status live AI diprioritaskan bila tidak kosong. Fallback progres lokal tetap memperlakukan `halaman_total = 100` sebagai placeholder lama dan membatasi progres maksimum 100%.
- Kegagalan koreksi dan embedding meneruskan status/error AI sesuai endpoint; koreksi yang ditolak tidak mengganti teks lokal. Permintaan jeda tetap menyimpan flag lokal saat AI tidak tersedia.
- ID dokumen yang tidak ada menghasilkan `404` sebelum validasi payload pada endpoint yang memuat dokumen terlebih dahulu.

### Kontrak tiket helpdesk yang dipertahankan

`POST /api/v1/internal/chat-tickets` (alias `/api/v1/internal/tickets`) menerima eskalasi dari layanan internal. Middleware memprioritaskan bearer token, lalu `X-Internal-Token`, `X-AI-Service-Token`, dan `AI-Service-Token`. Payload wajib berisi `session_id` dan `message`; `ticket_id` serta data warga bersifat opsional.

- Tiket baru menghasilkan HTTP `201`; penambahan pesan ke tiket yang dipakai ulang menghasilkan HTTP `200`. Keduanya mengembalikan `success`, `message`, dan `data` berisi `ticket_id`, `ticket_number`, `status`, `session_id`, serta `created_at`.
- `ticket_id` yang diberikan wajib merujuk tiket yang ada dan diprioritaskan saat pencarian. Bila tidak diberikan, pencarian memakai tiket terbaru berdasarkan sesi atau kontak warga.
- Tiket `open` atau `in_progress` dipakai ulang. Tiket `resolved` atau `closed` dibuka kembali bila tanggal `created_at` atau `resolved_at` adalah hari ini; status menjadi `in_progress`, sedangkan `resolved_at` dan `closed_at` dikosongkan. Tiket selesai dari hari sebelumnya menghasilkan tiket baru bila kedua syarat tanggal tersebut tidak terpenuhi.
- Thread mencakup pesan sistem `Ticket Opened: ...`, `Ticket Re-opened: ...`, dan `Ticket Closed: ...` di samping pesan warga. Pesan sistem turut menghasilkan event `message.sent`; konsumen harus membedakan `sender_type` saat menghitung atau menampilkan pesan warga.

Balasan admin dikirim melalui `POST /api/tickets/{id}/messages` dengan sesi Sanctum. Teks, lampiran, atau kombinasi keduanya diterima. Jika keduanya kosong, respons HTTP `422` berbentuk `{"success": false, "message": "Pesan atau lampiran tidak boleh kosong."}`. Kesalahan tipe field tetap memakai format validasi Laravel. Catatan internal tetap tersimpan dan disiarkan ke dashboard, sementara pengiriman ke kanal warga serta webhook hanya berlaku bagi balasan publik.

### Konsumen live chat di frontend

Dashboard membaca `GET /api/tickets` dengan `status` opsional dan `search` yang telah di-trim; statistik diambil dari `GET /api/tickets/stats`. Keduanya diminta bersamaan, dengan kegagalan statistik ditoleransi. Pesan tiket dibaca dari `GET /api/tickets/{id}/messages`.

Frontend mempertahankan dukungan respons daftar/pesan pada kunci `data`, kunci lama `tickets`/`messages`, atau array langsung. Polling antrean/pesan berjalan setiap 5 detik; frontend halaman live chat belum berlangganan Reverb. Event browser `app-tickets-updated` menghubungkan pembaruan statistik halaman dengan badge/notifikasi layout.

Balasan tetap memakai endpoint dan field yang sama melalui `src/api/tickets.js`: JSON `{message}` untuk teks, atau multipart dengan `message` dan `file` untuk lampiran. Pemisahan state ke hook tidak menambahkan header autentikasi, endpoint, atau koneksi websocket baru.

### Kontrak pengaturan admin yang dipertahankan

Semua endpoint `/api/settings/*` berikut memakai sesi Sanctum; path, metode, nama route, middleware, dan bentuk respons tetap sama setelah pemisahan controller.

| Fitur | Metode dan path |
| --- | --- |
| WhatsApp | `GET`/`POST /api/settings/whatsapp`; `POST /api/settings/whatsapp/test` |
| Telegram | `GET`/`POST /api/settings/telegram`; `POST /api/settings/telegram/test`; `POST /api/settings/telegram/webhook` |
| Chatbot/RAG | `GET`/`POST /api/settings/chatbot`; `POST /api/settings/chatbot/reset` |
| Diagnostik | `GET /api/settings/models`; `GET /api/settings/hardware`; `POST /api/settings/models/benchmark` |

- Respons baca menyamarkan token WhatsApp/Telegram yang tersimpan dengan `••••••••••••`. Mengirim nilai masker itu mempertahankan token; mengosongkan **atau tidak menyertakan field token** pada update kanal menghapus token. Update ini bukan patch sebagian untuk kredensial. Token baru disimpan terenkripsi.
- URL WhatsApp tanpa skema diberi `https://` sebelum validasi. Uji koneksi memakai payload Meta bila URL mengandung `graph.facebook.com`; URL lain memakai payload gateway generik. Uji ini benar-benar mengirim pesan bila endpoint dipanggil pada lingkungan aktif.
- Update Telegram dengan token baru mencoba `getMe` untuk menemukan username bot. Registrasi webhook memerlukan HTTPS; penghapusan webhook menggunakan `action=delete` dan tidak mensyaratkan URL HTTPS.
- Nilai suhu RAG dikembalikan sebagai angka pecahan; `rag_top_k`/`rag_num_ctx` sebagai integer; citation/status kanal sebagai boolean. Parameter model dan jendela konteks yang tidak disertakan pada update chatbot tetap memakai nilai tersimpan.
- Reset chatbot mempertahankan pengaturan kanal. Teks fallback hasil reset berbeda dari fallback saat pengaturan belum pernah disimpan; keduanya dipertahankan sesuai perilaku lama.
- Katalog model memakai daftar fallback ketika Ollama tidak tersedia atau tidak mengembalikan model. Badge, estimasi VRAM, dan kecepatan katalog adalah label statis berdasarkan nama/ukuran model. Kecepatan terukur diperoleh lewat endpoint benchmark; `eval_duration_ms` dan waktu token pertama memakai durasi dari Ollama, sedangkan `total_duration_ms` mengukur waktu permintaan Laravel.

## API Internal Python AI

Layanan FastAPI berjalan pada port `8080`. Spesifikasi mesin terkini tersedia dari aplikasi yang sedang berjalan:

- Swagger UI: `http://localhost:8080/docs`
- OpenAPI JSON: `http://localhost:8080/openapi.json`

Endpoint chat dan pemrosesan dokumen internal menggunakan token `Authorization: Bearer <INTERNAL_API_TOKEN>`. Health check tersedia melalui `GET /health` dan `GET /api/health`; kondisi hardware tersedia melalui `GET /api/health/hardware`. Endpoint internal ini ditujukan untuk komunikasi antarlayanan dan administrasi, bukan pengganti Public API Laravel.

### Kontrak health dan diagnostik hardware

| Endpoint | Auth | Respons dan cache |
| --- | --- | --- |
| `GET /health`, `GET /api/health` | Publik | Alias dengan cache bersama per proses selama 5 detik. HTTP 200 bila seluruh probe berhasil; HTTP 503 bila salah satu gagal. |
| `GET /api/health/hardware` | Bearer internal | HTTP 401 tanpa token yang valid, termasuk ketika cache tersedia. Cache efektif 3 detik; `nocache=true` memaksa refresh. |

Payload health tetap berisi `status` (`healthy`/`degraded`), `service`, `model`, serta `checks` dengan kunci `chromadb`, `mysql`, `redis`, dan `ollama`. Setiap probe menghasilkan `ok` dan `detail`; exception dilaporkan sebagai nama kelas tanpa pesan mentah dalam respons. Koleksi vektor kosong tetap menghasilkan `ok=true` bila dapat dibaca. Pemeriksaan Ollama memakai `LLM_MODEL_NAME` dari environment, bukan model override database. Cache juga menyimpan hasil `degraded` sampai TTL berakhir.

Payload hardware tetap berisi `konfigurasi`, `sistem`, `gpu`, `ram`, `ollama`, `rekomendasi`, dan `model_fit`. Query opsional `model` dipakai untuk estimasi kecocokan. Pada cache aktif, hanya `model_fit` yang dihitung ulang untuk model tersebut; `konfigurasi` dan `rekomendasi` tetap berasal dari snapshot cache. Gunakan `nocache=true` bersama `model` untuk menghitung seluruh snapshot baru. Angka rekomendasi adalah estimasi; algoritme dan satuan MiB tetap dipertahankan.

Implementasi HTTP/cache berada di `app/routers/health.py`, sedangkan probe/perhitungan berada di `app/services/diagnostics/`. Pemisahan ini mempertahankan nama operasi serta keseluruhan skema OpenAPI.

### Kontrak OCR dan routing yang dipertahankan

`GET /api/docs/extraction-prompts` tetap mengembalikan bagian `dasar`, `tabel_sop`, dan `kepala_sop`, masing-masing dengan `judul`, `kapan`, serta `teks`. Sumber nilainya berada di `ocr/prompts.py` dan tetap tersedia melalui ekspor `pdf_processor`; frontend tidak memelihara salinan prompt tersendiri.

Render editor tetap memakai `GET /api/docs/{document_id}/pages/{page_number}/image` dan ukuran nominal melalui `/pages/dimensions`. Zoom editor bawaan 2.0 dengan pilihan 1.5/2/3/4 dan batas sisi 2560 piksel. Render OCR PDF tetap terpisah pada zoom 1.5 dengan batas 2048 piksel. Pemisahan modul tidak mengganti byte prompt, aturan render, nomor halaman berbasis 1, atau bentuk metadata gambar.

Routing intent merupakan antarmuka internal Python melalui `tool_router.route_intent`, dengan hasil `{intent, params, label}`. Implementasinya berada di `routing/dispatch.py`; label trace, data handoff, urutan guard, dan fallback ke RAG tetap mengikuti algoritme yang sama. Tidak ada endpoint atau field HTTP baru akibat refactor ini.

### Kontrak progres pipeline dokumen Python

Koreksi `PUT /api/documents/{id}/pages/{n}` mempertahankan spasi, indentasi, tab,
dan newline di tepi teks ketika diteruskan ke Python dan disimpan. Teks kosong
atau hanya whitespace ditolak oleh validasi; trimming route lain tetap aktif.

Pemisahan modul embedding/ekstraksi serta workflow router/worker tidak mengganti endpoint, payload task, nama status, ataupun teks progres yang dikonsumsi Laravel.

Pembatalan `POST /api/docs/{id}/cancel` menandai `cancellation_requested` hanya
pada dokumen tersebut, memperbarui status `failed`/job `gagal`, dan melakukan
cleanup vektor dengan filter ID dokumen serta token operasi lama. Tidak ada
purge antrean atau unload model bersama. Respons `cancelled` mengakui permintaan
kooperatif; panggilan OCR/embedding yang sedang berjalan dapat selesai menghitung,
tetapi hasil token lama tidak boleh ditulis. Dokumen yang sudah tidak ada
menghasilkan 404. Task lama tanpa `_operation_token` tidak diproses; pemanggil
harus memulai/resume dokumen setelah migrasi protokol.

Laravel menyimpan flag pembatalan sebelum memanggil Python, termasuk pada
cancel, replace, dan delete. Fence tetap berlaku bila HTTP Python gagal.
Pekerjaan yang telah selesai mempertahankan korpusnya; cleanup generasi yang
belum selesai tidak menghapus token lain. Permintaan cleanup disimpan pada
outbox SQL dalam transaksi fence, sehingga kegagalan Chroma/Python tidak
menghilangkan request, termasuk setelah dokumen dihapus. FastAPI mencoba ulang
saat startup dan setiap 30 detik dengan backoff hingga 300 detik.

Replace/delete memakai cleanup penuh yang juga mencakup vektor lama tanpa token.
Endpoint mulai/resume/embedding Python dapat mengembalikan **503** dengan
`detail` bila cleanup penuh masih tertunda; tidak ada task generasi baru yang
diantrekan pada jalur tersebut. Cancel parsial boleh dilanjutkan dengan token
baru sambil cleanup token lama menunggu. DELETE Python tetap mengembalikan 500
jika cleanup vektor gagal, tetapi request persisten dicoba ulang di background.
Respons cancel tetap acknowledgement kooperatif. Tidak ada endpoint atau field
payload publik baru; perubahan korpus lintas MySQL/Chroma belum bersifat atomik.

Workflow tetap memakai ekspor kompatibilitas `embedding_service` dan `ekstraksi_bertahap`.

- Ekstraksi bertahap menyimpan setiap halaman beserta petunjuk format sebelum memeriksa jeda sesudah halaman. Halaman tersimpan dilewati saat melanjutkan. Task berhenti pada `menunggu_koreksi` setelah seluruh halaman terkumpul; pemotongan/embedding menggunakan task terpisah.
- Status job tetap berasal dari `ekstraksi_job`. `halaman_total` dan `halaman_selesai` tetap menyatakan jumlah halaman, sedangkan `persen` dibatasi 0–100.
- Progres embedding disimpan pada Redis dengan kunci `doc_embed_progress:{document_id}` dan TTL 3600 detik. Ketika tersedia, pembacaan status memakai `status`, `persen`, dan `pesan` dari nilai itu tanpa mengganti penghitung halaman OCR. Bila Redis tidak tersedia, pembacaan kembali memakai data job MySQL.
- Callback embedding mempertahankan tahap 35/45/pembaruan batch anak/95/100 beserta label lamanya. Tidak ada perubahan format metadata chunk, ID vektor, atau bentuk sumber sitasi akibat pemisahan modul.

### Batas klien dokumen Laravel → Python

Laravel tetap memanggil `AiMicroserviceClient`; operasi HTTP diimplementasikan oleh trait `Ai/DocumentRequests` dan `Ai/StagedExtractionRequests` pada instance yang sama. Konfigurasi URL/token dibaca ketika klien dibuat, dan token dikirim sebagai bearer pada setiap operasi. Ini mempertahankan metode klien serta route admin/Python yang ada.

- Mulai ekstraksi mengirim `maks_halaman` hanya bila bukan `null`, termasuk nilai 0 yang diberikan eksplisit. Opsi kategori yang tidak kosong dibatasi pada `category_prompt`, `job_titles`, `vision_model`, serta `custom_prompts`. Mulai ekstraksi dan embedding tanpa opsi mengirim JSON `{}`.
- Pratinjau tanpa opsi memakai GET ke `/api/docs/{id}/chunks/preview`; dengan opsi memakai POST ke path yang sama. Koreksi mengirim `text` apa adanya melalui PUT. Filter daftar halaman dikirim sebagai `perlu_diperiksa=0/1`, dan gambar menyertakan parameter `zoom`.
- Klien mempertahankan timeout per operasi tanpa retry tambahan: health 5 detik, pembatalan/jumlah vektor 10 detik, jeda/status/ukuran/hapus 15 detik, serta ekstraksi/editor/pratinjau/embedding/pembacaan chunk 30 detik. Timeout koneksi khusus tetap 3 detik untuk health, 5 detik untuk pembatalan/jeda, dan 10 detik untuk mulai ekstraksi/embedding; operasi lain memakai bawaan HTTP client.
- Respons JSON terbungkus memakai `success`/`data`. Pada kegagalan HTTP, format error mempertahankan `detail` string atau daftar validasi `loc`/`msg`; pembatalan tetap tidak menyertakan field `status`. Gambar dikembalikan sebagai respons biner asli atau `null`; health memakai boolean dan operasi baca vektor memakai array tanpa pembungkus.

Pembungkus ini adalah kontrak internal klien Laravel; controller/workflow tetap menentukan respons HTTP admin. Tes `AiMicroserviceClientContractTest` memeriksa request keluar dan fallback dengan HTTP fake.

`GET /api/documents/{id}/chunks` tetap meneruskan payload JSON sukses Python tanpa pembungkus. Jika Python membalas non-2xx atau koneksi melempar exception, klien mengembalikan `[]` dan endpoint admin membalas HTTP 200 dengan array kosong. Jalur HTTP gagal ini sebelumnya dapat menghasilkan HTTP 500 akibat return yang hilang; fallback eksplisit memperbaikinya tanpa mengubah status/jumlah chunk tersimpan pada dokumen. Dokumen lokal yang tidak ditemukan tetap menghasilkan HTTP 404 sebelum pemanggilan AI.

## Webhook masuk kanal pesan

Laravel juga menyediakan endpoint webhook kanal berikut:

| Metode | Path | Fungsi |
|---|---|---|
| `GET` | `/api/v1/webhook/whatsapp` | Verifikasi webhook WhatsApp. |
| `POST` | `/api/v1/webhook/whatsapp` | Menerima update WhatsApp. |
| `POST` | `/api/v1/webhook/telegram` | Menerima update Telegram. |

Endpoint ini adalah webhook masuk dari penyedia kanal. Endpoint tersebut berbeda dari webhook `ticket.reply.created` yang dikirim SAPA ke aplikasi penerima.

### Perilaku gateway kanal yang dipertahankan

Penerimaan webhook dibagi ke handler kanal; pengiriman AI JSON/SSE dipusatkan di `Channels/AiChatGateway`. Path, metode, nama route, middleware, payload, serta respons tetap sama.

- WhatsApp menerima teks Meta atau fallback field gateway generik. Nomor dinormalisasi menjadi digit untuk `session_id` (`wa-...`), sementara nilai nomor asli tetap diteruskan sebagai kontak/tujuan. Berkas upload dengan nama field teks tidak menggantikan input pesan.
- Tiket aktif `open`/`in_progress` menerima pesan warga dan event yang sama tanpa panggilan AI. Public chat tetap mengaitkan tiket handoff dengan API key yang memanggilnya.
- Webhook Telegram memakai kunci update dan pasangan chat/message dengan TTL 180 detik, sebelum pemeriksaan payload/kredensial berikutnya. Pesan edit tanpa field `message.text`/`message.caption` tetap diabaikan oleh webhook; polling menerima `edited_message`.
- Error konfigurasi token Telegram pada webhook tetap menghasilkan HTTP 200 dengan `status=error` dan `reason`; ini berbeda dari respons endpoint pengaturan. Penolakan AI pada WhatsApp menghasilkan HTTP 500. Pengiriman WhatsApp yang ditolak gateway setelah respons AI diterima tetap mempertahankan respons webhook sukses.
- Stream Telegram menyusun ulang baris `data:` yang terpotong antar callback, mengabaikan JSON tidak valid serta event selain `chunk`, dan tidak memproses sisa baris yang belum diakhiri newline. Webhook memperbarui draft setelah 1,2 detik dan 20 byte baru; polling setelah 1,5 detik dan 25 byte baru.
- Public chat SSE meneruskan byte AI tanpa parsing ulang. Fallback lokal berjalan bila tidak ada byte atau cURL melaporkan error, sesuai kondisi lama; fallback dapat ditambahkan setelah byte parsial bila transport berakhir dengan error.

Perilaku tersebut dicakup tes kontrak menggunakan HTTP palsu dan transport SSE tiruan. Verifikasi terhadap kanal, broker, dan layanan AI nyata tetap diperlukan untuk konektivitas serta batas layanan penyedia.
