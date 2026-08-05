"""
Service untuk memproses file PDF.
Mendukung PDF teks biasa, PDF hasil scan (vision), dan campuran keduanya.
Ekstraksi halaman scan menggunakan vision-language model via Ollama
sehingga mampu memahami struktur tabel dan layout dokumen lebih baik.
"""

import base64
import logging
from pathlib import Path

import fitz  # PyMuPDF
import requests

from app.config import settings

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


def _vision_extract_page(page: fitz.Page, dpi: int = 200, retries: int = 2) -> str:
    """
    Mengekstrak teks dari satu halaman PDF menggunakan vision-language model via Ollama.

    Mengkonversi halaman ke gambar (pixmap PNG), meng-encode ke base64, lalu
    mengirimkan ke endpoint Ollama /api/generate bersama prompt ekstraksi teks.
    Model vision mampu memahami struktur paragraf, tabel, dan layout dokumen
    lebih baik dibandingkan Tesseract OCR konvensional.

    Args:
        page: Objek halaman PyMuPDF.
        dpi: Resolusi render gambar (default: 200 DPI, cukup untuk vision model).
        retries: Jumlah maksimal percobaan ulang jika request gagal (default: 2).

    Returns:
        Teks yang diekstrak oleh vision model, atau string kosong jika gagal total.
        Tidak melempar exception agar proses halaman lain tetap berjalan.
    """
    # Render halaman PDF ke PNG bytes lalu encode ke base64
    zoom = dpi / 72  # 72 adalah DPI default PDF
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix)
    img_bytes = pixmap.tobytes("png")
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")

    prompt = (
        "Anda adalah sistem ekstraksi dokumen tingkat lanjut. Tugas Anda adalah mengekstrak seluruh teks dari gambar dokumen Standar Operasional Prosedur (SOP) ini secara akurat dan menyusunnya kembali secara ketat ke dalam format tabel Markdown.\n\n"
        "Ikuti aturan \"cara berpikir\" ekstraksi berikut:\n"
        "1. IDENTIFIKASI STRUKTUR: Perhatikan garis vertikal dan horizontal. Dokumen ini adalah tabel dengan kolom utama: \"No\", \"Uraian Prosedur\", \"Pelaksana\", \"Mutu Baku\", dan \"Ket\".\n"
        "2. BACA PER BARIS, BUKAN PER GARIS LURUS: Jangan menggabungkan teks dari kolom yang berbeda (misalnya, teks 'Uraian' dengan nama jabatan di kolom 'Pelaksana').\n"
        "3. EKSTRAKSI PENUH: Tangkap semua teks, termasuk catatan kecil di kolom \"Ket\" (Keterangan) jika ada.\n"
        "4. FORMAT: Keluarkan hasil HANYA dalam bentuk tabel Markdown. Jangan menambahkan basa-basi."
    )

    payload = {
        "model": settings.VISION_MODEL_NAME,
        "prompt": prompt,
        "images": [img_base64],
        "stream": False,
        "options": {
            "num_ctx": 8192,      # naikkan context window, dari default 4096
            "num_predict": 2048,  # batas token output biar teks nggak kepotong
        },
    }
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=settings.VISION_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "").strip()

        except requests.exceptions.RequestException as exc:
            body = getattr(getattr(exc, "response", None), "text", "")
            logger.warning(
                "Percobaan %d/%d gagal memanggil vision model untuk ekstraksi halaman: %s | Body: %s",
                attempt,
                retries,
                str(exc),
                body,
            )

    logger.error(
        "Semua percobaan (%d) gagal, halaman dilewati tanpa teks vision.", retries
    )
    return ""


def _clean_text_with_llm(dirty_text: str, retries: int = 2) -> str:
    """
    Menggunakan LLM untuk mengoreksi typo dan merapikan teks kotor hasil OCR/Vision.
    """
    if not dirty_text.strip():
        return dirty_text

    prompt = (
        "Anda adalah editor ahli dan auditor bahasa untuk dokumen Standar Operasional Prosedur (SOP) birokrasi pemerintahan Indonesia. Tugas Anda adalah memperbaiki hasil teks OCR (Optical Character Recognition) yang kotor tanpa merusak format tabel Markdown aslinya.\n\n"
        "Aturan Koreksi Anda:\n"
        "1. Pahami konteks kalimat birokrasi, keuangan, dan tata usaha pemerintahan (contoh: SPJ, BKU, PA/KPA, PPKD).\n"
        "2. Koreksi halusinasi OCR yang tidak masuk akal (misal: \"Ursian\" menjadi \"Uraian\", \"Kelesekaan\" menjadi \"Kelengkapan\", \"disrap\" menjadi \"diarsip\").\n"
        "3. JANGAN mengubah struktur tabel Markdown (simbol `|` dan `-`).\n"
        "4. JANGAN merangkum atau memotong teks.\n\n"
        "Berikut adalah teks OCR kotor dari sebuah tabel SOP:\n\n"
        f"{dirty_text}\n\n"
        "Sebelum Anda memberikan tabel yang sudah diperbaiki, Anda WAJIB menjabarkan proses berpikir Anda di dalam blok <analisis>.\n"
        "Dalam blok tersebut, lakukan langkah berikut:\n"
        "1. Deteksi kata-kata aneh/typo dari teks di atas.\n"
        "2. Tentukan perbaikan yang masuk akal berdasarkan konteks tata bahasa birokrasi.\n\n"
        "Setelah blok <analisis> selesai, berikan hasil akhir HANYA berupa tabel Markdown yang sudah bersih.\n\n"
        "Format jawaban Anda harus seperti ini:\n"
        "<analisis>\n"
        "- Menemukan kata \"X\", seharusnya \"Y\" karena konteksnya adalah Z.\n"
        "- Menemukan kata \"A\", seharusnya \"B\"...\n"
        "</analisis>\n\n"
        "[Tabel Markdown Bersih]"
    )

    payload = {
        "model": settings.LLM_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_ctx": 4096,
            "num_predict": 2048,
            "temperature": 0.0,  # Mematikan kreativitas agar tidak halusinasi
            "top_p": 0.1,
        },
    }
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            raw_response = result.get("response", "").strip()
            
            # Hapus blok <analisis>...</analisis> dari output LLM
            if "</analisis>" in raw_response:
                clean_text = raw_response.split("</analisis>")[-1].strip()
            else:
                clean_text = raw_response
                
            # Jika LLM mengembalikan string kosong, fallback ke teks asli
            return clean_text if clean_text else dirty_text

        except requests.exceptions.RequestException as exc:
            body = getattr(getattr(exc, "response", None), "text", "")
            logger.warning(
                "Percobaan %d/%d gagal memanggil LLM untuk koreksi teks: %s | Body: %s",
                attempt,
                retries,
                str(exc),
                body,
            )

    logger.error("Semua percobaan (%d) gagal, mengembalikan teks asli tanpa koreksi.", retries)
    return dirty_text


def extract_text(file_path: str) -> list[dict]:
    """
    Mengekstrak teks dari seluruh halaman PDF.

    Untuk halaman yang memiliki teks, menggunakan PyMuPDF langsung.
    Untuk halaman hasil scan, menggunakan vision-language model via Ollama.

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

            # Jika teks terlalu sedikit, gunakan vision model untuk ekstraksi
            if len(text) < _MIN_TEXT_LENGTH:
                logger.info(
                    "Halaman %d: teks minim (%d karakter), mencoba ekstraksi via vision model...",
                    page_num + 1,
                    len(text),
                )
                vision_text = _vision_extract_page(page)
                if vision_text:
                    logger.info("Halaman %d: Mengoreksi typo teks hasil vision via LLM...", page_num + 1)
                    text = _clean_text_with_llm(vision_text)

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

def process_single_page(page: fitz.Page, page_num: int) -> dict:
    """
    Ekstrak dan bersihkan teks dari satu halaman PDF (text / vision / llm correction).
    """
    text = _extract_text_from_page(page)

    if len(text) < _MIN_TEXT_LENGTH:
        logger.info(
            "Halaman %d: teks minim (%d karakter), mengekstrak via Vision Model...",
            page_num,
            len(text),
        )
        vision_text = _vision_extract_page(page)
        if vision_text:
            logger.info("Halaman %d: Mengoreksi hasil Vision via LLM...", page_num)
            text = _clean_text_with_llm(vision_text)

    if text:
        return {"page_number": page_num, "text": text}
    return {"page_number": page_num, "text": ""}

