# Laporan Evaluasi RAG — RAGAS (library resmi)

> Model generasi: `qwen2.5:7b` · Model juri: `deepseek/deepseek-v4-flash` (deepseek)
> Embedding: `BAAI/bge-m3`
> Ground truth: `reference_eval_dataset.json` (1 pertanyaan)

## Ringkasan Skor

| Metrik | Skor |
|--------|------|
| **faithfulness** | `1.0000` |
| **answer_relevancy** | `0.9537` |
| **context_recall** | `1.0000` |
| **llm_context_precision_with_reference** | `0.3333` |
| **factual_correctness(mode=f1)** | `0.9600` |

---

## Detail per Pertanyaan

### q01 — dasar_hukum

**Q:** Berapa jumlah dasar hukum ('Mengingat') pada Keputusan Walikota Banda Aceh tentang SOP Diskominfotik ini, dan sebutkan semuanya?

**Jawaban RAG:** Jumlah dasar hukum yang disebutkan dalam Keputusan Walikota Banda Aceh tentang SOP Diskominfotik ini adalah 13. Berikut daftarnya:

1. Undang-Undang Nomor 11 Tahun 2006 tentang Pemerintahan Aceh
2. Undang-Undang Nomor 14 Tahun 2008 tentang Keterbukaan Informasi Publik;
3. Undang-Undang Nomor 25 Tahun 2009 tentang Pelayanan Publik;
4. Undang-Undang Nomor 23 Tahun 2014 tentang Pemerintahan Daerah sebagaimana telah beberapa kali diubah terakhir dengan Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Peraturan Pemerintah Pengganti Undang-Undang Nomor 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-undang;
5. Undang-Undang Nomor 5 Tahun 2024 tentang Kota Banda Aceh di Aceh;
6. Peraturan Pemerintah Nomor 5 Tahun 1983 tentang Perubahan Batas Wilayah Kotamadya Daerah Tingkat II Banda Aceh;

7. Peraturan Menteri Dalam Negeri Nomor 52 Tahun 2011 tentang Standar Operasional Prosedur di Lingkungan Pemerintah Provinsi dan Kabupaten/Kota;
8. Peraturan Menteri Pemberdayaan Aparatur Negara Nomor 35 Tahun 2012 tentang Pedoman Penyusunan Standar Oprasional Administrasi Pemerintahan;
9. Peraturan Pemerintah Nomor 96 Tahun 2012 tentang Pelaksanaan Undang-Undang Nomor 25 Tahun 2009 tentang Pelayanan Publik;
10. Peraturan Menteri Pendayagunaan Aparatur Negara dan Reformasi Birokrasi Nomor 62 Tahun 2018 tentang Pedoman Sistem Pengaduan Pelayanan Publik Nasional;
11. Peraturan Menteri Komunikasi dan Informatika Nomor 4 Tahun 2024 tentang Penyelenggaraan Urusan Pemerintahan Konkuren Bidang Komunikasi dan Informatika;
12. Qanun Kota Banda Aceh Nomor 11 Tahun 2016 tentang Pembentukan dan Susunan Perangkat Daerah Kota Banda Aceh;
13. Peraturan Walikota Banda Aceh Nomor 54 Tahun 2016 tentang Susunan, Kedudukan, Tugas, Fungsi, Kewenangan dan Tata Kerja Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh.

**Ground truth:** Terdapat 13 dasar hukum ('Mengingat'): 1) UU No. 11 Tahun 2006 tentang Pemerintahan Aceh; 2) UU No. 14 Tahun 2008 tentang Keterbukaan Informasi Publik; 3) UU No. 25 Tahun 2009 tentang Pelayanan Publik; 4) UU No. 23 Tahun 2014 tentang Pemerintahan Daerah (sebagaimana diubah terakhir dengan UU No. 6 Tahun 2023 tentang Penetapan Perpu No. 2 Tahun 2022 tentang Cipta Kerja menjadi Undang-Undang); 5) UU No. 5 Tahun 2024 tentang Kota Banda Aceh; 6) PP No. 5 Tahun 1983 tentang Perubahan Batas Wilayah Kotamadya Daerah Tingkat II Banda Aceh; 7) Permendagri No. 52 Tahun 2011 tentang Standar Operasional Prosedur di Lingkungan Pemerintah Provinsi dan Kabupaten/Kota; 8) Permen PAN No. 35 Tahun 2012 tentang Pedoman Penyusunan Standar Operasional Administrasi Pemerintahan; 9) PP No. 96 Tahun 2012 tentang Pelaksanaan UU No. 25 Tahun 2009 tentang Pelayanan Publik; 10) Permen PANRB No. 62 Tahun 2018 tentang Pedoman Sistem Pengaduan Pelayanan Publik Nasional; 11) Permen Kominfo No. 4 Tahun 2024 tentang Penyelenggaraan Urusan Pemerintahan Konkuren Bidang Komunikasi dan Informatika; 12) Qanun Kota Banda Aceh No. 11 Tahun 2016 tentang Pembentukan dan Susunan Perangkat Daerah Kota Banda Aceh; 13) Peraturan Walikota Banda Aceh No. 54 Tahun 2016 tentang Susunan, Kedudukan, Tugas, Fungsi, Kewenangan dan Tata Kerja Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh.

| Metrik | Skor |
|--------|------|
| faithfulness | `1.0000` |
| answer_relevancy | `0.9537` |
| context_recall | `1.0000` |
| llm_context_precision_with_reference | `0.3333` |
| factual_correctness(mode=f1) | `0.9600` |

---

