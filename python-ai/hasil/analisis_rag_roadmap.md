# 📊 Analisis Kondisi Sistem RAG vs Roadmap Peningkatan Akurasi

> **Tanggal Analisis:** 17 Juli 2026  
> **Proyek:** Agentic Chatbot — Dinas Kominfo Banda Aceh  
> **Stack:** FastAPI + Celery + ChromaDB + Ollama (qwen2.5:3b + qwen2.5vl)

---

## Ringkasan Status

| # | Pilar | Status | Prioritas |
|---|-------|--------|-----------|
| 1 | Ekstraksi Data (PDF → Teks) | ✅ Sudah Selesai | — |
| 2 | Strategi Pemotongan (*Chunking*) | ⚠️ Belum Optimal | 🔴 Tinggi |
| 3 | Model Vektor (*Embedding*) | ⚠️ Belum Optimal | 🔴 Tinggi |
| 4 | Strategi Pencarian (*Retrieval*) | ❌ Belum Ada | 🟡 Menengah |
| 5 | Otak Chatbot (*System Prompt*) | ✅ Sudah Selesai | — |

---

## Detail Per Pilar

---

### ✅ Pilar 1 — Ekstraksi Data

**Status: SELESAI**

**File:** `app/services/pdf_processor.py`

Sistem ekstraksi sudah menggunakan pendekatan **3 lapis**:

1. **Layer 1 — PyMuPDF:** Membaca teks digital langsung dari PDF (cepat dan akurat).
2. **Layer 2 — Vision Model (qwen2.5vl):** Jika teks < 30 karakter (halaman scan/gambar), halaman dirender menjadi PNG dan dikirim ke model Vision OCR. Prompt sudah menggunakan teknik **Identifikasi Struktur Tabel (CoT Stage 1)**.
3. **Layer 3 — LLM Koreksi (qwen2.5:3b):** Teks kotor hasil OCR dikirim ke LLM pengoreksi. Prompt menggunakan teknik **Chain of Thought (CoT)** dengan blok `<analisis>` tersembunyi — model dipaksa "berpikir" dulu sebelum menulis tabel akhir. Blok analisis otomatis dihapus dari output final.

**Fitur Keamanan:**
- Jika Vision Model *timeout* → halaman dilewati, proses tetap jalan.
- Jika LLM Koreksi *timeout* → teks kotor asli digunakan (*fallback*), tidak ada data yang hilang.

---

### ⚠️ Pilar 2 — Strategi Pemotongan (*Chunking*)

**Status: BELUM OPTIMAL**

**File:** `app/services/embedding_service.py` (baris 28-29)

**Kondisi saat ini:**
```python
_CHUNK_SIZE = 500       # Ukuran chunk dalam karakter (~125 token)
_CHUNK_OVERLAP = 50     # Overlap antar chunk
```
Sistem menggunakan `RecursiveCharacterTextSplitter` yang **memotong teks secara acak** berdasarkan jumlah karakter.

**Masalah:**
Sebuah poin SOP yang panjang bisa terpotong di tengah jalan, membuat AI kehilangan konteks penting saat menjawab pertanyaan.

**Rekomendasi Perbaikan:**
Gunakan **Markdown-Aware Chunking** — potong berdasarkan struktur tabel (`|`) dan pemisah paragraf (`\n\n`), bukan sekadar jumlah karakter. Pastikan satu baris tabel tidak pernah terpotong menjadi dua chunk berbeda.

---

### ⚠️ Pilar 3 — Model Vektor (*Embedding*)

**Status: BELUM OPTIMAL**

**File:** `app/config.py` (baris 28-30)

**Kondisi saat ini:**
```python
EMBEDDING_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
```

Model `MiniLM-L12` adalah model lama berukuran kecil. Ia mampu menangani banyak bahasa, tetapi kualitas pemahamannya untuk Bahasa Indonesia dan istilah birokrasi masih terbatas.

**Catatan Penting:** PyTorch yang terinstal saat ini adalah **versi CPU**. Ini menyebabkan proses *embedding* berjalan di prosesor, bukan GPU (RTX 3050 yang tersedia). Ini membuat proses unggah dokumen jauh lebih lambat dari seharusnya.

**Rekomendasi Perbaikan (2 langkah):**

**Langkah A — Aktifkan GPU:**
```powershell
# Hapus versi CPU
pip uninstall torch torchvision torchaudio -y

# Instal versi GPU (CUDA 12.1 untuk RTX 3050)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

**Langkah B — Ganti Model Embedding:**
Ubah di `config.py` atau `.env`:
```
EMBEDDING_MODEL_NAME=intfloat/multilingual-e5-base
```
Model `multilingual-e5-base` jauh lebih paham konteks Bahasa Indonesia dan istilah birokrasi pemerintahan, sehingga pencarian RAG-nya lebih akurat.

---

### ❌ Pilar 4 — Strategi Pencarian (*Retrieval*)

**Status: BELUM ADA**

**File:** `app/services/rag_service.py` (baris 63-67)

**Kondisi saat ini:**
```python
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=_TOP_K,   # Hanya ambil 5 hasil teratas
    ...
)
```
Sistem saat ini hanya menggunakan **Vector Similarity Search** (pencarian berdasarkan kemiripan makna). Ini sudah cukup baik untuk pertanyaan umum, tetapi kurang presisi untuk pertanyaan spesifik seperti nomor undang-undang, nama jabatan, atau kode anggaran.

**Rekomendasi Perbaikan:**

- **Hybrid Search:** Gabungkan pencarian makna (vektor) dengan pencarian kata kunci tepat (BM25/full-text). Cocok untuk menemukan "Undang-Undang Nomor 17 Tahun 2003" atau "PA/KPA" yang spesifik.
- **Re-ranking:** Ambil 15 kandidat hasil, lalu gunakan model *Cross-Encoder* kecil untuk menyortir ulang dan memilih 5 yang paling relevan untuk dikirim ke LLM.

---

### ✅ Pilar 5 — Otak Chatbot (*System Prompt & Generation*)

**Status: SELESAI**

**File:** `app/services/rag_service.py` (baris 22-40)

*System Prompt* yang ada sudah ketat dan anti-halusinasi:

```
1. Jawab HANYA berdasarkan informasi yang ada di dalam konteks dokumen.
2. Selalu jawab dalam Bahasa Indonesia.
3. Sebutkan sumber dokumen (nomor halaman) yang relevan.
4. Jika tidak ada informasi → jawab "Maaf, saya tidak menemukan..."
5. Jangan mengarang atau berasumsi di luar konteks.
```

LLM di-set dengan `temperature=0.1` untuk menghasilkan jawaban yang konsisten dan tidak kreatif secara berlebihan.

---

## Rekomendasi Urutan Pengerjaan

Berdasarkan dampak vs. kemudahan implementasi:

```
1. [Prioritas Tinggi] Aktifkan GPU PyTorch  → Paling mudah, dampak kecepatan besar
2. [Prioritas Tinggi] Ganti Embedding Model → Mudah, dampak akurasi pencarian besar
3. [Prioritas Sedang]  Perbaiki Chunking    → Perlu analisis tabel Markdown
4. [Prioritas Rendah]  Tambah Hybrid Search → Kompleks, untuk tahap lanjut
```

---

*Dokumen ini dibuat secara otomatis berdasarkan analisis kode pada 17 Juli 2026.*
