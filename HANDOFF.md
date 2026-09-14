# Handoff — Optimasi RAG Chatbot Diskominfotik (nftxvn)

Ringkasan sesi analisis sebelumnya. Dibuat dari laptop lain (LAPTOP-MEKCNNHF),
jadi sebagian temuan berasal dari **salinan kode yang lebih lama** — ditandai
jelas di bawah. Verifikasi dulu sebelum bertindak.

## Mesin & Stack

|           |                                                                                         |
| --------- | --------------------------------------------------------------------------------------- |
| Host      | nftxvn — WSL Ubuntu, Ollama via systemd                                                 |
| GPU       | RTX 4050 Laptop, **6140 MiB total, 5072 MiB bebas** (~1068 MiB dipakai desktop Windows) |
| CPU / RAM | i7-12650H, 7.8 GiB RAM (5.0 GiB bebas), WSL lihat 8 CPU, llama.cpp pakai 4 thread       |
| LLM       | `qwen3:8b` (Q4_K_M, 4.86 GiB)                                                           |
| Vision    | `qwen2.5vl:7b-q4_K_M` (~6.0 GB) — hanya untuk OCR PDF pindai                            |
| Embedding | `BAAI/bge-m3` (terkonfirmasi di .env)                                                   |
| Stack     | FastAPI + LangChain + ChromaDB + Celery/Redis + MySQL (bersama Laravel), SSE            |
| Klien     | React widget (`/api/chat/stream`) + WhatsApp (`/api/chat/message`)                      |
| Pengguna  | Orang awam, Bahasa Indonesia, dokumen resmi Diskominfotik                               |

## MASALAH #1 (paling besar) — reload model 23 detik tiap request

`num_ctx` dihitung dinamis per pertanyaan. Di Ollama, **setiap nilai num_ctx
berbeda memaksa llama-server mati dan model dimuat ulang dari nol.**

Bukti dari `journalctl -u ollama`:

```
15:40:45  load dengan -c 4096
15:41:09  llama-server started in 23.30 seconds
15:41:11  POST /api/chat  ->  200 | 26.51 detik
15:41:21  load ulang dengan -c 9216      <- beda ctx, muat ulang lagi
```

Dari 26,5 detik itu **23,3 detik adalah loading**. Inferensi sebenarnya hanya
1831 ms (`total time = 1831.43 ms`). Pengguna menunggu 26 detik untuk jawaban
yang butuh 2 detik.

**Perbaikan: kunci `num_ctx` ke satu nilai tetap (rekomendasi 8192).**
Ini prioritas di atas segalanya — reranker, chunking, maupun ukuran model.

## MASALAH #2 — offload sebagian, hanya 12,2 tok/dtk

Log: `offloaded 27/37 layers to GPU` di ctx 4096, `23/37` di ctx 9216.
Penyebabnya auto-fit llama.cpp selalu menyisakan 1024 MiB:

```
common_params_fit_impl: cannot meet free memory target of 1024 MiB
common_params_fit_impl: id=0, target=4048 MiB      <- 5072 - 1024
```

PENTING: membebaskan VRAM saja **tidak cukup**. Meski VRAM bebas jadi 5900 MiB,
anggarannya tetap 5900 - 1024 = 4876 < 5319 yang dibutuhkan, jadi tetap di-split.
`num_gpu` harus di-set eksplisit agar llama.cpp memakai angka user.

**Perbaikan:** `PARAMETER num_gpu 99` + bebaskan VRAM + `OLLAMA_KV_CACHE_TYPE=q8_0`.

## Rumus KV cache (sudah divalidasi dengan log)

Qwen3 8B = **144 KiB per token** (36 layer x 1024 n_embd_k_gqa x 2 (K+V) x 2 byte).
Model di GPU: 4643 MiB. Di host: 333 MiB (token_embd — normal, tetap ada meski
full offload, bukan tanda kegagalan).

| num_ctx  | KV f16 | KV q8_0 | Total dgn q8_0 | Muat di kartu 6140?         |
| -------- | ------ | ------- | -------------- | --------------------------- |
| 4096     | 576    | 306     | 5049           | pas                         |
| **8192** | 1152   | 612     | **5375**       | perlu bebaskan VRAM         |
| 9216     | 1296   | 689     | 5442           | mepet                       |
| 16384    | 2304   | 1224    | 6017           | TIDAK — butuh seluruh kartu |

**`LLM_MAX_NUM_CTX=16384` di .env secara fisik tidak bisa full-GPU.**
Turunkan ke 8192.

## MASALAH #3 — vision model dan LLM tidak muat bersamaan

```
qwen2.5vl:7b-q4_K_M   ~6,0 GB
qwen3:8b              ~4,9 GB
                      ------- 10,9 GB di kartu 6,1 GB
```

Tiap Celery memproses PDF pindai, qwen3:8b digusur dari VRAM sehingga chat
berikutnya bayar 23 detik reload lagi. Ini juga menjelaskan OCR 30–90 detik per
halaman (vision 6 GB di kartu 6,1 GB = sebagian besar layer jalan di CPU).

**Perbaikan:** jadwalkan ingest di luar jam layanan, atau vision model lebih kecil.
Ide: Tesseract dulu (CPU, ~1 dtk/halaman), panggil vision HANYA bila hasilnya
terlihat rusak (rasio karakter non-alfabet tinggi / kata terlalu sedikit).

## Temuan dari SALINAN LAMA — WAJIB DIVERIFIKASI ULANG

Salinan yang dibaca ada di laptop lain dan **arsitekturnya berbeda**: OCR-nya
masih Tesseract, belum ada vision model sama sekali. Jadi hal berikut mungkin
sudah tidak berlaku di nftxvn:

1. **Belum ada reranker.** Pipeline: query -> embed -> Chroma top_k=5 -> langsung LLM.
   `sentence-transformers` sudah terpasang, jadi `CrossEncoder` tidak butuh dependency baru.
2. **`chunk_size=500` itu KARAKTER, bukan token.** `RecursiveCharacterTextSplitter`
   memakai `length_function=len`. 500 karakter kira-kira 125 token; dikali top_k=5
   berarti konteks hanya ~625 token. (Log menunjukkan `task.n_tokens = 423` — konsisten.)
   Saran: naikkan ke 1200–1500 karakter, overlap ~200, lalu **reindex seluruh dokumen**.
3. **Tidak ada ambang relevansi.** `similarity_search` selalu kembalikan 5 chunk
   teratas seberapa pun jauh jaraknya. Untuk pertanyaan di luar topik, LLM disodori
   5 chunk tidak relevan — di situlah model kecil paling sering mengarang.
   `distance` sudah tersimpan di hasil tapi belum dipakai menyaring.
4. **Cek konfigurasi bge-m3:** butuh `normalize_embeddings=True` di `model.encode()`,
   dan Chroma default pakai L2 sehingga perlu `metadata={"hnsw:space": "cosine"}`.

## Perintah verifikasi pertama di nftxvn

```bash
cd ~/python-ai

# nilai chunking sebenarnya
grep -n "chunk_size\|rag_top_k\|chunk_overlap" app/config.py

# di mana num_ctx dinamis dihitung  <- untuk MASALAH #1
grep -rn "num_ctx\|LLM_MAX_NUM_CTX" app/

# siapa memanggil model apa
grep -rn "vision_model\|VISION_MODEL" app/
grep -rn "llm_model_name" app/

# "ekstraksi kata kunci" jalan saat ingest atau saat query?
grep -rni "keyword\|kata_kunci" app/
grep -rni "keyword\|kata_kunci\|llm" app/tasks/
```

Blok terakhir menentukan: kalau `app/tasks/` memanggil LLM teks, berarti vision
dan qwen3:8b **bergantian saat ingest** — swap 20–30 detik terus-menerus, dan itu
harus diperbaiki lebih dulu.

## Urutan pengerjaan

1. **Kunci `num_ctx` = 8192**, hapus perhitungan dinamisnya. (~23 dtk/request)
2. **Full GPU offload:**
   - Bebaskan VRAM: pindahkan Chrome/Edge/dll ke iGPU Intel
     (Settings -> Display -> Graphics -> app -> Power saving). Butuh mode Hybrid,
     bukan "Discrete GPU only" di BIOS/Armoury Crate.
   - `sudo systemctl edit ollama` lalu tambahkan:
     `Environment="OLLAMA_FLASH_ATTENTION=1"` dan `Environment="OLLAMA_KV_CACHE_TYPE=q8_0"`
   - Modelfile: `PARAMETER num_gpu 99` + `PARAMETER num_ctx 8192`
   - Verifikasi: `offloaded 37/37 layers to GPU`, tidak ada baris `CPU KV buffer size`,
     `graph splits` turun dari 22 ke satuan.
   - Target: 12,2 -> 35–50 tok/dtk.
3. **Pisahkan jadwal OCR dari jam layanan chat.**
4. **Baseline RAGAS** (`test_ragas_official.py` sudah ada) sebelum menyentuh retrieval.
5. Chunking -> ambang relevansi -> baru reranker.
   Catatan: `bge-reranker-v2-m3` 568M parameter (~2,2 GB) **harus jalan di CPU**
   (~1–2 dtk untuk 20 kandidat), jangan di GPU — akan merebut VRAM yang baru
   diperjuangkan.
6. Terakhir baru pertimbangkan 8B vs 4B.

## Catatan kualitas RAG saat model diperkecil

Yang paling TIDAK terpengaruh: pengetahuan faktual (datang dari retrieval).
Yang paling rusak, berurutan: pemahaman konteks panjang -> faithfulness/grounding
-> kemampuan Bahasa Indonesia -> sintesis lintas chunk.

Aturan: **turunkan kuantisasi dulu, jangan parameter.** `8B IQ4_XS` lebih aman
daripada `4B Q4_K_M`. Jangan pernah di bawah Q4 — kepatuhan instruksi runtuh, dan
itu fatal untuk RAG. KV cache q8_0 aman; **q4_0 jangan** (merusak recall konteks panjang).

## Soal prompt untuk pengguna awam

Ketat itu soal **grounding**, bukan **gaya bahasa** — dua hal terpisah.
Aturan "jawab hanya dari konteks" harus DIPERTAHANKAN (makin penting kalau model
diperkecil); yang ditambahkan cukup aturan nada:

> Gunakan bahasa sehari-hari yang mudah dipahami, hindari istilah teknis dan
> singkatan birokrasi. Jika dokumen memakai istilah formal, jelaskan artinya
> dengan kata sederhana.

Masalah sebenarnya dengan pengguna awam ada di **retrieval**, bukan prompt:
mereka mengetik "cara urus ktp ilang", dokumen menulis "penerbitan Kartu Tanda
Penduduk pengganti karena hilang". Melonggarkan prompt tidak memperbaiki ini —
malah membuat model menutupi retrieval buruk dengan karangan. Solusinya reranker

- hybrid search + query expansion.

## Keamanan

`INTERNAL_API_TOKEN` sempat ter-paste utuh ke percakapan sebelumnya. Token itu
membuka `/api/docs/*` dan `/api/chat/message`. **Rotate**: generate baru dan
perbarui juga di sisi Laravel.

`CHAT_STREAM_REQUIRE_AUTH=false` — sesuai komentar di .env sendiri, ini hanya
untuk development. Jangan terbawa ke produksi.
