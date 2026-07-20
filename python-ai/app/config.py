"""
Konfigurasi aplikasi AI Microservice.
Memuat semua environment variables menggunakan python-dotenv.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Muat file .env dari root project
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_env_path)


class Settings:
    """
    Kelas konfigurasi utama.
    Semua nilai diambil dari environment variables dengan fallback default.
    """

    # --- LLM Configuration ---
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "qwen2.5:3b")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    VISION_MODEL_NAME: str = os.getenv("VISION_MODEL_NAME", "qwen2.5vl")
    VISION_TIMEOUT: int = int(os.getenv("VISION_TIMEOUT", "60"))

    # --- Embedding ---
    EMBEDDING_MODEL_NAME: str = os.getenv(
        "EMBEDDING_MODEL_NAME", "paraphrase-multilingual-MiniLM-L12-v2"
    )

    # --- Vector DB (ChromaDB) ---
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./data/chromadb")

    # --- Database MySQL (Shared with Laravel) ---
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "agentic_copilot")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "secret")

    # --- Celery (Antrian tugas async) ---
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv(
        "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"
    )

    # --- Security ---
    INTERNAL_API_TOKEN: str = os.getenv(
        "INTERNAL_API_TOKEN", "your-secure-internal-token-here"
    )

    @property
    def MYSQL_DATABASE_URL(self) -> str:
        """
        Menghasilkan URL koneksi SQLAlchemy untuk MySQL.
        Format: mysql+pymysql://user:password@host:port/database
        """
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )


# Instance singleton untuk digunakan di seluruh aplikasi
settings = Settings()
