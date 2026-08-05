from app.services.embedding_service import get_chroma_collection

col = get_chroma_collection()
data = col.get(where={"document_id": 1}, include=["documents", "metadatas"])

for doc, meta in zip(data["documents"], data["metadatas"]):
    if meta.get("page_number") == 8 and meta.get("chunk_type") == "parent":
        print(f"--- Halaman 8 (Renstra steps) ---")
        print(doc)
        print()
