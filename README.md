# 🤖 Agentic IT Support Copilot

Sistem chatbot berbasis AI lokal — memungkinkan penelolaan basis pengetahuan (dokumen PDF) secara mandiri tanpa modifikasi kode.

---

## 📦 Struktur Proyek

```
agentic-ai/
├── docs/                          # Dokumentasi proyek
│   ├── prd_agentic_copilot.md
│   ├── api_spec_agentic_copilot.md
│   ├── arsitektur_sistem_agentic_copilot.md
│   ├── rencana_fitur_agentic_copilot.md
│   └── pembagian_tugas_tim.md
├── python-ai/                     # 🟦 AI Microservice (FastAPI)
├── laravel-admin/                 # 🟩 Dashboard Admin (Laravel)
└── react-widget/                  # 🟨 Chat Widget (React — testing only)
```

---

## 🏗️ Tech Stack

| Komponen              | Teknologi                             |
| --------------------- | ------------------------------------- |
| Dashboard Admin       | Laravel (PHP)                         |
| AI Microservice       | Python + FastAPI                      |
| Chat Widget (Testing) | React.js + Vite                       |
| LLM Engine            | Ollama + Qwen2.5-Instruct             |
| Embedding Model       | paraphrase-multilingual-MiniLM-L12-v2 |
| Vector Database       | ChromaDB                              |
| AI Orchestration      | LangChain                             |
| OCR Engine            | Tesseract OCR                         |
| Queue System          | Celery + Redis                        |
| Database              | MySQL                                 |
| Containerization      | Docker Compose                        |

---

## 🌿 Struktur Branch

| Branch               | Isi                        | Developer |
| -------------------- | -------------------------- | --------- |
| `main`               | Dokumentasi + `.gitignore` | Semua     |
| `feat/python-ai`     | AI Microservice (FastAPI)  | Dev 1     |
| `feat/laravel-admin` | Dashboard Admin (Laravel)  | Dev 2     |
| `feat/react-widget`  | Chat Widget (React)        | Dev 3     |

---

## 🚀 Cara Menjalankan (Development)

### Prasyarat

Pastikan sudah terinstall:

- Python 3.10+
- PHP 8.2+ & Composer
- Node.js 18+ & npm
- Redis
- MySQL
- Ollama
- Tesseract OCR

---

### 🟦 1. Python AI Microservice

```bash
cd python-ai/

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env sesuai konfigurasi lokal

# Jalankan FastAPI (Terminal 1)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Jalankan Celery Worker (Terminal 2)
celery -A app.tasks worker --loglevel=info
```

> 🌐 API: `http://localhost:8000`  
> 📖 API Docs: `http://localhost:8000/docs`

---

### 🟩 2. Laravel Admin Dashboard

```bash
cd laravel-admin/

# Install dependencies
composer install
npm install

# Setup environment
cp .env.example .env
php artisan key:generate

# Isi .env — wajib diisi:
# DB_DATABASE, DB_USERNAME, DB_PASSWORD
# AI_MICROSERVICE_URL=http://localhost:8000

# Setup database
php artisan migrate

# Jalankan server (Terminal 3)
php artisan serve --port=8080

# Jalankan Vite (Terminal 4)
npm run dev
```

> 🌐 Dashboard: `http://localhost:8080`

---

### 🟨 3. React Chat Widget

```bash
cd react-widget/

# Install dependencies
npm install

# Setup environment
cp .env.example .env
# Isi VITE_API_URL=http://localhost:8000

# Jalankan dev server (Terminal 5)
npm run dev
```

> 🌐 Widget: `http://localhost:5173`

---

### 🔴 4. Ollama (LLM Engine)

```bash
# Install Ollama terlebih dahulu: https://ollama.ai

# Pull model (Fase 1 - Development)
ollama pull qwen2.5:3b

# Jalankan (Terminal 6)
ollama serve
```

---

## 📋 Urutan Menjalankan

```
1. redis-server                              # Queue
2. ollama serve                              # LLM
3. uvicorn app.main:app --reload             # FastAPI
4. celery -A app.tasks worker                # Worker
5. php artisan serve --port=8080             # Laravel
6. npm run dev  (di react-widget/)           # React
```

---

## 🔌 Port yang Digunakan

| Service          | Port    |
| ---------------- | ------- |
| FastAPI (Python) | `8000`  |
| Laravel Admin    | `8080`  |
| React Widget     | `5173`  |
| Redis            | `6379`  |
| MySQL            | `3306`  |
| Ollama           | `11434` |

---

## 💻 Setup Beda Komputer (Tim)

Jika setiap developer bekerja di komputer berbeda dalam **1 jaringan WiFi yang sama**:

1. **Dev 1** jalankan FastAPI dengan `--host 0.0.0.0` agar bisa diakses dari luar
2. **Dev 2** isi `.env` Laravel: `AI_MICROSERVICE_URL=http://<IP-Dev1>:8000`
3. **Dev 3** isi `.env` React: `VITE_API_URL=http://<IP-Dev1>:8000`

```bash
# Cari IP komputer (Linux/WSL)
ip addr show | grep "inet "

# Cari IP komputer (Windows)
ipconfig
```

---

## 📁 Dokumentasi

| File                                                                                | Deskripsi                            |
| ----------------------------------------------------------------------------------- | ------------------------------------ |
| [`prd_agentic_copilot.md`](docs/prd_agentic_copilot.md)                             | Product Requirements Document        |
| [`api_spec_agentic_copilot.md`](docs/api_spec_agentic_copilot.md)                   | Spesifikasi API antar komponen       |
| [`arsitektur_sistem_agentic_copilot.md`](docs/arsitektur_sistem_agentic_copilot.md) | Arsitektur sistem keseluruhan        |
| [`rencana_fitur_agentic_copilot.md`](docs/rencana_fitur_agentic_copilot.md)         | Rencana pengembangan fitur           |
| [`pembagian_tugas_tim.md`](docs/pembagian_tugas_tim.md)                             | Pembagian tugas & tanggung jawab tim |

---

## 🤝 Kontribusi

1. Clone repo: `git clone https://github.com/nftxvn/agentic-chatbot.git`
2. Checkout branch sesuai tugasmu:
   ```bash
   git checkout feat/python-ai      # Dev 1
   git checkout feat/laravel-admin  # Dev 2
   git checkout feat/react-widget   # Dev 3
   ```
3. Baca dokumen di folder `docs/` sebelum mulai coding
4. Commit minimal 1x sehari dengan format: `feat: deskripsi singkat`
5. Push ke branch masing-masing: `git push origin feat/<nama-branch>`

---

## 📞 Kontak & Koordinasi

> **Penting:** Dev 1 (Python) harus **share URL API & format response** ke Dev 2 & Dev 3 di **hari pertama**, bahkan sebelum logic selesai — cukup return dummy response dulu supaya tim lain bisa mulai coding integrasi.
