"""Titik masuk kompatibel untuk embedding, chunking, dan penyimpanan vektor.

Implementasi berada di embeddings.models, chunking, corpus, dan vector_store.
Model/reranker serta koleksi ChromaDB tetap memiliki satu pemilik state;
mengimpor modul ini tidak memuat model atau membuka koleksi.
"""

# Pertahankan pembacaan konfigurasi sebelum dependency model diimpor.
from app.config import settings

from app.services.embeddings.models import (
    _EMBEDDING_DEVICE,
    get_embedding_model,
    _get_available_ollama_models,
    _encode_via_ollama,
    encode_texts,
    encode_query,
    get_reranker_model,
)
from app.services.embeddings.chunking import (
    _PARENT_CHUNK_SIZE,
    _PARENT_CHUNK_OVERLAP,
    _CHILD_CHUNK_SIZE,
    _CHILD_CHUNK_OVERLAP,
    _DOC_TITLE_MAX_LEN,
    derive_document_title,
    _list_item_boundary,
    _LIST_ITEM_THRESHOLD,
    _LIST_BLOCK_HARD_CAP,
    _split_list_preserving_items,
    _POLA_NAMA_SOP,
    _POLA_PENANDA_BAGIAN,
    _POLA_BARIS_KAPITAL,
    _MAKS_BARIS_KEPALA,
    _MAKS_KATA_PENANDA,
    _MIN_PORSI_PENANDA,
    derive_page_context,
    chunk_text_hierarchical,
)
from app.services.embeddings.corpus import (
    _CORPUS_VERSION_FILE,
    _corpus_version_path,
    read_corpus_version,
    bump_corpus_version,
    _invalidate_search_index,
)
from app.services.embeddings.vector_store import (
    _COLLECTION_NAME,
    get_chroma_collection,
    delete_document_vectors,
    get_document_chunks,
    embed_and_store_hierarchical,
)
