"""
Router untuk endpoint pemrosesan dan manajemen dokumen.
Menerima request dari Laravel untuk memproses PDF dan mengecek status dokumen.
"""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from starlette.requests import Request

from app.config import settings
from app.database import get_all_documents, get_document_by_id
from app.schemas import (
    DocumentListItem,
    DocumentListResponse,
    DocumentStatusResponse,
    ProcessDocumentRequest,
    ProcessDocumentResponse,
)
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


# ── GET /api/docs — Daftar semua dokumen ─────────────────────────


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="Daftar semua dokumen",
    description="Mengambil daftar semua dokumen beserta status pemrosesannya.",
)
async def list_documents(
    _token: str = Depends(verify_token),
) -> DocumentListResponse:
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
        logger.error("Gagal mengambil daftar dokumen: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengambil daftar dokumen: {str(e)}",
        ) from e


# ── GET /api/docs/{document_id}/status — Status satu dokumen ─────


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Cek status dokumen",
    description="Mengecek status pemrosesan satu dokumen berdasarkan ID.",
)
async def get_document_status(
    document_id: int,
    _token: str = Depends(verify_token),
) -> DocumentStatusResponse:
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
            "Gagal mengecek status dokumen %d: %s",
            document_id,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengecek status dokumen: {str(e)}",
        ) from e


# ── POST /api/docs/process — Kirim dokumen untuk diproses ────────


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


@router.get(
    "/{document_id}/chunks",
    summary="Ambil daftar chunk dokumen",
    description="Mengambil semua chunk teks yang tersimpan di ChromaDB untuk dokumen tertentu.",
)
async def get_document_chunks_route(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
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


@router.post(
    "/{document_id}/re-embed",
    summary="Re-embed dokumen dari markdown flowchart",
    description="Menghapus vektor lama dan meng-embed ulang dari markdown yang diberikan (hasil konversi flowchart).",
)
async def re_embed_document(
    document_id: int,
    request: Request,
    _token: str = Depends(verify_token),
) -> dict:
    from app.database import update_document_status
    from app.services import embedding_service
    
    try:
        body = await request.json()
        markdown = body.get("markdown", "").strip()
        
        if not markdown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Markdown content cannot be empty."
            )
            
        logger.info("Re-embedding document %d from markdown", document_id)
        
        embedding_service.delete_document_vectors(document_id)
        
        pages = [{"page_number": 1, "text": markdown}]
        chunks = embedding_service.chunk_text(pages)
        embedding_service.embed_and_store(document_id, chunks)
        
        update_document_status(document_id, "completed")
        
        return {
            "success": True,
            "message": f"Dokumen {document_id} berhasil di-embed ulang.",
            "total_chunks": len(chunks)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Gagal melakukan re-embed dokumen %d: %s", document_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal melakukan re-embed: {str(e)}"
        )
