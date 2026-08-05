import sys
from app.services.embedding_service import chunk_text, embed_and_store, delete_document_vectors
from app.services.rag_service import generate_response

def run_test():
    # 1. Baca teks hasil ekstraksi yang sudah sempurna
    file_path = "hasil_test_combined.md"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            markdown_text = f.read()
    except FileNotFoundError:
        print(f"File {file_path} tidak ditemukan. Silakan jalankan test_vision.py terlebih dahulu.")
        return

    print("="*60)
    print("1. MEMASUKKAN DATA KE CHROMADB")
    print("="*60)
    
    # Format data seperti yang dikembalikan oleh pdf_processor.py
    mock_pages = [
        {"page_number": 10, "text": markdown_text}
    ]

    # Hapus data lama jika ada (document_id 999)
    delete_document_vectors(999)

    # Chunking & Embedding
    chunks = chunk_text(mock_pages)
    stored_count = embed_and_store(document_id=999, chunks=chunks)
    print(f"-> Berhasil menyimpan {stored_count} vektor ke ChromaDB.\n")

    
    print("="*60)
    print("2. MENGUJI CHATBOT (RAG)")
    print("="*60)
    
    # Daftar pertanyaan test
    questions = [
        "Siapa yang bertanggung jawab untuk Menyusun Rencana Kerja 1 (satu) tahun beserta indikatornya?",
        "Berapa lama waktu yang dibutuhkan untuk Menghimpun, merangkai dan menyusun draf Renja?",
        "Apa output atau hasil dari kegiatan Melaksanakan rapat Penyusunan Renja?"
    ]

    session_id = "test-session-123"

    for i, q in enumerate(questions):
        print(f"\n[PERTANYAAN {i+1}]")
        print(f"User: {q}")
        print("Chatbot: ", end="", flush=True)
        
        # Stream response dari RAG
        for chunk in generate_response(q, session_id):
            try:
                print(chunk, end="", flush=True)
            except UnicodeEncodeError:
                print(chunk.encode('ascii', 'ignore').decode('ascii'), end="", flush=True)
        print("\n" + "-"*60)


if __name__ == "__main__":
    run_test()
