"""Extraction chunks workflows; routers own request validation and authentication."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import HTTPException, status

from app.services import ekstraksi_bertahap as eb

from .extraction_control import _dokumen_atau_404, _mulai_operasi, _penyimpanan
from app.services.document_operations import DocumentOperationCancelled

if TYPE_CHECKING:
    from app.routers.ekstraksi import OpsiPemotongan

logger = logging.getLogger("app.routers.ekstraksi")


async def pratinjau_potongan(
    document_id: int,
    opsi: OpsiPemotongan | None,
    parent_chunk_size: int | None,
    parent_chunk_overlap: int | None,
    child_chunk_size: int | None,
    child_chunk_overlap: int | None,
) -> dict:
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


async def simpan_ke_korpus(document_id: int, opsi: OpsiPemotongan | None) -> dict:
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

    operation_token = _mulai_operasi(document_id, kind="embedding")
    try:
        _penyimpanan(operation_token=operation_token).catat_kemajuan_embed(
            document_id,
            status="embedding",
            persen=5,
            pesan="Mengirim permintaan embedding ke antrean worker...",
        )
    except DocumentOperationCancelled as error:
        raise HTTPException(status_code=409, detail="Operasi dokumen telah dibatalkan atau digantikan.") from error

    custom_kwargs = opsi.dict() if opsi else None
    potong_dan_embed_task.delay(document_id, custom_kwargs, _operation_token=operation_token)
    logger.info("Dokumen %d: potong & embed diantrekan dengan opsi %s", document_id, custom_kwargs)

    return {"document_id": document_id, "status": "diantrekan"}

