"""
Service RAG (Retrieval-Augmented Generation).
Melakukan pencarian konteks di ChromaDB dan menghasilkan jawaban
menggunakan LLM Ollama secara streaming.
"""

import logging
import re as _re
from typing import Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.services.embedding_service import get_chroma_collection, get_embedding_model

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# KONSTANTA
# ─────────────────────────────────────────────────────────────

# Jumlah dokumen konteks yang diambil per query oleh vector store
_TOP_K = 10

# Jumlah chunk maksimum yang dikirim ke LLM setelah multi-query aggregation.
_MAX_CONTEXT_CHUNKS = 7

# Limit lebih longgar khusus untuk query bertipe daftar/list lengkap
_MAX_CONTEXT_CHUNKS_LIST_QUERY = 20

# Konteks LLM yang lebih besar khusus untuk pertanyaan yang menghasilkan daftar panjang
_NUM_CTX_LIST_QUERY = 16384

# Konstanta k untuk Reciprocal Rank Fusion (RRF).
# Nilai standar di literatur information retrieval adalah 60.
_RRF_K = 60

# Ambang batas skor BM25 minimum agar sebuah chunk dianggap "match" secara leksikal.
_BM25_MIN_SCORE = 0.1

# Timeout (detik) untuk request ke Ollama. Dinaikkan karena inferensi di CPU bisa lambat.
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

    Invalidasi memakai `collection.count()`: kalau jumlah vektor sama seperti saat
    indeks dibangun, korpus dianggap tidak berubah dan indeks lama dipakai kembali.
    Untuk perubahan yang tidak mengubah jumlah (mis. re-ingest dokumen yang sama
    dengan isi berbeda), panggil invalidate_bm25_cache() secara eksplisit.

    Returns:
        Dict berisi bm25, docs, ids, metas, dan flag hierarchical.
    """
    global _bm25_cache

    try:
        current_count = collection.count()
    except Exception:
        current_count = -1

    if _bm25_cache is not None and _bm25_cache["count"] == current_count:
        return _bm25_cache

    empty = {"bm25": None, "docs": [], "ids": [], "metas": [],
             "hierarchical": True, "count": current_count}

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
        queries = [query]

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

        with open("debug_context.txt", "w", encoding="utf-8") as f:
            f.write(context_text)

        return context_text, sources_text

    except Exception as e:
        logger.error("Gagal melakukan pencarian konteks: %s", str(e))
        return "", ""


# ─────────────────────────────────────────────────────────────
# DETEKSI: KONTEKS HANYA BERISI NAMA SOP (BUKAN RINCIAN PROSEDUR)
# ─────────────────────────────────────────────────────────────

def _context_has_full_procedure(context_text: str) -> bool:
    """
    Cek apakah konteks berisi rincian prosedur SOP (Dasar Hukum, Kualifikasi
    Pelaksana, Peralatan/Perlengkapan, langkah-langkah, dsb) — bukan cuma
    daftar nama/judul SOP seperti yang ada di Diktum KEDUA.
    """
    return any(marker in context_text for marker in _SOP_DETAIL_MARKERS)


def _is_procedure_question(query: str) -> bool:
    """Mendeteksi apakah pertanyaan meminta prosedur/langkah-langkah suatu SOP."""
    query_lower = query.lower()
    return any(k in query_lower for k in _PROCEDURE_QUESTION_KEYWORDS)


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
            timeout=_OLLAMA_TIMEOUT,
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

        # Guard: pertanyaan minta prosedur, tapi konteks yang ditemukan cuma
        # daftar nama SOP (tanpa rincian) → jangan biarkan LLM mengarang.
        if _is_procedure_question(query) and not _context_has_full_procedure(context_text):
            logger.info("Konteks hanya berisi daftar nama SOP, bukan rincian prosedur — jawab langsung tanpa LLM.")
            yield "Dokumen hanya menyebutkan SOP ini sebagai salah satu item dalam daftar, namun tidak memuat rincian prosedurnya."
            if sources_text:
                yield f"\n\n📚 **Sumber Referensi:**\n{sources_text}"
            return

        context_text = _build_comparison_hint(context_text, query)

        system_prompt = _SYSTEM_PROMPT.format(context=context_text)

        num_ctx = _NUM_CTX_LIST_QUERY if _is_list_query(query) else 8192
        llm = ChatOllama(
            model=settings.LLM_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,
            num_ctx=num_ctx,
            # Matikan mode thinking — lihat catatan di _correct_query_typos().
            # Tanpa ini, model thinking (qwen3.5) mengembalikan konten kosong.
            reasoning=False,
            keep_alive=_OLLAMA_KEEP_ALIVE,
            timeout=_OLLAMA_TIMEOUT,
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        for chunk in llm.stream(messages):
            if chunk.content:
                yield chunk.content

        if sources_text:
            yield f"\n\n📚 **Sumber Referensi:**\n{sources_text}"

        logger.info("Respons berhasil di-generate untuk session %s", session_id)

    except Exception as e:
        logger.error(
            "Gagal generate respons (session=%s): %s",
            session_id,
            str(e),
        )
        yield f"\n\n⚠️ Terjadi kesalahan saat memproses pertanyaan Anda: {str(e)}"