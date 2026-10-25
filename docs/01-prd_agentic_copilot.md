# Dokumen Product Requirements Document (PRD) & Proposal Proyek KKP

## Proyek: Agentic IT Support Copilot (Layanan E-Government Diskominfotik)
### Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh

---

Dokumen ini menyatakan tujuan/kebutuhan produk. Implementasi dan hasil verifikasi saat ini mengacu ke spesifikasi API serta [status refactor](09-status-refactor-dan-verifikasi.md); target operasional pada PRD tidak menjadi hasil pengukuran otomatis.

## 📋 MATRIKS SPESIFIKASI KEBUTUHAN PRODUK (PRD)

| No | Komponen PRD | Rincian Spesifikasi Teknis & Operasional |
| :-: | :--- | :--- |
| **1** | **Nama Project** | **Agentic IT Support Copilot (Layanan E-Government Diskominfotik)** |
| **2** | **Masalah Utama** | **Ketergantungan tinggi pada WhatsApp (WA) Helpdesk & Widget Chat Statis**, yang memicu:<br>• **Beban Repetitif**: Staf lelah dan menghabiskan waktu menjawab FAQ dasar secara berulang kali.<br>• **Pelacakan Lambat**: Pengecekan status tiket/permohonan manual memicu antrean panjang.<br>• **UX Terputus & Pasif**: Pengguna harus keluar dari web untuk membuka WA, atau menghadapi widget live chat web (*tawk.to*) yang pasif, lambat merespons, dan berakhir dengan pemutusan sesi serta pengisian form offline tanpa jawaban solutif langsung. |
| **3** | **Tugas Utama (Tujuan)** | Mengotomatisasi FAQ layanan melalui pemrosesan dokumen SOP/regulasi format PDF (arsitektur **Retrieval-Augmented Generation / RAG**) dan menyediakan fitur pelacakan status tiket/layanan secara *real-time* melalui pemanggilan fungsi (**Agentic Tools & API Calling**), guna mengalihkan beban interaksi dasar dari staf ke dalam widget website yang aktif 24/7. |
| **4** | **Target Pengguna** | 1. **Perwakilan Instansi / SKPK / Publik (End-User)**: Menggunakan Copilot mandiri secara interaktif tanpa perlu repot mengantre di WA Helpdesk.<br>2. **Admin Diskominfotik (Internal)**: Terbantu karena pertanyaan dasar tersaring otomatis, sehingga staf dapat fokus pada eksekusi teknis jaringan/server dan pengelolaan basis pengetahuan AI. |
| **5** | **Backend & AI Engine** | 1. **Laravel 13 (PHP 8.3+)**: Sistem utama pengelola routing web, otentikasi Sanctum, governance database transaksional, dan penyedia Private API Gateway.<br>2. **Python 3.10+ (FastAPI)**: Microservice khusus komputasi AI (Hybrid Search, OCR Extraction, RRF Ranking, SSE Stream).<br>3. **Ollama**: Mesin inferensi LLM & Vision lokal yang ditentukan melalui konfigurasi layanan. |
| **6** | **Orkestrasi Agen Cerdas** | Bertindak sebagai **"Otak / Manajer Keputusan"** (*Decision Engine*) dengan alur kerja:<br>1. **Penerimaan Input**: Menerima pertanyaan pengguna dari widget web / API.<br>2. **Reasoning (Berpikir Logis)**: LLM menganalisis maksud dan entitas dalam kueri pengguna.<br>3. **Tool Calling (Eksekusi Alat Terarah)**:<br>   - *Jika pertanyaan seputar SOP/Regulasi*: Agen menggunakan **RAG Tool** untuk menarik konteks resmi dari Vector Database.<br>   - *Jika pertanyaan melacak tiket/layanan*: Agen menggunakan **API Tool** untuk menarik data JSON dari backend Laravel.<br>   - *Jika sapaan/chitchat lokal*: Menggunakan **Fast-Path Dialek Aceh**.<br>4. **Sintesis Jawaban**: Mengolah data mentah yang diperoleh dari tools menjadi balasan teks manusiawi yang ramah, santun, dan berbasis bukti resmi. |
| **7** | **Frontend** | **React.js 19 + Vite + Tailwind CSS v4**: Digunakan untuk membangun **Embedded Chat Widget** yang mengambang secara global di portal layanan publik, serta **Dashboard Admin & RAG Playground** terpadu. Komunikasi API bersifat *asynchronous* dengan dukungan streaming Server-Sent Events (SSE). Desain UI/UX dirancang profesional dan responsif. |
| **8** | **Database** | 1. **MySQL 8.0 (Relasional)**: Sistem data transaksional di Laravel untuk mencatat metadata dokumen, kategori SOP, status ekstraksi halaman, log telemetri performa, dan manajemen kunci API.<br>2. **ChromaDB (Vector Database)**: Database vektor persisten di lingkungan Python untuk menyimpan representasi angka (*dense embeddings*) 1024-dimensi dari dokumen PDF SOP kedinasan menggunakan model `BAAI/bge-m3`. |
| **9** | **Infrastruktur & Rilis** | Pengembangan di lingkungan **Linux (WSL2 / Ubuntu)** dengan version control **Git**. Rilis (*Deployment*) akhir menggunakan **Docker & Docker Compose** serta skrip peluncur mandiri (`start-all.sh`) agar seluruh klaster microservice stabil, portabel, dan siap dioperasikan pada server target Diskominfotik Kota Banda Aceh. |

---

## Kemampuan yang tersedia dan pembagian modul

Tabel ini menggantikan daftar fitur dan pembagian deliverable yang sebelumnya
terpisah. “Tersedia” berarti ada implementasinya; hasil pengujian dan batas
penggunaan mengacu pada [status verifikasi](09-status-refactor-dan-verifikasi.md).
Peta tanggung jawab kode ada pada
[panduan pemeliharaan](08-panduan-struktur-kode-dan-pemeliharaan.md).
Pembagian modul tidak menyatakan seluruh pekerjaan dilakukan oleh satu orang.

| Kemampuan tersedia | Modul penanggung jawab |
| --- | --- |
| Dashboard, kategori/dokumen, PDF viewer, editor koreksi, pratinjau chunk dan aksi korpus | React untuk presentasi/workflow form; Laravel untuk data dan gateway; Python untuk pemrosesan |
| Ekstraksi native/vision, jeda/lanjut, pembatalan per generasi dan indexing | Python FastAPI/Celery; Laravel menyimpan metadata dan mengoordinasikan permintaan |
| Hybrid retrieval dense/BM25, RRF, reranker sesuai konfigurasi, parent-child dan memori sesi | Python AI; model, ukuran chunk dan dimensi embedding mengikuti konfigurasi |
| Autentikasi sesi admin, Public API JSON/SSE dan pengelolaan API key | Laravel; React memakai cookie Sanctum, pemanggil publik memakai API key |
| Pengaturan prompt/model, parameter, Fast Path dan direktori | React untuk form; Laravel untuk persistensi; Python memakai konfigurasi efektif |
| Handoff, antrean tiket, balasan/lampiran dan integrasi WhatsApp/Telegram/webhook | Laravel dan Python untuk layanan; React untuk Live Chat dengan polling |
| Playground, trace/debug, log metadata, analitik dan health/hardware | Ketiga aplikasi sesuai batas kontrak; log Public API bukan transkrip percakapan |

Kuota per API key, permission granular, publikasi korpus atomik, dan deskew
presisi 0,25° bukan kemampuan yang sudah dinyatakan tersedia pada alur saat ini.
Pengiriman ke penerima kanal nyata, deployment server, mutu OCR/RAG dan beban
perlu pengujian tersendiri. Daftar tindak lanjut ada pada
[catatan verifikasi](09-status-refactor-dan-verifikasi.md#verifikasi-tambahan-dan-pekerjaan-produkoperasional).
Contoh profil model dan kebutuhan reindex dijelaskan di
[arsitektur RAG](05-arsitektur-rag-python-ai.md), bukan daftar versi terpisah.

## 🎯 Dampak dan Nilai Manfaat bagi Pemerintah Kota Banda Aceh

1. **Efisiensi Anggaran (Nol Biaya API Berulang)**: Tidak memerlukan langganan API berbayar luar negeri karena berjalan di atas model AI lokal berkinerja tinggi.
2. **Kebutuhan Privasi dan Penempatan Data**: Inferensi lokal menjadi sasaran deployment. Integrasi kanal, webhook, logging, konfigurasi jaringan, dan kebijakan penempatan data perlu diverifikasi pada lingkungan operasional instansi.
3. **Peningkatan Kualitas SPBE (Sistem Pemerintahan Berbasis Elektronik)**: Mempercepat indeks kepuasan masyarakat terhadap layanan komunikasi dan informatika di Kota Banda Aceh dengan target latensi yang diukur pada mesin serta model deployment; waktu respons bergantung jalur tool, retrieval, dan inferensi.
