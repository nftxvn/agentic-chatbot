from app.services import pdf_processor
import asyncio
import sys
import logging
from app.services.pdf_processor import extract_text, detect_pdf_type

logging.basicConfig(level=logging.INFO)

def main():
    if len(sys.argv) < 2:
        print("Penggunaan: python test_pdf.py <path_ke_file_pdf>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    
    print(f"\n--- Menguji file: {pdf_path} ---")
    
    # 1. Tes deteksi tipe PDF
    try:
        pdf_type = detect_pdf_type(pdf_path)
        print(f"Hasil deteksi tipe PDF: {pdf_type}")
    except Exception as e:
        print(f"Error saat mendeteksi tipe PDF: {e}")
        return

    # 2. Tes ekstraksi teks (termasuk memanggil vision model jika halaman scan)
    try:
        print("\nSedang mengekstrak teks...")
        results = extract_text(pdf_path)
        
        print(f"\nBerhasil mengekstrak {len(results)} halaman.")
        for page in results:
            print(f"\n--- Halaman {page['page_number']} ---")
            print(page["text"])
            print("-" * 20)
            
    except Exception as e:
        print(f"Error saat mengekstrak teks: {e}")

if __name__ == "__main__":
    main()
