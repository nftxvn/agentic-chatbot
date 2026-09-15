import logging
import re
from pathlib import Path
from typing import Callable
import pandas as pd
import docx

from app.services import pdf_processor

logger = logging.getLogger(__name__)


def _sanitize_text(text: str) -> str:
    """
    Sanitasi teks hasil ekstraksi untuk menjamin integritas data dan keamanan:
    - Menghapus null bytes (\x00) yang dapat merusak database / embedding tokenizer.
    - Menghapus karakter kontrol berbahaya (kecuali \n, \r, \t).
    - Menormalkan spasi berlebih.
    """
    if not text:
        return ""
    # Hapus null bytes
    cleaned = text.replace("\x00", "")
    # Hapus karakter kontrol ASCII 0x01-0x08, 0x0B-0x0C, 0x0E-0x1F, dan 0x7F
    cleaned = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    return cleaned.strip()


def get_total_pages(file_path: str) -> int:
    """
    Menghitung total halaman / lembar dokumen tanpa mengekstrak seluruh teks.
    """
    try:
        resolved = pdf_processor._resolve_pdf_path(file_path)
    except FileNotFoundError:
        return 1

    path = Path(resolved)
    ext = path.suffix.lower()
    if ext == ".pdf":
        try:
            import fitz
            with fitz.open(resolved) as doc:
                return len(doc)
        except Exception:
            return 1
    elif ext in [".xlsx", ".xls"]:
        try:
            dfs = pd.read_excel(resolved, sheet_name=None)
            return max(len(dfs), 1)
        except Exception:
            return 1
    return 1


def extract_document(
    file_path: str,
    page_num: int | None = None,
    progress_callback: Callable | None = None,
) -> list[dict]:
    """
    Ekstrak konten dari berbagai jenis file.
    Mendukung PDF, DOCX, XLSX, XLS, CSV, TXT, MD, PNG, JPG, JPEG.
    """
    resolved = pdf_processor._resolve_pdf_path(file_path)
    path = Path(resolved)
    ext = path.suffix.lower()
    
    if ext == ".pdf":
        return pdf_processor.extract_text(resolved, page_num, progress_callback)
    elif ext == ".docx":
        return _extract_docx(resolved)
    elif ext in [".xlsx", ".xls"]:
        return _extract_excel(resolved)
    elif ext == ".csv":
        return _extract_csv(resolved)
    elif ext in [".txt", ".md"]:
        return _extract_text_file(resolved)
    elif ext in [".png", ".jpg", ".jpeg"]:
        return _extract_image(resolved)
    else:
        raise ValueError(f"Tipe file '{ext}' belum didukung.")


def detect_document_type(file_path: str) -> str:
    try:
        resolved = pdf_processor._resolve_pdf_path(file_path)
    except FileNotFoundError:
        resolved = file_path

    path = Path(resolved)
    ext = path.suffix.lower()
    
    if ext == ".pdf":
        return pdf_processor.detect_pdf_type(resolved)
    elif ext in [".docx", ".txt", ".md"]:
        return "text"
    elif ext in [".xlsx", ".xls", ".csv"]:
        return "spreadsheet"
    elif ext in [".png", ".jpg", ".jpeg"]:
        return "image"
    else:
        return "unknown"


def _extract_docx(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file DOCX: %s", file_path)
    doc = docx.Document(file_path)
    
    content = []
    
    # Ekstrak paragraf
    for para in doc.paragraphs:
        cleaned_p = _sanitize_text(para.text)
        if cleaned_p:
            content.append(cleaned_p)
            
    # Ekstrak tabel jika ada
    if doc.tables:
        content.append("\n## Tabel\n")
        for i, table in enumerate(doc.tables):
            content.append(f"### Tabel {i+1}")
            for row in table.rows:
                row_data = [_sanitize_text(cell.text).replace('\n', ' ') for cell in row.cells]
                content.append(" | ".join(row_data))
            content.append("\n")
            
    full_text = _sanitize_text("\n\n".join(content))
    return [{"page_number": 1, "text": full_text}]


def _extract_excel(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file EXCEL: %s", file_path)
    dfs = pd.read_excel(file_path, sheet_name=None)
    content = []
    
    for sheet_name, df in dfs.items():
        # Isi NaN dengan string kosong agar tabel rapi
        df_clean = df.fillna("")
        content.append(f"## Sheet: {sheet_name}\n")
        content.append(df_clean.to_markdown(index=False))
        content.append("\n")
        
    full_text = _sanitize_text("\n".join(content))
    return [{"page_number": 1, "text": full_text}]


def _extract_csv(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file CSV: %s", file_path)
    try:
        df = pd.read_csv(file_path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="latin-1")
    df_clean = df.fillna("")
    full_text = _sanitize_text(df_clean.to_markdown(index=False))
    return [{"page_number": 1, "text": full_text}]


def _extract_text_file(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file TEKS: %s", file_path)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1", errors="replace") as f:
            text = f.read()
    return [{"page_number": 1, "text": _sanitize_text(text)}]


def _extract_image(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file GAMBAR: %s", file_path)
    import base64
    from app.services.pdf_processor import vision_extract_general
    
    with open(file_path, "rb") as image_file:
        img_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        
    text = vision_extract_general(img_base64)
    return [{"page_number": 1, "text": _sanitize_text(text)}]
