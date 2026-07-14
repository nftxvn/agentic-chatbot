# Dokumen PRD: Agentic IT Support Copilot (Versi 2.0)

## 1. Nama Project

**Agentic IT Support Copilot** (Layanan E-Government Diskominfotik)

## 2. Masalah Utama

Ketergantungan tinggi pada WhatsApp (WA) Helpdesk yang memicu:

- **Beban Repetitif:** Staf lelah menjawab FAQ dasar berulang kali.
- **Pelacakan Lambat:** Pengecekan tiket manual memicu antrean.
- **UX Terputus:** Pengguna harus keluar web untuk membuka WA.
- **Informasi Usang:** Dokumen panduan pemerintahan sering berubah/diperbarui, membuat jawaban manual rentan salah.

## 3. Tugas Utama (Tujuan)

Mengotomatisasi FAQ layanan melalui pemrosesan dokumen PDF (arsitektur **RAG dengan OCR**) dan fitur pelacakan status tiket _real-time_ via API (**Agentic Tools / Semantic Routing**), mengalihkan beban interaksi ke _widget_ website yang terkelola secara dinamis.

## 4. Target Pengguna

1. **Perwakilan Instansi/SKPK (End-User):** Menggunakan _Copilot_ mandiri via web.
2. **Admin Diskominfotik (Internal):** Bertindak sebagai _Knowledge Manager_. Memiliki akses ke _Control Panel_ di Laravel untuk mengunggah, memperbarui, dan menghapus dokumen PDF panduan AI tanpa menyentuh _coding_.

## 5. Backend & AI Engine

1. **Laravel (PHP):** Sistem utama pengelola web, penyedia API tiket, dan _Dashboard Admin_ pengelola PDF.
2. **Python (FastAPI/Flask):** _Microservice_ pemroses AI, dilengkapi pustaka **Tesseract OCR** untuk mengekstrak PDF hasil _scan_.
3. **Ollama (LLM Lokal):** Menjalankan model AI. Disiapkan skenario _Small Language Model (SLM)_ seperti Qwen 2.5 1.5B/3B atau Llama 3.2 jika server Diskominfotik hanya mengandalkan CPU (tanpa GPU).

## 6. Orkestrasi & Logika

1. **Semantic Routing / Tool Calling:** Menggunakan LangChain/LlamaIndex untuk menganalisis niat pengguna (memilih fungsi Cek Tiket API vs Tanya SOP via RAG).
2. **Dynamic Document Update:** Alur kerja asinkronus (Queue) di Python yang membedakan PDF teks/gambar (OCR), memotong data (_chunking_), dan secara otomatis menimpa (_overwrite_) dokumen lama di Vector DB berdasarkan metadata ID.

## 7. Frontend

**React.js** digunakan untuk membangun _Embedded Chat Widget_ yang mengambang secara global. Komunikasi API bersifat _asynchronous_. Desain UI/UX dirancang via **Figma**.

## 8. Database

1. **MySQL / PostgreSQL:** Di Laravel untuk data tiket dan pengguna.
2. **ChromaDB / FAISS:** _Vector Database_ di Python. Menggunakan **Metadata Tagging** (`"nama_file": "SOP_Jaringan_2026"`) untuk mempermudah penghapusan/penimpaan vektor dokumen lama.

## 9. Infrastruktur & Rilis

Pengembangan di Linux (WSL) dengan Git. Rilis menggunakan Docker agar _microservice_ stabil. Menggunakan _Queue System_ (Redis/RabbitMQ atau database queue) agar proses OCR PDF di belakang layar tidak membuat _browser_ Admin _loading_ lama.

## 10. Roadmap V2.0 (Pengembangan Lanjutan)

- **Multi-PDF Support:** Memungkinkan RAG membaca puluhan dokumen silang.
- **Quick Previews:** Menampilkan kutipan dokumen asli (sumber referensi) di bawah jawaban AI.
- **Automated Evaluation:** Menggunakan pustaka `ragas` untuk menilai kualitas/halusinasi AI secara otomatis.
- **Feedback Learning Loop:** Tombol "Puas/Tidak" di widget untuk bahan evaluasi Admin.
