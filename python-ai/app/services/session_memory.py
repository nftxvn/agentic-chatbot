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
            redis_url = os.getenv("CHAT_REDIS_URL")
            if not redis_url:
                broker = settings.CELERY_BROKER_URL
                if broker and broker.startswith("redis://"):
                    base = broker.rsplit("/", 1)[0]
                    redis_url = f"{base}/2"
                else:
                    redis_url = "redis://localhost:6379/2"
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
    "paling lama", "paling cepat", "lebih cepat", "terlama", "tercepat",
    "syarat berkas", "berkas", "persyaratan", "tahapan tadi", "langkah tadi",
    "dari awal", "hitung kembali", "koreksi", "hitung ulang",
}

# Topik mandiri baru yang benar-benar spesifik (jika kata ini muncul, barulah dianggap topik baru)
_STANDALONE_TOPIC_MARKERS = {
    "renja", "renstra", "rka", "dpa", "lkjip", "lppd", "sakip", "iku", "pk",
    "magang", "pkl", "kenaikan pangkat", "pangkat", "gaji", "cuti", "pensiun",
    "subdomain", "domain", "email", "server", "wifi", "internet",
    "jaringan", "perwal", "sk", "csirt", "siber", "smart city", "statistik", "persandian",
    "bappeda", "walikota", "kadis", "kepala dinas", "sekretaris",
}


_RE_SESSION_RECAP = re.compile(
    r"\b(bahas\s+apa|bicara\s+apa|ngomongin\s+apa|ngobrolin\s+apa|obrolan\s+kita|percakapan\s+kita|"
    r"tadi\s+(?:saya\s+)?tanya\s+apa|pertanyaan\s+saya\s+sebelumnya|rangkum\s+(?:obrolan|percakapan|topik)|"
    r"sebelumnya\s+kita\s+bahas|tadi\s+tentang\s+apa|kita\s+sedang\s+bahas\s+apa|topik\s+sebelumnya|"
    r"apa\s+yang\s+(?:tadi\s+)?kita\s+bahas|tadi\s+saya\s+bahas\s+apa)\b",
    re.IGNORECASE,
)

_RE_DOUBT_OR_CORRECTION = re.compile(
    r"\b(salah|keliru|bukan|bukannya|kok beda|kok salah|kok bisa|kenapa beda|memang iya|masa sih|masa|yakin|beneran|serius|ngaco|bohong|ngibul|gak bener|tidak benar|kurang tepat|tidak tepat|hah|lah|hitung kembali|hitung ulang)\b",
    re.IGNORECASE,
)


def clean_context_subject(raw_subject: str) -> str:
    """Membersihkan context subject dari prefiks pertanyaan atau kata perintah meta."""
    if not raw_subject:
        return ""
    text = raw_subject.strip()
    
    # Abaikan meta-queries agar tidak dijadikan nama entitas/topik
    meta_patterns = [
        r"^(?:coba\s+)?(?:hitung|kalkulasi|cek|lihat|tinjau)(?:\s+(?:kembali|ulang|lagi))?$",
        r"^(?:hari\s+apa|tanggal\s+berapa)(?:\s+hari\s+ini)?$",
        r"^(?:kapan|dimana|siapa|bagaimana|berapa)(?:\s+siapnya|\s+selesainya)?$",
    ]
    for mp in meta_patterns:
        if re.search(mp, text, re.IGNORECASE):
            return ""

    if "terkait " in text.lower():
        idx = text.lower().rfind("terkait ")
        text = text[idx + len("terkait "):].strip()
    text = re.sub(r"^(?:kalo|kalau|bagaimana|apa|berapa|dari\s+tahapan|dari\s+langkah)\s+", "", text, flags=re.IGNORECASE).strip()
    text = text.rstrip("?!., ")
    return text


_COMPARATIVE_PHRASE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:di\s*antara|antara)\s+kedua(?:\s*-\s*dua)?\s*mereka\b", re.IGNORECASE), "di antara {subj}"),
    (re.compile(r"\bkedua(?:\s*-\s*dua)?\s*mereka\b", re.IGNORECASE), "{subj}"),
    (re.compile(r"\b(?:di\s*antara|antara)\s+keduanya\b", re.IGNORECASE), "antara {subj}"),
    (re.compile(r"\bkedua(?:-dua)?nya\b", re.IGNORECASE), "{subj}"),
    (re.compile(r"\bkedua\s+(?:sop|dokumen|layanan|pihak|hal)\s+(?:tersebut|ini|tadi)\b", re.IGNORECASE), "{subj}"),
    (re.compile(r"\bmereka\s+berdua\b", re.IGNORECASE), "{subj}"),
    (re.compile(r"\b(?:sop|dokumen|layanan|hal)\s+(?:tersebut|ini|tadi)\b", re.IGNORECASE), "{subj}"),
    (re.compile(r"\b(beliau|dia|ia|mereka|tersebut|tadi)\b", re.IGNORECASE), "{subj}"),
]


def resolve_contextual_query(query: str, session_id: str) -> tuple[str, bool]:
    """
    Menganalisis apakah query pengguna adalah pertanyaan lanjutan (follow-up)
    yang membutuhkan penggabungan konteks dari sesi sebelumnya.

    Returns:
        tuple (resolved_query, is_resolved)
    """
    if not session_id or not query.strip():
        return query, False

    # Jangan resolusi pertanyaan rekap sesi / memori obrolan
    if _RE_SESSION_RECAP.search(query):
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

    context_subject = clean_context_subject(last_entity or last_topic or last_user_query)

    if not context_subject:
        return query, False

    q_lower = query.lower().strip()
    words = set(re.findall(r"\w+", q_lower))

    # 1. Ganti kata ganti eksplisit / frasa komparatif jika ada
    resolved = query
    replaced_pronoun = False
    for pat, repl in _COMPARATIVE_PHRASE_PATTERNS:
        if pat.search(resolved):
            resolved = pat.sub(repl.format(subj=context_subject), resolved)
            replaced_pronoun = True
            break

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

    # 4. Cek pertanyaan keraguan, sanggahan, atau koreksi (misal: "masa sih?", "kok beda?", "yakin 60 menit?")
    is_doubt = bool(_RE_DOUBT_OR_CORRECTION.search(query))

    if has_elliptic or is_short_fragment or is_doubt:
        resolved = f"{query} terkait {context_subject}"
        logger.info("Context Resolution: Menyambung follow-up/keraguan -> '%s'", resolved)
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
