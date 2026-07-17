"""
Test cepat PDF SOP Diskominfotik - spesifik Halaman 16.
"""
import sys
import logging
import fitz  # PyMuPDF

# Setup logging supaya bisa lihat proses Vision Model
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Tambahkan path agar bisa import app
sys.path.insert(0, ".")

from app.services.pdf_processor import _extract_text_from_page, _vision_extract_page

PDF_PATH = r"test_files\SOP-diskominfotik-2025.pdf"
TARGET_PAGE = 16  # Halaman 16 (index 15)

print("=" * 60)
print(f"  TEST PDF: SOP Diskominfotik 2025 - Halaman {TARGET_PAGE}")
print("=" * 60)

doc = fitz.open(PDF_PATH)
total_pages = len(doc)

if TARGET_PAGE > total_pages:
    print(f"Error: Dokumen hanya memiliki {total_pages} halaman.")
    sys.exit(1)

# PyMuPDF menggunakan index 0 untuk halaman 1
page = doc[TARGET_PAGE - 1]
text = _extract_text_from_page(page)

print(f"\n{'=' * 60}")
print(f"  Halaman {TARGET_PAGE}")
print(f"{'=' * 60}")

if len(text) >= 30:
    # Halaman teks biasa
    print(f"  [TEKS BIASA] {len(text)} karakter")
    print(f"  Preview: {text[:500].replace(chr(10), ' ')}...")
else:
    # Halaman scan -> pakai Vision Model
    print(f"  [SCAN/GAMBAR] Teks hanya {len(text)} karakter -> Vision Model...")
    vision_text = _vision_extract_page(page, retries=1)
    if vision_text:
        print(f"  [VISION OK] {len(vision_text)} karakter diekstrak")
        print(f"  Hasil Ekstraksi Penuh:\n\n{vision_text}")
    else:
        print(f"  [VISION GAGAL] Tidak ada teks yang bisa dibaca")

doc.close()
print(f"\n{'=' * 60}")
print("  TEST SELESAI")
print(f"{'=' * 60}")
