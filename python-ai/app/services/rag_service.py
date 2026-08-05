"""
Service RAG (Retrieval-Augmented Generation).
Melakukan pencarian konteks di ChromaDB dan menghasilkan jawaban
menggunakan LLM Ollama secara streaming.
"""

import logging
from typing import Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.services.embedding_service import get_chroma_collection, get_embedding_model

logger = logging.getLogger(__name__)

# Jumlah dokumen konteks yang diambil per query oleh vector store
# Dinaikkan ke 20 agar prosedur yang tersebar di banyak halaman semua ter-retrieve
_TOP_K = 10

# Jumlah chunk maksimum yang dikirim ke LLM setelah multi-query aggregation.
# Dikurangi menjadi 5 agar prompt tidak terlalu panjang dan membebani komputasi LLM
# (karena sekarang kueri sudah lebih spesifik berkat keyword extraction).
_MAX_CONTEXT_CHUNKS = 7

# Limit lebih longgar khusus untuk query bertipe daftar/list lengkap
_MAX_CONTEXT_CHUNKS_LIST_QUERY = 20

# Konteks LLM yang lebih besar khusus untuk pertanyaan yang menghasilkan daftar panjang
_NUM_CTX_LIST_QUERY = 16384

# System prompt untuk LLM — instruksi perilaku model
_SYSTEM_PROMPT = """Anda adalah asisten AI yang bertugas menjawab pertanyaan secara akurat berdasarkan dokumen yang diberikan.
Pahami konteks pertanyaan dengan baik dan berikan jawaban yang relevan, komprehensif, dan mudah dipahami.
Gunakan HANYA informasi dari TEKS DOKUMEN di bawah ini. Jangan mengarang informasi.
Jika pertanyaan meminta daftar, prosedur, atau penjelasan, rangkum poin-poin yang paling sesuai dari dokumen.
Jika informasi tidak ada dalam TEKS DOKUMEN, jawab: "Maaf, informasi tersebut tidak ditemukan dalam dokumen."

TEKS DOKUMEN:
{context}

Jawablah dengan rapi (gunakan poin-poin jika perlu) dan langsung ke intinya tanpa pengantar yang bertele-tele."""


def _retrieve_context(query: str, original_query: str = "") -> tuple[str, str]:
    """
    Melakukan pencarian similarity di ChromaDB berdasarkan query pengguna.
    Menggunakan strategi Parent-Child Retrieval:
    1. Cari child chunks (kecil, presisi) yang paling relevan.
    2. Ambil parent chunks (besar, lengkap) sebagai konteks ke LLM.

    Fallback ke flat retrieval jika data lama tanpa chunk_type ditemukan.

    Args:
        query: Pertanyaan dari pengguna (biasanya versi kata kunci).
        original_query: Pertanyaan asli pengguna tanpa filtering (untuk deteksi intent).

    Returns:
        Tuple berisi (context_text, sources_text).
    """
    model = get_embedding_model()
    collection = get_chroma_collection()

    # Tentukan limit chunk secara dinamis: lebih longgar untuk query "daftar/list"
    check_query = original_query if original_query else query
    max_chunks = _MAX_CONTEXT_CHUNKS_LIST_QUERY if _is_list_query(check_query) else _MAX_CONTEXT_CHUNKS
    if max_chunks != _MAX_CONTEXT_CHUNKS:
        logger.info("Query terdeteksi sebagai list-query, max_chunks dinaikkan ke %d", max_chunks)

    try:
        # Gunakan query yang diberikan langsung
        queries = [query]

        # ── Tahap 1: Cari child chunks yang relevan (Hybrid BM25 + Vector) ──
        seen: dict[str, tuple[str, dict, float]] = {}
        use_hierarchical = True

        # Inisialisasi BM25 untuk Hybrid Search
        try:
            from rank_bm25 import BM25Okapi
            import numpy as np
            
            all_data = collection.get(where={"chunk_type": "child"})
            if not all_data.get("documents"):
                all_data = collection.get()
                use_hierarchical = False
                
            all_docs = all_data.get("documents", [])
            all_ids = all_data.get("ids", [])
            all_metas = all_data.get("metadatas", [])
            
            tokenized_corpus = [doc.lower().split() for doc in all_docs]
            bm25 = BM25Okapi(tokenized_corpus) if tokenized_corpus else None
        except Exception as e:
            logger.warning(f"BM25 initialization failed: {e}")
            bm25 = None
            all_docs = []

        for q in queries:
            q_embedding = model.encode(q).tolist()

            # 1a. Vector Search (Semantic)
            try:
                results = collection.query(
                    query_embeddings=[q_embedding],
                    n_results=_TOP_K,
                    where={"chunk_type": "child"} if use_hierarchical else None,
                    include=["documents", "metadatas", "distances"],
                )
            except Exception:
                use_hierarchical = False
                results = collection.query(
                    query_embeddings=[q_embedding],
                    n_results=_TOP_K,
                    include=["documents", "metadatas", "distances"],
                )

            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]
            ids = results.get("ids", [[]])[0]

            for chunk_id, doc_text, metadata, distance in zip(ids, docs, metas, dists):
                if chunk_id not in seen or distance < seen[chunk_id][2]:
                    seen[chunk_id] = (doc_text, metadata, distance)

            # 1b. BM25 Search (Lexical / Kata Kunci)
            if bm25 and all_docs:
                tokenized_query = q.lower().split()
                bm25_scores = bm25.get_scores(tokenized_query)
                top_n = min(_TOP_K, len(all_docs))
                if top_n > 0:
                    top_indices = np.argsort(bm25_scores)[::-1][:top_n]
                    for idx in top_indices:
                        if bm25_scores[idx] > 0:  # Pastikan ada kecocokan kata
                            b_id = all_ids[idx]
                            b_doc = all_docs[idx]
                            b_meta = all_metas[idx]
                            # BM25 mendapat prioritas tinggi (distance sangat rendah)
                            b_dist = 0.001 
                            if b_id not in seen or b_dist < seen[b_id][2]:
                                seen[b_id] = (b_doc, b_meta, b_dist)

        if not seen:
            logger.info("Tidak ada dokumen relevan ditemukan untuk query: '%s'", query[:80])
            return "", ""

        # ── Tahap 2: Ambil parent chunks dari child yang cocok ──
        if use_hierarchical:
            # Kumpulkan parent_id unik dari child yang paling relevan
            sorted_children = sorted(seen.values(), key=lambda x: x[2])
            top_children = sorted_children[:_TOP_K]

            parent_ids_ordered: list[str] = []
            parent_best_dist: dict[str, float] = {}
            for _, metadata, distance in top_children:
                pid = metadata.get("parent_id")
                if pid and pid not in parent_best_dist:
                    parent_ids_ordered.append(pid)
                    parent_best_dist[pid] = distance
                elif pid and distance < parent_best_dist.get(pid, float('inf')):
                    parent_best_dist[pid] = distance

            # Ambil parent chunks dari ChromaDB
            if parent_ids_ordered:
                parent_results = collection.get(
                    ids=parent_ids_ordered,
                    include=["documents", "metadatas"],
                )

                parent_docs = parent_results.get("documents", [])
                parent_metas = parent_results.get("metadatas", [])
                parent_ret_ids = parent_results.get("ids", [])

                # Bangun data gabungan: (text, metadata, best_distance)
                combined = []
                for pid, doc, meta in zip(parent_ret_ids, parent_docs, parent_metas):
                    dist = parent_best_dist.get(pid, 1.0)
                    combined.append((doc, meta, dist))

                # Limit jumlah parent yang dikirim ke LLM
                combined = combined[:max_chunks]

                # Sort berdasarkan urutan dokumen (page + chunk_index)
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))

                logger.info(
                    "Parent-Child retrieval: %d child cocok -> %d parent unik -> %d dikirim ke LLM",
                    len(seen), len(parent_ids_ordered), len(combined),
                )
            else:
                # Tidak ada parent_id, fallback ke child langsung
                combined = sorted(seen.values(), key=lambda x: x[2])[:max_chunks]
                combined.sort(key=lambda x: (
                    int(x[1].get("page_number", 0)),
                    int(x[1].get("chunk_index", 0)),
                ))
        else:
            # ── Fallback: flat retrieval (data lama) ──
            all_chunks = sorted(seen.values(), key=lambda x: x[2])
            combined = all_chunks[:max_chunks]
            combined.sort(key=lambda x: (
                int(x[1].get("page_number", 0)),
                int(x[1].get("chunk_index", 0)),
            ))
            logger.info(
                "Flat retrieval (fallback): %d chunk dipilih dari %d total",
                len(combined), len(seen),
            )

        # ── Tahap 3: Bangun teks konteks dan sumber ──
        context_parts: list[str] = []
        sources_set: set[str] = set()

        for doc_text, metadata, distance in combined:
            doc_id = metadata.get("document_id", "?")
            page_num = metadata.get("page_number", "?")
            chunk_idx = metadata.get("chunk_index", "?")
            chunk_type = metadata.get("chunk_type", "flat")
            similarity = 1 - distance

            context_parts.append(
                f"[Sumber: Dokumen #{doc_id}, Halaman {page_num}, "
                f"Chunk #{chunk_idx} ({chunk_type}) "
                f"(relevansi: {similarity:.2%})]\n{doc_text}"
            )
            sources_set.add(f"Dokumen #{doc_id} \u2014 Halaman {page_num}")

        context_text = "\n\n---\n\n".join(context_parts)
        sources_text = "\n".join(f"- {s}" for s in sorted(sources_set))

        best_dist = min(v[2] for v in seen.values())
        logger.info(
            "Ditemukan %d konteks unik dari %d query (similarity terbaik: %.2f%%), "
            "dikirim %d chunk ke LLM",
            len(seen),
            len(queries),
            (1 - best_dist) * 100,
            len(combined),
        )

        with open("debug_context.txt", "w", encoding="utf-8") as f:
            f.write(context_text)

        return context_text, sources_text

    except Exception as e:
        logger.error("Gagal melakukan pencarian konteks: %s", str(e))
        return "", ""


import re as _re

def _extract_list_items(block: str, field_name: str) -> list[str]:
    """Ekstrak daftar item dari sebuah field (misal Peralatan/Perlengkapan) dalam teks blok."""
    # Cari baris setelah header field_name sampai baris kosong atau header berikutnya
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
        # Bersihkan markdown bold
        line = _re.sub(r"\*+", "", line).strip()
        if line:
            items.append(line)
    return items


def _build_comparison_hint(context_text: str, query: str) -> str:
    """
    Jika query adalah pertanyaan perbandingan antara dua SOP,
    bangun tabel perbandingan terstruktur dari context_text dan sisipkan di awal.
    Ini membantu LLM lokal yang lemah dalam reasoning perbandingan.
    """
    query_lower = query.lower()
    is_comparison = any(k in query_lower for k in [
        "perbedaan", "berbeda", "beda", "dibanding", "antara", "vs",
        "tidak dibutuhkan", "hanya ada di", "tidak ada di", "khusus",
    ])
    if not is_comparison:
        return context_text

    # Cari blok konteks berdasarkan tag [Konteks: ...]
    blocks = _re.split(r"\n---\n", context_text)
    sop_blocks: dict[str, str] = {}
    for block in blocks:
        match = _re.search(r"\[Konteks:\s*(.+?)\]", block)
        if match:
            sop_name = match.group(1).strip()
            if sop_name not in sop_blocks:
                sop_blocks[sop_name] = block

    if len(sop_blocks) < 2:
        return context_text

    # Buat perbandingan untuk semua field yang relevan
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


def _correct_query_typos(query: str) -> str:
    """
    Menggunakan LLM secara singkat untuk mengekstrak KATA KUNCI UTAMA (keyword)
    dari pertanyaan pengguna, agar hasil pencarian vektor lebih akurat dan tidak
    terdistraksi oleh kata pengantar yang panjang.
    """
    try:
        # Gunakan LLM yang sama dengan generator utama, dengan suhu 0 agar stabil
        llm = ChatOllama(
            model=settings.LLM_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0
        )
        prompt = (
            "Tugas Anda adalah mengekstrak SATU frasa kata kunci paling penting (subject matter) dari pertanyaan pengguna untuk sistem pencarian dokumen.\n"
            "Abaikan semua nama peraturan, nomor undang-undang, surat keputusan, atau kalimat pengantar. JANGAN HANYA mengekstrak kata generik seperti 'Prosedur', 'SOP', atau 'Perbedaan'. Ekstrak topik utamanya.\n\n"
            "Contoh 1:\n"
            "Pertanyaan: Berdasarkan Peraturan Bupati Nomor 12 Tahun 2023, apa saja syarat pengajuan Cuti Tahunan?\n"
            "Kata kunci: syarat pengajuan Cuti Tahunan\n\n"
            "Contoh 2:\n"
            "Pertanyaan: Sebutkan pihak yang terlibat dalam prosedur Pengadaan Barang dan Jasa di dokumen ini!\n"
            "Kata kunci: pihak Pengadaan Barang dan Jasa\n\n"
            "Contoh 3:\n"
            "Pertanyaan: Berdasarkan daftar SOP pada Diktum KEDUA, sebutkan prosedur apa saja yang secara spesifik berkaitan dengan dokumen kinerja dan pelaporan instansi!\n"
            "Kata kunci: dokumen kinerja dan pelaporan instansi\n\n"
            "Tugas Anda (berikan HANYA kata kuncinya, tanpa tanda kutip):\n"
            f"Pertanyaan: {query}\n"
            "Kata kunci:"
        )
        response = llm.invoke([HumanMessage(content=prompt)])
        corrected = response.content.strip()
        
        # Bersihkan kutipan tambahan jika LLM iseng mengembalikannya
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


def generate_response(query: str, session_id: str) -> Generator[str, None, None]:
    """
    Menghasilkan respons RAG secara streaming.

    Langkah-langkah:
    1. Cari konteks relevan di ChromaDB.
    2. Bangun prompt dengan konteks.
    3. Panggil LLM Ollama dan stream hasilnya.
    4. Sertakan referensi sumber di akhir.

    Args:
        query: Pertanyaan dari pengguna.
        session_id: ID sesi chat (untuk logging dan tracking).

    Yields:
        String berisi chunk-chunk respons dari LLM.
    """
    logger.info(
        "Memulai generate response — session=%s, query='%s'",
        session_id,
        query[:80],
    )

    try:
        # Langkah 0: Perbaiki typo
        corrected_query = _correct_query_typos(query)

        # Langkah 1: Ambil konteks dari vector store menggunakan query terkoreksi
        context_text, sources_text = _retrieve_context(corrected_query, original_query=query)

        # Langkah 1b: Sisipkan tabel perbandingan jika query mengandung perbandingan
        context_text = _build_comparison_hint(context_text, query)


        # Langkah 2: Bangun prompt dengan konteks
        if not context_text:
            # Tidak ada konteks, langsung beri tahu pengguna
            yield "Maaf, saya tidak menemukan informasi tersebut di dokumen yang tersedia."
            return

        system_prompt = _SYSTEM_PROMPT.format(
            context=context_text,
            sources=sources_text,
        )

        # Langkah 3: Inisialisasi LLM dan stream respons
        num_ctx = _NUM_CTX_LIST_QUERY if _is_list_query(query) else 8192
        llm = ChatOllama(
            model=settings.LLM_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.0,   # Suhu 0.0 untuk hasil paling deterministik/kaku
            num_ctx=num_ctx,       # Context window eksplisit agar tidak overflow diam-diam
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        # Stream respons dari LLM
        for chunk in llm.stream(messages):
            if chunk.content:
                yield chunk.content

        # Langkah 4: Tambahkan referensi sumber di akhir
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
