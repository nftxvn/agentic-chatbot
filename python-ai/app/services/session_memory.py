"""
Modul Session Memory untuk percakapan Multi-Turn.
Menyimpan riwayat chat (User & Assistant) serta entitas/topik aktif per session_id
menggunakan Redis (dengan fallback ke in-memory TTL cache).
"""

import json
import logging
import os
import re
import time
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# TTL sesi dalam detik (30 menit)
_SESSION_TTL = 1800
_MAX_HISTORY_MESSAGES = 6

# Fallback in-memory cache bila Redis tidak tersedia
_local_memory_cache: dict[str, tuple[float, dict[str, Any]]] = {}

# Client Redis lazy singleton
_redis_client = None
_redis_available: bool | None = None


def _get_redis():
    global _redis_client, _redis_available
    if _redis_available is False:
        return None

    if _redis_client is None:
        try:
            import redis
            redis_url = os.getenv("CHAT_REDIS_URL", "redis://localhost:6379/2")
            _redis_client = redis.from_url(redis_url, socket_timeout=2.0, socket_connect_timeout=2.0)
            _redis_client.ping()
            _redis_available = True
            logger.info("Session Memory: Terhubung ke Redis di %s", redis_url)
        except Exception as e:
            logger.warning("Session Memory: Redis tidak tersedia (%s), fallback ke in-memory cache", e)
            _redis_available = False
            _redis_client = None
            return None

    return _redis_client


def _get_session_data(session_id: str) -> dict[str, Any]:
    """Mengambil payload data sesi dari Redis atau memory."""
    if not session_id or session_id in ("api-session", "test-session"):
        return {"messages": [], "last_topic": None, "last_entity": None}

    r = _get_redis()
    if r:
        try:
            key = f"chatbot:session:{session_id}"
            raw = r.get(key)
            if raw:
                return json.loads(raw)
        except Exception as e:
            logger.warning("Session Memory: Gagal membaca Redis untuk %s: %s", session_id, e)

    # Fallback memory
    now = time.time()
    if session_id in _local_memory_cache:
        expire_at, data = _local_memory_cache[session_id]
        if now < expire_at:
            return data
        else:
            del _local_memory_cache[session_id]

    return {"messages": [], "last_topic": None, "last_entity": None}


def _save_session_data(session_id: str, data: dict[str, Any]) -> None:
    """Menyimpan payload data sesi ke Redis atau memory."""
    if not session_id or session_id in ("api-session", "test-session"):
        return

    r = _get_redis()
    if r:
        try:
            key = f"chatbot:session:{session_id}"
            r.setex(key, _SESSION_TTL, json.dumps(data, ensure_ascii=False))
            return
        except Exception as e:
            logger.warning("Session Memory: Gagal menulis Redis untuk %s: %s", session_id, e)

    # Fallback memory
    now = time.time()
    _local_memory_cache[session_id] = (now + _SESSION_TTL, data)


def add_user_message(session_id: str, content: str) -> None:
    """Menambahkan pesan pengguna ke riwayat sesi."""
    if not session_id or not content.strip():
        return
    data = _get_session_data(session_id)
    messages = data.get("messages", [])
    messages.append({
        "role": "user",
        "content": content.strip(),
        "timestamp": time.time(),
    })
    # Batasi jumlah pesan riwayat
    data["messages"] = messages[-_MAX_HISTORY_MESSAGES:]
    _save_session_data(session_id, data)


def add_assistant_message(
    session_id: str,
    content: str,
    topic: str | None = None,
    entity: str | None = None,
) -> None:
    """Menambahkan pesan asisten dan mencatat topik/entitas aktif ke riwayat sesi."""
    if not session_id or not content.strip():
        return
    data = _get_session_data(session_id)
    messages = data.get("messages", [])
    messages.append({
        "role": "assistant",
        "content": content.strip(),
        "timestamp": time.time(),
    })
    data["messages"] = messages[-_MAX_HISTORY_MESSAGES:]
    if topic:
        data["last_topic"] = topic
    if entity:
        data["last_entity"] = entity
    _save_session_data(session_id, data)


def get_session_history(session_id: str, max_turns: int = 4) -> list[dict[str, str]]:
    """
    Mengambil riwayat percakapan terkini untuk disuntikkan ke LLM.
    Returns:
        List of dict [{"role": "user"|"assistant", "content": "..."}]
    """
    if not session_id:
        return []
    data = _get_session_data(session_id)
    messages = data.get("messages", [])
    # Ambil N pesan terakhir
    recent = messages[-max_turns:]
    return [{"role": m["role"], "content": m["content"]} for m in recent]


def get_last_context(session_id: str) -> tuple[str | None, str | None]:
    """Mengembalikan (last_topic, last_entity) dari sesi."""
    if not session_id:
        return None, None
    data = _get_session_data(session_id)
    return data.get("last_topic"), data.get("last_entity")


# Kata/frasa penanda follow-up atau kata ganti anafora (Indonesia & Aceh)
_PRONOUNS_EXPLICIT = {
    "beliau", "dia", "ia", "mereka", "tersebut", "tadi",
    "disana", "di sana", "di situ", "disitu", "ke sana", "kesana",
}

_ELLIPTIC_FOLLOWUP_WORDS = {
    "kapan", "tahun berapa", "tanggal berapa", "pukul berapa", "jam berapa",
    "siapa namanya", "namanya", "kontaknya", "nomornya", "alamatnya",
    "syaratnya", "biayanya", "waktunya", "prosesnya", "tahapannya", "langkahnya",
    "bagaimana caranya", "caranya", "durasi", "lama proses", "estimasi", "outputnya",
    "pat", "pajan", "padup", "padip", "soe", "peue", "kiban", "pane",
}

_STANDALONE_TOPIC_MARKERS = {
    "sop", "renja", "renstra", "rka", "dpa", "lkjip", "lppd", "sakip", "iku", "pk",
    "magang", "pkl", "subdomain", "domain", "email", "server", "wifi", "internet",
    "jaringan", "perwal", "sk", "csirt", "siber", "smart city", "statistik", "persandian",
    "aplikasi", "helpdesk", "layanan", "surat", "disposisi", "bappeda", "walikota", "kantor",
    "kadis", "kepala dinas", "sekretaris", "bidang",
}


def resolve_contextual_query(query: str, session_id: str) -> tuple[str, bool]:
    """
    Menganalisis apakah query pengguna adalah pertanyaan lanjutan (follow-up)
    yang membutuhkan penggabungan konteks dari sesi sebelumnya.

    Returns:
        tuple (resolved_query, is_resolved)
    """
    if not session_id or not query.strip():
        return query, False

    data = _get_session_data(session_id)
    messages = data.get("messages", [])
    if not messages:
        return query, False

    last_topic = data.get("last_topic")
    last_entity = data.get("last_entity")

    # Cari pertanyaan user terakhir
    last_user_query = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user_query = m.get("content", "")
            break

    context_subject = last_entity or last_topic
    if not context_subject and last_user_query:
        context_subject = last_user_query

    if not context_subject:
        return query, False

    q_lower = query.lower().strip()
    words = set(re.findall(r"\w+", q_lower))

    # 1. Ganti kata ganti eksplisit jika ada (beliau, dia, dsb)
    resolved = query
    replaced_pronoun = False
    for p in ["beliau", "dia", "ia", "tersebut"]:
        if re.search(rf"\b{p}\b", resolved, re.IGNORECASE):
            resolved = re.sub(rf"\b{p}\b", context_subject, resolved, flags=re.IGNORECASE)
            replaced_pronoun = True

    if replaced_pronoun:
        logger.info("Context Resolution: Mengganti kata ganti -> '%s'", resolved)
        return resolved, True

    # 2. Cek apakah ada penanda topik mandiri baru (standalone topic)
    has_standalone_topic = bool(words.intersection(_STANDALONE_TOPIC_MARKERS))
    if has_standalone_topic:
        # Jika pengguna menanyakan topik baru yang jelas (misal 'sop', 'renja', 'magang'), jangan tempel topik lama!
        return query, False

    # 3. Cek pertanyaan eliptik / akhiran -nya (misal: "berapa lama prosesnya?", "apa syaratnya?", "sudah berapa hari?")
    has_elliptic = bool(words.intersection(_ELLIPTIC_FOLLOWUP_WORDS)) or any(w.endswith("nya") for w in words)
    is_short_fragment = len(words) <= 4 and ("berapa" in words or "kapan" in words or "siapa" in words or "dimana" in words or "bagaimana" in words or "apa" in words)

    if has_elliptic or is_short_fragment:
        resolved = f"{query} terkait {context_subject}"
        logger.info("Context Resolution: Menyambung follow-up -> '%s'", resolved)
        return resolved, True

    return query, False


def clear_session(session_id: str) -> bool:
    """Menghapus seluruh memori sesi."""
    if not session_id:
        return False
    r = _get_redis()
    if r:
        try:
            r.delete(f"chatbot:session:{session_id}")
        except Exception:
            pass
    if session_id in _local_memory_cache:
        del _local_memory_cache[session_id]
    return True
