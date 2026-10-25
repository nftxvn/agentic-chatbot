"""Streaming Ollama dengan riwayat terbatas dan satu fallback alokasi memori.

Estimasi token hanya untuk telemetri. Jendela aktif tetap memakai konfigurasi
database atau LLM_NUM_CTX; retry ke 4096 hanya sebelum konten terkirim.
"""

import logging
import math
from typing import Generator

from langchain_ollama import ChatOllama
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.config import settings

logger = logging.getLogger("app.services.rag_service")

_CHARS_PER_TOKEN = 3.0

_NUM_CTX_RESPONSE_HEADROOM = 2048

_NUM_CTX_FALLBACK = 4096

_OLLAMA_TIMEOUT = 300

_OLLAMA_KEEP_ALIVE = "30m"

_NUM_GPU = settings.LLM_NUM_GPU or None



# ─────────────────────────────────────────────────────────────
# JENDELA KONTEKS & KETAHANAN TERHADAP KEGAGALAN ALOKASI
# ─────────────────────────────────────────────────────────────

def _estimasi_token_konteks(context_text: str) -> int:
    """
    Menaksir jumlah token pada konteks + jawaban, HANYA untuk ditampilkan di
    telemetri. Tidak lagi menentukan jendela — num_ctx dipatok ke
    settings.LLM_NUM_CTX atau setelan database (lihat catatan konstanta di atas).

    Pembaginya sengaja kecil supaya taksirannya melebihkan.
    """
    perlu = int(len(context_text) / _CHARS_PER_TOKEN) + _NUM_CTX_RESPONSE_HEADROOM
    return math.ceil(perlu / 1024) * 1024


# Penanda bahwa kegagalan berasal dari memori, bukan sebab lain. Dicocokkan
# pada teks pesan karena Ollama meneruskannya sebagai ResponseError biasa —
# tidak ada tipe exception khusus yang bisa dibedakan.
_PENANDA_GAGAL_ALOKASI = (
    "failed to allocate",
    "out-of-memory",
    "out of memory",
    "cannot allocate",
    "llama-server process has terminated",
)


def _gagal_alokasi(e: Exception) -> bool:
    """Apakah kegagalan ini soal memori."""
    pesan = str(e).lower()
    return any(p in pesan for p in _PENANDA_GAGAL_ALOKASI)


def _stream_jawaban(
    system_prompt: str,
    query: str,
    temperature: float = 0.0,
    num_ctx: int = settings.LLM_NUM_CTX,
    chat_history: list[dict[str, str]] | None = None,
    model_name: str | None = None,
) -> Generator[str, None, None]:
    """
    Alirkan jawaban LLM pada jendela konteks aktif dengan dukungan riwayat multi-turn.
    """
    messages = [SystemMessage(content=system_prompt)]
    if chat_history:
        import re
        for msg in chat_history[-4:]:
            role = msg.get("role")
            cnt = msg.get("content", "")
            if cnt:
                if role == "user":
                    messages.append(HumanMessage(content=cnt))
                elif role == "assistant":
                    # Sanitize: Remove previous system-appended citations to break the LLM's pattern recognition
                    cnt_bersih = re.sub(r"(?i)\n*?\**Sumber Referensi:\**.*", "", cnt, flags=re.DOTALL)
                    messages.append(AIMessage(content=cnt_bersih))
    messages.append(HumanMessage(content=query))

    jendela_dicoba = [num_ctx]
    if _NUM_CTX_FALLBACK < num_ctx:
        jendela_dicoba.append(_NUM_CTX_FALLBACK)

    for i, jendela in enumerate(jendela_dicoba):
        sudah_terkirim = False
        try:
            llm = ChatOllama(
                model=model_name or settings.LLM_MODEL_NAME,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=temperature,
                num_ctx=jendela,
                num_gpu=_NUM_GPU,
                # Matikan mode thinking — lihat catatan di _correct_query_typos().
                # Tanpa ini, model thinking (qwen3.5) mengembalikan konten kosong.
                reasoning=False,
                keep_alive=_OLLAMA_KEEP_ALIVE,
                client_kwargs={"timeout": _OLLAMA_TIMEOUT},
                stop=["**Sumber Referensi:**", "Sumber Referensi:"]
            )
            for chunk in llm.stream(messages):
                if chunk.content:
                    sudah_terkirim = True
                    yield chunk.content
            return

        except Exception as e:
            if sudah_terkirim or i == len(jendela_dicoba) - 1 or not _gagal_alokasi(e):
                raise
            logger.warning(
                "Ollama gagal mengalokasikan memori pada num_ctx=%d — dicoba ulang sekali dengan %d",
                jendela, jendela_dicoba[i + 1],
            )
