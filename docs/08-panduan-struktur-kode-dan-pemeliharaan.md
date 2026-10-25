# Panduan Struktur Kode dan Pemeliharaan

Panduan ini mencatat pembagian tanggung jawab aplikasi dan batas integrasi yang perlu dijaga ketika kode dirapikan. Untuk versi runtime dan dependensi, manifest tiap aplikasi adalah sumber kebenaran; beberapa dokumen lama di `docs/` masih memuat versi atau rancangan yang belum tentu sama dengan implementasi saat ini.

## Komponen dan tanggung jawab

| Komponen | Tanggung jawab | Batas utama |
| --- | --- | --- |
| `admin-frontend` | SPA admin untuk dokumen, RAG playground, pengaturan, log, dan live chat | Panggilan admin menggunakan API Laravel melalui `src/api/`; jangan letakkan akses HTTP langsung di komponen halaman |
| `laravel-admin` | Auth Sanctum, data transaksional, API admin/public, integrasi webhook, tiket, serta gateway ke AI | Route menentukan middleware dan controller; validasi input berada di Form Request; integrasi AI berada di `app/Services/` |
| `python-ai` | FastAPI, chat/RAG, ekstraksi dokumen, embedding, dan task Celery | Router menangani HTTP; layanan domain/adaptor berada di `app/services/`; autentikasi HTTP bersama berada di `app/security.py` |
| `docker/`, `docker-compose.yml`, launcher | Menjalankan dan menghubungkan layanan serta dependensi | Port, nama environment variable, volume, dan health check harus selaras dengan manifest aplikasi dan panduan ini |

## Alur integrasi

1. Browser mengirim permintaan admin ke Laravel dengan cookie sesi Sanctum. Frontend menyentralisasi konfigurasi Axios di `admin-frontend/src/api/client.js`, lalu modul per fitur membungkus endpoint.
2. Laravel menyimpan data transaksional pada MySQL, memakai `AiMicroserviceClient` untuk dokumen/ekstraksi, dan memakai `Channels/AiChatGateway` untuk chat JSON/SSE ke Python AI.
3. Python AI menyajikan HTTP/JSON dan SSE untuk chat, memakai Celery/Redis untuk pekerjaan ekstraksi di latar belakang, serta memakai `app/services/backend_client.py` untuk handoff tiket ke Laravel. ChromaDB menyimpan indeks vektor.
4. Endpoint publik `/api/v1` berada di Laravel dan memakai API key. Endpoint internal Python memakai bearer token; jangan mengirim rahasia itu ke browser atau mencatat nilainya di log.
5. Live chat/helpdesk mengalir dari handoff Python ke endpoint internal Laravel, kemudian Laravel menyimpan tiket/pesan dan menyiarkan event melalui Reverb. Dashboard saat ini mengambil antrean/pesan melalui polling 5 detik; event browser `app-tickets-updated` menyelaraskan badge/notifikasi layout.

## Batas kontrak yang harus dijaga

- UI saat ini menjadi acuan: pertahankan layout, warna, tipografi, tema, animasi, navigasi, teks, serta interaksi. Pemisahan komponen atau hook harus menghasilkan tampilan dan perilaku yang sama, termasuk fokus input dan posisi scroll.
- Pertahankan path, metode HTTP, middleware autentikasi, kode status, bentuk payload JSON, dan header SSE yang dipakai klien.
- Perubahan internal pada controller, service, hook, atau modul Python tidak boleh mengubah kontrak tanpa perubahan terkoordinasi pada ketiga aplikasi dan spesifikasi API.
- Perubahan skema database memerlukan migrasi maju yang kompatibel dengan data yang sudah ada; jangan mengubah tabel secara manual.
- Event tiket dan nama channel Reverb harus tetap cocok dengan kontrak konsumennya. Frontend live chat saat ini memakai polling; jangan mengganti mekanisme sinkronisasi saat melakukan pemisahan kode struktural.
- Variabel environment yang dipakai runtime harus disebutkan di `.env.example` dan dijelaskan di panduan aplikasi terkait. Jangan menyalin nilai rahasia dari `.env` ke dokumentasi.

## Panduan kontribusi refactor

- Buat perubahan kecil per fitur, pertahankan satu sumber kebenaran untuk validasi, pemetaan respons, dan konfigurasi.
- Pisahkan validasi request Laravel ke Form Request; gunakan service untuk alur domain/integrasi yang dipakai lintas controller. Pertahankan urutan resolusi resource dan validasi: update direktori dengan ID yang tidak ada tetap menghasilkan 404 sebelum pemeriksaan payload.
- Workflow dokumen berada di `app/Services/Documents/`: penyimpanan/penggantian berkas dan pemrosesan ulang di `DocumentWorkflowService`, ekstraksi/koreksi/embedding di `DocumentExtractionService`, dan format respons dashboard di `DocumentPresenter`. `DocumentCategoryOptions` dipakai kedua workflow agar opsi kategori tetap sama pada upload, resume, dan mulai ekstraksi.
- Klien HTTP dokumen tetap diakses melalui `AiMicroserviceClient`. Operasi dipisah ke trait `Ai/DocumentRequests` dan `Ai/StagedExtractionRequests`; konstruktor, properti URL/token, dan formatter error tetap dimiliki kelas lama. Pertahankan signature metode, override formatter, timeout per operasi, payload kosong `{}`, pratinjau GET/POST, respons gambar biner, serta perbedaan pembungkus error pembatalan. Jangan menambahkan retry global atau memindahkan transaksi database ke trait HTTP ini. Pembacaan chunk memakai fallback `[]` untuk exception koneksi dan respons non-2xx; perbaikan return yang hilang dijelaskan di README Laravel.
- Penerimaan dan penggunaan ulang tiket ditangani `app/Services/Tickets/TicketIngestionService.php`; pengiriman balasan ke kanal dan antrean webhook ditangani `TicketReplyDeliveryService.php`. Controller tetap menangani validasi dan respons HTTP.
- Query antrean/detail/percakapan berada di `TicketQueryService`; penugasan, transisi status, serta penghapusan berada di `TicketLifecycleService`; penyimpanan pesan/lampiran dan urutan delivery/event berada di `TicketReplyService`. `TicketController` mempertahankan validasi/resource lookup, format HTTP, unduhan lampiran, dan hook protected cleanup Redis. Callback cleanup mempertahankan override controller dan urutan efek lama; pemisahan tidak menambah transaksi atau lock baru.
- `EntityExtractorService` tetap menyediakan API statis. Trait di `Services/Entities/` membagi leksikon/normalisasi (`NormalizesCitizenEntities`), parsing teks (`ParsesCitizenEntities`), pembacaan Redis (`ReadsSessionEntities`), dan enrichment (`EnrichesTicketEntities`). Binding `self::`, urutan alias/stopword, Redis DB 2/key sesi, first-value-wins, serta perbedaan fallback profil antarjalur tetap dipertahankan.
- HTTP pengaturan dipisah ke controller di `Api/Settings/`. `ChannelSettingsService` dan `ChatbotSettingsService` menyimpan pengaturan; `OllamaModelCatalog` membentuk data katalog. `SettingController` menyisakan alias statis prompt bawaan untuk kompatibilitas.
- `WhatsAppClient` membaca konfigurasi dan mengelola hasil pengiriman. `WhatsAppGateway` membentuk request Meta/gateway generik yang sama untuk webhook masuk, balasan petugas, dan uji koneksi pengaturan.
- Gateway kanal Laravel berada di `Services/Channels/`: `AiChatGateway` memiliki transport JSON/SSE, inbound handler memiliki parsing/takeover/hasil workflow, dan `TelegramPollingMessageHandler` memiliki pemrosesan satu update. Controller serta `telegram:poll` tetap memiliki entrypoint HTTP/CLI. `TelegramAiResponder` mempertahankan profil webhook/polling karena ambang draft dan kebijakan kirim ulangnya berbeda.
- Pisahkan dependency autentikasi Python dari endpoint agar endpoint tetap fokus pada validasi request dan orkestrasi respons.
- Koreksi halaman Laravel mengecualikan `TrimStrings` hanya pada `PUT api/documents/*/pages/*`, agar format teks editor tetap utuh sampai Python dan database. Validasi menolak teks kosong tanpa memodifikasi teks valid; jangan memperluas pengecualian ke route lain. `DocumentCorrectionWhitespaceTest` menjaga batas ini.
- Callback tiket Python membaca `LARAVEL_BASE_URL` bila dikonfigurasi dan hanya menghubungi instance itu. Nilai kosong mempertahankan daftar discovery lama; fallback ke instance lain setelah URL eksplisit gagal dapat melintasi batas environment.
- Parser sitasi JSON mengenali separator halaman retrieval dan format em dash lama. Resolusi judul ke ID dibatasi kecocokan tepat dan unik dalam `document_ids`; judul ambigu atau tanpa scope tetap memiliki ID opsional. Generator dan SSE tetap memiliki format yang sama.
- `python-ai/app/main.py` merakit aplikasi, lifecycle, middleware, dan router. `routers/health.py` memiliki HTTP/cache health serta hardware; `services/diagnostics/health.py` memiliki probe dan `hardware.py` memiliki pembacaan/perhitungan mesin. Pertahankan alias health publik, autentikasi hardware sebelum cache, TTL health 5 detik, dan kondisi TTL hardware 3 detik. Konstanta lama `_MESIN_CACHE_TTL=10` tetap tersedia tetapi tidak mengatur cache aktif.
- Router dokumen/ekstraksi mempertahankan dependency HTTP, schema, signature, dan metadata OpenAPI; workflow berada di `services/document_workflows/`. Query/lifecycle/citra/prompt dipisah dari kendali OCR/SSE, koreksi, dan preview/embed. Lookup/storage ekstraksi dimiliki `extraction_control` dan dipakai modul koreksi/chunk. Patch dependency pada modul workflow pemiliknya.
- Query MySQL berada di `app/repositories/`: `connection.py` memiliki satu engine lazy per proses; `documents.py` memiliki query status/metadata/sitasi; `settings.py` memiliki konversi/fallback pengaturan; `directories.py` memiliki cache FAQ/direktori; `document_logs.py` memiliki debounce log. `app/database.py` mempertahankan alias fungsi lama. Jangan menggandakan engine/cache di facade atau mengubah SQL, batas transaksi, urutan hasil, dan kebijakan propagasi error saat memindahkan kode.
- Cache direktori/FAQ menggunakan wall-clock dan TTL 5 detik; kegagalan refresh mengembalikan cache lama tanpa memperbarui timestamp. Cache health/hardware menggunakan monotonic clock. Konfigurasi RAG kembali ke seluruh nilai default bila satu konversi gagal; log dokumen mempertahankan debounce 15 detik. Patch dependency tes pada modul pemiliknya, misalnya `repositories.documents.get_engine`, bukan hanya pada ekspor facade.
- `python-ai/app/services/rag_service.py` mengorkestrasi routing, riwayat, penjaga, dan respons. Paket `rag/` membagi pencarian/sitasi (`retrieval.py`), pemeriksaan konteks dan jawaban terprogram (`grounding.py`), streaming model (`generation.py`), serta prompt/konteks instansi (`prompts.py`). Router dan worker tetap mengimpor titik masuk yang lama.
- Cache BM25 dan lock hanya berada di `rag/retrieval.py`; jangan membuat salinan state di facade. Invalidation tetap melewati `invalidate_bm25_cache`, dan penanda versi korpus tetap diperlukan untuk perubahan dari proses Celery.
- Embedding dan pemotongan Python berada di `services/embeddings/`: cache model/reranker pada `models.py`, algoritme judul/label/daftar pada `chunking.py`, koleksi serta operasi ChromaDB pada `vector_store.py`, dan versi korpus/invalidasi pada `corpus.py`. `embedding_service.py` mempertahankan ekspor lama. Dependency model tetap diimpor setelah pembacaan `.env`.
- Ekstraksi bertahap berada di `services/extraction/`: `contracts.py` menyimpan status/protokol/laporan, `workflow.py` mengatur simpan-jeda-resume, `mysql_storage.py` menyimpan halaman/job serta progres Redis, dan `memory_storage.py` melayani CLI satu proses. `ekstraksi_bertahap.py` mempertahankan ekspor lama. Jangan menukar urutan penyimpanan halaman/petunjuk format dengan pemeriksaan jeda.
- PDF/OCR berada di `services/ocr/`: `pdf_io.py` menangani berkas/render/teks native; `prompts.py` menyimpan prompt utuh; `vision.py` memilih model dan mengirim request; `sop.py` memeriksa hasil formulir; `cleanup.py` merapikan teks/penanda daftar; `pipeline.py` mengorkestrasi halaman dan gambar tertanam. `pdf_processor.py` mempertahankan fungsi dan konstanta yang dipakai router, worker, CLI, dan diagnostik prompt. Cache autodeteksi model vision hanya dimiliki `ocr/vision.py`.
- Intent dan tool berada di `services/routing/`: `language.py` untuk normalisasi/keyword, `patterns.py` untuk pola intent, `semantic.py` untuk cache anchor/klasifikasi, `citizen.py` untuk data warga, `calendar.py` untuk tanggal/durasi, dan `dispatch.py` untuk prioritas routing. `tool_router.py` mempertahankan ekspor lama. Perubahan struktural harus menjaga bentuk `intent`, `params`, `label`, ambang classifier, dan urutan guard handoff/pertanyaan/direktori/RAG.
- Workflow worker berada di `services/task_workflows/{legacy,extraction,embedding,cleanup}.py`. Modul task mempertahankan registrasi/decorator dan meneruskan task instance serta collaborator secara eksplisit. Jangan menukar cleanup lintas halaman dengan status review, memindahkan penghapusan vektor sebelum chunking, atau menghilangkan pemeriksaan dokumen terhapus.
- Instance Celery bersama dibuat oleh `app/celery_app.py`. Task mengimpor instance itu, dan `app.tasks.process_document` tetap mendaftarkan ketiga task untuk entrypoint worker lama. Pertahankan nama task, payload, kebijakan retry, serializer, prefetch, dan concurrency; perubahan tersebut dapat memengaruhi task yang masih mengantre.
- Hardening cancel menambahkan keyword internal `_operation_token` pada ketiga task. `document_operations.py` memiliki token, flag, dan lock dokumen. Inferensi berjalan di luar lock; SQL/vektor ditulis setelah validasi pada koneksi/lock yang sama. Retry/kelanjutan mempertahankan token. Worker tanpa token sengaja ditolak sehingga pesan lama perlu diantrekan ulang melalui endpoint mulai/resume setelah migrasi; jangan melakukan purge bersama.
- Callback progres tidak boleh dipanggil sambil menahan lock upsert karena callback membuka transaksi sendiri. Audit log worker juga harus menerima token agar insert FK memakai koneksi yang memegang lock dokumen. Cleanup vektor menggunakan dokumen dan token, bukan daftar ID hasil pembacaan lama yang dapat ditimpa generasi baru.
- `vector_cleanup.py` memiliki outbox bersama Laravel, drainer background FastAPI, serta CLI retry. Fence dan request harus commit bersama. Token kosong berarti seluruh dokumen dan harus memblokir start baru sampai cleanup selesai; token biasa aman diulang setelah resume. Outbox tidak memakai FK cascade, semua timestamp UTC, dan urutan lock selalu dokumen → request cleanup. Jangan menghapus request sebelum operasi Chroma serta pemanggilan invalidasi selesai. Reset ekstraksi DELETE hanya boleh mengubah dokumen yang masih dibatalkan di bawah lock.
- Pindahkan presentasi UI yang dipakai ulang ke komponen; letakkan panggilan backend dalam modul API per fitur.
- Frontend live chat memakai `hooks/tickets/useLiveChat`, `useConversationScroll`, dan `useTicketAttachment`; `services/liveChatService` menyatukan pengambilan serta pemetaan data antrean/pesan. Pertahankan urutan effect pemuatan awal → pemilihan tiket → auto-scroll → polling, serta layout effect pengembalian fokus input.
- Respons pesan harus cocok dengan tiket aktif dan nomor permintaan terbaru sebelum mengubah pesan/scroll/loading. Refresh antrean memakai pilihan tiket terkini; callback status/balasan lama tidak boleh mengubah percakapan yang baru dipilih.
- Data detail dokumen berada di `hooks/documents/useDocumentDetail`. Hook memiliki timer polling dan guard unmount; halaman memiliki toast, animasi, layout editor, serta tindakan mutasi. Jangan mengosongkan editor karena satu kegagalan polling setelah data berhasil dimuat.
- `ManualCorrectionEditor` mempertahankan JSX dan memakai `useCorrectionEditor` sebagai orkestrator. `useCorrectionPersistence` memiliki autosave/navigasi, `useCorrectionViewport` memiliki ukuran/zoom/pan, `useCorpusEmbedding` memiliki workflow simpan/tracker, dan `useChunkPreview` memiliki delapan state modal/parameter serta empat preset. Effect GSAP dan urutan hook/effect tetap mengikuti acuan lama setelah ekspansi hook. Pertahankan initializer, payload `??`, pemilihan preset yang langsung meminta pratinjau, serta hasil lama ketika request gagal.
- Urutkan PUT koreksi, tunggu hasilnya sebelum navigasi, dan pertahankan halaman/draft ketika gagal. History harus dipulihkan bila URL sudah berganti. `useCorpusEmbedding` menerima callback `persistCorrection` dari orkestrator dan menunggunya sebelum membuka progres/mengirim embedding; kegagalan koreksi memblokir embedding. Jangan melewati antrean simpan saat menambah tindakan editor.
- Hook layout membagi orkestrasi shell (`useAdminLayout`), notifikasi (`useAdminNotifications`), pencarian (`useAdminSearch`), dan pemantauan embedding (`useActiveEmbeddingPoller`). Workflow integrasi dibagi ke API key/WhatsApp/Telegram di `hooks/integrations/`; kategori memisahkan CRUD/form dan uji OCR di `hooks/categories/`; monitoring memisahkan telemetri/hardware; dashboard memakai `useDashboardDocuments`. Halaman/komponen tetap memiliki JSX dengan event handler dan state yang sama.
- Form pengaturan WhatsApp dan chatbot berada di `hooks/settings/`. Hook menyimpan snapshot awal dan mengelola load/save/reset/diagnostik; halaman mempertahankan navigasi, clipboard, fokus kursor prompt, dan JSX. Subscription sandbox tetap memakai singleton `aiChatService`; jangan membuat instance baru dalam hook.
- Form Direktori dan Fast Path memakai `useDirectorySettings` serta `useFastPathSettings`. Kedua hook memiliki state, pemetaan form, validasi, CRUD/filter, notifikasi dan scroll lock. JSX/portal tetap di komponen, termasuk pemetaan kelas kategori Fast Path. Pertahankan perbedaan domain seperti konversi array daftar tugas menjadi teks dan kategori bawaan yang mengikuti filter; jangan menyatukannya dengan abstraksi CRUD generik tanpa kebutuhan.
- Hindari perubahan algoritme RAG, prompt, format stream, atau urutan proses ekstraksi dalam refactor struktural kecuali ada baseline dan perubahan perilakunya memang diminta.
- Jangan mengedit output build, `node_modules`, `vendor`, virtual environment, cache, log, atau data ChromaDB sebagai bagian dari refactor sumber.

## Verifikasi lokal

Jalankan dari root repo setelah perubahan. Contoh Python memakai virtual environment lokal `python-ai/venv`; sesuaikan path bila environment bernama `.venv`.

```bash
# Frontend
(cd admin-frontend && npm run build)

# Laravel
(cd laravel-admin && php artisan test)

# Python
(cd python-ai && venv/bin/python -m unittest discover -s tests)
```

Untuk perubahan integrasi, verifikasi juga alur: login Sanctum → operasi admin; chat Laravel → Python (sinkron dan SSE); unggah/ekstraksi → koreksi halaman → indexing; serta handoff tiket → event live chat → balasan admin. Pengujian yang membutuhkan MySQL, Redis, Ollama, Reverb, atau model lokal harus dijalankan dengan layanan tersebut tersedia.

Tes kontrak dokumen Laravel memakai HTTP palsu dan disk pengujian; label/progres dashboard serta bentuk respons dicek pada batas API. Tes ini melengkapi verifikasi terhadap layanan AI dan worker yang berjalan, dan tidak menjalankan OCR atau embedding model secara nyata.

`AiMicroserviceClientContractTest` menjaga batas request keluar dan respons klien dokumen: auth, URL/konfigurasi, timeout, opsi kategori, payload editor, error FastAPI, kegagalan koneksi, dan byte gambar. Tes juga memeriksa override formatter agar pemisahan trait tetap memakai instance klien yang sama. Gunakan `Http::preventStrayRequests()` dan HTTP fake; pengujian ini tidak memerlukan database atau layanan Python aktif.

Regresi fallback chunk mencakup HTTP upstream 404/429/503, array kosong pada endpoint admin, payload sukses tanpa pembungkus, serta status/jumlah chunk dokumen yang tetap tersimpan. Return eksplisit mencegah `TypeError` pada jalur HTTP gagal.

`EntityExtractorContractTest` memeriksa parsing, normalisasi, Redis history, dan enrichment tanpa Redis nyata. `TicketWorkflowContractTest` memeriksa query, assignment, transisi, penghapusan, cleanup callback, dan penyimpanan/delivery balasan. Nama tes serta assertion yang lebih rinci ada di README Laravel.

`test_document_workflows.py` memeriksa HTTP dokumen/ekstraksi, prioritas opsi kategori, urutan simpan/antre, koreksi, preview, citra/cache, SSE dan cleanup pembatalan. `test_task_workflows.py` memeriksa cleanup sebelum review, retry gambar, serta batas penulisan/progres ketika dokumen dihapus atau tokennya dibatalkan. `test_document_operations.py` dan `test_vector_cancellation.py` menjaga lock, token, pembatalan/resume dan cleanup terisolasi. Broker, model dan transport diganti mock; tes store memakai SQLite atau transaksi MySQL tiruan. Respons `cancelled` merupakan acknowledgement kooperatif, bukan bukti proses model sudah diputus.

`test_vector_cleanup.py` memeriksa retry/backoff, rollback dua arah antara
fence/outbox, acknowledgement SQL gagal setelah delete remote, token baru,
orphan, gate start penuh dan reset ekstraksi terlambat. Runner
[`run_cleanup_recovery.py`](../scripts/integration/run_cleanup_recovery.py)
mematikan Chroma serta me-restart API milik run untuk memeriksa pemulihan
background melalui MySQL/HTTP nyata. Batch vektor dalam profil tersebut adalah
fixture sintetis, bukan pengujian timing encoder model.

`SettingsContractTest` menjaga 13 route pengaturan beserta nilai JSON, prompt, payload kanal, katalog model, dan diagnostik dengan HTTP palsu. Tes Python di `tests/test_rag_contract.py` memakai dependency jaringan tiruan untuk memeriksa retrieval, grounding, streaming, orkestrasi, serta bentuk event SSE. Pengujian ini tidak menjalankan model atau menilai mutu OCR/jawaban.

Regresi kanal dijaga oleh `ChannelWebhookContractTest`, `TelegramPollingContractTest`,
`TelegramStreamContractTest`, dan `PublicChatGatewayContractTest`. Transport SSE
diganti mock melalui `AiChatGateway`; `Http::fake` saja tidak mencegat cURL mentah.
Tes Python tambahan pada `test_ocr_regression.py` dan
`test_routing_extraction_regression.py` memeriksa cache, retry, prioritas routing,
urutan simpan/jeda/resume, serta batas retry/requeue Celery tanpa model/broker nyata.

`test_health_contract.py` memeriksa HTTP 200/503, alias/cache health, HTTP 401 hardware meski cache tersedia, TTL/nocache, override model pada cache, serta parser dan estimasi hardware dengan probe tiruan. `test_database_contract.py` menjaga opsi engine, SQL/parameter, fallback pengaturan, cache stale, dan debounce log memakai koneksi tiruan. Pengujian ini tidak membuktikan konektivitas MySQL atau kondisi hardware nyata; periksa integrasi tersebut pada lingkungan layanan aktif.

Untuk perubahan frontend, bandingkan hasil render sebelum dan sesudah refactor pada route, ukuran layar, tema, serta data yang sama. Periksa juga animasi, navigasi, fokus input, dan posisi scroll agar refactor tidak mengubah UI yang sudah ada.

Pemeriksaan sumber dapat membandingkan JSX, callback GSAP, handler yang dipindahkan, dan dependency effect sebelum/sesudah. Build frontend memeriksa kompilasi/resolusi modul; keduanya tidak menggantikan pemeriksaan browser atau integrasi dengan backend aktif. Peta hook dan perilaku rinci ada di [`../admin-frontend/README.md`](../admin-frontend/README.md).

`npm run verify:ui` di frontend menyediakan pemeriksaan JSX/aset dan ekspansi
workflow kedua form terhadap baseline Git. Regresi CRUD browser tersedia pada
`scripts/integration/browser/settings-crud.js`, dengan comparator screenshot
`scripts/integration/compare_settings_screenshots.py`. Seluruh sumber verifier
dan instruksi tersedia dalam repository, tanpa bergantung pada verifier lama
di `/tmp`. Batas pemeriksaan serta prosedur capture ada di
[panduan verifikasi frontend](../admin-frontend/scripts/README.md).

Pada pemisahan pratinjau editor, seluruh JSX serta statement effect/handler di luar hook dibandingkan dengan acuan sumber. Pemeriksaan browser memakai API/dokumen sintetis pada viewport 1440×1000 untuk empat kondisi editor/modal dan memeriksa payload preset/kustom serta kegagalan request. Pemeriksaan ini tidak menjalankan autentikasi admin, OCR, atau embedding nyata.

Tahap multiagent memperluas perbandingan frontend ke editor, layout, integrasi API key/WhatsApp/Telegram, kategori, telemetri, hardware, dan dashboard. Verifikasi sumber mengekspansi hook untuk membandingkan JSX, statement, dependency array, serta urutan hook/effect dengan snapshot awal. Fixture browser membandingkan teks, nilai/disabled kontrol dan geometri, serta memeriksa autosave/navigasi/zoom editor. Status dan batas bukti tercatat di [checklist refactor](09-status-refactor-dan-verifikasi.md).

## Sumber kebenaran versi dan konfigurasi

- Frontend: `admin-frontend/package.json` dan `package-lock.json`.
- Backend: `laravel-admin/composer.json` dan `composer.lock`.
- AI: `python-ai/requirements.txt` untuk rentang dependensi dan `requirements.lock.txt` untuk resolusi yang dikunci.
- Konfigurasi deployment: `docker-compose.yml`, Dockerfile, `.env.example`, `start-all.sh`, dan `stop-all.sh`.

Jika angka versi atau daftar fitur di dokumen lain berbeda dari implementasi, verifikasi manifest dan route aktif, lalu perbarui dokumen terkait dalam perubahan yang sama.
