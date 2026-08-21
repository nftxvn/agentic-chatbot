"""
Aplikasi utama FastAPI untuk Agentic IT Support Copilot - AI Service.
Menyediakan endpoint untuk pemrosesan dokumen dan RAG-based chat.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, documents, ekstraksi

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Redam kegagalan telemetri ChromaDB. Dependensinya tidak sepadan: chromadb
# 0.5.5 memanggil posthog.capture() dengan 3 argumen posisional, sedangkan
# posthog 7.x hanya menerima 1. Akibatnya SETIAP operasi ChromaDB — termasuk
# tiap pertanyaan pengguna — menuliskan "Failed to send telemetry event ...:
# capture() takes 1 positional argument but 3 were given" ke log server.
#
# Tidak ada dampak fungsional: yang gagal hanya pengiriman statistik anonim,
# dan pengirimannya memang sudah dimatikan lewat Settings di
# embedding_service. Yang tersisa murni kebisingan log.
#
# CRITICAL, bukan ERROR: pesan ini dicatat dengan logger.error(), dan ambang
# menyaring level di BAWAHnya — menyetel ERROR justru meloloskannya.
for _telemetry_logger in ("chromadb.telemetry", "posthog", "backoff"):
    logging.getLogger(_telemetry_logger).setLevel(logging.CRITICAL)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan event handler untuk startup dan shutdown.
    Mencatat informasi konfigurasi saat aplikasi dimulai.
    """
    # --- Startup ---
    logger.info("=" * 60)
    logger.info("🚀 Memulai Agentic IT Support Copilot - AI Service")
    logger.info("=" * 60)
    logger.info("📦 Model LLM       : %s", settings.LLM_MODEL_NAME)
    logger.info("🌐 Ollama URL      : %s", settings.OLLAMA_BASE_URL)
    logger.info("🔤 Embedding Model : %s", settings.EMBEDDING_MODEL_NAME)
    logger.info("💾 ChromaDB Dir    : %s", settings.CHROMA_PERSIST_DIR)
    logger.info("🗄️  MySQL Database  : %s@%s:%d/%s",
                settings.MYSQL_USER, settings.MYSQL_HOST,
                settings.MYSQL_PORT, settings.MYSQL_DATABASE)
    logger.info("📮 Celery Broker   : %s", settings.CELERY_BROKER_URL)
    logger.info("=" * 60)

    yield  # Aplikasi berjalan di sini

    # --- Shutdown ---
    logger.info("🛑 Menghentikan AI Service...")
    logger.info("Cleanup selesai. Sampai jumpa! 👋")


# Inisialisasi aplikasi FastAPI
app = FastAPI(
    title="Agentic IT Support Copilot - AI Service",
    description="Microservice AI untuk memproses dokumen dan menyediakan RAG-based chat",
    version="1.0.0",
    lifespan=lifespan,
)

# Konfigurasi CORS.
#
# Origin dibaca dari CORS_ALLOW_ORIGINS di .env, bukan "*". Kombinasi
# allow_origins=["*"] dengan allow_credentials=True membuat Starlette
# memantulkan balik origin peminta apa pun, sehingga penjagaan CORS-nya praktis
# tidak ada — situs mana pun bisa memanggil API ini memakai kredensial
# pengunjungnya.
#
# Method dan header juga dipersempit ke yang benar-benar dipakai.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# Daftarkan routers
app.include_router(documents.router)
app.include_router(ekstraksi.router)
app.include_router(chat.router)


# ── Health check ────────────────────────────────────────────────

# Batas waktu tiap pemeriksaan. Sengaja pendek: health check yang ikut
# menggantung saat dependensinya menggantung tidak memberi tahu apa pun.
_HEALTH_TIMEOUT = 3

# Hasil pemeriksaan disimpan sebentar. /health tidak butuh autentikasi, dan tanpa
# cache setiap permintaan membuka koneksi MySQL + Redis + satu request HTTP ke
# Ollama — artinya endpoint ini bisa dipakai untuk membebani dependensinya.
# Pemantauan umumnya menyapa tiap 10–30 detik, jadi 5 detik tidak mengurangi
# kegunaannya.
_HEALTH_CACHE_TTL = 5
_health_cache: tuple[float, dict] | None = None


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


@app.get("/health", tags=["Health"])
def health_check(response: Response) -> dict:
    """
    Health check yang benar-benar memeriksa dependensi: ChromaDB, MySQL, Redis,
    dan Ollama. Membalas 503 bila salah satu mati, sehingga pemantauan bisa
    membedakan "proses hidup" dari "layanan bisa melayani permintaan".

    Sengaja ditulis sinkron (`def`, bukan `async def`) supaya FastAPI
    menjalankannya di threadpool — seluruh pemeriksaan di dalamnya memblokir dan
    akan menahan event loop bila dijalankan langsung di atasnya.
    """
    global _health_cache

    now = time.monotonic()
    if _health_cache is not None and now - _health_cache[0] < _HEALTH_CACHE_TTL:
        payload = _health_cache[1]
    else:
        checks = _run_health_checks()
        payload = {
            "status": "healthy" if all(c["ok"] for c in checks.values()) else "degraded",
            "service": "ai-service",
            "model": settings.LLM_MODEL_NAME,
            "checks": checks,
        }
        _health_cache = (now, payload)

    if payload["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return payload
