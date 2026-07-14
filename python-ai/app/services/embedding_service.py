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


def chunk_text(pages: list[dict]) -> list[dict]:
    """
    Memecah teks dari setiap halaman menjadi chunk-chunk yang lebih kecil.
    Menggunakan LangChain RecursiveCharacterTextSplitter.

    Args:
        pages: List of dict dari pdf_processor.extract_text():
               [{"page_number": 1, "text": "..."}]

    Returns:
        List of dict berisi chunk dengan metadata:
        [
            {
                "text": "isi chunk",
                "page_number": 1,
                "chunk_index": 0,
            },
            ...
        ]
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_CHUNK_SIZE,
        chunk_overlap=_CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: list[dict] = []
    chunk_index = 0

    for page in pages:
        page_number = page["page_number"]
        text = page["text"]

        # Pecah teks halaman menjadi chunk
        page_chunks = splitter.split_text(text)

        for chunk_text_content in page_chunks:
            chunks.append({
                "text": chunk_text_content,
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
        # ChromaDB memiliki batas batch, proses per 100 chunk
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
            "Berhasil menyimpan %d vektor ke ChromaDB (dokumen %d) ✅",
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
