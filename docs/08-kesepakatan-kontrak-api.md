# Kesepakatan Kontrak API — bahan rapat Dev 1 / Dev 2 / Dev 3

**Disiapkan Dev 1 (Python), 19 Agustus 2026.**

Dokumen ini menutup dua hal yang selama ini menggantung: tiga ketidakcocokan
kontrak di [`04-api_spec_agentic_copilot.md`](04-api_spec_agentic_copilot.md) §0
yang belum pernah diputuskan, dan cara React Widget memperoleh token.

Semuanya keputusan **bersama**, bukan sepihak — tapi setiap butir di sini sudah
disertai usulan dan alasannya, supaya rapatnya cukup menyetujui atau menolak,
bukan mulai dari nol.

> Setelah disepakati, hasilnya dituliskan ke `docs/04` §0 dan bagian ini boleh
> dihapus.

---

## 1. Tiga ketidakcocokan kontrak

### 1.1 Bentuk event SSE — **paling mendesak**

| | |
|---|---|
| Spesifikasi awal | `data: {"chunk": "..."}` |
| Yang dikirim kode | `data: {"type":"chunk","content":"..."}` |
| Akibat bila dibiarkan | Widget membaca kunci `chunk` yang tidak ada → **jawaban tidak muncul sama sekali** |

Ini bukan soal tampilan kurang rapi. Widget akan menerima aliran data yang sah,
tidak melihat galat apa pun, dan menampilkan layar kosong.

**Usulan: pertahankan bentuk kode, ubah sisi widget.**

Alasannya bukan karena kode lebih dulu ada, melainkan karena bentuk lama
kehilangan informasi. Aliran ini mengirim tiga jenis event:

```
data: {"type":"chunk","content":"Terdapat 74 item..."}
data: {"type":"chunk","content":" Berikut daftarnya..."}
data: {"type":"done","content":""}
```

dan bila pipeline gagal di tengah:

```
data: {"type":"error","content":"Terjadi kesalahan saat memproses permintaan Anda..."}
```

Dengan bentuk `{"chunk": "..."}` saja, `done` dan `error` tidak punya tempat.
Widget jadi tidak bisa membedakan **"jawaban selesai"** dari **"koneksi putus di
tengah"** — dua keadaan yang tampilannya harus berbeda.

Perubahan di sisi Dev 3 satu baris:

```js
const evt = JSON.parse(e.data);
if (evt.type === "chunk")      tambahkanTeks(evt.content);
else if (evt.type === "done")  selesai();
else if (evt.type === "error") tampilkanGalat(evt.content);
```

Catatan penting: **`error` datang sebagai event, bukan kode status.** Saat
pipeline gagal, koneksi SSE sudah terbuka dan status 200 sudah terkirim —
tidak bisa diubah lagi. Widget yang hanya memeriksa kode status akan menggantung
selamanya.

Bentuk ini sekarang dikunci `test_api_kontrak.py::TestFormatSSE`, jadi kalau
suatu saat berubah, ujinya gagal lebih dulu sebelum sampai ke Dev 3.

---

### 1.2 Sumber referensi belum terstruktur

| | |
|---|---|
| Spesifikasi awal | event `sources` terpisah di akhir stream |
| Yang dikirim kode | teks biasa berawalan `📚 **Sumber Referensi:**` di dalam aliran `chunk` |
| Akibat bila dibiarkan | Klien tidak bisa merender sumber sebagai tautan atau chip — hanya sebagai teks |

**Usulan: tambahkan event `sources` sebelum `done`.**

Datanya sudah ada. Endpoint non-streaming `POST /api/chat/message` sudah
mengembalikan objek terstruktur:

```json
{ "doc_name": "SOP-diskominfotik 2025-1-10.pdf", "document_id": 1, "page": 7 }
```

Jadi ini bukan menambah kemampuan baru, melainkan menyamakan dua endpoint yang
sekarang berbeda bentuk untuk data yang sama.

Usulan bentuknya:

```
data: {"type":"sources","content":[{"doc_name":"...","document_id":1,"page":7}]}
data: {"type":"done","content":""}
```

Sifatnya **aditif**: klien yang mengabaikan `type` yang tidak dikenalnya tetap
berjalan seperti sekarang. Jadi bisa dipasang lebih dulu di Python tanpa
menunggu widget siap.

Yang perlu diputuskan Dev 3: apakah teks `📚 **Sumber Referensi:**` tetap ikut
dikirim di dalam `chunk` (supaya WhatsApp yang hanya menerima teks polos tetap
melihat sumbernya), atau dibuang begitu event terstrukturnya ada.
**Usulan: tetap dikirim** — kanal WhatsApp tidak punya cara lain menampilkannya.

---

### 1.3 Nilai `status` pada pemrosesan dokumen

| | |
|---|---|
| Spesifikasi awal | `{"status": "processing_started"}` |
| Yang dikirim kode | `{"status": "accepted"}`, dengan HTTP **202 Accepted** |
| Akibat bila dibiarkan | Pengecekan string di Laravel tidak pernah cocok |

**Usulan: pertahankan `accepted`, ubah sisi Laravel.** Nilainya sejalan dengan
kode status 202 Accepted yang memang berarti "diterima, diproses belakangan".

Perubahannya sepele di kedua sisi — yang penting bukan pilihannya, melainkan
**dituliskan** supaya tidak ada lagi yang menebak. Nilai ini sekarang dikunci
`test_api_kontrak.py::TestEndpointDokumen`.

---

## 2. Cara React Widget memperoleh token

### Masalahnya

`POST /api/chat/stream` menuntut `Authorization: Bearer <INTERNAL_API_TOKEN>`.
Widget berjalan **di dalam browser pengguna**, dan `INTERNAL_API_TOKEN` tidak
boleh sampai ke JavaScript sisi klien — siapa pun bisa membacanya lewat panel
jaringan.

Yang membuatnya serius: token yang sama juga membuka `/api/docs/process`, yaitu
pemicu pemrosesan dokumen. Membocorkannya bukan sekadar membuka akses tanya
jawab, melainkan memberi orang luar kendali atas antrean pemrosesan.

### Pilihan

**(a) Laravel meneruskan aliran (proxy)** — Widget → Laravel → Python.
Token disimpan di sisi server Laravel dan tidak pernah dikirim ke browser.

- **Untung:** tidak ada kode baru di Python, tidak ada rahasia baru. Laravel
  sekaligus bisa menerapkan sesi login dan pembatasan lajunya sendiri.
- **Rugi:** Laravel harus meneruskan SSE apa adanya. Perlu memastikan buffering
  dimatikan, kalau tidak jawabannya baru muncul sekaligus di akhir — hilang
  seluruh gunanya streaming.

**(b) Token sesi berumur pendek terbitan Laravel** — Laravel menerbitkan token
bertanda tangan (mis. JWT, berlaku 15 menit, hanya untuk chat), widget
mengirimkannya, Python memverifikasi.

- **Untung:** streaming langsung dari Python, tanpa risiko buffering perantara.
- **Rugi:** perlu jalur verifikasi baru di Python dan satu rahasia bersama.
  Lebih banyak bagian bergerak.

**(c) `CHAT_STREAM_REQUIRE_AUTH=false`** — **hanya untuk pengembangan lokal.**
Di jaringan instansi ini berarti siapa pun yang menjangkau port tersebut dapat
menanyai seluruh isi dokumen yang sudah di-ingest. Bukan jawaban produksi.

### Usulan

**Mulai dengan (a).** Tidak menuntut kode baru di Python maupun rahasia
tambahan, dan Laravel memang sudah menjadi pemilik sesi pengguna. Kalau
penerusan SSE lewat Laravel ternyata merepotkan, barulah pindah ke (b).

Apa pun yang dipilih, satu hal sudah dijamin uji: `CHAT_STREAM_REQUIRE_AUTH`
**hanya** melonggarkan `/api/chat/stream`. Ia tidak pernah membuka
`/api/docs/*`, sehingga menyalakannya saat pengembangan lokal tidak pernah
membuka jalur pemrosesan dokumen
(`test_api_kontrak.py::TestAutentikasi::test_endpoint_dokumen_tidak_pernah_dibuka_oleh_saklar_stream`).

---

## 3. Yang sudah dikunci uji

Sejak `test_api_kontrak.py` ada (37 uji, berjalan tanpa satu pun layanan
menyala), perilaku berikut akan menggagalkan uji bila berubah — jadi perubahan
kontrak menjadi keputusan sadar yang bisa dikabarkan, bukan kejutan saat
integrasi:

| Yang dijamin | Kenapa penting bagi kalian |
|---|---|
| Bentuk event SSE `type` + `content`, ditutup `done` | Dev 3 — inti §1.1 |
| Kegagalan datang sebagai `type:"error"`, bukan 500 | Dev 3 — kalau tidak, widget menggantung |
| Pesan galat tidak memuat path, host, atau kredensial | Keduanya — jangan tampilkan mentah ke pengguna |
| **401** konsisten di semua endpoint (dulu 422) | Dev 2 — penanganan galat jadi seragam |
| `CHAT_STREAM_REQUIRE_AUTH` tidak membuka `/api/docs/*` | Keduanya — batas keamanan |
| `POST /api/docs/process` → **202** + `{"status":"accepted"}` | Dev 2 — §1.3 |
| `GET /api/docs` → `{"total": n, "documents": [...]}` | Dev 2 |
| Dokumen tak dikenal → **404** | Dev 2 |
| CORS tidak pernah `*` | Keduanya — origin widget harus terdaftar di `CORS_ALLOW_ORIGINS` |
| `/health` → **503** bila ada dependensi mati, hasil di-cache 5 detik | Pemantauan — 200 bukan satu-satunya jawaban, dan status bisa tertinggal 5 detik |

Jalankan sendiri kapan saja:

```bash
cd python-ai
python -m unittest test_api_kontrak
```

---

## 4. Yang perlu diputuskan di rapat

1. §1.1 — setuju widget yang menyesuaikan ke bentuk `type`/`content`?
2. §1.2 — pasang event `sources`? Dan teks `📚` tetap dikirim untuk WhatsApp?
3. §1.3 — pakai `accepted`?
4. §2 — proxy lewat Laravel (a), atau token sesi berumur pendek (b)?
5. Origin mana saja yang masuk `CORS_ALLOW_ORIGINS` untuk pengembangan dan produksi?

Butir 1 yang paling mendesak: selama belum disepakati, widget menampilkan layar
kosong dan itu bukan bug yang akan terlihat di log siapa pun.
