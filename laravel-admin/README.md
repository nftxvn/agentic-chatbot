# Laravel Admin API

Laravel menyediakan autentikasi admin berbasis Sanctum, REST API admin, gateway publik `/api/v1`, integrasi kanal, pengelolaan dokumen, dan helpdesk tiket. Manifest adalah sumber versi: PHP `^8.3`, Laravel `^13.8`, dan Sanctum `^4.3` (`composer.json`).

## Tanggung jawab kode

- `routes/api.php`: daftar endpoint dan middleware.
- `app/Http/Controllers/Api/`: orkestrasi request dan response HTTP.
- `app/Http/Requests/`: validasi payload; direktori menggunakan `DirectoryStoreRequest` dan `DirectoryUpdateRequest`.
- `app/Models/` dan `database/migrations/`: data transaksional MySQL.
- `app/Services/`: integrasi dengan Python AI, degradasi layanan, ekstraksi entitas, dan lampiran.
- `app/Services/Ai/`: operasi HTTP dokumen dan ekstraksi Python, disusun sebagai trait pada `AiMicroserviceClient`. Pemanggil tetap memakai kelas serta metode publik yang sama.
- `app/Services/Documents/`: `DocumentWorkflowService` mengelola berkas dan pemrosesan ulang; `DocumentExtractionService` menangani ekstraksi, jeda, koreksi, dan embedding; `DocumentPresenter` mempertahankan format data serta label dashboard; `DocumentCategoryOptions` menyatukan pemetaan opsi kategori ke Python.
- `app/Services/Tickets/`: `TicketIngestionService` mengelola penerimaan/penggunaan ulang tiket; `TicketQueryService` membaca antrean/detail/percakapan; `TicketLifecycleService` menangani penugasan, status, dan penghapusan; `TicketReplyService` menyimpan balasan/lampiran serta memperbarui tiket sebelum delivery/event; `TicketReplyDeliveryService` mengirim balasan publik melalui kanal dan antrean webhook.
- `app/Services/Entities/`: parsing, normalisasi/leksikon, riwayat Redis, dan enrichment tiket dibagi ke trait pada API statis `EntityExtractorService` yang sama.
- `app/Http/Controllers/Api/Settings/`: endpoint WhatsApp, Telegram, chatbot, dan diagnostik AI dipisahkan per fitur; path dan middleware tetap ditentukan di `routes/api.php`.
- `app/Services/Settings/`: `ChannelSettingsService` menangani penyimpanan kredensial kanal; `ChatbotSettingsService` menyimpan prompt/parameter RAG; `OllamaModelCatalog` membentuk katalog model beserta fallback.
- `app/Services/WhatsAppClient.php`: membaca konfigurasi dan mengirim balasan webhook/tiket. `WhatsAppGateway` menyatukan payload HTTP Meta Cloud API dan gateway generik, termasuk untuk uji koneksi dari pengaturan.
- `app/Services/Channels/`: penerimaan pesan kanal, pemrosesan satu update polling, profil balasan Telegram, dan transport AI. Controller tetap membentuk respons HTTP; command tetap mengatur loop long polling.
- `app/Events/` dan `app/Jobs/`: broadcasting tiket dan pengiriman webhook di latar belakang.

Pertahankan path, metode, autentikasi, response JSON, dan event broadcast karena frontend serta Python AI bergantung pada kontrak tersebut. Spesifikasi bersama ada di [`../docs/03-api_spec_agentic_copilot.md`](../docs/03-api_spec_agentic_copilot.md).

## Menjalankan lokal

```bash
cp .env.example .env
composer install
php artisan key:generate
php artisan serve --host=0.0.0.0 --port=8000
```

Konfigurasikan MySQL, session/cookie Sanctum, URL AI, dan token internal melalui `.env`. Jangan commit `.env` atau menyalin token ke dokumentasi. Untuk menjalankan worker antrean, gunakan terminal terpisah dengan `php artisan queue:work` sesuai driver queue yang dipakai.

## Helpdesk dan ekstraksi entitas

`TicketController` menangani validasi, resolusi resource, serta respons HTTP. Query antrean berada di `TicketQueryService`: eager loading, pengelompokan OR pencarian, urutan `last_message_at DESC, id DESC`, statistik, dan urutan pesan tetap mengikuti query sebelumnya. Controller mempertahankan normalisasi parameter `per_page` ke rentang 5–100 serta pemeriksaan `filled` pada filter.

`TicketLifecycleService` memiliki mutasi penugasan, transisi status, dan penghapusan. `TicketReplyService` memiliki penyimpanan pesan/lampiran, pembaruan metadata tiket, delivery, lalu event. Perilaku yang dipertahankan:

- Penugasan mengubah status `open` menjadi `in_progress`; status lain tetap dipertahankan. `admin_id=null` memakai identitas pengguna yang sedang terautentikasi.
- Penyelesaian/penutupan menyimpan tiket, membersihkan sesi AI, membuat pesan sistem, menyiarkan `TicketMessageSent`, lalu `TicketUpdated`. Membuka kembali tiket membersihkan kedua timestamp penutupan. Permintaan status selesai/ditutup yang diulang tetap mengikuti kebijakan pesan sistem sebelumnya.
- Balasan disimpan sebelum metadata tiket dan relasi dimuat; delivery berlangsung sebelum kedua event. Balasan publik pada tiket tertutup mempertahankan status tertutup sesuai perilaku lama. Catatan internal mempertahankan kebijakan penugasan/status yang ada.
- Penghapusan mempertahankan urutan berkas → memori Redis → record tiket. Hook protected `TicketController::forgetAiSessionMemory` tetap digunakan melalui callback untuk transisi/penghapusan dan menangani kegagalan Redis sebagai best effort. Pemisahan service tidak menambah transaksi atau lock.
- Urutan validasi dan pencarian resource, teks pesan, pembungkus JSON, serta kode HTTP tetap sama. Unduhan lampiran tetap ditangani controller dengan `basename` dan pemeriksaan disk privat.

`EntityExtractorService` tetap menyediakan `extractFromText`, `extractFromSessionHistory`, `enrichTicket`, `cleanName`, dan `cleanAgency`. Implementasinya berada pada trait berikut, yang dimuat di kelas yang sama agar binding `self::` serta properti/helper protected tetap berlaku:

| Trait pada `Services/Entities/` | Tanggung jawab |
| --- | --- |
| `NormalizesCitizenEntities` | Stopword nama, alias instansi, normalisasi, dan deteksi sapaan/handoff murni |
| `ParsesCitizenEntities` | Parsing pesan terstruktur dan percakapan alami; prioritas pola serta fallback profil |
| `ReadsSessionEntities` | Pembacaan Redis dan pengambilan nilai entitas pertama yang tidak kosong dari riwayat pengguna |
| `EnrichesTicketEntities` | Penerapan nama/instansi/ringkasan baru dan relabel pesan warga dengan nama generik |

Riwayat tetap memakai koneksi Redis default, `select(2)`, dan kunci `chatbot:session:{sessionId}`. Pembacaan berjalan dari pesan awal ke akhir dan mengabaikan role selain `user`. Profil pengirim yang telah menjadi nilai nama awal tetap dapat mendahului nama pada pesan berikutnya; kebijakan fallback jalur sesi kosong/riwayat/teks tetap dipertahankan tersendiri. Kegagalan pembacaan Redis menangkap `Throwable` dan memakai fallback yang sama.

Enrichment memperbarui nama, instansi, dan ringkasan berdasarkan guard lama; kontak yang diekstrak tetap dipakai oleh workflow penerimaan tiket, sedangkan `enrichTicket` mempertahankan perilaku tanpa memperbarui kontak. Relabel nama hanya mengenai pesan warga yang memakai nama generik; nama petugas serta nama warga yang sudah spesifik tetap dipertahankan.

## Klien dokumen Python AI

`AiMicroserviceClient` tetap memiliki konstruktor tanpa argumen, snapshot URL/token dari konfigurasi, serta formatter error `extractErrorMessage`. `Ai/DocumentRequests` berisi health, pembatalan, pembacaan chunk/jumlah vektor, dan penghapusan. `Ai/StagedExtractionRequests` berisi mulai/jeda/status ekstraksi, koreksi dan gambar halaman, ukuran halaman, pratinjau, serta embedding.

Trait berjalan pada instance klien yang sama sehingga properti terlindungi dan override formatter pada subclass tetap berlaku. Trait ini bukan service container terpisah. Workflow berkas/database tetap berada di `Services/Documents/`; transport chat JSON/SSE berada di `Channels/AiChatGateway`.

Endpoint koreksi `PUT /api/documents/{id}/pages/{n}` mempertahankan indentasi,
spasi, tab dan newline teks editor. Middleware `TrimStrings` dilewati khusus
untuk method/path tersebut; validasi tetap menolak teks kosong tanpa mengubah
teks valid. Route lain tetap mengikuti trimming biasa. Tes regresinya ada pada
`DocumentCorrectionWhitespaceTest`.

Pengujian HTTP dengan FastAPI/Celery/MySQL/Redis serta model lokal nyata tersedia
melalui [runner integrasi](../scripts/integration/README.md). Helper
`scripts/integration/prepare.php` hanya menerima konfigurasi dan marker run
sementara sebelum menjalankan migrasi serta fixture sintetis.

Pembatalan, penggantian dan penghapusan dokumen menyimpan
`cancellation_requested` pada transaksi yang mengunci baris dokumen sebelum
memanggil Python. Flag tetap berlaku ketika transport Python gagal; token
generasi tidak dirotasi oleh Laravel, agar Python dapat membersihkan generasi
yang tepat. Python mengeluarkan token baru ketika mulai/resume atau embedding.
Middleware/UI tidak berubah untuk fitur pembatalan ini. Respons cancel merupakan
acknowledgement kooperatif, bukan pemutusan seketika panggilan model.

Migrasi `2026_10_25_000001_add_document_operation_fences.php` menambah
`processing_token` nullable dan `cancellation_requested` default false pada
`documents`. Terapkan migrasi sebelum menjalankan versi API/worker yang baru;
worker lama perlu diselesaikan/dihentikan dalam rollout yang terkoordinasi.
Tes `DocumentCancellationFenceTest` memeriksa isolasi dokumen, HTTP Python yang
gagal, replace/delete, dan state Eloquent yang telah berubah karena resume.
Migrasi operasional tidak dijalankan oleh runner integrasi.

Migrasi `2026_10_25_000002_create_document_vector_cleanups_table.php` menambahkan
outbox cleanup vektor. `DocumentWorkflowService` mencatat request cleanup pada
transaksi fence yang sama sebelum memanggil Python: cancel hanya untuk token
yang belum selesai, sedangkan replace/delete memakai token kosong untuk seluruh
dokumen. Request tetap ada setelah baris dokumen dihapus dan tidak diduplikasi
oleh cancel berulang. `available_at`/timestamp outbox ditulis dalam **UTC** agar
Python tidak menunda retry karena zona waktu aplikasi Laravel.

API Python menguras outbox saat startup dan setiap 30 detik, dengan backoff
hingga 300 detik; tidak perlu antrean atau jadwal Laravel tambahan. Cleanup
penuh yang tertunda menghalangi generasi baru. Jika dispatch replacement gagal
karena Chroma belum pulih, dokumen tetap `pending` dan dapat dilanjutkan setelah
cleanup selesai. UI dan bentuk respons admin tetap memakai alur yang ada.
Terapkan kedua migrasi sebelum API/worker baru. Perintah retry manual dan batas
pemulihan dijelaskan di [README Python](../python-ai/README.md).

Untuk diagnosis, baca `document_vector_cleanups` (`document_id`,
`operation_token`, `attempts`, `last_error`, `available_at`); seluruh jadwal
outbox memakai UTC. `DocumentCancellationFenceTest` juga memeriksa request yang
bertahan setelah delete, idempotensi, UTC, korpus selesai dan rollback ketika
penyimpanan outbox gagal. Uji outage nyata tersedia pada
[`run_cleanup_recovery.py`](../scripts/integration/run_cleanup_recovery.py).

| Operasi | Timeout respons | Timeout koneksi |
| --- | --- | --- |
| Health | 5 detik | 3 detik |
| Pembatalan dokumen | 10 detik | 5 detik |
| Mulai ekstraksi dan simpan ke korpus | 30 detik | 10 detik |
| Jeda ekstraksi | 15 detik | 5 detik |
| Status, ukuran halaman, hapus vektor | 15 detik | Bawaan HTTP client |
| Daftar/koreksi/gambar halaman, pratinjau, pembacaan chunk | 30 detik | Bawaan HTTP client |
| Jumlah vektor | 10 detik | Bawaan HTTP client |

Bawaan timeout koneksi Laravel saat ini 10 detik. Pemisahan modul tidak menambah retry atau menyamakan timeout antaroperasi.

Kontrak yang perlu dijaga:

- Mulai ekstraksi dan embedding mengirim objek JSON `{}` bila payload kosong. Pratinjau tanpa opsi memakai GET; dengan opsi memakai POST. `maks_halaman=0` tetap dikirim bila diberikan; validasi domain tetap milik endpoint Python.
- Opsi kategori yang diteruskan hanya `category_prompt`, `job_titles`, `vision_model`, dan `custom_prompts` yang tidak kosong. Seluruh opsi kosong pada kategori yang diberikan tetap menghasilkan warning.
- Hasil JSON terbungkus memakai `success`/`data`; kegagalan HTTP umumnya menyertakan `message`/`status`. Pembatalan mempertahankan hasil error tanpa `status`. Kegagalan koneksi memakai kebijakan pesan/log masing-masing operasi.
- Detail error FastAPI dapat berupa string, daftar validasi `loc`/`msg`, atau array lain. Formatter mempertahankan isi string, Unicode, serta pesan fallback dengan status HTTP.
- Gambar halaman mengembalikan objek respons HTTP beserta byte dan header aslinya, atau `null` bila gagal. Health mengembalikan boolean; pembacaan chunk dan jumlah vektor memakai array tanpa pembungkus `success`.

`getDocumentChunks` mengembalikan `[]` saat koneksi melempar exception maupun saat Python membalas HTTP non-2xx. Return eksplisit pada jalur non-2xx memperbaiki `TypeError` akibat fungsi bertipe array yang sebelumnya selesai tanpa return. Endpoint admin pembacaan chunk tetap memakai respons tanpa pembungkus; pada kegagalan upstream kini mengembalikan HTTP 200 dengan `[]`, tanpa mengubah status atau jumlah chunk tersimpan pada dokumen. Respons upstream 2xx yang valid tetap diteruskan apa adanya.

## Batas gateway kanal

| Modul | Tanggung jawab |
| --- | --- |
| `Channels/AiChatGateway` | Request JSON ke AI (timeout 60 detik) dan transport byte SSE (120 detik). Pemanggil menentukan parsing dan kebijakan fallback. |
| `Channels/WhatsAppInboundHandler` | Format Meta/gateway generik, human takeover, payload AI, sitasi balasan, dan telemetri. Pengiriman keluar tetap melewati entrypoint `sendWhatsAppMessage` dan `WhatsAppClient`. |
| `Channels/TelegramInboundHandler` | Toggle, deduplikasi webhook, normalisasi command, kredensial, dan human takeover. Handler menerima input request tanpa file, sesuai pembacaan input lama. |
| `Channels/TelegramPollingMessageHandler` | Satu update polling: teks/edit/foto, lampiran, tiket aktif, pembuatan/pembukaan ulang tiket foto, dan penerusan ke AI. |
| `Channels/TelegramAiResponder` | Placeholder, pembacaan SSE terfragmentasi, pembaruan draft, balasan final, dan telemetri; profil webhook/polling tetap terpisah. |
| `Channels/ChannelResponse` | Payload/status hasil workflow sebelum controller mengubahnya menjadi JSON. |

`telegram:poll` mempertahankan opsi `--once`, offset update, long-poll 20 detik,
penanganan konflik 409, serta jeda retry yang ada. Callback console dan
entrypoint streaming lama dipertahankan agar pemanggil command/controller
tetap memakai antarmuka yang sama.

Perbedaan perilaku yang perlu dijaga:

- Webhook Telegram memakai deduplikasi update dan pesan selama 180 detik. Kunci dapat sudah terpasang sebelum payload/kredensial dinyatakan tidak lengkap. Polling tidak memakai deduplikasi webhook tersebut.
- Polling memproses `message` maupun `edited_message`. Webhook mengambil chat/message ID dari keduanya, tetapi teks masih berasal dari `message`; payload edit saja tetap diabaikan.
- Draft webhook Telegram memakai ambang 1,2 detik/20 byte teks baru; polling memakai 1,5 detik/25 byte. Keduanya tetap memakai `strlen`, bukan jumlah karakter Unicode.
- Setelah edit Markdown ditolak, keduanya mencoba edit plain text. Polling dapat mengirim pesan baru bila edit tetap gagal; profil webhook mempertahankan perilaku tanpa kirim pesan baru pada kondisi itu.
- Respons WhatsApp tetap sukses setelah AI berhasil meskipun gateway keluar menolak pengiriman. Kegagalan AI sendiri menghasilkan error HTTP 500. Public chat JSON memakai graceful degradation lokal; stream publik tetap meneruskan byte mentah dan memakai kebijakan fallback lamanya.
- `ChatLog` kanal menyimpan metadata telemetri; kolom query/answer tetap kosong sesuai perilaku lama. Hal ini tidak mengganti kebijakan logging aplikasi pada lokasi lain.

## Verifikasi

```bash
php artisan test
```

Test fitur menggunakan SQLite in-memory dan migrasi yang kompatibel dengan SQLite. Uji integrasi yang mengandalkan MySQL, Redis, Python AI, atau Reverb perlu dijalankan dengan dependensi tersebut hidup.

`DocumentPipelineContractTest` memakai HTTP dan penyimpanan berkas palsu untuk memeriksa kontrak dokumen tanpa menghubungi Python. Cakupannya meliputi label/progres dashboard, upload dan penggantian berkas, kegagalan AI, opsi kategori lama dan baru, koreksi halaman, serta antrean embedding.

`AiMicroserviceClientContractTest` memeriksa request keluar melalui HTTP fake: bearer token, normalisasi URL/snapshot konfigurasi, timeout operasi, objek JSON kosong, opsi kategori, pratinjau GET/POST, teks koreksi, byte gambar, format error, kegagalan koneksi tanpa retry, dan override formatter pada subclass. Tes ini tidak menghubungi Python AI atau menjalankan worker/model nyata.

Fallback chunk diuji untuk respons Python HTTP 404/429/503. Tes endpoint pada `DocumentPipelineContractTest` memastikan kegagalan upstream menghasilkan array kosong tanpa mengubah status/jumlah chunk dokumen, serta memastikan payload sukses tetap diteruskan tanpa pembungkus.

`EntityExtractorContractTest` memeriksa pola/normalisasi, prioritas riwayat, DB/kunci Redis, JSON gagal, kegagalan ekstensi Redis, fallback profil, binding helper `self::`, serta side effect enrichment pada tiket/pesan. `TicketWorkflowContractTest` menjaga timestamp/pesan sistem, assignment tiket tertutup, pencarian/paginasi, penyimpanan/delivery sebelum event, override cleanup, dan penghapusan berkas/pesan ketika Redis gagal. Tes memakai SQLite in-memory, mock Redis/delivery, event fake, dan disk pengujian; tidak mengakses Redis/kanal pesan nyata.

`SettingsContractTest` memeriksa tipe nilai pengaturan, prompt bawaan, enkripsi/masking token, payload uji kanal, webhook Telegram, katalog model, diagnostik, dan benchmark menggunakan HTTP palsu. Tes tidak mengirim pesan ke penerima nyata. `SettingController::getDefaultRagPrompt()` dipertahankan sebagai alias kompatibilitas; pemanggil baru memakai `ChatbotSettingsService`.

`ChannelWebhookContractTest` dan `TelegramPollingContractTest` menjaga respons,
deduplikasi, takeover, input edit/foto, serta perilaku `--once`.
`TelegramStreamContractTest` memeriksa SSE terfragmentasi, Markdown/plain text,
ambang draft, dan profil pengiriman final. `PublicChatGatewayContractTest`
menjaga payload JSON, header/byte SSE, fallback, dan telemetri public chat.
HTTP kanal digantikan fake dan transport SSE AI digantikan mock; tes ini tidak
menjalankan cURL ke AI, mengirim Telegram/WhatsApp nyata, atau membuka runner
polling terus-menerus.

Panduan batas modul dan pemeliharaan lintas layanan ada di [`../docs/08-panduan-struktur-kode-dan-pemeliharaan.md`](../docs/08-panduan-struktur-kode-dan-pemeliharaan.md).
