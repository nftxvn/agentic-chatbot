"""Extraction corrections workflows; routers own request validation and authentication."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from .extraction_control import _dokumen_atau_404, _penyimpanan

logger = logging.getLogger("app.routers.ekstraksi")


async def daftar_halaman(document_id: int, perlu_diperiksa: bool) -> dict:
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


async def simpan_koreksi(document_id: int, page_number: int, text: str) -> dict:
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

