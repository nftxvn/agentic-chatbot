# Admin Frontend

SPA React untuk dashboard admin, pengelolaan dokumen, RAG playground, pengaturan integrasi, log percakapan, dan live chat. Versi frontend yang dipakai ditetapkan di `package.json` dan `package-lock.json`.

## Batas kode

UI yang ada menjadi acuan refactor. Pertahankan layout, warna, font, tema, animasi, navigasi, teks, serta interaksi pengguna. Pemindahan logika ke komponen atau hook harus menjaga hasil render, fokus input, dan perilaku scroll.

- `src/pages/`: komposisi layar dan alur interaksi halaman.
- `src/components/`: komponen UI yang dapat dipakai ulang; komponen domain ditempatkan dalam subdirektori seperti `Tickets/`.
- `src/hooks/`: state dan alur per fitur; hook dipanggil oleh halaman dan tidak merender elemen UI.
- `src/api/`: modul endpoint per fitur. Konfigurasi Axios dan perilaku autentikasi terpusat di `src/api/client.js`.
- `src/context/`: state aplikasi lintas halaman seperti autentikasi dan tema.
- `src/services/`: orkestrasi data dan layanan bersama. `liveChatService` tidak menyimpan state; `aiChatService` menyimpan sesi streaming agar tetap tersedia saat halaman berganti.

Gunakan Laravel sebagai sumber API admin dan pertahankan cookie Sanctum, format response, serta kontrak SSE yang didokumentasikan di [`../docs/03-api_spec_agentic_copilot.md`](../docs/03-api_spec_agentic_copilot.md). Live chat pada frontend saat ini menggunakan polling; broadcasting Reverb tetap disediakan backend untuk konsumennya.

## Pembagian logika halaman

Semua path berikut relatif terhadap `src/`:

| Modul | Tanggung jawab |
| --- | --- |
| `hooks/tickets/useLiveChat.js` | Antrean, filter, tiket terpilih, polling, balasan, status, penghapusan, notifikasi, dan pengembalian fokus input |
| `hooks/tickets/useConversationScroll.js` | Posisi scroll, ambang dekat bawah 100px, badge unread, dan auto-scroll pesan baru |
| `hooks/tickets/useTicketAttachment.js` | Pilihan file, batas 10 MB, object URL pratinjau, dan reset input file |
| `services/liveChatService.js` | Pengambilan antrean/statistik bersamaan dan pemetaan bentuk respons pesan |
| `hooks/documents/useDocumentDetail.js` | Data detail dan chunk, polling pemrosesan, serta pembatasan update setelah unmount |
| `hooks/documents/useChunkPreview.js` | State modal pratinjau editor, parameter/preset chunk, pengambilan pratinjau, dan pemilihan preset |
| `hooks/documents/useCorrectionEditor.js` | Data halaman/draft, kesiapan korpus, event hasil embedding, animasi modal chunk, serta komposisi hook editor |
| `hooks/documents/useCorrectionPersistence.js` | Simpan manual/autosave, simpan sebelum navigasi, URL/localStorage/history, dan shortcut keyboard |
| `hooks/documents/useCorrectionViewport.js` | Dimensi/orientasi citra, fit/zoom, pan, ResizeObserver, wheel, dan isolasi scroll |
| `hooks/documents/useCorpusEmbedding.js` | State konfirmasi/progres korpus, request embedding, dan pendaftaran tracker sesudah antrean berhasil |
| `hooks/documents/useDashboardDocuments.js` | Daftar/statistik/kategori, polling dokumen, upload, hapus, jeda/resume, serta lifecycle modal dashboard |
| `hooks/layout/useAdminLayout.js` | Navigasi/sidebar, menu pengguna, badge tiket, toast, animasi shell, dan komposisi hook layout |
| `hooks/layout/useAdminNotifications.js` | Pemetaan aktivitas dokumen/kategori/kanal, penggabungan riwayat lokal, unread, baca, serta hapus notifikasi lokal |
| `hooks/layout/useAdminSearch.js` | Pemuatan indeks, pemfilteran fitur/dokumen/kategori, serta lifecycle dropdown pencarian |
| `hooks/layout/useActiveEmbeddingPoller.js` | Polling tracker embedding dan event penyelesaian/kegagalan yang tetap aktif saat modal ditutup |
| `hooks/integrations/useIntegrations.js` | Tab URL, pemuatan gabungan, status, clipboard, snippet API, animasi header, dan komposisi workflow integrasi |
| `hooks/integrations/useIntegrationApiKeys.js` | API key, toggle/hapus, konfigurasi webhook, rotasi secret sekali tampil, dan riwayat pengiriman |
| `hooks/integrations/useIntegrationWhatsApp.js`, `useIntegrationTelegram.js` | Snapshot/dirty state kanal, simpan/batal, uji koneksi, serta registrasi webhook Telegram |
| `hooks/categories/useCategorySettings.js` | Daftar kategori/model/prompt bawaan, editor prompt/pelaksana, CRUD, ref imperatif, dan lifecycle modal kategori |
| `hooks/categories/useCategoryOcrTest.js` | Gambar sampel/FileReader/drag-drop, request uji OCR, hasil raw/final, durasi, serta clipboard hasil |
| `hooks/monitoring/useTelemetryMonitoring.js`, `useHardwareMonitoring.js` | Data/filter/pagination/tindakan telemetri serta diagnostik/refresh/visibility/metrik mesin |
| `hooks/settings/useWhatsappSettings.js` | Pengambilan kredensial, dirty state, simpan/batal, dan uji pengiriman WhatsApp |
| `hooks/settings/useChatbotSettings.js` | Konfigurasi chatbot/RAG, daftar dokumen, katalog model, diagnostik, benchmark, dan reset |
| `hooks/settings/useDirectorySettings.js` | State/filter direktori, pemetaan daftar tugas, validasi, CRUD, notifikasi dan scroll lock modal |
| `hooks/settings/useFastPathSettings.js` | State/filter kategori Fast Path, validasi, CRUD, notifikasi dan scroll lock modal |

Halaman dan komponen tetap memiliki JSX, teks, kelas/style, portal, serta callback presentasi inline yang sama. Hook controller memiliki state, ref DOM, handler, dan lifecycle yang sebelumnya berada sebelum JSX; hook domain memisahkan tanggung jawab independen. Pemisahan mempertahankan urutan hook/effect serta dependency array. Subscription sandbox tetap berada di `ChatbotSettingsPage` dan memakai `aiChatService` yang sama; melepas subscription halaman tidak menghentikan stream persisten.

### Perilaku yang dipertahankan

- Live chat mengambil antrean saat tab berubah dan menyegarkan antrean/pesan setiap **5 detik**. Perubahan teks pencarian diterapkan saat refresh manual atau polling berikutnya. Interval dibersihkan saat dependency berganti atau halaman ditutup.
- Respons pesan hanya diterapkan untuk tiket aktif dan permintaan pesan terbaru. Refresh antrean mempertahankan pilihan tiket terkini; respons status/balasan untuk tiket sebelumnya tidak mengganti percakapan aktif.
- Statistik yang gagal tidak menggagalkan pengambilan antrean. Statistik yang berhasil tetap memicu event browser `app-tickets-updated`, yang juga didengarkan layout untuk memperbarui badge/notifikasi.
- Pesan baru menggulir otomatis saat jarak dari bawah kurang dari **100px**. Saat petugas membaca riwayat di atas, viewport tetap di tempat dan badge unread bertambah. Jeda scroll awal/pesan baru tetap **50 ms**.
- Balasan berhasil mengosongkan teks/lampiran, mengambil ulang pesan, lalu menggulir ke bawah. Balasan gagal mempertahankan draft. Fokus dikembalikan setelah proses kirim selesai bila tiket yang sama masih dipilih dan belum `resolved`.
- Detail dokumen melakukan polling **4 detik** untuk status pemrosesan/antrean atau permintaan jeda. Kegagalan polling setelah data pernah termuat mempertahankan editor dan menjadwalkan retry; kegagalan pertama tetap menampilkan error halaman.
- Form pengaturan mempertahankan pemetaan nilai awal, dirty state, pesan notifikasi, dan waktu loading minimum **200 ms**. Masker token WhatsApp dikirim utuh sesuai kontrak backend. Data chatbot wajib berhasil dimuat; dokumen/model/hardware memiliki fallback masing-masing.
- Editor koreksi memakai autosave **1,8 detik**, polling halaman ekstraksi **3,5 detik**, status simpan yang memudar setelah **3 detik**, dan shortcut Ctrl/Cmd+S, Ctrl/Cmd+Enter, serta Alt+panah. Navigasi menyimpan draft sebelum berpindah dan memperbarui URL/localStorage. Callback reset viewport hanya memakai setter React yang stabil sehingga dependency navigasi serta urutan hook tetap mengikuti implementasi semula.
- Permintaan koreksi diurutkan agar autosave lambat tidak menimpa simpan terbaru. Gagal simpan membatalkan perpindahan dan mempertahankan draft, termasuk saat Back/Forward mengubah URL. Konfirmasi korpus menunggu koreksi tersimpan, termasuk request yang sudah berjalan; jika koreksi gagal, embedding tidak dikirim.
- Layout menyegarkan notifikasi/badge tiket setiap **10 detik** dan melalui event browser terkait. Tracker embedding dipantau setiap **2 detik**; kondisi selesai tetap `persen >= 100`, atau status selesai/completed dengan `persen >= 95` setelah **2,5 detik**. Toast tetap maksimal tiga dan memudar setelah **5,5 detik**.
- Dashboard memuat ulang setiap **10 detik** selama respons menyatakan `has_processing`, mempertahankan loading minimum **350 ms**, serta jeda tahap upload selesai **600 ms**. Monitoring hardware menyegarkan setiap **15 detik** ketika dokumen browser terlihat dan pada event visibility; indikator loading manual mempertahankan minimum **250 ms**.

### Pratinjau chunk editor koreksi

`ManualCorrectionEditor` memakai `useCorrectionEditor` untuk mengomposisikan state dan workflow editor. Hook tersebut memakai `useChunkPreview(documentId)` untuk request `documentsApi.getChunksPreview`, `useCorrectionPersistence` untuk simpan/navigasi, `useCorrectionViewport` untuk citra/zoom/pan, dan `useCorpusEmbedding` untuk antrean korpus. Komponen tetap memiliki JSX/modal portal dan callback presentasi inline. Hook pratinjau memiliki delapan state tanpa effect tambahan; urutan effect hasil komposisi tetap sama.

| Preset | Ukuran induk / overlap | Ukuran anak / overlap | Strategi |
| --- | --- | --- | --- |
| SOP & Prosedur | 1500 / 200 | 300 / 50 | `sop` |
| Deskriptif / Laporan | 2000 / 250 | 400 / 60 | `general` |
| Regulasi & Pasal | 1800 / 200 | 350 / 50 | `regulasi` |
| FAQ / Butir Singkat | 1000 / 150 | 200 / 40 | `faq` |

Ukuran dan overlap memakai jumlah karakter. Modal membuka pratinjau dengan parameter aktif; pemilihan preset langsung mengirim nilai preset yang dipilih. Slider mengubah strategi menjadi `custom`, dan tombol **Hitung Ulang** mengirim nilai aktif. Parameter request tetap `parent_chunk_size`, `parent_chunk_overlap`, `child_chunk_size`, `child_chunk_overlap`, serta `strategy`; override memakai operator `??` sehingga nilai 0 yang diberikan eksplisit tetap diteruskan.

Kegagalan request mempertahankan hasil pratinjau sebelumnya, menampilkan alert yang sama, dan mengakhiri status loading. Tombol simpan ke korpus memakai nilai parameter yang sama dari hook; `useCorpusEmbedding` mendaftarkan tracker sesudah backend berhasil membuat antrean. Event hasil background tetap dikonsumsi oleh orkestrator editor dan callback modal progres yang sama.

## Pemeriksaan perubahan

Verifier sumber yang dapat dijalankan dari checkout tersedia melalui
`npm run verify:ui`. Ia membandingkan JSX/aset dengan baseline Git serta
mengekspansi kedua hook form untuk menjaga urutan state/effect, validasi dan
payload. Skenario CLI `settings-crud.js` menguji kedua form pada backend
sementara. Perintah lengkap, pemilihan baseline, capture sebelum/sesudah dan
comparator screenshot ada di [panduan verifikasi](scripts/README.md).

Build memeriksa kompilasi dan resolusi modul. Untuk menilai tampilan, bandingkan halaman sebelum/sesudah pada ukuran layar, tema, route, dan data yang sama. Sertakan kondisi loading/kosong, pergantian tiket, pengiriman gagal, lampiran, posisi scroll, fokus input, simpan/batal pengaturan, serta sandbox SSE. Kesamaan JSX saja tidak menggantikan pemeriksaan browser.

Untuk pratinjau editor, periksa modal SOP/FAQ, tema terang/gelap, slider dengan keyboard, payload hitung ulang, dan hasil lama saat satu request gagal. Pemisahan `useChunkPreview` diperiksa dengan fixture browser sintetis pada viewport 1440×1000: editor utama, modal SOP, modal FAQ, dan modal FAQ gelap dibandingkan sebelum/sesudah; payload SOP/FAQ/kustom serta pemulihan setelah HTTP 503 juga diperiksa. Pemeriksaan ini melengkapi pengujian terhadap PDF nyata dan sesi admin aktif.

Pemisahan controller berikutnya memeriksa AST statement/payload, parameter, dependency array, urutan hook/effect setelah ekspansi hook, serta sumber JSX pada editor, layout, integrasi, kategori, monitoring, dan dashboard. Fixture browser sintetis membandingkan sembilan kondisi layar/tab pada viewport 1440×1000; teks, nilai/disabled kontrol, dan geometri kontrol identik. Tujuh screenshot identik piksel; dua lainnya memiliki perbedaan raster kecil pada tepi ikon/teks tanpa perubahan geometri. Interaksi editor mencakup autosave satu request, simpan sebelum perpindahan, pemulihan teks tersimpan, reset zoom saat navigasi, dan draft yang tetap tersedia setelah gagal simpan. Pemeriksaan ini tidak menjalankan layanan AI, pengiriman kanal, upload produksi, atau autentikasi admin nyata.

## Menjalankan dan membangun

Tahap browser dengan backend nyata menjalankan 20 pemeriksaan alur/kondisi,
termasuk unggah hingga embedding, pengaturan, respons tiket terlambat,
fokus/scroll, serta logout. Enam halaman dicapture pada dua tema dan tiga
viewport (36 screenshot). Empat perbaikan hook di atas tidak mengubah komponen,
JSX, CSS atau aset. Prasyarat, skenario, dan batas bukti ada di
[`../scripts/integration/browser/README.md`](../scripts/integration/browser/README.md)
dan [catatan verifikasi](../docs/09-status-refactor-dan-verifikasi.md).

```bash
npm install
npm run dev
npm run build
```

Vite berjalan di port `5173` dan mem-proxy permintaan `/api` ke Laravel. Atur host target di `vite.config.js` bila backend berjalan di alamat lain.

Panduan integrasi dan pemeliharaan lintas layanan ada di [`../docs/08-panduan-struktur-kode-dan-pemeliharaan.md`](../docs/08-panduan-struktur-kode-dan-pemeliharaan.md).
