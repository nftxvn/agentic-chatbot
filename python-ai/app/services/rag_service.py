"""
Service RAG (Retrieval-Augmented Generation).
Melakukan pencarian konteks di ChromaDB dan menghasilkan jawaban
menggunakan LLM Ollama secara streaming.
"""

import logging
from typing import Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.services.embedding_service import get_chroma_collection, get_embedding_model

logger = logging.getLogger(__name__)

# Jumlah dokumen konteks yang diambil dari vector store
_TOP_K = 5

# System prompt untuk LLM — instruksi perilaku model
_SYSTEM_PROMPT = """Kamu adalah asisten IT Support yang cerdas dan membantu.
Tugas utamamu adalah menjawab pertanyaan pengguna HANYA berdasarkan konteks dokumen yang diberikan.

ATURAN KETAT:
1. Jawab HANYA berdasarkan informasi yang ada di dalam konteks dokumen di bawah.
2. Selalu jawab dalam Bahasa Indonesia.
3. Jika kamu menemukan jawabannya, sebutkan sumber dokumen (nomor halaman) yang relevan.
4. Jika konteks tidak mengandung informasi yang relevan, jawab dengan:
   "Maaf, saya tidak menemukan informasi tersebut di dokumen yang tersedia."
5. Jangan mengarang atau berasumsi di luar konteks yang diberikan.
6. Berikan jawaban yang jelas, terstruktur, dan mudah dipahami.
7. Gunakan poin-poin atau langkah-langkah jika diperlukan untuk kejelasan.

KONTEKS DOKUMEN:
{context}

SUMBER DOKUMEN YANG TERSEDIA:
{sources}
"""


def _retrieve_context(query: str) -> tuple[str, str]:
    """
    Melakukan pencarian similarity di ChromaDB berdasarkan query pengguna.

    Args:
        query: Pertanyaan dari pengguna.

    Returns:
        Tuple berisi (context_text, sources_text):
        - context_text: Gabungan teks dari dokumen yang relevan.
        - sources_text: Informasi sumber dokumen (document_id, halaman).
    """
    model = get_embedding_model()
    collection = get_chroma_collection()

    try:
        # Generate embedding untuk query
        query_embedding = model.encode(query).tolist()

        # Cari dokumen yang paling mirip
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=_TOP_K,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            logger.info("Tidak ada dokumen relevan ditemukan untuk query: '%s'", query[:80])
            return "", ""

        # Bangun teks konteks dan sumber
        context_parts: list[str] = []
        sources_set: set[str] = set()

        for i, (doc_text, metadata, distance) in enumerate(
            zip(documents, metadatas, distances)
        ):
            doc_id = metadata.get("document_id", "?")
            page_num = metadata.get("page_number", "?")
            similarity = 1 - distance  # ChromaDB cosine distance -> similarity

            context_parts.append(
                f"[Sumber: Dokumen #{doc_id}, Halaman {page_num} "
                f"(relevansi: {similarity:.2%})]\n{doc_text}"
            )
            sources_set.add(f"Dokumen #{doc_id} — Halaman {page_num}")

        context_text = "\n\n---\n\n".join(context_parts)
        sources_text = "\n".join(f"- {s}" for s in sorted(sources_set))

        logger.info(
            "Ditemukan %d konteks relevan untuk query (similarity terbaik: %.2f%%)",
            len(documents),
            (1 - distances[0]) * 100 if distances else 0,
        )

        return context_text, sources_text

    except Exception as e:
        logger.error("Gagal melakukan pencarian konteks: %s", str(e))
        return "", ""


def generate_response(query: str, session_id: str) -> Generator[str, None, None]:
    """
    Menghasilkan respons RAG secara streaming.

    Langkah-langkah:
    1. Cari konteks relevan di ChromaDB.
    2. Bangun prompt dengan konteks.
    3. Panggil LLM Ollama dan stream hasilnya.
    4. Sertakan referensi sumber di akhir.

    Args:
        query: Pertanyaan dari pengguna.
        session_id: ID sesi chat (untuk logging dan tracking).

    Yields:
        String berisi chunk-chunk respons dari LLM.
    """
    logger.info(
        "Memulai generate response — session=%s, query='%s'",
        session_id,
        query[:80],
    )

    try:
        # Langkah 1: Ambil konteks dari vector store
        context_text, sources_text = _retrieve_context(query)

        # Langkah 2: Bangun prompt dengan konteks
        if not context_text:
            # Tidak ada konteks, langsung beri tahu pengguna
            yield "Maaf, saya tidak menemukan informasi tersebut di dokumen yang tersedia."
            return

        system_prompt = _SYSTEM_PROMPT.format(
            context=context_text,
            sources=sources_text,
        )

        # Langkah 3: Inisialisasi LLM dan stream respons
        llm = ChatOllama(
            model=settings.LLM_MODEL_NAME,
            base_url=settings.OLLAMA_BASE_URL,
            temperature=0.1,  # Suhu rendah untuk jawaban yang lebih akurat
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query),
        ]

        # Stream respons dari LLM
        for chunk in llm.stream(messages):
            if chunk.content:
                yield chunk.content

        # Langkah 4: Tambahkan referensi sumber di akhir
        if sources_text:
            yield f"\n\n📚 **Sumber Referensi:**\n{sources_text}"

        logger.info("Respons berhasil di-generate untuk session %s", session_id)

    except Exception as e:
        logger.error(
            "Gagal generate respons (session=%s): %s",
            session_id,
            str(e),
        )
        yield f"\n\n⚠️ Terjadi kesalahan saat memproses pertanyaan Anda: {str(e)}"
