"""Document lifecycle workflows; routers own request validation and authentication."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from app.services.document_operations import DocumentNotFound, cancel_operation
from app.services.vector_cleanup import drain_cleanups, request_document_cleanup

logger = logging.getLogger("app.routers.documents")


async def cancel_document_processing(document_id: int) -> dict:
    """Fence one document's work; running model calls stop at their next boundary.

    The database token invalidates queued/retrying/in-flight work without
    purging other documents or unloading a model they may share. Cleanup only
    targets partial vectors tagged with the cancelled operation's token.
    """
    try:
        previous_token = cancel_operation(document_id)
    except DocumentNotFound as error:
        raise HTTPException(status_code=404, detail=f"Dokumen {document_id} tidak ditemukan") from error

    if previous_token:
        try:
            drain_cleanups(document_id=document_id, due_only=False)
        except Exception:
            # The durable fence remains valid even if the vector server is down.
            logger.warning("Cleanup vektor operasi yang dibatalkan gagal untuk dokumen %d", document_id, exc_info=True)

    logger.info("Dokumen %d: pembatalan kooperatif diminta", document_id)
    return {
        "document_id": document_id,
        "status": "cancelled",
        "message": "Permintaan pembatalan dokumen diterima. Operasi aktif berhenti pada batas aman berikutnya.",
    }


async def delete_document_route(document_id: int) -> dict:
    from app.services.ekstraksi_bertahap import PenyimpananMySQL
    try:
        request_document_cleanup(document_id)
        outcome = drain_cleanups(document_id=document_id, due_only=False)
        if outcome["failed"]:
            raise RuntimeError("Cleanup vektor tersimpan untuk dicoba ulang.")
        deleted_count = outcome["deleted_vectors"]
        try:
            PenyimpananMySQL().reset_ekstraksi(document_id, only_cancelled=True)
        except Exception as ex:
            logger.warning("Gagal membersihkan tabel ekstraksi MySQL untuk dokumen %d: %s", document_id, ex)

        logger.info("Dokumen %d: %d vektor berhasil dihapus dari ChromaDB", document_id, deleted_count)
        return {
            "success": True,
            "document_id": document_id,
            "deleted_vectors": deleted_count,
            "message": f"Berhasil menghapus {deleted_count} vektor untuk dokumen {document_id}.",
        }
    except Exception as e:
        logger.error("Gagal menghapus vektor dokumen %d: %s", document_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menghapus vektor dokumen dari ChromaDB: {str(e)}",
        )


async def get_all_vector_counts_route() -> dict:
    from app.services.embedding_service import get_chroma_collection
    try:
        collection = get_chroma_collection()
        all_meta = collection.get(include=["metadatas"]).get("metadatas", [])
        counts: dict[int, int] = {}
        for m in all_meta:
            if m and "document_id" in m:
                doc_id = int(m["document_id"])
                counts[doc_id] = counts.get(doc_id, 0) + 1
        return {
            "total_vectors": len(all_meta),
            "counts": counts,
        }
    except Exception as e:
        logger.error("Gagal menghitung vektor per dokumen di ChromaDB: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menghitung vektor ChromaDB: {str(e)}"
        )


async def get_document_chunks_route(document_id: int) -> dict:
    from app.services.embedding_service import get_document_chunks
    try:
        chunks = get_document_chunks(document_id)
        return {
            "document_id": document_id,
            "total_chunks": len(chunks),
            "chunks": chunks
        }
    except Exception as e:
        logger.error("Gagal mengambil chunk dokumen %d: %s", document_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil chunk: {str(e)}"
        )

