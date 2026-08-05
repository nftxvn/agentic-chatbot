import sys
import json
from app.services.pdf_processor import extract_text

def test_pdf():
    pdf_path = "test_files/SOP-diskominfotik 2025-1-10.pdf"
    
    page_num = None
    if len(sys.argv) > 1:
        # User menginput halaman berbasis 1-index (contoh: '9' untuk Halaman 9)
        # di pdf_processor.py page_num berbasis 0-index.
        page_num = int(sys.argv[1]) - 1

    if page_num is not None:
        print(f"Menguji pdf_processor.extract_text() pada file: {pdf_path} (Halaman {page_num + 1})")
    else:
        print(f"Menguji pdf_processor.extract_text() pada file: {pdf_path} (Semua Halaman)")
    
    try:
        pages = extract_text(pdf_path, page_num=page_num)
        
        output_file = "hasil_test_pipeline.md"
        with open(output_file, "w", encoding="utf-8") as f:
            for page in pages:
                f.write(f"\n\n# Halaman {page['page_number']}\n\n")
                f.write(page['text'])
                
        print("="*50)
        print(f"SELESAI! Hasil telah disimpan ke dalam file: {output_file}")
        print("="*50)
        
    except Exception as e:
        import traceback
        print(f"Terjadi kesalahan: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_pdf()
