# Rencana Fitur & Rekomendasi Model

## 1. Modul Dashboard Admin (Laravel)
- **Autentikasi & Otorisasi:** Sistem Login eksklusif untuk Admin Diskominfotik.
- **Manajemen Dokumen (Knowledge Base):**
  - **Tabel Daftar PDF:** Menampilkan daftar dokumen yang aktif di dalam sistem Vector DB.
  - **Status Pemrosesan:** Indikator visual (*Badge*) untuk status sinkronisasi: `Pending` -> `Processing` -> `Completed` / `Failed`.
  - **Preview PDF Terintegrasi:** Admin dapat melihat isi PDF langsung di *browser* (menggunakan iframe / PDF.js terintegrasi) untuk memastikan kebenaran isi dokumen tanpa perlu mengunduhnya.
  - **Fungsi Overwrite (Timpa):** Tombol aksi untuk menimpa PDF lama. Saat diganti, Laravel menyimpan file baru, mempertahankan metadata ID dokumen tersebut, dan memicu *webhook/queue* ke Python.

## 2. Modul AI Processing (Python Microservice)
- **Asynchronous Queue Worker:** Menggunakan task queue manager seperti `Celery` (via Redis) atau `FastAPI BackgroundTasks` agar proses ekstraksi 170+ halaman berjalan di *background* dan Laravel bisa memberikan respon instan.
- **Smart Text Extraction & OCR:**
  - Mengecek apakah setiap halaman berisi teks (*native PDF*) atau hanya *scan* gambar.
  - Jika gambar *scan*, halaman dikirim sebagai gambar ke **model vision `qwen2.5vl`** lewat Ollama. (Membutuhkan optimasi/pembagian proses agar RAM tidak penuh untuk PDF 170 halaman.)
  - **Perubahan dari rencana awal:** semula `Tesseract OCR`, diganti model vision karena dokumen uji padat tabel dan hasil Tesseract di situ jauh lebih kotor. Konsekuensinya perlu diketahui: keluaran model vision **tidak deterministik** dan bisa menjatuhkan isi tanpa menimbulkan galat — rinciannya di [`07-arsitektur-rag-python-ai.md`](07-arsitektur-rag-python-ai.md) §8.
  - **Prapemrosesan wajib:** halaman diluruskan lebih dulu dengan pencarian sudut berlangkah **0,25°**. Terukur pada dokumen 171 halaman: 64 halaman miring pada ±0,25°, dan tanpa pelurusan ini deteksi struktur gagal di sebagian besar halaman.
- **Vector DB Management (ChromaDB / FAISS):**
  - Menghapus *chunk* (vektor teks) lama dari *database* berdasarkan parameter `document_id`.
  - Melakukan *embedding* dan memasukkan vektor teks PDF yang baru.
- **Update Database Lintas Layanan:** Setelah semua selesai, skrip Python dapat langsung meng-update kolom `status` pada tabel `documents` di database MySQL (yang dibagikan dengan Laravel) menjadi `'completed'`.

## 3. Stack AI Final yang Disepakati

```
LLM teks (Ollama)   : qwen2.5:7b            -> menyusun jawaban
LLM vision (Ollama) : qwen2.5vl             -> OCR halaman pindai
Embedding Model     : BAAI/bge-m3           (via SentenceTransformers)
Vector Database     : ChromaDB
Pencarian kata      : rank_bm25             (digabung dengan vektor lewat RRF)
Orkestrasi AI       : LangChain (Python)
Penilai evaluasi    : DeepSeek (RAGAS) + penilai fakta deterministik
```

**Dua model Ollama dipakai terpisah dan itu disengaja.** Memakai satu model
multimodal untuk OCR sekaligus chat pernah dicoba dan membuat jawaban chat jauh
lebih lambat tanpa keuntungan apa pun. Konsekuensi yang perlu diterima: pada
mesin ber-VRAM kecil Ollama akan bertukar model bila ingest dan chat berjalan
berdekatan.

### Strategi Model Bertahap (Model-Swap)
Model dikonfigurasi melalui **satu variabel** di file `.env` sehingga upgrade dari Fase 1 ke Fase 2 **tidak memerlukan perubahan logika kode apapun**.

| Fase | Model LLM | RAM Dibutuhkan | Tujuan |
|---|---|---|---|
| **Fase 1 (Testing Lokal)** | `qwen2.5:3b` | ~4–5 GB | Development & validasi fitur RAG + Tool Calling di mesin lokal (WSL) |
| **Fase 2 (Produksi Server)** | `qwen2.5:7b` | ~12 GB | Deploy ke server Diskominfotik setelah konfirmasi spesifikasi RAM |

### Mengapa Qwen2.5 untuk RAG & Tool Calling?
- ✅ **Native Tool Calling / Function Calling** — dilatih secara resmi untuk menghasilkan structured JSON untuk pemilihan fungsi (bukan *prompt hack*).
- ✅ **Bahasa Indonesia paling kuat** di kelas SLM (Small Language Model) dibanding Llama/Mistral.
- ✅ **Konsistensi instruksi tinggi** — ideal untuk RAG (tidak mengarang jawaban di luar konteks dokumen).
- ✅ **Format GGUF Q4_K_M** via Ollama — paling efisien untuk inferensi di atas CPU.

### Pertanyaan Konfirmasi ke Admin Server (sebelum upgrade ke Fase 2)

| Spesifikasi | Target Minimum (7B) |
|---|---|
| Total RAM Server | **≥ 12 GB** |
| Jumlah Core CPU | **≥ 8 core** |
| Sistem Operasi | Linux (Ubuntu/Debian) |
| Akses root/sudo | Diperlukan untuk Ollama & Docker |
| Ada GPU? | Bonus — mempercepat inferensi drastis |

### Embedding Model
- **`BAAI/bge-m3`** — yang dipakai sekarang. Multilingual termasuk Bahasa Indonesia, dan kualitas retrieval-nya lebih baik pada dokumen berbahasa Indonesia yang padat istilah resmi.
- **`paraphrase-multilingual-MiniLM-L12-v2`** — pilihan awal, kini menjadi nilai bawaan di `config.py` bila `.env` tidak menyetel apa pun. Jauh lebih kecil (<500 MB) dan lebih ringan di CPU, jadi tetap masuk akal untuk mesin yang sangat terbatas.

Model dipilih lewat `EMBEDDING_MODEL_NAME` di `.env`. **Mengganti model embedding menuntut ingest ulang seluruh dokumen** — vektor lama tidak sebanding dengan vektor model baru.

