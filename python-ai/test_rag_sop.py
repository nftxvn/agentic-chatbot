"""
Test RAG end-to-end menggunakan PDF SOP Diskominfotik 2025.
Pipeline: PDF → ekstrak teks → chunking → embedding → ChromaDB → query → LLM → jawaban

Cara pakai:
    python test_rag_sop.py                  # semua fase
    python test_rag_sop.py --skip-ingest    # skip ekstraksi, langsung query (data sudah ada di ChromaDB)
"""

import sys
import logging
import argparse
from pathlib import Path

# ──────────────────────────────────────────────────────
# Logging
# ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test_rag_sop")

# ──────────────────────────────────────────────────────
# Konstanta
# ──────────────────────────────────────────────────────
PDF_PATH  = "test_files/SOP-diskominfotik 2025-1-10.pdf"
DOC_ID    = 1          # ID dokumen di ChromaDB
SESSION   = "test-rag-sop"

# Halaman yang akan di-ingest (None = semua halaman)
# Set ke list angka untuk ingest sebagian, misal: [7, 8, 9, 10]
PAGES_TO_INGEST = None

# ID dokumen lama yang perlu dibersihkan dari ChromaDB sebelum ingest
# (tambahkan semua doc_id lama agar tidak kontaminasi hasil retrieval)
DOC_IDS_TO_CLEAN = [1, 999]

# Daftar pertanyaan uji RAG — disesuaikan dengan konten PDF halaman 1-10
# (Keputusan Walikota + daftar nama SOP Diskominfotik 2025)
QUESTIONS = [
    "apa saja sop pada dinas komunikasi ,informatika dan statistik kota banda aceh?"
]


# ──────────────────────────────────────────────────────
# Fase 1: Ingest PDF ke ChromaDB
# ──────────────────────────────────────────────────────
def phase_ingest():
    from app.services.document_processor import detect_document_type, extract_document
    from app.services.embedding_service import (
        chunk_text_hierarchical, embed_and_store_hierarchical, delete_document_vectors
    )

    sep = "=" * 60
    print(f"\n{sep}")
    print("FASE 1 -- EKSTRAKSI & INGEST PDF KE CHROMADB")
    print(f"{sep}")

    if not Path(PDF_PATH).exists():
        print(f"[ERROR] File PDF tidak ditemukan: {PDF_PATH}")
        sys.exit(1)

    # Deteksi tipe PDF
    doc_type = detect_document_type(PDF_PATH)
    print(f"  Tipe dokumen   : {doc_type}")

    # Ekstrak teks
    print(f"  Mengekstrak teks dari PDF (halaman: {'semua' if PAGES_TO_INGEST is None else PAGES_TO_INGEST})...")
    pages = extract_document(PDF_PATH)

    if PAGES_TO_INGEST is not None:
        pages = [p for p in pages if p["page_number"] in PAGES_TO_INGEST]

    print(f"  Halaman berhasil diekstrak : {len(pages)}")

    if not pages:
        print("[WARNING] Tidak ada halaman yang diekstrak. Ingest dibatalkan.")
        return

    # Preview halaman pertama
    first = pages[0]
    preview = first["text"][:300].replace("\n", " ")
    print(f"  Preview halaman {first['page_number']} : {preview}...")

    # Hapus SEMUA dokumen lama (termasuk sisa dari test sebelumnya)
    total_deleted = 0
    for old_doc_id in DOC_IDS_TO_CLEAN:
        n = delete_document_vectors(old_doc_id)
        if n > 0:
            print(f"  Vektor lama doc #{old_doc_id} dihapus : {n}")
            total_deleted += n
    if total_deleted == 0:
        print("  Tidak ada vektor lama yang perlu dihapus")

    # Chunking Hierarchical
    parent_chunks, child_chunks = chunk_text_hierarchical(pages)
    print(f"  Total parent chunk : {len(parent_chunks)}")
    print(f"  Total child chunk  : {len(child_chunks)}")

    # Embed & store
    print("  Meng-embed dan menyimpan ke ChromaDB...")
    stored = embed_and_store_hierarchical(
        document_id=DOC_ID,
        parent_chunks=parent_chunks,
        child_chunks=child_chunks
    )
    print(f"  Vektor tersimpan: {stored} [OK]")


# ──────────────────────────────────────────────────────
# Fase 2: Query RAG
# ──────────────────────────────────────────────────────
def phase_query():
    from app.services.rag_service import generate_response

    sep = "=" * 60
    print(f"\n{sep}")
    print("FASE 2 -- UJI QUERY RAG")
    print(f"{sep}")

    results = []

    for i, question in enumerate(QUESTIONS, start=1):
        print(f"\n[PERTANYAAN {i}/{len(QUESTIONS)}]")
        print(f"User     : {question}")
        print(f"Chatbot  : ", end="", flush=True)

        full_answer = []
        try:
            for chunk in generate_response(question, SESSION):
                try:
                    print(chunk, end="", flush=True)
                except UnicodeEncodeError:
                    safe = chunk.encode("ascii", "ignore").decode("ascii")
                    print(safe, end="", flush=True)
                full_answer.append(chunk)
        except Exception as e:
            error_msg = f"[ERROR: {e}]"
            print(error_msg, end="")
            full_answer.append(error_msg)

        print()  # newline setelah jawaban
        print("-" * 60)
        results.append({
            "question": question,
            "answer": "".join(full_answer),
        })

    return results


# ──────────────────────────────────────────────────────
# Fase 3: Simpan hasil ke file
# ──────────────────────────────────────────────────────
def phase_save(results: list[dict]):
    output_path = "hasil_rag_sop.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Hasil Test RAG — SOP Diskominfotik 2025\n\n")
        f.write(f"**PDF**: `{PDF_PATH}`  \n")
        f.write(f"**Document ID**: {DOC_ID}  \n\n")
        f.write("---\n\n")
        for i, r in enumerate(results, start=1):
            f.write(f"## Pertanyaan {i}\n\n")
            f.write(f"**Q:** {r['question']}\n\n")
            f.write(f"**A:**\n\n{r['answer']}\n\n")
            f.write("---\n\n")
    print(f"\n[OK] Hasil disimpan ke: {output_path}")


# ──────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────
# Fase 0: Bersihkan ChromaDB (opsional)
# ──────────────────────────────────────────────────────
def phase_clean():
    from app.services.embedding_service import delete_document_vectors
    print("\n[CLEAN] Membersihkan ChromaDB dari dokumen lama...")
    total = 0
    for doc_id in DOC_IDS_TO_CLEAN:
        n = delete_document_vectors(doc_id)
        if n > 0:
            print(f"  Doc #{doc_id}: {n} vektor dihapus")
            total += n
    print(f"  Total dihapus: {total} vektor [OK]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test RAG pipeline untuk SOP PDF")
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        help="Lewati fase ingest (gunakan data ChromaDB yang sudah ada)",
    )
    parser.add_argument(
        "--ingest-only",
        action="store_true",
        help="Hanya jalankan fase ingest, tanpa query",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Hapus semua vektor lama dari ChromaDB (DOC_IDS_TO_CLEAN) tanpa re-ingest",
    )
    parser.add_argument(
        "--page",
        type=int,
        default=None,
        metavar="N",
        help="Ingest hanya halaman N (1-indexed). Contoh: --page 3",
    )
    args = parser.parse_args()

    if args.clean:
        phase_clean()
    elif not args.skip_ingest:
        # Override PAGES_TO_INGEST jika --page diberikan
        if args.page is not None:
            import app.services.document_processor  # noqa: pastikan import bisa
            # Patch global sementara
           
            PAGES_TO_INGEST = [args.page]
            print(f"[INFO] Mode 1 halaman: hanya memproses halaman {args.page}")
        phase_ingest()

    if not args.ingest_only and not args.clean:
        results = phase_query()
        phase_save(results)

