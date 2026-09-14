# Panduan Menjalankan Proyek dengan Docker & Docker Compose

Panduan ini ditujukan agar seluruh tim / rekan kerja dapat menjalankan sistem **Agentic AI & Admin Copilot** di komputer masing-masing secara praktis, fleksibel, dan terisolasi.

---

## 1. Prasyarat Sistem

1. **Docker Desktop** sudah terpasang dan berjalan:
   - [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
   - Di Windows: Pastikan opsi **WSL 2 backend** diaktifkan pada pengaturan Docker Desktop.
2. **GPU NVIDIA (Opsional / Otomatis Terdeteksi)**:
   - Jika memiliki GPU NVIDIA, Docker Desktop akan otomatis memanfaatkannya untuk akselerasi LLM & AI.

---

## 2. Cara Menjalankan

### Langkah A: Nyalakan Seluruh Layanan
Buka terminal di root folder proyek, lalu jalankan:
```bash
docker compose up -d --build
```

Docker akan secara otomatis:
- Mengunduh & menyalakan MySQL 8.0 dan Redis 7.
- Mengompilasi PHP 8.3 dengan ekstensi lengkap (`intl`, `pdo_mysql`, `redis`, `gd`, dll.).
- Menjalankan migrasi database Laravel secara otomatis.
- Menginstal dependensi Python AI & ChromaDB.
- Menjalankan Celery Worker untuk pemrosesan OCR Vision & PDF di latar belakang.
- Menjalankan Frontend Admin React (Vite) dengan Hot-Reload.

---

### Langkah B: Pilih & Unduh Model AI ke Ollama Sesuai Selera

Teman Anda bebas menentukan model LLM yang ingin digunakan sesuai kapasitas VRAM/RAM komputernya.

1. **Unduh model ke Ollama** (jalankan via terminal):
   ```bash
   # Contoh jika ingin model 7B standar:
   docker compose exec ollama ollama pull qwen2.5:7b
   docker compose exec ollama ollama pull qwen2.5vl:7b-q4_K_M

   # Atau jika ingin model ringan (3B):
   docker compose exec ollama ollama pull qwen2.5:3b
   ```

2. **(Opsional) Menyesuaikan Model di Konfigurasi**:
   Jika menggunakan model selain default, cukup buat berkas `.env` di root proyek:
   ```env
   LLM_MODEL_NAME=qwen2.5:3b
   VISION_MODEL_NAME=qwen2.5vl:7b-q4_K_M
   ```
   Lalu restart service Python AI:
   ```bash
   docker compose restart python-ai celery-worker
   ```

---

## 3. Alamat Akses Layanan di Browser

| Layanan | Alamat URL | Keterangan |
| :--- | :--- | :--- |
| **Frontend Admin UI** | [http://localhost:5173](http://localhost:5173) | Antarmuka Admin Panel & Manajemen Dokumen |
| **Backend Laravel API** | [http://localhost:8000](http://localhost:8000) | REST API & Sanctum Authentication |
| **Python AI Microservice** | [http://localhost:8080](http://localhost:8080) | FastAPI RAG Engine & Stream Chat |
| **Ollama Local Engine** | [http://localhost:11434](http://localhost:11434) | API Engine LLM lokal |

---

## 4. Cara Mengedit Kode (Live Development)

Semua folder kode lokal (`admin-frontend/`, `laravel-admin/`, `python-ai/`) terhubung secara langsung (*Bind Mount*) ke dalam container:
* **Frontend React (Vite)**: Mengedit file `.jsx` / `.css` langsung ter-update di browser (*Hot Module Replacement*).
* **Python FastAPI**: Mengedit file `.py` di `python-ai/` langsung otomatis di-reload oleh Uvicorn (*Auto Reload*).
* **Laravel**: Mengedit controller/model/route langsung aktif saat request berikutnya dikirim.

---

## 5. Perintah Berguna Sehari-hari

* **Melihat status semua container**:
  ```bash
  docker compose ps
  ```
* **Melihat log container secara realtime**:
  ```bash
  docker compose logs -f
  # Atau spesifik untuk satu service:
  docker compose logs -f python-ai
  docker compose logs -f celery-worker
  docker compose logs -f laravel-backend
  ```
* **Menghentikan seluruh layanan**:
  ```bash
  docker compose down
  ```
* **Menghapus dan me-reset seluruh database (jika ingin mulai dari awal)**:
  ```bash
  docker compose down -v
  ```
