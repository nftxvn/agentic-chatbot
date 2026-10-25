"""Document queries workflows; routers own request validation and authentication."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from app.database import get_all_documents, get_document_by_id
from app.schemas import DocumentListItem, DocumentListResponse, DocumentStatusResponse

logger = logging.getLogger("app.routers.documents")

_ERROR_MESSAGE = "Terjadi kesalahan internal. Rinciannya tercatat di log server."


async def list_documents() -> DocumentListResponse:
    """
    Endpoint untuk mengambil daftar semua dokumen dari database.

    Digunakan oleh Laravel untuk menampilkan tabel daftar dokumen
    di halaman admin dashboard.

    Returns:
        200 OK dengan daftar dokumen dan total count.
    """
    try:
        rows = get_all_documents()

        documents = [
            DocumentListItem(**row) for row in rows
        ]

        logger.info("Mengirim daftar %d dokumen", len(documents))

        return DocumentListResponse(
            total=len(documents),
            documents=documents,
        )

    except Exception as e:
        logger.error("Gagal mengambil daftar dokumen", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
        ) from e


async def get_document_status(document_id: int) -> DocumentStatusResponse:
    """
    Endpoint untuk mengecek status pemrosesan dokumen.

    Digunakan oleh Laravel untuk polling status secara periodik
    (AJAX setiap 10 detik) sampai status berubah dari 'processing'
    ke 'completed' atau 'failed'.

    Returns:
        200 OK dengan detail status dokumen.
        404 Not Found jika dokumen tidak ditemukan.
    """
    try:
        document = get_document_by_id(document_id)

        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Dokumen dengan ID {document_id} tidak ditemukan.",
            )

        logger.info(
            "Status dokumen %d: %s", document_id, document["status"]
        )

        return DocumentStatusResponse(**document)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Gagal mengecek status dokumen %d",
            document_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
        ) from e

