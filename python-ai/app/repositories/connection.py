"""Engine SQLAlchemy tunggal yang dibuat hanya saat get_engine dipanggil."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import settings

logger = logging.getLogger("app.database")

_engine: Engine | None = None


def get_engine() -> Engine:
    """
    Mendapatkan atau membuat SQLAlchemy engine (lazy loading).
    Menggunakan pool_pre_ping untuk menangani koneksi yang terputus.
    """
    global _engine
    if _engine is None:
        logger.info("Membuat koneksi database ke %s", settings.MYSQL_HOST)
        _engine = create_engine(
            settings.MYSQL_DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            pool_recycle=3600,  # Recycle koneksi setiap 1 jam
        )
    return _engine


