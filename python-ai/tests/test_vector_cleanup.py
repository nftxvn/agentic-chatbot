"""Durable cleanup recovery, fencing, rollback and orphan handling without services."""

import asyncio
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.services import document_operations as operations, vector_cleanup as cleanup
from app.services.embeddings import vector_store
from app.services.extraction.mysql_storage import PenyimpananMySQL
from test_document_operations import OperationDatabaseCase


class DurableCleanupTest(OperationDatabaseCase):
    def setUp(self):
        super().setUp()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.collection = Mock()
        self.rows = {}
        self.stack.enter_context(patch.object(vector_store, "get_chroma_collection", return_value=self.collection))
        self.invalidate = self.stack.enter_context(patch.object(vector_store, "_invalidate_search_index"))

        def matches(metadata, where):
            if "$and" in where:
                return all(matches(metadata, part) for part in where["$and"])
            return all(metadata.get(key) == value for key, value in where.items())

        self.collection.get.side_effect = lambda **kw: {"ids": [key for key, value in self.rows.items() if matches(value, kw["where"])]}
        def delete(**kw):
            for key in list(self.rows):
                if matches(self.rows[key], kw["where"]):
                    del self.rows[key]
        self.collection.delete.side_effect = delete

    def jobs(self):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text("SELECT * FROM document_vector_cleanups ORDER BY id")).mappings()]

    def drain(self, **kwargs):
        return cleanup.drain_cleanups(engine=self.engine, **kwargs)

    def test_failed_cleanup_survives_resume_and_later_deletes_only_cancelled_generation(self):
        old = operations.start_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        reader = self.collection.get.side_effect
        self.collection.get.side_effect = RuntimeError("Chroma offline")
        with self.assertLogs(cleanup.logger, level="WARNING"):
            self.assertEqual(self.drain()["failed"], 1)
        job = self.jobs()[0]
        self.assertEqual((job["operation_token"], job["attempts"], job["last_error"]), (old, 1, "RuntimeError"))
        current = operations.start_operation(1, self.engine)
        self.rows.update({"old": {"document_id": 1, "operation_token": old},
                          "new": {"document_id": 1, "operation_token": current},
                          "other": {"document_id": 2, "operation_token": old}})
        self.collection.get.side_effect = reader
        self.assertEqual(self.drain(due_only=False), {"completed": 1, "failed": 0, "deleted_vectors": 1})
        self.assertEqual(set(self.rows), {"new", "other"})
        self.assertEqual(self.jobs(), [])
        operations.OperationGuard(1, current, self.engine).checkpoint()

    def test_background_backoff_does_not_hammer_unavailable_server(self):
        operations.start_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        self.collection.get.side_effect = RuntimeError("offline")
        with self.assertLogs(cleanup.logger, level="WARNING"):
            self.drain()
        self.assertEqual(self.drain()["failed"], 0)
        self.assertEqual(self.collection.get.call_count, 1)

    def test_full_cleanup_blocks_extraction_and_embedding_until_recovery(self):
        old = operations.start_operation(1, self.engine)
        cleanup.request_document_cleanup(1, self.engine)
        for kind in ("extraction", "embedding"):
            with self.subTest(kind=kind), self.assertRaises(operations.DocumentCleanupPending):
                operations.start_operation(1, self.engine, kind=kind)
        self.assertEqual(self.document()["processing_token"], old)
        self.assertEqual(self.document()["cancellation_requested"], 1)
        self.rows["legacy"] = {"document_id": 1}  # No generation metadata on old corpora.
        self.assertEqual(self.drain()["deleted_vectors"], 1)
        current = operations.start_operation(1, self.engine)
        self.assertNotEqual(old, current)
        operations.OperationGuard(1, current, self.engine).checkpoint()

    def test_full_cleanup_survives_sql_document_deletion_and_keeps_other_document(self):
        cleanup.request_document_cleanup(1, self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM documents WHERE id=1"))
        self.rows.update({"old": {"document_id": 1}, "other": {"document_id": 2}})
        self.assertEqual(self.drain()["deleted_vectors"], 1)
        self.assertEqual(set(self.rows), {"other"})
        self.assertEqual(self.jobs(), [])

    def test_token_cleanup_also_survives_deleted_document(self):
        old = operations.start_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM documents WHERE id=1"))
        self.rows["old"] = {"document_id": 1, "operation_token": old}
        self.assertEqual(self.drain()["deleted_vectors"], 1)

    def test_repeated_cancel_and_full_cleanup_requests_are_idempotent(self):
        operations.start_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        cleanup.request_document_cleanup(1, self.engine)
        cleanup.request_document_cleanup(1, self.engine)
        self.assertEqual(len(self.jobs()), 2)
        self.assertEqual(self.drain()["completed"], 2)
        self.assertEqual(self.drain()["completed"], 0)

    def test_completed_corpus_does_not_get_cancel_cleanup_job(self):
        operations.start_operation(1, self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE documents SET status='completed' WHERE id=1"))
        operations.cancel_operation(1, self.engine)
        self.assertEqual(self.jobs(), [])

    def test_outbox_write_failure_rolls_back_cancellation_fence_and_job_status(self):
        old = operations.start_operation(1, self.engine)
        with patch.object(cleanup, "enqueue_cleanup", side_effect=RuntimeError("disk full")):
            with self.assertRaisesRegex(RuntimeError, "disk full"):
                operations.cancel_operation(1, self.engine)
        operations.OperationGuard(1, old, self.engine).checkpoint()
        self.assertEqual(self.document()["status"], "processing")
        self.assertEqual(self.jobs(), [])

    def test_fence_write_failure_rolls_back_an_already_inserted_outbox_request(self):
        old = operations.start_operation(1, self.engine)
        original = Connection.execute
        def fail_fence(connection, statement, *args, **kwargs):
            if str(statement).startswith("UPDATE documents SET cancellation_requested"):
                raise RuntimeError("fence update failed")
            return original(connection, statement, *args, **kwargs)
        with patch("sqlalchemy.engine.Connection.execute", new=fail_fence):
            with self.assertRaisesRegex(RuntimeError, "fence update failed"):
                operations.cancel_operation(1, self.engine)
        operations.OperationGuard(1, old, self.engine).checkpoint()
        self.assertEqual(self.jobs(), [])

    def test_lost_sql_acknowledgement_retries_remote_delete_and_cache_invalidation(self):
        cleanup.request_document_cleanup(1, self.engine)
        self.rows["old"] = {"document_id": 1}
        original = Connection.execute
        def fail_ack(connection, statement, *args, **kwargs):
            if str(statement).startswith("DELETE FROM document_vector_cleanups"):
                raise RuntimeError("SQL acknowledgement lost")
            return original(connection, statement, *args, **kwargs)
        with patch("sqlalchemy.engine.Connection.execute", new=fail_ack):
            with self.assertRaisesRegex(RuntimeError, "acknowledgement lost"):
                self.drain()
        self.assertEqual(self.rows, {})
        self.assertEqual(len(self.jobs()), 1)
        self.assertEqual(self.drain()["completed"], 1)
        self.assertEqual(self.invalidate.call_count, 2)

    def test_bounded_batch_does_not_drop_jobs_not_yet_processed(self):
        cleanup.request_document_cleanup(1, self.engine)
        cleanup.request_document_cleanup(2, self.engine)
        self.assertEqual(self.drain(limit=1)["completed"], 1)
        self.assertEqual([job["document_id"] for job in self.jobs()], [2])

    def test_targeted_full_cleanup_is_not_hidden_behind_a_backlog_of_token_jobs(self):
        with self.engine.begin() as connection:
            for number in range(11):
                cleanup.enqueue_cleanup(connection, 1, f"cancelled-{number}")
        cleanup.request_document_cleanup(1, self.engine)
        self.rows["legacy"] = {"document_id": 1}
        self.assertEqual(self.drain(document_id=1, limit=1)["deleted_vectors"], 1)
        self.assertEqual(len(self.jobs()), 11)
        self.assertTrue(all(job["operation_token"] for job in self.jobs()))
        operations.start_operation(1, self.engine)

    def test_late_extraction_reset_after_full_cleanup_cannot_erase_resumed_pages(self):
        cleanup.request_document_cleanup(1, self.engine)
        self.drain()
        operations.start_operation(1, self.engine)
        PenyimpananMySQL(self.engine).reset_ekstraksi(1, only_cancelled=True)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT text FROM ekstraksi_halaman WHERE document_id=1")).scalar(), "Saved correction")

    def test_cancelled_extraction_can_still_be_reset(self):
        cleanup.request_document_cleanup(1, self.engine)
        PenyimpananMySQL(self.engine).reset_ekstraksi(1, only_cancelled=True)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM ekstraksi_halaman WHERE document_id=1")).scalar(), 0)


class CleanupLoopTest(unittest.IsolatedAsyncioTestCase):
    async def test_api_restart_drains_pending_jobs_and_stops_after_inflight_batch(self):
        stop = asyncio.Event()
        def drain():
            stop.set()
            return {"completed": 1, "failed": 0, "deleted_vectors": 2}
        with patch.object(cleanup, "drain_cleanups", side_effect=drain) as worker:
            await cleanup.cleanup_loop(stop)
        worker.assert_called_once_with()

    async def test_database_failure_is_retried_without_ending_the_loop(self):
        stop = asyncio.Event()
        def drain():
            stop.set()
            raise RuntimeError("database unavailable")
        with patch.object(cleanup, "drain_cleanups", side_effect=drain), self.assertLogs(cleanup.logger, level="WARNING"):
            await cleanup.cleanup_loop(stop)


if __name__ == "__main__":
    unittest.main()
