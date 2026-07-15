"""
Router untuk endpoint chat — streaming (SSE) dan non-streaming (WhatsApp).
Menyediakan RAG-based chat untuk menjawab pertanyaan pengguna
berdasarkan dokumen yang sudah diproses.
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatRequest,
    SourceReference,
)
from app.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/chat",
    tags=["Chat"],
)


# ── Dependency untuk autentikasi WhatsApp webhook ────────────────


async def verify_webhook_token(authorization: str = Header(...)) -> str:
    """
    Dependency untuk memverifikasi token webhook dari header Authorization.
    Format yang diharapkan: 'Bearer <token>'

    Raises:
        HTTPException: 401 jika token tidak valid.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format Authorization header tidak valid. Gunakan 'Bearer <token>'.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    if token != settings.INTERNAL_API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid. Akses ditolak.",
        )

    return token


# ── POST /api/chat/stream — Chat streaming via SSE ──────────────


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


# ── POST /api/chat/message — Chat non-streaming (WhatsApp) ──────


@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Chat non-streaming (WhatsApp)",
    description=(
        "Endpoint non-streaming untuk WhatsApp webhook. "
        "Menerima pesan, memproses pertanyaan, dan mengembalikan "
        "jawaban lengkap dalam satu respons JSON."
    ),
)
async def chat_message(
    request: ChatMessageRequest,
    _token: str = Depends(verify_webhook_token),
) -> ChatMessageResponse:
    """
    Endpoint chat non-streaming untuk WhatsApp Business API webhook.

    Menerima pesan dari pengguna WhatsApp, menjalankan RAG pipeline,
    dan mengembalikan jawaban lengkap beserta sumber referensi
    dalam satu respons JSON (karena WhatsApp tidak mendukung SSE).

    Returns:
        200 OK dengan jawaban lengkap dan daftar sumber dokumen.
    """
    if not request.message.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pesan tidak boleh kosong.",
        )

    logger.info(
        "Chat message (non-streaming) — phone=%s, message='%s'",
        request.phone_number,
        request.message[:100],
    )

    try:
        # Gunakan phone_number sebagai session_id untuk tracking
        session_id = f"wa-{request.phone_number}"

        # Kumpulkan seluruh respons dari generator
        reply_parts: list[str] = []
        sources: list[SourceReference] = []

        for chunk in rag_service.generate_response(
            query=request.message,
            session_id=session_id,
        ):
            # Pisahkan bagian sumber referensi dari jawaban utama
            if chunk.startswith("\n\n📚 **Sumber Referensi:**"):
                # Parse sumber dari teks referensi
                source_lines = chunk.strip().split("\n")
                for line in source_lines:
                    line = line.strip()
                    if line.startswith("- Dokumen #"):
                        # Format: "- Dokumen #12 — Halaman 45"
                        try:
                            parts = line.removeprefix("- Dokumen #").split(" — Halaman ")
                            doc_id = int(parts[0])
                            page_num = int(parts[1]) if len(parts) > 1 else None
                            sources.append(SourceReference(
                                document_id=doc_id,
                                page=page_num,
                            ))
                        except (ValueError, IndexError):
                            # Jika gagal parse, skip
                            pass
            else:
                reply_parts.append(chunk)

        reply_text = "".join(reply_parts).strip()

        if not reply_text:
            reply_text = "Maaf, saya tidak dapat memproses pertanyaan Anda saat ini."

        logger.info(
            "Respons non-streaming berhasil — phone=%s, panjang=%d karakter, sumber=%d",
            request.phone_number,
            len(reply_text),
            len(sources),
        )

        return ChatMessageResponse(
            reply=reply_text,
            sources=sources,
        )

    except Exception as e:
        logger.error(
            "Gagal memproses chat message (phone=%s): %s",
            request.phone_number,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal memproses pesan: {str(e)}",
        ) from e
