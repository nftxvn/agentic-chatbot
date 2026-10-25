"""
Endpoint kendali ekstraksi bertahap: mulai, jeda, lanjut, koreksi, simpan.

Alur yang dilayani berkas ini punya dua gerbang manual. Sistem berhenti sendiri
dan menunggu manusia di keduanya:

    unggah -> ekstraksi (bisa dijeda) -> KOREKSI -> pratinjau -> SIMPAN -> selesai

Tidak ada tahap yang berjalan otomatis setelah tahap sebelumnya selesai. Hasil
OCR dokumen pindaian tidak layak masuk korpus tanpa diperiksa mata manusia, dan
embedding adalah satu-satunya langkah yang mahal sekaligus mengganti isi korpus
- jadi hanya itu yang dijaga tombol.
"""


from fastapi import APIRouter, Body, Depends, status
from pydantic import BaseModel, Field

from app.routers.documents import verify_token
from app.services.document_workflows import (
    extraction_chunks,
    extraction_control,
    extraction_corrections,
)

router = APIRouter(prefix="/api/docs", tags=["Ekstraksi"])

# ── POST /{id}/ekstraksi - Mulai atau lanjutkan ──────────────────


class MulaiEkstraksiRequest(BaseModel):
    maks_halaman: int | None = None
    category_prompt: str | None = None
    job_titles: str | None = None
    vision_model: str | None = None
    custom_prompts: dict | None = None


@router.post(
    "/{document_id}/extraction",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Mulai atau lanjutkan ekstraksi",
)
async def mulai_ekstraksi(
    document_id: int,
    payload: MulaiEkstraksiRequest = Body(default_factory=MulaiEkstraksiRequest),
    _token: str = Depends(verify_token),
) -> dict:
    # Mulai atau lanjutkan ekstraksi
    return await extraction_control.mulai_ekstraksi(document_id, payload)


# ── POST /{id}/extraction/pause - Minta berhenti ────────────────
@router.post(
    "/{document_id}/extraction/pause",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Minta ekstraksi berhenti di batas halaman berikutnya",
)
async def jeda_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    """
    Jeda adalah PERMINTAAN, bukan penghentian seketika.
    Satu panggilan model vision berlangsung 20-60 detik dan tidak bisa dipotong
    di tengah tanpa menyisakan halaman separuh.
    """
    return await extraction_control.jeda_ekstraksi(document_id)


# ── GET /{id}/ekstraksi - Keadaan sekarang ───────────────────────


@router.get("/{document_id}/extraction", summary="Status dan kemajuan ekstraksi")
async def status_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    return await extraction_control.status_ekstraksi(document_id)


# ── GET /{id}/extraction/stream - Kemajuan langsung (SSE) ───────
@router.get(
    "/{document_id}/extraction/stream",
    summary="Kemajuan ekstraksi secara langsung",
)
async def aliran_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
):
    """
    Aliran ditutup sendiri begitu pekerjaannya berhenti - selesai, dijeda,
    menunggu koreksi, atau gagal. Aliran yang dibiarkan terbuka selamanya
    menahan koneksi dan worker untuk keadaan yang tidak akan berubah lagi.
    """
    return await extraction_control.aliran_ekstraksi(document_id)


# ── GET /{id}/pages - Teks semua halaman (untuk editor) ──────────
@router.get("/{document_id}/pages", summary="Teks halaman untuk editor koreksi")
async def daftar_halaman(
    document_id: int,
    perlu_diperiksa: bool = False,
    _token: str = Depends(verify_token),
) -> dict:
    # Daftar halaman untuk editor koreksi
    return await extraction_corrections.daftar_halaman(document_id, perlu_diperiksa)


# ── PUT /{id}/pages/{n} - Simpan koreksi satu halaman ────────────
@router.put("/{document_id}/pages/{page_number}", summary="Simpan koreksi satu halaman")
async def simpan_koreksi(
    document_id: int,
    page_number: int,
    text: str = Body(..., embed=True),
    _token: str = Depends(verify_token),
) -> dict:
    # Simpan koreksi per halaman
    return await extraction_corrections.simpan_koreksi(document_id, page_number, text)


class OpsiPemotongan(BaseModel):
    parent_chunk_size: int = Field(1500, ge=300, le=4500)
    parent_chunk_overlap: int = Field(200, ge=0, le=800)
    child_chunk_size: int = Field(300, ge=100, le=1200)
    child_chunk_overlap: int = Field(50, ge=0, le=300)
    strategy: str = "auto"


# ── POST / GET /{id}/chunks/preview - Pratinjau induk/anak ──────
@router.post("/{document_id}/chunks/preview", summary="Pratinjau potongan dengan opsi kustom")
@router.get("/{document_id}/chunks/preview", summary="Pratinjau potongan induk dan anak")
async def pratinjau_potongan(
    document_id: int,
    opsi: OpsiPemotongan | None = None,
    parent_chunk_size: int | None = None,
    parent_chunk_overlap: int | None = None,
    child_chunk_size: int | None = None,
    child_chunk_overlap: int | None = None,
    _token: str = Depends(verify_token),
) -> dict:
    # Dihitung saat diminta, tidak disimpan.
    return await extraction_chunks.pratinjau_potongan(
        document_id,
        opsi,
        parent_chunk_size,
        parent_chunk_overlap,
        child_chunk_size,
        child_chunk_overlap,
    )


# ── POST /{id}/embed - Tombol akhir: potong lalu embed ───────────
@router.post(
    "/{document_id}/embed",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Potong lalu simpan vektornya ke korpus",
)
async def simpan_ke_korpus(
    document_id: int,
    opsi: OpsiPemotongan | None = None,
    _token: str = Depends(verify_token),
) -> dict:
    # Simpan ke korpus
    return await extraction_chunks.simpan_ke_korpus(document_id, opsi)
