# Spesifikasi API (API Spec)

Antarmuka komunikasi internal dan eksternal antara Laravel, Python Microservice, dan berbagai channel chat (React Widget untuk testing, WhatsApp untuk produksi).

> **Catatan Arsitektur:** API Chat di Python bersifat *channel-agnostic*. Endpoint yang sama melayani React Widget (testing) maupun WhatsApp Webhook (produksi). Tidak ada perubahan kode backend saat berpindah channel.

> **Diperbarui 13 Agustus 2026** agar sesuai dengan implementasi di `python-ai/`.
> Bagian [§0](#0-perbedaan-yang-perlu-disepakati-tim) mencatat tiga titik di mana
> dokumen versi sebelumnya berbeda dari kode — ketiganya **belum diputuskan**
> dan perlu disepakati bersama sebelum integrasi.
>
> **Perubahan yang memengaruhi pemanggil (13 Agustus 2026):**
>
> | Perubahan | Dampak |
> |---|---|
> | `/api/chat/stream` kini butuh `Authorization: Bearer` | Widget wajib mengirim header, atau setel `CHAT_STREAM_REQUIRE_AUTH=false` saat pengembangan lokal |
> | Permintaan tanpa header `Authorization` dijawab **401**, sebelumnya 422 | Pengecekan kode status di Laravel jadi konsisten untuk seluruh endpoint |
> | CORS tidak lagi `*` | Origin widget harus terdaftar di `CORS_ALLOW_ORIGINS` |
> | Pesan galat 500 tidak lagi memuat rincian exception | Rinciannya ada di log server |
> | `doc_name` kini terisi | Sebelumnya selalu `null` |
> | `/health` memeriksa dependensi dan bisa membalas **503** | Pemantauan yang menganggap 200 sebagai satu-satunya jawaban perlu disesuaikan |

---

## 0. Perbedaan yang perlu disepakati tim

Dokumen ini kini menjelaskan **apa yang kode lakukan sekarang**. Tiga hal di
bawah berbeda dari spesifikasi awal. Perbaikannya bisa di sisi Python atau di
sisi klien — itu keputusan bersama, bukan sepihak.

| # | Spesifikasi awal | Implementasi sekarang | Dampak bila dibiarkan |
|---|---|---|---|
| 1 | `data: {"chunk": "..."}` | `data: {"type":"chunk","content":"..."}` | **Widget membaca kunci `chunk` → teks tidak muncul sama sekali** |
| 2 | Event `sources` terpisah di akhir stream | Sumber dikirim sebagai potongan teks biasa berawalan `📚 **Sumber Referensi:**` | Klien tidak menerima sumber dalam bentuk data terstruktur |
| 3 | `{"status": "processing_started"}` | `{"status": "accepted"}` | Pengecekan string di Laravel gagal |

Perbedaan **nomor 1 yang paling mendesak** — akibatnya bukan tampilan yang
kurang rapi, melainkan jawaban yang tidak muncul sama sekali.

---

## 1. Komunikasi Laravel → Python (Manajemen Dokumen)

Saat Admin mengunggah dokumen baru (menimpa yang lama), Laravel menyimpan file ke *storage* lokal (atau *shared storage*) dan memicu proses di Python.

Seluruh endpoint `/api/docs/*` **wajib** menyertakan header
`Authorization: Bearer <INTERNAL_API_TOKEN>`. Token dicocokkan dengan nilai
`INTERNAL_API_TOKEN` di `.env` milik Python. Bila tidak cocok → `401`.

### `POST /api/docs/process`
**Fungsi:** Memicu proses pembaruan dokumen (ekstraksi + OCR + embedding) ke dalam antrean Celery di latar belakang.

- **Base URL:** `http://python-service:8000`
- **Headers:** `Authorization: Bearer <internal_token>`
- **Payload (JSON):**
  ```json
  {
    "document_id": 12,
    "file_path": "/var/www/html/storage/app/public/documents/peraturan_v2.pdf",
    "action": "overwrite"
  }
  ```
  | Field | Tipe | Keterangan |
  |---|---|---|
  | `document_id` | int | ID dokumen di tabel `documents` milik Laravel |
  | `file_path` | string | Path absolut yang bisa dijangkau **pekerja Celery** |
  | `action` | string | `"new"` atau `"overwrite"`. `"overwrite"` menghapus vektor lama lebih dulu |

- **Response (202 Accepted):**
  ```json
  {
    "status": "accepted",
    "message": "Dokumen 12 sedang diproses."
  }
  ```
  > ⚠️ Spesifikasi awal menulis `"processing_started"` — lihat §0 nomor 3.

### `GET /api/docs`
**Fungsi:** Mengambil daftar seluruh dokumen beserta status pemrosesannya. Dipakai Laravel untuk tabel di dashboard admin.

- **Headers:** `Authorization: Bearer <internal_token>`
- **Response (200 OK):**
  ```json
  {
    "total": 2,
    "documents": [
      {
        "id": 12,
        "original_name": "SOP_Diskominfotik_2025.pdf",
        "file_path": "/var/www/.../peraturan_v2.pdf",
        "status": "completed",
        "pdf_type": "text",
        "total_pages": 10,
        "total_chunks": 10,
        "created_at": "2026-08-10T09:12:00",
        "updated_at": "2026-08-10T09:24:00"
      }
    ]
  }
  ```

### `GET /api/docs/{document_id}/status`
**Fungsi:** Mengecek status pemrosesan satu dokumen. Dipakai Laravel untuk polling AJAX berkala sampai status berubah dari `processing`.

- **Headers:** `Authorization: Bearer <internal_token>`
- **Response (200 OK):**
  ```json
  {
    "id": 12,
    "status": "completed",
    "pdf_type": "text",
    "total_pages": 10,
    "total_chunks": 10,
    "error_message": null,
    "processed_at": "2026-08-10T09:24:00",
    "created_at": "2026-08-10T09:12:00",
    "updated_at": "2026-08-10T09:24:00"
  }
  ```
- **Response (404):** dokumen tidak ditemukan.

Nilai `status` yang mungkin: `pending`, `processing`, `completed`, `failed`.

---

---

### Ekstraksi bertahap — bisa dijeda dan dilanjutkan

`POST /api/docs/process` menjalankan seluruh pipeline sekaligus tanpa bisa
disela. Untuk dokumen pindaian ratusan halaman itu berjam-jam, dan proses yang
mati di halaman 168 membuang seluruh pekerjaannya.

Kelompok endpoint di bawah ini memecah pekerjaan itu jadi bertahap: tiap
halaman disimpan sebelum lanjut ke halaman berikutnya, dan admin bisa
menghentikannya di tengah jalan tanpa kehilangan kemajuan.

Alurnya punya **dua gerbang manual** — sistem berhenti dan menunggu manusia:

```
unggah -> ekstraksi (bisa dijeda) -> KOREKSI -> pratinjau -> SIMPAN -> selesai
```

Nilai `status` yang mungkin:

| Status | Artinya |
|---|---|
| `antre` | Tugas sudah masuk Celery, belum mulai |
| `berjalan` | OCR sedang mengerjakan halaman |
| `jeda` | Berhenti di batas halaman; kemajuan aman |
| `menunggu_koreksi` | Semua halaman terekstrak, menunggu admin |
| `selesai` | Vektor sudah masuk ChromaDB |
| `gagal` | Ada halaman yang tidak terbaca; lihat `pesan` |

---

#### `POST /api/docs/{document_id}/ekstraksi`

Memulai **atau** melanjutkan ekstraksi. Satu endpoint untuk keduanya —
halaman yang sudah tersimpan dilewati otomatis, jadi Laravel tidak perlu
melacak sendiri apakah ini pekerjaan baru atau penerusan.

- **Body (opsional):**

```json
{ "maks_halaman": 20 }
```

`maks_halaman` membatasi jumlah halaman per putaran; tugas berikutnya
mengantre sendiri. Berguna agar satu tugas Celery tidak berjalan berjam-jam.

- **Response (202):**

```json
{ "document_id": 1, "status": "antre" }
```

---

#### `POST /api/docs/{document_id}/ekstraksi/jeda`

- **Response (202):**

```json
{ "document_id": 1, "jeda_diminta": true }
```

> **Penting untuk antarmuka.** Jeda adalah **permintaan**, bukan penghentian
> seketika. Satu panggilan model vision berlangsung 20–60 detik dan tidak bisa
> dipotong di tengah tanpa menyisakan halaman separuh, jadi benderanya baru
> diperiksa **di antara halaman**.
>
> Akibatnya status **belum langsung** `jeda` — ia masih `berjalan` dengan
> `jeda_diminta: true` sampai halaman yang sedang dibaca selesai. Tampilkan
> *"Menjeda…"* selama masa itu. Kalau tombolnya langsung berkata *"Terjeda"*,
> admin akan mengira sistemnya macet.

Laravel juga boleh menyalakan benderanya langsung tanpa memanggil layanan
Python: `UPDATE ekstraksi_job SET jeda_diminta = 1 WHERE document_id = ?`.
Dengan begitu tombol jeda tetap bekerja walau layanan AI sedang sibuk.

---

#### `GET /api/docs/{document_id}/ekstraksi`

- **Response (200):**

```json
{
  "document_id": 1,
  "status": "berjalan",
  "jeda_diminta": false,
  "halaman_total": 171,
  "halaman_selesai": 83,
  "persen": 49,
  "pesan": null
}
```

Dokumen yang **belum pernah** diekstrak menjawab `200` dengan
`status: "antre"` dan `persen: 0` — bukan `404`. Belum diekstrak adalah
keadaan awal, bukan galat.

---

#### `GET /api/docs/{document_id}/ekstraksi/aliran`

Kemajuan langsung lewat SSE. Formatnya sama dengan `/api/chat/stream`:
`{"type": ..., "content": ...}`.

```
data: {"type":"kemajuan","content":{"status":"berjalan","halaman_selesai":84,...}}

data: {"type":"selesai","content":"menunggu_koreksi"}
```

Kabar hanya dikirim saat ada yang **berubah**, dan aliran **menutup dirinya
sendiri** begitu pekerjaan berhenti — `jeda`, `menunggu_koreksi`, `selesai`,
atau `gagal`.

---

### Koreksi manual sebelum masuk korpus

#### `GET /api/docs/{document_id}/halaman`

Teks tiap halaman, untuk ditampilkan di editor koreksi.

- **Query:** `perlu_diperiksa=1` mengembalikan **hanya** halaman yang ditandai
  mencurigakan oleh sistem, beserta alasannya:

```json
{
  "document_id": 1,
  "jumlah": 2,
  "halaman": [
    { "page_number": 9,  "alasan": "baris 'NIP.' hilang" },
    { "page_number": 58, "alasan": "'Nama SOP' hilang" }
  ]
}
```

Triase ini yang membuat ratusan halaman masuk akal dikoreksi manusia. Tanpa
urutan yang menempatkan halaman bermasalah di depan, memeriksa satu per satu
terasa mustahil dan pada akhirnya dilewati.

---

#### `PUT /api/docs/{document_id}/halaman/{page_number}`

- **Body:**

```json
{ "text": "isi halaman yang sudah dikoreksi" }
```

- **Response (200):**

```json
{ "document_id": 1, "page_number": 9, "tersimpan": true }
```

- **Response (400):** teks kosong. Halaman kosong lenyap dari korpus tanpa
  galat apa pun dan baru ketahuan lewat jawaban *"tidak ditemukan"*, jadi
  ditolak di pintu masuk.

Menyimpan **per halaman**, bukan seluruh dokumen sekaligus: satu kesalahan
jaringan tidak boleh menimpa pekerjaan berjam-jam.

---

#### `GET /api/docs/{document_id}/halaman/ukuran`

Ukuran dan orientasi tiap halaman **tanpa merender apa pun** — dipakai editor
untuk menyiapkan ukuran panel sebelum gambarnya sampai.

```json
{
  "document_id": 1,
  "halaman_total": 171,
  "zoom_bawaan": 2.0,
  "zoom_diizinkan": [1.5, 2.0, 3.0, 4.0],
  "halaman": [
    { "page_number": 1, "lebar": 1872, "tinggi": 1224, "orientasi": "lanskap" },
    { "page_number": 2, "lebar": 1224, "tinggi": 1872, "orientasi": "potret" }
  ]
}
```

---

#### `GET /api/docs/{document_id}/halaman/{page_number}/citra`

Citra satu halaman sebagai JPEG, agar korektor bisa membandingkan hasil OCR
dengan halaman aslinya.

- **Query:** `zoom` — salah satu dari `1.5`, `2`, `3`, `4`. Nilai lain
  dijawab `400`; tanpa daftar tertutup, satu permintaan `zoom=50` memaksa
  server merender gambar 46.000 piksel.
- **Response (200):** `image/jpeg`, ditambah header
  `Cache-Control: public, max-age=31536000, immutable`, `ETag`,
  `X-Lebar-Piksel`, dan `X-Tinggi-Piksel`.

Terukur pada halaman lanskap 936×612 pt: **186 KB** pada zoom 2, dirender
dalam **0,02 detik**. JPEG dipilih karena halaman pindaian bersifat fotografis
— PNG tiga kali lebih besar untuk hasil yang terlihat sama.

> **Zoom bawaan sama persis dengan yang dibaca model OCR** (`Matrix(2.0, 2.0)`,
> 144 DPI). Itu syarat, bukan kebetulan: bila korektor melihat gambar lebih
> tajam daripada yang dibaca model, ia akan memperbaiki teks yang mustahil
> terbaca mesin dan mengira masalahnya selesai — padahal itu pertanda
> resolusi render yang perlu dinaikkan.

---

#### `GET /api/docs/{document_id}/potongan`

Pratinjau potongan induk/anak, **dihitung saat diminta dan tidak disimpan**.

Pemotongan adalah fungsi murni dari teksnya — teks yang sama selalu
menghasilkan potongan yang sama, dan biayanya milidetik. Menyimpannya justru
menciptakan risiko potongan basi yang dibuat dari teks versi lama, tetap
tampak sah, lalu masuk korpus tanpa ada yang menyadari selisihnya.

```json
{
  "document_id": 1,
  "judul": "KEPUTUSAN WALIKOTA BANDA ACEH NOMOR 395 TAHUN 2025 ...",
  "jumlah_induk": 10,
  "jumlah_anak": 65,
  "induk": [ ... ],
  "anak": [ ... ],
  "siap": true
}
```

---

#### `POST /api/docs/{document_id}/simpan`

Tombol akhir: potong lalu simpan vektornya ke ChromaDB. **Satu-satunya langkah
yang dijaga tombol**, karena satu-satunya yang mahal sekaligus mengganti isi
korpus.

- **Response (202):** `{ "document_id": 1, "status": "diantrekan" }`
- **Response (409):** ekstraksi masih `berjalan`, atau belum ada halaman
  terekstrak sama sekali.

Potongannya dihitung ulang di dalam tugas, bukan diambil dari pratinjau yang
mungkin dilihat berjam-jam sebelumnya — sehingga yang masuk korpus selalu
berasal dari teks yang berlaku sekarang.

---

### Tabel yang diperlukan

Kedua tabel di bawah ini dipakai bersama Laravel. Skemanya ditentukan sisi
Python, tetapi **migrasinya sebaiknya ditulis Laravel** agar skema tidak hidup
di dua tempat yang bisa berbeda.

```sql
CREATE TABLE ekstraksi_job (
  document_id     BIGINT PRIMARY KEY,
  status          ENUM('antre','berjalan','jeda',
                       'menunggu_koreksi','selesai','gagal') NOT NULL,
  jeda_diminta    TINYINT(1) NOT NULL DEFAULT 0,
  halaman_total   INT NOT NULL,
  halaman_selesai INT NOT NULL DEFAULT 0,
  petunjuk_format TEXT NULL,
  pesan           TEXT NULL,
  updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE ekstraksi_halaman (
  document_id  BIGINT NOT NULL,
  page_number  INT NOT NULL,
  text         LONGTEXT NOT NULL,
  diperiksa    TINYINT(1) NOT NULL DEFAULT 0,
  created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (document_id, page_number)
);
```

`PRIMARY KEY (document_id, page_number)` bukan formalitas: dengan
`INSERT ... ON DUPLICATE KEY UPDATE`, melanjutkan ekstraksi tidak pernah bisa
menggandakan halaman — walau tugas Celery-nya kebetulan berjalan dua kali.

`petunjuk_format` menyimpan catatan format yang dibawa antar halaman. Halaman
kedua sebuah formulir tidak memuat kepala apa pun tetapi tetap butuh aturan
format langkah prosedurnya; tanpa disimpan, catatan itu hilang saat pekerjaan
dijeda dan worker dijalankan ulang.

## 2. Komunikasi Python → MySQL (Update Status Asynchronous)

Untuk menghindari keharusan Laravel menunggu *(timeout)*, Python memproses ekstraksi dan embedding di latar belakang (bisa memakan waktu 10+ menit untuk 170 halaman di CPU).

Setelah selesai, Python **secara langsung** memperbarui tabel `documents` milik Laravel lewat SQLAlchemy + PyMySQL.

Kolom yang ditulis Python (`app/database.py:68`):

```
status, updated_at, pdf_type, total_chunks, total_pages,
error_message, processed_at
```

Field di luar daftar itu ditolak dan dicatat sebagai peringatan — daftar ini
berfungsi sebagai pengaman, jadi menambah kolom baru berarti mengubah
`allowed_fields` juga.

*(Di sisi Dashboard Laravel, Admin bisa dibuatkan polling AJAX/Livewire setiap 10 detik untuk me-refresh status di tabel selama status masih `processing`.)*

---

## 3. Chat API — Channel-Agnostic (Testing & Produksi)

### `POST /api/chat/stream` — Untuk React Widget (Testing/SSE)

**Fungsi:** Mengirim pertanyaan dan menerima respons berformat *Server-Sent Events* agar teks muncul mengetik sedikit demi sedikit.

- **Base URL:** `http://localhost:8000`
- **Headers:** `Content-Type: application/json`,
  `Authorization: Bearer <INTERNAL_API_TOKEN>`
- **Autentikasi:** Bearer token, sama seperti endpoint lain. Bisa dimatikan
  lewat `CHAT_STREAM_REQUIRE_AUTH=false` **hanya untuk pengembangan lokal**.

  > ⚠️ **Widget di browser tidak boleh memegang `INTERNAL_API_TOKEN`.** Token
  > yang sama membuka `/api/docs/*`, dan apa pun yang masuk ke JavaScript sisi
  > klien terbaca lewat devtools. Untuk produksi, widget memanggil Laravel dan
  > Laravel yang meneruskannya ke layanan ini dengan token di sisi server.
  > Alternatif lain — token terpisah khusus chat — **belum diputuskan tim.**

- **Payload (JSON):**
  ```json
  {
    "session_id": "sesi-987-xyz",
    "query": "Apa persyaratan untuk memperpanjang izin?",
    "document_ids": [12, 15]
  }
  ```
  | Field | Wajib | Keterangan |
  |---|---|---|
  | `session_id` | ya | Saat ini hanya dipakai untuk log — belum ada memori percakapan |
  | `query` | ya | Ditolak `400` bila kosong. Belum ada batas panjang |
  | `document_ids` | tidak | Batasi pencarian ke dokumen tertentu. Kosongkan untuk mencari ke seluruh koleksi |

- **Response (200 OK — `text/event-stream`):**

  Setiap event berisi objek JSON dengan dua kunci: `type` dan `content`.

  ```text
  data: {"type": "chunk", "content": "Untuk "}
  data: {"type": "chunk", "content": "memperpanjang "}
  data: {"type": "chunk", "content": "izin, "}
  data: {"type": "chunk", "content": "Anda harus..."}
  data: {"type": "chunk", "content": "\n\n📚 **Sumber Referensi:**\n- Dokumen #12 — Halaman 45"}
  data: {"type": "done", "content": ""}
  ```

  | `type` | Arti |
  |---|---|
  | `chunk` | Potongan jawaban. Gabungkan berurutan |
  | `done` | Stream selesai |
  | `error` | Terjadi kesalahan; `content` memuat pesannya |

  > ⚠️ **Dua catatan penting — lihat §0 nomor 1 dan 2:**
  > 1. Kuncinya `content`, **bukan** `chunk` seperti spesifikasi awal.
  > 2. **Tidak ada event `sources` terpisah.** Daftar sumber datang sebagai
  >    potongan teks terakhir yang berawalan `\n\n📚 **Sumber Referensi:**`.
  >    Klien yang menunggu event `sources` akan menunggu selamanya.

### `POST /api/chat/message` — Untuk WhatsApp Webhook (Produksi)

**Fungsi:** Endpoint non-streaming. Menerima pesan dari WhatsApp Business API webhook, memproses pertanyaan, dan mengembalikan jawaban lengkap dalam satu respons JSON (karena WhatsApp tidak mendukung SSE).

- **Base URL:** `https://api-ai.diskominfotik.go.id`
- **Headers:** `Content-Type: application/json`, `Authorization: Bearer <INTERNAL_API_TOKEN>`
- **Payload (JSON):**
  ```json
  {
    "phone_number": "6281234567890",
    "message": "Apa persyaratan untuk memperpanjang izin?",
    "document_ids": null
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "reply": "Untuk memperpanjang izin, Anda harus menyiapkan: 1. Surat permohonan...",
    "sources": [
      {"doc_name": "SOP_Diskominfotik_2025.pdf", "document_id": 12, "page": 45}
    ]
  }
  ```
  > `doc_name` diambil dari kolom `original_name` di tabel `documents` lewat
  > satu query untuk seluruh dokumen yang dirujuk. Bila MySQL sedang tidak bisa
  > dihubungi, nilainya kembali `null` dan jawabannya **tetap dikirim** —
  > rujukan bernomor lebih baik daripada tidak ada jawaban sama sekali. Klien
  > harus tetap menganggap `doc_name` bisa bernilai `null`.

- **Catatan:** Respons JSON ini dikirim balik ke pengguna WhatsApp oleh middleware/gateway WhatsApp Business API.

---

## 4. Health Check

### `GET /health`

- **Autentikasi:** tidak ada
- **Response (200 OK)** — seluruh dependensi hidup:
  ```json
  {
    "status": "healthy",
    "service": "ai-service",
    "model": "qwen2.5:7b",
    "checks": {
      "chromadb": {"ok": true, "detail": "75 vektor"},
      "mysql":    {"ok": true, "detail": "agentic_copilot"},
      "redis":    {"ok": true, "detail": "PING"},
      "ollama":   {"ok": true, "detail": "qwen2.5:7b"}
    }
  }
  ```
- **Response (503 Service Unavailable)** — ada dependensi yang mati:
  ```json
  {
    "status": "degraded",
    "service": "ai-service",
    "model": "qwen2.5:7b",
    "checks": {
      "chromadb": {"ok": true,  "detail": "75 vektor"},
      "mysql":    {"ok": false, "detail": "OperationalError"},
      "redis":    {"ok": true,  "detail": "PING"},
      "ollama":   {"ok": true,  "detail": "qwen2.5:7b"}
    }
  }
  ```

Yang diperiksa: ChromaDB bisa dibuka dan jumlah vektornya terbaca; MySQL
menjawab `SELECT 1`; Redis menjawab `PING`; Ollama hidup **dan** model chat
yang dikonfigurasi sudah di-pull.

Beberapa catatan untuk pemanggil:

- `detail` pada kegagalan hanya memuat **nama kelas exception**, bukan pesannya.
  Endpoint ini terbuka tanpa autentikasi, dan pesan mentah bisa memuat host atau
  nama pengguna basis data.
- Hasilnya di-cache 5 detik. Tanpa itu, setiap permintaan membuka koneksi
  MySQL + Redis dan satu request ke Ollama — endpoint terbuka yang bisa dipakai
  membebani dependensinya sendiri.
- Tiap pemeriksaan dibatasi 3 detik.

---

## 5. Ringkasan Endpoint

| Metode | Rute | Auth | Dipakai oleh |
|---|---|---|---|
| `POST` | `/api/chat/stream` | Bearer¹ | React Widget |
| `POST` | `/api/chat/message` | Bearer | WhatsApp gateway |
| `GET` | `/api/docs` | Bearer | Laravel |
| `GET` | `/api/docs/{id}/status` | Bearer | Laravel (polling) |
| `POST` | `/api/docs/process` | Bearer | Laravel |
| `POST` | `/api/docs/{id}/ekstraksi` | Bearer | Laravel (mulai / lanjut) |
| `POST` | `/api/docs/{id}/ekstraksi/jeda` | Bearer | Laravel (tombol jeda) |
| `GET` | `/api/docs/{id}/ekstraksi` | Bearer | Laravel (status) |
| `GET` | `/api/docs/{id}/ekstraksi/aliran` | Bearer | Laravel (SSE kemajuan) |
| `GET` | `/api/docs/{id}/halaman` | Bearer | Laravel (editor koreksi) |
| `PUT` | `/api/docs/{id}/halaman/{n}` | Bearer | Laravel (simpan koreksi) |
| `GET` | `/api/docs/{id}/halaman/ukuran` | Bearer | Laravel (ukuran panel) |
| `GET` | `/api/docs/{id}/halaman/{n}/citra` | Bearer | Laravel (citra halaman) |
| `GET` | `/api/docs/{id}/potongan` | Bearer | Laravel (pratinjau potongan) |
| `POST` | `/api/docs/{id}/simpan` | Bearer | Laravel (tombol simpan) |
| `GET` | `/health` | tidak ada | Pemantauan |

¹ Bisa dimatikan lewat `CHAT_STREAM_REQUIRE_AUTH=false` untuk pengembangan lokal.

Seluruh endpoint ber-Bearer menjawab **401** bila header `Authorization` tidak
ada, formatnya bukan `Bearer <token>`, atau tokennya tidak cocok. Pembandingan
token memakai `secrets.compare_digest`, sehingga lamanya tidak bergantung pada
berapa karakter awal yang cocok.

Dokumentasi interaktif tersedia otomatis di `http://localhost:8000/docs`
selama server berjalan.
