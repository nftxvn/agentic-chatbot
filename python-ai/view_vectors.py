"""
Script untuk melihat hasil vektor (embedding) berupa angka dari ChromaDB.
Menampilkan: ID, metadata, 10 angka pertama embedding, dan panjang total vektor.
"""
import sys
import os

# Tambah path agar bisa import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.embedding_service import get_chroma_collection

def view_vectors(limit: int = 5):
    collection = get_chroma_collection()

    # Ambil data DENGAN embeddings (include="embeddings")
    data = collection.get(
        include=["embeddings", "documents", "metadatas"],
        limit=limit,
    )

    ids        = data.get("ids", [])
    embeddings = data.get("embeddings", [])
    documents  = data.get("documents", [])
    metadatas  = data.get("metadatas", [])

    print(f"\nTotal dokumen di ChromaDB: {collection.count()}")
    print(f"Menampilkan {len(ids)} vektor pertama\n")
    print("=" * 70)

    for i, (doc_id, emb, doc, meta) in enumerate(zip(ids, embeddings, documents, metadatas), 1):
        dim = len(emb) if emb else 0
        print(f"[{i}] ID       : {doc_id}")
        print(f"    Halaman  : {meta.get('page_number', '?')} | Tipe: {meta.get('chunk_type', '?')}")
        print(f"    Teks     : {doc[:80].strip()}...")
        print(f"    Dimensi  : {dim} angka")
        if emb:
            # Tampilkan 10 angka pertama vektor
            preview = [round(x, 6) for x in emb[:10]]
            print(f"    Vektor   : {preview} ...")
        print("-" * 70)

if __name__ == "__main__":
    # Bisa ubah angka berikut untuk melihat lebih banyak vektor
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    view_vectors(limit=limit)
