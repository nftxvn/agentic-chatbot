"""Pencarian hybrid, cache BM25, reranking, dan penyusunan sitasi dokumen."""

import logging
import re
import threading

from app.config import settings
from app.database import get_document_names_by_ids
from app.services import tool_router
from app.services.embedding_service import (
    encode_query,
    get_chroma_collection,
    get_reranker_model,
    read_corpus_version,
)
from app.services.rag.grounding import _is_list_query

_re = re
logger = logging.getLogger("app.services.rag_service")
_bm25_lock = threading.Lock()

_TOP_K = 4

_MAX_CONTEXT_CHUNKS = 4

_MAX_CONTEXT_CHUNKS_LIST_QUERY = 20

_RRF_K = 60

_BM25_MIN_SCORE = 0.1

_ACRONYM_EXPANSIONS = {
    "renja": "Penyusunan Rencana Kerja (Renja)",
    "renstra": "Penyusunan Rencana Strategis (Renstra)",
    "rka": "Penyusunan Rencana Kegiatan Anggaran (RKA)",
    "lkjip": "Penyusunan Laporan Kinerja Instansi Pemerintah (LKjIP)",
    "lppd": "Penyiapan dan Kompilasi Data Capaian Kinerja Penyelenggaraan Pemerintah Daerah (LPPD)",
    "pk": "Penyusunan Perjanjian Kinerja (PK)",
    "dpa": "Dokumen Pelaksanaan Anggaran (DPA)",
    "iku": "Indikator Kinerja Utama (IKU)",
    "sakip": "Sistem Akuntabilitas Kinerja Instansi Pemerintah (SAKIP)",
    "csirt": "Penanganan Insiden Siber CSIRT",
    "smart city": "Smart City",
}


def _format_pages_list(pages: list[int]) -> str:
    """
    Format daftar nomor halaman integer menjadi string rentang atau koma yang rapi.
    Contoh: [3, 4, 5, 6] -> 'Halaman 3–6', [64, 65] -> 'Halaman 64, 65'.
    """
    if not pages:
        return ""
    sorted_pages = sorted(set(pages))
    ranges: list[str] = []
    start = sorted_pages[0]
    prev = sorted_pages[0]

    for p in sorted_pages[1:]:
        if p == prev + 1:
            prev = p
        else:
            if start == prev:
                ranges.append(str(start))
            elif prev == start + 1:
                ranges.append(f"{start}, {prev}")
            else:
                ranges.append(f"{start}-{prev}")
            start = p
            prev = p

    if start == prev:
        ranges.append(str(start))
    elif prev == start + 1:
        ranges.append(f"{start}, {prev}")
    else:
        ranges.append(f"{start}-{prev}")

    return f"Halaman {', '.join(ranges)}"


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

    with _bm25_lock:
        # Double check setelah memperoleh lock
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
        int_ids = [int(x) for x in document_ids if str(x).isdigit()]
        if int_ids:
            conditions.append(
                {"document_id": {"$in": int_ids}}
                if len(int_ids) > 1
                else {"document_id": int_ids[0]}
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
    top_k_override: int | None = None,
    return_chunks_info: bool = False,
) -> tuple[str, str] | tuple[str, str, list[dict]]:
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
        document_ids: Daftar ID dokumen untuk membatasi pencarian.
        top_k_override: Override jumlah chunk yang diambil (untuk testing sandbox).
        return_chunks_info: Bila True, mengembalikan tuple (context, sources, debug_chunks).

    Returns:
        Tuple (context_text, sources_text) atau (context_text, sources_text, debug_chunks).
    """
    collection = get_chroma_collection()
    reranker = get_reranker_model()

    check_query = original_query if original_query else query
    is_list = _is_list_query(check_query)
    base_k = top_k_override if top_k_override is not None else _TOP_K
    max_chunks = _MAX_CONTEXT_CHUNKS_LIST_QUERY if is_list else _MAX_CONTEXT_CHUNKS

    # Bila reranker aktif, perluas pencarian awal (Stage 1 High Recall) agar kandidat lebih komprehensif
    if reranker is not None:
        stage1_k = max(base_k * 3, settings.RERANKER_TOP_CANDIDATES)
        top_k = base_k * 4 if is_list else stage1_k
    else:
        top_k = base_k * 4 if is_list else base_k

    if is_list:
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

        # Normalisasi slang/typo untuk query pencarian
        norm_q = tool_router.normalize_query(query)
        norm_orig = tool_router.normalize_query(original_query) if original_query else ""
        if norm_q and norm_q != query.lower():
            queries.append(norm_q)
        if norm_orig and norm_orig != original_query.lower() and norm_orig != norm_q:
            queries.append(norm_orig)

        # Deteksi akronim domain & tambahkan query spesifik
        search_corpus_text = f"{query} {original_query} {norm_q} {norm_orig}".lower()
        acronym_anchors = []
        for acr_key, full_name in _ACRONYM_EXPANSIONS.items():
            if _re.search(rf"\b{acr_key}\b", search_corpus_text):
                acronym_anchors.append(f"SOP {full_name}")
                acronym_anchors.append(f"Prosedur {full_name}")
                acronym_anchors.append(full_name)

        if acronym_anchors:
            queries.extend(acronym_anchors)

        # Tambahkan anchor kata kunci inti untuk meningkatkan recall pada pertanyaan percakapan panjang
        clean_core = _re.sub(
            r"\b(jika|hari\s+ini|saya|mengajukan|pengajuan|untuk|kapan|siapnya|kapan\s+siapnya|estimasinya|estimasi|berapa|lama|proses|syarat|prosedur|tata\s+cara|langkah)\b",
            " ",
            query,
            flags=_re.IGNORECASE,
        ).strip()
        clean_core = " ".join(clean_core.split())
        if clean_core and len(clean_core) >= 4 and clean_core.lower() != query.lower():
            queries.append(f"SOP {clean_core}")
            queries.append(f"Pelaksanaan {clean_core}")
            queries.append(clean_core)

        if is_list:
            # Anchor query membantu menemukan halaman yang memuat daftar/enumerasi master SOP
            queries.extend([
                "Standar Operasional Prosedur sebagaimana dimaksud dalam Diktum Kesatu terdiri dari",
                "Diktum KEDUA Standar Operasional Prosedur",
                "MEMUTUSKAN Menetapkan KESATU KEDUA",
                "Penyusunan Rencana Strategis Renstra Penyusunan Rencana Kerja Renja",
                "daftar Standar Operasional Prosedur SOP",
                "Layanan Permintaan Data Sektoral",
            ])
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
            q_embedding = encode_query(q)

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

                # Filter kata-kata generik domain kedinasan agar kata topik spesifik (mis: 'subdomain', 'cuti') tidak tenggelam
                domain_stopwords = {
                    "persyaratan", "syarat", "pengajuan", "layanan", "sop", "prosedur", "tata", "cara",
                    "bagaimana", "apa", "saja", "tentang", "pada", "dinas", "kota", "banda", "aceh",
                    "untuk", "dari", "dan", "yang", "di", "ke", "ini", "itu", "diskominfotik", "diskominfo"
                }
                raw_tokens = q.lower().split()
                meaningful_tokens = [w for w in raw_tokens if w not in domain_stopwords]
                tokenized_query = meaningful_tokens if meaningful_tokens else raw_tokens
                bm25_scores = bm25.get_scores(tokenized_query)
                if top_k > 0 and len(all_docs) > 0:
                    # Indeks BM25 dibangun atas SELURUH korpus (agar bisa di-cache),
                    # jadi pembatasan dokumen diterapkan di sini saat menyaring hasil.
                    # Urutan diambil penuh lalu dipotong setelah filter, supaya jatah
                    # top_k tidak habis terpakai oleh dokumen yang justru dikecualikan.
                    doc_filter = {int(x) for x in document_ids if str(x).isdigit()} if document_ids else None
                    for idx in np.argsort(bm25_scores)[::-1]:
                        if len(bm25_ranked_ids) >= top_k:
                            break
                        score = bm25_scores[idx]
                        if score <= _BM25_MIN_SCORE:
                            break  # sisanya pasti lebih kecil — hemat iterasi
                        meta_doc_id = all_metas[idx].get("document_id")
                        if doc_filter is not None and (meta_doc_id is None or int(meta_doc_id) not in doc_filter):
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
            if return_chunks_info:
                return "", "", []
            return "", ""

        initial_ranked_ids = sorted(
            aggregated_rrf.keys(),
            key=lambda cid: aggregated_rrf[cid],
            reverse=True,
        )

        # ── Tahap 2: CrossEncoder Reranking (BGE-Reranker) ──
        # Menghitung relevansi mendalam pasangan (query, chunk) untuk menyaring false-positives
        # dan memprioritaskan potongan paling presisi.
        rerank_scores: dict[str, float] = {}

        if reranker is not None and initial_ranked_ids:
            scoring_query = original_query.strip() if original_query and original_query.strip() else query.strip()
            candidate_limit = max(settings.RERANKER_TOP_CANDIDATES, 40) if is_list else settings.RERANKER_TOP_CANDIDATES
            candidates_to_rerank = initial_ranked_ids[:candidate_limit]

            try:
                if is_list:
                    list_anchors = [
                        scoring_query,
                        "Standar Operasional Prosedur sebagaimana dimaksud dalam Diktum Kesatu terdiri dari",
                        "Diktum KEDUA Standar Operasional Prosedur",
                        "daftar Standar Operasional Prosedur SOP",
                    ]
                    all_pairs = [(sq, chunk_data[cid][0]) for cid in candidates_to_rerank for sq in list_anchors]
                    raw_scores = reranker.predict(all_pairs, batch_size=32)
                    n_anchors = len(list_anchors)
                    for i, cid in enumerate(candidates_to_rerank):
                        c_scores = raw_scores[i * n_anchors : (i + 1) * n_anchors]
                        rerank_scores[cid] = float(max(c_scores))
                else:
                    scoring_anchors = [query.strip()]
                    if original_query and original_query.strip() != query.strip():
                        scoring_anchors.append(original_query.strip())
                    if norm_q and norm_q not in scoring_anchors:
                        scoring_anchors.append(norm_q)
                    if norm_orig and norm_orig not in scoring_anchors:
                        scoring_anchors.append(norm_orig)
                    if acronym_anchors:
                        scoring_anchors.extend(acronym_anchors[:4])
                    if clean_core:
                        scoring_anchors.append(f"SOP {clean_core}")
                        scoring_anchors.append(f"Pelaksanaan {clean_core}")
                    elif not query.lower().startswith("sop "):
                        scoring_anchors.append(f"SOP {query.strip()}")

                    all_pairs = [(sq, chunk_data[cid][0]) for cid in candidates_to_rerank for sq in scoring_anchors]
                    raw_scores = reranker.predict(all_pairs, batch_size=32)
                    n_anchors = len(scoring_anchors)
                    for i, cid in enumerate(candidates_to_rerank):
                        c_scores = raw_scores[i * n_anchors : (i + 1) * n_anchors]
                        rerank_scores[cid] = float(max(c_scores))

                # Filter potongan yang berada di bawah ambang batas relevansi minimum
                surviving_ids = [
                    cid for cid in candidates_to_rerank
                    if rerank_scores[cid] >= settings.RERANKER_MIN_SCORE
                ]

                if surviving_ids:
                    ranked_chunk_ids = sorted(
                        surviving_ids,
                        key=lambda cid: rerank_scores[cid],
                        reverse=True,
                    )
                    top_score = rerank_scores[ranked_chunk_ids[0]]

                    # Dynamic Adaptive Pruning (Relative Gap & Score-Drop Cutoff)
                    # Pangkas potongan yang skornya anjlok jauh di bawah peringkat #1
                    if len(ranked_chunk_ids) > 1:
                        if is_list:
                            # Pada list query: jika terdapat chunk master daftar dengan keyakinan sangat tinggi (>= 0.90),
                            # perketat cutoff ke 0.90 agar potongan rincian SOP tunggal tidak ikut terseret.
                            if top_score >= 0.90:
                                relative_cutoff = 0.90
                            elif top_score >= 0.70:
                                relative_cutoff = max(0.50, top_score * 0.60)
                            else:
                                relative_cutoff = settings.RERANKER_MIN_SCORE
                        else:
                            # Rasio toleransi: pertahankan chunk yang skornya minimal 50% dari skor peringkat #1 bila positif
                            if top_score > 0:
                                relative_cutoff = max(settings.RERANKER_MIN_SCORE, top_score * 0.50)
                                if top_score >= 0.15:
                                    relative_cutoff = max(relative_cutoff, top_score * 0.60)
                            else:
                                relative_cutoff = settings.RERANKER_MIN_SCORE

                        pruned_ids = [
                            cid for cid in ranked_chunk_ids
                            if rerank_scores[cid] >= relative_cutoff
                        ]
                        if pruned_ids:
                            ranked_chunk_ids = pruned_ids

                    logger.info(
                        "BGE-Reranker: %d kandidat dinilai -> %d chunk lolos cutoff dinamis (skor terbaik: %.4f, terendah: %.4f)",
                        len(candidates_to_rerank),
                        len(ranked_chunk_ids),
                        rerank_scores[ranked_chunk_ids[0]],
                        rerank_scores[ranked_chunk_ids[-1]],
                    )
                else:
                    logger.info(
                        "BGE-Reranker: seluruh %d kandidat di bawah threshold %.4f (pertanyaan di luar domain)",
                        len(candidates_to_rerank),
                        settings.RERANKER_MIN_SCORE,
                    )
                    ranked_chunk_ids = []
            except Exception as e:
                logger.warning("BGE-Reranker gagal inferensi, fallback ke urutan RRF: %s", e)
                ranked_chunk_ids = initial_ranked_ids
        else:
            ranked_chunk_ids = initial_ranked_ids

        if not ranked_chunk_ids:
            logger.info("Tidak ada dokumen yang lolos ambang batas reranker untuk query: '%s'", query[:80])
            if return_chunks_info:
                return "", "", []
            return "", ""

        # ── Tahap 3: Ambil parent chunks dari child yang cocok ──
        if use_hierarchical:
            child_limit = len(ranked_chunk_ids) if is_list else base_k
            top_children_ids = ranked_chunk_ids[:child_limit]

            parent_ids_ordered: list[str] = []
            parent_best_score: dict[str, float] = {}
            parent_best_rerank: dict[str, float | None] = {}
            for chunk_id in top_children_ids:
                _, metadata = chunk_data[chunk_id]
                pid = metadata.get("parent_id")
                score = aggregated_rrf.get(chunk_id, 0.0)
                r_score = rerank_scores.get(chunk_id)
                if pid and pid not in parent_best_score:
                    parent_ids_ordered.append(pid)
                    parent_best_score[pid] = score
                    parent_best_rerank[pid] = r_score
                elif pid:
                    if score > parent_best_score.get(pid, float("-inf")):
                        parent_best_score[pid] = score
                    if r_score is not None:
                        curr_r = parent_best_rerank.get(pid)
                        if curr_r is None or r_score > curr_r:
                            parent_best_rerank[pid] = r_score

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
                    r_score = parent_best_rerank.get(pid)
                    combined.append((doc, meta, score, r_score))

                # Jika reranker aktif, utamakan pengurutan parent berdasarkan skor rerank tertinggi
                if reranker is not None and any(x[3] is not None for x in combined):
                    combined.sort(key=lambda x: (x[3] if x[3] is not None else -1.0), reverse=True)
                    top_parent_score = combined[0][3] if combined[0][3] is not None else 0.0
                    min_confidence = max(0.10, settings.RERANKER_MIN_SCORE)
                    if top_parent_score < min_confidence:
                        logger.info("Relevance Gate: Skor parent reranker teratas (%.4f) < threshold (%.4f). Mengabaikan konteks.", top_parent_score, min_confidence)
                        combined = []
                    elif len(combined) > 1:
                        if is_list:
                            if top_parent_score >= 0.90:
                                parent_cutoff = 0.90
                            elif top_parent_score >= 0.70:
                                parent_cutoff = max(0.50, top_parent_score * 0.60)
                            else:
                                parent_cutoff = min_confidence
                        else:
                            parent_cutoff = max(min_confidence, top_parent_score * 0.50)
                            if top_parent_score >= 0.15:
                                parent_cutoff = max(parent_cutoff, top_parent_score * 0.60)
                        combined = [x for x in combined if (x[3] is not None and x[3] >= parent_cutoff)]
                else:
                    combined.sort(key=lambda x: x[2], reverse=True)

                combined = combined[:max_chunks]

                # SOP Sibling Pairing:
                # Bila bukan list query, setiap chunk SOP (Identitas atau Prosedur) harus dilengkapi dengan
                # seluruh halaman pasangannya dari SOP yang sama agar LLM mendapatkan konteks prosedur & identitas yang utuh.
                if not is_list and combined:
                    paired_combined = list(combined)
                    existing_p_keys = {
                        (int(m.get("document_id", 0)), int(m.get("page_number", 0)))
                        for _, m, _, _ in combined
                    }
                    sop_contexts_to_fetch = set()
                    for d_text, m, _, _ in combined:
                        d_id = m.get("document_id")
                        if not d_id or not str(d_id).isdigit():
                            continue
                        ctx_match = _re.search(r'\[Konteks:\s*(.*?)\]', d_text, _re.IGNORECASE)
                        if ctx_match:
                            c_tag = ctx_match.group(1).strip()
                            if "sop" in c_tag.lower():
                                sop_contexts_to_fetch.add((int(d_id), c_tag.lower()))

                    if sop_contexts_to_fetch:
                        for d_id, c_tag_lower in sop_contexts_to_fetch:
                            try:
                                all_doc_parents = collection.get(
                                    where={"$and": [{"document_id": d_id}, {"chunk_type": "parent"}]},
                                    include=["documents", "metadatas"],
                                )
                                sib_docs = all_doc_parents.get("documents", [])
                                sib_metas = all_doc_parents.get("metadatas", [])
                                for s_doc, s_meta in zip(sib_docs, sib_metas):
                                    s_page = int(s_meta.get("page_number", 0))
                                    if (d_id, s_page) in existing_p_keys:
                                        continue
                                    s_ctx_match = _re.search(r'\[Konteks:\s*(.*?)\]', s_doc, _re.IGNORECASE)
                                    if s_ctx_match and s_ctx_match.group(1).strip().lower() == c_tag_lower:
                                        paired_combined.append((s_doc, s_meta, 0.0, 1.0))
                                        existing_p_keys.add((d_id, s_page))
                            except Exception as e:
                                logger.warning("Gagal fetch sibling SOP parent chunks: %s", e)

                    combined = paired_combined

                # Jika list query dan memuat potongan Diktum KEDUA / MEMUTUSKAN,
                # pastikan seluruh halaman lanjutan diktum tersebut tersambung utuh.
                if is_list:
                    expanded_combined = list(combined)
                    for doc_text, meta, score, r_score in combined:
                        doc_lower = doc_text.lower()
                        if "diktum kesatu terdiri dari" in doc_lower or "kedua :" in doc_lower or "memutuskan :" in doc_lower:
                            doc_id = meta.get("document_id")
                            page_num = meta.get("page_number", 1)
                            if doc_id:
                                next_results = collection.get(
                                    where={"$and": [{"document_id": doc_id}, {"chunk_type": "parent"}]},
                                    include=["documents", "metadatas"],
                                )
                                all_p_docs = next_results.get("documents", [])
                                all_p_metas = next_results.get("metadatas", [])
                                p_by_page = {pm.get("page_number"): (pd, pm) for pd, pm in zip(all_p_docs, all_p_metas)}

                                curr_page = page_num + 1
                                while curr_page in p_by_page:
                                    pdoc, pmeta = p_by_page[curr_page]
                                    if not any(pm.get("page_number") == curr_page and pm.get("document_id") == doc_id for _, pm, _, _ in expanded_combined):
                                        expanded_combined.append((pdoc, pmeta, score, 1.0))
                                    pdoc_lower = pdoc.lower()
                                    if "ketiga :" in pdoc_lower or "diktum ketiga" in pdoc_lower or "ditetapkan di banda aceh" in pdoc_lower:
                                        break
                                    curr_page += 1
                    combined = expanded_combined

                # Batasi maksimum chunk terakumulasi agar tidak meluap melampaui context window LLM
                max_allowed_chunks = _MAX_CONTEXT_CHUNKS_LIST_QUERY if is_list else _MAX_CONTEXT_CHUNKS
                if len(combined) > max_allowed_chunks:
                    combined = combined[:max_allowed_chunks]

                # Sort ulang untuk presentasi ke LLM berdasarkan urutan dokumen (page + chunk_index)
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))

                logger.info(
                    "Two-Stage RAG: %d child cocok -> %d parent unik -> %d dikirim ke LLM",
                    len(ranked_chunk_ids), len(parent_ids_ordered), len(combined),
                )
            else:
                combined = [
                    (chunk_data[cid][0], chunk_data[cid][1], aggregated_rrf.get(cid, 0.0), rerank_scores.get(cid))
                    for cid in ranked_chunk_ids[:max_chunks]
                ]
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))
        else:
            combined = [
                (chunk_data[cid][0], chunk_data[cid][1], aggregated_rrf.get(cid, 0.0), rerank_scores.get(cid))
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

        # ── Tahap 4: Bangun teks konteks dan sumber ──
        context_parts: list[str] = []
        doc_pages_for_sources: dict[str, set[int]] = {}
        non_page_sources: set[str] = set()

        # Ambil nama asli dokumen dari database untuk sitasi yang informatif
        doc_ids_set = {
            int(meta.get("document_id"))
            for _, meta, _, _ in combined
            if meta.get("document_id") is not None and str(meta.get("document_id")).isdigit()
        }
        doc_names_map: dict[int, str] = {}
        if doc_ids_set:
            try:
                doc_names_map = get_document_names_by_ids(doc_ids_set)
            except Exception as e:
                logger.warning("Gagal mengambil nama dokumen untuk sitasi: %s", str(e))

        debug_chunks: list[dict] = []
        for doc_text, metadata, rrf_score, r_score in combined:
            doc_id = metadata.get("document_id", "?")
            page_num = metadata.get("page_number", "?")
            chunk_idx = metadata.get("chunk_index", "?")
            chunk_type = metadata.get("chunk_type", "flat")

            doc_name = doc_names_map.get(int(doc_id)) if str(doc_id).isdigit() else None
            display_title = doc_name or f"Dokumen #{doc_id}"

            score_labels = [f"skor RRF: {rrf_score:.4f}"]
            if r_score is not None:
                score_labels.append(f"Rerank: {r_score:.4f}")
            score_str = ", ".join(score_labels)

            context_parts.append(
                f"[Sumber: {display_title}, Halaman {page_num}, "
                f"Chunk #{chunk_idx} ({chunk_type}) "
                f"({score_str})]\n{doc_text}"
            )

            # Agregasikan nomor halaman per dokumen
            if str(page_num).isdigit():
                doc_pages_for_sources.setdefault(display_title, set()).add(int(page_num))
            else:
                non_page_sources.add(f"{display_title} — Halaman {page_num}")

            if return_chunks_info:
                chunk_item = {
                    "id": metadata.get("chunk_id", f"{doc_id}-{page_num}-{chunk_idx}"),
                    "document_id": doc_id,
                    "document_name": display_title,
                    "page_number": page_num,
                    "chunk_index": chunk_idx,
                    "chunk_type": chunk_type,
                    "rrf_score": round(float(rrf_score), 4),
                    "content": doc_text,
                }
                if r_score is not None:
                    chunk_item["rerank_score"] = round(float(r_score), 4)
                debug_chunks.append(chunk_item)

        context_text = "\n\n---\n\n".join(context_parts)

        # Susun daftar sumber yang ringkas, bersih, dan teragregasi
        sources_lines: list[str] = []
        for d_title in sorted(doc_pages_for_sources.keys()):
            pages_list = sorted(doc_pages_for_sources[d_title])
            sources_lines.append(f"- {d_title} - {_format_pages_list(pages_list)}")
        for np in sorted(non_page_sources):
            sources_lines.append(f"- {np}")

        sources_text = "\n".join(sources_lines)

        best_score = max(aggregated_rrf.values()) if aggregated_rrf else 0.0
        logger.info(
            "Ditemukan %d konteks unik dari %d query (skor RRF terbaik: %.4f), "
            "dikirim %d chunk ke LLM",
            len(ranked_chunk_ids),
            len(queries),
            best_score,
            len(combined),
        )

        if settings.DEBUG_DUMP_CONTEXT:
            try:
                with open("debug_context.txt", "w", encoding="utf-8") as f:
                    f.write(context_text)
            except OSError as e:
                logger.warning("Gagal menulis debug_context.txt: %s", e)

        if return_chunks_info:
            return context_text, sources_text, debug_chunks
        return context_text, sources_text

    except Exception:
        # exc_info=True: tanpa jejak lengkapnya, kegagalan retrieval tidak bisa
        # dibedakan dari "memang tidak ada dokumen yang relevan".
        logger.error("Gagal melakukan pencarian konteks", exc_info=True)
        if return_chunks_info:
            return "", "", []
        return "", ""
