"""Durable cancellation contracts with SQLite or mocked MySQL transactions.

No broker, model, Redis, or external database is contacted. SQLite checks state
and rollback semantics; production FOR UPDATE ordering is checked separately.
The integration runner exercises actual MySQL row locks across processes.
"""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from sqlalchemy import create_engine, text

from app.repositories import document_logs, documents
from app.services import document_operations as operations
from app.services.extraction.mysql_storage import PenyimpananMySQL


class OperationDatabaseCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.addCleanup(self.engine.dispose)
        with self.engine.begin() as connection:
            connection.execute(text(
                "CREATE TABLE documents (id INTEGER PRIMARY KEY, processing_token TEXT, "
                "cancellation_requested INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL, "
                "error_message TEXT, updated_at DATETIME, total_pages INTEGER DEFAULT 2, "
                "total_chunks INTEGER DEFAULT 0, processed_at DATETIME)"
            ))
            connection.execute(text(
                "CREATE TABLE ekstraksi_job (document_id INTEGER PRIMARY KEY, status TEXT, "
                "jeda_diminta INTEGER DEFAULT 0, halaman_total INTEGER DEFAULT 2, "
                "halaman_selesai INTEGER DEFAULT 0, petunjuk_format TEXT, pesan TEXT, "
                "updated_at DATETIME)"
            ))
            connection.execute(text(
                "CREATE TABLE ekstraksi_halaman (document_id INTEGER, page_number INTEGER, "
                "text TEXT, PRIMARY KEY (document_id, page_number))"
            ))
            connection.execute(text(
                "CREATE TABLE document_logs (id INTEGER PRIMARY KEY, document_id INTEGER, "
                "action TEXT, details TEXT, created_at DATETIME)"
            ))
            connection.execute(text(
                "CREATE TABLE document_vector_cleanups (id INTEGER PRIMARY KEY, document_id INTEGER, "
                "operation_token TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0, "
                "last_error TEXT, available_at DATETIME, created_at DATETIME, updated_at DATETIME, "
                "UNIQUE (document_id, operation_token))"
            ))
            connection.execute(text("INSERT INTO documents (id, status) VALUES (1, 'processing'), (2, 'processing'), (3, 'pending')"))
            connection.execute(text("INSERT INTO ekstraksi_job (document_id, status) VALUES (1, 'berjalan'), (2, 'berjalan')"))
            connection.execute(text("INSERT INTO ekstraksi_halaman VALUES (1, 1, 'Saved correction')"))

    def document(self, document_id=1):
        with self.engine.connect() as connection:
            return dict(connection.execute(text("SELECT * FROM documents WHERE id=:id"), {"id": document_id}).mappings().one())


class DocumentOperationTest(OperationDatabaseCase):
    def test_new_generation_invalidates_older_worker_without_affecting_another_document(self):
        first = operations.start_operation(1, self.engine)
        other = operations.start_operation(2, self.engine)
        guard = operations.OperationGuard(1, first, self.engine)
        guard.checkpoint()
        second = operations.start_operation(1, self.engine)
        self.assertNotEqual(first, second)
        with self.assertRaises(operations.DocumentOperationCancelled):
            guard.checkpoint()
        operations.OperationGuard(2, other, self.engine).checkpoint()

    def test_cancel_atomically_fences_old_generation_and_preserves_saved_pages(self):
        token = operations.start_operation(1, self.engine)
        other = operations.start_operation(2, self.engine)
        self.assertEqual(operations.cancel_operation(1, self.engine), token)
        document = self.document()
        self.assertEqual(document["status"], "failed")
        self.assertEqual(document["error_message"], operations.CANCELLATION_MESSAGE)
        self.assertEqual(document["cancellation_requested"], 1)
        self.assertEqual(document["processing_token"], token)
        with self.assertRaises(operations.DocumentOperationCancelled):
            operations.OperationGuard(1, token, self.engine).checkpoint()
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT status FROM ekstraksi_job WHERE document_id=1")).scalar(), "gagal")
            self.assertEqual(connection.execute(text("SELECT text FROM ekstraksi_halaman WHERE document_id=1")).scalar(), "Saved correction")
        operations.OperationGuard(2, other, self.engine).checkpoint()

    def test_immediate_resume_does_not_allow_the_pre_cancel_result_to_write(self):
        old = operations.start_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        current = operations.start_operation(1, self.engine)
        self.assertEqual(self.document()["cancellation_requested"], 0)
        for token in (None, old):
            with self.subTest(token=token), self.assertRaises(operations.DocumentOperationCancelled):
                with operations.OperationGuard(1, token, self.engine).write() as connection:
                    connection.execute(text("UPDATE documents SET total_chunks=99 WHERE id=1"))
        self.assertEqual(self.document()["total_chunks"], 0)
        operations.OperationGuard(1, current, self.engine).checkpoint()

    def test_cancel_after_completion_does_not_select_the_completed_corpus_for_cleanup(self):
        token = operations.start_operation(1, self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE documents SET status='completed' WHERE id=1"))
        self.assertIsNone(operations.cancel_operation(1, self.engine))
        with self.assertRaises(operations.DocumentOperationCancelled):
            operations.OperationGuard(1, token, self.engine).checkpoint()

    def test_completion_timestamp_protects_corpus_if_laravel_already_set_failed_status(self):
        operations.start_operation(1, self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE documents SET status='failed', processed_at='2026-10-25 00:00:00' WHERE id=1"))
            connection.execute(text("UPDATE ekstraksi_job SET status='gagal' WHERE document_id=1"))
        self.assertIsNone(operations.cancel_operation(1, self.engine))

    def test_new_embedding_does_not_inherit_the_previous_corpus_completion_marker(self):
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE documents SET status='completed', processed_at='2026-10-25 00:00:00' WHERE id=1"))
            connection.execute(text("UPDATE ekstraksi_job SET status='selesai' WHERE document_id=1"))
        token = operations.start_operation(1, self.engine, kind="embedding")
        self.assertEqual(self.document()["status"], "processing")
        self.assertIsNone(self.document()["processed_at"])
        self.assertEqual(operations.cancel_operation(1, self.engine), token)

    def test_repeated_cancel_can_retry_cleanup_of_the_same_invalidated_generation(self):
        token = operations.start_operation(1, self.engine)
        self.assertEqual(operations.cancel_operation(1, self.engine), token)
        self.assertEqual(operations.cancel_operation(1, self.engine), token)

    def test_resume_publishes_queued_status_but_embedding_preserves_review_gate(self):
        operations.cancel_operation(1, self.engine)
        operations.start_operation(1, self.engine)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT status FROM ekstraksi_job WHERE document_id=1")).scalar(), "antre")
        with self.engine.begin() as connection:
            connection.execute(text("UPDATE ekstraksi_job SET status='menunggu_koreksi' WHERE document_id=1"))
        operations.start_operation(1, self.engine, kind="embedding")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT status FROM ekstraksi_job WHERE document_id=1")).scalar(), "menunggu_koreksi")

    def test_guarded_transaction_rolls_back_a_failed_mutation(self):
        token = operations.start_operation(1, self.engine)
        with self.assertRaisesRegex(RuntimeError, "synthetic"):
            with operations.OperationGuard(1, token, self.engine).write() as connection:
                connection.execute(text("UPDATE documents SET total_chunks=99 WHERE id=1"))
                raise RuntimeError("synthetic write failure")
        self.assertEqual(self.document()["total_chunks"], 0)

    def test_missing_document_never_creates_an_operation_or_authorizes_a_write(self):
        for function in (operations.start_operation, operations.cancel_operation):
            with self.subTest(function=function.__name__), self.assertRaises(operations.DocumentNotFound):
                function(99, self.engine)
        guard = operations.OperationGuard(99, "synthetic", self.engine)
        with self.assertRaises(operations.DocumentOperationCancelled):
            guard.checkpoint()
        with self.assertRaises(operations.DocumentOperationCancelled), guard.write():
            self.fail("Missing document authorized a write")

    def test_tokenless_old_messages_are_rejected_before_opening_an_engine(self):
        guard = operations.OperationGuard(1, None)
        with patch.object(operations, "get_engine") as engine:
            with self.assertRaises(operations.DocumentOperationCancelled):
                guard.checkpoint()
            with self.assertRaises(operations.DocumentOperationCancelled), guard.write():
                self.fail("Tokenless task authorized a write")
        engine.assert_not_called()


class MySqlGuardLockTest(unittest.TestCase):
    def test_row_lock_precedes_mutation_on_the_same_connection(self):
        engine = MagicMock()
        connection = engine.begin.return_value.__enter__.return_value
        connection.dialect = SimpleNamespace(name="mysql")
        connection.execute.return_value.mappings.return_value.fetchone.return_value = {
            "processing_token": "current", "cancellation_requested": 0, "status": "processing",
        }
        with operations.OperationGuard(7, "current", engine).write() as authorized:
            self.assertIs(authorized, connection)
            authorized.execute(text("UPDATE documents SET total_chunks=2 WHERE id=7"))
        queries = [str(call.args[0]) for call in connection.execute.call_args_list]
        self.assertTrue(queries[0].endswith("WHERE id = :id FOR UPDATE"))
        self.assertEqual(len(queries), 2)
        engine.connect.assert_not_called()


class GuardedRepositoryTest(OperationDatabaseCase):
    def test_current_status_and_log_writes_use_the_guarded_connection(self):
        token = operations.start_operation(1, self.engine)
        with patch.object(documents, "get_engine", return_value=self.engine), \
                patch.object(document_logs, "get_engine", return_value=self.engine):
            documents.update_document_status(1, "completed", operation_token=token, total_chunks=5)
            document_logs.record_document_log(1, "completed", "Synthetic result", operation_token=token)
        self.assertEqual(self.document()["total_chunks"], 5)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM document_logs")).scalar(), 1)

    def test_old_status_and_audit_log_writes_are_not_retried_or_suppressed_after_cancel(self):
        token = operations.start_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        with patch.object(documents, "get_engine", return_value=self.engine), \
                patch.object(document_logs, "get_engine", return_value=self.engine):
            with self.assertRaises(operations.DocumentOperationCancelled):
                documents.update_document_status(1, "completed", operation_token=token, total_chunks=5)
            with self.assertRaises(operations.DocumentOperationCancelled):
                document_logs.record_document_log(1, "completed", operation_token=token)
        self.assertEqual(self.document()["status"], "failed")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM document_logs")).scalar(), 0)


class GuardedStorageTest(OperationDatabaseCase):
    def setUp(self):
        super().setUp()
        self.redis = Mock()
        self.redis.get.return_value = None
        patcher = patch("app.services.session_memory._get_redis", return_value=self.redis)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_cancelled_storage_rejects_all_writes_before_redis_or_sql_changes(self):
        token = operations.start_operation(1, self.engine)
        storage = PenyimpananMySQL(self.engine, operation_token=token)
        operations.cancel_operation(1, self.engine)
        calls = [
            lambda: storage.simpan_halaman(1, 2, "late result"),
            lambda: storage.simpan_petunjuk(1, "late hint"),
            lambda: storage.catat_status(1, "selesai"),
            lambda: storage.mulai_job(1, 2),
            lambda: storage.minta_jeda(1),
            lambda: storage.batalkan_jeda(1),
            lambda: storage.catat_kemajuan_embed(1, "selesai", 100),
            lambda: storage.reset_ekstraksi(1),
        ]
        for index, call in enumerate(calls):
            with self.subTest(write=index), self.assertRaises(operations.DocumentOperationCancelled):
                call()
        self.redis.setex.assert_not_called()
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT text FROM ekstraksi_halaman WHERE document_id=1")).scalar(), "Saved correction")

    def test_current_progress_is_tagged_and_keeps_page_counts(self):
        token = operations.start_operation(1, self.engine)
        storage = PenyimpananMySQL(self.engine, operation_token=token)
        storage.catat_kemajuan_embed(1, "embedding", 125, "Synthetic progress")
        key, ttl, value = self.redis.setex.call_args.args
        self.assertEqual((key, ttl), ("doc_embed_progress:1", 3600))
        info = json.loads(value)
        self.assertEqual(info["operation_token"], token)
        self.assertEqual(info["persen"], 100)
        self.redis.get.return_value = value
        state = PenyimpananMySQL(self.engine).keadaan(1)
        self.assertEqual((state["status"], state["persen"], state["halaman_total"]), ("embedding", 100, 2))

    def test_cancelled_state_does_not_read_or_trust_a_stale_redis_completion(self):
        operations.start_operation(1, self.engine)
        operations.cancel_operation(1, self.engine)
        self.redis.get.return_value = json.dumps({"status": "selesai", "persen": 100})
        state = PenyimpananMySQL(self.engine).keadaan(1)
        self.assertEqual(state["status"], "gagal")
        self.assertEqual(state["pesan"], operations.CANCELLATION_MESSAGE)
        self.redis.get.assert_not_called()

    def test_cancel_before_a_worker_creates_its_job_still_has_terminal_status(self):
        operations.cancel_operation(3, self.engine)
        state = PenyimpananMySQL(self.engine).keadaan(3)
        self.assertEqual((state["status"], state["halaman_total"], state["halaman_selesai"]), ("gagal", 0, 0))

    def test_new_generation_ignores_old_or_untagged_redis_progress(self):
        old = operations.start_operation(1, self.engine)
        current = operations.start_operation(1, self.engine)
        self.assertNotEqual(old, current)
        for stale_token in (old, None):
            with self.subTest(token=stale_token):
                self.redis.get.return_value = json.dumps({"status": "selesai", "persen": 100, "operation_token": stale_token})
                state = PenyimpananMySQL(self.engine).keadaan(1)
                self.assertEqual((state["status"], state["persen"]), ("antre", 0))

    def test_legacy_progress_keeps_existing_overlay_before_any_generation_was_issued(self):
        self.redis.get.return_value = json.dumps({"status": "embedding", "persen": 55, "pesan": "Existing progress"})
        state = PenyimpananMySQL(self.engine).keadaan(1)
        self.assertEqual((state["status"], state["persen"]), ("embedding", 55))


if __name__ == "__main__":
    unittest.main()
