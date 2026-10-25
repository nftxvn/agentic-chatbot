"""Document pages workflows; routers own request validation and authentication."""

from __future__ import annotations

import logging

from fastapi import HTTPException, Response, status

from app.database import get_document_by_id
from app.services import pdf_processor

logger = logging.getLogger("app.routers.documents")

_ERROR_MESSAGE = "Terjadi kesalahan internal. Rinciannya tercatat di log server."


async def citra_halaman(document_id: int, page_number: int, zoom: float) -> Response:
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


async def ukuran_semua_halaman(document_id: int) -> dict:
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

