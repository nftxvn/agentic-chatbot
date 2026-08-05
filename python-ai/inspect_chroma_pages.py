from app.services.embedding_service import get_chroma_collection
col = get_chroma_collection()
data = col.get(where={"document_id": 1}, include=["documents","metadatas"])
docs = data["documents"]
metas = data["metadatas"]

items = sorted(zip(docs, metas), key=lambda x: (x[1].get("page_number",0), x[1].get("chunk_index",0)))
for doc, meta in items:
    if meta.get("page_number") in [2,3,4,5] and meta.get("chunk_type") == "parent":
        print(f"--- Halaman {meta['page_number']} Chunk #{meta['chunk_index']} ---")
        print(doc[:2000])
        print()
