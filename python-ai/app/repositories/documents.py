"""Query dokumen/kategori, nama sitasi, dan pembaruan status terparameterisasi."""

import logging
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import bindparam, text

from app.repositories.connection import get_engine
from app.services.document_operations import DocumentOperationCancelled, OperationGuard

logger = logging.getLogger("app.database")

def update_document_status(
    document_id: int,
    status: str,
    *,
    operation_token: str | None = None,
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
        "processed_pages",
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
        context = (
            OperationGuard(document_id, operation_token, engine).write()
            if operation_token is not None else engine.connect()
        )
        with context as conn:
            result = conn.execute(query, params)
            if operation_token is None:
                conn.commit()
            logger.info(
                "Status dokumen %d diupdate ke '%s' (%d baris terpengaruh)",
                document_id,
                status,
                result.rowcount,
            )
    except DocumentOperationCancelled:
        raise
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


def get_document_names(document_ids: Iterable[int]) -> dict[int, str]:
    """
    Mengambil Judul Dokumen (title) atau fallback ke nama berkas (original_name)
    untuk sekumpulan dokumen sekaligus.

    Dipakai untuk mengisi rujukan sumber / sitasi di jawaban chat RAG dan API
    agar menampilkan judul resmi dokumen seperti yang terlihat di Dashboard.

    Args:
        document_ids: Kumpulan ID dokumen. Duplikat diabaikan.

    Returns:
        Dict {document_id: title or original_name}. ID yang tidak ada di basis data
        tidak muncul di hasil.
    """
    ids = sorted({int(document_id) for document_id in document_ids})
    if not ids:
        return {}

    engine = get_engine()

    # expanding=True: SQLAlchemy yang menyusun daftar parameter untuk klausa IN,
    # sehingga nilainya tetap lewat jalur parameter dan tidak pernah dirangkai
    # ke dalam string SQL.
    query = text(
        "SELECT id, title, original_name FROM documents WHERE id IN :document_ids"
    ).bindparams(bindparam("document_ids", expanding=True))

    try:
        with engine.connect() as conn:
            rows = conn.execute(query, {"document_ids": ids}).mappings().all()
            return {
                row["id"]: (
                    str(row["title"]).strip()
                    if row.get("title") and str(row.get("title")).strip()
                    else row["original_name"]
                )
                for row in rows
            }

    except Exception as e:
        logger.error("Gagal mengambil nama/judul untuk dokumen %s: %s", ids, str(e))
        raise


get_document_names_by_ids = get_document_names


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
        "SELECT d.id, d.original_name, d.file_path, d.status, d.pdf_type, "
        "d.category_id, d.total_pages, d.total_chunks, d.error_message, d.processed_at, "
        "d.created_at, d.updated_at, "
        "c.vision_prompt AS category_vision_prompt, "
        "c.vision_model AS category_vision_model, "
        "c.prompt_variables AS category_prompt_variables "
        "FROM documents d "
        "LEFT JOIN document_categories c ON d.category_id = c.id "
        "WHERE d.id = :document_id"
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


