"""
Database helper untuk koneksi MySQL menggunakan SQLAlchemy.
Digunakan untuk mengupdate status dokumen di database yang di-share dengan Laravel.
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.config import settings

logger = logging.getLogger(__name__)

# Engine SQLAlchemy (singleton, dibuat saat modul pertama kali diimpor)
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


def update_document_status(
    document_id: int,
    status: str,
    **kwargs: Any,
) -> None:
    """
    Mengupdate status dokumen di tabel 'documents'.

    Args:
        document_id: ID dokumen yang akan diupdate.
        status: Status baru ('processing', 'completed', 'failed').
        **kwargs: Field tambahan yang bisa diupdate:
            - pdf_type (str): Tipe PDF ('text', 'scanned', 'mixed')
            - total_chunks (int): Jumlah total chunk yang dihasilkan
            - total_pages (int): Jumlah total halaman PDF
            - error_message (str): Pesan error jika gagal
            - processed_at (datetime): Waktu selesai diproses
    """
    engine = get_engine()

    # Bangun klausa SET secara dinamis berdasarkan kwargs
    set_clauses = ["status = :status", "updated_at = :updated_at"]
    params: dict[str, Any] = {
        "document_id": document_id,
        "status": status,
        "updated_at": datetime.utcnow(),
    }

    # Tambahkan field opsional jika ada
    allowed_fields = {
        "pdf_type",
        "total_chunks",
        "total_pages",
        "error_message",
        "processed_at",
    }

    for key, value in kwargs.items():
        if key in allowed_fields:
            set_clauses.append(f"{key} = :{key}")
            params[key] = value
        else:
            logger.warning("Field '%s' tidak diizinkan untuk update, diabaikan.", key)

    # Susun query SQL
    set_clause_str = ", ".join(set_clauses)
    query = text(f"UPDATE documents SET {set_clause_str} WHERE id = :document_id")

    try:
        with engine.connect() as conn:
            result = conn.execute(query, params)
            conn.commit()
            logger.info(
                "Status dokumen %d diupdate ke '%s' (%d baris terpengaruh)",
                document_id,
                status,
                result.rowcount,
            )
    except Exception as e:
        logger.error(
            "Gagal mengupdate status dokumen %d: %s",
            document_id,
            str(e),
        )
        raise


def get_all_documents() -> list[dict[str, Any]]:
    """
    Mengambil daftar semua dokumen dari tabel 'documents'.

    Returns:
        List of dict, setiap dict merepresentasikan satu baris dokumen.
    """
    engine = get_engine()

    query = text(
        "SELECT id, original_name, file_path, status, pdf_type, "
        "total_pages, total_chunks, created_at, updated_at "
        "FROM documents ORDER BY created_at DESC"
    )

    try:
        with engine.connect() as conn:
            result = conn.execute(query)
            rows = result.mappings().all()
            documents = [dict(row) for row in rows]
            logger.info("Berhasil mengambil %d dokumen dari database", len(documents))
            return documents

    except Exception as e:
        logger.error("Gagal mengambil daftar dokumen: %s", str(e))
        raise


def get_document_by_id(document_id: int) -> dict[str, Any] | None:
    """
    Mengambil data satu dokumen berdasarkan ID.

    Args:
        document_id: ID dokumen yang dicari.

    Returns:
        Dict berisi data dokumen, atau None jika tidak ditemukan.
    """
    engine = get_engine()

    query = text(
        "SELECT id, original_name, file_path, status, pdf_type, "
        "total_pages, total_chunks, error_message, processed_at, "
        "created_at, updated_at "
        "FROM documents WHERE id = :document_id"
    )

    try:
        with engine.connect() as conn:
            result = conn.execute(query, {"document_id": document_id})
            row = result.mappings().fetchone()

            if row is None:
                logger.info("Dokumen %d tidak ditemukan", document_id)
                return None

            document = dict(row)
            logger.info("Berhasil mengambil data dokumen %d", document_id)
            return document

    except Exception as e:
        logger.error(
            "Gagal mengambil data dokumen %d: %s",
            document_id,
            str(e),
        )
        raise
