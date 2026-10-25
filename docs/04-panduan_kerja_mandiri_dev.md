# Panduan Kerja Mandiri dan Integrasi Lokal

Frontend, Laravel, dan Python dapat diuji terpisah menggunakan kontrak API serta dependency tiruan. Kontrak bersama berada di [spesifikasi API](03-api_spec_agentic_copilot.md); pembagian modul ada di [panduan pemeliharaan](08-panduan-struktur-kode-dan-pemeliharaan.md).

## Python AI

Dari direktori `python-ai`, gunakan environment yang dependensinya sudah terpasang:

```bash
venv/bin/python -m unittest discover -s tests
venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Sesuaikan path `venv` bila environment bernama `.venv`. Titik masuk API adalah `app.main:app`. Chat sinkron memakai `POST /api/chat/message`; streaming memakai `POST /api/chat/stream`. Endpoint dokumen menggunakan prefix `/api/docs`, termasuk `POST /api/docs/{id}/extraction`.

Tes menggantikan koneksi database, broker, model, dan HTTP eksternal dengan mock. Menjalankan API untuk integrasi membutuhkan `.env` yang sesuai. Health check publik `/health` dan `/api/health` benar-benar membaca ChromaDB, MySQL, Redis, serta daftar model Ollama; HTTP 503 menandakan salah satu probe gagal. OCR, embedding, dan worker nyata memerlukan layanan serta model terkait.

## Laravel tanpa server Python

Jalankan dari `laravel-admin`:

```bash
php artisan test
```

Tes fitur memakai SQLite in-memory. Gunakan HTTP fake pada URL Python yang benar agar tes tidak memerlukan route mock di aplikasi:

```php
use App\Services\AiMicroserviceClient;
use Illuminate\Support\Facades\Http;

config([
    'services.ai_microservice.url' => 'http://ai.example.test',
    'services.ai_microservice.token' => 'synthetic-test-token',
]);
Http::preventStrayRequests();
Http::fake([
    'http://ai.example.test/api/docs/42/extraction' => Http::response([
        'document_id' => 42,
        'status' => 'antre',
        'halaman_total' => 2,
        'halaman_selesai' => 0,
    ], 202),
]);

$result = (new AiMicroserviceClient)->mulaiEkstraksi(42);
$this->assertTrue($result['success']);
Http::assertSentCount(1);
```

Contoh dijalankan di dalam `Tests\TestCase` agar container dan facade tersedia. Gunakan `Storage::fake('local')` untuk berkas serta fake/mock khusus transport SSE pada `Channels/AiChatGateway`; `Http::fake` tidak mencegat cURL mentah. Contoh lengkap tersedia di `DocumentPipelineContractTest`, `AiMicroserviceClientContractTest`, dan tes gateway kanal.

Untuk integrasi ke Python yang berjalan, sesuaikan `AI_SERVICE_URL` dan `AI_SERVICE_TOKEN` pada `.env` Laravel. `config/services.php` juga menerima `INTERNAL_API_TOKEN` sebagai fallback token. Di Docker, gunakan nama host service pada `docker-compose.yml`; `127.0.0.1` merujuk container itu sendiri. Konfigurasi tidak perlu diubah untuk menjalankan tes HTTP fake di atas.

## Frontend dengan data sintetis

Dari `admin-frontend`:

```bash
npm run build
npm run dev
```

SPA admin memanggil Laravel melalui `src/api/client.js`, memakai cookie sesi Sanctum. Target proxy Vite ditentukan oleh `VITE_LARAVEL_URL` dan `VITE_AI_URL` pada `vite.config.js`. Frontend admin tidak membaca `VITE_API_URL` sebagai pengganti kedua nilai tersebut.

Untuk memeriksa editor secara terisolasi, gunakan fixture komponen dengan router React, CSS aplikasi, dan API sintetis. Contoh intersepsi daftar halaman dengan Playwright:

```javascript
await page.route('**/api/documents/42/pages?*', route => route.fulfill({
  status: 200,
  contentType: 'application/json',
  body: JSON.stringify({
    success: true,
    data: {
      document_id: 42,
      jumlah: 1,
      halaman: [{ page_number: 1, text: 'Teks sintetis', diperiksa: false }],
      halaman_mencurigakan: [],
    },
  }),
}));
```

Fixture juga perlu menyediakan endpoint lain yang dipakai layar tersebut, misalnya ukuran/gambar halaman dan pratinjau chunk. Mock browser tidak menggantikan autentikasi atau layanan yang belum diintersepsi. Pertahankan bentuk JSON Laravel, termasuk pembungkus `success`/`data`; gunakan fixture terpisah dari JSX aplikasi.

## Pemeriksaan gabungan

Runner layanan nyata dapat dijalankan dari root repository:

```bash
python-ai/venv/bin/python scripts/integration/run_document_pipeline.py
```

Runner membuat instance MySQL/Redis, storage Laravel, dan indeks Chroma baru
pada direktori sementara; FastAPI, Celery, dan Laravel memakai konfigurasi run
tersebut. Model Ollama lokal yang sudah terpasang dipakai bersama. Tidak ada
launcher utama, purge antrean bersama, atau penerima kanal eksternal yang
dipanggil. Prasyarat, profil model, artefak, serta batas pembuktian dijelaskan
di [panduan runner integrasi](../scripts/integration/README.md).

Alur smoke test mencakup login cookie/CSRF, PDF citra dan native, pause/resume,
koreksi, preview, embedding, serta gateway chat JSON/SSE. Pemeriksaan browser,
handoff dan pengiriman kanal tetap merupakan tahap tersendiri.

| Batas integrasi | Pemeriksaan |
| --- | --- |
| Browser → Laravel | Login Sanctum, load/save form, validasi error, fokus, scroll, dan navigasi |
| Laravel → Python | Token internal, path/metode, timeout, JSON, fallback, serta byte SSE |
| Python → Celery/Redis | Nama task, retry/requeue, jeda/resume, progres, dan worker aktif |
| Python → model/penyimpanan | OCR PDF nyata, metadata halaman, embedding, retrieval dan jawaban grounded |
| Tiket → kanal keluar | Gunakan penerima/endpoint pengujian untuk balasan dan webhook |

Simpan baseline request/response dan tampilan pada route, data, tema, serta ukuran layar yang sama. Catat hasil dengan dependency tiruan terpisah dari integrasi layanan nyata. Build dan tes unit yang lulus belum membuktikan mutu OCR atau jawaban model.
