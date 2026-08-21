"""
Router untuk endpoint pemrosesan dan manajemen dokumen.
Menerima request dari Laravel untuk memproses PDF dan mengecek status dokumen.
"""

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
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
from app.services import pdf_processor
from app.tasks.process_document import process_document_task

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/docs",
    tags=["Documents"],
)

# Pesan umum untuk kesalahan tak terduga. Rinciannya ditahan di log server:
# pesan exception mentah dari SQLAlchemy/Celery kerap memuat host, nama
# pengguna basis data, atau path berkas.
_ERROR_MESSAGE = (
    "Terjadi kesalahan internal. Rinciannya tercatat di log server."
)


async def verify_token(authorization: str | None = Header(default=None)) -> str:
    """
    Dependency untuk memverifikasi token internal dari header Authorization.
    Format yang diharapkan: 'Bearer <token>'

    `default=None`, bukan `Header(...)`: dengan header berstatus wajib, FastAPI
    menolak permintaan tanpa Authorization lewat validasi bawaannya dan
    membalas 422 sebelum fungsi ini sempat berjalan. Permintaan tanpa
    kredensial harus dijawab 401 — itu yang dicek pemanggil seperti Laravel.

    Raises:
        HTTPException: 401 jika token tidak ada, formatnya salah, atau tidak cocok.
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Format Authorization header tidak valid")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format Authorization header tidak valid. Gunakan 'Bearer <token>'.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    # compare_digest, bukan '==': lama pembandingannya tidak bergantung pada
    # berapa karakter awal yang cocok, sehingga token tidak bisa ditebak
    # karakter demi karakter lewat pengukuran waktu respons.
    if not secrets.compare_digest(token, settings.INTERNAL_API_TOKEN):
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
        logger.error("Gagal mengambil daftar dokumen", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
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
            "Gagal mengecek status dokumen %d",
            document_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
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
            "Gagal mengirim dokumen %d ke antrian",
            request.document_id,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
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


# ── GET /api/docs/{id}/halaman/{n}/citra — Citra satu halaman ────


@router.get(
    "/{document_id}/halaman/{page_number}/citra",
    summary="Citra satu halaman dokumen",
    description=(
        "Merender satu halaman PDF jadi JPEG. Dipakai editor koreksi agar "
        "korektor bisa membandingkan hasil OCR dengan halaman aslinya."
    ),
    responses={
        200: {"content": {"image/jpeg": {}}, "description": "Citra halaman"},
        400: {"description": "Nilai zoom tidak diizinkan"},
        404: {"description": "Dokumen, berkas, atau halaman tidak ditemukan"},
    },
    response_class=Response,
)
async def citra_halaman(
    document_id: int,
    page_number: int,
    zoom: float = Query(
        default=pdf_processor.ZOOM_OCR,
        description=(
            "Perbesaran render. Bawaannya sama dengan yang dibaca model OCR, "
            "sehingga apa yang terlihat korektor sama dengan apa yang terbaca mesin."
        ),
    ),
    _token: str = Depends(verify_token),
) -> Response:
    """
    Render dikerjakan saat diminta, bukan disiapkan lebih dulu.

    Satu halaman butuh 20-120 milidetik. Menyiapkan ratusan gambar di muka
    berarti ratusan berkas yang harus disimpan, dibersihkan, dan dijaga agar
    tidak basi — demi menghemat sepersepuluh detik.

    Sebagai gantinya, hasilnya boleh di-cache selamanya oleh browser: citra
    halaman tidak pernah berubah selama PDF-nya tidak diganti.
    """
    dokumen = get_document_by_id(document_id)
    if dokumen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak ditemukan",
        )

    berkas = dokumen.get("file_path")
    if not berkas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak punya berkas",
        )

    try:
        data, lebar, tinggi = pdf_processor.render_halaman(berkas, page_number, zoom)
    except ValueError as e:
        # Zoom terlarang adalah salah pemanggil; halaman di luar jangkauan
        # adalah sumber daya yang tidak ada. Dua hal berbeda, dua kode berbeda.
        kode = (
            status.HTTP_400_BAD_REQUEST
            if "zoom" in str(e).lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=kode, detail=str(e)) from e
    except FileNotFoundError as e:
        logger.error("Berkas dokumen %d hilang: %s", document_id, berkas)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas dokumen tidak ditemukan di server",
        ) from e
    except Exception as e:
        logger.exception("Gagal merender halaman %d dokumen %d", page_number, document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
        ) from e

    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{document_id}-{page_number}-{zoom}"',
            # Dipakai editor untuk menyiapkan ukuran panel tanpa menunggu
            # gambarnya selesai diurai browser.
            "X-Lebar-Piksel": str(lebar),
            "X-Tinggi-Piksel": str(tinggi),
        },
    )


# ── GET /api/docs/{id}/halaman/ukuran — Ukuran semua halaman ─────


@router.get(
    "/{document_id}/halaman/ukuran",
    summary="Ukuran dan orientasi semua halaman",
    description=(
        "Lebar, tinggi, dan orientasi tiap halaman pada perbesaran bawaan — "
        "tanpa merender apa pun. Dipakai editor untuk menyiapkan ukuran panel."
    ),
)
async def ukuran_semua_halaman(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    """
    Tanpa ini panel editor berkedip menyesuaikan ukuran tiap kali pindah
    halaman — dan pada dokumen pindaian kedipannya nyata, karena orientasi
    halaman kerap bercampur di satu berkas yang sama.
    """
    dokumen = get_document_by_id(document_id)
    if dokumen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak ditemukan",
        )

    berkas = dokumen.get("file_path")
    if not berkas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak punya berkas",
        )

    try:
        halaman = pdf_processor.ukuran_halaman(berkas)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Berkas dokumen tidak ditemukan di server",
        ) from e
    except Exception as e:
        logger.exception("Gagal membaca ukuran halaman dokumen %d", document_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
        ) from e

    return {
        "document_id": document_id,
        "halaman_total": len(halaman),
        "zoom_bawaan": pdf_processor.ZOOM_OCR,
        "zoom_diizinkan": list(pdf_processor.ZOOM_DIIZINKAN),
        "halaman": halaman,
    }
