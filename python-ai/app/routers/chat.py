"""
Router untuk endpoint chat — streaming (SSE) dan non-streaming (WhatsApp).
Menyediakan RAG-based chat untuk menjawab pertanyaan pengguna
berdasarkan dokumen yang sudah diproses.
"""

import json
import logging
import secrets
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.database import get_document_names
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

# Pesan yang dikirim ke klien saat terjadi kesalahan tak terduga. Rinciannya
# sengaja ditahan di log server: pesan exception mentah kerap memuat path
# berkas, host basis data, atau potongan kredensial.
_ERROR_MESSAGE = (
    "Terjadi kesalahan saat memproses permintaan Anda. "
    "Silakan coba lagi; bila berulang, hubungi administrator."
)


# ── Dependency untuk autentikasi ─────────────────────────────────


def _assert_valid_bearer(authorization: str | None) -> str:
    """
    Memvalidasi header Authorization berformat 'Bearer <token>'.

    Raises:
        HTTPException: 401 bila header tidak ada, formatnya salah, atau
            tokennya tidak cocok.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Format Authorization header tidak valid. Gunakan 'Bearer <token>'.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    # compare_digest, bukan '==': lama pembandingannya tidak bergantung pada
    # berapa karakter awal yang cocok, sehingga token tidak bisa ditebak
    # karakter demi karakter lewat pengukuran waktu respons.
    if not secrets.compare_digest(token, settings.INTERNAL_API_TOKEN):
        logger.warning("Token tidak valid — akses ditolak")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid. Akses ditolak.",
        )

    return token


async def verify_webhook_token(authorization: str | None = Header(default=None)) -> str:
    """Dependency autentikasi untuk endpoint WhatsApp webhook."""
    return _assert_valid_bearer(authorization)


async def verify_chat_stream_token(
    authorization: str | None = Header(default=None),
) -> str | None:
    """
    Dependency autentikasi untuk /api/chat/stream.

    Bisa dimatikan lewat CHAT_STREAM_REQUIRE_AUTH=false untuk pengembangan
    lokal, karena React widget memanggil endpoint ini langsung dari browser.
    Di jaringan instansi penjagaan ini WAJIB aktif: tanpanya, siapa pun yang
    menjangkau port ini dapat menanyai seluruh isi dokumen yang sudah di-ingest.
    """
    if not settings.CHAT_STREAM_REQUIRE_AUTH:
        return None

    return _assert_valid_bearer(authorization)


# ── POST /api/chat/stream — Chat streaming via SSE ──────────────


async def _stream_response(
    query: str,
    session_id: str,
    document_ids: list[int] | None = None,
    system_prompt: str | None = None,
    temperature: float | None = None,
    top_k: int | None = None,
    include_debug: bool = False,
) -> AsyncGenerator[str, None]:
    """
    Async generator yang membungkus generator sinkron dari rag_service.
    Menghasilkan data SSE dalam format JSON untuk setiap chunk respons.

    Args:
        query: Pertanyaan dari pengguna.
        session_id: ID sesi chat.
        document_ids: Bila diisi, pencarian dibatasi hanya pada dokumen tersebut.
        system_prompt: Override system prompt untuk sandbox testing.
        temperature: Override temperature untuk sandbox testing.
        top_k: Override top_k untuk sandbox testing.
        include_debug: Sertakan metadata chunk debug di awal stream.

    Yields:
        String JSON berisi chunk respons, metadata debug, atau status selesai.
    """
    try:
        import asyncio
        for item in rag_service.generate_response(
            query=query,
            session_id=session_id,
            document_ids=document_ids,
            system_prompt_override=system_prompt,
            temperature_override=temperature,
            top_k_override=top_k,
            include_debug=include_debug,
        ):
            if isinstance(item, dict):
                yield json.dumps(item, ensure_ascii=False)
            else:
                # Kirim setiap chunk sebagai event SSE
                yield json.dumps({"type": "chunk", "content": item}, ensure_ascii=False)
            await asyncio.sleep(0.01) # Beri napas ke event loop agar bisa mengirim data ke frontend

        # Sinyal bahwa streaming selesai
        yield json.dumps({"type": "done", "content": ""}, ensure_ascii=False)

    except Exception:
        # exc_info=True: jejak lengkapnya masuk ke log server, satu-satunya
        # tempat yang tepat untuknya. Yang dikirim ke klien hanya pesan umum —
        # pesan exception mentah bisa memuat path berkas, host, atau kredensial.
        logger.error("Error saat streaming respons (session=%s)", session_id, exc_info=True)
        yield json.dumps(
            {"type": "error", "content": _ERROR_MESSAGE},
            ensure_ascii=False,
        )


@router.post(
    "/stream",
    summary="Chat dengan streaming SSE",
    description="Mengirim pertanyaan dan menerima jawaban secara streaming melalui SSE.",
)
async def chat_stream(
    request: ChatRequest,
    _token: str | None = Depends(verify_chat_stream_token),
) -> EventSourceResponse:
    """
    Endpoint chat dengan Server-Sent Events streaming.

    Menerima pertanyaan pengguna, melakukan pencarian di vector store,
    dan mengembalikan jawaban secara streaming menggunakan SSE.

    Butuh header `Authorization: Bearer <INTERNAL_API_TOKEN>` kecuali
    CHAT_STREAM_REQUIRE_AUTH=false disetel untuk pengembangan lokal.

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
        _stream_response(
            query=request.query,
            session_id=request.session_id,
            document_ids=request.document_ids,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            top_k=request.top_k,
            include_debug=request.include_debug,
        ),
        media_type="text/event-stream",
    )


# ── POST /api/chat/message — Chat non-streaming (WhatsApp) ──────


def _build_source_references(
    parsed_sources: list[tuple[int, int | None]],
) -> list[SourceReference]:
    """
    Melengkapi rujukan sumber dengan nama berkas aslinya.

    Nama diambil dari kolom `original_name` di tabel documents lewat satu query
    untuk seluruh dokumen yang dirujuk. Sebelumnya `doc_name` selalu null,
    sehingga pengguna WhatsApp hanya melihat nomor dokumen.

    Kegagalan basis data sengaja tidak dinaikkan: lebih baik pengguna menerima
    jawaban dengan rujukan bernomor daripada tidak menerima jawaban sama sekali.
    """
    if not parsed_sources:
        return []

    names: dict[int, str] = {}
    try:
        names = get_document_names(doc_id for doc_id, _ in parsed_sources)
    except Exception:
        logger.warning(
            "Gagal mengambil nama dokumen — doc_name dibiarkan kosong", exc_info=True
        )

    return [
        SourceReference(
            doc_name=names.get(doc_id),
            document_id=doc_id,
            page=page_num,
        )
        for doc_id, page_num in parsed_sources
    ]


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
        session_id = request.session_id or (f"wa-{request.phone_number}" if request.phone_number else "api-session")

        # Kumpulkan seluruh respons dari generator
        reply_parts: list[str] = []
        parsed_sources: list[tuple[int, int | None]] = []

        for chunk in rag_service.generate_response(
            query=request.message,
            session_id=session_id,
            document_ids=request.document_ids,
            system_prompt_override=request.system_prompt,
            temperature_override=request.temperature,
            top_k_override=request.top_k,
        ):
            # Pisahkan bagian sumber referensi dari jawaban utama
            if isinstance(chunk, str) and "Sumber Referensi" in chunk:
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
                            parsed_sources.append((doc_id, page_num))
                        except (ValueError, IndexError):
                            # Jika gagal parse, skip
                            pass
            else:
                reply_parts.append(chunk)

        sources = _build_source_references(parsed_sources)
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
            "Gagal memproses chat message (phone=%s)",
            request.phone_number,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=_ERROR_MESSAGE,
        ) from e
