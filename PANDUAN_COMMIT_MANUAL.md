# Pilihan commit manual SAPA

Panduan ini berdasarkan workspace yang diperiksa pada 26 Oktober 2026,
branch `feat/integration`. Belum ada perubahan yang di-stage saat pemeriksaan.
Tidak ada commit atau push yang dijalankan oleh asisten.

## Pilihan berkas

| Kelompok | Pilihan |
| --- | --- |
| Kode refactoring | Commit perubahan dan modul baru React, Laravel, Python; sertakan tes, migrasi, package/lock file, `.env.example`, verifier UI, dan runner integrasi |
| Dokumentasi teknis | Commit dokumentasi utama yang tersisa setelah konsolidasi, penghapusan dokumen duplikat yang sudah tracked, README aplikasi, dan panduan verifier |
| Materi penyerahan | README root, `SERAH_TERIMA.md` dan sumber LaTeX ikut commit dokumentasi; PPT/PDF dapat menjadi commit lampiran terpisah setelah identitas/versi diperiksa |
| Laporan akademik | Tunda seluruh `laporan-kkp/`; pilih sumber/laporan sendiri secara terpisah setelah review |
| Artefak lokal | Jangan ikutkan `.agents/`, `.playwright-cli/`, screenshot root, log, browser storage state, cache, dependency terpasang, atau output pengujian |
| Utilitas screenshot | Tunda `take_screenshot.cjs`, `take_screenshot.mjs`, dan `admin-frontend/scripts/capture-hd.js`; terpisah dari refactoring. Versi `.cjs` masih memakai path Windows pribadi |

Perintah di bawah memilih path tertentu. Hindari `git add .` dan `git add -A`
untuk kondisi workspace ini. Tidak perlu menghapus berkas lokal yang dikecualikan.
Seleksi kode saat pemeriksaan mencakup 225 berkas berubah/baru, ditambah aturan
ignore output Playwright. Berkas hasil ekstraksi kode wajib ikut: memilih hanya
berkas lama berstatus modified akan meninggalkan import/dependency yang hilang.

## Tinjau dump database sebelum push

`docker/mysql/init.sql` **sudah tracked dan ada pada HEAD**, meskipun tidak
muncul sebagai perubahan baru. Isinya berupa dump dengan INSERT ke `users`,
`app_settings`, dokumen, hasil ekstraksi, direktori, log, dan tabel lain.
Pemeriksaan menemukan alamat email dan hash password; nilai pengaturan perlu
ditinjau untuk memastikan tidak ada kredensial atau data yang tidak boleh dibagikan.

Periksa lokal tanpa menyalin nilai sensitif ke issue/chat. Dump ini perlu
diklasifikasikan sebelum menentukan kelayakan push ke tujuan repository.
Untuk instalasi baru, utamakan migrasi dan seeder dengan data sintetis setelah
memeriksa kebutuhan Docker yang sekarang memakai dump tersebut.

Menambahkan `.gitignore`, menghapus file pada commit baru, atau tidak memilihnya
dalam staging **tidak menghapus isi commit terdahulu**. Jika ditemukan rahasia,
ganti kredensial terkait dan rencanakan pembersihan riwayat bersama pemilik repo.
Jangan melakukan force-push atau rewrite history tanpa koordinasi.
Pemeriksaan ini bukan audit lengkap seluruh riwayat Git.

## Commit 1: kode, tes, migrasi dan alat verifikasi

Jalankan dari root repository. Gabungkan backend Python/Laravel karena perubahan
pipeline, pembatalan dan cleanup saling berhubungan. UI frontend tetap memakai
hasil refactoring yang telah diverifikasi sebelumnya.

```bash
git add -- \
  admin-frontend/src \
  admin-frontend/package.json \
  admin-frontend/package-lock.json \
  admin-frontend/scripts/verify-refactor-ui.cjs \
  laravel-admin/app \
  laravel-admin/bootstrap/app.php \
  laravel-admin/routes/api.php \
  laravel-admin/database/migrations \
  laravel-admin/tests \
  laravel-admin/scripts/integration \
  python-ai/app \
  python-ai/tests \
  python-ai/.env.example \
  scripts/integration \
  output/playwright/.gitignore

git diff --cached --stat
git diff --cached --name-only
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check
git diff --cached
```

Setelah isi staging selesai diperiksa:

```bash
git commit -m "refactor: rapikan modul aplikasi dan perkuat verifikasi pipeline"
```

Pastikan dua migrasi baru `2026_10_25_000001_add_document_operation_fences.php`
dan `2026_10_25_000002_create_document_vector_cleanups_table.php` ikut.
Commit ini tidak menjalankan migrasi pada server.

## Commit 2: dokumentasi teknis

```bash
git add -- \
  docs \
  README.md \
  SERAH_TERIMA.md \
  admin-frontend/README.md \
  admin-frontend/scripts/README.md \
  laravel-admin/README.md \
  python-ai/README.md \
  scripts/integration/browser/README.md \
  PANDUAN_COMMIT_MANUAL.md

git diff --cached --stat
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check
git diff --cached
git commit -m "docs: selaraskan arsitektur panduan dan hasil audit refactoring"
```

Pemilihan `docs` juga mencatat penghapusan dokumen duplikat yang sudah tracked;
glob berkas yang masih ada saja dapat melewatkan penghapusan tersebut. Folder
ini sekarang hanya memuat dokumen Markdown dan sumber LaTeX ringkasan.
README root dan `SERAH_TERIMA.md` ikut karena tautannya diperbarui saat
konsolidasi. Tautan PPT/PDF pada serah terima memerlukan lampiran pada commit
opsional berikut atau penyesuaian lokasi sebelum materi dibagikan melalui Git.

## Commit 3 opsional: lampiran penyerahan

Lengkapi nama pembimbing, tanggal, identitas dan versi kode terlebih dahulu.
PPT berukuran 49.541.148 byte, sekitar 47,2 MiB. Pilih apakah repository juga
menjadi tempat menyimpan materi presentasi. Jika hanya menyerahkan source code,
tunda kelompok ini dan bagikan materi sebagai lampiran terpisah; sesuaikan
tautan README/serah terima apabila lokasi materi dipindahkan.

Jika PPT dan ringkasan memang dipilih untuk masuk repository:

```bash
git add -- \
  "PPT DISKOMINFOTIK.pptx" \
  output/serah-terima/.gitignore

git add -f -- output/serah-terima/SAPA-Ringkasan-Pembimbing.pdf
git diff --cached --stat
git diff --cached --name-only
git commit -m "docs: tambahkan lampiran presentasi dan ringkasan SAPA"
```

`-f` sengaja hanya untuk satu PDF yang sudah diperiksa; folder output tetap
diabaikan. Jangan memakai `git add -f output/` karena dapat memasukkan cookie,
log, screenshot atau artefak lokal lain. PDF adalah hasil build; jika sumber
LaTeX diubah, bangun ulang sebelum memilih PDF tersebut.

## Berkas yang tetap dibiarkan lokal

- `.agents/` dan `.playwright-cli/`: catatan kerja agen dan snapshot browser.
- `output/`: hasil pengujian/build, kecuali dua `.gitignore` dan satu PDF yang
  secara eksplisit dipilih di atas.
- `login-macbook14.png`, `login_hd_macbook14.png`, `login_lightmode_macbook14.png`,
  `screenshot_dark_macbook14.png`, `screenshot_light_macbook14.png`.
- Tiga utilitas screenshot yang disebut pada tabel awal.
- Seluruh `laporan-kkp/` untuk commit kode: terdapat build LaTeX, identitas,
  logbook/draf, panduan, serta PDF laporan milik pihak lain. Pilih laporan
  mahasiswa sendiri secara terpisah; jangan ikutkan seluruh direktori.
- `.env`, token, database operasional, `node_modules/`, `vendor/`, virtualenv,
  dan cache. `.env.example` yang berisi placeholder tetap diperlukan.

Status untracked yang tersisa setelah commit merupakan hasil seleksi yang
disengaja; working tree tidak harus bersih agar commit pilihan dapat di-push.

## Pemeriksaan akhir dan push manual

```bash
git status --short
git log -3 --oneline
git show --stat --oneline HEAD
git remote -v
git branch -vv
```

Pastikan remote benar, hasil seleksi sesuai, dan temuan dump database di atas
sudah ditangani sesuai tujuan/akses repository. Push mengirim commit yang belum
ada di remote beserta riwayat yang diperlukan, bukan hanya staging terakhir.
Jika nama remote memang `origin` dan branch tetap `feat/integration`:

```bash
git push -u origin feat/integration
```

Pemeriksaan pemilihan berkas tidak menjalankan ulang suite aplikasi. Bukti
pengujian sebelumnya ada pada dokumentasi status, audit, dan penutupan.
Pada pemeriksaan ini, `git diff --check` biasa menandai CRLF sebagai whitespace;
pemeriksaan dengan `cr-at-eol` lulus. Tidak dilakukan normalisasi line ending
massal atau perubahan UI.
