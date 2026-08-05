"""
Script untuk memperbarui teks chunk di ChromaDB dengan menambahkan header
[Konteks: SOP ...] tanpa perlu re-OCR.

Cara kerja:
1. Ambil semua parent chunk dari ChromaDB untuk doc_id tertentu.
2. Deteksi NAMA SOP dari teks tiap chunk.
3. Tambahkan header [Konteks: SOP ...] ke teks jika belum ada.
4. Upsert kembali ke ChromaDB.

Cara pakai:
    python patch_chroma_context.py
"""

import logging
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("patch_chroma_context")

DOC_ID = 1  # Ubah sesuai document_id yang ingin dipatch


def patch():
    from app.services.embedding_service import get_chroma_collection, get_embedding_model

    collection = get_chroma_collection()
    model = get_embedding_model()

    # Ambil semua chunk untuk doc_id ini
    data = collection.get(
        where={"document_id": DOC_ID},
        include=["documents", "metadatas"],
    )
    ids = data["ids"]
    docs = data["documents"]
    metas = data["metadatas"]

    logger.info("Total chunk ditemukan untuk doc #%d: %d", DOC_ID, len(ids))

    # Pola deteksi NAMA SOP (fleksibel)
    sop_name_pattern = re.compile(
        r"(?:(?:-\s*\*\*)?NAMA\s+SOP(?:\*\*)?\s*:\s*)(.+)",
        re.IGNORECASE,
    )
    context_already_pattern = re.compile(r"\[Konteks: SOP .+?\]")

    current_sop_name = None
    current_sop_page = None

    # ── Tahap 1: Scan semua chunk untuk menemukan semua NAMA SOP
    # (urutkan berdasarkan halaman, lalu chunk_index)
    sorted_items = sorted(
        zip(ids, docs, metas),
        key=lambda x: (int(x[2].get("page_number", 0)), int(x[2].get("chunk_index", 0))),
    )

    # Temukan nama SOP per range halaman
    sop_map: list[tuple[int, str]] = []  # [(page_number, sop_name)]
    for _, doc_text, meta in sorted_items:
        match = sop_name_pattern.search(doc_text)
        if match:
            sop_name = match.group(1).strip()
            sop_name = re.sub(r"\*+", "", sop_name).strip()
            page = int(meta.get("page_number", 0))
            sop_map.append((page, sop_name))
            logger.info("SOP ditemukan di halaman %d: '%s'", page, sop_name)

    if not sop_map:
        logger.warning("Tidak ada NAMA SOP ditemukan di chunk! Patch dibatalkan.")
        return

    def get_sop_for_page(page_num: int) -> str | None:
        """Mengembalikan nama SOP yang berlaku untuk halaman tertentu."""
        applicable = None
        for p, name in sop_map:
            if p <= page_num:
                applicable = name
            else:
                break
        return applicable

    # ── Tahap 2: Patch setiap chunk
    to_patch_ids = []
    to_patch_docs = []
    to_patch_metas = []
    to_patch_embeddings = []

    for chunk_id, doc_text, meta in sorted_items:
        page = int(meta.get("page_number", 0))
        sop_name = get_sop_for_page(page)

        if not sop_name:
            logger.debug("Chunk %s (hal %d): tidak ada SOP — skip", chunk_id, page)
            continue

        # Cek apakah header konteks sudah ada
        if context_already_pattern.search(doc_text):
            logger.debug("Chunk %s (hal %d): sudah ada [Konteks] — skip", chunk_id, page)
            continue

        # Sisipkan header setelah baris [Halaman X]
        if doc_text.startswith("[Halaman"):
            first_newline = doc_text.index("\n")
            new_text = (
                doc_text[: first_newline + 1]
                + f"[Konteks: SOP {sop_name}]\n"
                + doc_text[first_newline + 1 :]
            )
        else:
            new_text = f"[Konteks: SOP {sop_name}]\n{doc_text}"

        to_patch_ids.append(chunk_id)
        to_patch_docs.append(new_text)
        to_patch_metas.append(meta)

    logger.info("Total chunk yang perlu dipatch: %d", len(to_patch_ids))

    if not to_patch_ids:
        logger.info("Tidak ada yang perlu dipatch.")
        return

    # Re-embed teks yang sudah dipatch
    logger.info("Menghasilkan embedding baru untuk %d chunk...", len(to_patch_ids))
    new_embeddings = model.encode(to_patch_docs, show_progress_bar=True).tolist()

    # Upsert ke ChromaDB
    batch_size = 100
    for i in range(0, len(to_patch_ids), batch_size):
        end = min(i + batch_size, len(to_patch_ids))
        collection.upsert(
            ids=to_patch_ids[i:end],
            documents=to_patch_docs[i:end],
            metadatas=to_patch_metas[i:end],
            embeddings=new_embeddings[i:end],
        )
        logger.info("Batch %d-%d selesai di-upsert", i, end)

    logger.info("Patch selesai! %d chunk berhasil diperbarui.", len(to_patch_ids))

    # Preview hasil
    print("\n=== Contoh chunk setelah patch ===")
    for chunk_id, doc in zip(to_patch_ids[:3], to_patch_docs[:3]):
        print(f"\n[{chunk_id}]")
        print(doc[:400])
        print("---")


if __name__ == "__main__":
    patch()
