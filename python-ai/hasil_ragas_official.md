# Laporan Evaluasi RAG — RAGAS (library resmi)

> Model generasi: `qwen2.5:7b` · Model juri: `gemini/gemini-3.5-flash-lite` (gemini)
> Embedding: `BAAI/bge-m3`
> Ground truth: `reference_eval_dataset.json` (3 pertanyaan)

## Ringkasan Skor

| Metrik | Skor |
|--------|------|
| **faithfulness** | `1.0000` |
| **answer_relevancy** | `0.8970` |
| **context_recall** | `1.0000` |
| **llm_context_precision_with_reference** | `0.6667` |
| **factual_correctness(mode=f1)** | `0.1300` |

---

## Detail per Pertanyaan

### q01 — dasar_hukum

**Q:** Berapa jumlah dasar hukum ('Mengingat') pada Keputusan Walikota Banda Aceh tentang SOP Diskominfotik ini, dan sebutkan semuanya?

**Jawaban RAG:** Jumlah dasar hukum yang disebutkan dalam Keputusan Walikota Banda Aceh tentang SOP Diskominfotik adalah 13. Berikut daftarnya:

1. Undang-Undang Nomor 11 Tahun 2006 tentang Pemerintahan Aceh
2. Undang-Undang Nomor 14 Tahun 2008 tentang Keterbukaan Informasi Publik
3. Undang-Undang Nomor 25 Tahun 2009 tentang Pelayanan Publik
4. Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah sebagaimana telah beberapa kali diubah terakhir dengan Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-undang
5. Undang-Undang Nomor 5 Tahun 2024 tentang Kota Banda Aceh di Aceh
6. Peraturan Pemerintah Nomor 5 Tahun 1983 tentang Perubahan Batas Wilayah Kotamadya Daerah Tingkat II Banda Aceh

Untuk dasar hukum dalam Lampiran Keputusan tersebut, terdapat 10 dasar hukum:

7. Undang-Undang Nomor 17 Tahun 2003 tentang Keuangan Negara
8. Undang-Undang Nomor 1 Tahun 2004 tentang Perbendaharaan Negara
9. Undang-Undang Nomor 25 Tahun 2004 tentang Sistem Perencanaan Pembangunan Nasional
10. Undang-Undang Nomor 15 Tahun 2004 tentang Pemeriksaan dan Pertanggungjawaban Keuangan Negara
11. Peraturan Presiden Nomor 12 Tahun 2021 tentang Perubahan atas Peraturan Presiden Nomor 16 Tahun 2018 tentang Pengadaan Barang/Jasa Pemerintahaan
12. Peraturan Menteri Dalam Negeri Nomor 77 Tahun 2020 tentang Pedoman Teknis Pengelolaan Keuangan Daerah
13. Peraturan Pemerintah Nomor 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah
14. Peraturan Menteri Negara Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 29 Tahun 2010 tentang Pedoman Penyusunan Kinerja dan Pelaporan Akuntabilitas Kinerja Instansi Pemerintah
15. Peraturan Menteri Dalam Negeri Nomor 86 Tahun 2017 tentang Tata Cara Perencanaan, Pengendalian dan Evaluasi Pembangunan Daerah, Tata Cara Evaluasi Rancangan Peraturan Daerah Tentang Rencana Pembangunan Jangka Panjang Daerah dan Rencana Pembangunan Jangka Menengah Daerah, serta Tata Cara Perubahan Rencana Pembangunan Jangka Panjang Daerah, Rencana Pembangunan Jangka Menengah Daerah, Dan Rencana Kerja Pemerintah Daerah
16. Peraturan Menteri Dalam Negeri Nomor 90 Tahun 2019 tentang Klasifikasi, Kodefikasi dan Nomenklatur Perencanaan Pembangunan dan Keuangan Daerah

**Ground truth:** Terdapat 13 dasar hukum ('Mengingat'): 1) UU No. 11 Tahun 2006 tentang Pemerintahan Aceh; 2) UU No. 14 Tahun 2008 tentang Keterbukaan Informasi Publik; 3) UU No. 25 Tahun 2009 tentang Pelayanan Publik; 4) UU No. 23 Tahun 2014 tentang Pemerintahan Daerah (sebagaimana diubah terakhir dengan UU No. 6 Tahun 2023 tentang Penetapan Perpu No. 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-Undang); 5) UU No. 5 Tahun 2024 tentang Kota Banda Aceh; 6) PP No. 5 Tahun 1983 tentang Perubahan Batas Wilayah Kotamadya Daerah Tingkat II Banda Aceh; 7) Permendagri No. 52 Tahun 2011 tentang Standar Operasional Prosedur di Lingkungan Pemerintah Provinsi dan Kabupaten/Kota; 8) Permen PAN No. 35 Tahun 2012 tentang Pedoman Penyusunan Standar Operasional Administrasi Pemerintahan; 9) PP No. 96 Tahun 2012 tentang Pelaksanaan UU No. 25 Tahun 2009 tentang Pelayanan Publik; 10) Permen PANRB No. 62 Tahun 2018 tentang Pedoman Sistem Pengaduan Pelayanan Publik Nasional; 11) Permen Kominfo No. 4 Tahun 2024 tentang Penyelenggaraan Urusan Pemerintahan Konkuren Bidang Komunikasi dan Informatika; 12) Qanun Kota Banda Aceh No. 11 Tahun 2016 tentang Pembentukan dan Susunan Perangkat Daerah Kota Banda Aceh; 13) Peraturan Walikota Banda Aceh No. 54 Tahun 2016 tentang Susunan, Kedudukan, Tugas, Fungsi, Kewenangan dan Tata Kerja Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh.

| Metrik | Skor |
|--------|------|
| faithfulness | `1.0000` |
| answer_relevancy | `0.9452` |
| context_recall | `1.0000` |
| llm_context_precision_with_reference | `0.0000` |
| factual_correctness(mode=f1) | `0.3900` |

---

### q02 — diktum

**Q:** Berapa nomor Keputusan Walikota Banda Aceh tentang SOP pada Dinas Komunikasi, Informatika dan Statistik ini?

**Jawaban RAG:** Nomor Keputusan Walikota Banda Aceh tentang SOP pada Dinas Komunikasi, Informatika dan Statistik adalah 395 Tahun 2025.

**Ground truth:** Nomor 395 Tahun 2025 (tercantum pada sampul halaman 1 dan pada Lampiran di halaman 7: 'Nomor : 395').

> **Catatan:** Dokumen sumber TIDAK konsisten: pada header pasal di halaman 2 tertulis 'KEPUTUSAN WALIKOTA BANDA ACEH NOMOR 305 TAHUN 2025' (beda dari sampul dan lampiran yang menyebut 395). Karena 395 muncul di dua tempat (sampul + lampiran) vs 305 hanya satu tempat, 395 dianggap nomor yang benar, namun kejanggalan 305 tetap perlu diketahui saat menilai jawaban RAG — jika RAG menyebut 305, itu bukan otomatis halusinasi karena angka itu memang ada di sumber halaman 2.

| Metrik | Skor |
|--------|------|
| faithfulness | `1.0000` |
| answer_relevancy | `0.9934` |
| context_recall | `1.0000` |
| llm_context_precision_with_reference | `1.0000` |
| factual_correctness(mode=f1) | `0.0000` |

---

### q03 — diktum

**Q:** Apa isi Diktum KESATU dari Keputusan Walikota ini?

**Jawaban RAG:** Isi Diktum KESATU dari Keputusan Walikota Banda Aceh Nomor 395 Tahun 2025 adalah:

"Menetapkan : Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh sebagaimana tercantum dalam Lampiran Keputusan ini."

Isi Diktum KESATU tersebut mencakup penetapan standar operasional prosedur yang berlaku untuk Dinas Komunikasi, Informatika dan Statistik di Kota Banda Aceh, dengan detail lebih lanjut dapat ditemukan dalam lampiran keputusan tersebut.

**Ground truth:** Diktum KESATU berbunyi: 'Standar Operasional Prosedur pada Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh sebagaimana tercantum dalam Lampiran Keputusan ini.' Diktum ini tidak merinci daftar SOP secara langsung, melainkan merujuk ke Lampiran Keputusan (yang isinya dirinci di Diktum KEDUA).

| Metrik | Skor |
|--------|------|
| faithfulness | `1.0000` |
| answer_relevancy | `0.7524` |
| context_recall | `1.0000` |
| llm_context_precision_with_reference | `1.0000` |
| factual_correctness(mode=f1) | `0.0000` |

---

