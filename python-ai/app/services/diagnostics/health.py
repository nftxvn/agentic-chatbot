"""Probe dependensi untuk health check; koneksi hanya dibuat saat probe dipanggil."""

import logging

from app.config import settings

logger = logging.getLogger("app.main")

_HEALTH_TIMEOUT = 3


def _check_chromadb() -> dict:
    """Basis data vektor bisa dibuka dan jumlah vektornya terbaca."""
    from app.services.embedding_service import get_chroma_collection

    return {"ok": True, "detail": f"{get_chroma_collection().count()} vektor"}


def _check_mysql() -> dict:
    """Koneksi ke MySQL yang dipakai bersama Laravel masih hidup."""
    from sqlalchemy import text

    from app.database import get_engine

    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"ok": True, "detail": settings.MYSQL_DATABASE}


def _check_redis() -> dict:
    """Broker Celery menjawab PING — tanpa ini dokumen tidak bisa masuk antrean."""
    import redis

    client = redis.from_url(
        settings.CELERY_BROKER_URL,
        socket_connect_timeout=_HEALTH_TIMEOUT,
        socket_timeout=_HEALTH_TIMEOUT,
    )
    try:
        client.ping()
    finally:
        client.close()
    return {"ok": True, "detail": "PING"}


def _check_ollama() -> dict:
    """Ollama hidup DAN model chat yang dikonfigurasi benar-benar sudah di-pull."""
    import requests

    response = requests.get(
        f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=_HEALTH_TIMEOUT
    )
    response.raise_for_status()

    # Ollama menuliskan tag lengkap ("qwen2.5:7b"); nama tanpa tag dianggap ":latest".
    installed = {model.get("name", "") for model in response.json().get("models", [])}
    wanted = settings.LLM_MODEL_NAME
    if wanted not in installed and f"{wanted}:latest" not in installed:
        return {"ok": False, "detail": f"model '{wanted}' belum di-pull"}

    return {"ok": True, "detail": wanted}


_HEALTH_CHECKS = {
    "chromadb": _check_chromadb,
    "mysql": _check_mysql,
    "redis": _check_redis,
    "ollama": _check_ollama,
}


def _run_health_checks() -> dict:
    """Jalankan seluruh pemeriksaan; kegagalan satu dependensi tidak menghentikan sisanya."""
    results: dict[str, dict] = {}

    for name, check in _HEALTH_CHECKS.items():
        try:
            results[name] = check()
        except Exception as e:
            # Hanya nama kelas exception yang dilaporkan. Endpoint ini terbuka
            # tanpa autentikasi, dan pesan exception mentah bisa memuat host,
            # nama pengguna basis data, atau potongan kredensial.
            logger.warning("Health check '%s' gagal: %s", name, e)
            results[name] = {"ok": False, "detail": type(e).__name__}

    return results


