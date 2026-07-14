"""
Router untuk endpoint pemrosesan dokumen.
Menerima request dari Laravel untuk memproses PDF ke dalam vector store.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.config import settings
from app.schemas import ProcessDocumentRequest, ProcessDocumentResponse
from app.tasks.process_document import process_document_task

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/docs",
    tags=["Documents"],
)


async def verify_token(authorization: str = Header(...)) -> str:
    """
    Dependency untuk memverifikasi token internal dari header Authorization.
    Format yang diharapkan: 'Bearer <token>'

    Raises:
        HTTPException: 401 jika token tidak valid atau tidak ada.
    """
    if not authorization.startswith("Bearer "):
        logger.warning("Format Authorization header tidak valid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format Authorization header tidak valid. Gunakan 'Bearer <token>'.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    if token != settings.INTERNAL_API_TOKEN:
        logger.warning("Token internal tidak valid — akses ditolak")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid. Akses ditolak.",
        )

    return token


@router.post(
    "/process",
    response_model=ProcessDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Kirim dokumen untuk diproses",
    description="Mengirim dokumen PDF ke antrian Celery untuk diekstrak dan di-embed.",
)
async def process_document(
    request: ProcessDocumentRequest,
    _token: str = Depends(verify_token),
) -> ProcessDocumentResponse:
    """
    Endpoint untuk memulai pemrosesan dokumen.

    Menerima request berisi document_id, file_path, dan action,
    lalu mendispatch Celery task untuk pemrosesan asinkron.

    Returns:
        202 Accepted dengan pesan bahwa dokumen sedang diproses.
    """
    try:
        # Dispatch Celery task secara asinkron
        process_document_task.delay(
            document_id=request.document_id,
            file_path=request.file_path,
            action=request.action,
        )

        logger.info(
            "Dokumen %d dikirim ke antrian (action=%s, path=%s)",
            request.document_id,
            request.action,
            request.file_path,
        )

        return ProcessDocumentResponse(
            status="accepted",
            message=f"Dokumen {request.document_id} sedang diproses.",
        )

    except Exception as e:
        logger.error(
            "Gagal mengirim dokumen %d ke antrian: %s",
            request.document_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memproses dokumen: {str(e)}",
        ) from e
