# Hasil ekstraksi dokumen #1 — 2026-08-20 15:22

## Cara mengoreksi

1. Sunting **hanya** isi blok ```` ```text ```` di bawah judul `KOREKSI halaman N`. Blok `OCR asli` biarkan apa adanya — ia rujukan.
2. Jangan mengubah baris judul `### KOREKSI halaman N`; baris itu yang dipakai untuk menemukan potongan Anda saat dibaca kembali.
3. Setelah selesai, jalankan:

       python ingest_dokumen.py --id 1 --pakai-koreksi

   Teks di blok KOREKSI itulah yang dipotong jadi induk/anak lalu di-embed. Blok yang tidak Anda sentuh tetap terpakai apa adanya.

| | Nilai |
|---|---|
| Berkas sumber | `data\ekstraksi_1.json (ekstraksi tersimpan, tanpa OCR ulang)` |
| Halaman | **10** |
| Total karakter | 16.413 |
| Status | **belum masuk korpus** — masih bisa dikoreksi |


## Ringkasan

| Hal | Karakter | Item | Jalur chunking | Konteks |
|---:|---:|---:|---|---|
| 1 | 193 | 0 | entri prosedur / splitter | KEPUTUSAN WALIKOTA BANDA ACEH |
| 2 | 1371 | 5 | entri prosedur / splitter | Mengingat |
| 3 | 1524 | 10 | daftar utuh | Mengingat |
| 4 | 1387 | 28 | daftar utuh | KEDUA |
| 5 | 1443 | 28 | daftar utuh | KEDUA |
| 6 | 944 | 15 | daftar utuh | KEDUA |
| 7 | 2425 | 24 | daftar utuh | SOP PENYUSUNAN RENCANA STRATEGIS (RENSTRA) DISKOMINFO |
| 8 | 2505 | 59 | daftar utuh | SOP PENYUSUNAN RENCANA STRATEGIS (RENSTRA) DISKOMINFO |
| 9 | 2295 | 25 | daftar utuh | SOP PENYUSUNAN RENCANA KERJA (RENJA) DISKOMINFOTIK |
| 10 | 2326 | 59 | daftar utuh | SOP PENYUSUNAN RENCANA KERJA (RENJA) DISKOMINFOTIK |


---

## Halaman 1

- Konteks: **KEPUTUSAN WALIKOTA BANDA ACEH**
- 193 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
KEPUTUSAN WALIKOTA BANDA ACEH
NOMOR 395 TAHUN 2025

TENTANG

STANDAR OPERASIONAL PROSEDUR PADA
DINAS KOMUNIKASI, INFORMATIKA DAN
STATISTIK KOTA BANDA ACEH

PEMERINTAH KOTA BANDA ACEH
TAHUN 2025
```
</details>

### KOREKSI halaman 1

```text
KEPUTUSAN WALIKOTA BANDA ACEH
NOMOR 395 TAHUN 2025

TENTANG

STANDAR OPERASIONAL PROSEDUR PADA
DINAS KOMUNIKASI, INFORMATIKA DAN
STATISTIK KOTA BANDA ACEH

PEMERINTAH KOTA BANDA ACEH
TAHUN 2025
```

---

## Halaman 2

- Konteks: **Mengingat**
- 1371 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
WALI KOTA BANDA ACEH
KEPUTUSAN WALIKOTA BANDA ACEH
NOMOR 305 TAHUN 2025
TENTANG
STANDAR OPERASIONAL PROSEDUR
PADA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK KOTA BANDA ACEH
DENGAN RAHMAT ALLAH YANG MAHA KUASA
WALIKOTA BANDA ACEH,

Menimbang : bahwa untuk melaksanakan ketentuan Pasal 13 Peraturan Menteri Dalam Negeri Nomor 52 Tahun 2011 tentang Standar Operasional Prosedur di Lingkungan Pemerintah Provinsi dan Kabupaten/Kota, perlu menetapkan Keputusan Walikota tentang Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;

Mengingat : 1. Undang-Undang Nomor 11 Tahun 2006 tentang Pemerintahan Aceh
2. Undang-Undang Nomor 14 Tahun 2008 tentang Keterbukaan Informasi Publik;
3. Undang-Undang Nomor 25 Tahun 2009 tentang Pelayanan Publik;
4. Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah sebagaimana telah beberapa kali diubah terakhir dengan Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-undang;
5. Undang-Undang Nomor 5 Tahun 2024 tentang Kota Banda Aceh di Aceh;
6. Peraturan Pemerintah Nomor 5 Tahun 1983 tentang Perubahan Batas Wilayah Kotamadya Daerah Tingkat II Banda Aceh;

Jalan. Tgk. Abu Lam U, Nomor 7 Banda Aceh
Telepon (0651) 21855 Faximile (0651) 31980 E-mail : - Website : bandaacehkota.go.id
```
</details>

### KOREKSI halaman 2

```text
WALI KOTA BANDA ACEH
KEPUTUSAN WALIKOTA BANDA ACEH
NOMOR 305 TAHUN 2025
TENTANG
STANDAR OPERASIONAL PROSEDUR
PADA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK KOTA BANDA ACEH
DENGAN RAHMAT ALLAH YANG MAHA KUASA
WALIKOTA BANDA ACEH,

Menimbang : bahwa untuk melaksanakan ketentuan Pasal 13 Peraturan Menteri Dalam Negeri Nomor 52 Tahun 2011 tentang Standar Operasional Prosedur di Lingkungan Pemerintah Provinsi dan Kabupaten/Kota, perlu menetapkan Keputusan Walikota tentang Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;

Mengingat : 1. Undang-Undang Nomor 11 Tahun 2006 tentang Pemerintahan Aceh
2. Undang-Undang Nomor 14 Tahun 2008 tentang Keterbukaan Informasi Publik;
3. Undang-Undang Nomor 25 Tahun 2009 tentang Pelayanan Publik;
4. Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah sebagaimana telah beberapa kali diubah terakhir dengan Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-undang;
5. Undang-Undang Nomor 5 Tahun 2024 tentang Kota Banda Aceh di Aceh;
6. Peraturan Pemerintah Nomor 5 Tahun 1983 tentang Perubahan Batas Wilayah Kotamadya Daerah Tingkat II Banda Aceh;

Jalan. Tgk. Abu Lam U, Nomor 7 Banda Aceh
Telepon (0651) 21855 Faximile (0651) 31980 E-mail : - Website : bandaacehkota.go.id
```

---

## Halaman 3

- Konteks: **Mengingat**
- 1524 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
7. Peraturan Menteri Dalam Negeri Nomor 52 Tahun 2011 tentang Standar Operasional Prosedur di Lingkungan Pemerintah Provinsi dan Kabupaten/Kota;
8. Peraturan Menteri Pemberdayaan Aparatur Negara Nomor 35 Tahun 2012 tentang Pedoman Penyusunan Standar Operasional Administrasi Pemerintahan;
9. Peraturan Pemerintah Nomor 96 Tahun 2012 tentang Pelaksanaan Undang-Undang Nomor 25 Tahun 2009 tentang Pelayanan Publik;
10. Peraturan Menteri Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 62 Tahun 2018 tentang Pedoman Sistem Pengaduan Pelayanan Publik Nasional;
11. Peraturan Menteri Komunikasi dan Informatika Nomor 4 Tahun 2024 tentang Penyelenggaraan Urusan Pemerintahan Konkuren Bidang Komunikasi dan Informatika;
12. Qanun Kota Banda Aceh Nomor 11 Tahun 2016 tentang Pembentukan dan Susunan Perangkat Daerah Kota Banda Aceh;
13. Peraturan Walikota Banda Aceh Nomor 54 Tahun 2016 tentang Susunan, Kedudukan, Tugas, Fungsi, Kewenangan dan Tata Kerja Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh.

MEMUTUSKAN :

Menetapkan :
KESATU : Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh sebagaimana tercantum dalam Lampiran Keputusan ini.
KEDUA : Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh sebagaimana dimaksud dalam Diktum Kesatu terdiri dari:
a. Penyusunan Rencana Strategis (Renstra);
b. Penyusunan Rencana Kerja (Renja);
c. Penyusunan Rencana Kegiatan Anggaran (RKA) dan Dokumen Pelaksana Anggaran (DPA);
```
</details>

### KOREKSI halaman 3

```text
7. Peraturan Menteri Dalam Negeri Nomor 52 Tahun 2011 tentang Standar Operasional Prosedur di Lingkungan Pemerintah Provinsi dan Kabupaten/Kota;
8. Peraturan Menteri Pemberdayaan Aparatur Negara Nomor 35 Tahun 2012 tentang Pedoman Penyusunan Standar Operasional Administrasi Pemerintahan;
9. Peraturan Pemerintah Nomor 96 Tahun 2012 tentang Pelaksanaan Undang-Undang Nomor 25 Tahun 2009 tentang Pelayanan Publik;
10. Peraturan Menteri Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 62 Tahun 2018 tentang Pedoman Sistem Pengaduan Pelayanan Publik Nasional;
11. Peraturan Menteri Komunikasi dan Informatika Nomor 4 Tahun 2024 tentang Penyelenggaraan Urusan Pemerintahan Konkuren Bidang Komunikasi dan Informatika;
12. Qanun Kota Banda Aceh Nomor 11 Tahun 2016 tentang Pembentukan dan Susunan Perangkat Daerah Kota Banda Aceh;
13. Peraturan Walikota Banda Aceh Nomor 54 Tahun 2016 tentang Susunan, Kedudukan, Tugas, Fungsi, Kewenangan dan Tata Kerja Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh.

MEMUTUSKAN :

Menetapkan :
KESATU : Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh sebagaimana tercantum dalam Lampiran Keputusan ini.
KEDUA : Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh sebagaimana dimaksud dalam Diktum Kesatu terdiri dari:
a. Penyusunan Rencana Strategis (Renstra);
b. Penyusunan Rencana Kerja (Renja);
c. Penyusunan Rencana Kegiatan Anggaran (RKA) dan Dokumen Pelaksana Anggaran (DPA);
```

---

## Halaman 4

- Konteks: **KEDUA**
- 1387 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
d. Prosedur Pengumpulan Data dan Evaluasi Kinerja Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;
e. Penyusunan Laporan Kinerja Instansi Pemerintah (LKJiP) Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;
f. Penyiapan dan Kompilasi Data Capaian Kinerja Penyelenggaraan Pemerintah Daerah;
g. Penyusunan Perjanjian Kinerja (PK);
h. Penanganan Pengaduan Secara Langsung;
i. Penanganan Pengaduan Secara Tidak Langsung;
j. Survei Kepuasan Masyarakat (SKM);
k. Penyusunan Dokumen Sistem Pengendalian Intern Pemerintah (SPIP);
l. Penyusunan Rencana Tindak Pengendalian (RTP);
m. Penyusunan Penilaian Mandiri Pelaksanaan Reformasi Birokrasi (PMPRB);
n. Penyusunan Standar Pelayanan;
o. Penyusunan Standar Operasional Prosedur Administrasi Pemerintah (SOP-AP);
p. Penyusunan Indikator Kinerja Utama (IKU);
q. Pengukuran Kinerja;
r. Pelayanan Konsultasi;
s. Pengajuan SPP LS;
t. Pertanggungjawaban Penggunaan Uang Persediaan (UP)/ Ganti Uang Persediaan (GU-P);
u. Pertanggungjawaban Penggunaan Tambah Uang (TU-P);
v. Penyusunan SPJ Fungsional dan Administratif;
w. Penyusunan Laporan Keuangan SKPD;
x. Penyusunan Laporan Keuangan Semesteran;
y. Prosedur Penerbitan SPM (UP, GU dan TU);
z. Pelaksanaan Perjalanan Dinas;
aa. Pengelolaan Arsip;
bb. Pengelolaan Surat Masuk;
cc. Pengelolaan Surat Keluar;
dd. Pengajuan Cuti Pegawai;
ee. Pengajuan Usulan Kenaikan Gaji Berkala;
```
</details>

### KOREKSI halaman 4

```text
d. Prosedur Pengumpulan Data dan Evaluasi Kinerja Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;
e. Penyusunan Laporan Kinerja Instansi Pemerintah (LKJiP) Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;
f. Penyiapan dan Kompilasi Data Capaian Kinerja Penyelenggaraan Pemerintah Daerah;
g. Penyusunan Perjanjian Kinerja (PK);
h. Penanganan Pengaduan Secara Langsung;
i. Penanganan Pengaduan Secara Tidak Langsung;
j. Survei Kepuasan Masyarakat (SKM);
k. Penyusunan Dokumen Sistem Pengendalian Intern Pemerintah (SPIP);
l. Penyusunan Rencana Tindak Pengendalian (RTP);
m. Penyusunan Penilaian Mandiri Pelaksanaan Reformasi Birokrasi (PMPRB);
n. Penyusunan Standar Pelayanan;
o. Penyusunan Standar Operasional Prosedur Administrasi Pemerintah (SOP-AP);
p. Penyusunan Indikator Kinerja Utama (IKU);
q. Pengukuran Kinerja;
r. Pelayanan Konsultasi;
s. Pengajuan SPP LS;
t. Pertanggungjawaban Penggunaan Uang Persediaan (UP)/ Ganti Uang Persediaan (GU-P);
u. Pertanggungjawaban Penggunaan Tambah Uang (TU-P);
v. Penyusunan SPJ Fungsional dan Administratif;
w. Penyusunan Laporan Keuangan SKPD;
x. Penyusunan Laporan Keuangan Semesteran;
y. Prosedur Penerbitan SPM (UP, GU dan TU);
z. Pelaksanaan Perjalanan Dinas;
aa. Pengelolaan Arsip;
bb. Pengelolaan Surat Masuk;
cc. Pengelolaan Surat Keluar;
dd. Pengajuan Cuti Pegawai;
ee. Pengajuan Usulan Kenaikan Gaji Berkala;
```

---

## Halaman 5

- Konteks: **KEDUA**
- 1443 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
ff. Pengajuan Usulan Kenaikan Pangkat;
gg. Pelayanan Administrasi Penyusunan Pelaporan Aset Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh
hh. Penyusunan Rencana Kebutuhan Milik Daerah (RKBMD) dan Rencana Kebutuhan Pemeliharaan laporan aset Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;
ii. Penghapusan Barang Milik Daerah dari daftar Barang Pengguna Barang;
jj. Layanan Permohonan Akun;
kk. Layanan Gangguan;
ll. Layanan Perencanaan/Pengembangan Aplikasi;
mm. Layanan Pembangunan Aplikasi;
nn. Layanan Penghapusan Aplikasi;
oo. Layanan Hosting;
pp. Layanan Subdomain
qq. Layanan Colocation;
rr. Layanan Aplikasi e-Government;
ss. Layanan Pengujian Aplikasi;
tt. Layanan Pembangunan/Pengembangan API (application programming interface);
uu. Layanan Cloud Storage;
vv. Layanan Aset TIK (teknologi informasi dan komunikasi);
ww. Layanan VPN (virtual private network);
xx. Layanan Integrasi API (aplication programming interface);
yy. Layanan Publikasi Aplikasi ke Playstore;
zz. Layanan Pembuatan Tandatangan Elektronik;
aaa. Layanan Penghapusan Tanda tangan Elektronik;
bbb. Layanan Perpanjangan Tanda tangan Elektronik;
ccc. Pelaporan Insiden Keamanan TIK oleh Masyarakat;
ddd. Pelaporan Insiden Keamanan TIK oleh OPD;
eee. Penanganan Insiden Siber pada Aplikasi Pusat Data;
fff. Layanan Permohonan WEB Gampong;
ggg. Pelaksanaan Siaran Keliling menggunakan Mobil Pusat Teknologi Informasi dan Komunitas (M-Pustika);
```
</details>

### KOREKSI halaman 5

```text
ff. Pengajuan Usulan Kenaikan Pangkat;
gg. Pelayanan Administrasi Penyusunan Pelaporan Aset Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh
hh. Penyusunan Rencana Kebutuhan Milik Daerah (RKBMD) dan Rencana Kebutuhan Pemeliharaan laporan aset Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh;
ii. Penghapusan Barang Milik Daerah dari daftar Barang Pengguna Barang;
jj. Layanan Permohonan Akun;
kk. Layanan Gangguan;
ll. Layanan Perencanaan/Pengembangan Aplikasi;
mm. Layanan Pembangunan Aplikasi;
nn. Layanan Penghapusan Aplikasi;
oo. Layanan Hosting;
pp. Layanan Subdomain
qq. Layanan Colocation;
rr. Layanan Aplikasi e-Government;
ss. Layanan Pengujian Aplikasi;
tt. Layanan Pembangunan/Pengembangan API (application programming interface);
uu. Layanan Cloud Storage;
vv. Layanan Aset TIK (teknologi informasi dan komunikasi);
ww. Layanan VPN (virtual private network);
xx. Layanan Integrasi API (aplication programming interface);
yy. Layanan Publikasi Aplikasi ke Playstore;
zz. Layanan Pembuatan Tandatangan Elektronik;
aaa. Layanan Penghapusan Tanda tangan Elektronik;
bbb. Layanan Perpanjangan Tanda tangan Elektronik;
ccc. Pelaporan Insiden Keamanan TIK oleh Masyarakat;
ddd. Pelaporan Insiden Keamanan TIK oleh OPD;
eee. Penanganan Insiden Siber pada Aplikasi Pusat Data;
fff. Layanan Permohonan WEB Gampong;
ggg. Pelaksanaan Siaran Keliling menggunakan Mobil Pusat Teknologi Informasi dan Komunitas (M-Pustika);
```

---

## Halaman 6

- Konteks: **KEDUA**
- 944 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
hhh. Peliputan Publikasi Berita OPD;
iii. Diseminasi layanan Informasi Melalui Media Sosial;
jjj. Pelaksanaan Kegiatan Podcast;
kkk. Diseminasi Informasi melalui Media Luar Ruang;
lll. Kunjungan Banda Aceh Command Centre;
mmm. Permintaan Rekaman CCTV;
nnn. Tinjauan Lapangan Smart City;
ooo. Monitoring dan Evaluasi Smart City;
ppp. Pengumpulan Data Statistik Sektoral;
qqq. Pengumpulan Data dari survey (D/K/LI)
rrr. Pengolahan Data Sektoral;
sss. Diseminasi Data Sektoral ke Sosial Media;
ttt. Diseminasi Data Sektoral ke Porta Satu Data;
uuu. Diseminasi Melalui Buku Publikasi Statistik dan
vvv. Layanan Permintaan Data Sektoral.

KETIGA : Keputusan Walikota ini berlaku pada tanggal ditetapkan, apabila di kemudian hari ternyata terdapat kekeliruan dalam penetapan ini, akan diperbaiki kembali sebagaimana mestinya.

Ditetapkan di Banda Aceh
pada tanggal 26 Agustus 2025 M
2 Rabuul Awal 1447 H
WALI KOTA BANDA ACEH,
ILLIZA SA'ADUDDIN DJAMAL
```
</details>

### KOREKSI halaman 6

```text
hhh. Peliputan Publikasi Berita OPD;
iii. Diseminasi layanan Informasi Melalui Media Sosial;
jjj. Pelaksanaan Kegiatan Podcast;
kkk. Diseminasi Informasi melalui Media Luar Ruang;
lll. Kunjungan Banda Aceh Command Centre;
mmm. Permintaan Rekaman CCTV;
nnn. Tinjauan Lapangan Smart City;
ooo. Monitoring dan Evaluasi Smart City;
ppp. Pengumpulan Data Statistik Sektoral;
qqq. Pengumpulan Data dari survey (D/K/LI)
rrr. Pengolahan Data Sektoral;
sss. Diseminasi Data Sektoral ke Sosial Media;
ttt. Diseminasi Data Sektoral ke Porta Satu Data;
uuu. Diseminasi Melalui Buku Publikasi Statistik dan
vvv. Layanan Permintaan Data Sektoral.

KETIGA : Keputusan Walikota ini berlaku pada tanggal ditetapkan, apabila di kemudian hari ternyata terdapat kekeliruan dalam penetapan ini, akan diperbaiki kembali sebagaimana mestinya.

Ditetapkan di Banda Aceh
pada tanggal 26 Agustus 2025 M
2 Rabuul Awal 1447 H
WALI KOTA BANDA ACEH,
ILLIZA SA'ADUDDIN DJAMAL
```

---

## Halaman 7

- Konteks: **SOP PENYUSUNAN RENCANA STRATEGIS (RENSTRA) DISKOMINFO**
- 2425 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
Lampiran: Keputusan Wali Kota Banda Aceh
Nomor: 395
Tanggal: 26 Agustus 2025 M
2 Rabuul Awal 1447 H

NOMOR SOP: 9 / DISKOMINFOTIK / 2025
TANGGAL PEMBUATAN: 5 FEBRUARI 2025
TANGGAL REVISI: -
TANGGAL PENGESAHAN: 26 Agustus 2026

KEPALA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK
KOTA BANDA ACEH
SUB BAGIAN PROGRAM DAN PELAPORAN

KEPALA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK
KOTA BANDA ACEH
ALIZAR, S.Ag.Hum
PEMBINA UTAMA MUDA
NIP. 196911172001121002

NAMA SOP: PENYUSUNAN RENCANA STRATEGIS (RENSTRA) DISKOMINFO

Dasar Hukum:
1. Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara;
2. Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara;
3. Undang-Undang Nomor 25 Tahun 2004 tentang Sistem Perencanaan Pembangunan Nasional;
4. Undang-Undang Nomor 15 Tahun 2004 tentang Pemeriksaan dan Pertanggungjawaban Keuangan Negara;
5. Peraturan Presiden Nomor 12 Tahun 2021 tentang Perubahan atas Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintahan;
6. Peraturan Menteri Dalam Negeri Nomor 77 Tahun 2020 tentang Pedoman Teknis Pengelolaan Keuangan Daerah;
7. Peraturan Pemerintah Nomor 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah;
8. Peraturan Menteri Negara Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 29 Tahun 2010 tentang Pedoman Penyusunan Kinerja dan Pelaporan Akuntabilitas Kinerja Instansi Pemerintah;
9. Peraturan Menteri Dalam Negeri Nomor 86 Tahun 2017 tentang Tata Cara Perencanaan, Pengendalian dan Evaluasi Pembangunan Daerah, Tata Cara Evaluasi Rancangan Peraturan Daerah Tentang Rencana Pembangunan Jangka Panjang Daerah dan Rencana Pembangunan Jangka Menengah Daerah, serta Tata Cara Perubahan Rencana Pembangunan Jangka Panjang Daerah, Rencana Pembangunan Jangka Menengah Daerah, Dan Rencana Kerja Pemerintah Daerah;
10. Peraturan Menteri Dalam Negeri Nomor 90 Tahun 2019 tentang Klasifikasi, Kodefikasi dan Nomenklatur Perencanaan Pembangunan dan Keuangan Daerah.

Kualifikasi Pelaksana:
1. Minimal D-III Ekonomi
2. Memahami dan mengetahui tata cara atau prosedur penyusunan Renstra
3. Memahami proses perencanaan kegiatan dan anggaran

Keterkaitan:
1. SOP Penyusunan RENJA

Peralatan/Perlengkapan:
1. Komputer PC,
2. Printer,
3. Jaringan Internet,
4. ATK
5. Data
6. Kalkulator
7. Hasil rapat dengan bidang-bidang BAPPEDA
8. RPJMD
9. Format Renstra

Peringatan:
Jika tidak dilaksanakan tidak ada sinkronisasi dalam perencanaan pembangunan daerah
```
</details>

### KOREKSI halaman 7

```text
Lampiran: Keputusan Wali Kota Banda Aceh
Nomor: 395
Tanggal: 26 Agustus 2025 M
2 Rabuul Awal 1447 H

NOMOR SOP: 9 / DISKOMINFOTIK / 2025
TANGGAL PEMBUATAN: 5 FEBRUARI 2025
TANGGAL REVISI: -
TANGGAL PENGESAHAN: 26 Agustus 2026

KEPALA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK
KOTA BANDA ACEH
SUB BAGIAN PROGRAM DAN PELAPORAN

KEPALA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK
KOTA BANDA ACEH
ALIZAR, S.Ag.Hum
PEMBINA UTAMA MUDA
NIP. 196911172001121002

NAMA SOP: PENYUSUNAN RENCANA STRATEGIS (RENSTRA) DISKOMINFO

Dasar Hukum:
1. Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara;
2. Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara;
3. Undang-Undang Nomor 25 Tahun 2004 tentang Sistem Perencanaan Pembangunan Nasional;
4. Undang-Undang Nomor 15 Tahun 2004 tentang Pemeriksaan dan Pertanggungjawaban Keuangan Negara;
5. Peraturan Presiden Nomor 12 Tahun 2021 tentang Perubahan atas Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintahan;
6. Peraturan Menteri Dalam Negeri Nomor 77 Tahun 2020 tentang Pedoman Teknis Pengelolaan Keuangan Daerah;
7. Peraturan Pemerintah Nomor 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah;
8. Peraturan Menteri Negara Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 29 Tahun 2010 tentang Pedoman Penyusunan Kinerja dan Pelaporan Akuntabilitas Kinerja Instansi Pemerintah;
9. Peraturan Menteri Dalam Negeri Nomor 86 Tahun 2017 tentang Tata Cara Perencanaan, Pengendalian dan Evaluasi Pembangunan Daerah, Tata Cara Evaluasi Rancangan Peraturan Daerah Tentang Rencana Pembangunan Jangka Panjang Daerah dan Rencana Pembangunan Jangka Menengah Daerah, serta Tata Cara Perubahan Rencana Pembangunan Jangka Panjang Daerah, Rencana Pembangunan Jangka Menengah Daerah, Dan Rencana Kerja Pemerintah Daerah;
10. Peraturan Menteri Dalam Negeri Nomor 90 Tahun 2019 tentang Klasifikasi, Kodefikasi dan Nomenklatur Perencanaan Pembangunan dan Keuangan Daerah.

Kualifikasi Pelaksana:
1. Minimal D-III Ekonomi
2. Memahami dan mengetahui tata cara atau prosedur penyusunan Renstra
3. Memahami proses perencanaan kegiatan dan anggaran

Keterkaitan:
1. SOP Penyusunan RENJA

Peralatan/Perlengkapan:
1. Komputer PC,
2. Printer,
3. Jaringan Internet,
4. ATK
5. Data
6. Kalkulator
7. Hasil rapat dengan bidang-bidang BAPPEDA
8. RPJMD
9. Format Renstra

Peringatan:
Jika tidak dilaksanakan tidak ada sinkronisasi dalam perencanaan pembangunan daerah
```

---

## Halaman 8

- Konteks: **SOP PENYUSUNAN RENCANA STRATEGIS (RENSTRA) DISKOMINFO**
- 2505 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
1. Menerima surat tentang Penyusunan Renstra OPD, dan memerintahkan Sekretaris untuk mengkoordinir Penyusunan Renstra Dinas Komunikasi, Informatika dan Statistik
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Surat Penyusunan Renstra
  - Waktu: 30 menit
  - Output: Disposisi

2. Memerintahkan/mengarahkan JF Perencana Ahli Muda untuk menyusun SK Tim Penyusunan Renstra
  - Pelaksana: Sekretaris
  - Kelengkapan: Disposisi
  - Waktu: 30 menit
  - Output: Disposisi

3. Membuat format pengumpulan data penyusunan Rencana Kerja 5 (lima) tahun, beserta indikator yang ingin dicapai sesuai dengan Visi dan Misi Walikota terpilih.
  - Pelaksana: JF Perencana Ahli Muda
  - Kelengkapan: Disposisi, visi dan misi Walikota terpilih
  - Waktu: 1 Hari
  - Output: Format Renstra

4. Menyusun Rencana Kerja 5 (lima) tahunan beserta indikator yang ingin dicapai pada Bidang dan Sekretariat
  - Pelaksana: Tim Penyusunan RENSTRA
  - Kelengkapan: Format Renstra, visi dan misi Walikota terpilih
  - Waktu: 5 Hari
  - Output: Rencana Kerja 5 (lima) tahun

5. Memerintahkan Penelaah Teknis Kebijakan untuk menghimpun dan menganalisis bahan penyusunan Renstra dari Bidang dan Sekretariat.
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Rencana Kerja 5 (lima) tahun
  - Waktu: 60 Menit
  - Output: Disposisi

6. Menghimpun, menganalisis dan menyerahkan draft Renstra kepada JF Perencana Ahli Muda
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Disposisi, Rencana Kerja 5 (lima) tahun
  - Waktu: 10 Hari
  - Output: draft Renstra

7. Melakukan rapat Penyusunan RENSTRA
  - Pelaksana: Tim Penyusunan RENSTRA
  - Kelengkapan: Draf Renstra
  - Waktu: 1 Hari
  - Output: Berita Acara/Notulen Rapat

8. Menyusun Renstra dan SK penyusunan Renstra sesuai hasil rapat Tim Penyusunan Renstra dan menyerahkan kepada Sekretaris.
  - Pelaksana: Tim Penyusunan RENSTRA
  - Kelengkapan: Draf Renstra, Notulen rapat
  - Waktu: 6 hari
  - Output: Dokumen Renstra

9. Memeriksa dan memeriksa Renstra. Jika data salah mengembalikan kepada JF Perencana Ahli Muda untuk diperbaiki. Jika data telah sesuai menyerahkan kepada Kepala Dinas Komunikasi, Informatika dan Statistik untuk ditandatangani.
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Dokumen Renstra
  - Waktu: 1 hari
  - Output: Dokumen Renstra

10. Mengesahkan Renstra
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Dokumen Renstra
  - Waktu: 1 Hari
  - Output: Dokumen Renstra
```
</details>

### KOREKSI halaman 8

```text
1. Menerima surat tentang Penyusunan Renstra OPD, dan memerintahkan Sekretaris untuk mengkoordinir Penyusunan Renstra Dinas Komunikasi, Informatika dan Statistik
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Surat Penyusunan Renstra
  - Waktu: 30 menit
  - Output: Disposisi

2. Memerintahkan/mengarahkan JF Perencana Ahli Muda untuk menyusun SK Tim Penyusunan Renstra
  - Pelaksana: Sekretaris
  - Kelengkapan: Disposisi
  - Waktu: 30 menit
  - Output: Disposisi

3. Membuat format pengumpulan data penyusunan Rencana Kerja 5 (lima) tahun, beserta indikator yang ingin dicapai sesuai dengan Visi dan Misi Walikota terpilih.
  - Pelaksana: JF Perencana Ahli Muda
  - Kelengkapan: Disposisi, visi dan misi Walikota terpilih
  - Waktu: 1 Hari
  - Output: Format Renstra

4. Menyusun Rencana Kerja 5 (lima) tahunan beserta indikator yang ingin dicapai pada Bidang dan Sekretariat
  - Pelaksana: Tim Penyusunan RENSTRA
  - Kelengkapan: Format Renstra, visi dan misi Walikota terpilih
  - Waktu: 5 Hari
  - Output: Rencana Kerja 5 (lima) tahun

5. Memerintahkan Penelaah Teknis Kebijakan untuk menghimpun dan menganalisis bahan penyusunan Renstra dari Bidang dan Sekretariat.
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Rencana Kerja 5 (lima) tahun
  - Waktu: 60 Menit
  - Output: Disposisi

6. Menghimpun, menganalisis dan menyerahkan draft Renstra kepada JF Perencana Ahli Muda
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Disposisi, Rencana Kerja 5 (lima) tahun
  - Waktu: 10 Hari
  - Output: draft Renstra

7. Melakukan rapat Penyusunan RENSTRA
  - Pelaksana: Tim Penyusunan RENSTRA
  - Kelengkapan: Draf Renstra
  - Waktu: 1 Hari
  - Output: Berita Acara/Notulen Rapat

8. Menyusun Renstra dan SK penyusunan Renstra sesuai hasil rapat Tim Penyusunan Renstra dan menyerahkan kepada Sekretaris.
  - Pelaksana: Tim Penyusunan RENSTRA
  - Kelengkapan: Draf Renstra, Notulen rapat
  - Waktu: 6 hari
  - Output: Dokumen Renstra

9. Memeriksa dan memeriksa Renstra. Jika data salah mengembalikan kepada JF Perencana Ahli Muda untuk diperbaiki. Jika data telah sesuai menyerahkan kepada Kepala Dinas Komunikasi, Informatika dan Statistik untuk ditandatangani.
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Dokumen Renstra
  - Waktu: 1 hari
  - Output: Dokumen Renstra

10. Mengesahkan Renstra
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Dokumen Renstra
  - Waktu: 1 Hari
  - Output: Dokumen Renstra
```

---

## Halaman 9

- Konteks: **SOP PENYUSUNAN RENCANA KERJA (RENJA) DISKOMINFOTIK**
- 2295 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
Nomor SOP: 6/DISKOMINFOTIK/2025
Tanggal Pembuatan: 5 Februari 2025
Tanggal Revisi: -
Tanggal Pengesahan: 26 Agustus 2025
Disahkan Oleh: KEPALA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK KOTA BANDA ACEH
Nama SOP: PENYUSUNAN RENCANA KERJA (RENJA) DISKOMINFOTIK
Dasar Hukum:
1. Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara;
2. Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara;
3. Undang-Undang Nomor 25 Tahun 2004 tentang Sistem Perencanaan Pembangunan Nasional;
4. Undang-Undang Nomor 15 Tahun 2004 tentang Pemeriksaan dan Pertanggungjawaban Keuangan Negara;
5. Peraturan Presiden Nomor 12 Tahun 2021 tentang Perubahan atas Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintahan;
6. Peraturan Menteri Dalam Negeri Nomor 77 Tahun 2020 tentang Pedoman Teknis Pengelolaan Keuangan Daerah;
7. Peraturan Pemerintah Nomor 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah;
8. Peraturan Menteri Negara Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 29 Tahun 2010 tentang Pedoman Penyusunan Kinerja dan Pelaporan Akuntabilitas Kinerja Instansi Pemerintah;
9. Peraturan Menteri Dalam Negeri Nomor 86 Tahun 2017 tentang Tata Cara Perencanaan, Pengendalian dan Evaluasi Pembangunan Daerah, Tata Cara Evaluasi Rancangan Peraturan Daerah Tentang Rencana Pembangunan Jangka Panjang Daerah dan Rencana Pembangunan Jangka Menengah Daerah, serta Tata Cara Perubahan Rencana Pembangunan Jangka Panjang Daerah, Rencana Pembangunan Jangka Menengah Daerah, Dan Rencana Kerja Pemerintah Daerah;
10. Peraturan Menteri Dalam Negeri Nomor 90 Tahun 2019 tentang Klasifikasi, Kodeifikasi dan Nomenklatur Perencanaan Pembangunan dan Keuangan Daerah.
Kualifikasi Pelaksana:
1. Minimal D-III Ekonomi
2. Memahami dan mengetahui tata cara atau prosedur penyusunan Renstra
3. Memahami proses perencanaan kegiatan dan anggaran
Keterkaitan:
1. SOP Penyusunan Renstra
2. SOP Penyusunan RKA
Peralatan/Perlengkapan:
1. Komputer PC,
2. Printer,
3. Jaringan Internet,
4. ATK
5. Data
6. Kalkulator
7. Hasil rapat dengan bidang-bidang Dinas Komunikasi, Informatika dan Statistik
8. Dokumen RPJMD
9. Format Renja
10. Dokumen Renstra Dinas Komunikasi, Informatika dan Statistik
Peringatan:
Jika tidak dilaksanakan tidak ada sinkronisasi dalam perencanaan pembangunan daerah
```
</details>

### KOREKSI halaman 9

```text
Nomor SOP: 6/DISKOMINFOTIK/2025
Tanggal Pembuatan: 5 Februari 2025
Tanggal Revisi: -
Tanggal Pengesahan: 26 Agustus 2025
Disahkan Oleh: KEPALA DINAS KOMUNIKASI, INFORMATIKA DAN STATISTIK KOTA BANDA ACEH
Nama SOP: PENYUSUNAN RENCANA KERJA (RENJA) DISKOMINFOTIK
Dasar Hukum:
1. Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara;
2. Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara;
3. Undang-Undang Nomor 25 Tahun 2004 tentang Sistem Perencanaan Pembangunan Nasional;
4. Undang-Undang Nomor 15 Tahun 2004 tentang Pemeriksaan dan Pertanggungjawaban Keuangan Negara;
5. Peraturan Presiden Nomor 12 Tahun 2021 tentang Perubahan atas Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintahan;
6. Peraturan Menteri Dalam Negeri Nomor 77 Tahun 2020 tentang Pedoman Teknis Pengelolaan Keuangan Daerah;
7. Peraturan Pemerintah Nomor 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah;
8. Peraturan Menteri Negara Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 29 Tahun 2010 tentang Pedoman Penyusunan Kinerja dan Pelaporan Akuntabilitas Kinerja Instansi Pemerintah;
9. Peraturan Menteri Dalam Negeri Nomor 86 Tahun 2017 tentang Tata Cara Perencanaan, Pengendalian dan Evaluasi Pembangunan Daerah, Tata Cara Evaluasi Rancangan Peraturan Daerah Tentang Rencana Pembangunan Jangka Panjang Daerah dan Rencana Pembangunan Jangka Menengah Daerah, serta Tata Cara Perubahan Rencana Pembangunan Jangka Panjang Daerah, Rencana Pembangunan Jangka Menengah Daerah, Dan Rencana Kerja Pemerintah Daerah;
10. Peraturan Menteri Dalam Negeri Nomor 90 Tahun 2019 tentang Klasifikasi, Kodeifikasi dan Nomenklatur Perencanaan Pembangunan dan Keuangan Daerah.
Kualifikasi Pelaksana:
1. Minimal D-III Ekonomi
2. Memahami dan mengetahui tata cara atau prosedur penyusunan Renstra
3. Memahami proses perencanaan kegiatan dan anggaran
Keterkaitan:
1. SOP Penyusunan Renstra
2. SOP Penyusunan RKA
Peralatan/Perlengkapan:
1. Komputer PC,
2. Printer,
3. Jaringan Internet,
4. ATK
5. Data
6. Kalkulator
7. Hasil rapat dengan bidang-bidang Dinas Komunikasi, Informatika dan Statistik
8. Dokumen RPJMD
9. Format Renja
10. Dokumen Renstra Dinas Komunikasi, Informatika dan Statistik
Peringatan:
Jika tidak dilaksanakan tidak ada sinkronisasi dalam perencanaan pembangunan daerah
```

---

## Halaman 10

- Konteks: **SOP PENYUSUNAN RENCANA KERJA (RENJA) DISKOMINFOTIK**
- 2326 karakter

<details>
<summary>OCR asli — rujukan, jangan diubah</summary>

```text
1. Menerima surat tentang Penyusunan Renja OPD, dan memerintahkan Sekretaris untuk mengkoordinir Penyusunan Renja
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Surat Penyusunan Renja
  - Waktu: 30 menit
  - Output: Disposisi

2. Memerintahkan/mengarahkan JF Perencana Ahli Muda untuk menyusun SK Tim Penyusunan Renja
  - Pelaksana: Sekretaris
  - Kelengkapan: Disposisi
  - Waktu: 30 menit
  - Output: Disposisi

3. Membuat format pengumpulan data penyusunan Rencana Kerja 1 (satu) tahun beserta indikator yang ingin dicapai
  - Pelaksana: JF Perencana Ahli Muda
  - Kelengkapan: Disposisi, Renstra
  - Waktu: 1 Hari
  - Output: Format Renja

4. Menyusun Rencana Kerja 1 (satu) tahun beserta indikator yang ingin dicapai pada Bidang dan Sekretariat
  - Pelaksana: Tim Penyusunan RENJA
  - Kelengkapan: Format Renja dan Renstra
  - Waktu: 5 Hari
  - Output: Rencana Kerja 1 (satu) tahun

5. Memerintahkan Penelaah Teknis Kebijakan untuk menghimpun dan menganalisis bahan penyusunan Renja dari Bidang dan Sekretariat.
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Rencana Kerja 1 (satu) tahun
  - Waktu: 60 Menit
  - Output: Disposisi

6. Menghimpun, menganalisis dan menyerahkan draft Renja kepada JF Perencana Ahli Muda
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Disposisi, Rencana Kerja 1 (satu) tahun, Renstra
  - Waktu: 10 Hari
  - Output: draft Renja

7. Melakukan rapat Penyusunan Renja
  - Pelaksana: Tim Penyusunan Renstra
  - Kelengkapan: Draf Renja
  - Waktu: 1 Hari
  - Output: Berita Acara/Notulen Rapat

8. Menyusun Renja dan SK penyusunan Renja sesuai hasil rapat Tim Penyusunan Renstra dan menyerahkan kepada Sekretaris.
  - Pelaksana: Tim Penyusunan Renstra
  - Kelengkapan: Draf Renja, Notulen rapat
  - Waktu: 6 hari
  - Output: Dokumen Renja

9. Memeriksa dan memaraf Renja. Jika data salah mengembalikan kepada JF Perencana Ahli Muda untuk diperbaiki. Jika data telah sesuai menyerahkan kepada Kepala Dinas Komunikasi, Informatika dan Statistik untuk ditandatangani.
  - Pelaksana: Tim Penyusunan Renstra
  - Kelengkapan: Dokumen Renja
  - Waktu: 1 hari
  - Output: Dokumen Renja

10. Mengesahkan Renja
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Dokumen Renja
  - Waktu: 1 Hari
  - Output: Dokumen Renja
```
</details>

### KOREKSI halaman 10

```text
1. Menerima surat tentang Penyusunan Renja OPD, dan memerintahkan Sekretaris untuk mengkoordinir Penyusunan Renja
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Surat Penyusunan Renja
  - Waktu: 30 menit
  - Output: Disposisi

2. Memerintahkan/mengarahkan JF Perencana Ahli Muda untuk menyusun SK Tim Penyusunan Renja
  - Pelaksana: Sekretaris
  - Kelengkapan: Disposisi
  - Waktu: 30 menit
  - Output: Disposisi

3. Membuat format pengumpulan data penyusunan Rencana Kerja 1 (satu) tahun beserta indikator yang ingin dicapai
  - Pelaksana: JF Perencana Ahli Muda
  - Kelengkapan: Disposisi, Renstra
  - Waktu: 1 Hari
  - Output: Format Renja

4. Menyusun Rencana Kerja 1 (satu) tahun beserta indikator yang ingin dicapai pada Bidang dan Sekretariat
  - Pelaksana: Tim Penyusunan RENJA
  - Kelengkapan: Format Renja dan Renstra
  - Waktu: 5 Hari
  - Output: Rencana Kerja 1 (satu) tahun

5. Memerintahkan Penelaah Teknis Kebijakan untuk menghimpun dan menganalisis bahan penyusunan Renja dari Bidang dan Sekretariat.
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Rencana Kerja 1 (satu) tahun
  - Waktu: 60 Menit
  - Output: Disposisi

6. Menghimpun, menganalisis dan menyerahkan draft Renja kepada JF Perencana Ahli Muda
  - Pelaksana: Penelaah Teknis Kebijakan
  - Kelengkapan: Disposisi, Rencana Kerja 1 (satu) tahun, Renstra
  - Waktu: 10 Hari
  - Output: draft Renja

7. Melakukan rapat Penyusunan Renja
  - Pelaksana: Tim Penyusunan Renstra
  - Kelengkapan: Draf Renja
  - Waktu: 1 Hari
  - Output: Berita Acara/Notulen Rapat

8. Menyusun Renja dan SK penyusunan Renja sesuai hasil rapat Tim Penyusunan Renstra dan menyerahkan kepada Sekretaris.
  - Pelaksana: Tim Penyusunan Renstra
  - Kelengkapan: Draf Renja, Notulen rapat
  - Waktu: 6 hari
  - Output: Dokumen Renja

9. Memeriksa dan memaraf Renja. Jika data salah mengembalikan kepada JF Perencana Ahli Muda untuk diperbaiki. Jika data telah sesuai menyerahkan kepada Kepala Dinas Komunikasi, Informatika dan Statistik untuk ditandatangani.
  - Pelaksana: Tim Penyusunan Renstra
  - Kelengkapan: Dokumen Renja
  - Waktu: 1 hari
  - Output: Dokumen Renja

10. Mengesahkan Renja
  - Pelaksana: Kepala Dinas Komunikasi, Informatika dan Statistik
  - Kelengkapan: Dokumen Renja
  - Waktu: 1 Hari
  - Output: Dokumen Renja
```
