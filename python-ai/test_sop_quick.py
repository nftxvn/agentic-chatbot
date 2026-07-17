"""
Test cepat PDF SOP Diskominfotik - hanya 5 halaman pertama.
Menampilkan: tipe PDF, hasil ekstraksi teks per halaman.
"""
import sys
import logging
import fitz  # PyMuPDF

# Setup logging supaya bisa lihat proses Vision Model
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Tambahkan path agar bisa import app
sys.path.insert(0, ".")

from app.services.pdf_processor import detect_pdf_type, _extract_text_from_page, _vision_extract_page

PDF_PATH = r"test_files\SOP-diskominfotik-2025.pdf"
MAX_PAGES = 5  # Hanya test 5 halaman pertama

print("=" * 60)
print("  TEST PDF: SOP Diskominfotik 2025")
print("=" * 60)

# --- 1. Deteksi tipe PDF ---
print("\n[1] Mendeteksi tipe PDF...")
pdf_type = detect_pdf_type(PDF_PATH)
print(f"    Tipe PDF: {pdf_type.upper()}")

# --- 2. Ekstraksi per halaman (5 halaman pertama) ---
doc = fitz.open(PDF_PATH)
total_pages = len(doc)
print(f"\n[2] Total halaman: {total_pages}")
print(f"    Menguji {MAX_PAGES} halaman pertama...\n")

for i in range(min(MAX_PAGES, total_pages)):
    page = doc[i]
    page_num = i + 1
    text = _extract_text_from_page(page)

    print(f"{'=' * 60}")
    print(f"  Halaman {page_num}")
    print(f"{'=' * 60}")

    if len(text) >= 30:
        # Halaman teks biasa
        print(f"  [TEKS BIASA] {len(text)} karakter")
        print(f"  Preview: {text[:200].replace(chr(10), ' ')}...")
    else:
        # Halaman scan -> pakai Vision Model
        print(f"  [SCAN/GAMBAR] Teks hanya {len(text)} karakter -> Vision Model...")
        vision_text = _vision_extract_page(page, retries=1)
        if vision_text:
            print(f"  [VISION OK] {len(vision_text)} karakter diekstrak")
            print(f"  Preview: {vision_text[:200].replace(chr(10), ' ')}...")
        else:
            print(f"  [VISION GAGAL] Tidak ada teks yang bisa dibaca")

doc.close()
print(f"\n{'=' * 60}")
print("  TEST SELESAI")
print(f"{'=' * 60}")
