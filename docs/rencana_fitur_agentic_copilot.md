# Rencana Fitur & Rekomendasi Model

## 1. Modul Dashboard Admin (Laravel)

- **Autentikasi & Otorisasi:** Sistem Login eksklusif untuk Admin Diskominfotik.
- **Manajemen Dokumen (Knowledge Base):**
  - **Tabel Daftar PDF:** Menampilkan daftar dokumen yang aktif di dalam sistem Vector DB.
  - **Status Pemrosesan:** Indikator visual (_Badge_) untuk status sinkronisasi: `Pending` -> `Processing` -> `Completed` / `Failed`.
  - **Preview PDF Terintegrasi:** Admin dapat melihat isi PDF langsung di _browser_ (menggunakan iframe / PDF.js terintegrasi) untuk memastikan kebenaran isi dokumen tanpa perlu mengunduhnya.
  - **Fungsi Overwrite (Timpa):** Tombol aksi untuk menimpa PDF lama. Saat diganti, Laravel menyimpan file baru, mempertahankan metadata ID dokumen tersebut, dan memicu _webhook/queue_ ke Python.

## 2. Modul AI Processing (Python Microservice)

- **Asynchronous Queue Worker:** Menggunakan task queue manager seperti `Celery` (via Redis) atau `FastAPI BackgroundTasks` agar proses ekstraksi 170+ halaman berjalan di _background_ dan Laravel bisa memberikan respon instan.
- **Smart Text Extraction & OCR:**
  - Mengecek apakah setiap halaman berisi teks (_native PDF_) atau hanya _scan_ gambar.
  - Jika gambar _scan_, memicu `Tesseract OCR` untuk mengekstrak teks. (Membutuhkan optimasi/pembagian proses agar RAM tidak penuh untuk PDF 170 halaman).
- **Vector DB Management (ChromaDB / FAISS):**
  - Menghapus _chunk_ (vektor teks) lama dari _database_ berdasarkan parameter `document_id`.
  - Melakukan _embedding_ dan memasukkan vektor teks PDF yang baru.
- **Update Database Lintas Layanan:** Setelah semua selesai, skrip Python dapat langsung meng-update kolom `status` pada tabel `documents` di database MySQL (yang dibagikan dengan Laravel) menjadi `'completed'`.

## 3. Stack AI Final yang Disepakati

```
LLM (via Ollama)  : Qwen2.5-Instruct (lihat strategi fase di bawah)
Embedding Model   : paraphrase-multilingual-MiniLM-L12-v2 (via SentenceTransformers)
Vector Database   : ChromaDB
Orkestrasi AI     : LangChain (Python)
```

### Strategi Model Bertahap (Model-Swap)

Model dikonfigurasi melalui **satu variabel** di file `.env` sehingga upgrade dari Fase 1 ke Fase 2 **tidak memerlukan perubahan logika kode apapun**.

| Fase                         | Model LLM    | RAM Dibutuhkan | Tujuan                                                               |
| ---------------------------- | ------------ | -------------- | -------------------------------------------------------------------- |
| **Fase 1 (Testing Lokal)**   | `qwen2.5:3b` | ~4–5 GB        | Development & validasi fitur RAG + Tool Calling di mesin lokal (WSL) |
| **Fase 2 (Produksi Server)** | `qwen2.5:7b` | ~12 GB         | Deploy ke server Diskominfotik setelah konfirmasi spesifikasi RAM    |

### Mengapa Qwen2.5 untuk RAG & Tool Calling?

- ✅ **Native Tool Calling / Function Calling** — dilatih secara resmi untuk menghasilkan structured JSON untuk pemilihan fungsi (bukan _prompt hack_).
- ✅ **Bahasa Indonesia paling kuat** di kelas SLM (Small Language Model) dibanding Llama/Mistral.
- ✅ **Konsistensi instruksi tinggi** — ideal untuk RAG (tidak mengarang jawaban di luar konteks dokumen).
- ✅ **Format GGUF Q4_K_M** via Ollama — paling efisien untuk inferensi di atas CPU.

### Pertanyaan Konfirmasi ke Admin Server (sebelum upgrade ke Fase 2)

| Spesifikasi      | Target Minimum (7B)                   |
| ---------------- | ------------------------------------- |
| Total RAM Server | **≥ 12 GB**                           |
| Jumlah Core CPU  | **≥ 8 core**                          |
| Sistem Operasi   | Linux (Ubuntu/Debian)                 |
| Akses root/sudo  | Diperlukan untuk Ollama & Docker      |
| Ada GPU?         | Bonus — mempercepat inferensi drastis |

### Embedding Model

- **`paraphrase-multilingual-MiniLM-L12-v2`** — Pilihan final. Ukuran < 500MB, berjalan instan di CPU, dilatih untuk _multilingual_ termasuk Bahasa Indonesia. Memastikan pencarian semantik dokumen sangat akurat.
