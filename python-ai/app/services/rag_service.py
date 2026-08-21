"""
Service RAG (Retrieval-Augmented Generation).
Melakukan pencarian konteks di ChromaDB dan menghasilkan jawaban
menggunakan LLM Ollama secara streaming.
"""

import logging
import math
import re as _re
from typing import Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.services.embedding_service import (
    get_chroma_collection,
    get_embedding_model,
    read_corpus_version,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────

# Jumlah dokumen konteks yang diambil per query oleh vector store
_TOP_K = 20

# Jumlah chunk maksimum yang dikirim ke LLM setelah multi-query aggregation.
_MAX_CONTEXT_CHUNKS = 10

# Limit lebih longgar khusus untuk query bertipe daftar/list lengkap
_MAX_CONTEXT_CHUNKS_LIST_QUERY = 20

# ── Jendela konteks LLM ──────────────────────────────────────
#
# Ukurannya DIHITUNG dari panjang konteks yang benar-benar terkumpul, bukan
# dipatok. Nilai tetap 16384 untuk setiap pertanyaan daftar membuat Ollama
# mengalokasikan KV cache besar walau konteksnya pendek — dan pada mesin
# ber-RAM terbatas alokasi itu gagal dengan "failed to allocate buffer",
# menjatuhkan seluruh permintaan. Kegagalannya bergantung pada apa yang
# kebetulan sedang berjalan di mesin, jadi gejalanya adalah pertanyaan yang
# kadang berhasil kadang gagal tanpa pola yang jelas.

# Perkiraan kasar karakter per token untuk teks bahasa Indonesia. Sengaja
# konservatif (kecil) supaya taksirannya melebihkan, bukan mengurangi.
_CHARS_PER_TOKEN = 3.0

# Ruang yang disisakan untuk jawaban model.
_NUM_CTX_RESPONSE_HEADROOM = 2048

# Batas bawah — di bawah ini konteks apa pun akan terpotong.
_NUM_CTX_MIN = 4096

# Konstanta k untuk Reciprocal Rank Fusion (RRF).
# Nilai standar di literatur information retrieval adalah 60.
_RRF_K = 60

# Ambang batas skor BM25 minimum agar sebuah chunk dianggap "match" secara leksikal.
_BM25_MIN_SCORE = 0.1

# Timeout (detik) untuk request ke Ollama. Dinaikkan karena inferensi di CPU bisa lambat.
# Diteruskan lewat client_kwargs, BUKAN parameter timeout= milik ChatOllama:
# langchain_ollama 1.1.0 tidak punya field bernama `timeout` sama sekali,
# sehingga menuliskannya di sana diabaikan tanpa peringatan apa pun. Akibatnya
# nyata: satu permintaan yang menggantung pernah menahan evaluasi 27 menit
# tanpa pernah diputus. client_kwargs diteruskan ke httpx, yang benar-benar
# memberlakukannya.
_OLLAMA_TIMEOUT = 300

# Berapa lama model tetap "warm" (di-load) di memori Ollama antar-request.
# Mencegah reload model dari disk setiap kali dipanggil, yang bisa memicu timeout.
_OLLAMA_KEEP_ALIVE = "30m"

# Field yang menandakan sebuah chunk berisi RINCIAN prosedur SOP (bukan cuma daftar nama).
_SOP_DETAIL_MARKERS = [
    "Dasar Hukum:", "Kualifikasi Pelaksana:", "Peralatan/Perlengkapan:",
    "Pelaksana:", "Kelengkapan:",
]

# Kata kunci yang menandakan pertanyaan meminta prosedur/langkah-langkah
_PROCEDURE_QUESTION_KEYWORDS = ["prosedur", "langkah", "bagaimana cara", "tahapan", "tata cara"]

# System prompt untuk LLM — instruksi perilaku model
_SYSTEM_PROMPT = """Anda adalah asisten virtual yang bertugas menjawab pertanyaan berdasarkan dokumen sumber yang diberikan.

Konteks Dokumen:
{context}

Instruksi:

Jawab hanya dalam bahasa Indonesia.

Bila konteks memuat dua nilai yang BERTENTANGAN untuk hal yang sama, sebutkan keduanya beserta letaknya; jangan diam-diam memilih salah satu.

Bila pertanyaan menyebut nomor, nama, atau bagian yang TIDAK ada di konteks, katakan bahwa hal itu tidak ada. JANGAN menggantinya dengan bagian lain yang mirip.

Bila yang ditanyakan tidak ada namun konteks memuat padanannya, sebutkan apa yang ADA di tempatnya; jangan berhenti pada penolakan saja.

JANGAN menjumlahkan atau menghitung angka yang tidak tertulis di dokumen. Bila dokumen tidak memuat totalnya, sampaikan rinciannya apa adanya.

Salin nama, jabatan, dan angka PERSIS seperti tertulis, sekalipun tampak keliru.

Jawab pertanyaan HANYA berdasarkan informasi yang ada di Konteks Dokumen di atas.

JANGAN menggunakan pengetahuan di luar dokumen tersebut.

Jika Konteks Dokumen tidak berisi informasi untuk menjawab pertanyaan, Anda WAJIB menjawab persis seperti ini: "Maaf, informasi tersebut tidak ditemukan di dalam dokumen." JANGAN pernah mengarang atau menebak jawaban.

Mulailah jawaban Anda dengan kalimat pengantar yang relevan dengan pertanyaan."""


# ─────────────────────────────────────────────────────────────
# HYBRID RETRIEVAL (Vector + BM25, digabung via Reciprocal Rank Fusion)
# ─────────────────────────────────────────────────────────────

def _reciprocal_rank_fusion(
    vector_ranked_ids: list[str],
    bm25_ranked_ids: list[str],
    k: int = _RRF_K,
) -> dict[str, float]:
    """
    Menggabungkan dua daftar hasil retrieval (vector search & BM25) menggunakan
    Reciprocal Rank Fusion (RRF).

    RRF menggabungkan berdasarkan PERINGKAT (rank), bukan skor mentah — sehingga
    tidak ada masalah "skala skor tidak sepadan" seperti pendekatan hardcode
    distance BM25 = 0.001 (yang membuat BM25 selalu menang atas vector search
    meski relevansinya lemah).

    Args:
        vector_ranked_ids: List id chunk, terurut dari yang paling relevan
            (distance terkecil) versi vector search.
        bm25_ranked_ids: List id chunk, terurut dari yang paling relevan
            (skor BM25 tertinggi) versi lexical search.
        k: Konstanta RRF, default 60.

    Returns:
        Dict {chunk_id: rrf_score}, belum diurutkan.
    """
    scores: dict[str, float] = {}

    for rank, chunk_id in enumerate(vector_ranked_ids):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    for rank, chunk_id in enumerate(bm25_ranked_ids):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)

    return scores


# Cache indeks BM25 di level modul (pola singleton, sama seperti _embedding_model
# dan _chroma_collection di embedding_service).
#
# Membangun BM25 berarti menarik SELURUH korpus dari ChromaDB lalu men-tokenisasi
# semuanya — biayanya sebanding dengan besar korpus. Sebelumnya itu dilakukan pada
# SETIAP pertanyaan, padahal isi korpus tidak berubah di antara dua pertanyaan;
# hanya berubah saat ada ingest/hapus dokumen. Pada korpus besar, beban itu
# tertambahkan ke tiap query dan terus tumbuh seiring dokumen bertambah.
_bm25_cache: dict | None = None


def invalidate_bm25_cache() -> None:
    """Buang cache indeks BM25. Dipanggil setelah dokumen di-ingest atau dihapus
    supaya query berikutnya membangun ulang indeks dari korpus terbaru."""
    global _bm25_cache
    if _bm25_cache is not None:
        logger.info("Cache BM25 di-invalidasi (korpus berubah)")
    _bm25_cache = None


def _get_bm25_index(collection) -> dict:
    """
    Mengembalikan indeks BM25 beserta korpusnya, dibangun sekali lalu dipakai ulang.

    Dua penanda dipakai untuk memutuskan apakah indeks lama masih sahih:

    1. `collection.count()` — menangkap penambahan atau penghapusan vektor.
    2. Penanda versi korpus di disk (`read_corpus_version`) — menangkap
       perubahan yang TIDAK mengubah jumlah vektor, misalnya menimpa dokumen
       dengan jumlah potongan yang kebetulan sama. Penanda ini juga satu-satunya
       jalan bagi proses ini untuk mengetahui ingest yang terjadi di proses
       pekerja Celery, karena cache di sini tidak terjangkau dari sana.

    Returns:
        Dict berisi bm25, docs, ids, metas, dan flag hierarchical.
    """
    global _bm25_cache

    try:
        current_count = collection.count()
    except Exception:
        current_count = -1

    current_version = read_corpus_version()

    if (
        _bm25_cache is not None
        and _bm25_cache["count"] == current_count
        and _bm25_cache["version"] == current_version
    ):
        return _bm25_cache

    empty = {"bm25": None, "docs": [], "ids": [], "metas": [],
             "hierarchical": True, "count": current_count,
             "version": current_version}

    try:
        from rank_bm25 import BM25Okapi

        all_data = collection.get(where={"chunk_type": "child"})
        hierarchical = True
        if not all_data.get("documents"):
            # Data lama tanpa chunk_type — pakai seluruh koleksi (jalur flat)
            all_data = collection.get()
            hierarchical = False

        docs = all_data.get("documents", [])
        ids = all_data.get("ids", [])
        metas = all_data.get("metadatas", [])

        tokenized_corpus = [doc.lower().split() for doc in docs]
        _bm25_cache = {
            "bm25": BM25Okapi(tokenized_corpus) if tokenized_corpus else None,
            "docs": docs,
            "ids": ids,
            "metas": metas,
            "hierarchical": hierarchical,
            "count": current_count,
            "version": current_version,
        }
        logger.info(
            "Indeks BM25 dibangun: %d chunk (%s) — akan dipakai ulang sampai korpus berubah",
            len(docs), "hierarchical" if hierarchical else "flat",
        )
        return _bm25_cache
    except Exception as e:
        logger.warning(f"BM25 initialization failed: {e}")
        _bm25_cache = None  # jangan cache kegagalan
        return empty


def _build_where_filter(
    chunk_type: str | None,
    document_ids: list[int] | None,
) -> dict | None:
    """
    Menyusun filter `where` untuk ChromaDB dari dua kondisi opsional.

    ChromaDB butuh operator $and secara eksplisit bila ada lebih dari satu
    kondisi; satu kondisi harus dikirim polos tanpa $and.
    """
    conditions: list[dict] = []
    if chunk_type:
        conditions.append({"chunk_type": chunk_type})
    if document_ids:
        conditions.append(
            {"document_id": {"$in": list(document_ids)}}
            if len(document_ids) > 1
            else {"document_id": document_ids[0]}
        )

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _retrieve_context(
    query: str,
    original_query: str = "",
    document_ids: list[int] | None = None,
) -> tuple[str, str]:
    """
    Melakukan pencarian similarity di ChromaDB berdasarkan query pengguna.
    Menggunakan strategi Parent-Child Retrieval + Hybrid Search (Vector + BM25)
    yang digabungkan dengan Reciprocal Rank Fusion (RRF):
    1. Cari child chunks (kecil, presisi) yang paling relevan lewat vector search
       DAN BM25 secara terpisah.
    2. Gabungkan kedua peringkat hasil menggunakan RRF agar chunk yang match
       leksikal lemah tidak mengalahkan chunk yang secara makna benar-benar relevan.
    3. Ambil parent chunks (besar, lengkap) sebagai konteks ke LLM.

    Fallback ke flat retrieval jika data lama tanpa chunk_type ditemukan.

    Args:
        query: Pertanyaan dari pengguna (biasanya versi kata kunci).
        original_query: Pertanyaan asli pengguna tanpa filtering (untuk deteksi intent).

    Returns:
        Tuple berisi (context_text, sources_text).
    """
    model = get_embedding_model()
    collection = get_chroma_collection()

    check_query = original_query if original_query else query
    is_list = _is_list_query(check_query)
    max_chunks = _MAX_CONTEXT_CHUNKS_LIST_QUERY if is_list else _MAX_CONTEXT_CHUNKS
    top_k = _TOP_K * 4 if is_list else _TOP_K

    if max_chunks != _MAX_CONTEXT_CHUNKS:
        logger.info("Query terdeteksi sebagai list-query, max_chunks dinaikkan ke %d, top_k ke %d", max_chunks, top_k)

    try:
        # Pertanyaan asli ikut dicari, tidak digantikan.
        #
        # `query` di sini adalah versi kata kunci hasil ekstraksi LLM. Ekstraksi
        # itu memang membuang kalimat pengantar yang mengaburkan pencarian, tapi
        # kadang ikut membuang kata pembatas yang justru menentukan — misalnya
        # "tetap" pada "cuti pegawai tetap". Bila hanya kata kunci yang dicari,
        # pembatas itu hilang dan dua daftar berbeda dalam satu dokumen
        # tercampur. Dengan keduanya dicari, RRF yang memutuskan mana yang lebih
        # relevan, bukan hasil ekstraksi kata kunci.
        queries = [query]

        if original_query and original_query.strip() != query.strip():
            queries.append(original_query)

        if is_list:
            # Anchor query membantu menemukan halaman yang memuat daftar/enumerasi.
            # Dibentuk dari kata kunci pertanyaan user + frasa enumerasi yang umum,
            # BUKAN dari nama dokumen tertentu yang dipatok di kode — anchor yang
            # dipatok akan menyeret halaman dokumen itu masuk ke pertanyaan tentang
            # dokumen lain.
            queries.append(f"daftar {query} terdiri dari")
            queries.append(f"{query} terdiri dari sebagai berikut")
            logger.info("List-query: menambahkan %d anchor query untuk retrieve halaman daftar", len(queries) - 1)

        # ── Tahap 1: Cari child chunks yang relevan (Hybrid BM25 + Vector, digabung via RRF) ──
        chunk_data: dict[str, tuple[str, dict]] = {}  # id -> (doc_text, metadata)

        bm25_index = _get_bm25_index(collection)
        bm25 = bm25_index["bm25"]
        all_docs = bm25_index["docs"]
        all_ids = bm25_index["ids"]
        all_metas = bm25_index["metas"]
        use_hierarchical = bm25_index["hierarchical"]

        aggregated_rrf: dict[str, float] = {}

        for q in queries:
            # show_progress_bar=False: query hanya satu kalimat, bilah kemajuannya
            # tidak berguna dan mengotori log tiap kali ada pertanyaan masuk.
            q_embedding = model.encode(q, show_progress_bar=False).tolist()

            # 1a. Vector Search (Semantic) — hasil SUDAH terurut dari yang paling relevan
            try:
                results = collection.query(
                    query_embeddings=[q_embedding],
                    n_results=top_k,
                    where=_build_where_filter(
                        "child" if use_hierarchical else None, document_ids
                    ),
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                use_hierarchical = False
                results = collection.query(
                    query_embeddings=[q_embedding],
                    n_results=top_k,
                    where=_build_where_filter(None, document_ids),
                    include=["documents", "metadatas", "distances"],
                )

            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            ids = results.get("ids", [[]])[0]

            vector_ranked_ids = list(ids)
            for chunk_id, doc_text, metadata in zip(ids, docs, metas):
                chunk_data[chunk_id] = (doc_text, metadata)

            # 1b. BM25 Search (Lexical / Kata Kunci)
            bm25_ranked_ids: list[str] = []
            if bm25 and all_docs:
                import numpy as np

                tokenized_query = q.lower().split()
                bm25_scores = bm25.get_scores(tokenized_query)
                if top_k > 0 and len(all_docs) > 0:
                    # Indeks BM25 dibangun atas SELURUH korpus (agar bisa di-cache),
                    # jadi pembatasan dokumen diterapkan di sini saat menyaring hasil.
                    # Urutan diambil penuh lalu dipotong setelah filter, supaya jatah
                    # top_k tidak habis terpakai oleh dokumen yang justru dikecualikan.
                    doc_filter = set(document_ids) if document_ids else None
                    for idx in np.argsort(bm25_scores)[::-1]:
                        if len(bm25_ranked_ids) >= top_k:
                            break
                        score = bm25_scores[idx]
                        if score <= _BM25_MIN_SCORE:
                            break  # sisanya pasti lebih kecil — hemat iterasi
                        if doc_filter is not None and all_metas[idx].get("document_id") not in doc_filter:
                            continue
                        b_id = all_ids[idx]
                        bm25_ranked_ids.append(b_id)
                        if b_id not in chunk_data:
                            chunk_data[b_id] = (all_docs[idx], all_metas[idx])

            # 1c. Gabungkan peringkat vector & BM25 via RRF
            rrf_scores = _reciprocal_rank_fusion(vector_ranked_ids, bm25_ranked_ids)
            for chunk_id, score in rrf_scores.items():
                aggregated_rrf[chunk_id] = aggregated_rrf.get(chunk_id, 0.0) + score

        if not aggregated_rrf:
            logger.info("Tidak ada dokumen relevan ditemukan untuk query: '%s'", query[:80])
            return "", ""

        ranked_chunk_ids = sorted(aggregated_rrf.keys(), key=lambda cid: aggregated_rrf[cid], reverse=True)

        # ── Tahap 2: Ambil parent chunks dari child yang cocok ──
        if use_hierarchical:
            child_limit = len(ranked_chunk_ids) if is_list else top_k
            top_children_ids = ranked_chunk_ids[:child_limit]

            parent_ids_ordered: list[str] = []
            parent_best_score: dict[str, float] = {}
            for chunk_id in top_children_ids:
                _, metadata = chunk_data[chunk_id]
                pid = metadata.get("parent_id")
                score = aggregated_rrf[chunk_id]
                if pid and pid not in parent_best_score:
                    parent_ids_ordered.append(pid)
                    parent_best_score[pid] = score
                elif pid and score > parent_best_score.get(pid, float("-inf")):
                    parent_best_score[pid] = score

            if parent_ids_ordered:
                parent_results = collection.get(
                    ids=parent_ids_ordered,
                    include=["documents", "metadatas"],
                )

                parent_docs = parent_results.get("documents", [])
                parent_metas = parent_results.get("metadatas", [])
                parent_ret_ids = parent_results.get("ids", [])

                combined = []
                for pid, doc, meta in zip(parent_ret_ids, parent_docs, parent_metas):
                    score = parent_best_score.get(pid, 0.0)
                    combined.append((doc, meta, score))

                combined.sort(key=lambda x: x[2], reverse=True)
                combined = combined[:max_chunks]

                # Sort ulang untuk presentasi ke LLM berdasarkan urutan dokumen (page + chunk_index)
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))

                logger.info(
                    "Hybrid RRF retrieval: %d child cocok -> %d parent unik -> %d dikirim ke LLM",
                    len(ranked_chunk_ids), len(parent_ids_ordered), len(combined),
                )
            else:
                combined = [
                    (chunk_data[cid][0], chunk_data[cid][1], aggregated_rrf[cid])
                    for cid in ranked_chunk_ids[:max_chunks]
                ]
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))
        else:
            combined = [
                (chunk_data[cid][0], chunk_data[cid][1], aggregated_rrf[cid])
                for cid in ranked_chunk_ids[:max_chunks]
            ]
            combined.sort(key=lambda x: (
                int(x[1].get("page_number", 0)),
                int(x[1].get("chunk_index", 0)),
            ))
            logger.info(
                "Flat retrieval (fallback): %d chunk dipilih dari %d total",
                len(combined), len(ranked_chunk_ids),
            )

        # ── Tahap 3: Bangun teks konteks dan sumber ──
        context_parts: list[str] = []
        sources_set: set[str] = set()

        for doc_text, metadata, rrf_score in combined:
            doc_id = metadata.get("document_id", "?")
            page_num = metadata.get("page_number", "?")
            chunk_idx = metadata.get("chunk_index", "?")
            chunk_type = metadata.get("chunk_type", "flat")

            context_parts.append(
                f"[Sumber: Dokumen #{doc_id}, Halaman {page_num}, "
                f"Chunk #{chunk_idx} ({chunk_type}) "
                f"(skor RRF: {rrf_score:.4f})]\n{doc_text}"
            )
            sources_set.add(f"Dokumen #{doc_id} \u2014 Halaman {page_num}")

        context_text = "\n\n---\n\n".join(context_parts)
        sources_text = "\n".join(f"- {s}" for s in sorted(sources_set))

        best_score = max(aggregated_rrf.values())
        logger.info(
            "Ditemukan %d konteks unik dari %d query (skor RRF terbaik: %.4f), "
            "dikirim %d chunk ke LLM",
            len(ranked_chunk_ids),
            len(queries),
            best_score,
            len(combined),
        )

        # Hanya ditulis bila DEBUG_DUMP_CONTEXT aktif.
        #
        # Sebelumnya berkas ini ditulis pada SETIAP pertanyaan. Karena
        # penulisannya berada di dalam blok try yang sama, satu kegagalan tulis
        # — direktori kerja read-only, berkas terkunci proses lain — tertelan
        # oleh except di bawah dan membuat SELURUH retrieval mengembalikan hasil
        # kosong. Bagi pengguna, gejalanya adalah setiap pertanyaan dijawab
        # "informasi tidak ditemukan", tanpa petunjuk apa pun soal sebabnya.
        if settings.DEBUG_DUMP_CONTEXT:
            try:
                with open("debug_context.txt", "w", encoding="utf-8") as f:
                    f.write(context_text)
            except OSError as e:
                logger.warning("Gagal menulis debug_context.txt: %s", e)

        return context_text, sources_text

    except Exception:
        # exc_info=True: tanpa jejak lengkapnya, kegagalan retrieval tidak bisa
        # dibedakan dari "memang tidak ada dokumen yang relevan".
        logger.error("Gagal melakukan pencarian konteks", exc_info=True)
        return "", ""


# ─────────────────────────────────────────────────────────────
# DETEKSI: KONTEKS HANYA BERISI NAMA SOP (BUKAN RINCIAN PROSEDUR)
# ─────────────────────────────────────────────────────────────

# Penanda bahwa konteks memang berasal dari dokumen berformat formulir SOP
# pemerintah. Dipakai untuk membatasi ruang berlaku penjaga di bawah.
_SOP_FORMAT_MARKERS = ["[Konteks: SOP", "Nomor SOP", "NOMOR SOP", "Nama SOP", "NAMA SOP"]


def _context_is_sop_document(context_text: str) -> bool:
    """
    Apakah konteks ini berasal dari dokumen berformat formulir SOP.

    Penting untuk platform multi-dokumen: penjaga "prosedur tanpa rincian" di
    bawah mengenali rincian lewat nama-nama kolom formulir SOP pemerintah.
    Dokumen di luar format itu — panduan, peraturan, manual — tidak punya kolom
    tersebut, sehingga tanpa pemeriksaan ini SETIAP pertanyaan "bagaimana cara"
    padanya akan ditolak walau jawabannya jelas ada di konteks.
    """
    return any(marker in context_text for marker in _SOP_FORMAT_MARKERS)


def _context_has_full_procedure(context_text: str) -> bool:
    """
    Cek apakah konteks berisi rincian prosedur SOP (Dasar Hukum, Kualifikasi
    Pelaksana, Peralatan/Perlengkapan, langkah-langkah, dsb) — bukan cuma
    daftar nama/judul SOP seperti yang ada di Diktum KEDUA.
    """
    return any(marker in context_text for marker in _SOP_DETAIL_MARKERS)


# ─────────────────────────────────────────────────────────────
# PENJAGA PREMIS PALSU (entitas bernomor yang tidak ada di dokumen)
# ─────────────────────────────────────────────────────────────

# Pertanyaan berpremis palsu adalah kegagalan yang paling berbahaya: jawabannya
# terdengar meyakinkan justru karena modelnya patuh. Ditanya "Diktum KEEMPAT"
# pada keputusan yang hanya punya tiga diktum, model menyodorkan isi Diktum
# KEDUA; ditanya "langkah ke-11" pada prosedur bersepuluh langkah, ia menyalin
# output langkah ke-10. Keduanya bisa dipastikan salah TANPA model, jadi
# diperiksa lebih dulu — pola yang sama dengan penjaga prosedur dan penjaga
# daftar di generate_response.
_URUTAN_DIKTUM = (
    "kesatu", "pertama", "kedua", "ketiga", "keempat", "kelima",
    "keenam", "ketujuh", "kedelapan", "kesembilan", "kesepuluh",
)
_POLA_TANYA_DIKTUM = _re.compile(
    r"\bdiktum\s+(" + "|".join(_URUTAN_DIKTUM) + r")\b", _re.IGNORECASE
)
_POLA_TANYA_LANGKAH = _re.compile(
    r"\b(?:langkah|tahap|tahapan)\s+(?:ke\s*-?\s*)?(\d{1,3})\b", _re.IGNORECASE
)
_POLA_ITEM_BERNOMOR = _re.compile(r"(?m)^\s*(\d{1,3})[.)]\s+\S")

# Di bawah ambang ini konteksnya tidak cukup terstruktur untuk menyimpulkan
# "langkah sebanyak itu tidak ada" — lebih baik diam daripada menolak keliru.
_MIN_ITEM_UNTUK_SIMPULAN = 3


def _nomor_item_tertinggi(context_text: str) -> int:
    """Nomor urut terbesar yang benar-benar ada di konteks, 0 bila tak ada."""
    nomor = [int(m.group(1)) for m in _POLA_ITEM_BERNOMOR.finditer(context_text)]
    return max(nomor) if nomor else 0


def _entitas_tak_ada_di_konteks(query: str, context_text: str) -> str | None:
    """
    Kembalikan nama entitas yang ditanyakan tetapi tidak ada di konteks.

    Hanya menjawab untuk hal yang bisa dipastikan dari teks: nama diktum, dan
    nomor langkah yang melampaui item bernomor tertinggi. Bila konteksnya tidak
    cukup terstruktur, fungsi ini memilih diam — menolak menjawab secara keliru
    jauh lebih merugikan daripada melewatkan satu premis palsu.

    Returns:
        Nama entitas yang tidak ada, atau None bila tidak ada yang bisa
        dipastikan.
    """
    rendah = context_text.lower()

    for m in _POLA_TANYA_DIKTUM.finditer(query):
        nama = m.group(1).lower()
        if "diktum " + nama not in rendah and nama.upper() not in context_text:
            return "Diktum " + nama.upper()

    tertinggi = _nomor_item_tertinggi(context_text)
    if tertinggi >= _MIN_ITEM_UNTUK_SIMPULAN:
        for m in _POLA_TANYA_LANGKAH.finditer(query):
            if int(m.group(1)) > tertinggi:
                return "langkah ke-" + m.group(1)

    return None


def _is_procedure_question(query: str) -> bool:
    """Mendeteksi apakah pertanyaan meminta prosedur/langkah-langkah suatu SOP."""
    query_lower = query.lower()
    return any(k in query_lower for k in _PROCEDURE_QUESTION_KEYWORDS)


# ─────────────────────────────────────────────────────────────
# DAFTAR PANJANG DIEKSTRAK TERPROGRAM (bukan disalin LLM)
# ─────────────────────────────────────────────────────────────
#
# Terukur pada qwen2.5:7b: diminta menyalin daftar 74 item yang SELURUHNYA ada
# di konteks, model berhenti di item ke-46 — tiga kali berturut-turut, di item
# yang persis sama, pada temperature 0. Bukan soal retrieval (74/74 hadir),
# bukan jendela konteks (9.216 dialokasikan, ~6.300 terpakai), bukan batas
# keluaran (num_predict=8192 memberi hasil identik). Menambah instruksi
# "salin seluruhnya" justru MEMPERBURUK: 46 turun jadi 20, karena instruksi
# tambahan ikut berebut perhatian dengan tugas menyalin.
#
# Jadi daftarnya diambil secara terprogram lalu disodorkan ke model — pola yang
# sama seperti _build_comparison_hint di bawah.

# Item daftar: huruf (a. / a) / (a)) atau angka (1. / 1)).
#
# Judul boleh MENYATU di baris yang sama, seperti "Mengingat : 1. Undang-Undang...".
# Bentuk itu lazim pada dokumen resmi dan sempat membuat item pertama tidak
# terdeteksi sama sekali — runtun lalu dimulai dari item KEDUA, dan kata pembeda
# di judulnya ("Mengingat") tertinggal di luar jangkauan penilaian relevansi.
_ENUM_ITEM = _re.compile(
    r"^[ \t]*(?:[^:\n]{0,60}:[ \t]*)?"          # judul opsional di baris yang sama
    r"\(?(?P<tanda>[a-zA-Z]{1,3}|\d{1,3})[.)][ \t]+"
    r"(?P<isi>\S.*?)[ \t]*;?[ \t]*$",
    _re.MULTILINE,
)

# Baris rincian di bawah sebuah item daftar ("- Pelaksana:", "- Waktu: 1 Hari").
# Kehadirannya menandakan daftar BERTINGKAT, yang tidak boleh disajikan sebagai
# daftar datar karena rinciannya justru sering yang ditanyakan.
_ENUM_SUBITEM = _re.compile(r"^[ \t]+[-*•]\s+\S", _re.MULTILINE)

# Batas minimum item agar daftar dijawab terprogram.
#
# Bukan sekadar soal panjang. Model gagal pada dua keadaan: daftar yang terlalu
# panjang untuk disalin utuh, DAN dokumen yang memuat beberapa daftar mirip
# sehingga ia memilih yang keliru — persis yang terjadi pada pertanyaan tentang
# dasar hukum, di mana satu dokumen memuat tiga daftar peraturan sekaligus
# (milik Keputusan, milik SOP Renstra, milik SOP Renja).
#
# Ambang 10 memasukkan keduanya sambil tetap menyisakan daftar sangat pendek
# (mis. "2 SOP yang berkaitan") untuk dijawab model secara wajar.
_ENUM_MIN_ITEMS_FOR_HINT = 10

# Panjang teks pengantar sebelum daftar yang ikut dinilai relevansinya. Di situ
# biasanya tertulis penanda seperti "Dasar Hukum:" atau "KEDUA : ... terdiri dari:"
# yang membedakan satu daftar dari daftar lain di dokumen yang sama.
_ENUM_LEAD_IN = 220

# Kata yang terlalu umum untuk membedakan daftar mana yang dimaksud.
_ENUM_STOPWORDS = {
    "berapa", "total", "yang", "dalam", "dan", "ini", "apa", "saja", "pada",
    "dari", "untuk", "sebutkan", "seluruhnya", "semua", "jumlah", "adalah",
    "dengan", "atau", "itu", "ada", "seluruh", "tercantum", "dibutuhkan",
}


# Kata yang menandakan pengguna meminta daftar UTUH, bukan sekadar beberapa
# contoh. "Sebutkan 5 contoh" tidak butuh daftar 74 item disodorkan.
#
# Dicocokkan di AWAL kata (\b di depan, bebas di belakang): imbuhan akhiran
# harus tetap cocok — "seluruhnya", "semuanya", "lengkapnya" — sementara awalan
# TIDAK boleh, karena "perlengkapan" dan "kelengkapan" memuat "lengkap" tanpa
# ada hubungannya dengan permintaan daftar utuh. Pencocokan substring polos
# membuat pertanyaan "peralatan/perlengkapan apa saja" ikut terjaring.
_COMPLETE_LIST_PATTERN = _re.compile(
    r"\b(?:seluruh|semua|keseluruhan|lengkap)"
    r"|\bberapa\s+(?:total|jumlah|banyak)\b",
    _re.IGNORECASE,
)


# Pertanyaan bisa MENYODORKAN jumlah alih-alih memintanya ("benarkah hanya 46
# SOP?"). Bentuk ini tidak tertangkap pola daftar-utuh, sehingga jawabannya
# dulu hanya "lebih dari 46" — premis palsunya memang ditolak, tetapi angka
# sebenarnya tidak pernah disebut. Padahal jumlahnya bisa dihitung pasti.
_POLA_JUMLAH_DISODORKAN = _re.compile(
    r"\b(?:benarkah|betulkah|apakah|benar)\b.{0,90}?\bhanya\b.{0,40}?\b(\d{1,3})\b"
    r"|\bhanya\s+(?:memuat|berisi|ada|terdiri\s+dari)\s+(\d{1,3})\b",
    _re.IGNORECASE | _re.DOTALL,
)


def _jumlah_yang_disodorkan(query: str) -> int | None:
    """Angka yang diklaim pertanyaan sebagai jumlah suatu daftar, bila ada."""
    m = _POLA_JUMLAH_DISODORKAN.search(query)
    if not m:
        return None
    return int(m.group(1) or m.group(2))

def _asks_for_complete_list(query: str) -> bool:
    """Apakah pertanyaan meminta daftar utuh beserta jumlahnya."""
    return bool(_COMPLETE_LIST_PATTERN.search(query))


def _enum_sort_key(marker: str) -> tuple:
    """
    Kunci pengurutan penanda item, supaya "urutan maju" bisa diperiksa.

    Angka memakai nilainya. Huruf memakai (berapa kali diulang, hurufnya):
    a < b < ... < z < aa < bb < ... < zz < aaa. Skema "huruf diulang" itulah
    yang dipakai dokumen resmi Indonesia untuk daftar melebihi 26 item.
    """
    if marker.isdigit():
        return (0, int(marker), "")
    huruf = marker.lower()
    return (1, len(huruf), huruf[0])


def _penanda_huruf_sah(marker: str) -> bool:
    """
    Benar bila penanda huruf memakai skema huruf-diulang (a, aa, aaa, ...).

    Daftar resmi Indonesia yang melebihi 26 item memakai huruf yang diulang,
    bukan gabungan huruf berbeda. Tanpa syarat ini, kata pendek berhuruf besar
    yang kebetulan diikuti titik ikut terbaca sebagai item — nyata terjadi:
    "NIP.196911172001121002" di halaman pengesahan tercatut sebagai item ke-75
    pada daftar yang seharusnya berhenti di 74.

    Konsekuensi yang diterima: angka Romawi (i, ii, iii, iv, v) tidak lagi
    dikenali mulai dari "iv". Skema pengurutan yang ada memang sudah tidak
    menanganinya dengan benar, jadi tidak ada yang hilang.
    """
    return len(set(marker.lower())) == 1

def _penanda_maju(sekarang: str, sebelumnya: str) -> bool:
    """
    Benar bila penanda `sekarang` melanjutkan `sebelumnya`.

    Aturan pokoknya urutan biasa (lihat _enum_sort_key). Yang ditambahkan di
    sini adalah toleransi terhadap kerusakan OCR yang nyata terjadi pada korpus
    ini: halaman hasil pindai kerap kehilangan huruf berulang, sehingga "hhh."
    terbaca "h." dan "jjj." terbaca "jj.".

    Tanpa toleransi itu, penanda yang memendek terbaca sebagai MUNDUR, runtunnya
    terputus di batas halaman, dan daftar 74 item terpecah menjadi 59 + 15 —
    lalu yang 59 menang karena lebih panjang. Kegagalan itu tidak menampakkan
    diri sebagai galat; jawabannya hanya berhenti lebih awal dengan yakin.

    Toleransinya sengaja sempit: hanya bila hurufnya maju TEPAT SATU langkah
    (g -> h). Dua daftar berbeda yang kebetulan bersambung huruf tetap bisa
    salah gabung, tetapi itu jauh lebih jarang daripada OCR yang merontokkan
    huruf pada dokumen pindai.
    """
    kunci_kini, kunci_lalu = _enum_sort_key(sekarang), _enum_sort_key(sebelumnya)
    if kunci_kini > kunci_lalu:
        return True

    # Hanya berlaku antar-penanda huruf.
    if kunci_kini[0] != 1 or kunci_lalu[0] != 1:
        return False

    return ord(kunci_kini[2]) - ord(kunci_lalu[2]) == 1


def _extract_enumeration_runs(
    context_text: str,
) -> list[tuple[list[tuple[str, str]], int, int]]:
    """
    Pecah seluruh item berpenanda menjadi runtun-runtun yang penandanya maju terus.

    Kesinambungan urutan, BUKAN gaya penanda, yang menentukan batas antar daftar.
    Satu konteks kerap memuat beberapa daftar angka yang tak berhubungan — dasar
    hukum, langkah prosedur, peralatan — dan mengelompokkannya berdasarkan gaya
    akan menggabungkan ketiganya menjadi satu daftar palsu.

    Perbandingan memakai "lebih besar", bukan "penerus persis", supaya satu item
    yang terlewat saat OCR tidak memutus runtun.

    Returns:
        List of (daftar item [(penanda, isi)], posisi awal, posisi akhir) dalam
        karakter. Rentang awal–akhir dipakai untuk menilai relevansi: baris
        rincian DI ANTARA item (mis. "- Pelaksana:", "- Waktu:") berada di
        rentang itu, dan kerap justru di situlah kata pembeda pertanyaan berada.
    """
    runs: list[tuple[list[tuple[str, str]], int, int]] = []
    current: list[tuple[str, str]] = []
    previous_key = None
    previous_marker = ""
    start = end = 0

    for match in _ENUM_ITEM.finditer(context_text):
        marker, isi = match.group("tanda"), match.group("isi")
        if not marker.isdigit() and not _penanda_huruf_sah(marker):
            continue
        key = _enum_sort_key(marker)

        # Gaya berganti atau penanda tidak maju -> daftar baru dimulai.
        if previous_key is not None and (
            key[0] != previous_key[0] or not _penanda_maju(marker, previous_marker)
        ):
            runs.append((current, start, end))
            current = []
        if not current:
            # Dijangkar pada PENANDA, bukan awal baris: bila judulnya menyatu
            # ("Mengingat : 1. ..."), judul itu ikut terbaca sebagai teks
            # pengantar saat menilai daftar mana yang dimaksud pertanyaan.
            start = match.start("tanda")

        current.append((marker, isi))
        end = match.end()
        previous_key = key
        previous_marker = marker

    if current:
        runs.append((current, start, end))

    return runs


# Dokumen bisa memuat beberapa bagian berlabel yang isinya nyaris kembar.
# Pada korpus SOP ini, dua SOP berbeda punya daftar peralatan yang sama persis
# di enam butir pertama, dan bagian Kualifikasi yang identik kata per kata
# akibat salin-tempel di dokumen aslinya. Kata pertanyaan tidak membedakan
# keduanya, sehingga pemilihan jatuh ke pemutus terakhir — daftar terpanjang —
# dan pertanyaan tentang yang satu dijawab dengan daftar milik yang lain.
#
# Pembedanya DITURUNKAN dari label yang benar-benar ada di korpus, bukan dari
# daftar nama yang dipatok di kode. Mematoknya berarti layanan ini hanya
# bekerja untuk satu dokumen tertentu, padahal kode yang sama melayani seluruh
# dokumen yang di-ingest.
_POLA_LABEL_KONTEKS = _re.compile(r"\[Konteks:\s*([^\]]+)\]")

# Kata sependek tiga huruf terlalu sering muncul kebetulan untuk dipercaya
# sebagai pembeda; empat huruf menyaringnya tanpa membuang nama yang berarti.
_MIN_HURUF_PEMBEDA = 4


def _label_di_konteks(context_text: str) -> list[str]:
    """Seluruh label [Konteks: ...] yang ada di konteks, unik dan terurut."""
    return sorted({m.group(1).strip() for m in _POLA_LABEL_KONTEKS.finditer(context_text)})


def _kata_pembeda_label(labels: list[str]) -> dict:
    """
    Kata yang HANYA dimiliki satu label di antara label-label yang ada.

    Inilah yang menggantikan daftar nama yang dulu dipatok di kode. Kata yang
    dipakai bersama semua label ("sop", "penyusunan", "rencana") tidak
    membedakan apa pun dan otomatis gugur; yang tersisa justru kata penentu
    seperti nama khas tiap bagian. Berlaku untuk dokumen apa pun, karena
    daftarnya lahir dari isi korpus itu sendiri.

    Returns:
        Peta label -> himpunan kata pembedanya. Bisa kosong bila dua label
        kebetulan memakai kata yang sama semua.
    """
    kata = {
        label: set(_re.findall(rf"[a-z0-9]{{{_MIN_HURUF_PEMBEDA},}}", label.lower()))
        for label in labels
    }
    return {
        label: milik - set().union(*(lain for l, lain in kata.items() if l != label))
        if len(kata) > 1 else milik
        for label, milik in kata.items()
    }


def _label_yang_ditanya(query: str, labels: list[str]) -> list[str]:
    """Label mana yang disebut pertanyaan, dilihat dari kata pembedanya."""
    rendah = query.lower()
    pembeda = _kata_pembeda_label(labels)
    return [l for l in labels if any(k in rendah for k in pembeda[l])]

def _label_yang_menaungi(context_text: str, posisi: int) -> str:
    """Label [Konteks: ...] terdekat SEBELUM posisi, atau string kosong."""
    terakhir = ""
    for m in _POLA_LABEL_KONTEKS.finditer(context_text, 0, posisi):
        terakhir = m.group(1)
    return terakhir


def _saring_menurut_label(kandidat, context_text, query):
    """
    Buang runtun yang berada di bawah label yang jelas bukan yang ditanya.

    Hanya aktif bila pertanyaan menyebut TEPAT SATU label. Pertanyaan
    pembanding menyebut lebih dari satu dan justru MEMBUTUHKAN semuanya tetap
    ada; menyaringnya akan merusak jawaban yang selama ini sudah benar. Runtun
    tanpa label di atasnya tidak pernah dibuang, sebab ketiadaan label bukan
    bukti ketidakcocokan.
    """
    labels = _label_di_konteks(context_text)
    if len(labels) < 2:
        return kandidat            # tak ada yang bisa tertukar

    diminta = _label_yang_ditanya(query, labels)
    if len(diminta) != 1:
        return kandidat
    sasaran = diminta[0]

    tersisa = []
    for run, awal, akhir in kandidat:
        naungan = _label_yang_menaungi(context_text, awal).strip()
        if not naungan or naungan == sasaran:
            tersisa.append((run, awal, akhir))

    # Bila penyaringan menghabiskan semua calon, penyaringannya yang keliru.
    if not tersisa:
        return kandidat
    if len(tersisa) < len(kandidat):
        logger.info(
            "Saring label: %d dari %d runtun dibuang (pertanyaan tentang %s)",
            len(kandidat) - len(tersisa), len(kandidat), sasaran[:60],
        )
    return tersisa

def _select_relevant_run(
    runs: list[tuple[list[tuple[str, str]], int, int]],
    context_text: str,
    query: str,
) -> list[tuple[str, str]] | None:
    """
    Pilih runtun yang paling cocok dengan pertanyaan.

    Runtun terpanjang bukan jawabannya: satu dokumen bisa memuat daftar SOP 74
    item DAN daftar dasar hukum 13 item, dan pertanyaan tentang dasar hukum
    harus mendapat yang kedua. Penilaian memakai kata dari pertanyaan yang
    ditemukan di teks pengantar daftar plus beberapa item pertamanya.
    """
    # Seluruh runtun ikut dinilai, TERMASUK yang pendek. Menyaring yang panjang
    # lebih dulu adalah kesalahan: daftar terpanjang lalu menang tanpa lawan,
    # sehingga pertanyaan tentang dasar hukum (13 item) pun mendapat daftar SOP
    # 74 item hanya karena daftar pendeknya sudah tersingkir dari pencalonan.
    kandidat = [(r, a, b) for r, a, b in runs if len(r) >= 5]
    if not kandidat:
        return None

    kandidat = _saring_menurut_label(kandidat, context_text, query)

    kata = {
        w for w in _re.findall(r"\w+", query.lower())
        if len(w) > 2 and w not in _ENUM_STOPWORDS
    }
    if not kata:
        return None

    # Dinilai atas teks pengantar DAN seluruh rentang daftarnya. Membatasi
    # penilaian pada judul item saja membuat pertanyaan tentang rincian
    # ("siapa pelaksananya", "berapa waktunya") kehilangan kata pembedanya,
    # karena kata itu ada di baris rincian di antara item.
    ladang = [
        (context_text[max(0, awal - _ENUM_LEAD_IN):akhir]).lower()
        for _, awal, akhir in kandidat
    ]

    # Kata dibobot menurut KELANGKAAN di antara kandidat. Menghitung tiap kata
    # sama berat membuat kata umum menenggelamkan kata penentu: "sop", "dasar",
    # dan "hukum" muncul di hampir semua daftar sehingga tidak membedakan apa
    # pun, sedangkan "Mengingat" — yang hanya ada di satu daftar — justru
    # kalah suara meski ialah satu-satunya pembeda yang sesungguhnya.
    bobot = {}
    for w in kata:
        muncul = sum(1 for l in ladang if w in l)
        bobot[w] = 1.0 / muncul if muncul else 0.0

    skor = [
        (sum(bobot[w] for w in kata if w in l), len(run), run)
        for l, (run, _, _) in zip(ladang, kandidat)
    ]

    skor.sort(key=lambda x: (-x[0], -x[1]))
    terbaik = skor[0]

    # Tanpa satu pun kata pertanyaan yang cocok, tidak ada dasar untuk memilih.
    if terbaik[0] <= 0:
        return None
    # Daftar pendek disalin model dengan andal — membantu di situ hanya menambah
    # panjang konteks tanpa manfaat, dan berisiko mengganggu jawaban yang sudah benar.
    if terbaik[1] < _ENUM_MIN_ITEMS_FOR_HINT:
        return None

    return terbaik[2]


def _build_enumeration_answer(context_text: str, query: str) -> str | None:
    """
    Susun jawaban daftar lengkap secara terprogram, tanpa melibatkan LLM sama sekali.

    Menyisipkan daftar ke dalam konteks lalu meminta model menyalinnya sudah
    dicoba dan GAGAL: jawaban justru memburuk dari 46 item menjadi 31, dan
    jumlah yang disebut dari 46 menjadi 26. Menambah teks ke konteks membuat
    model makin buruk, bukan makin baik — sama seperti menambah instruksi.

    Jadi untuk kasus sempit ini — pertanyaan meminta daftar utuh, dan dokumen
    memuat daftar panjang yang relevan — daftarnya dikirim apa adanya. Pola yang
    sama sudah dipakai dua penjaga lain di generate_response: bila jawabannya
    bisa dipastikan tanpa model, jangan libatkan model.

    Returns:
        Teks jawaban siap kirim, atau None bila kasusnya tidak berlaku.
    """
    disodorkan = _jumlah_yang_disodorkan(query)
    minta_daftar_utuh = _is_list_query(query) and _asks_for_complete_list(query)
    if not minta_daftar_utuh and disodorkan is None:
        return None

    runs = _extract_enumeration_runs(context_text)
    run = _select_relevant_run(runs, context_text, query)
    if run is None:
        return None

    awal, akhir = next(((a, b) for r, a, b in runs if r is run), (0, 0))

    # Daftar yang tiap itemnya punya baris rincian sendiri — "- Pelaksana:",
    # "- Waktu:", "- Output:" — TIDAK boleh dijawab sebagai daftar datar:
    # jawabannya akan kehilangan justru bagian yang ditanyakan. Serahkan ke LLM.
    if _ENUM_SUBITEM.search(context_text[awal:akhir]):
        logger.info("Daftar terpilih memuat rincian bertingkat — diserahkan ke LLM")
        return None

    # Kalimat pengantar diambil dari dokumen (teks tepat sebelum daftarnya),
    # bukan dikarang — di situ biasanya tertulis daftar apa ini.
    pengantar = context_text[max(0, awal - _ENUM_LEAD_IN):awal]
    pengantar = _re.sub(r"\[[^\]]*\]", " ", pengantar)          # buang penanda [Halaman N] dsb
    pengantar = " ".join(pengantar.split())[-160:].strip()
    # Mulai dari batas kalimat supaya tidak terpotong di tengah kata.
    potong = _re.search(r"[.:;]\s+(\S.*)$", pengantar)
    if potong:
        pengantar = potong.group(1)

    # Sebutkan daftar ini milik SOP yang mana. Jawaban terprogram tidak melalui
    # LLM, jadi tidak ada tahap yang bisa menyadari salah ambil; menyebut
    # sumbernya membuat kekeliruan semacam itu langsung kelihatan oleh pembaca.
    label = _label_yang_menaungi(context_text, awal)
    asal = f" ({label})" if label else ""

    baris = [f"Terdapat **{len(run)}** item{asal}. Berikut daftar lengkapnya:"]
    if len(pengantar) > 20:
        baris = [f"{pengantar}", "", f"Terdapat **{len(run)}** item{asal} selengkapnya:"]

    # Bantahan didahulukan supaya pembaca tidak perlu menghitung sendiri untuk
    # tahu bahwa angka di pertanyaannya keliru. Disisipkan SESUDAH pengantar
    # dirakit, sebab perakitan itu menimpa seluruh isi baris.
    if disodorkan is not None and disodorkan != len(run):
        baris[:0] = [f"Tidak benar. Jumlah yang tercantum bukan {disodorkan}.", ""]
    baris.append("")
    baris += [f"{n}. {isi}" for n, (_, isi) in enumerate(run, 1)]

    logger.info(
        "Daftar %d item dijawab terprogram tanpa LLM (pertanyaan meminta daftar utuh)",
        len(run),
    )
    return "\n".join(baris)


# ─────────────────────────────────────────────────────────────
# TABEL PERBANDINGAN TERSTRUKTUR (untuk pertanyaan comparison)
# ─────────────────────────────────────────────────────────────

def _extract_list_items(block: str, field_name: str) -> list[str]:
    """Ekstrak daftar item dari sebuah field (misal Peralatan/Perlengkapan) dalam teks blok."""
    pattern = _re.compile(
        rf"[-*]?\s*\*{{0,2}}{_re.escape(field_name)}\*{{0,2}}:\s*\n(.*?)(?=\n\s*[-*]?\s*\*{{0,2}}\w|\Z)",
        _re.IGNORECASE | _re.DOTALL
    )
    match = pattern.search(block)
    if not match:
        return []
    raw = match.group(1)
    items = []
    for line in raw.splitlines():
        line = line.strip().lstrip("-*0123456789. ").strip()
        line = _re.sub(r"\*+", "", line).strip()
        if line:
            items.append(line)
    return items


def _build_comparison_hint(context_text: str, query: str) -> str:
    """
    Jika query adalah pertanyaan perbandingan antara dua SOP,
    bangun tabel perbandingan terstruktur dari context_text dan sisipkan di awal.
    Ini membantu LLM lokal yang lemah dalam reasoning perbandingan.

    PENTING: Pengelompokan blok dilakukan berdasarkan tag [Konteks: NAMA SOP]
    yang sudah tertanam di dalam teks chunk sejak proses ingestion — BUKAN
    berdasarkan document_id, karena beberapa SOP berbeda bisa berasal dari
    document_id yang sama (satu PDF berisi banyak SOP).
    """
    query_lower = query.lower()
    is_comparison = any(k in query_lower for k in [
        "perbedaan", "berbeda", "beda", "dibanding", "antara", "vs",
        "tidak dibutuhkan", "hanya ada di", "tidak ada di", "khusus",
    ])
    if not is_comparison:
        return context_text

    blocks = _re.split(r"\n---\n", context_text)
    sop_blocks: dict[str, str] = {}
    for block in blocks:
        match = _re.search(r"\[Konteks:\s*(.+?)\]", block)
        if match:
            sop_name = match.group(1).strip()
            if sop_name not in sop_blocks:
                sop_blocks[sop_name] = block
            else:
                # Gabungkan blok tambahan dari SOP yang sama (misal beda halaman)
                sop_blocks[sop_name] += "\n" + block

    if len(sop_blocks) < 2:
        return context_text

    FIELDS_TO_COMPARE = [
        "Peralatan/Perlengkapan", "Kualifikasi Pelaksana", "Keterkaitan",
        "Dasar Hukum", "Peringatan"
    ]

    sop_names = list(sop_blocks.keys())
    sop_a_name, sop_b_name = sop_names[0], sop_names[1]
    sop_a_text, sop_b_text = sop_blocks[sop_a_name], sop_blocks[sop_b_name]

    hint_lines = [
        "=== TABEL PERBANDINGAN TERSTRUKTUR (dihasilkan oleh sistem, gunakan ini untuk menjawab pertanyaan perbandingan) ===",
        f"SOP A: {sop_a_name}",
        f"SOP B: {sop_b_name}",
    ]

    for field in FIELDS_TO_COMPARE:
        items_a = set(_extract_list_items(sop_a_text, field))
        items_b = set(_extract_list_items(sop_b_text, field))
        if not items_a and not items_b:
            continue
        only_in_a = sorted(items_a - items_b)
        only_in_b = sorted(items_b - items_a)
        in_both = sorted(items_a & items_b)
        if only_in_a or only_in_b:
            hint_lines.append(f"\n[PERBANDINGAN: {field}]")
            if in_both:
                hint_lines.append(f"  SAMA di kedua SOP: {'; '.join(in_both)}")
            if only_in_a:
                hint_lines.append(f"  HANYA di {sop_a_name}: {'; '.join(only_in_a)}")
            if only_in_b:
                hint_lines.append(f"  HANYA di {sop_b_name}: {'; '.join(only_in_b)}")

    hint_lines.append("=== AKHIR TABEL PERBANDINGAN ===\n")
    hint_text = "\n".join(hint_lines)
    return hint_text + "\n\n---\n\n" + context_text


# ─────────────────────────────────────────────────────────────
# KEYWORD EXTRACTION & DETEKSI TIPE QUERY
# ─────────────────────────────────────────────────────────────

def _petunjuk_fokus_label(query: str, context_text: str) -> str:
    """
    Susun peringatan singkat bila konteks memuat lebih dari satu bagian berlabel.

    Konteks yang dikirim ke LLM kerap memuat dua bagian sekaligus yang isinya
    nyaris kembar. Model diberi kesempatan mencampur, lalu memang mencampur:
    pernah menjawab bahwa satu SOP berkaitan dengan SOP lain — padahal itu
    milik tetangganya — sambil mengarang rujukan halaman.

    Menyaring konteksnya sengaja TIDAK dilakukan: pertanyaan pembanding
    membutuhkan seluruh bagian tetap ada, dan empat pertanyaan semacam itu
    sudah terjawab benar. Yang ditambahkan hanya petunjuk, sehingga kasus
    terburuk dari salah deteksi cuma satu kalimat mubazir.

    Returns:
        Kalimat petunjuk, atau string kosong bila tidak berlaku.
    """
    labels = _label_di_konteks(context_text)
    if len(labels) < 2:
        return ""

    diminta = _label_yang_ditanya(query, labels)
    if len(diminta) != 1:
        return ""

    sasaran = diminta[0]
    lain = [l for l in labels if l != sasaran]
    return (
        "\n\nPENTING: Pertanyaan ini HANYA tentang " + sasaran + ". "
        "Konteks di atas juga memuat " + ", ".join(lain) + " yang isinya "
        "nyaris sama. Ambil jawaban HANYA dari bagian yang berlabel "
        + sasaran + "; jangan memakai data dari bagian yang lain."
    )

def _correct_query_typos(query: str) -> str:
    """
    Menggunakan LLM secara singkat untuk mengekstrak KATA KUNCI UTAMA (keyword)
    dari pertanyaan pengguna, agar hasil pencarian vektor lebih akurat dan tidak
    terdistraksi oleh kata pengantar yang panjang.
    """
    try:
        llm = ChatOllama(
            model=settings.LLM_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
            reasoning=False,
            keep_alive=_OLLAMA_KEEP_ALIVE,
            client_kwargs={"timeout": _OLLAMA_TIMEOUT},
        )
        prompt = (
            "Tugas Anda adalah mengekstrak SATU frasa kata kunci paling penting (subject matter) dari pertanyaan pengguna untuk sistem pencarian dokumen.\n"
            "Abaikan semua nama peraturan, nomor undang-undang, surat keputusan, atau kalimat pengantar. JANGAN HANYA mengekstrak kata generik seperti 'Prosedur', 'SOP', atau 'Perbedaan'. Ekstrak topik utamanya SESPESIFIK MUNGKIN, termasuk singkatan resmi jika ada (mis. IKU, RKA, DPA).\n\n"
            "Contoh 1:\n"
            "Pertanyaan: Berdasarkan Peraturan Bupati Nomor 12 Tahun 2023, apa saja syarat pengajuan Cuti Tahunan?\n"
            "Kata kunci: syarat pengajuan Cuti Tahunan\n\n"
            "Contoh 2:\n"
            "Pertanyaan: Sebutkan pihak yang terlibat dalam prosedur Pengadaan Barang dan Jasa di dokumen ini!\n"
            "Kata kunci: pihak Pengadaan Barang dan Jasa\n\n"
            "Contoh 3:\n"
            "Pertanyaan: bagaimana prosedur pelaporan Indikator Kinerja Utama?\n"
            "Kata kunci: prosedur pelaporan Indikator Kinerja Utama (IKU)\n\n"
            "Contoh 4:\n"
            "Pertanyaan: Berdasarkan daftar SOP pada Diktum KEDUA, sebutkan prosedur apa saja yang secara spesifik berkaitan dengan dokumen kinerja dan pelaporan instansi!\n"
            "Kata kunci: daftar SOP Diktum KEDUA\n\n"
            "Tugas Anda (berikan HANYA kata kuncinya, tanpa tanda kutip):\n"
            f"Pertanyaan: {query}\n"
            "Kata kunci:"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        corrected = response.content.strip()

        if corrected.startswith("'") and corrected.endswith("'"):
            corrected = corrected[1:-1]
        elif corrected.startswith('"') and corrected.endswith('"'):
            corrected = corrected[1:-1]

        if corrected.lower() != query.lower():
            logger.info("Query diekstrak menjadi keyword: '%s' -> '%s'", query, corrected)
        return corrected
    except Exception as e:
        logger.warning("Gagal mengekstrak query (fallback ke aslinya): %s", str(e))
        return query


def _is_list_query(query: str) -> bool:
    """Mendeteksi apakah pertanyaan pengguna meminta daftar panjang (list)."""
    query_lower = query.lower()
    keywords = ["apa saja", "sebutkan", "daftar", "macam-macam", "jenis-jenis", "semua"]
    return any(k in query_lower for k in keywords)


# ─────────────────────────────────────────────────────────────
# JENDELA KONTEKS & KETAHANAN TERHADAP KEGAGALAN ALOKASI
# ─────────────────────────────────────────────────────────────

def _hitung_num_ctx(context_text: str) -> int:
    """
    Menghitung jendela konteks seperlunya, bukan memakai angka yang dipatok.

    Taksiran tokennya sengaja dibuat melebihkan (pembagi kecil): konteks yang
    terpotong jauh lebih merugikan daripada jendela yang sedikit kebesaran.
    Hasilnya dibulatkan ke kelipatan 1024 dan dibatasi LLM_MAX_NUM_CTX.
    """
    perlu = int(len(context_text) / _CHARS_PER_TOKEN) + _NUM_CTX_RESPONSE_HEADROOM
    perlu = math.ceil(perlu / 1024) * 1024
    return max(_NUM_CTX_MIN, min(perlu, settings.LLM_MAX_NUM_CTX))


# Penanda bahwa kegagalan berasal dari memori, bukan sebab lain. Dicocokkan
# pada teks pesan karena Ollama meneruskannya sebagai ResponseError biasa —
# tidak ada tipe exception khusus yang bisa dibedakan.
_PENANDA_GAGAL_ALOKASI = (
    "failed to allocate",
    "out-of-memory",
    "out of memory",
    "cannot allocate",
    "llama-server process has terminated",
)


def _gagal_alokasi(e: Exception) -> bool:
    """Apakah kegagalan ini soal memori."""
    pesan = str(e).lower()
    return any(p in pesan for p in _PENANDA_GAGAL_ALOKASI)


def _stream_jawaban(
    system_prompt: str,
    query: str,
    num_ctx: int,
) -> Generator[str, None, None]:
    """
    Alirkan jawaban LLM, menurunkan jendela konteks bila Ollama kehabisan memori.

    Tanpa ini, satu kegagalan alokasi menjatuhkan seluruh permintaan — dan pada
    mesin ber-RAM terbatas kegagalan itu datang dan pergi mengikuti beban mesin,
    sehingga pertanyaan yang sama kadang berhasil kadang tidak.

    Percobaan ulang HANYA dilakukan bila kegagalan terjadi sebelum satu potong
    pun terkirim. Mengulang di tengah aliran akan menduplikasi teks yang sudah
    terbaca pengguna — lebih buruk daripada galat yang jujur.
    """
    tangga: list[int] = []
    n = num_ctx
    while n > _NUM_CTX_MIN:
        tangga.append(n)
        n //= 2
    tangga.append(_NUM_CTX_MIN)

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=query)]

    for i, jendela in enumerate(tangga):
        sudah_terkirim = False
        try:
            llm = ChatOllama(
                model=settings.LLM_MODEL_NAME,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.0,
                num_ctx=jendela,
                # Matikan mode thinking — lihat catatan di _correct_query_typos().
                # Tanpa ini, model thinking (qwen3.5) mengembalikan konten kosong.
                reasoning=False,
                keep_alive=_OLLAMA_KEEP_ALIVE,
                client_kwargs={"timeout": _OLLAMA_TIMEOUT},
            )
            for chunk in llm.stream(messages):
                if chunk.content:
                    sudah_terkirim = True
                    yield chunk.content
            return

        except Exception as e:
            if sudah_terkirim or i == len(tangga) - 1 or not _gagal_alokasi(e):
                raise
            logger.warning(
                "Ollama gagal mengalokasikan memori pada num_ctx=%d — dicoba ulang dengan %d",
                jendela, tangga[i + 1],
            )


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

def generate_response(
    query: str,
    session_id: str,
    document_ids: list[int] | None = None,
) -> Generator[str, None, None]:
    """
    Menghasilkan respons RAG secara streaming.

    Langkah-langkah:
    1. Cari konteks relevan di ChromaDB.
    2. Jika pertanyaan minta prosedur tapi konteks cuma daftar nama SOP,
       jawab langsung tanpa perlu panggil LLM.
    3. Bangun prompt dengan konteks (+ tabel perbandingan jika relevan).
    4. Panggil LLM Ollama dan stream hasilnya.
    5. Sertakan referensi sumber di akhir.

    Args:
        query: Pertanyaan dari pengguna.
        session_id: ID sesi chat (untuk logging dan tracking).
        document_ids: Bila diisi, pencarian dibatasi hanya pada dokumen tersebut.
            Bila None, mencari ke seluruh dokumen yang ada di koleksi.

    Yields:
        String berisi chunk-chunk respons dari LLM.
    """
    logger.info(
        "Memulai generate response — session=%s, query='%s'",
        session_id,
        query[:80],
    )

    try:
        corrected_query = _correct_query_typos(query)

        context_text, sources_text = _retrieve_context(
            corrected_query, original_query=query, document_ids=document_ids
        )

        if not context_text:
            yield "Maaf, saya tidak menemukan informasi tersebut di dokumen yang tersedia."
            return

        # Guard: pertanyaan menyebut entitas bernomor yang tidak ada di dokumen
        # (Diktum KEEMPAT, langkah ke-11). Dipasang PALING AWAL karena jalur
        # daftar terprogram di bawah menjawab tanpa melibatkan LLM sama sekali,
        # sehingga tidak ada tahap lain yang berkesempatan menyadari premisnya
        # palsu — ditanya Diktum KEEMPAT, ia pernah memuntahkan 74 SOP milik
        # Diktum KEDUA dengan penuh percaya diri.
        entitas = _entitas_tak_ada_di_konteks(query, context_text)
        if entitas is not None:
            logger.info("Premis palsu: %s tidak ada di konteks", entitas)
            yield (
                f"Maaf, {entitas} tidak ditemukan di dalam dokumen. "
                "Pastikan penomorannya sesuai dengan isi dokumen."
            )
            if sources_text:
                yield f"\n\n📚 **Sumber Referensi:**\n{sources_text}"
            return

        # Guard: pertanyaan minta prosedur, tapi konteks yang ditemukan cuma
        # daftar nama SOP (tanpa rincian) → jangan biarkan LLM mengarang.
        if (
            _is_procedure_question(query)
            and _context_is_sop_document(context_text)
            and not _context_has_full_procedure(context_text)
        ):
            logger.info("Konteks hanya berisi daftar nama SOP, bukan rincian prosedur — jawab langsung tanpa LLM.")
            yield "Dokumen hanya menyebutkan SOP ini sebagai salah satu item dalam daftar, namun tidak memuat rincian prosedurnya."
            if sources_text:
                yield f"\n\n📚 **Sumber Referensi:**\n{sources_text}"
            return

        # Guard: pertanyaan meminta daftar UTUH dan dokumen memuat daftar panjang
        # yang relevan → kirim daftarnya apa adanya. Model lokal terbukti
        # memotong daftar 74 item di sekitar item ke-46, dan tidak ada cara dari
        # sisi prompt maupun konteks yang memperbaikinya (lihat
        # _build_enumeration_answer).
        jawaban_daftar = _build_enumeration_answer(context_text, query)
        if jawaban_daftar is not None:
            yield jawaban_daftar
            if sources_text:
                yield f"\n\n📚 **Sumber Referensi:**\n{sources_text}"
            return

        context_text = _build_comparison_hint(context_text, query)
        context_text += _petunjuk_fokus_label(query, context_text)

        system_prompt = _SYSTEM_PROMPT.format(context=context_text)

        num_ctx = _hitung_num_ctx(system_prompt)
        logger.info(
            "Jendela konteks: %d token (konteks %d karakter, batas atas %d)",
            num_ctx, len(system_prompt), settings.LLM_MAX_NUM_CTX,
        )

        yield from _stream_jawaban(system_prompt, query, num_ctx)

        if sources_text:
            yield f"\n\n📚 **Sumber Referensi:**\n{sources_text}"

        logger.info("Respons berhasil di-generate untuk session %s", session_id)

    except Exception:
        # Rincian exception ditahan di log, tidak dikirim ke pengguna: pesan
        # mentah dari Ollama/ChromaDB kerap memuat URL internal dan path berkas.
        logger.error(
            "Gagal generate respons (session=%s)",
            session_id,
            exc_info=True,
        )
        yield (
            "\n\n⚠️ Terjadi kesalahan saat memproses pertanyaan Anda. "
            "Silakan coba lagi; bila berulang, hubungi administrator."
        )