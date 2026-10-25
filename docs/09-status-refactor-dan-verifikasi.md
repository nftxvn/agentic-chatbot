# Status Refactoring, Audit dan Bukti Verifikasi

**Status terbaru 26 Oktober 2026:** refactoring awal ketiga aplikasi dan
pembaruan dokumentasi telah ditutup; temuan audit A1/A2 sudah ditangani.
Bukti audit, penutupan dan batas kesetaraan UI disatukan di dokumen ini.
Ini tidak menyatakan aplikasi bebas seluruh bug atau sudah dideploy.

Cakupan awal adalah struktur `admin-frontend`, `laravel-admin`, dan `python-ai`,
dokumentasi yang sesuai, serta UI yang dipertahankan. Publikasi korpus atomik,
pengiriman kanal eksternal, deployment dan evaluasi mutu model merupakan
pekerjaan terpisah. Catatan bertanggal di bawah adalah hasil run pada tahapnya;
jumlah tes lama tidak menggantikan hasil audit terbaru.

## Checklist tahap ini

| Area | Hasil yang diperiksa | Status |
| --- | --- | --- |
| Editor koreksi | State/data, autosave/navigasi, viewport, pratinjau dan workflow korpus memiliki batas tanggung jawab | Selesai; source verifier dan fixture browser lulus |
| Layout admin | Notifikasi, pencarian dan pemantauan embedding terpisah dari JSX | Selesai; source verifier dan fixture browser lulus |
| Integrasi dan kategori | Workflow API key/WhatsApp/Telegram serta CRUD kategori/uji OCR dipisah | Selesai; source verifier dan fixture browser lulus |
| Monitoring dan dashboard | Pengambilan data/telemetri/hardware dipisah dari presentasi | Selesai; source verifier dan fixture browser lulus |
| Router Python | Dependency/schema/HTTP tetap pada router; workflow dokumen dan ekstraksi terpisah | Selesai; AST, tes HTTP dan OpenAPI 23 path identik |
| Worker Python | Entry point/nama task Celery tetap; implementasi workflow terpisah | Selesai; AST, retry/requeue dan tes batas worker lulus |
| Entity extractor Laravel | Parsing, leksikon/normalisasi, Redis history, dan enrichment terpisah | Selesai; AST dan tes karakterisasi lulus |
| Tiket Laravel | Query, lifecycle, serta penyimpanan/delivery balasan terpisah dari HTTP | Selesai; suite terbaru 227 tes Laravel / 1403 assertion lulus |
| Dokumentasi | Peta modul, kontrak, konfigurasi, contoh SSE dan diagram mengikuti implementasi | Selesai; review sumber, tautan dan contoh SSE lulus |
| Pembatalan dokumen | Token persisten, guard SQL/vektor, cancel/resume serta isolasi antrean | Selesai; 16 pemeriksaan integrasi termasuk alur utama dan cancellation lulus |
| Browser dengan backend nyata | Login/upload/editor, pengaturan, live chat, tema/viewport dan logout | 20 pemeriksaan alur/kondisi lulus; 36 tangkapan layar utama |
| Pemulihan cleanup | Outbox SQL, retry lintas restart, tombstone delete, dan gate replacement | Selesai; sembilan pemeriksaan layanan nyata lulus |
| Direktori dan Fast Path | Workflow form terpisah dari JSX/portal, verifier tersedia dalam repository | Selesai; ekspansi AST dan 18 pemeriksaan browser terkelompok lulus |

## Perubahan perilaku yang disengaja

- Perbaikan fallback chunk pada tahap sebelumnya: HTTP non-2xx dari Python menghasilkan `[]` pada klien Laravel, sehingga endpoint pembacaan chunk tidak lagi gagal karena return yang hilang. Status dan jumlah chunk tersimpan pada dokumen tetap dipertahankan.
- Pada tahap awal, impor dependency pembaruan status yang hilang diperbaiki agar handler cancel tidak gagal dengan `NameError`. Hardening berikutnya mengganti perilaku purge/unload lama dengan pembatalan kooperatif per dokumen sebagaimana dijelaskan di bawah.
- Integrasi menemukan pemangkasan format koreksi oleh middleware Laravel. `TrimStrings` kini dilewati hanya pada endpoint PUT koreksi halaman; validasi menolak teks kosong termasuk whitespace Unicode tanpa mengubah teks valid. Indentasi, tab, CRLF dan newline diteruskan/disimpan utuh.
- Parser sitasi JSON kini membaca separator halaman yang benar-benar dipakai retrieval. Resolusi ID dari judul dibatasi kecocokan tepat dan unik dalam `document_ids`; judul ambigu atau tanpa scope tetap dapat memiliki ID `null`. Teks jawaban dan protokol SSE tetap sama.
- Callback tiket Python menerima `LARAVEL_BASE_URL` eksplisit yang tidak fallback ke instance lain. Tanpa konfigurasi tersebut, daftar discovery lama dipertahankan.
- `CHROMA_HTTP_HOST` mengaktifkan satu server Chroma bagi API dan worker. Pengujian embedded lintas proses sebelumnya gagal membuka segmen HNSW saat query, meskipun count/chunk terbaca. Mode HTTP memperbaiki batas ini pada profil uji; host kosong tetap memakai mode embedded lama.

## Hasil pemisahan struktural 24 Oktober

- Python: seluruh 142 tes lulus setelah pemisahan workflow. OpenAPI lengkap tetap identik pada 23 path; tiga nama task dan konfigurasi retry tetap sama. Perbandingan AST menjaga signature/decorator serta urutan statement pada 19 endpoint, helper terkait, dan empat implementasi worker/cleanup.
- Router meneruskan workflow ke tujuh modul `services/document_workflows/`; worker meneruskan pipeline ke empat modul `services/task_workflows/`. Tidak ada perubahan skema database, prompt, algoritme chunking, atau konfigurasi task.
- Pada lanjutan terakhir, hash sumber frontend dan Laravel sama dengan snapshot awal lanjutan. Hasil sebelumnya tetap berlaku: build frontend lulus, sembilan kondisi layar diperiksa dengan fixture browser, serta 208 tes Laravel / 1321 assertion lulus.
- Verifier frontend memeriksa JSX, hook/effect, dependency dan payload. Urutan semua statement non-hook tidak dibuktikan otomatis oleh verifier; wiring penting ditinjau manual dan interaksi editor diperiksa melalui fixture. Bukti tersebut tetap terbatas pada kondisi sintetis yang diuji.

Pemisahan struktural pada checklist ini selesai. Hasil tersebut dicatat terpisah dari smoke test layanan nyata dan pekerjaan operasional yang tersisa di bawah.

## Batas pembuktian

Pemeriksaan sumber menggunakan snapshot sebelum tahap ini agar perubahan refactor terdahulu di workspace tetap dipertahankan. Kontrak yang dijaga meliputi JSX, hook/effect dan payload frontend; route/middleware/JSON Laravel; OpenAPI, autentikasi, SQL, progres, dan registrasi task Python.

Suite unit/fitur Laravel memakai SQLite in-memory serta HTTP/Redis/broadcast tiruan. Suite unit Python menggantikan koneksi database, broker, model dan transport jaringan. Fixture browser memakai data sintetis. Ketiganya memberikan bukti kontrak dan kesetaraan struktural; smoke test layanan nyata berikut memakai proses dan penyimpanan tersendiri.

Pembatalan kini tidak melakukan purge atau unload model bersama. Kolom token
dan flag cancellation mengotorisasi setiap write worker pada baris dokumen yang
dikunci. Cancel/resume menggagalkan token lama; panggilan model yang sedang
berjalan tidak diputus, tetapi hasilnya dibuang sebelum disimpan. Cleanup
generasi parsial hanya memakai filter dokumen dan token, sehingga vektor
dokumen/generasi lain tetap ada. Jika Chroma tidak tersedia, fence SQL tetap
berlaku dan request cleanup disimpan pada outbox untuk retry otomatis;
penggantian korpus belum merupakan transaksi atomik lintas layanan.

## Integrasi layanan nyata 25 Oktober

Runner tersedia pada [panduan integrasi](../scripts/integration/README.md). Pemeriksaan yang sudah lulus memakai server MySQL/Redis/Chroma baru, FastAPI, Celery, Laravel, serta model Ollama lokal yang sudah terpasang. Database, broker, storage, indeks dan `.env` operasional tetap dipertahankan; tidak ada endpoint cancel atau penerima kanal eksternal yang dipanggil.

- Login/logout cookie Sanctum melalui HTTP, 401 tanpa sesi dan 419 tanpa CSRF.
- Unggah PDF dua halaman sintetis: vision OCR pada citra dan ekstraksi native pada halaman berikutnya.
- Pause setelah halaman disimpan, resume tanpa menimpa halaman tersimpan, lalu gerbang `menunggu_koreksi` tanpa vektor.
- Koreksi teks termasuk newline akhir, ukuran halaman, dan preview dengan overlap nol.
- Embedding pada worker nyata, penyimpanan Chroma, serta status/jumlah vektor melalui Laravel.
- Chat JSON dan SSE melalui gateway yang menjawab 37 menit dari koreksi, disertai sitasi dokumen pada JSON dan event `done` pada SSE.
- Pertanyaan naratif melalui stream Python mencapai trace `generation`, menghasilkan fakta pemeriksaan registrasi/kelengkapan dari konteks, dan melaporkan model `qwen2.5:3b` pada telemetry.

Run akhir lulus **12 pemeriksaan**, dengan semua proses milik runner berhenti.
Artefak sesi tersimpan sementara pada
`/tmp/agentic-integration-n9l_442u/report.json`, bersama PDF, log dan data uji.
Perintah runner dapat dipakai untuk menghasilkan laporan baru; durasi sesi
62,14 detik ini bukan benchmark.

Profil memakai vision `qwen2.5vl:7b-q4_K_M`, chat `qwen2.5:3b`, embedding `bge-m3:latest`, context 4096 dan reranker nonaktif. Ini smoke test fakta sintetis, bukan evaluasi kualitas umum atau benchmark performa.

Ada batas kualitas yang terlihat pada jawaban naratif: setelah menjelaskan
tugas petugas dengan benar, model menambahkan bahwa estimasi waktu tidak
spesifik, meskipun konteks memuat 37 menit. Assertion smoke test memeriksa jalur
generasi dan fakta tugas yang diminta; kelulusan tersebut tidak membuktikan
seluruh klaim tambahan model benar. Evaluasi grounding pada korpus representatif
tetap diperlukan sebelum menyatakan mutu jawaban memadai.

Suite sebelum hardening cancel: **164 tes Python lulus; 219 tes Laravel / 1371 assertion lulus**. Source frontend tetap dipertahankan; pengujian tahap ini tidak menjalankan browser.

## Hardening pembatalan per dokumen

Suite pada tahap pembatalan lulus **210 tes Python** dan **223 tes Laravel / 1390 assertion**.
Run `--cancellation` lulus **16 pemeriksaan integrasi nyata**, mencakup 12
pemeriksaan alur utama dan empat skenario tambahan:

1. Cancel task A yang masih antre tidak menghapus pesan B; B selesai dan A
   tidak menulis halaman.
2. Cancel OCR C yang aktif lalu langsung resume menghasilkan token baru.
   Hasil C lama dibuang dan dokumen D di belakangnya tetap diproses.
3. Generasi C baru menyelesaikan dua halaman tanpa hasil lama atau duplikasi.
4. Cancel setelah pekerjaan selesai mempertahankan korpus. Fixture vektor
   parsial pada generasi embedding baru dibersihkan tanpa menghapus korpus
   sebelumnya; task embedding yang dibatalkan dibuang ketika dikonsumsi.

Artefak sesi sementara: `/tmp/agentic-integration-13zdigm3/report.json`.
Semua proses milik runner berhenti. Pembatalan tepat saat encoding diperiksa
dengan tes unit terarah; fixture parsial di Chroma nyata tidak diklaim sebagai
pengujian timing encoding model. Laravel juga diuji menyimpan fence sebelum
HTTP cancel/replace/delete yang gagal, serta terhadap model Eloquent yang
sudah dimuat sebelum resume lain memperbarui database.

Migrasi `2026_10_25_000001_add_document_operation_fences.php` hanya dijalankan
di database sementara. Rollout memerlukan migrasi sebelum API/worker baru dan
penghentian worker lama yang belum mengenali token. Pesan lama tanpa token
ditolak; dokumennya perlu dimulai/resume kembali tanpa purge antrean bersama.
Signature HTTP, bentuk data utama, JSX, CSS, dan route Laravel dipertahankan.
Metadata OpenAPI cancel diperbarui untuk menyatakan semantik kooperatif, dan
task Celery mendapat keyword internal opsional `_operation_token`.

## Browser dengan backend nyata, 25 Oktober

Profil browser memakai Chromium headless, Vite, Laravel, MySQL, Redis,
FastAPI, Celery, Chroma HTTP dan Ollama lokal. Semua penyimpanan/akun memakai
fixture sementara. Unggah PDF native dua halaman dilakukan melalui browser;
worker mencapai gerbang koreksi, lalu konfirmasi korpus dari browser menghasilkan
empat vektor yang memuat penanda koreksi terbaru.

**20 pemeriksaan alur/kondisi lulus**, meliputi login salah/benar, unggah,
autosave berformat dan fokus, navigasi/history/shortcut, kegagalan simpan,
pengurutan simpan, flush sebelum korpus, penolakan korpus jika koreksi gagal,
loading/simpan pengaturan, pergantian tiket, polling/scroll/unread, balasan
gagal/retry, pembaruan status, tema/viewport, embedding nyata dan logout.
Skenario CLI dan prasyaratnya ada di [panduan browser](../scripts/integration/browser/README.md).

Empat masalah perilaku berhasil direproduksi sebelum diperbaiki:

- Navigasi tetap berpindah setelah PUT koreksi gagal sehingga draft hilang.
  Kini perpindahan dibatalkan dan URL history dikembalikan ke halaman draft.
- Autosave lama yang lambat menimpa koreksi lebih baru. Permintaan koreksi
  kini diurutkan sebelum navigasi atau tindakan berikutnya dilanjutkan.
- Permintaan korpus bisa dikirim sebelum autosave terakhir. Konfirmasi kini
  menunggu koreksi tersimpan; kegagalan koreksi mempertahankan draft dan
  tidak mengirim permintaan embedding.
- Respons pesan tiket lama bisa mengganti percakapan tiket yang baru dipilih.
  Pembaruan pesan/scroll, antrean dan hasil status/balasan kini memeriksa tiket
  aktif serta urutan respons yang sesuai.

Build frontend lulus (166 modul). Dari snapshot awal tahap browser, 82 berkas
sumber dibandingkan: hanya empat hook yang berubah (`useCorrectionPersistence`,
`useCorrectionEditor`, `useCorpusEmbedding`, `useLiveChat`). Seluruh komponen,
JSX, stylesheet dan aset dalam snapshot tetap identik. Tidak ada perubahan
layout, warna, teks atau kontrol UI.

Dashboard, editor, pengaturan, integrasi, monitoring dan live chat diperiksa
pada tema terang/gelap di viewport 1440×1000, 1024×768 dan 390×844: **36
tangkapan layar**, tanpa overflow horizontal pada elemen halaman. Ini tidak
membuktikan seluruh kontrol nyaman pada perangkat fisik; editor mobile masih
memakai kolom sempit dari layout yang ada. Navigasi mobile, reset zoom editor,
dan pratinjau chunk nyata juga diperiksa. Screenshot tahap ini adalah bukti
kondisi akhir, bukan perbandingan piksel otomatis sebelum/sesudah.

HTTP 500/503 dan keterlambatan tertentu sengaja disisipkan pada browser untuk
menguji kegagalan/race; request lain menuju layanan nyata. Log mencakup 401
yang diharapkan saat tanpa sesi, error injeksi, dan Fast Refresh saat hook
diubah. Reload penuh dilakukan setelah perubahan jumlah hook. Kelulusan tidak
berarti seluruh log selama pengembangan bebas error. Balasan web memakai
tiket sintetis tanpa API key atau penerima kanal eksternal.

Laporan dan screenshot lokal ada di
`output/playwright/browser-integration/report.json`; direktori tersebut diabaikan
Git. Log/data layanan sementara ada di `/tmp/agentic-integration-t14uonba`.
Sesi browser dan seluruh proses milik runner telah dihentikan. Suite backend
ketika itu tetap 210 Python dan 223 Laravel / 1390 assertion; tahap browser ini
tidak menjalankan ulang kedua suite tersebut.

## Pemulihan cleanup lintas gangguan layanan

Suite terbaru lulus **228 tes Python** dan **227 tes Laravel / 1403 assertion**.
Migrasi baru `2026_10_25_000002_create_document_vector_cleanups_table.php`
menambahkan outbox SQL tanpa FK cascade ke dokumen. Laravel/Python menyimpan
request cleanup dan fence dalam satu transaksi sebelum I/O ke Chroma. Cancel
memakai token generasi yang belum selesai, sedangkan replace/delete memakai
scope seluruh dokumen. Request tetap ada setelah dokumen dihapus.

Lifespan FastAPI menguras maksimal 10 request pada startup dan setiap 30 detik
melalui thread, dengan backoff retry 30–300 detik. Scope token aman terhadap
resume; scope penuh menahan generasi baru sampai cleanup selesai. Handler
mulai/resume/embedding Python mencoba cleanup terlebih dahulu dan mengembalikan
503 jika masih tertunda. Callback reset ekstraksi DELETE juga memeriksa fence
di bawah lock, sehingga callback lama tidak menghapus halaman generasi baru.

Uji outage menemukan jadwal Laravel yang semula memakai WIB terbaca sebagai
waktu UTC oleh Python. Timestamp outbox kini diseragamkan ke UTC dan memiliki
tes regresi. Tes juga memeriksa rollback kedua arah antara fence/outbox serta
pengulangan setelah delete Chroma berhasil tetapi acknowledgement SQL gagal.

Runner [pemulihan cleanup](../scripts/integration/run_cleanup_recovery.py)
lulus **sembilan pemeriksaan termasuk setup**, memakai MySQL, Redis, Chroma,
Laravel, FastAPI dan worker asli pada penyimpanan sementara:

- Cancel saat Chroma offline tetap mencatat token lama meskipun langsung resume.
- Replacement tidak memulai generasi baru selama cleanup penuh tertunda.
- Delete saat Python offline menghapus baris dokumen tetapi mempertahankan
  request cleanup di SQL.
- API yang di-restart menemukan request lama; ketika Chroma hidup kembali,
  drainer background membersihkan scope lama serta menjaga ID yang telah
  dipakai ulang oleh generasi baru dan vektor dokumen lain.
- Replacement dapat dilanjutkan dan mencapai review setelah cleanup selesai.

Artefak: `/tmp/agentic-integration-mfawjv0e/report.json`; seluruh proses awal
dan hasil restart milik runner telah berhenti. Batch vektor adalah fixture
dua dimensi dan deadline retry fixture dimajukan setelah Chroma pulih; tes ini
tidak mengukur timing encoder model. Perintah dan batas profil ada di
[panduan integrasi](../scripts/integration/README.md).

Regresi alur utama dan pembatalan juga lulus kembali **16 pemeriksaan** pada
`/tmp/agentic-integration-p6vkyb0f/report.json`, mencakup OCR/embedding model
nyata, chat JSON/SSE dan pembatalan antrean/OCR/embedding. Seluruh proses milik
run tersebut telah berhenti.

Kedua migrasi fence/outbox hanya diterapkan pada database sementara. Rollout
operasional tetap perlu menjalankan migrasi sebelum API/worker baru serta
menghentikan worker lama. Retry otomatis memerlukan FastAPI hidup; tersedia CLI
`python -m app.services.vector_cleanup` untuk request yang sudah tercatat.
Tidak ada perubahan frontend/UI. Ini pemulihan eventual: vektor orphan bisa
tetap ada selama outage, dan penggantian korpus belum atomik lintas SQL/Chroma.

## Audit dan penutupan 26 Oktober

Audit menilai permintaan awal, tanpa menambahkan syarat fitur/deployment baru.
Tidak semua berkas harus berubah: komponen presentasi dan modul kecil yang
kohesif dapat dipertahankan. Jumlah baris, jumlah agen dan banyaknya tes bukan
persentase penyelesaian. Tidak ditemukan regresi yang terbukti melalui
pemeriksaan audit; kesimpulan tetap terbatas pada cakupan pengujiannya.

Pada audit awal, A1 menemukan workflow Direktori/Fast Path masih menyatu dengan
JSX. A2 menemukan sebagian verifier dan baseline tahap lama hanya berada di
`/tmp`. Keduanya merupakan temuan pemeliharaan, bukan laporan kegagalan runtime.
Tabel berikut menyatakan hasil penutupan setelah perbaikan.

### Penutupan temuan

| Temuan | Perubahan dan bukti | Status |
| --- | --- | --- |
| A1: workflow Direktori/Fast Path menyatu dengan JSX | `useDirectorySettings` dan `useFastPathSettings` memiliki state, filter, validasi, CRUD/notifikasi dan scroll lock; komponen mempertahankan JSX/portal. Ekspansi AST hook cocok dengan body awal, termasuk urutan effect dan payload | Ditutup |
| A2: verifikasi UI bergantung pada artefak/verifier sementara | `npm run verify:ui`, skenario browser `settings-crud.js`, comparator gambar, baseline Git eksplisit, dan instruksi tersedia di repository | Ditutup |
| Status/dokumentasi penutupan belum tegas | Peta hook dan prosedur verifikasi diperbarui; daftar fitur/deployment tambahan dipisahkan dari syarat refactoring | Ditutup |

Kode workflow ada pada
[`useDirectorySettings.js`](../admin-frontend/src/hooks/settings/useDirectorySettings.js)
dan [`useFastPathSettings.js`](../admin-frontend/src/hooks/settings/useFastPathSettings.js).
Pemetaan kelas kategori Fast Path tetap berada di komponen presentasi. Tidak
ada perubahan endpoint, payload, pesan validasi, label, markup, atau CSS pada
pemindahan kedua workflow ini.

### Pemeriksaan yang selesai

- Build frontend lulus: **168 modul**. Fingerprint stylesheet keluaran tetap
  `index-BDeneO2c.css`, sama seperti sebelum pemindahan. Peringatan ukuran
  bundle utama >500 kB tetap ada.
- `npm run verify:ui` lulus terhadap Git
  `129834bddfde6cd9253b270553d9ac7e0283db05`: 35 berkas JSX identik, pemindahan
  badge live chat tervalidasi pada empat status, delapan stylesheet/aset/HTML
  acuan identik, serta kedua body workflow identik setelah ekspansi hook.
- Negative control pada salinan sementara membuktikan verifier menolak
  perubahan JSX, initializer workflow dan CSS. Kode aplikasi tidak dimutasi
  untuk negative control tersebut.
- Browser dengan Laravel/MySQL nyata lulus **18 pemeriksaan terkelompok per
  run** sebelum dan sesudah perubahan: loading, validasi lokal, portal/scroll,
  create gagal/retry, edit/batal, format field, persistensi, toggle,
  pencarian/reload, delete batal/gagal/retry, dan reset form baru.
- Pembandingan label, nilai, status checkbox, disabled state dan geometri
  kontrol lulus pada **24 kondisi capture / 210 pengukuran kontrol**.
- Logout nyata dan pengalihan halaman privat ke login diperiksa setelah uji.

Backend tidak diubah pada penutupan ini. Hasil audit sebelumnya tetap **228 tes
Python** dan **227 tes Laravel / 1403 assertion**, bukan suite yang dijalankan
ulang pada tahap frontend ini.

### Hasil perbandingan gambar

Capture memakai daftar/modal kedua form, tema terang/gelap, serta viewport
1440×1000, 1024×768 dan 390×844. **21 dari 24 pasangan identik piksel**. Tiga
pasangan daftar memiliki selisih 5, 14 dan 24 piksel; dimensi gambar serta
seluruh pengukuran kontrol tetap sama. Seluruh 12 pasangan modal identik.

Comparator ketat **tetap mengembalikan gagal** untuk pasangan yang memiliki
selisih; hasil ini tidak dilaporkan sebagai 24 pasangan identik. Review batas
diff menemukan 5 piksel pada tepi border dalam area 2×3 piksel, serta selisih
kecil pada raster daftar mobile. Kontrol tambahan membandingkan dua capture
dari **kode final yang sama**: selisih 14 dan 24 piksel muncul kembali di area
yang sama, sedangkan 22 pasangan lainnya identik.

Kesamaan source/stylesheet, body workflow, data/geometri kontrol, dan kontrol
capture dengan kode yang sama mendukung kesimpulan tidak ada perubahan UI
akibat pemindahan hook. Ini review dengan variasi raster yang dicatat, bukan
klaim kesamaan piksel mutlak pada semua lingkungan atau seluruh state produk.
Ambang comparator tidak dilonggarkan.

Sesi uji pertama sempat kedaluwarsa. Baseline asli dan versi refactor disimpan
terpisah, lalu capture terakhir diulang pada lingkungan baru. Toast sementara
ditutup melalui kontrol UI sebelum capture agar tidak menutupi form. Snapshot
`before` terakhir dirender dengan kode komponen asli; snapshot `after`
dirender setelah kedua hook dikembalikan. Screenshot versi akhir tidak disalin
untuk dijadikan baseline awal.

### Prosedur dan artefak

Prosedur yang dapat dijalankan dari checkout ada di
[panduan verifikasi frontend](../admin-frontend/scripts/README.md). Verifier
sumber memakai baseline Git, bukan baseline tersembunyi di `/tmp`. Regresi
browser standalone dapat dijalankan melalui Playwright CLI pada fixture
sementara. Mode `before/after` menambahkan pembandingan layout dan screenshot.

Artefak lokal pada `output/playwright/refactor-closure/` meliputi:

- `report.json`: ringkasan penutupan dengan status pixel comparator apa adanya.
- `source-verification.json` dan `source-negative-controls.json`.
- `pixel-comparison.json`: hasil ketat sebelum/sesudah.
- `same-code-pixel-comparison.json`: kontrol dua capture dari kode final sama.
- `before-*`, `after-*` dan `current-*` PNG, serta snapshot/log CLI.
- `settings-before-state.json` dan `settings-after-state.json`, berisi state
  browser sintetis. Direktori privat ini diabaikan Git.

Laporan environment terakhir berada di
`/tmp/agentic-integration-xflw775x/report.json`. Browser ditutup dan seluruh
proses milik runner telah dihentikan. Migrasi hanya diterapkan pada database
sementara. Tidak ada pesan kanal eksternal atau inferensi OCR/RAG yang
dipicu oleh regresi CRUD ini.

### Bukti tambahan pada audit awal

Build audit awal lulus dengan 166 modul; build penutupan berikutnya mencapai
168 modul karena dua hook baru. Suite backend dijalankan ulang saat audit:
228 tes Python serta 227 tes Laravel / 1403 assertion lulus. Parse AST seluruh
78 berkas Python dan lint 78 berkas PHP aplikasi lulus pada checkout audit.
Pemeriksaan tautan/pagar kode pada 17 dokumen utama saat itu juga lulus;
angka tersebut merekam kondisi sebelum konsolidasi dokumentasi.

Perbandingan sumber terhadap Git `129834bddfde6cd9253b270553d9ac7e0283db05`
menemukan 35 dari 36 berkas JSX identik; satu lainnya adalah pemindahan badge
live chat yang divalidasi tersendiri. Sampel lima modul inti Python memuat
99 definisi identik setelah pemindahan fungsi dan pengabaian docstring; enam
definisi berubah untuk guard/transport Chroma, checkpoint OCR, status dan log.
Dispatch tiket berpindah ke `backend_client.dispatch_ticket_to_laravel` dengan
alias kompatibilitas. Tidak ditemukan fungsi lama tanpa pengganti pada sampel
tersebut. Identitas AST tidak membuktikan seluruh import/global state/lifecycle.
Route pengaturan Laravel hanya berganti controller tujuan pada diff audit;
metode, path, nama dan middleware dipertahankan.

Audit memeriksa kembali laporan 20 pemeriksaan browser/36 screenshot,
16 pemeriksaan pipeline/cancel dan sembilan pemeriksaan cleanup dari run
25 Oktober di atas. Ini review artefak lama, bukan run integrasi/model baru.
Workspace berisi perubahan terdahulu serta berkas untracked; audit tidak
mengatribusikan seluruh diff kepada satu tahap dan tidak mengklaim memiliki
snapshot lengkap sebelum percakapan pertama.

Contoh batas kelulusan tes: GET preview dengan overlap query `0` tetap memakai
default 200/50, sementara POST mempertahankan `0`. Perilaku lama ini dijaga oleh
`test_preview_body_zero_overlap_is_preserved_while_query_zero_uses_existing_default`;
kelulusan tes tidak menyatakan semua perilaku lama sudah ideal. Perubahan
semantiknya merupakan bugfix tersendiri.

## Verifikasi tambahan dan pekerjaan produk/operasional

Daftar berikut mencatat perluasan QA, fitur dan kesiapan operasional. Seluruhnya
tidak otomatis menjadi syarat wajib untuk menyelesaikan refactoring awal;
pemeriksaan regresi yang relevan dengan kode yang diubah tetap diperlukan.

1. Perluasan browser QA ke lampiran, CRUD kategori, operasi integrasi, sandbox SSE, dan browser/perangkat lain. Alur admin utama, tema/viewport, fokus/scroll dan error/loading di atas sudah diperiksa.
2. Handoff tiket, balasan petugas dan pengiriman WhatsApp/Telegram/webhook ke penerima uji yang ditentukan.
3. Penggantian korpus secara atomik dan pembatasan retrieval terhadap generasi yang dipublikasikan; retry cleanup persisten sudah diterapkan.
4. Konfigurasi deployment/launcher untuk server Chroma bersama serta rollout kedua migrasi fence/outbox. Mode HTTP sudah tersedia dan diuji; konfigurasi/indeks operasional tidak diubah otomatis. Penanda versi korpus tetap perlu dibagi oleh API dan worker.
5. Evaluasi OCR/RAG pada korpus representatif, reranker aktif, beban serentak, serta kondisi kegagalan layanan.

Detail perintah dan batas layanan ada di [panduan kerja mandiri](04-panduan_kerja_mandiri_dev.md), [panduan runner](../scripts/integration/README.md), serta README masing-masing aplikasi.
