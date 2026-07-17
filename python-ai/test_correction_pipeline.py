import sys
import logging
import fitz  # PyMuPDF

# Setup logging supaya bisa lihat proses Vision Model & LLM Correction
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Tambahkan path agar bisa import app
sys.path.insert(0, ".")

from app.services.pdf_processor import _extract_text_from_page, _vision_extract_page, _clean_text_with_llm

PDF_PATH = r"test_files\SOP-diskominfotik-2025.pdf"
TARGET_PAGE = 55  # Halaman 16 (index 15)

print("=" * 60)
print(f"  TEST PIPELINE LENGKAP: Halaman {TARGET_PAGE}")
print("=" * 60)

doc = fitz.open(PDF_PATH)
page = doc[TARGET_PAGE - 1]
text = _extract_text_from_page(page)

print(f"\n{'=' * 60}")
print(f"  Ekstraksi PyMuPDF")
print(f"{'=' * 60}")

if len(text) >= 30:
    print(f"  [TEKS BIASA] {len(text)} karakter. Tidak perlu Vision & Koreksi.")
else:
    print(f"  [SCAN/GAMBAR] Teks hanya {len(text)} karakter -> Memanggil Vision Model...")
    vision_text = _vision_extract_page(page, retries=1)
    
    if vision_text:
        print(f"\n  [VISION OK] {len(vision_text)} karakter diekstrak.")
        print("  Mengirim teks kotor ke LLM (Qwen) untuk dikoreksi...")
        
        # Panggil fungsi koreksi yang baru kita buat!
        clean_text = _clean_text_with_llm(vision_text, retries=1)
        
        print("\n=== TEKS KOTOR (VISION) ===")
        print(vision_text + "\n")
        
        print("\n=== TEKS BERSIH (KOREKSI LLM) ===")
        print(clean_text + "\n")
        
    else:
        print(f"  [VISION GAGAL] Tidak ada teks yang bisa diekstrak dari gambar.")

doc.close()
print(f"\n{'=' * 60}")
print("  TEST SELESAI")
print(f"{'=' * 60}")
