"""Kontrak SQL/parameter/cache repository menggunakan koneksi tiruan."""

import importlib
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from app import database as db


def owner(function):
    return importlib.import_module(function.__module__)


class EngineContractTest(unittest.TestCase):
    def test_engine_remains_lazy_singleton_with_existing_pool_options(self):
        module = owner(db.get_engine)
        engine = Mock()
        with patch.object(module, "_engine", None), patch.object(module, "create_engine", return_value=engine) as create:
            self.assertIs(db.get_engine(), engine)
            self.assertIs(db.get_engine(), engine)
        self.assertEqual(create.call_count, 1)
        self.assertTrue(create.call_args.args[0] == module.settings.MYSQL_DATABASE_URL)
        self.assertEqual(create.call_args.kwargs, {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10, "pool_recycle": 3600})


class DatabaseContractTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.engine = MagicMock()
        self.conn = self.engine.connect.return_value.__enter__.return_value
        self.conn.execute.return_value.rowcount = 1
        functions = [db.update_document_status, db.record_document_log, db.get_all_documents, db.get_app_setting,
                     db.get_active_fast_paths, db.get_active_directories]
        for module in {owner(function) for function in functions}:
            self.stack.enter_context(patch.object(module, "get_engine", return_value=self.engine))
        self.sources = owner(db.get_active_fast_paths)
        self.stack.enter_context(patch.object(self.sources, "_fast_paths_cache", None))
        self.stack.enter_context(patch.object(self.sources, "_directories_cache", None))

    def test_status_update_keeps_whitelist_and_parameter_binding(self):
        module = owner(db.update_document_status)
        with self.assertLogs(module.logger, level="WARNING"):
            db.update_document_status(7, "processing", total_pages=12, processed_pages=2, unexpected="ignored")
        query, params = self.conn.execute.call_args.args
        self.assertEqual(str(query), "UPDATE documents SET status = :status, updated_at = :updated_at, total_pages = :total_pages, processed_pages = :processed_pages WHERE id = :document_id")
        self.assertEqual(params["document_id"], 7)
        self.assertEqual(params["total_pages"], 12)
        self.assertNotIn("unexpected", params)
        self.conn.commit.assert_called_once()

    def test_status_write_error_propagates_without_commit(self):
        self.conn.execute.side_effect = RuntimeError("synthetic database error")
        with self.assertLogs(owner(db.update_document_status).logger, level="ERROR"):
            with self.assertRaises(RuntimeError):
                db.update_document_status(7, "failed")
        self.conn.commit.assert_not_called()

    def test_document_list_preserves_select_columns_and_order(self):
        rows = [{"id": 2, "original_name": "b.pdf"}, {"id": 1, "original_name": "a.pdf"}]
        self.conn.execute.return_value.mappings.return_value.all.return_value = rows
        self.assertEqual(db.get_all_documents(), rows)
        sql = str(self.conn.execute.call_args.args[0])
        self.assertIn("FROM documents ORDER BY created_at DESC", sql)
        self.assertIn("total_pages, total_chunks", sql)

    def test_empty_document_names_skips_engine_and_preserves_alias(self):
        self.assertEqual(db.get_document_names([]), {})
        self.engine.connect.assert_not_called()
        self.assertIs(db.get_document_names_by_ids, db.get_document_names)

    def test_document_names_deduplicate_ids_and_fall_back_from_blank_titles(self):
        rows = [{"id": 1, "title": " Official ", "original_name": "a.pdf"},
                {"id": 2, "title": " ", "original_name": "b.pdf"}]
        self.conn.execute.return_value.mappings.return_value.all.return_value = rows
        self.assertEqual(db.get_document_names([2, 1, 2]), {1: "Official", 2: "b.pdf"})
        self.assertEqual(self.conn.execute.call_args.args[1], {"document_ids": [1, 2]})

    def test_missing_document_returns_none_and_existing_row_keeps_category_fields(self):
        mapped = self.conn.execute.return_value.mappings.return_value
        mapped.fetchone.return_value = None
        self.assertIsNone(db.get_document_by_id(999))
        row = {"id": 1, "category_vision_model": "category-vl", "category_prompt_variables": '{"kata_kunci": ["Operator"]}'}
        mapped.fetchone.return_value = row
        self.assertEqual(db.get_document_by_id(1), row)
        query, params = self.conn.execute.call_args.args
        self.assertIn("LEFT JOIN document_categories c ON d.category_id = c.id", str(query))
        self.assertEqual(params, {"document_id": 1})

    def test_setting_default_applies_only_to_none(self):
        result = self.conn.execute.return_value
        for value in (None, "", 0, False):
            with self.subTest(value=value):
                result.scalar.return_value = value
                self.assertEqual(db.get_app_setting("key", "default"), "default" if value is None else value)

    def test_setting_query_failure_returns_supplied_default(self):
        self.conn.execute.side_effect = RuntimeError("synthetic error")
        with self.assertLogs(owner(db.get_app_setting).logger, level="WARNING"):
            self.assertEqual(db.get_app_setting("key", "default"), "default")

    def test_engine_creation_errors_keep_existing_per_helper_policy(self):
        for function, args in [(db.get_app_setting, ("key", "default")), (db.record_document_log, (1, "progress"))]:
            with self.subTest(function=function.__name__):
                with patch.object(owner(function), "get_engine", side_effect=RuntimeError("engine unavailable")):
                    with self.assertRaisesRegex(RuntimeError, "engine unavailable"):
                        function(*args)
        module = owner(db.get_chatbot_rag_config)
        with patch.object(module, "get_engine", side_effect=RuntimeError("engine unavailable")):
            with self.assertLogs(module.logger, level="WARNING"):
                self.assertEqual(db.get_chatbot_rag_config()["rag_temperature"], 0.2)

    def test_rag_config_preserves_casts_and_case_sensitive_boolean(self):
        self.conn.execute.return_value.fetchall.return_value = [
            ("llm_model_name", "custom"), ("chatbot_name", ""), ("rag_temperature", "0"),
            ("rag_top_k", "5"), ("rag_num_ctx", "6144"), ("rag_citation_enabled", "TRUE"),
        ]
        config = db.get_chatbot_rag_config()
        self.assertEqual(config["llm_model_name"], "custom")
        self.assertEqual(config["chatbot_name"], "")
        self.assertEqual(config["rag_temperature"], 0.0)
        self.assertEqual(config["rag_top_k"], 5)
        self.assertEqual(config["rag_num_ctx"], 6144)
        self.assertFalse(config["rag_citation_enabled"])

    def test_invalid_rag_value_falls_back_to_entire_default_configuration(self):
        self.conn.execute.return_value.fetchall.return_value = [("chatbot_name", "Custom"), ("rag_temperature", "invalid")]
        with self.assertLogs(owner(db.get_chatbot_rag_config).logger, level="WARNING"):
            config = db.get_chatbot_rag_config()
        self.assertEqual(config["chatbot_name"], "Asisten Virtual Diskominfotik")
        self.assertEqual(config["rag_temperature"], 0.2)
        self.assertTrue(config["rag_citation_enabled"])

    def test_fast_path_cache_refreshes_at_five_seconds(self):
        self.conn.execute.return_value.fetchall.return_value = [(1, "general", "Kontak", " KOMINFO, ,Data ", "112", 1)]
        with patch.object(self.sources, "time", SimpleNamespace(time=Mock(side_effect=[100, 104.99, 105]))):
            first = db.get_active_fast_paths()
            self.assertIs(db.get_active_fast_paths(), first)
            self.assertEqual(db.get_active_fast_paths(), first)
        self.assertEqual(first[0]["keywords"], ["kominfo", "data"])
        self.assertEqual(self.conn.execute.call_count, 2)
        self.assertIn("ORDER BY sort_order ASC, id DESC", str(self.conn.execute.call_args.args[0]))

    def test_expired_directory_cache_survives_query_failure(self):
        cached = [{"id": 1, "nama_bidang": "Cached"}]
        self.sources._directories_cache = (100, cached)
        self.conn.execute.side_effect = RuntimeError("unavailable")
        with patch.object(self.sources, "time", SimpleNamespace(time=Mock(return_value=200))):
            with self.assertLogs(self.sources.logger, level="WARNING"):
                self.assertIs(db.get_active_directories(), cached)

    def test_empty_cache_and_failed_database_return_empty_source_lists(self):
        self.conn.execute.side_effect = RuntimeError("unavailable")
        with self.assertLogs(self.sources.logger, level="WARNING"):
            self.assertEqual(db.get_active_directories(), [])
            self.assertEqual(db.get_active_fast_paths(), [])

    def test_directory_tasks_parse_json_lines_and_existing_lists(self):
        rows = [(1, "A", " DATA ", "C", "a@example.test", "Layanan", '["Publikasi"]', None, 1),
                (2, "B", "data", "C", "b@example.test", "Layanan", "Satu\nDua", "Jam khusus", 2),
                (3, "C", "data", "C", "c@example.test", "Layanan", ["Tiga"], None, 3)]
        self.conn.execute.return_value.fetchall.return_value = rows
        result = db.get_active_directories()
        self.assertEqual([item["daftar_tugas"] for item in result], [["Publikasi"], ["Satu", "Dua"], ["Tiga"]])
        self.assertEqual(result[0]["keywords"], ["data"])
        self.assertEqual(result[0]["jam_operasional"], "Senin - Jumat (08:00 - 16:45 WIB)")
        self.assertIn("ORDER BY sort_order ASC, id ASC", str(self.conn.execute.call_args.args[0]))

    def test_log_debounce_updates_changed_details_without_duplicate_insert(self):
        module = owner(db.record_document_log)
        now = datetime(2026, 10, 23, 12)
        self.conn.execute.return_value.mappings.return_value.fetchone.return_value = {"id": 5, "action": "progress", "details": "old", "created_at": now - timedelta(seconds=10)}
        with patch.object(module, "datetime") as clock:
            clock.utcnow.return_value = now
            db.record_document_log(1, "progress", "new")
        self.assertEqual(self.conn.execute.call_count, 2)
        self.assertEqual(str(self.conn.execute.call_args.args[0]), "UPDATE document_logs SET details = :details WHERE id = :id")
        self.assertEqual(self.conn.execute.call_args.args[1], {"details": "new", "id": 5})

    def test_identical_log_within_debounce_skips_write_and_commit(self):
        module = owner(db.record_document_log)
        now = datetime(2026, 10, 23, 12)
        self.conn.execute.return_value.mappings.return_value.fetchone.return_value = {"id": 5, "action": "progress", "details": "same", "created_at": now}
        with patch.object(module, "datetime") as clock:
            clock.utcnow.return_value = now
            db.record_document_log(1, "progress", "same")
        self.assertEqual(self.conn.execute.call_count, 1)
        self.conn.commit.assert_not_called()

    def test_log_query_failure_is_suppressed(self):
        self.conn.execute.side_effect = RuntimeError("synthetic error")
        with self.assertLogs(owner(db.record_document_log).logger, level="WARNING"):
            self.assertIsNone(db.record_document_log(1, "progress"))


if __name__ == "__main__":
    unittest.main()
