# Serah Terima Proyek Magang — SAPA

**Status dokumen: draf pendamping untuk review pembimbing lapangan.**
Ringkasan ini mengikuti presentasi
[PPT DISKOMINFOTIK.pptx](<PPT DISKOMINFOTIK.pptx>) yang sudah disampaikan.
PPT tetap menjadi pengantar masalah dan solusi; dokumen ini menghubungkannya
dengan hasil implementasi, bukti pengujian, dan materi yang diserahkan.

| Identitas | Keterangan |
| --- | --- |
| Mahasiswa / penyerah | Muhammad Naufal Tiftazani |
| NIM | 230705117 |
| Instansi / unit | Diskominfotik Kota Banda Aceh / E-Government |
| Proyek | SAPA — asisten layanan informasi berbasis dokumen |
| Fokus laporan yang sudah tersedia | API Gateway dan sistem manajemen dokumen |
| Pembimbing lapangan | Diisi sebelum penyerahan |
| Tanggal penyerahan | Diisi saat penyerahan |
| Versi kode yang diserahkan | Cantumkan commit atau nama arsip final setelah dibekukan |

Identitas mengikuti `laporan-kkp/setup/identitas.tex`. Konfirmasi kembali
sebelum menyerahkan dokumen. Ruang lingkup sistem tidak otomatis menyatakan
seluruh modul dikerjakan oleh satu orang; uraikan kontribusi pribadi sesuai
pekerjaan dan logbook yang benar-benar dilakukan.

## Mulai dari dokumen ini

| Kebutuhan pembimbing | Materi yang disiapkan |
| --- | --- |
| Membaca gambaran hasil dengan cepat | [Ringkasan PDF pembimbing](output/serah-terima/SAPA-Ringkasan-Pembimbing.pdf), tiga halaman |
| Mengikuti penjelasan yang telah dipresentasikan | [PPT DISKOMINFOTIK.pptx](<PPT DISKOMINFOTIK.pptx>), 18 slide |
| Meninjau kode dan cara menjalankan | [README proyek](README.md), README setiap aplikasi, dan [panduan lokal](docs/04-panduan_kerja_mandiri_dev.md) |
| Memeriksa hasil pengujian dan refactoring | [Status verifikasi, audit dan penutupan](docs/09-status-refactor-dan-verifikasi.md) |
| Membaca laporan akademik | Pilih PDF laporan final milik mahasiswa dari `laporan-kkp/`, setelah memastikan versinya benar |

PDF ringkasan adalah hasil build dari
[`docs/10-serah-terima-pembimbing.tex`](docs/10-serah-terima-pembimbing.tex).
Jika menyerahkan melalui Git, sertakan PDF tersebut sebagai lampiran terpisah
atau bangun ulang dengan perintah di bagian akhir. Folder output diabaikan Git.

## Ringkasan untuk pembimbing

Presentasi mengangkat pengalaman penelusuran chat layanan yang berakhir pada
pesan petugas tidak tersedia dan formulir. Temuan tersebut menjadi alasan
pengembangan SAPA: membantu menjawab pertanyaan berulang dari dokumen yang
dikelola dinas dan menyediakan jalur bantuan petugas ketika diperlukan.
Observasi pada PPT bukan hasil survei seluruh layanan atau pengukuran waktu
respons umum.

Sistem terdiri dari dashboard admin React, backend/API Gateway Laravel,
serta layanan AI dan pemrosesan dokumen Python. Admin mengunggah dokumen,
meninjau hasil ekstraksi, lalu menyimpan hasil koreksi ke basis pengetahuan.
Pertanyaan diproses menggunakan konteks dokumen; tiket membantu tindak lanjut
yang memerlukan petugas. Manfaat yang diharapkan adalah pengelolaan informasi
dan penelusuran sumber yang lebih teratur, bukan penggantian keputusan petugas.

## Hubungan dengan PPT yang sudah dipresentasikan

| Bagian PPT | Penjelasan pendamping saat penyerahan |
| --- | --- |
| Slide 1–8: SAPA, observasi dan kebutuhan | Jelaskan masalah layanan dan kebutuhan warga, petugas serta dinas. Presentasikan manfaat sebagai tujuan; hindari mengubahnya menjadi angka dampak yang belum diukur |
| Slide 9–11: gagasan alur layanan | Tunjukkan bagaimana dokumen dinas, pertanyaan dan bantuan petugas dihubungkan oleh aplikasi |
| Slide 12: unggah, ekstraksi, koreksi, embedding | Demo satu dokumen kecil dan hasil koreksinya sebelum dipakai menjawab |
| Slide 13–17: pencarian, reranker, LLM dan tiket | Bedakan komponen yang tersedia dari profil yang diuji. Reranker didukung konfigurasi; profil integrasi terakhir memakai reranker nonaktif. Uji kanal eksternal memerlukan penerima uji tersendiri |
| Slide 18: demo | Tunjukkan alur nyata, hasil pengujian, keterbatasan dan pekerjaan operasional berikutnya |

## Status implementasi dan bukti

| Bagian | Yang dapat dinyatakan dari bukti saat ini |
| --- | --- |
| Struktur kode/dokumentasi | Refactoring awal dan temuan audit A1/A2 ditutup; UI dipertahankan sesuai batas bukti pada laporan penutupan |
| Laravel | 227 tes / 1403 assertion lulus pada audit; tes terutama memakai SQLite dan dependency tiruan |
| Python AI | 228 tes lulus pada audit; tes unit menggantikan database, broker, model dan transport terkait |
| Pipeline dokumen/chat | 16 pemeriksaan integrasi nyata lulus pada layanan sementara, termasuk OCR, koreksi, embedding, JSON/SSE dan pembatalan |
| Pemulihan layanan | 9 pemeriksaan termasuk setup lulus untuk cleanup vektor setelah gangguan Chroma/API |
| Form Direktori/Fast Path | 18 pemeriksaan browser terkelompok per run lulus; 210 pengukuran kontrol cocok sebelum/sesudah. Dari 24 pasangan screenshot, 21 identik dan tiga selisih raster kecil ditinjau |
| Kualitas jawaban umum | Belum dinyatakan memadai untuk seluruh dokumen instansi; pengujian sintetis tidak membuktikan akurasi umum |
| Kanal dan penerapan | Alur tiket/kanal tersedia, tetapi pengiriman WhatsApp/Telegram/webhook ke penerima nyata serta penerapan server instansi belum dibuktikan oleh penutupan refactoring |

Angka tersebut adalah hasil run yang didokumentasikan pada 25–26 Oktober 2026,
bukan hasil pengujian baru pada server pembimbing. Pembatalan/outbox memiliki
dua migrasi baru yang selama pengujian hanya diterapkan pada database sementara.

## Alur pertemuan yang disarankan

Alokasi berikut adalah susunan presentasi sekitar 14 menit, bukan janji durasi
inferensi model. Siapkan layanan, akun demo dan contoh dokumen sebelum pertemuan.

| Alokasi | Kegiatan | Yang ditunjukkan |
| --- | --- | --- |
| 2 menit | Ingatkan masalah dan tujuan dari PPT | Hubungan kebutuhan dinas dengan ruang lingkup proyek |
| 4 menit | Demo pengelolaan dokumen | Unggah contoh kecil, status ekstraksi, koreksi teks, pratinjau dan penyimpanan korpus |
| 4 menit | Demo pertanyaan dan sumber | Satu pertanyaan yang jawabannya ada pada contoh, lalu satu pertanyaan di luar cakupan; cocokkan jawaban dengan dokumen |
| 2 menit | Demo tindak lanjut dan monitoring | Tiket internal atau form direktori, status layanan, dan log yang relevan |
| 2 menit | Jelaskan hasil dan penyerahan | Bukti pengujian, batas penggunaan, lokasi kode dan masukan pembimbing |

Gunakan dokumen sintetis atau dokumen yang memang boleh ditampilkan. Siapkan
hasil ekstraksi cadangan; jika menampilkan hasil yang sudah diproses, sebutkan
bahwa itu hasil sebelumnya. Tampilkan keluaran model apa adanya dan catat
ketidaksesuaian, bukan menjanjikan jawaban benar untuk setiap pertanyaan.

Untuk demo yang mengubah data, gunakan lingkungan sementara pada
[panduan integrasi/browser](scripts/integration/browser/README.md). Periksa
launcher sebelum dipakai pada mesin bersama: `start-all.sh` saat ini dapat
menghentikan proses, mereset job, mem-purge antrean, dan menjalankan migrasi.

## Isi paket yang diserahkan

1. Ringkasan PDF, PPT yang telah dipresentasikan, serta PDF laporan akademik
   final yang dipilih mahasiswa.
2. Kode `admin-frontend`, `laravel-admin`, dan `python-ai`, termasuk seluruh
   modul baru, lock file dependency, migrasi, tes, verifier dan dokumentasi.
3. Contoh konfigurasi serta panduan operator: layanan/model yang diperlukan,
   perintah menjalankan, pengujian, backup dan kebutuhan rollout migrasi.
4. Contoh data demo yang memang boleh dibagikan dan catatan hasil uji.
5. Daftar pekerjaan lanjutan: evaluasi korpus instansi, uji kanal penerima
   nyata, konfigurasi server, serta prioritas yang disepakati setelah review.

Pilih berkas yang dibagikan; jangan mengirim seluruh folder kerja begitu saja.
Dependency terpasang, cache, log, `.env`, API key/token, database operasional dan
referensi laporan milik pihak lain tidak menjadi isi paket kode. Akses
operasional diserahkan terpisah kepada pihak yang berwenang bila diperlukan.

Sebelum mengirim tautan repository, pastikan modul/file baru ikut dalam versi
yang dibekukan; perubahan workspace belum otomatis tersedia pada commit lama.
Dokumen ini belum menyatakan paket sudah dikirim atau diterima pembimbing.

## Pertanyaan untuk penutupan review

- Apakah alur pengelolaan dokumen dan layanan informasi sudah sesuai kebutuhan unit?
- Dokumen serta jenis pertanyaan apa yang perlu menjadi prioritas uji berikutnya?
- Siapa operator/penerima kode, dan lingkungan mana yang dipilih untuk uji penerapan?
- Apa catatan pembimbing dan tindak lanjut yang disepakati?

## Membangun ulang PDF ringkasan

Dari root repository dengan LaTeX yang dependensinya sudah tersedia:

```bash
mkdir -p output/serah-terima
pdflatex -interaction=nonstopmode -halt-on-error -output-directory=output/serah-terima -jobname=SAPA-Ringkasan-Pembimbing docs/10-serah-terima-pembimbing.tex
```

Sumber PDF dan dokumen ini merupakan materi pendamping untuk direview. Lengkapi
nama pembimbing, tanggal penyerahan dan versi paket sebelum dibagikan.
