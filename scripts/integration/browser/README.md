# Browser admin pada layanan sementara

Jalankan dari root repository dengan dependency frontend/backend terpasang,
Chromium lokal, serta prasyarat [runner integrasi](../README.md):

```bash
python-ai/venv/bin/python scripts/integration/start_browser_environment.py
```

Proses tetap hidup sampai `stop_file` dibuat, menerima SIGTERM/Ctrl+C, atau
timeout (bawaan 3600 detik; ubah melalui `--timeout-seconds`). Baris
`BROWSER_READY` dan `browser.json` dalam direktori run memuat URL frontend,
backend, PDF native, ID tiket dan lokasi stop file. Status `ready_for_browser`
atau `stopped` pada laporan layanan bukan hasil kelulusan skenario browser.

Profil membuat MySQL/Redis/Chroma baru, storage/cache Laravel baru, API,
worker dan Vite. `.env` operasional tidak diubah. Ollama/model lokal tetap
dipakai bersama. Akun `browser@example.test` dengan password
`Browser-Synthetic-Only-2026!` hanya ada pada fixture sementara. Dua tiket
web memiliki ringkasan **Riwayat panjang sintetis** dan **Percakapan kedua
sintetis**, tanpa API key, WhatsApp, Telegram atau webhook eksternal.

## Menjalankan skenario CLI

Setiap berkas JS adalah fungsi `async (page) => ...` untuk Playwright CLI
`run-code --filename`; tidak memerlukan runner `@playwright/test`. Siapkan
direktori privat `output/playwright/browser-integration/` sebagai working
directory seluruh perintah CLI. Berikan konfigurasi CLI yang memilih executable
Chromium yang sudah tersedia, browser headless dan viewport 1440×1000.

```bash
bash /home/nftxvn/.codex/skills/playwright/scripts/playwright_cli.sh -s=refactor-browser open URL_FRONTEND/login --config=cli.config.json
bash /home/nftxvn/.codex/skills/playwright/scripts/playwright_cli.sh -s=refactor-browser snapshot
bash /home/nftxvn/.codex/skills/playwright/scripts/playwright_cli.sh -s=refactor-browser run-code --filename=/home/nftxvn/agentic-ai/scripts/integration/browser/login.js
```

Ganti URL/path sesuai lingkungan. Login, unggah PDF dari `native_pdf` melalui
dashboard, tunggu **Verifikasi**, lalu buka editor. Skenario memiliki prasyarat
halaman berikut; navigasikan melalui UI dan ambil snapshot sebelum tiap
kelompok. Jangan menjalankannya terhadap data operasional.

| Skenario | Prasyarat dan pemeriksaan |
| --- | --- |
| `login.js` | Form login; autentikasi nyata ke dashboard |
| `editor-autosave.js` | Editor halaman 1; satu autosave, format dan fokus |
| `editor-save-failure.js` | Editor halaman 1; PUT gagal, draft/halaman dipertahankan |
| `editor-navigation.js` | Langsung setelah skenario gagal di atas; retry, Prev/Next, Back, Ctrl+S |
| `editor-save-order.js` | Editor dua halaman, salah satu halaman; tunda PUT lama, periksa simpan terbaru |
| `editor-corpus-flush.js` | Editor siap korpus; periksa koreksi nyata pada saat dispatch, lalu hentikan POST embed dengan 503 sintetis |
| `editor-corpus-save-failure.js` | Editor siap korpus; PUT gagal harus memblokir POST embed, lalu retry simpan |
| `editor-viewports.js` | Editor dua halaman; zoom/reset navigasi, enam screenshot tema/viewport, preview nyata |
| `editor-real-corpus.js` | Editor siap korpus; konfirmasi nyata hingga worker selesai dan Chroma memuat penanda terbaru |
| `settings-loading.js` | Halaman admin; buka konfigurasi dengan GET nyata tertunda dan periksa skeleton |
| `settings-save.js` | Pengaturan tab Identitas; gagal simpan mempertahankan form, retry benar-benar persisten |
| `settings-crud.js` | Akun fixture; otomatis memeriksa CRUD Direktori/Fast Path, loading/error, portal/scroll, format, filter dan reset, serta capture tema/viewport |
| `live-chat-stale-response.js` | Live chat; respons tiket lama tertunda tidak mengganti pilihan baru |
| `live-chat-queue-selection.js` | Live chat tiket kedua; refresh antrean tertunda mempertahankan pilihan baru |
| `live-chat-scroll-focus.js` | Live chat; riwayat panjang, polling/pesan sintetis nyata, unread/jump, balasan gagal/retry/fokus |
| `live-chat-status-selection.js` | Live chat; PATCH status tertunda tidak mengubah tiket kedua, lalu pulihkan status pertama |
| `viewports-themes.js` | Halaman admin; lima halaman × dua tema × tiga viewport, navigasi mobile |
| `logout.js` | Akun terautentikasi, menu akun tertutup; logout nyata dan halaman privat kembali ke login |

Skenario tertentu mengubah data sintetis. Ini kumpulan skenario dengan
prasyarat, bukan satu runner yang mengatur seluruh perjalanan secara otomatis.
Periksa hasil assertion setiap perintah. `editor-autosave.js` mencatat hasil
melalui console; skenario lain mengembalikan objek atau melempar error. Pada
pengembangan hook, lakukan reload penuh setelah jumlah hook berubah agar
Fast Refresh tidak mempertahankan urutan state lama.

Setelah selesai, tutup sesi CLI (`-s=refactor-browser close`) lalu buat file
yang disebut `stop_file`, atau Ctrl+C proses environment. `report.json` layanan
harus menunjukkan `owned_processes_stopped: true`. Penghentian hanya menyasar
process group milik run; data/log sementara dipertahankan untuk inspeksi.

## Hasil dan batas bukti

Run 25 Oktober 2026 memverifikasi **20 alur/kondisi**, dengan **36 screenshot**
utama pada tema terang/gelap dan viewport 1440×1000, 1024×768, 390×844. Keenam
halaman: dashboard, editor, pengaturan, integrasi, monitoring, live chat.
Tidak ditemukan overflow horizontal halaman; ini bukan bukti seluruh kontrol
nyaman pada perangkat fisik. Screenshot adalah kondisi akhir, bukan diff piksel
otomatis. Snapshot 82 berkas sumber menunjukkan perubahan hanya pada empat
hook; komponen/JSX/CSS/aset tetap sama.

Login/upload/penyimpanan/retry/polling/embedding/logout memakai backend nyata.
Kegagalan 500/503 dan penundaan respons tertentu disisipkan di browser. Dalam
uji flush korpus, alert 503 sintetis sementara disenyapkan agar assertion dapat
selesai; uji `editor-real-corpus.js` terpisah menjalankan embedding sebenarnya.
Kegagalan jaringan total, browser lain, lampiran, CRUD kategori, mutasi integrasi,
sandbox SSE serta pengiriman kanal eksternal belum dicakup tahap ini.

Artefak lokal di `output/playwright/browser-integration/` diabaikan Git.
Ringkasan hasil ada di [catatan verifikasi](../../../docs/13-status-refactor-dan-verifikasi.md).

Penutupan form memakai working directory `output/playwright/refactor-closure/`.
Skenario `settings-crud.js` dapat dijalankan standalone; mode URL
`verifyPhase=before|after` menambahkan perbandingan geometri kontrol. Verifier
sumber dan prosedur pembandingan 24 pasangan screenshot dijelaskan di
[panduan verifikasi frontend](../../../admin-frontend/scripts/README.md).
