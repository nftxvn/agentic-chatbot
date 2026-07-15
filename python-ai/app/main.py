"""
Aplikasi utama FastAPI untuk Agentic IT Support Copilot - AI Service.
Menyediakan endpoint untuk pemrosesan dokumen dan RAG-based chat.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import chat, documents

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


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

# Konfigurasi CORS (izinkan semua origin untuk development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Batasi origin di produksi
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Daftarkan routers
app.include_router(documents.router)
app.include_router(chat.router)


@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint.
    Digunakan untuk memverifikasi bahwa service berjalan dengan baik.
    """
    return {
        "status": "healthy",
        "service": "ai-service",
        "model": settings.LLM_MODEL_NAME,
    }
