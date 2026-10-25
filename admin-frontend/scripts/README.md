# Verifikasi refactoring frontend

Jalankan dari `admin-frontend` setelah `npm ci`:

```bash
npm run verify:ui
npm run verify:ui -- --report ../output/playwright/refactor-closure/source-verification.json
npm run build
```

`verify-refactor-ui.cjs` hanya membaca kode dan Git. Baseline bawaan adalah
`129834bddfde6cd9253b270553d9ac7e0283db05`, acuan yang digunakan pada audit
refactoring. Checkout harus menyediakan commit tersebut; pada clone dangkal,
sediakan riwayat yang diperlukan. Untuk acuan lain yang sudah ditinjau:

```bash
npm run verify:ui -- --baseline COMMIT_ACUAN
```

Pemeriksaan gagal dengan exit code nonzero jika:

- JSX berkas acuan berubah. Pemindahan badge tiket ditangani secara eksplisit:
  markup utama, empat label/status dan himpunan kelas CSS dicocokkan.
- Stylesheet/aset/HTML yang ada pada acuan berubah.
- Workflow Direktori atau Fast Path berubah setelah body hook diekspansi ke
  lokasi pemanggilan aslinya: initializer, urutan state/effect, dependency,
  handler, validasi, filter, dan payload dibandingkan sebagai AST.
- Controller form tidak lagi dipanggil atau binding yang dikembalikan berubah.

Verifier ini menjaga struktur sumber yang dicakup baseline. Ia tidak menilai
seluruh perilaku browser, variasi data, maupun semantik arbitrary JavaScript.
Perubahan UI yang memang diinginkan memerlukan review dan acuan baru; jangan
mengubah baseline hanya agar kegagalan pemeriksaan hilang.

## Pemeriksaan browser kedua form

Gunakan [layanan sementara](../../scripts/integration/browser/README.md) dan
Playwright CLI dengan Chromium yang sudah tersedia. Siapkan working directory
privat `output/playwright/refactor-closure/` dan konfigurasi CLI seperti panduan
browser. Tidak perlu snapshot dari `/tmp` atau dokumen operasional.

Dari root repository, jalankan environment pada terminal terpisah:

```bash
python-ai/venv/bin/python scripts/integration/start_browser_environment.py --timeout-seconds 21600
```

Gunakan URL `frontend_url` yang dicetak runner. Setelah membuka `/login`,
jalankan `scripts/integration/browser/login.js` melalui CLI. Ambil snapshot
setelah navigasi, lalu jalankan `settings-crud.js` dari halaman admin:

```bash
bash "$PWCLI" -s=refactor-closure snapshot
bash "$PWCLI" -s=refactor-closure run-code --filename="$REFACTOR_REPO_ROOT/scripts/integration/browser/settings-crud.js"
```

`PWCLI` menunjuk executable/wrapper Playwright CLI yang dipasang pada mesin,
dan `REFACTOR_REPO_ROOT` adalah path absolut checkout. Jalankan seluruh perintah
CLI dari direktori artefak yang sama. Panduan browser menyediakan contoh
konfigurasi dan akun sintetis; skenario menolak host nonlokal dan akun lain.

Skenario mengatur navigasi serta fixture sendiri. Kedua domain diperiksa untuk
loading GET tertunda, validasi lokal, portal/scroll lock, create gagal/retry,
edit/batal/persistensi, format field, toggle, pencarian, reload, delete
batal/gagal/retry, serta reset form baru. HTTP error tertentu diinjeksi browser;
request berhasil memakai Laravel/database nyata. Fixture yang dibuat dihapus
kembali. Sebagian assertion memeriksa backend melalui HTTP sesudah interaksi UI.

### Membandingkan perubahan berikutnya

Sebelum mengedit kode, navigasikan ke URL berikut dan jalankan skenario:

```text
FRONTEND_URL/settings/chatbot?tab=directories&verifyPhase=before
```

Setelah perubahan, lakukan reload penuh melalui navigasi ke URL berikut, lalu
jalankan skenario yang sama:

```text
FRONTEND_URL/settings/chatbot?tab=directories&verifyPhase=after
```

Mode `before` menyimpan label, nilai, checkbox, disabled state dan geometri
kontrol ke browser serta `settings-before-state.json`. Mode `after`
membandingkannya dan gagal bila berbeda. Gunakan profil browser yang sama;
jika sesi perlu dibuka ulang pada URL environment yang sama, konfigurasi `browser.contextOptions.storageState`
dapat menunjuk file state baseline tersebut. Berkas state memuat cookie sesi
sintetis: simpan dalam direktori artefak privat yang diabaikan Git. Mode tanpa
`verifyPhase` tetap menjalankan regresi standalone dengan prefix `current`.

Masing-masing mode menyimpan 24 screenshot: daftar/modal × dua domain × dua
tema × viewport 1440×1000, 1024×768, 390×844. Toast sementara ditutup lewat
kontrol UI sebelum capture; font ditunggu dan animasi/caret dinonaktifkan hanya
saat screenshot. CSS aplikasi tidak dimodifikasi oleh skenario.

Dari root repository, bandingkan pasangan screenshot menggunakan Pillow yang
sudah tercantum pada environment Python aplikasi:

```bash
python-ai/venv/bin/python scripts/integration/compare_settings_screenshots.py output/playwright/refactor-closure --report output/playwright/refactor-closure/pixel-comparison.json
```

Comparator gagal jika gambar hilang, ukurannya berubah, atau ada piksel RGB
yang berbeda. Selidiki overlay/animasi/raster lingkungan bila gagal; jangan
melonggarkan ambang secara otomatis. Perbandingan aktual harus memakai capture
kode sebelum dan sesudah, bukan menggandakan screenshot versi akhir.

Untuk menyelidiki variasi renderer, mode `current` dapat dijalankan lagi pada
kode yang sama; bandingkan dengan `--reference-prefix after --candidate-prefix current`.
Ini kontrol tambahan, bukan pengganti pembandingan sebelum/sesudah. Hasil
penutupan aktual dan selisih raster yang ditinjau dicatat pada
[laporan penutupan](../../docs/09-status-refactor-dan-verifikasi.md#audit-dan-penutupan-26-oktober).

Tutup sesi browser dan buat `stop_file` yang dicetak runner setelah selesai.
Laporan environment harus menyatakan `owned_processes_stopped: true`.
