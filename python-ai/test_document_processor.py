import sys
import json
from app.services.document_processor import detect_document_type, extract_document

def test_file(path, out_file, page_num=None):
    print(f"--- Testing {path} ---")
    try:
        doc_type = detect_document_type(path)
        print(f"Detected Type: {doc_type}")
        
        pages = extract_document(path, page_num=page_num)
        print(f"Extracted {len(pages)} pages/parts.")
        
        with open(out_file, "w", encoding="utf-8") as f:
            for i, p in enumerate(pages):
                f.write(f"## Bagian {i+1} (Halaman {p.get('page_number', '?')})\n\n")
                f.write(p['text'])
                f.write("\n\n---\n\n")
                
        print(f"Sukses! Hasil ekstraksi disimpan ke {out_file}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    target = "test_files/SOP_diskominfotik_2025.pdf"
    output = "hasil_ekstraksi_sop.md"
    
    # Ambil argumen halaman (0-indexed) dari argumen terminal, jika tidak ada default None
    # Halaman 1 = 0, Halaman 2 = 1, dst.
    page_to_test = int(sys.argv[1]) if len(sys.argv) > 1 else None
    
    if page_to_test is not None:
        print(f"Mencoba ekstrak hanya Halaman {page_to_test + 1}...")
        
    test_file(target, output, page_num=page_to_test)
