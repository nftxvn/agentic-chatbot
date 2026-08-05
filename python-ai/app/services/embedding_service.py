"""
Service untuk embedding teks dan penyimpanan vektor di ChromaDB.
Menggunakan SentenceTransformer untuk menghasilkan embedding
dan ChromaDB sebagai vector store persisten.
"""

import logging
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

# Variabel global untuk lazy loading (singleton pattern)
_embedding_model: SentenceTransformer | None = None
_chroma_client: chromadb.ClientAPI | None = None
_chroma_collection: Collection | None = None

# Nama koleksi di ChromaDB
_COLLECTION_NAME = "documents"

# Konfigurasi text splitter
_CHUNK_SIZE = 500       # Ukuran chunk dalam karakter (~125 token)
_CHUNK_OVERLAP = 50     # Overlap antar chunk untuk menjaga konteks


def get_embedding_model() -> SentenceTransformer:
    """
    Mendapatkan model SentenceTransformer (lazy loading).
    Model hanya dimuat sekali saat pertama kali dipanggil.

    Returns:
        Instance SentenceTransformer yang sudah dimuat.
    """
    global _embedding_model
    if _embedding_model is None:
        logger.info(
            "Memuat model embedding: %s ...", settings.EMBEDDING_MODEL_NAME
        )
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        logger.info("Model embedding berhasil dimuat ✅")
    return _embedding_model


def get_chroma_collection() -> Collection:
    """
    Mendapatkan koleksi ChromaDB (lazy loading).
    Client dan koleksi hanya dibuat sekali saat pertama kali dipanggil.

    Returns:
        Koleksi ChromaDB 'documents'.
    """
    global _chroma_client, _chroma_collection
    if _chroma_collection is None:
        logger.info(
            "Menginisialisasi ChromaDB di: %s", settings.CHROMA_PERSIST_DIR
        )
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR
        )
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # Gunakan cosine similarity
        )
        logger.info(
            "Koleksi ChromaDB '%s' siap (total: %d dokumen) ✅",
            _COLLECTION_NAME,
            _chroma_collection.count(),
        )
    return _chroma_collection


import re

def chunk_text(pages: list[dict]) -> list[dict]:
    """
    Memecah teks per halaman menjadi chunk.
    Prioritas: split per entri prosedur ("**No. X**") supaya satu entri
    (Uraian, Pelaksana, Waktu, Output) tidak terpotong ke chunk berbeda.
    Fallback ke character splitter untuk entri yang masih terlalu panjang
    atau teks yang bukan format list bernomor.
    """
    # Splitter fallback untuk entri yang masih kepanjangan (>1200 karakter)
    fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=150,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[dict] = []
    chunk_index = 0

    # Pola boundary entri: "**No. 1**", "**No.1**", "No. 1", dll
    entry_pattern = re.compile(r"(?=\*\*No\.?\s*\d+\*\*)")

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        # Coba split berdasarkan entri bernomor dulu
        parts = entry_pattern.split(text)
        parts = [p.strip() for p in parts if p.strip()]

        # Kalau tidak ketemu pola "No. X" sama sekali, treat sebagai 1 blok teks biasa
        if len(parts) <= 1:
            parts = [text]

        for part in parts:
            if len(part) <= 1200:
                # Entri utuh muat dalam satu chunk — JANGAN dipecah lagi
                # Tambahkan prefix halaman ke teks chunk agar LLM punya konteks inline
                text_with_meta = f"[Halaman {page_number}]\n{part}"
                chunks.append({
                    "text": text_with_meta,
                    "page_number": page_number,
                    "chunk_index": chunk_index,
                })
                chunk_index += 1
            else:
                # Entri kepanjangan, pecah dengan overlap besar
                sub_chunks = fallback_splitter.split_text(part)
                for sc in sub_chunks:
                    text_with_meta = f"[Halaman {page_number}]\n{sc}"
                    chunks.append({
                        "text": text_with_meta,
                        "page_number": page_number,
                        "chunk_index": chunk_index,
                    })
                    chunk_index += 1

    logger.info(
        "Teks dipecah menjadi %d chunk dari %d halaman",
        len(chunks),
        len(pages),
    )
    return chunks


# ── Konfigurasi Parent-Child Chunking ─────────────────────────────
_PARENT_CHUNK_SIZE = 1500
_PARENT_CHUNK_OVERLAP = 200
_CHILD_CHUNK_SIZE = 300
_CHILD_CHUNK_OVERLAP = 50


def chunk_text_hierarchical(pages: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Memecah teks menjadi parent chunks (besar) dan child chunks (kecil).

    - Parent chunks (~1500 char): Dikirim ke LLM sebagai konteks yang lengkap.
    - Child chunks (~300 char): Di-embed untuk pencarian semantik yang presisi.
    - Setiap child memiliki 'parent_index' yang menunjuk ke parent-nya.

    Untuk dokumen SOP yang memiliki format "**No. X**", setiap entri prosedur
    dijadikan satu parent chunk utuh agar tidak terpotong.

    Returns:
        Tuple of (parent_chunks, child_chunks).
    """
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=_PARENT_CHUNK_SIZE,
        chunk_overlap=_PARENT_CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CHILD_CHUNK_SIZE,
        chunk_overlap=_CHILD_CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    parent_chunks: list[dict] = []
    child_chunks: list[dict] = []
    parent_index = 0
    child_index = 0

    # Pola boundary entri SOP: "**No. 1**", "**No.1**", "**No 1**", dll
    entry_pattern = re.compile(r"(?=\*\*No\.?\s*\d+\*\*)")

    # ── Deteksi daftar besar secara GENERIK (bukan cuma format dokumen ini) ──
    # Mengenali: nomor "1." / "1)", huruf "a." / "a)", romawi "i." / "I.",
    # atau bullet "- • *" — supaya berlaku untuk berbagai jenis dokumen yang
    # nanti diupload lewat platform, bukan cuma SOP Diktum KEDUA.
    _list_item_boundary = re.compile(
        r"(?=^\s*(?:\d{1,3}[.\)]|[a-zA-Z]{1,3}[.\)]|[ivxlcdmIVXLCDM]{1,7}[.\)]|[-•*])\s+)",
        re.MULTILINE,
    )
    _LIST_ITEM_THRESHOLD = 8      # min. item beruntun agar dianggap "daftar besar"
    _LIST_BLOCK_HARD_CAP = 6000   # di atas ini tetap dipecah, demi keamanan num_ctx LLM

    def _split_list_preserving_items(list_text: str, max_size: int) -> list[str]:
        """Pecah daftar per BATAS ITEM (bukan per karakter). Item individual
        tidak pernah terpotong di tengah, walau daftar keseluruhan harus
        dipecah karena melebihi _LIST_BLOCK_HARD_CAP."""
        raw_items = _list_item_boundary.split(list_text)
        raw_items = [i.strip() for i in raw_items if i.strip()]
        out, current = [], ""
        for item in raw_items:
            if current and len(current) + len(item) + 1 > max_size:
                out.append(current)
                current = item
            else:
                current = f"{current}\n{item}" if current else item
        if current:
            out.append(current)
        return out

    # Pola item daftar berhuruf, mis. Diktum KEDUA: "a.", "b.", ... "aa.", "vvv."
    # Dipakai untuk MENDETEKSI (bukan memecah) halaman yang berisi daftar
    # enumerasi panjang, supaya daftar tsb TIDAK dipecah di tengah oleh
    # parent_splitter berbasis jumlah karakter.
    _letter_list_item = re.compile(r"^\s*[a-z]{1,3}\.\s", re.MULTILINE)
    _LIST_ITEM_THRESHOLD = 10  # min. jumlah item huruf berurutan agar dianggap "daftar besar"

    # Tracker Nama SOP — mendeteksi berbagai variasi format:
    # - NAMA SOP: ... (kapital semua, dari OCR plain text)
    # - - **Nama SOP**: ... (format markdown bold dari OCR lain)
    # Menggunakan IGNORECASE agar tidak terpengaruh kapitalisasi
    sop_name_pattern = re.compile(
        r"(?:(?:-\s*\*\*)?NAMA\s+SOP(?:\*\*)?\s*:\s*)(.+)",
        re.IGNORECASE,
    )
    current_sop_name: str | None = None

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        # Cek apakah ada Nama SOP di halaman ini — update jika ditemukan
        match = sop_name_pattern.search(text)
        if match:
            current_sop_name = match.group(1).strip()
            # Bersihkan sisa markdown bold jika masih ada (mis: "Renja **")
            current_sop_name = re.sub(r"\*+", "", current_sop_name).strip()
            logger.info("SOP tracker updated: '%s' (halaman %d)", current_sop_name, page_number)

        # Deteksi dulu: apakah halaman ini berisi daftar enumerasi panjang,
        # format apa pun (nomor, huruf, romawi, atau bullet)?
        list_item_count = len(_list_item_boundary.findall(text))
        is_large_list = list_item_count >= _LIST_ITEM_THRESHOLD

        if is_large_list:
            if len(text) <= _LIST_BLOCK_HARD_CAP:
                # Aman disimpan utuh sebagai SATU parent chunk — semua item ikut.
                parent_texts = [text]
                logger.info(
                    "Halaman %d terdeteksi sebagai daftar besar (%d item) "
                    "— disimpan utuh tanpa dipecah",
                    page_number, list_item_count,
                )
            else:
                # Daftar terlalu panjang untuk 1 chunk — pecah di BATAS ITEM,
                # bukan di tengah karakter, supaya tidak ada item yang terpotong.
                parent_texts = _split_list_preserving_items(text, _PARENT_CHUNK_SIZE)
                logger.info(
                    "Halaman %d: daftar besar (%d item, %d karakter) melebihi "
                    "hard cap %d — dipecah jadi %d chunk di batas item",
                    page_number, list_item_count, len(text),
                    _LIST_BLOCK_HARD_CAP, len(parent_texts),
                )
        else:
            # Coba split berdasarkan entri prosedur bernomor dulu
            parts = entry_pattern.split(text)
            parts = [p.strip() for p in parts if p.strip()]

            if len(parts) <= 1:
                # Tidak ada pola "No. X", gunakan splitter biasa untuk parent
                parent_texts = parent_splitter.split_text(text)
            else:
                # Gunakan entri-entri sebagai parent chunks
                parent_texts = []
                for part in parts:
                    if len(part) <= _PARENT_CHUNK_SIZE:
                        parent_texts.append(part)
                    else:
                        parent_texts.extend(parent_splitter.split_text(part))

        for parent_text in parent_texts:
            prefix = f"[Halaman {page_number}]"
            if current_sop_name:
                prefix += f"\n[Konteks: SOP {current_sop_name}]"

            parent_text_with_meta = f"{prefix}\n{parent_text}"
            parent_chunks.append({
                "text": parent_text_with_meta,
                "page_number": page_number,
                "chunk_index": parent_index,
            })

            # Pecah parent menjadi child chunks yang lebih kecil
            child_texts = child_splitter.split_text(parent_text)
            for ct in child_texts:
                child_text_with_meta = f"{prefix}\n{ct}"
                child_chunks.append({
                    "text": child_text_with_meta,
                    "page_number": page_number,
                    "chunk_index": child_index,
                    "parent_index": parent_index,
                })
                child_index += 1

            parent_index += 1

    logger.info(
        "Hierarchical chunking: %d parent, %d child dari %d halaman",
        len(parent_chunks), len(child_chunks), len(pages),
    )
    return parent_chunks, child_chunks


def delete_document_vectors(document_id: int) -> int:
    """
    Menghapus semua vektor yang terkait dengan document_id dari ChromaDB.

    Args:
        document_id: ID dokumen yang vektornya akan dihapus.

    Returns:
        Jumlah vektor yang dihapus.
    """
    collection = get_chroma_collection()

    try:
        # Cari semua ID yang terkait dengan document_id
        results = collection.get(
            where={"document_id": document_id},
        )

        existing_ids = results["ids"]
        count = len(existing_ids)

        if count > 0:
            collection.delete(ids=existing_ids)
            logger.info(
                "Berhasil menghapus %d vektor untuk dokumen %d",
                count,
                document_id,
            )
        else:
            logger.info("Tidak ada vektor yang ditemukan untuk dokumen %d", document_id)

        return count

    except Exception as e:
        logger.error(
            "Gagal menghapus vektor untuk dokumen %d: %s",
            document_id,
            str(e),
        )
        raise


def embed_and_store(document_id: int, chunks: list[dict]) -> int:
    """
    Menghasilkan embedding untuk setiap chunk dan menyimpannya di ChromaDB.
    (Fungsi flat/lama — dipertahankan untuk backward compatibility dengan Celery task.)

    Args:
        document_id: ID dokumen sumber.
        chunks: List of dict dari chunk_text():
                [{"text": "...", "page_number": 1, "chunk_index": 0}]

    Returns:
        Jumlah vektor yang berhasil disimpan.
    """
    if not chunks:
        logger.warning("Tidak ada chunk untuk di-embed (dokumen %d)", document_id)
        return 0

    model = get_embedding_model()
    collection = get_chroma_collection()

    try:
        # Siapkan data untuk batch insert
        texts: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for chunk in chunks:
            chunk_id = f"doc_{document_id}_chunk_{chunk['chunk_index']}"
            ids.append(chunk_id)
            texts.append(chunk["text"])
            metadatas.append({
                "document_id": document_id,
                "page_number": chunk["page_number"],
                "chunk_index": chunk["chunk_index"],
            })

        # Generate embedding untuk semua teks sekaligus (batch processing)
        logger.info(
            "Menghasilkan embedding untuk %d chunk (dokumen %d)...",
            len(texts),
            document_id,
        )
        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        # Simpan ke ChromaDB (batch upsert untuk menghindari duplikasi)
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            batch_end = min(i + batch_size, len(ids))
            collection.upsert(
                ids=ids[i:batch_end],
                embeddings=embeddings[i:batch_end],
                documents=texts[i:batch_end],
                metadatas=metadatas[i:batch_end],
            )

        logger.info(
            "Berhasil menyimpan %d vektor ke ChromaDB (dokumen %d)",
            len(ids),
            document_id,
        )

        return len(ids)

    except Exception as e:
        logger.error(
            "Gagal meng-embed dan menyimpan chunk (dokumen %d): %s",
            document_id,
            str(e),
        )
        raise


def embed_and_store_hierarchical(
    document_id: int,
    parent_chunks: list[dict],
    child_chunks: list[dict],
) -> int:
    """
    Menyimpan parent dan child chunks ke ChromaDB.

    - Child chunks: di-embed untuk pencarian semantik (metadata: chunk_type="child")
    - Parent chunks: di-embed dan disimpan untuk konteks LLM (metadata: chunk_type="parent")
    - Setiap child memiliki metadata 'parent_id' yang menunjuk ke parent-nya.

    Args:
        document_id: ID dokumen sumber.
        parent_chunks: List parent chunks dari chunk_text_hierarchical().
        child_chunks: List child chunks dari chunk_text_hierarchical().

    Returns:
        Jumlah total vektor yang berhasil disimpan (parent + child).
    """
    if not child_chunks:
        logger.warning("Tidak ada chunk untuk di-embed (dokumen %d)", document_id)
        return 0

    model = get_embedding_model()
    collection = get_chroma_collection()

    try:
        batch_size = 100

        # ── Simpan Parent Chunks ──
        parent_texts: list[str] = []
        parent_ids: list[str] = []
        parent_metadatas: list[dict[str, Any]] = []

        for c in parent_chunks:
            pid = f"doc_{document_id}_parent_{c['chunk_index']}"
            parent_ids.append(pid)
            parent_texts.append(c["text"])
            parent_metadatas.append({
                "document_id": document_id,
                "page_number": c["page_number"],
                "chunk_index": c["chunk_index"],
                "chunk_type": "parent",
            })

        logger.info(
            "Menghasilkan embedding untuk %d parent chunks (dokumen %d)...",
            len(parent_texts), document_id,
        )
        parent_embeddings = model.encode(parent_texts, show_progress_bar=False).tolist()

        for i in range(0, len(parent_ids), batch_size):
            end = min(i + batch_size, len(parent_ids))
            collection.upsert(
                ids=parent_ids[i:end],
                embeddings=parent_embeddings[i:end],
                documents=parent_texts[i:end],
                metadatas=parent_metadatas[i:end],
            )

        logger.info("Disimpan %d parent chunks (dokumen %d)", len(parent_ids), document_id)

        # ── Simpan Child Chunks ──
        child_texts: list[str] = []
        child_ids: list[str] = []
        child_metadatas: list[dict[str, Any]] = []

        for c in child_chunks:
            cid = f"doc_{document_id}_child_{c['chunk_index']}"
            child_ids.append(cid)
            child_texts.append(c["text"])
            child_metadatas.append({
                "document_id": document_id,
                "page_number": c["page_number"],
                "chunk_index": c["chunk_index"],
                "chunk_type": "child",
                "parent_id": f"doc_{document_id}_parent_{c['parent_index']}",
            })

        logger.info(
            "Menghasilkan embedding untuk %d child chunks (dokumen %d)...",
            len(child_texts), document_id,
        )
        child_embeddings = model.encode(child_texts, show_progress_bar=False).tolist()

        for i in range(0, len(child_ids), batch_size):
            end = min(i + batch_size, len(child_ids))
            collection.upsert(
                ids=child_ids[i:end],
                embeddings=child_embeddings[i:end],
                documents=child_texts[i:end],
                metadatas=child_metadatas[i:end],
            )

        logger.info("Disimpan %d child chunks (dokumen %d)", len(child_ids), document_id)

        total = len(parent_ids) + len(child_ids)
        logger.info(
            "Total %d vektor hierarchical disimpan ke ChromaDB (dokumen %d)",
            total, document_id,
        )
        return total

    except Exception as e:
        logger.error(
            "Gagal menyimpan hierarchical chunks (dokumen %d): %s",
            document_id, str(e),
        )
        raise