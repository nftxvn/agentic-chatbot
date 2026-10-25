"""
Router untuk endpoint pemrosesan dan manajemen dokumen.
Menerima request dari Laravel untuk memproses PDF dan mengecek status dokumen.
"""

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status

from app.config import settings
from app.schemas import (
    DocumentListResponse,
    DocumentStatusResponse,
)
from app.services import pdf_processor
from app.services.document_workflows import (
    document_lifecycle,
    document_pages,
    document_prompts,
    document_queries,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/docs",
    tags=["Documents"],
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
    return await document_queries.list_documents()


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
    return await document_queries.get_document_status(document_id)


@router.post(
    "/{document_id}/cancel",
    summary="Minta pembatalan pemrosesan dokumen",
    description="Membatalkan operasi satu dokumen secara kooperatif tanpa membersihkan antrean dokumen lain. Hasil operasi aktif dibuang pada batas aman berikutnya.",
)
async def cancel_document_processing(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    return await document_lifecycle.cancel_document_processing(document_id)


@router.delete(
    "/{document_id}",
    summary="Hapus vektor dokumen dari ChromaDB",
    description="Menghapus seluruh chunk embedding yang terkait dengan document_id dari ChromaDB.",
)
async def delete_document_route(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    return await document_lifecycle.delete_document_route(document_id)


@router.get(
    "/vector-counts",
    summary="Hitung jumlah vektor aktif per dokumen di ChromaDB",
    description="Mengambil rekapitulasi jumlah vektor yang tersimpan di ChromaDB dikelompokkan per document_id.",
)
async def get_all_vector_counts_route(
    _token: str = Depends(verify_token),
) -> dict:
    return await document_lifecycle.get_all_vector_counts_route()


@router.get(
    "/{document_id}/chunks",
    summary="Ambil daftar chunk dokumen",
    description="Mengambil semua chunk teks yang tersimpan di ChromaDB untuk dokumen tertentu.",
)
async def get_document_chunks_route(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    return await document_lifecycle.get_document_chunks_route(document_id)


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
    return await document_pages.citra_halaman(document_id, page_number, zoom)


# ── GET /api/docs/{id}/pages/dimensions — Ukuran semua halaman ──
@router.get(
    "/{document_id}/pages/dimensions",
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
    return await document_pages.ukuran_semua_halaman(document_id)


@router.get("/ollama/tags", tags=["Ollama"])
def get_ollama_tags():
    """Mengambil daftar model yang terpasang di server Ollama."""
    return document_prompts.get_ollama_tags()


@router.get("/extraction-prompts", tags=["Ollama"])
def prompt_ekstraksi_bawaan(_token: str = Depends(verify_token)) -> dict:
    """
    Teks prompt bawaan yang BENAR-BENAR dipakai saat ekstraksi.

    Diambil langsung dari konstanta di pdf_processor, bukan disalin ke frontend.
    Salinan di frontend pernah ada dan itulah sumber masalahnya: teksnya mirip
    tapi tidak sama, admin menyetel berdasarkan teks yang tidak pernah berjalan,
    dan tidak ada yang memberi tahu ketika keduanya melenceng. Dengan diambil
    dari sini, keduanya tidak bisa berbeda.
    """
    return document_prompts.prompt_ekstraksi_bawaan()


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
    return document_prompts.test_prompt_endpoint(payload)


