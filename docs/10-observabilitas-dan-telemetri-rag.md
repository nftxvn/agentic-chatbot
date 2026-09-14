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
* **Aktivitas:** Mengkueri basis data vektor *ChromaDB* (Dense Vector) dan indeks leksikal *RankBM25* (Sparse Retrieval).
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

Setiap respons asisten dilengkapi kartu informasi telemetri yang diekstrak dari event `telemetry`:

| Parameter | Sumber Data | Keterangan |
| :--- | :--- | :--- |
| **Grounding Status** | Logika Guard / RAG Context | Menandai apakah jawaban bersumber dari dokumen SOP (*Terjawab dari Korpus*) atau di luar dokumen (*Fallback*). |
| **Model Engine** | Konfigurasi AI | Nama model LLM yang menjalankan inferensi (contoh: `qwen3:8b`). |
| **Beban Token Konteks** | Perhitungan Tokenizer | Estimasi jumlah token pada prompt sistem dan konteks dokumen (contoh: `~2.450 token`). |
| **Tautan Chunks Terambil** | `debug_chunks` | Tautan interaktif yang mengarahkan langsung ke tab *Inspeksi Retrieval*. |
| **Latensi End-to-End** | Timestamp Komputasi | Durasi total pemrosesan dari pengiriman pertanyaan hingga token terakhir (milidetik). |

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

### Klasifikasi Status:
1. **Normal / Siap (Hijau):** Seluruh 4 dependensi beroperasi normal.
2. **Terdegradasi (Kuning):** Salah satu dependensi sekunder (misal Redis atau MySQL) mengalami gangguan, namun endpoint inti masih menerima koneksi.
3. **Offline (Merah):** Layanan mikroservis Python AI atau model Ollama tidak dapat dihubungi.

---

## 6. Prosedur Operasional & Skrip Manajemen Layanan

Seluruh layanan terintegrasi dapat dijalankan dan dimatikan secara bersih melalui skrip terpusat di direktori utama:

```bash
# Menyalakan seluruh layanan (MySQL, Redis, Ollama, Python AI 8080, Celery, Laravel 8000, Vite 5173)
./start-all.sh

# Menghentikan seluruh layanan secara bersih
./stop-all.sh
```
