"""Pencatatan log dokumen dengan debounce dan penanganan kegagalan query."""

import logging
from datetime import datetime

from sqlalchemy import text

from app.repositories.connection import get_engine
from app.services.document_operations import DocumentOperationCancelled, OperationGuard

logger = logging.getLogger("app.database")

def record_document_log(
    document_id: int,
    action: str,
    details: str | None = None,
    debounce_seconds: int = 15,
    *,
    operation_token: str | None = None,
) -> None:
    """
    Mencatat log aktivitas dokumen ke tabel 'document_logs' dengan proteksi debounce.

    Args:
        document_id: ID dokumen.
        action: Kode aksi (misal 'ocr_completed', 'chunked', 'embedding_completed', 'completed').
        details: Catatan/keterangan aktivitas.
        debounce_seconds: Rentang waktu dalam detik untuk mencegah log duplikat beruntun.
    """
    engine = get_engine()
    now = datetime.utcnow()

    try:
        context = (
            OperationGuard(document_id, operation_token, engine).write()
            if operation_token is not None else engine.connect()
        )
        with context as conn:
            # Cek log terakhir untuk dokumen ini
            check_query = text(
                "SELECT id, action, details, created_at FROM document_logs "
                "WHERE document_id = :document_id ORDER BY created_at DESC LIMIT 1"
            )
            row = conn.execute(check_query, {"document_id": document_id}).mappings().fetchone()

            if row and row["action"] == action:
                if row["created_at"]:
                    diff = (now - row["created_at"]).total_seconds()
                    if diff < debounce_seconds:
                        if details and row["details"] != details:
                            conn.execute(
                                text("UPDATE document_logs SET details = :details WHERE id = :id"),
                                {"details": details, "id": row["id"]},
                            )
                            if operation_token is None:
                                conn.commit()
                        return

            insert_query = text(
                "INSERT INTO document_logs (document_id, action, details, created_at) "
                "VALUES (:document_id, :action, :details, :created_at)"
            )
            conn.execute(
                insert_query,
                {
                    "document_id": document_id,
                    "action": action,
                    "details": details,
                    "created_at": now,
                },
            )
            if operation_token is None:
                conn.commit()
            logger.info("Log aktivitas dokumen %d dicatat: '%s'", document_id, action)
    except DocumentOperationCancelled:
        raise
    except Exception as e:
        logger.warning("Gagal mencatat log dokumen %d (%s): %s", document_id, action, e)


