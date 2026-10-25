# Integrasi dokumen pada layanan sementara

Jalankan dari root repository menggunakan environment Python yang sudah terpasang:

```bash
python-ai/venv/bin/python scripts/integration/run_document_pipeline.py
# Tambahkan skenario cancel pada layanan sementara yang sama:
python-ai/venv/bin/python scripts/integration/run_document_pipeline.py --cancellation
```

Runner memerlukan `mysqld`, `redis-server`, PHP beserta dependency Laravel,
dependency Python aplikasi, dan Ollama lokal. Model bawaan pengujian adalah
`qwen2.5vl:7b-q4_K_M`, `qwen2.5:3b`, dan `bge-m3:latest`; model harus sudah
terpasang. `--vision-model`, `--chat-model`, dan `--ollama-url` tersedia untuk
profil lokal lain. Model embedding `bge-m3:latest` tetap diperlukan oleh profil
ini. Tidak ada perintah pull/download model pada runner.

Setiap eksekusi membuat direktori privat `/tmp/agentic-integration-*`, datadir
MySQL baru, proses Redis baru, server ChromaDB baru, serta storage/cache Laravel baru.
Port dipilih dari port loopback yang tersedia. Database aplikasi, broker Redis,
storage, indeks vektor, dan berkas `.env` yang sudah ada tidak digunakan untuk
menyimpan fixture. Jangan menjalankan launcher utama untuk tes ini.

`laravel-admin/scripts/integration/prepare.php` menolak eksekusi tanpa marker
run dan konfigurasi terisolasi. Helper tersebut memakai migrasi aplikasi asli
dan membuat admin, kategori, serta API key sintetis. Kredensial acak dikirim
melalui environment proses dan tidak dicetak dalam laporan. Output log dapat
memuat konfigurasi/kredensial sementara; direktori run hanya dapat diakses
pemiliknya dan tidak perlu dimasukkan ke Git.

Runner menjalankan aplikasi FastAPI, worker Celery, serta server Laravel asli.
FastAPI dan worker menggunakan `HttpClient` ke satu server Chroma milik run;
keduanya tidak membuka database embedded pada path yang sama. Path lokal
`CHROMA_PERSIST_DIR` tetap dibagi untuk penanda invalidasi korpus. Pendekatan
server bersama mengikuti [dokumentasi client/server Chroma](https://docs.trychroma.com/production/chroma-server/client-server-mode).
Model Ollama lokal dipakai bersama dan pengujian menambah beban inferensi serta
dapat mengubah model yang sedang dimuat di RAM/VRAM. Model yang dimuat oleh tes
dibiarkan mengikuti kebijakan cache Ollama setelah proses aplikasi berhenti.

## Alur yang diperiksa

1. Login cookie Sanctum, penolakan tanpa sesi, dan CSRF dengan HTTP sungguhan.
2. Upload PDF sintetis dua halaman: halaman citra melalui vision OCR dan halaman
   teks native. Jeda diminta saat OCR berjalan; halaman harus disimpan sebelum
   worker berhenti.
3. Resume melewati halaman yang sudah tersimpan, mencapai `menunggu_koreksi`,
   dan mempertahankan gerbang manual sebelum embedding.
4. Koreksi teks, ukuran halaman, serta pratinjau chunk dengan overlap nol.
5. Embedding melalui Celery/Ollama, penyimpanan ChromaDB, dan sinkronisasi status
   serta jumlah chunk pada Laravel.
6. Chat JSON/SSE melalui gateway Laravel terhadap korpus uji; jawaban harus
   memakai angka hasil koreksi dan JSON harus merujuk dokumen yang diminta.
7. Logout dan penghentian proses milik runner.

`report.json`, log setiap layanan, PDF, teks OCR, jawaban, event SSE, serta
datadir sementara dipertahankan dalam direktori run yang dicetak. Exit code 0
berarti seluruh assertion lulus. Kegagalan menyimpan nama pemeriksaan terakhir
dan alasan pada laporan; inspeksi log layanan terkait sebelum menyimpulkan
regresi aplikasi. Satu pengujian dapat memerlukan beberapa menit karena
inisialisasi model dan OCR nyata.

Ini adalah smoke test sintetis dengan reranker dimatikan dan jendela konteks
4096 token. Hasilnya tidak mengukur akurasi umum OCR/RAG, beban serentak,
kualitas dokumen produksi, tampilan/fokus/scroll browser, handoff tiket, atau
pengiriman WhatsApp/Telegram/webhook. Mode bawaan tidak memanggil endpoint
cancel. Mode `--cancellation` menambahkan pemeriksaan berikut:

- Dua dokumen diantrekan ketika konsumsi worker dinonaktifkan pada broker run.
  Cancel A mempertahankan pesan B, lalu B tetap selesai dan A tidak menulis.
- Saat OCR C berjalan, dokumen D diantrekan. C dibatalkan lalu langsung di-resume;
  hasil token C lama dibuang, D selesai, dan generasi C baru menyimpan dua halaman.
- Korpus yang telah selesai tetap ada ketika dibatalkan. Fixture vektor parsial
  generasi embedding berikutnya dibersihkan tanpa menghapus korpus sebelumnya.

Kontrol consumer hanya ditujukan pada broker/worker milik run. Task tidak
dibunuh, antrean tidak dipurge, dan endpoint cancel tidak melakukan unload
model. Penyisipan fixture parsial dilakukan langsung pada Chroma sementara;
pembatalan tepat di tengah encoding juga diperiksa oleh tes unit terarah.
Migrasi kolom token/cancellation dijalankan oleh helper prepare pada database
sementara. Task tanpa token sengaja tidak diproses oleh worker baru.

`LARAVEL_BASE_URL` pada layanan Python diarahkan secara eksplisit ke server
Laravel milik run. Bila variabel ini diberikan, callback tiket hanya mencoba
instance itu dan tidak beralih ke hostname/port Laravel lain. Tanpa variabel,
daftar discovery lama dipertahankan untuk kompatibilitas.

## Browser dengan backend nyata

`start_browser_environment.py` menambahkan Vite dan fixture akun/tiket ke
layanan sementara yang sama. PDF native dua halaman tersedia untuk unggah
melalui UI. Skenario Playwright CLI, urutan, kredensial sintetis, penghentian
layanan dan batas hasil dijelaskan di [panduan browser](browser/README.md).
Profil browser tidak menggantikan runner OCR/cancellation di atas.

## Pemulihan cleanup saat layanan terputus

```bash
python-ai/venv/bin/python scripts/integration/run_cleanup_recovery.py
```

Profil ini memakai layanan sementara yang sama dan menerapkan kedua migrasi
fence/outbox. Empat PDF native diunggah dan diekstrak worker nyata. Consumer
worker milik run kemudian dijeda agar fixture vektor parsial dapat disisipkan
tanpa bergantung pada timing encoder. Hanya server Chroma dan API yang dibuat
runner dimatikan/di-restart; layanan operasional tetap berjalan.

Sembilan pemeriksaan termasuk setup memverifikasi: request cancel bertahan saat
Chroma offline lalu resume membuat token baru, replacement ditahan oleh cleanup
penuh, delete saat Python offline menyisakan outbox meski baris dokumen hilang,
startup API mencoba ulang, dan background cleanup setelah Chroma pulih menjaga
ID vektor yang telah dipakai ulang oleh generasi baru serta dokumen lain.
Dokumen pengganti dapat dilanjutkan setelah cleanup selesai.

Fixture menggunakan embedding dua dimensi untuk memeriksa penghapusan dan
predicate; tidak menjalankan encoding OCR/embedding model atau query RAG.
Deadline retry fixture dimajukan melalui SQL setelah Chroma hidup agar tes
tidak menunggu seluruh backoff; drainer API 30 detik tetap benar-benar bekerja.
Semua timestamp outbox harus UTC. `report.json` dan log tetap berada dalam
direktori run; `owned_processes_stopped: true` memeriksa proses awal maupun
proses hasil restart. Gunakan runner utama `--cancellation` untuk regresi model
dan pembatalan aktif yang sesungguhnya.
