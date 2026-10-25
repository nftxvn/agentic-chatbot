"""Resolusi path, render JPEG, ukuran/deteksi halaman, dan teks PDF native.

ZOOM_OCR adalah nama konstanta lama untuk zoom editor/API sebesar 2.0.
Pipeline OCR memakai zoom 1.5 secara terpisah. Zoom API berupa daftar tertutup;
render JPEG memakai kualitas 80 dan batas sisi panjang yang sama.
"""

import logging
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except (ImportError, Exception):
    fitz = None


logger = logging.getLogger("app.services.pdf_processor")

_MIN_TEXT_LENGTH = 300


ZOOM_OCR = 2.0


ZOOM_DIIZINKAN = (1.5, 2.0, 3.0, 4.0)


_MUTU_JPEG = 80


def _resolve_pdf_path(file_path: str) -> str:
    """Mencari lokasi fisik berkas dokumen di berbagai kemungkinan path storage."""
    if not file_path:
        raise FileNotFoundError("Path berkas kosong")

    p = Path(file_path)
    if p.exists() and p.is_file():
        return str(p)

    filename = p.name
    candidates = [
        Path("/var/www/html/storage/app/private/documents") / filename,
        Path("/var/www/html/storage/app/documents") / filename,
        Path("/var/www/html/storage/app/private") / filename,
        Path("/var/www/html/storage/app") / filename,
        Path("/app/data/uploads") / filename,
        Path("/app/uploads") / filename,
        Path("./laravel-admin/storage/app/private/documents") / filename,
        Path("./laravel-admin/storage/app/documents") / filename,
    ]
    for cand in candidates:
        if cand.exists() and cand.is_file():
            return str(cand)

    norm = file_path.replace("\\", "/")
    if "storage/" in norm:
        rel = norm.split("storage/", 1)[1]
        cand = Path("/var/www/html/storage") / rel
        if cand.exists() and cand.is_file():
            return str(cand)

    raise FileNotFoundError(f"Berkas tidak ditemukan: {file_path}")


def render_halaman(
    file_path: str, page_number: int, zoom: float = ZOOM_OCR
) -> tuple[bytes, int, int]:
    """
    Render satu halaman PDF jadi JPEG.

    Args:
        file_path: berkas PDF.
        page_number: nomor halaman, dihitung dari 1 — sama seperti yang dilihat
            pengguna dan yang dipakai di seluruh API. PyMuPDF memakai indeks 0;
            penyesuaiannya dikerjakan di sini, satu kali, supaya pemanggil tidak
            perlu mengingatnya.
        zoom: perbesaran. Harus salah satu dari ZOOM_DIIZINKAN.

    Returns:
        (data JPEG, lebar piksel, tinggi piksel)

    Raises:
        FileNotFoundError: berkas tidak ada.
        ValueError: nomor halaman di luar jangkauan, atau zoom tidak diizinkan.
    """
    if zoom not in ZOOM_DIIZINKAN:
        raise ValueError(
            f"zoom {zoom} tidak diizinkan. Pilih salah satu: "
            f"{', '.join(str(z) for z in ZOOM_DIIZINKAN)}"
        )

    file_path = _resolve_pdf_path(file_path)

    with fitz.open(file_path) as doc:
        if not 1 <= page_number <= len(doc):
            raise ValueError(
                f"Halaman {page_number} di luar jangkauan (dokumen ini {len(doc)} halaman)"
            )

        page = doc[page_number - 1]
        rect = page.rect
        max_side = max(rect.width, rect.height)
        effective_zoom = zoom
        if max_side * zoom > 2560:
            effective_zoom = max(2560.0 / max_side, 0.5)

        pix = page.get_pixmap(matrix=fitz.Matrix(effective_zoom, effective_zoom))
        return pix.tobytes("jpeg", jpg_quality=_MUTU_JPEG), pix.width, pix.height


def ukuran_halaman(file_path: str) -> list[dict]:
    """
    Lebar dan tinggi tiap halaman pada perbesaran bawaan, tanpa merender apa pun.

    Dipakai editor web untuk menyiapkan ukuran panel sebelum gambarnya sampai.
    Tanpa ini panel berkedip menyesuaikan ukuran tiap kali pindah halaman —
    dan pada dokumen ini kedipannya nyata, karena 6 dari 171 halaman potret
    sementara sisanya lanskap.
    """
    file_path = _resolve_pdf_path(file_path)

    with fitz.open(file_path) as doc:
        return [
            {
                "page_number": i + 1,
                "lebar": round(h.rect.width * ZOOM_OCR),
                "tinggi": round(h.rect.height * ZOOM_OCR),
                "orientasi": "lanskap" if h.rect.width >= h.rect.height else "potret",
            }
            for i, h in enumerate(doc)
        ]


def detect_pdf_type(file_path: str) -> str:
    """
    Mendeteksi tipe PDF berdasarkan konten setiap halaman.
    """
    file_path = _resolve_pdf_path(file_path)

    try:
        doc = fitz.open(file_path)
        has_text_pages = False
        has_scanned_pages = False

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text().strip()

            if len(text) >= _MIN_TEXT_LENGTH:
                has_text_pages = True
            else:
                image_list = page.get_images(full=True)
                if image_list:
                    has_scanned_pages = True
                else:
                    has_scanned_pages = True

        doc.close()

        if has_text_pages and has_scanned_pages:
            pdf_type = "mixed"
        elif has_scanned_pages:
            pdf_type = "scanned"
        else:
            pdf_type = "text"

        logger.info("Tipe PDF '%s' terdeteksi: %s", file_path, pdf_type)
        return pdf_type

    except Exception as e:
        logger.error("Gagal mendeteksi tipe PDF '%s': %s", file_path, str(e))
        raise


def _extract_text_from_page(page: "fitz.Page") -> str:
    """
    Ekstrak teks dan tabel dari halaman secara native dengan PyMuPDF.
    Hanya membaca teks — tidak mencoba membaca gambar flowchart.
    """
    tabs = page.find_tables()

    if not tabs.tables:
        return page.get_text().strip()

    elements = []
    table_bboxes = []

    for tab in tabs:
        table_bboxes.append(tab.bbox)
        rows = tab.extract()

        # Convert ke Markdown
        md_table = []
        for r in rows:
            cleaned_row = [str(c).replace("\n", " ").replace("|", "/").strip() if c else "-" for c in r]
            md_table.append("| " + " | ".join(cleaned_row) + " |")

        if len(rows) > 0:
            sep = "| " + " | ".join(["---"] * len(rows[0])) + " |"
            md_table.insert(1, sep)

        elements.append({
            "type": "table",
            "y0": tab.bbox[1],
            "content": "\n".join(md_table)
        })

    # Ekstrak blocks teks biasa (di luar tabel)
    blocks = page.get_text("blocks")
    for b in blocks:
        b_rect = fitz.Rect(b[:4])
        b_text = b[4].strip()

        if not b_text:
            continue

        in_table = False
        for t_bbox in table_bboxes:
            t_rect = fitz.Rect(t_bbox)
            if t_rect.intersects(b_rect):
                in_table = True
                break

        if not in_table:
            elements.append({
                "type": "text",
                "y0": b_rect.y0,
                "content": b_text
            })

    # Urutkan berdasarkan posisi Y (dari atas ke bawah)
    elements.sort(key=lambda x: x["y0"])
    return "\n\n".join([e["content"] for e in elements])


