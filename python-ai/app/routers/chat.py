"""
Router untuk endpoint chat dengan SSE (Server-Sent Events) streaming.
Menyediakan RAG-based chat untuk menjawab pertanyaan pengguna
berdasarkan dokumen yang sudah diproses.
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.schemas import ChatRequest
from app.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
)


async def _stream_response(query: str, session_id: str) -> AsyncGenerator[str, None]:
    """
    Async generator yang membungkus generator sinkron dari rag_service.
    Menghasilkan data SSE dalam format JSON untuk setiap chunk respons.

    Args:
        query: Pertanyaan dari pengguna.
        session_id: ID sesi chat.

    Yields:
        String JSON berisi chunk respons atau metadata sumber.
    """
    try:
        import asyncio
        for chunk in rag_service.generate_response(
            query=query,
            session_id=session_id,
        ):
            # Kirim setiap chunk sebagai event SSE
            yield json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False)
            await asyncio.sleep(0.01) # Beri napas ke event loop agar bisa mengirim data ke frontend

        # Sinyal bahwa streaming selesai
        yield json.dumps({"type": "done", "content": ""}, ensure_ascii=False)

    except Exception as e:
        logger.error("Error saat streaming respons: %s", str(e))
        yield json.dumps(
            {"type": "error", "content": f"Terjadi kesalahan: {str(e)}"},
            ensure_ascii=False,
        )


@router.post(
    "/stream",
    summary="Chat dengan streaming SSE",
    description="Mengirim pertanyaan dan menerima jawaban secara streaming melalui SSE.",
)
async def chat_stream(request: ChatRequest) -> EventSourceResponse:
    """
    Endpoint chat dengan Server-Sent Events streaming.

    Menerima pertanyaan pengguna, melakukan pencarian di vector store,
    dan mengembalikan jawaban secara streaming menggunakan SSE.

    Returns:
        EventSourceResponse: Stream SSE berisi chunk-chunk jawaban.
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query tidak boleh kosong.",
        )

    logger.info(
        "Chat stream dimulai — session=%s, query='%s'",
        request.session_id,
        request.query[:100],  # Log hanya 100 karakter pertama
    )

    return EventSourceResponse(
        _stream_response(query=request.query, session_id=request.session_id),
        media_type="text/event-stream",
    )
