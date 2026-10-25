"""
Aplikasi utama FastAPI untuk Agentic IT Support Copilot - AI Service.
Menyediakan endpoint untuk pemrosesan dokumen dan RAG-based chat.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, documents, ekstraksi, health

# Ekspor kompatibilitas untuk pemanggil yang mengimpor helper dari app.main.
from app.services.diagnostics.health import (
    _HEALTH_TIMEOUT,
    _check_chromadb,
    _check_mysql,
    _check_redis,
    _check_ollama,
    _HEALTH_CHECKS,
    _run_health_checks,
)
from app.services.diagnostics.hardware import (
    _baca_nvidia_smi,
    _deteksi_os_platform,
    _baca_system_ram,
    _hitung_rekomendasi_hardware,
    _baca_ollama_ps,
    _hitung_kecocokan_model,
)
from app.routers.health import (
    health_check,
    diagnostik_mesin,
    _HEALTH_CACHE_TTL,
    _MESIN_CACHE_TTL,
)

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Redam pesan dari logger telemetri ChromaDB dan dependensinya. Kegagalan
# pengiriman statistik anonim tidak boleh menutupi log aplikasi; retrieval dan
# penyimpanan vektor tetap dijalankan oleh layanan ChromaDB.
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

    from app.services.vector_cleanup import cleanup_loop
    cleanup_stop = asyncio.Event()
    cleanup_task = asyncio.create_task(cleanup_loop(cleanup_stop))
    try:
        yield  # Aplikasi berjalan di sini
    finally:
        cleanup_stop.set()
        await cleanup_task

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
app.include_router(health.router)
