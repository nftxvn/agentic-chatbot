"""
Router untuk endpoint pemrosesan dan manajemen dokumen.
Menerima request dari Laravel untuk memproses PDF dan mengecek status dokumen.
"""

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from app.config import settings
from app.database import get_all_documents, get_document_by_id
from app.schemas import (
    DocumentListItem,
    DocumentListResponse,
    DocumentStatusResponse,
)
from app.services import pdf_processor

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





@router.post(
    "/{document_id}/cancel",
    summary="Batalkan pemrosesan dokumen secara instan",
    description="Membatalkan tugas ekstraksi aktif, membersihkan antrean, dan membebaskan RAM/VRAM model AI.",
)
async def cancel_document_processing(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    import httpx
    from app.tasks.process_document import celery_app

    # 1. Update status di database
    update_document_status(
        document_id,
        status="failed",
        error_message="Pemrosesan dibatalkan oleh pengguna.",
    )

    # 2. Bersihkan antrean Celery
    try:
        celery_app.control.purge()
    except Exception as e:
        logger.warning("Gagal purge Celery antrean: %s", e)

    # 3. Bebaskan VRAM/CPU Ollama segera
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": settings.VISION_MODEL_NAME, "keep_alive": 0},
            )
    except Exception as e:
        logger.warning("Gagal unload Ollama model: %s", e)

    logger.info("Dokumen %d: pemrosesan dibatalkan dan memori dibebaskan", document_id)
    return {
        "document_id": document_id,
        "status": "cancelled",
        "message": "Pemrosesan dokumen berhasil dibatalkan dan resource sistem telah dibebaskan.",
    }


@router.delete(
    "/{document_id}",
    summary="Hapus vektor dokumen dari ChromaDB",
    description="Menghapus seluruh chunk embedding yang terkait dengan document_id dari ChromaDB.",
)
async def delete_document_route(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    from app.services.embedding_service import delete_document_vectors
    from app.services.ekstraksi_bertahap import PenyimpananMySQL
    try:
        deleted_count = delete_document_vectors(document_id)
        try:
            PenyimpananMySQL().reset_ekstraksi(document_id)
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




# ── GET /api/docs/{id}/halaman/{n}/citra — Citra satu halaman ────


@router.get(
    "/{document_id}/pages/{page_number}/image",
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
@router.get(
    "/{document_id}/halaman/{page_number}/citra",
    include_in_schema=False,
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

    from pathlib import Path
    mtime = 0
    try:
        mtime = int(Path(berkas).stat().st_mtime)
    except Exception:
        pass

    return Response(
        content=data,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{document_id}-{page_number}-{zoom}-{mtime}"',
            # Dipakai editor untuk menyiapkan ukuran panel tanpa menunggu
            # gambarnya selesai diurai browser.
            "X-Lebar-Piksel": str(lebar),
            "X-Tinggi-Piksel": str(tinggi),
        },
    )


# ── GET /api/docs/{id}/pages/dimensions — Ukuran semua halaman ──
@router.get(
    "/{document_id}/pages/dimensions",
    summary="Ukuran dan orientasi semua halaman",
    description=(
        "Lebar, tinggi, dan orientasi tiap halaman pada perbesaran bawaan — "
        "tanpa merender apa pun. Dipakai editor untuk menyiapkan ukuran panel."
    ),
)
@router.get(
    "/{document_id}/halaman/ukuran",
    include_in_schema=False,
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


@router.get("/ollama/tags", tags=["Ollama"])
def get_ollama_tags():
    """Mengambil daftar model yang terpasang di server Ollama."""
    import requests

    try:
        r = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            return r.json()
        return {"models": []}
    except Exception as e:
        logger.warning("Gagal mengambil tag Ollama: %s", e)
        return {"models": []}


@router.get("/extraction-prompts", tags=["Ollama"])
@router.get("/prompt-ekstraksi", tags=["Ollama"], include_in_schema=False)
def prompt_ekstraksi_bawaan(_token: str = Depends(verify_token)) -> dict:
    """
    Teks prompt bawaan yang BENAR-BENAR dipakai saat ekstraksi.

    Diambil langsung dari konstanta di pdf_processor, bukan disalin ke frontend.
    Salinan di frontend pernah ada dan itulah sumber masalahnya: teksnya mirip
    tapi tidak sama, admin menyetel berdasarkan teks yang tidak pernah berjalan,
    dan tidak ada yang memberi tahu ketika keduanya melenceng. Dengan diambil
    dari sini, keduanya tidak bisa berbeda.
    """
    from app.services import pdf_processor as pp

    return {
        "dasar": {
            "judul": "Aturan dasar",
            "kapan": "",
            "teks": pp._PROMPT_OCR_DASAR,
        },
        "tabel_sop": {
            "judul": "Petunjuk tabel prosedur SOP",
            "kapan": (
                "Dipasang otomatis begitu sebuah halaman terdeteksi berformat "
                "formulir SOP, lalu ikut dipakai pada halaman-halaman berikutnya."
            ),
            "teks": pp._PETUNJUK_TABEL_SOP,
        },
        "kepala_sop": {
            "judul": "Petunjuk kepala formulir SOP",
            "kapan": (
                "Hanya dipasang pada halaman yang kepala formulirnya memang "
                "terlihat ('Nomor SOP', 'Nama SOP', 'Disahkan Oleh')."
            ),
            "teks": pp._PETUNJUK_KEPALA_SOP,
        },
    }


@router.post("/test-prompt", tags=["Ollama"])
def test_prompt_endpoint(payload: dict):
    """
    Uji coba prompt ekstraksi pada satu gambar.

    Menjalankan gambar lewat `ekstrak_gambar_uji`, yaitu jalur vision yang SAMA
    dengan yang dipakai tombol Ekstraksi. Endpoint ini sengaja tidak punya
    logika prompt sendiri — dulu punya, dan itulah sumber kebingungannya:
    sandbox memakai prompt kategori sebagai pengganti aturan dasar dan tidak
    mengenal deteksi formulir SOP, sehingga hasil uji tidak mewakili hasil
    sungguhan.

    Tahap koreksi LLM juga sudah dihapus. Pipeline produksi tidak punya tahap
    itu — koreksi dikerjakan manusia lewat editor koreksi — dan menyimulasikan
    tahap yang tidak ada membuat hasil uji makin jauh dari kenyataan. Di mesin
    ber-VRAM terbatas tahap itu juga memaksa tukar model vision <-> teks pada
    tiap halaman, yang mahal.
    """
    import time

    from app.services.pdf_processor import ekstrak_gambar_uji

    start_time = time.time()
    try:
        image_base64 = payload.get("image_base64", "")
        if not image_base64:
            return {"success": False, "error": "Gambar (base64) wajib diunggah."}

        # Bersihkan format data URL bila ada
        if "," in image_base64:
            image_base64 = image_base64.split(",", 1)[1]

        category = payload.get("category") or {}
        vision_model = (category.get("vision_model") or "").strip() or None

        # Kata kunci disimpan sebagai daftar di prompt_variables; sisi ekstraksi
        # menerimanya sebagai teks. Kunci lama `job_titles` tetap dibaca supaya
        # kategori yang sudah ada tidak kehilangan datanya.
        prompt_vars = category.get("prompt_variables") or {}
        daftar = prompt_vars.get("kata_kunci") or prompt_vars.get("job_titles") or []
        kata_kunci = ", ".join(daftar) if isinstance(daftar, list) else str(daftar)
        custom_prompts = prompt_vars.get("custom_prompts") or category.get("custom_prompts") or None

        hasil = ekstrak_gambar_uji(
            image_base64,
            category_prompt=(category.get("vision_prompt") or "").strip() or None,
            job_titles=kata_kunci or None,
            vision_model=vision_model,
            custom_prompts=custom_prompts,
        )

        return {
            "success": True,
            "result": hasil["teks"],
            "raw_ocr": hasil["teks_awal"],
            "petunjuk_aktif": hasil["petunjuk_aktif"],
            "duration": round(time.time() - start_time, 2),
        }
    except Exception as e:
        logger.exception("Error saat uji coba prompt")
        return {
            "success": False,
            "error": str(e),
            "duration": round(time.time() - start_time, 2),
        }


