"""Koleksi ChromaDB tunggal, pembacaan/penghapusan chunk, dan upsert vektor."""

import logging
import os
from contextlib import nullcontext
from typing import Any, Callable

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings as ChromaSettings

from app.config import settings
from app.services.document_operations import (
    DocumentOperationCancelled,
    OperationGuard,
    lock_document,
)
from app.services.embeddings.models import encode_texts
from app.services.embeddings.corpus import _invalidate_search_index

logger = logging.getLogger("app.services.embedding_service")

_chroma_collection: Collection | None = None

_COLLECTION_NAME = "documents"

def get_chroma_collection() -> Collection:
    """
    Mendapatkan koleksi ChromaDB (lazy loading).
    Client dan koleksi hanya dibuat sekali saat pertama kali dipanggil.
    CHROMA_HTTP_HOST mengaktifkan server bersama untuk API/worker; host kosong
    mempertahankan penyimpanan embedded. Konfigurasi HTTP gagal secara eksplisit
    dan tidak beralih ke direktori lokal. Penanda versi korpus tetap mengikuti
    CHROMA_PERSIST_DIR dan perlu dibagi oleh proses yang berbagi korpus.

    Returns:
        Koleksi ChromaDB 'documents'.
    """
    global _chroma_collection
    if _chroma_collection is None:
        # Matikan telemetri anonim ChromaDB: tidak ada data pemakaian yang
        # dikirim keluar dari mesin ini. Efeknya, chromadb menyetel
        # posthog.disabled = True (chromadb/telemetry/product/posthog.py:17).
        #
        # CATATAN — ini TIDAK menghilangkan baris error di log. chromadb 0.5.5
        # memanggil posthog.capture() dengan 3 argumen posisional, sedangkan
        # posthog 7.x hanya menerima 1, sehingga TypeError terjadi saat
        # pemanggilan — sebelum pengecekan `disabled` di dalam fungsi sempat
        # dijalankan. Kebisingan "Failed to send telemetry event ..." karena
        # itu diredam di level logging (lihat app/main.py), bukan di sini.
        # HTTP mode gives API and worker one server-owned persistence path.
        # An explicit server failure must not create a second local corpus.
        http_host = os.getenv("CHROMA_HTTP_HOST", "").strip()
        if http_host:
            logger.info("Menginisialisasi koneksi HTTP ChromaDB")
            _chroma_client = chromadb.HttpClient(
                host=http_host,
                port=int(os.getenv("CHROMA_HTTP_PORT", "8000")),
                ssl=os.getenv("CHROMA_HTTP_SSL", "false").strip().lower()
                in {"1", "true", "yes", "on"},
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        else:
            logger.info(
                "Menginisialisasi ChromaDB di: %s", settings.CHROMA_PERSIST_DIR
            )
            _chroma_client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        _chroma_collection = _chroma_client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},  # Gunakan cosine similarity
        )
        logger.info(
            "Koleksi ChromaDB '%s' siap (total: %d chunk vektor)",
            _COLLECTION_NAME,
            _chroma_collection.count(),
        )
    return _chroma_collection


def _checkpoint(document_id: int, operation_guard: OperationGuard | None) -> None:
    if operation_guard is not None:
        if operation_guard.document_id != document_id:
            raise ValueError("Operation guard belongs to a different document")
        operation_guard.checkpoint()


def _write(operation_guard: OperationGuard | None):
    return operation_guard.write() if operation_guard is not None else nullcontext()


def delete_document_vectors(
    document_id: int, *, operation_guard: OperationGuard | None = None,
) -> int:
    """
    Menghapus semua vektor yang terkait dengan document_id dari ChromaDB.

    Args:
        document_id: ID dokumen yang vektornya akan dihapus.
        operation_guard: Opsional; otorisasi generasi dicek ulang di bawah lock
            dokumen sebelum mutasi Chroma dijalankan.

    Returns:
        Jumlah vektor yang dihapus.
    """
    _checkpoint(document_id, operation_guard)
    collection = get_chroma_collection()

    try:
        # Hitung terlebih dahulu untuk pelaporan
        results = collection.get(
            where={"document_id": document_id},
        )
        count = len(results.get("ids", []))

        if count > 0:
            # Hapus secara native menggunakan metadata where filter agar aman dari limit ID
            with _write(operation_guard):
                collection.delete(where={"document_id": document_id})
            _invalidate_search_index()
            logger.info(
                "Berhasil menghapus %d vektor untuk dokumen %d",
                count,
                document_id,
            )
        else:
            logger.info("Tidak ada vektor yang ditemukan untuk dokumen %d", document_id)

        _checkpoint(document_id, operation_guard)
        return count

    except DocumentOperationCancelled:
        raise
    except Exception as e:
        logger.error(
            "Gagal menghapus vektor untuk dokumen %d: %s",
            document_id,
            str(e),
        )
        raise


def delete_cleanup_vectors(document_id: int, operation_token: str = "") -> int:
    """Outbox adapter; caller holds document/outbox locks until acknowledgement.

    A blank token targets the document; that pending outbox job blocks starts.
    Invalidate even on an empty retry, since an earlier remote deletion may
    have succeeded before cache invalidation or the SQL commit failed.
    """
    collection = get_chroma_collection()
    where = {"document_id": document_id}
    if operation_token:
        where = {"$and": [where, {"operation_token": operation_token}]}
    count = len(collection.get(where=where).get("ids", []))
    if count:
        collection.delete(where=where)
    _invalidate_search_index()
    return count


def delete_operation_vectors(document_id: int, operation_token: str) -> int:
    """Delete only a cancelled generation, preserving vectors of later runs.

    Use the native predicate for deletion as well as counting: deleting the IDs
    returned by an earlier read could remove rows overwritten by a newer run.
    """
    if not operation_token:
        raise ValueError("An operation token is required for generation cleanup")
    collection = get_chroma_collection()
    where = {"$and": [
        {"document_id": document_id},
        {"operation_token": operation_token},
    ]}
    # Cleanup uses the same document lock as start/cancel and guarded upserts.
    # This keeps a newer upsert from reusing an ID while the delete is pending.
    with lock_document(document_id):
        count = len(collection.get(where=where).get("ids", []))
        if count:
            collection.delete(where=where)
    if count:
        _invalidate_search_index()
    return count



def get_document_chunks(document_id: int) -> list[dict]:
    """
    Mengambil semua chunk teks yang tersimpan di ChromaDB untuk dokumen tertentu.
    
    Args:
        document_id: ID dokumen sumber.
        
    Returns:
        List of dict berisi chunk data.
    """
    collection = get_chroma_collection()
    try:
        results = collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"]
        )
        
        chunks = []
        if results and results.get("ids"):
            for i in range(len(results["ids"])):
                chunks.append({
                    "id": results["ids"][i],
                    "text": results["documents"][i],
                    "metadata": results["metadatas"][i]
                })
                
        # Urutkan berdasarkan chunk_type (parent dahulu), lalu nomor halaman dan chunk_index
        chunks.sort(key=lambda x: (
            0 if x.get("metadata", {}).get("chunk_type") == "parent" else 1,
            int(x.get("metadata", {}).get("page_number", 0)),
            int(x.get("metadata", {}).get("chunk_index", 0)),
        ))
        return chunks
    except Exception as e:
        logger.error("Gagal mengambil chunk dari ChromaDB (dokumen %d): %s", document_id, str(e))
        return []


def embed_and_store_hierarchical(
    document_id: int,
    parent_chunks: list[dict],
    child_chunks: list[dict],
    progress_callback: Callable[[int, str], None] | None = None,
    *,
    operation_guard: OperationGuard | None = None,
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
        progress_callback: Callback opsional (persen: int, pesan: str) untuk progres live.
        operation_guard: Opsional; inferensi di luar lock, setiap upsert di dalam
            lock dokumen, dan callback progres setelah lock dilepas.

    Returns:
        Jumlah total vektor yang berhasil disimpan (parent + child).
    """
    _checkpoint(document_id, operation_guard)
    if not child_chunks:
        logger.warning("Tidak ada chunk untuk di-embed (dokumen %d)", document_id)
        return 0

    if progress_callback:
        _checkpoint(document_id, operation_guard)
        progress_callback(35, "Menyiapkan mesin embedding vektor...")

    collection = get_chroma_collection()

    try:
        batch_size = 50

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
            if operation_guard is not None:
                parent_metadatas[-1]["operation_token"] = operation_guard.token

        if progress_callback:
            _checkpoint(document_id, operation_guard)
            progress_callback(45, f"Menghitung embedding {len(parent_texts)} potongan induk...")

        logger.info(
            "Menghasilkan embedding untuk %d parent chunks (dokumen %d)...",
            len(parent_texts), document_id,
        )
        _checkpoint(document_id, operation_guard)
        parent_embeddings = encode_texts(parent_texts)
        _checkpoint(document_id, operation_guard)

        for i in range(0, len(parent_ids), batch_size):
            _checkpoint(document_id, operation_guard)
            end = min(i + batch_size, len(parent_ids))
            with _write(operation_guard):
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
            if operation_guard is not None:
                child_metadatas[-1]["operation_token"] = operation_guard.token

        total_children = len(child_texts)
        child_embeddings: list[list[float]] = []

        for i in range(0, total_children, batch_size):
            _checkpoint(document_id, operation_guard)
            end = min(i + batch_size, total_children)
            batch_texts = child_texts[i:end]
            if progress_callback:
                pct = 55 + int((i / max(1, total_children)) * 35)
                progress_callback(pct, f"Menghitung embedding potongan anak ({end}/{total_children})...")
            _checkpoint(document_id, operation_guard)
            batch_emb = encode_texts(batch_texts)
            _checkpoint(document_id, operation_guard)
            with _write(operation_guard):
                collection.upsert(
                    ids=child_ids[i:end],
                    embeddings=batch_emb,
                    documents=batch_texts,
                    metadatas=child_metadatas[i:end],
                )

        if progress_callback:
            _checkpoint(document_id, operation_guard)
            progress_callback(95, "Memperbarui indeks pencarian ChromaDB...")

        logger.info("Disimpan %d child chunks (dokumen %d)", len(child_ids), document_id)

        _checkpoint(document_id, operation_guard)
        _invalidate_search_index()

        total = len(parent_ids) + len(child_ids)
        if progress_callback:
            _checkpoint(document_id, operation_guard)
            progress_callback(100, f"Selesai! {total} vektor berhasil disimpan.")

        logger.info(
            "Total %d vektor hierarchical disimpan ke ChromaDB (dokumen %d)",
            total, document_id,
        )
        _checkpoint(document_id, operation_guard)
        return total

    except DocumentOperationCancelled:
        raise
    except Exception as e:
        logger.error(
            "Gagal menyimpan hierarchical chunks (dokumen %d): %s",
            document_id, str(e),
        )
        raise
