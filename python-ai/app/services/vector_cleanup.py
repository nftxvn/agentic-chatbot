"""Durable vector cleanup outbox shared with Laravel; no broker is required.

Document locks serialize cleanup with generation starts and vector writes.
Whole-document requests block new starts until deletion is acknowledged.
Token requests remain safe after resume, and rows survive document deletion.
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.repositories.connection import get_engine

logger = logging.getLogger(__name__)
RETRY_INTERVAL_SECONDS = 30


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def enqueue_cleanup(connection, document_id: int, operation_token: str = "") -> None:
    """Call inside the transaction holding the document lock/fence."""
    values = {"document_id": document_id, "token": operation_token, "now": _now()}
    query = (
        "INSERT INTO document_vector_cleanups "
        "(document_id, operation_token, attempts, available_at, created_at, updated_at) "
        "VALUES (:document_id, :token, 0, :now, :now, :now)"
    )
    # A duplicate scope must retain its attempts/backoff. Do not commit through
    # a nested savepoint: the fence and request belong to the outer transaction.
    if connection.dialect.name == "mysql":
        query += " ON DUPLICATE KEY UPDATE id = id"
    elif connection.dialect.name == "sqlite":
        query += " ON CONFLICT(document_id, operation_token) DO NOTHING"
    connection.execute(text(query), values)


def request_document_cleanup(document_id: int, engine=None) -> None:
    """Persist a full cleanup before remote I/O, even for an orphan document ID."""
    from app.services.document_operations import _document_row

    engine = engine if engine is not None else get_engine()
    with engine.begin() as connection:
        row = _document_row(connection, document_id, lock=True)
        if row is not None:
            connection.execute(text(
                "UPDATE documents SET cancellation_requested = 1, updated_at = :now WHERE id = :id"
            ), {"id": document_id, "now": _now()})
        enqueue_cleanup(connection, document_id)


def _process_cleanup(cleanup_id, document_id, engine, *, due_only):
    from app.services.document_operations import _document_row
    from app.services.embeddings.vector_store import delete_cleanup_vectors

    with engine.begin() as connection:
        # Always take locks in document -> outbox order, including duplicate drains.
        _document_row(connection, document_id, lock=True)
        query = "SELECT * FROM document_vector_cleanups WHERE id = :id"
        if due_only:
            query += " AND available_at <= :now"
        if connection.dialect.name != "sqlite":
            query += " FOR UPDATE"
        row = connection.execute(text(query), {"id": cleanup_id, "now": _now()}).mappings().first()
        if row is None:
            return {"completed": 0, "failed": 0, "deleted_vectors": 0}
        try:
            deleted = delete_cleanup_vectors(document_id, row["operation_token"])
        except Exception as error:
            attempts = row["attempts"] + 1
            now = _now()
            connection.execute(text(
                "UPDATE document_vector_cleanups SET attempts = :attempts, "
                "last_error = :error, available_at = :next, updated_at = :now WHERE id = :id"
            ), {"id": cleanup_id, "attempts": attempts, "error": type(error).__name__,
                "now": now, "next": now + timedelta(seconds=min(300, 30 * 2 ** min(attempts - 1, 4)))})
            logger.warning("Vector cleanup %d for document %d failed; retained for retry", cleanup_id, document_id, exc_info=True)
            return {"completed": 0, "failed": 1, "deleted_vectors": 0}
        # Delete and cache invalidation are idempotent if SQL commit is interrupted.
        connection.execute(text("DELETE FROM document_vector_cleanups WHERE id = :id"), {"id": cleanup_id})
        return {"completed": 1, "failed": 0, "deleted_vectors": deleted}


def drain_cleanups(*, document_id=None, limit=10, due_only=True, engine=None) -> dict:
    """Process a bounded snapshot. Failed jobs back off; explicit retries may bypass it."""
    if not 1 <= limit <= 1000:
        raise ValueError("Cleanup limit must be between 1 and 1000")
    engine = engine if engine is not None else get_engine()
    query = "SELECT id, document_id FROM document_vector_cleanups WHERE 1 = 1"
    values = {"limit": limit, "now": _now()}
    if document_id is not None:
        query += " AND document_id = :document_id"
        values["document_id"] = document_id
    if due_only:
        query += " AND available_at <= :now"
    # A targeted DELETE/start must process its full scope even when many older
    # cancelled-token requests exceed this bounded batch. Background stays FIFO.
    query += " ORDER BY "
    if document_id is not None:
        query += "CASE WHEN operation_token = '' THEN 0 ELSE 1 END, "
    query += "id LIMIT :limit"
    with engine.connect() as connection:
        rows = connection.execute(text(query), values).mappings().all()
    result = {"completed": 0, "failed": 0, "deleted_vectors": 0}
    for row in rows:
        outcome = _process_cleanup(row["id"], row["document_id"], engine, due_only=due_only)
        for key in result:
            result[key] += outcome[key]
    return result


async def cleanup_loop(stop: asyncio.Event) -> None:
    """Retry on API startup and every 30s; each database job owns its lock."""
    while not stop.is_set():
        try:
            await asyncio.to_thread(drain_cleanups)
        except Exception:
            logger.warning("Unable to drain vector cleanup outbox; retrying later", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=RETRY_INTERVAL_SECONDS)
        except TimeoutError:
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", type=int)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    result = drain_cleanups(document_id=args.document_id, limit=args.limit, due_only=False)
    print(json.dumps(result))
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
