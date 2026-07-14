# 👥 Pembagian Tugas & Tanggung Jawab Tim

## Proyek: Agentic IT Support Copilot

---

## 🟦 Dev 1 — Backend AI (Python)

**Branch:** `feat/python-ai`  
**Folder:** `python-ai/`

### ✅ Tugas Utama

| No  | Tugas                                                      | Prioritas |
| --- | ---------------------------------------------------------- | --------- |
| 1   | Setup FastAPI project structure                            | 🔴 Tinggi |
| 2   | Buat endpoint `POST /api/chat` (RAG pipeline)              | 🔴 Tinggi |
| 3   | Buat endpoint `POST /api/documents/upload`                 | 🔴 Tinggi |
| 4   | Buat endpoint `GET /api/documents` (list dokumen)          | 🔴 Tinggi |
| 5   | Buat endpoint `GET /api/documents/{id}/status`             | 🔴 Tinggi |
| 6   | Integrasi Ollama + Qwen2.5 sebagai LLM                     | 🔴 Tinggi |
| 7   | Integrasi ChromaDB sebagai vector database                 | 🔴 Tinggi |
| 8   | Integrasi embedding model (paraphrase-multilingual-MiniLM) | 🔴 Tinggi |
| 9   | Setup Celery + Redis untuk async processing PDF            | 🟡 Sedang |
| 10  | Integrasi Tesseract OCR untuk PDF scan                     | 🟡 Sedang |
| 11  | Buat LangChain RAG chain                                   | 🔴 Tinggi |
| 12  | Update status dokumen ke database (MySQL) setelah proses   | 🟡 Sedang |
| 13  | Buat `.env.example` lengkap                                | 🟢 Rendah |
| 14  | Tulis dokumentasi API (otomatis via FastAPI /docs)         | 🟢 Rendah |

### 📌 Tanggung Jawab

- Menjaga API tetap **running & accessible** selama development
- Share **base URL API** ke Dev 2 & Dev 3
- Kalau ada perubahan endpoint → **kabari Dev 2 & Dev 3 segera**
- Pastikan response format sesuai `docs/api_spec_agentic_copilot.md`

### ⚠️ Dependency

- Dev 2 & Dev 3 **bergantung** pada API ini — prioritas tertinggi

---

## 🟩 Dev 2 — Backend Web (Laravel)

**Branch:** `feat/laravel-admin`  
**Folder:** `laravel-admin/`

### ✅ Tugas Utama

| No  | Tugas                                                                    | Prioritas |
| --- | ------------------------------------------------------------------------ | --------- |
| 1   | Setup Laravel project + konfigurasi MySQL                                | 🔴 Tinggi |
| 2   | Buat migration tabel `documents` & `document_logs`                       | 🔴 Tinggi |
| 3   | Buat halaman **Login Admin**                                             | 🔴 Tinggi |
| 4   | Buat halaman **Daftar Dokumen** (list + status)                          | 🔴 Tinggi |
| 5   | Buat fitur **Upload PDF** (form + validasi)                              | 🔴 Tinggi |
| 6   | Integrasi hit API Python untuk trigger pemrosesan PDF                    | 🔴 Tinggi |
| 7   | Tampilkan **status real-time** dokumen (Menunggu/Diproses/Selesai/Gagal) | 🟡 Sedang |
| 8   | Buat halaman **Detail Dokumen** + preview PDF                            | 🟡 Sedang |
| 9   | Fitur **Replace/Update** dokumen lama                                    | 🟡 Sedang |
| 10  | Buat **log aktivitas** upload per dokumen                                | 🟢 Rendah |
| 11  | Polling status otomatis (AJAX) tanpa refresh halaman                     | 🟡 Sedang |
| 12  | Validasi file: hanya PDF, max size                                       | 🟡 Sedang |
| 13  | Setup `.env.example` dengan `AI_MICROSERVICE_URL`                        | 🟢 Rendah |

### 📌 Tanggung Jawab

- Koordinasi dengan **Dev 1** untuk format request/response API
- Pastikan `.env` sudah diisi `AI_MICROSERVICE_URL` dengan benar
- Menjaga keamanan: Auth admin wajib sebelum semua fitur
- Handle error jika API Python tidak respond

### ⚠️ Dependency

- Butuh API Python dari Dev 1 untuk: upload trigger & cek status

---

## 🟨 Dev 3 — Frontend (React)

**Branch:** `feat/react-widget`  
**Folder:** `react-widget/`

### ✅ Tugas Utama

| No  | Tugas                                                        | Prioritas |
| --- | ------------------------------------------------------------ | --------- |
| 1   | Setup React + Vite project                                   | 🔴 Tinggi |
| 2   | Buat komponen **ChatWidget** (bubble chat UI)                | 🔴 Tinggi |
| 3   | Buat komponen **MessageBubble** (pesan user & bot)           | 🔴 Tinggi |
| 4   | Buat komponen **SourceReference** (tampilkan sumber dokumen) | 🟡 Sedang |
| 5   | Integrasi `POST /api/chat` ke API Python                     | 🔴 Tinggi |
| 6   | Handle **loading state** saat menunggu jawaban AI            | 🟡 Sedang |
| 7   | Handle **error state** jika API tidak respond                | 🟡 Sedang |
| 8   | Implement **streaming response** (jika API support)          | 🟡 Sedang |
| 9   | Simpan **riwayat chat** di local state                       | 🟡 Sedang |
| 10  | Desain UI yang responsive (mobile & desktop)                 | 🟡 Sedang |
| 11  | Setup `VITE_API_URL` di `.env`                               | 🟢 Rendah |
| 12  | Clear chat / reset session                                   | 🟢 Rendah |

### 📌 Tanggung Jawab

- Koordinasi dengan **Dev 1** untuk format request/response chat API
- Pastikan `.env` sudah diisi `VITE_API_URL` dengan benar
- Widget ini **hanya untuk testing & demo** — bukan produksi
- Handle CORS error jika muncul (lapor ke Dev 1)

### ⚠️ Dependency

- Butuh endpoint `POST /api/chat` dari Dev 1

---

## 🔗 Diagram Ketergantungan

```
Dev 1 (Python)
     │
     ├──► Dev 2 (Laravel) — butuh: /api/documents/upload, /api/documents/{id}/status
     │
     └──► Dev 3 (React)   — butuh: /api/chat
```

---

## 📅 Timeline Saran

| Minggu | Dev 1 (Python)                          | Dev 2 (Laravel)                      | Dev 3 (React)                   |
| ------ | --------------------------------------- | ------------------------------------ | ------------------------------- |
| **1**  | Setup FastAPI, endpoint dasar, ChromaDB | Setup Laravel, auth, halaman upload  | Setup React, UI chat            |
| **2**  | Integrasi Celery, OCR, LLM              | Integrasi API Python, polling status | Integrasi API Python, streaming |
| **3**  | Bug fix, optimasi RAG                   | Bug fix, UI polish                   | Bug fix, UX polish              |
| **4**  | Testing end-to-end bersama              | Testing end-to-end bersama           | Testing end-to-end bersama      |

---

## 📋 Aturan Git Tim

```bash
# Setiap dev kerja di branch sendiri
git checkout feat/python-ai      # Dev 1
git checkout feat/laravel-admin  # Dev 2
git checkout feat/react-widget   # Dev 3

# Commit rutin (minimal 1x sehari)
git add .
git commit -m "feat: deskripsi perubahan"
git push origin feat/<nama-branch>

# Kalau butuh update dari main
git pull origin main
```

### Format Commit Message

| Prefix      | Kapan Dipakai      |
| ----------- | ------------------ |
| `feat:`     | Fitur baru         |
| `fix:`      | Bug fix            |
| `chore:`    | Setup, config      |
| `docs:`     | Update dokumentasi |
| `refactor:` | Refactor kode      |

---

## 📞 Acuan Bersama

> Semua dev **WAJIB** baca file ini sebelum mulai coding:
>
> - `docs/prd_agentic_copilot.md` — tujuan & scope proyek
> - `docs/api_spec_agentic_copilot.md` — kontrak API antar komponen
> - `docs/arsitektur_sistem_agentic_copilot.md` — arsitektur sistem keseluruhan
