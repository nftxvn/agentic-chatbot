"""Durable generation fences shared by document HTTP handlers and workers.

Model inference runs outside the lock. Every persisted result is authorized
again inside a transaction locking its document row. Cancellation and a new
operation therefore fence old results without purging another document's task.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text

from app.repositories.connection import get_engine


CANCELLATION_MESSAGE = "Pemrosesan dibatalkan oleh pengguna."


class DocumentNotFound(LookupError):
    """The requested document no longer exists."""


class DocumentOperationCancelled(Exception):
    """A task has no valid generation, was cancelled, or was superseded."""


class DocumentCleanupPending(Exception):
    """Full cleanup must finish before another generation can begin."""


def _document_row(connection, document_id: int, *, lock: bool):
    query = (
        "SELECT processing_token, cancellation_requested, status, processed_at FROM documents "
        "WHERE id = :id"
    )
    # SQLite fixtures have no SELECT FOR UPDATE; production MySQL locks the row.
    if lock and connection.dialect.name != "sqlite":
        query += " FOR UPDATE"
    return connection.execute(text(query), {"id": document_id}).mappings().fetchone()


@contextmanager
def _locked_document(document_id: int, engine=None):
    engine = engine if engine is not None else get_engine()
    with engine.begin() as connection:
        row = _document_row(connection, document_id, lock=True)
        if row is None:
            raise DocumentNotFound(f"Dokumen {document_id} tidak ditemukan")
        yield connection, row


@contextmanager
def lock_document(document_id: int, engine=None):
    """Serialize generation-specific cleanup with starts/cancels/guarded writes.

    Cleanup already knows the invalidated token and must not validate it against
    the replacement token. It still holds the same document lock while its
    conditional vector deletion is executed by the external storage adapter.
    """
    with _locked_document(document_id, engine) as (connection, _row):
        yield connection


class OperationGuard:
    def __init__(self, document_id: int, token: str | None, engine=None) -> None:
        self.document_id = document_id
        self.token = token
        self._engine = engine

    def _require_token(self) -> None:
        if not self.token:
            raise DocumentOperationCancelled(
                "Task lama tidak memiliki token operasi; mulai ulang dokumen."
            )

    def _get_engine(self):
        if self._engine is None:
            self._engine = get_engine()
        return self._engine

    def _validate(self, row) -> None:
        if row is None or row["cancellation_requested"] or row["processing_token"] != self.token:
            raise DocumentOperationCancelled(
                "Operasi dokumen telah dibatalkan, digantikan, atau dihapus."
            )

    def checkpoint(self) -> None:
        """Check before/after expensive work without keeping a database lock."""
        self._require_token()
        with self._get_engine().connect() as connection:
            self._validate(_document_row(connection, self.document_id, lock=False))

    @contextmanager
    def write(self):
        """Authorize and persist using this same locked transaction/connection."""
        self._require_token()
        try:
            with _locked_document(self.document_id, self._get_engine()) as (connection, row):
                self._validate(row)
                yield connection
        except DocumentNotFound as error:
            raise DocumentOperationCancelled(
                "Operasi dokumen telah dibatalkan, digantikan, atau dihapus."
            ) from error


def start_operation(document_id: int, engine=None, *, kind: str = "extraction") -> str:
    """Issue a new generation; prior queued/active generations remain fenced."""
    if kind not in {"extraction", "embedding"}:
        raise ValueError("Jenis operasi dokumen tidak dikenal")
    engine = engine if engine is not None else get_engine()
    token = uuid4().hex
    with _locked_document(document_id, engine) as (connection, _row):
        if connection.execute(text(
            "SELECT id FROM document_vector_cleanups "
            "WHERE document_id = :id AND operation_token = ''"
        ), {"id": document_id}).first():
            raise DocumentCleanupPending("Pembersihan vektor dokumen masih tertunda.")
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        connection.execute(text(
            "UPDATE documents SET processing_token = :token, "
            "cancellation_requested = 0, status = 'processing', error_message = NULL, "
            "processed_at = NULL, updated_at = :updated_at WHERE id = :id"
        ), {"id": document_id, "token": token, "updated_at": now})
        connection.execute(text(
            "UPDATE ekstraksi_job SET status = :status, jeda_diminta = 0, "
            "pesan = NULL, updated_at = :updated_at WHERE document_id = :id"
        ), {"id": document_id, "updated_at": now,
            "status": "antre" if kind == "extraction" else "menunggu_koreksi"})
    return token


def cancel_operation(document_id: int, engine=None) -> str | None:
    """Invalidate one generation and record failure in the same transaction.

    Return its old token so vector cleanup can target only that generation.
    Page texts and other documents are preserved; an in-flight inference may
    finish computing, but cannot commit a result through its old guard.
    """
    engine = engine if engine is not None else get_engine()
    with _locked_document(document_id, engine) as (connection, row):
        # Laravel may already have marked the status/job failed. The completion
        # timestamp survives that update; every new operation clears it first.
        completed = row["status"] == "completed" or row["processed_at"] is not None
        previous_token = row["processing_token"] if not completed else None
        if previous_token:
            from app.services.vector_cleanup import enqueue_cleanup
            enqueue_cleanup(connection, document_id, previous_token)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        connection.execute(text(
            "UPDATE documents SET cancellation_requested = 1, status = 'failed', "
            "error_message = :message, updated_at = :updated_at WHERE id = :id"
        ), {"id": document_id, "message": CANCELLATION_MESSAGE, "updated_at": now})
        connection.execute(text(
            "UPDATE ekstraksi_job SET status = 'gagal', jeda_diminta = 0, "
            "pesan = :message, updated_at = :updated_at WHERE document_id = :id"
        ), {"id": document_id, "message": CANCELLATION_MESSAGE, "updated_at": now})
    return previous_token
