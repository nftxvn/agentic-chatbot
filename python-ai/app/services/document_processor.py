import logging
from pathlib import Path
import pandas as pd
import docx

from app.services import pdf_processor

logger = logging.getLogger(__name__)

def extract_document(file_path: str, page_num: int | None = None) -> list[dict]:
    """
    Ekstrak konten dari berbagai jenis file.
    Mendukung PDF, DOCX, XLSX, XLS, CSV, TXT, MD, PNG, JPG, JPEG.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")
        
    ext = path.suffix.lower()
    
    if ext == ".pdf":
        return pdf_processor.extract_text(file_path, page_num)
    elif ext == ".docx":
        return _extract_docx(file_path)
    elif ext in [".xlsx", ".xls"]:
        return _extract_excel(file_path)
    elif ext == ".csv":
        return _extract_csv(file_path)
    elif ext in [".txt", ".md"]:
        return _extract_text_file(file_path)
    elif ext in [".png", ".jpg", ".jpeg"]:
        return _extract_image(file_path)
    else:
        raise ValueError(f"Tipe file '{ext}' belum didukung.")

def detect_document_type(file_path: str) -> str:
    path = Path(file_path)
    ext = path.suffix.lower()
    
    if ext == ".pdf":
        return pdf_processor.detect_pdf_type(file_path)
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
        if para.text.strip():
            content.append(para.text.strip())
            
    # Ekstrak tabel jika ada
    if doc.tables:
        content.append("\n## Tabel\n")
        for i, table in enumerate(doc.tables):
            content.append(f"### Tabel {i+1}")
            for row in table.rows:
                row_data = [cell.text.strip().replace('\n', ' ') for cell in row.cells]
                content.append(" | ".join(row_data))
            content.append("\n")
            
    return [{"page_number": 1, "text": "\n\n".join(content)}]

def _extract_excel(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file EXCEL: %s", file_path)
    dfs = pd.read_excel(file_path, sheet_name=None)
    content = []
    
    for sheet_name, df in dfs.items():
        content.append(f"## Sheet: {sheet_name}\n")
        content.append(df.to_markdown(index=False))
        content.append("\n")
        
    return [{"page_number": 1, "text": "\n".join(content)}]

def _extract_csv(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file CSV: %s", file_path)
    df = pd.read_csv(file_path)
    return [{"page_number": 1, "text": df.to_markdown(index=False)}]

def _extract_text_file(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file TEKS: %s", file_path)
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()
    return [{"page_number": 1, "text": text}]

def _extract_image(file_path: str) -> list[dict]:
    logger.info("Mengekstrak file GAMBAR: %s", file_path)
    import base64
    from app.services.pdf_processor import vision_extract_general
    
    with open(file_path, "rb") as image_file:
        img_base64 = base64.b64encode(image_file.read()).decode("utf-8")
        
    text = vision_extract_general(img_base64)
    return [{"page_number": 1, "text": text}]
