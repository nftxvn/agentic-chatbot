"""
Service untuk memproses file PDF dan mengekstrak gambar secara umum.
Tidak lagi terbatas pada tabel SOP.
"""

import base64
import logging
import re
from pathlib import Path

import fitz  # PyMuPDF
import requests

from app.config import settings

logger = logging.getLogger(__name__)

# Threshold minimum jumlah karakter untuk dianggap sebagai halaman teks murni
# Ditingkatkan ke 300 agar halaman SOP (yang sebagian besar flowchart/gambar tapi punya header teks)
# tetap dikirim ke vision pipeline agar tidak terlewat.
_MIN_TEXT_LENGTH = 300


def detect_pdf_type(file_path: str) -> str:
    """
    Mendeteksi tipe PDF berdasarkan konten setiap halaman.
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


def _extract_text_from_page(page: fitz.Page) -> str:
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


def _strip_garbage(text: str) -> str:
    """Hapus tag HTML dan base64 image dari output LLM, tanpa merusak tabel Markdown."""
    text = re.sub(r'<img[^>]+/?>', '', text)
    
    # Bersihkan markdown code fences (misalnya ```markdown ... ```)
    if text.startswith("```"):
        lines = text.split('\n')
        if len(lines) > 2:
            text = '\n'.join(lines[1:-1])
    
    return text.strip()


def vision_extract_general(img_base64: str, retries: int = 2) -> str:
    """Fallback pipeline: uses LLM vision to extract text from a full page image."""
    logger.info("Using general vision extraction pipeline...")

    prompt = (
        "Anda adalah sistem OCR canggih yang membaca dokumen pemerintahan Indonesia. "
        "Ekstrak SEMUA teks dari gambar ini ke format teks/daftar. JANGAN gunakan tabel Markdown (tanda |).\n\n"

        "ATURAN SANGAT PENTING (BACA BAIK-BAIK):\n"
        "Dokumen ini terdiri dari 2 bagian: HEADER (Informasi SOP) dan TABEL PROSEDUR (Langkah-langkah).\n\n"

        "1. BAGIAN HEADER (Teks Biasa & Daftar):\n"
        "Bagian seperti 'Nomor SOP', 'Dasar Hukum', 'Kualifikasi Pelaksana', 'Keterkaitan', 'Peralatan/Perlengkapan', "
        "dan 'Peringatan' BUKAN TABEL PROSEDUR. Tulis bagian ini SEBAGAI TEKS BIASA ATAU DAFTAR (LIST) NORMAL. "
        "DILARANG KERAS menambahkan atribut 'Pelaksana', 'Kelengkapan', 'Waktu', atau 'Output' pada bagian ini!\n\n"

        "2. BAGIAN TABEL PROSEDUR (Uraian Prosedur / Langkah-langkah):\n"
        "HANYA UNTUK TABEL YANG MEMILIKI KOLOM 'Uraian Prosedur', 'Pelaksana', dan 'Mutu Baku', gunakan format ini PERSIS untuk setiap langkah:\n"
        "- <Nomor>. <Uraian Prosedur>\n"
        "  - Pelaksana: <nama jabatan yang ada centang/simbol di kolomnya>\n"
        "  - Kelengkapan: <isi kolom Kelengkapan>\n"
        "  - Waktu: <isi kolom Waktu>\n"
        "  - Output: <isi kolom Output>\n\n"

        "ATURAN TAMBAHAN:\n"
        "- Pelaksana ditentukan dari POSISI simbol flowchart (kotak/belah ketupat). Lihat simbol berada di bawah kolom jabatan mana.\n"
        "- Waktu dan Output adalah DUA kolom BERBEDA. JANGAN digabung. (Contoh BENAR: Waktu: 30 menit / Output: Disposisi).\n"
        "- HANYA keluarkan teks hasil ekstraksi, tanpa penjelasan atau komentar.\n"
    )
    
    payload = {
        "model": settings.VISION_MODEL_NAME,
        "prompt": prompt,
        "images": [img_base64],
        "stream": False,
        "options": {
            "num_ctx": 8192, 
            "num_predict": -1, 
            "temperature": 0.1
        }
    }
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=settings.VISION_TIMEOUT)
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            return _strip_garbage(raw)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt}/{retries}: Timeout/Error saat vision extract: {e}")
            
    return ""


def _clean_text_with_llm(dirty_text: str, retries: int = 2) -> str:
    """Menggunakan LLM untuk mengoreksi typo pada teks bebas hasil OCR/Vision."""
    if not dirty_text.strip():
        return dirty_text

    prompt = (
        "Anda adalah editor ahli bahasa. Koreksi typo dari teks OCR berikut tanpa merubah makna asli. "
        "Pertahankan struktur Markdown (seperti tabel, header). "
        "Keluarkan HANYA teks yang sudah diperbaiki.\n\n"
        f"{dirty_text}"
    )

    payload = {
        "model": settings.LLM_MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {"num_ctx": 4096, "num_predict": 2048, "temperature": 0.0, "top_p": 0.1},
    }
    url = f"{settings.OLLAMA_BASE_URL}/api/generate"

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            return _strip_garbage(raw)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Attempt {attempt}/{retries} LLM correction gagal: {e}")
            
    return dirty_text


def extract_text(file_path: str, page_num: int | None = None) -> list[dict]:
    """
    Mengekstrak teks dari seluruh halaman PDF.
    - Halaman teks: PyMuPDF langsung.
    - Halaman scan: Ekstrak menggunakan Ollama Vision Model secara umum.
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    pages_content: list[dict] = []

    try:
        doc = fitz.open(file_path)
        total_pages = len(doc)
        if page_num is not None:
            pages_to_process = [page_num]
            logger.info("Memproses PDF '%s' (hanya halaman %d)", file_path, page_num + 1)
        else:
            pages_to_process = list(range(total_pages))
            logger.info("Memproses PDF '%s' (%d halaman)", file_path, total_pages)

        for p_idx in pages_to_process:
            if p_idx >= total_pages:
                logger.warning(f"Halaman {p_idx + 1} di luar jangkauan (total {total_pages}).")
                continue
                
            page = doc[p_idx]
            text = _extract_text_from_page(page)

            # Jika teks terlalu sedikit, masuk ke vision pipeline
            if len(text) < _MIN_TEXT_LENGTH:
                logger.info(f"Halaman {p_idx + 1}: teks minim ({len(text)} karakter), memulai vision pipeline umum...")

                pixmap = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                img_base64 = base64.b64encode(pixmap.tobytes("png")).decode("utf-8")

                text = vision_extract_general(img_base64)

            if text:
                pages_content.append({
                    "page_number": p_idx + 1,
                    "text": text,
                })

        doc.close()
        logger.info("Berhasil mengekstrak teks dari %d/%d halaman PDF '%s'", len(pages_content), total_pages, file_path)
        return pages_content

    except Exception as e:
        logger.error("Gagal mengekstrak teks dari PDF '%s': %s", file_path, str(e))
        raise
