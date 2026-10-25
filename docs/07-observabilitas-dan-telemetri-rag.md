# Observabilitas, Telemetri, dan Pemantauan Klaster RAG

Dokumen ini menjelaskan arsitektur sistem observabilitas, pelacakan pipa inferensi (*pipeline tracing*), telemetri performa, dan pemantauan kesehatan klaster (*health status monitoring*) yang diterapkan pada platform Central RAG Engine Diskominfotik Kota Banda Aceh.

---

## 1. Arsitektur Observabilitas & Keandalan RAG

Sistem ini menerapkan standar observabilitas menyeluruh untuk memberikan transparansi penuh kepada administrator terkait alur pemrosesan pertanyaan pengguna dari hulu ke hilir.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND ADMIN & PLAYGROUND                       │
│  - Live Pipeline Stepper (Retrieval -> RRF Fusion -> LLM Inference)         │
│  - Singleton Background Service (Persisten lintas navigasi menu)             │
│  - Telemetri Jawaban (Grounding Status, Token Konteks, Latensi Milidetik)   │
│  - Topbar Cluster Health Indicator (FastAPI, Ollama, ChromaDB, DB, Redis)    │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │ SSE Stream + Health Polling
                                       ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         PYTHON AI MICROSERVICE (Port 8080)                   │
│  - Event Emitter: type='trace', type='telemetry', type='chunk', type='debug' │
│  - Health Check Endpoint (/health & /api/health) dengan active ping          │
│  - Hybrid Search & Reciprocal Rank Fusion (RRF) Scorer                       │
│  - Model LLM Lokal: Ollama qwen3:8b + Embedding BAAI/bge-m3                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Tiga Tahap Pelacakan Pipeline (3-Stage Live Tracing)

Saat pertanyaan dikirimkan melalui Simulator Obrolan (*RAG Playground*), backend mikroservis memancarkan event bertipe `trace` secara bertahap melalui *Server-Sent Events (SSE)*:

### Tahap 1: Retrieval Korpus Dokumen
* **Event:** `{"type": "trace", "stage": "retrieval", "step": 1, "total_steps": 3, "label": "Pencarian Vektor & BM25", "detail": "..."}`
* **Aktivitas:** Mengkueri database vektor *ChromaDB* (Dense Vector) dan indeks leksikal *RankBM25* (Sparse Retrieval).
* **Metadata Tambahan:** Menghasilkan event bertipe `debug` yang memuat potongan teks mentah (*chunks*), skor similaritas, dan nama dokumen rujukan.

### Tahap 2: Reciprocal Rank Fusion (RRF)
* **Event:** `{"type": "trace", "stage": "ranking", "step": 2, "total_steps": 3, "label": "Reciprocal Rank Fusion", "detail": "..."}`
* **Aktivitas:** Menggabungkan peringkat dari pencarian vektor dan leksikal menggunakan formula $RRF(d) = \sum \frac{1}{k + r_i(d)}$ untuk menyaring potongan teks yang paling relevan serta melakukan deduplikasi.

### Tahap 3: Inferensi Model Bahasa (LLM Generation)
* **Event:** `{"type": "trace", "stage": "generation", "step": 3, "total_steps": 3, "label": "Inferensi LLM", "detail": "..."}`
* **Aktivitas:** Menyusun jendela konteks (*context window*), menghitung kebutuhan token, dan mengirimkan prompt ke mesin Ollama `qwen3:8b`.
* **Transisi:** Saat token pertama tiba, antarmuka langsung mengalirkan teks jawaban secara mulus.

---

## 3. Singleton Background Service (Ketahanan Navigasi SPA)

Untuk mencegah pembatalan proses inferensi ketika administrator berpindah halaman di dalam Admin Panel, logika *streaming* dikelola oleh singleton service independen (`src/services/aiChatService.js`):

* **Manajemen Siklus Hidup:** Request `fetch SSE` diikat pada modul latar belakang, bukan pada komponen React yang dapat mengalami *unmount*.
* **Sinkronisasi Session Storage:** State pesan percakapan, ID sesi sandbox, dan riwayat *retrieved chunks* disinkronisasikan ke `sessionStorage` secara otomatis.
* **Reaktivitas UI:** Komponen `ChatbotSettingsPage` berlangganan (*subscribe*) ke service saat aktif dan langsung menerima status terkini tanpa memutus alur streaming.

---

## 4. Metadata Telemetri & Explainability Jawaban

Pada RAG Playground, metadata `telemetry` yang tersedia dipetakan oleh `aiChatService` ke pesan asisten. Kartu menunjukkan profil/model, estimasi token konteks, jumlah chunk, flag fallback, dan durasi total; field yang tersedia bergantung jalur jawaban dan permintaan debug.

| Parameter | Sumber data | Makna |
| --- | --- | --- |
| Flag fallback | `is_fallback` pada metadata | Label jalur/fallback menurut layanan; bukan skor kebenaran jawaban atau bukti koneksi terputus. |
| Model/profil | `model_name` pada metadata | Nama profil yang dilaporkan layanan; jawaban terprogram dapat selesai tanpa inferensi LLM. |
| Token konteks | `context_tokens` | Estimasi dari layanan, bukan pengukuran tagihan/tokenizer yang dijamin persis. |
| Chunk | `chunks_count` dan metadata debug | Jumlah/konteks retrieval yang dapat diinspeksi ketika debug tersedia. |
| Durasi total | `elapsedMs` pada klien | Waktu dari pengiriman sampai stream selesai menurut klien; kartu tidak memecah latensi per tahap. |

Event trace menunjukkan tahap yang dilalui, sedangkan JSON Public API dan log admin memiliki kontrak metadata sendiri. Stream publik tidak meminta debug secara otomatis.

---

## 5. Pemantauan Kesehatan Klaster (System Health Indicator)

Widget status kesehatan disematkan pada bar navigasi atas (*topbar*) panel admin (`src/components/UI/SystemHealthIndicator.jsx`) dan melakukan verifikasi berkala setiap 30 detik:

### Endpoint Pemantauan:
* **URL:** `GET /api/ai/health` (melalui proxy) atau `GET http://localhost:8080/health`
* **Metode Verifikasi:** Pengecekan aktif (*active ping*) ke seluruh subsistem dependen:

```json
{
  "status": "healthy",
  "service": "ai-service",
  "model": "qwen3:8b",
  "checks": {
    "chromadb": { "ok": true, "detail": "76 vektor" },
    "mysql": { "ok": true, "detail": "agentic_copilot" },
    "redis": { "ok": true, "detail": "PING" },
    "ollama": { "ok": true, "detail": "qwen3:8b" }
  }
}
```

### Kontrak status dan cache

Python menyediakan alias publik `GET /health` dan `GET /api/health`. Semua probe berhasil menghasilkan HTTP 200 dengan `status=healthy`; satu probe gagal menghasilkan HTTP 503 dengan `status=degraded`, termasuk bila Ollama gagal. Kedua alias berbagi cache per proses selama 5 detik untuk hasil sehat maupun gagal. Koleksi ChromaDB dengan 0 vektor tetap sehat bila dapat dibaca.

Probe dijalankan berurutan oleh `app/services/diagnostics/health.py`. Kegagalan satu probe tidak menghentikan probe berikutnya; respons publik hanya memuat nama kelas exception pada `detail`. Redis dan request Ollama memakai timeout 3 detik; tidak ada batas global 3 detik untuk keseluruhan health check atau timeout baru untuk ChromaDB/MySQL. Probe ini tidak memeriksa apakah worker Celery sedang mengonsumsi antrean.

`SystemHealthIndicator` menerima JSON dari HTTP 200 maupun 503. Status `offline` dipakai ketika fetch/pembacaan respons gagal atau kode HTTP berbeda; kegagalan Ollama yang masih dilaporkan lewat HTTP 503 tetap berstatus `degraded`. Angka layanan aktif di UI menghitung empat kelompok: FastAPI, Ollama, ChromaDB, serta gabungan MySQL+Redis. Baris gabungan aktif hanya bila kedua probe berhasil. Penjelasan ini mengikuti komponen yang ada; tampilan dan polling 30 detik dipertahankan.

### Diagnostik perangkat keras

`GET /api/health/hardware` memerlukan bearer token internal, termasuk saat cache tersedia. Handler/cache berada di `app/routers/health.py`; pembacaan OS, RAM, NVIDIA, Ollama, dan kalkulasi kapasitas berada di `services/diagnostics/hardware.py`. Cache efektif 3 detik dan dapat dilewati dengan `nocache=true`. Konstanta lama `_MESIN_CACHE_TTL=10` tidak dipakai kondisi cache.

Parameter `model` pada respons yang masih tercache hanya menghitung ulang `model_fit`; konfigurasi dan rekomendasi tetap berasal dari snapshot awal. Untuk snapshot penuh baru gunakan `nocache=true`. Pembacaan NVIDIA memakai GPU pertama dan ukuran memori memakai MiB; rekomendasi merupakan estimasi berbasis aturan, bukan ukuran throughput inferensi.

Kontrak HTTP/cache, parser probe, dan estimasi diperiksa dengan dependency tiruan pada `python-ai/tests/test_health_contract.py`. Pemeriksaan kondisi mesin dan konektivitas layanan nyata tetap perlu dilakukan pada lingkungan operasional.

---

## 6. Prosedur Operasional & Skrip Manajemen Layanan

Seluruh layanan terintegrasi dapat dijalankan dan dimatikan secara bersih melalui skrip terpusat di direktori utama:

```bash
# Menyalakan seluruh layanan (MySQL, Redis, Ollama, Python AI 8080, Celery, Laravel 8000, Vite 5173)
./start-all.sh

# Menghentikan seluruh layanan secara bersih
./stop-all.sh
```
