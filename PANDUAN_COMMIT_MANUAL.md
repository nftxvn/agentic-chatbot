# Commit dan sinkronisasi branch secara manual

Pemeriksaan 26 Oktober 2026 dilakukan pada branch `main`. Refactoring dan
pembaruan dokumentasi telah masuk ke `main`; panduan ini memilih perubahan
pembersihan repository berikutnya. Commit dan push dijalankan oleh pengguna.

## Status branch sebelum pembersihan

- `main`: `540da01`, merge hasil refactoring SAPA.
- `feat/integration`: `9455ac1`, sudah menjadi ancestor `main`.
- Isi berkas kedua branch identik sebelum pembersihan. Lima commit tambahan
  pada riwayat `main` mencakup merge/revert/reapply; bukan lima perubahan kode
  yang belum masuk ke feature branch.
- Pembersihan dibuat pada working tree `main`; branch lain mendapatkannya
  setelah commit dan sinkronisasi yang dipilih pengguna.

## Isi perubahan pembersihan

| Bagian | Perlakuan |
| --- | --- |
| Dokumen root lama tentang rencana helpdesk dan suite E2E yang tidak tersedia | Dihapus; referensi aktif ada pada docs bernomor, README aplikasi dan runner integrasi |
| Ikon duplikat dan screenshot lepas di root | Dihapus; ikon/aset yang dipakai aplikasi dipertahankan |
| Skrip capture lama, snapshot browser lama dan file perantara LaTeX | Dihapus setelah disalin ke backup lokal sementara |
| Folder output, catatan kerja agen dan materi akademik lokal | Diabaikan Git; PDF laporan, sumber akademik dan bukti pengujian tetap disimpan lokal |
| README, serah terima dan aturan ignore | Diperbarui agar sesuai struktur repository dan lampiran yang tersedia |

## Meninjau dan membuat commit

Dari root repository, pastikan branch masih `main` dan periksa perubahan:

```bash
git branch --show-current
git status --short
git diff --stat
```

Stage hanya berkas tracked yang berubah/dihapus pada pembersihan ini:

```bash
git add -u -- \
  .gitignore \
  README.md \
  SERAH_TERIMA.md \
  PANDUAN_COMMIT_MANUAL.md \
  PROJECT.md \
  TEST_INFRA.md \
  TEST_READY.md \
  "Screenshot 2026-10-02 094139.png" \
  sapa-icon-512.svg \
  output/playwright/.gitignore

git diff --cached --name-status
git diff --cached --stat
git -c core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol diff --cached --check
git diff --cached
```

`-u` mencatat perubahan dan penghapusan berkas tracked. Berkas lokal yang belum
pernah dilacak Git tidak memerlukan commit penghapusan. Setelah hasil staging
diperiksa, buat commit dan push manual:

```bash
git commit -m "chore: bersihkan artefak lokal dan dokumentasi lama"
git push origin main
```

Jika push ditolak karena remote berubah, periksa riwayat terbaru terlebih
dahulu; jangan memakai force-push untuk melewati penolakan tersebut.

## Menyelaraskan feat/integration bila masih dipakai

Setelah commit pembersihan dibuat pada `main`, feature branch dapat mengikuti
`main` dengan fast-forward. Ini opsional bila pengembangan selanjutnya memakai
branch baru.

```bash
git switch feat/integration
git merge --ff-only main
git push origin feat/integration
git switch main
```

Jika fast-forward ditolak, ada riwayat baru yang perlu diperiksa. Jangan reset
branch untuk memaksakan sinkronisasi.

## Materi penyerahan dan data aplikasi

Pilih laporan milik mahasiswa sendiri dari `laporan-kkp/`; folder ini juga
memuat referensi pihak lain. PPT acuan saat pemeriksaan tidak tersedia pada
checkout. PDF ringkasan dapat dibangun dari sumber pada `docs/` menggunakan
[panduan serah terima](SERAH_TERIMA.md), lalu dibagikan sebagai lampiran.
Jangan memakai `git add -f output/` untuk memasukkan seluruh folder artefak.

`docker/mysql/init.sql` tetap dipertahankan karena Docker Compose masih
memakainya. Dump tersebut sudah tracked, berisi data pengguna/dokumen dan
pengaturan, sehingga perlu review data sebelum repository dibagikan lebih
luas. Mengabaikan atau menghapusnya pada commit baru tidak menghapus isi
riwayat. Penggantian dengan bootstrap sintetis perlu perubahan Docker yang
terkoordinasi, terpisah dari pembersihan ini.

Konfigurasi `.env`, token, storage operasional, database/vektor, lock file,
migrasi, dependency dan seluruh source aplikasi dipertahankan. Bukti pengujian
serta cara menjalankannya tersedia pada dokumentasi status dan README aplikasi.
