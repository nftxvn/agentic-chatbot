"""
Service untuk memproses file PDF.
Mendukung PDF teks biasa, PDF hasil scan (OCR), dan campuran keduanya.
"""

import io
import logging
from pathlib import Path

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# Threshold minimum jumlah karakter untuk dianggap sebagai halaman teks
_MIN_TEXT_LENGTH = 30


def detect_pdf_type(file_path: str) -> str:
    """
    Mendeteksi tipe PDF berdasarkan konten setiap halaman.

    Mengecek setiap halaman apakah memiliki teks yang bisa diekstrak.
    - 'text'    : Semua halaman memiliki teks yang bisa diekstrak.
    - 'scanned' : Semua halaman berupa gambar tanpa teks.
    - 'mixed'   : Campuran halaman teks dan halaman scan.

    Args:
        file_path: Path absolut ke file PDF.

    Returns:
        String tipe PDF: 'text', 'scanned', atau 'mixed'.

    Raises:
        FileNotFoundError: Jika file tidak ditemukan.
        Exception: Jika terjadi error saat membaca PDF.
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

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
                # Cek apakah halaman memiliki gambar (indikasi scan)
                image_list = page.get_images(full=True)
                if image_list:
                    has_scanned_pages = True
                else:
                    # Halaman kosong tanpa teks dan tanpa gambar
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


def _extract_text_from_page(page: fitz.Page) -> str:
    """
    Ekstrak teks dari satu halaman menggunakan PyMuPDF.

    Args:
        page: Objek halaman PyMuPDF.

    Returns:
        Teks yang diekstrak dari halaman.
    """
    return page.get_text().strip()


def _ocr_page(page: fitz.Page, dpi: int = 300) -> str:
    """
    Melakukan OCR pada satu halaman PDF menggunakan Tesseract.

    Mengkonversi halaman ke gambar (pixmap), lalu menjalankan
    Tesseract OCR untuk mengekstrak teks.

    Args:
        page: Objek halaman PyMuPDF.
        dpi: Resolusi gambar untuk OCR (default: 300 DPI).

    Returns:
        Teks hasil OCR dari halaman.
    """
    try:
        # Konversi halaman ke pixmap dengan resolusi tinggi
        zoom = dpi / 72  # 72 adalah DPI default PDF
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)

        # Konversi pixmap ke PIL Image
        img_data = pixmap.tobytes("png")
        image = Image.open(io.BytesIO(img_data))

        # Jalankan OCR menggunakan Tesseract (bahasa Indonesia + Inggris)
        text = pytesseract.image_to_string(image, lang="ind+eng")

        return text.strip()

    except Exception as e:
        logger.error("Gagal melakukan OCR pada halaman: %s", str(e))
        return ""


def extract_text(file_path: str) -> list[dict]:
    """
    Mengekstrak teks dari seluruh halaman PDF.

    Untuk halaman yang memiliki teks, menggunakan PyMuPDF langsung.
    Untuk halaman hasil scan, menggunakan Tesseract OCR.

    Args:
        file_path: Path absolut ke file PDF.

    Returns:
        List of dict dengan format:
        [
            {"page_number": 1, "text": "isi teks halaman 1"},
            {"page_number": 2, "text": "isi teks halaman 2"},
            ...
        ]

    Raises:
        FileNotFoundError: Jika file tidak ditemukan.
        Exception: Jika terjadi error saat memproses PDF.
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    pages_content: list[dict] = []

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        logger.info("Memproses PDF '%s' (%d halaman)", file_path, total_pages)

        for page_num in range(total_pages):
            page = doc[page_num]
            text = _extract_text_from_page(page)

            # Jika teks terlalu sedikit, coba OCR
            if len(text) < _MIN_TEXT_LENGTH:
                logger.info(
                    "Halaman %d: teks minim (%d karakter), mencoba OCR...",
                    page_num + 1,
                    len(text),
                )
                ocr_text = _ocr_page(page)
                if ocr_text:
                    text = ocr_text

            if text:  # Hanya tambahkan halaman yang memiliki konten
                pages_content.append({
                    "page_number": page_num + 1,
                    "text": text,
                })

        doc.close()

        logger.info(
            "Berhasil mengekstrak teks dari %d/%d halaman PDF '%s'",
            len(pages_content),
            total_pages,
            file_path,
        )

        return pages_content

    except Exception as e:
        logger.error("Gagal mengekstrak teks dari PDF '%s': %s", file_path, str(e))
        raise
