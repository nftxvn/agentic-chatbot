"""Extraction control workflows; routers own request validation and authentication."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.database import get_document_by_id
from app.services import ekstraksi_bertahap as eb
from app.services.document_operations import DocumentCleanupPending, DocumentNotFound, DocumentOperationCancelled, start_operation

if TYPE_CHECKING:
    from app.routers.ekstraksi import MulaiEkstraksiRequest

logger = logging.getLogger("app.routers.ekstraksi")

# Poll at the existing two-second cadence and close on terminal states.
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


def _penyimpanan(*, operation_token: str | None = None) -> 'eb.PenyimpananMySQL':
    if operation_token is None:
        return eb.PenyimpananMySQL()
    return eb.PenyimpananMySQL(operation_token=operation_token)


def _mulai_operasi(document_id: int, *, kind: str = "extraction") -> str:
    try:
        return start_operation(document_id, kind=kind)
    except DocumentNotFound as error:
        raise HTTPException(status_code=404, detail=f"Dokumen {document_id} tidak ditemukan") from error
    except DocumentCleanupPending:
        from app.services.vector_cleanup import drain_cleanups
        try:
            drain_cleanups(document_id=document_id, due_only=False)
            return start_operation(document_id, kind=kind)
        except DocumentNotFound as error:
            raise HTTPException(status_code=404, detail=f"Dokumen {document_id} tidak ditemukan") from error
        except DocumentCleanupPending as error:
            raise HTTPException(status_code=503, detail="Pembersihan vektor dokumen masih tertunda. Coba lagi setelah layanan vektor pulih.") from error


async def mulai_ekstraksi(document_id: int, payload: MulaiEkstraksiRequest) -> dict:
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

    # Cabut permintaan jeda sebelumnya saat pengguna menekan mulai/lanjutkan
    operation_token = _mulai_operasi(document_id)
    try:
        _penyimpanan(operation_token=operation_token).batalkan_jeda(document_id)
    except DocumentOperationCancelled as error:
        raise HTTPException(status_code=409, detail="Operasi dokumen telah dibatalkan atau digantikan.") from error

    from app.tasks.ekstraksi import ekstrak_dokumen_task

    ekstrak_dokumen_task.delay(
        document_id,
        dokumen["file_path"],
        payload.maks_halaman,
        category_prompt=category_prompt,
        job_titles=job_titles,
        vision_model=vision_model,
        custom_prompts=custom_prompts,
        _operation_token=operation_token,
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


async def jeda_ekstraksi(document_id: int) -> dict:
    """
    Jeda adalah PERMINTAAN, bukan penghentian seketika.
    Satu panggilan model vision berlangsung 20-60 detik dan tidak bisa dipotong
    di tengah tanpa menyisakan halaman separuh.
    """
    _dokumen_atau_404(document_id)
    _penyimpanan().minta_jeda(document_id)
    logger.info("Dokumen %d: jeda diminta", document_id)

    return {"document_id": document_id, "jeda_diminta": True}


async def status_ekstraksi(document_id: int) -> dict:
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


async def aliran_ekstraksi(document_id: int) -> EventSourceResponse:
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

