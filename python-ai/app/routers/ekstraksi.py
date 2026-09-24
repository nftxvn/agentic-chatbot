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

import json
import logging

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.database import get_document_by_id
from app.routers.documents import verify_token
from app.services import ekstraksi_bertahap as eb

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docs", tags=["Ekstraksi"])

_ERROR_MESSAGE = "Terjadi kesalahan internal. Rinciannya tercatat di log server."

# Jeda antar kabar pada aliran SSE. Dua detik: cukup rapat agar bilah kemajuan
# terasa hidup, cukup renggang agar 171 halaman tidak menghasilkan ribuan
# kabar yang isinya sama.
_JEDA_ALIRAN_DETIK = 2.0


def _dokumen_atau_404(document_id: int) -> dict:
    dokumen = get_document_by_id(document_id)
    if dokumen is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak ditemukan",
        )
    if not dokumen.get("file_path"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dokumen {document_id} tidak punya berkas",
        )
    return dokumen


def _penyimpanan() -> "eb.PenyimpananMySQL":
    return eb.PenyimpananMySQL()


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
@router.post("/{document_id}/extract", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
@router.post("/{document_id}/ekstraksi", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
@router.post("/{document_id}/ekstrak", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
async def mulai_ekstraksi(
    document_id: int,
    payload: MulaiEkstraksiRequest = Body(default_factory=MulaiEkstraksiRequest),
    _token: str = Depends(verify_token),
) -> dict:
    # Mulai atau lanjutkan ekstraksi
    dokumen = _dokumen_atau_404(document_id)

    # Fallback to category settings from database if not explicitly passed in payload
    category_prompt = payload.category_prompt or dokumen.get("category_vision_prompt")
    vision_model = (payload.vision_model or dokumen.get("category_vision_model") or "").strip() or None

    prompt_vars = dokumen.get("category_prompt_variables")
    if isinstance(prompt_vars, str):
        try:
            prompt_vars = json.loads(prompt_vars)
        except Exception:
            prompt_vars = {}
    elif not isinstance(prompt_vars, dict):
        prompt_vars = {}

    job_titles = payload.job_titles
    if not job_titles and prompt_vars:
        daftar = prompt_vars.get("kata_kunci") or prompt_vars.get("job_titles") or []
        job_titles = ", ".join(daftar) if isinstance(daftar, list) else str(daftar) if daftar else None

    custom_prompts = payload.custom_prompts or prompt_vars.get("custom_prompts")

    from app.tasks.ekstraksi import ekstrak_dokumen_task

    ekstrak_dokumen_task.delay(
        document_id,
        dokumen["file_path"],
        payload.maks_halaman,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
    )
    logger.info(
        "Dokumen %d: ekstraksi diantrekan (maks_halaman=%s, vision_model=%s, has_cat_prompt=%s, has_custom_prompts=%s)",
        document_id,
        payload.maks_halaman,
        vision_model,
        bool(category_prompt),
        bool(custom_prompts),
    )

    return {"document_id": document_id, "status": eb.STATUS_ANTRE}


# ── POST /{id}/extraction/pause - Minta berhenti ────────────────
@router.post(
    "/{document_id}/extraction/pause",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Minta ekstraksi berhenti di batas halaman berikutnya",
)
@router.post("/{document_id}/pause", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
@router.post("/{document_id}/ekstraksi/jeda", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
@router.post("/{document_id}/jeda", status_code=status.HTTP_202_ACCEPTED, include_in_schema=False)
async def jeda_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    """
    Jeda adalah PERMINTAAN, bukan penghentian seketika.
    Satu panggilan model vision berlangsung 20-60 detik dan tidak bisa dipotong
    di tengah tanpa menyisakan halaman separuh.
    """
    _dokumen_atau_404(document_id)
    _penyimpanan().minta_jeda(document_id)
    logger.info("Dokumen %d: jeda diminta", document_id)

    return {"document_id": document_id, "jeda_diminta": True}


# ── GET /{id}/ekstraksi - Keadaan sekarang ───────────────────────


@router.get("/{document_id}/extraction", summary="Status dan kemajuan ekstraksi")
@router.get("/{document_id}/ekstraksi", summary="Status dan kemajuan ekstraksi", include_in_schema=False)
async def status_ekstraksi(
    document_id: int,
    _token: str = Depends(verify_token),
) -> dict:
    _dokumen_atau_404(document_id)

    keadaan = _penyimpanan().keadaan(document_id)
    if keadaan is None:
        return {
            "document_id": document_id,
            "status": eb.STATUS_ANTRE,
            "jeda_diminta": False,
            "halaman_total": 0,
            "halaman_selesai": 0,
            "persen": 0,
            "pesan": None,
        }
    return keadaan


# ── GET /{id}/extraction/stream - Kemajuan langsung (SSE) ───────
@router.get(
    "/{document_id}/extraction/stream",
    summary="Kemajuan ekstraksi secara langsung",
)
@router.get(
    "/{document_id}/ekstraksi/aliran",
    include_in_schema=False,
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
    _dokumen_atau_404(document_id)
    penyimpanan = _penyimpanan()

    async def kabar():
        import asyncio

        BERHENTI = {
            eb.STATUS_JEDA,
            eb.STATUS_MENUNGGU_KOREKSI,
            eb.STATUS_SELESAI,
            eb.STATUS_GAGAL,
        }
        terakhir = None

        while True:
            keadaan = penyimpanan.keadaan(document_id) or {
                "status": eb.STATUS_ANTRE,
                "halaman_selesai": 0,
                "halaman_total": 0,
                "persen": 0,
            }

            # Hanya kirim bila ada yang berubah. Bilah kemajuan yang menerima
            # kabar identik tiap dua detik tidak lebih informatif, hanya lebih
            # berisik.
            sidik = (keadaan["status"], keadaan["halaman_selesai"])
            if sidik != terakhir:
                terakhir = sidik
                yield json.dumps(
                    {"type": "kemajuan", "content": keadaan}, ensure_ascii=False
                )

            if keadaan["status"] in BERHENTI:
                yield json.dumps(
                    {"type": "selesai", "content": keadaan["status"]},
                    ensure_ascii=False,
                )
                return

            await asyncio.sleep(_JEDA_ALIRAN_DETIK)

    return EventSourceResponse(kabar(), media_type="text/event-stream")


# ── GET /{id}/pages - Teks semua halaman (untuk editor) ──────────
@router.get("/{document_id}/pages", summary="Teks halaman untuk editor koreksi")
@router.get("/{document_id}/halaman", summary="Teks halaman untuk editor koreksi", include_in_schema=False)
async def daftar_halaman(
    document_id: int,
    perlu_diperiksa: bool = False,
    _token: str = Depends(verify_token),
) -> dict:
    # Daftar halaman untuk editor koreksi
    _dokumen_atau_404(document_id)

    from app.services.pdf_processor import _bagian_kepala_hilang, _header_sop_tidak_lengkap

    halaman = _penyimpanan().teks_terkumpul(document_id)

    if perlu_diperiksa:
        curiga = [
            {
                "page_number": h["page_number"],
                "alasan": f"{_bagian_kepala_hilang(h['text'])} hilang",
            }
            for h in halaman
            if _header_sop_tidak_lengkap(h["text"])
        ]
        return {
            "document_id": document_id,
            "jumlah": len(curiga),
            "halaman": curiga,
        }

    return {
        "document_id": document_id,
        "jumlah": len(halaman),
        "halaman": halaman,
    }


# ── PUT /{id}/pages/{n} - Simpan koreksi satu halaman ────────────
@router.put("/{document_id}/pages/{page_number}", summary="Simpan koreksi satu halaman")
@router.put("/{document_id}/halaman/{page_number}", summary="Simpan koreksi satu halaman", include_in_schema=False)
async def simpan_koreksi(
    document_id: int,
    page_number: int,
    text: str = Body(..., embed=True),
    _token: str = Depends(verify_token),
) -> dict:
    # Simpan koreksi per halaman
    _dokumen_atau_404(document_id)

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Teks halaman tidak boleh kosong. Halaman kosong lenyap dari "
                "korpus tanpa galat, dan baru ketahuan lewat jawaban "
                "'tidak ditemukan'."
            ),
        )

    _penyimpanan().simpan_halaman(document_id, page_number, text)
    logger.info("Dokumen %d halaman %d dikoreksi (%d huruf)", document_id, page_number, len(text))

    return {"document_id": document_id, "page_number": page_number, "tersimpan": True}


class OpsiPemotongan(BaseModel):
    parent_chunk_size: int = Field(1500, ge=300, le=4500)
    parent_chunk_overlap: int = Field(200, ge=0, le=800)
    child_chunk_size: int = Field(300, ge=100, le=1200)
    child_chunk_overlap: int = Field(50, ge=0, le=300)
    strategy: str = "auto"


# ── POST / GET /{id}/chunks/preview - Pratinjau induk/anak ──────
@router.post("/{document_id}/chunks/preview", summary="Pratinjau potongan dengan opsi kustom")
@router.get("/{document_id}/chunks/preview", summary="Pratinjau potongan induk dan anak")
@router.post("/{document_id}/potongan", include_in_schema=False)
@router.get("/{document_id}/potongan", include_in_schema=False)
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
    _dokumen_atau_404(document_id)

    from app.services import embedding_service

    halaman = _penyimpanan().teks_terkumpul(document_id)
    if not halaman:
        return {"document_id": document_id, "induk": [], "anak": [], "siap": False}

    # Ambil parameter dari model opsi atau query params
    p_size = opsi.parent_chunk_size if opsi else (parent_chunk_size or 1500)
    p_overlap = opsi.parent_chunk_overlap if opsi else (parent_chunk_overlap or 200)
    c_size = opsi.child_chunk_size if opsi else (child_chunk_size or 300)
    c_overlap = opsi.child_chunk_overlap if opsi else (child_chunk_overlap or 50)
    strat = opsi.strategy if opsi else "auto"

    judul = embedding_service.derive_document_title(halaman)
    induk, anak = embedding_service.chunk_text_hierarchical(
        halaman,
        document_title=judul,
        parent_chunk_size=p_size,
        parent_chunk_overlap=p_overlap,
        child_chunk_size=c_size,
        child_chunk_overlap=c_overlap,
        strategy=strat,
    )

    return {
        "document_id": document_id,
        "judul": judul,
        "parent_chunk_size": p_size,
        "parent_chunk_overlap": p_overlap,
        "child_chunk_size": c_size,
        "child_chunk_overlap": c_overlap,
        "jumlah_induk": len(induk),
        "jumlah_anak": len(anak),
        "induk": induk,
        "anak": anak,
        "siap": True,
    }


# ── POST /{id}/embed - Tombol akhir: potong lalu embed ───────────
@router.post(
    "/{document_id}/embed",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Potong lalu simpan vektornya ke korpus",
)
@router.post(
    "/{document_id}/simpan",
    status_code=status.HTTP_202_ACCEPTED,
    include_in_schema=False,
)
async def simpan_ke_korpus(
    document_id: int,
    opsi: OpsiPemotongan | None = None,
    _token: str = Depends(verify_token),
) -> dict:
    # Simpan ke korpus
    _dokumen_atau_404(document_id)

    keadaan = _penyimpanan().keadaan(document_id)
    if keadaan is None or keadaan["halaman_selesai"] == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dokumen ini belum punya halaman terekstrak",
        )

    if keadaan["status"] == eb.STATUS_BERJALAN:
        total = keadaan.get("halaman_total") or 0
        selesai = keadaan.get("halaman_selesai") or 0
        if total > 0 and selesai >= total:
            _penyimpanan().catat_status(document_id, eb.STATUS_MENUNGGU_KOREKSI)
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Ekstraksi masih berjalan. Tunggu sampai selesai atau jeda "
                    "dulu sebelum menyimpan ke korpus."
                ),
            )

    from app.tasks.ekstraksi import potong_dan_embed_task

    _penyimpanan().catat_kemajuan_embed(
        document_id,
        status="embedding",
        persen=5,
        pesan="Mengirim permintaan embedding ke antrean worker...",
    )

    custom_kwargs = opsi.dict() if opsi else None
    potong_dan_embed_task.delay(document_id, custom_kwargs)
    logger.info("Dokumen %d: potong & embed diantrekan dengan opsi %s", document_id, custom_kwargs)

    return {"document_id": document_id, "status": "diantrekan"}
