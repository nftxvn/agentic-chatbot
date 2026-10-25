"""Client boundaries for embedded and explicitly shared Chroma deployments.

Factories are mocked: no Chroma server, files, model, or database is accessed.
"""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from app.services.embeddings import vector_store


class VectorStoreClientTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(vector_store, "_chroma_collection", None))
        self.stack.enter_context(patch.dict("os.environ", {
            "CHROMA_HTTP_HOST": "", "CHROMA_HTTP_PORT": "8000", "CHROMA_HTTP_SSL": "false",
        }))
        self.local = self.stack.enter_context(patch.object(vector_store.chromadb, "PersistentClient"))
        self.remote = self.stack.enter_context(patch.object(vector_store.chromadb, "HttpClient"))
        self.collection = Mock()
        self.collection.count.return_value = 5
        for factory in (self.local, self.remote):
            factory.return_value.get_or_create_collection.return_value = self.collection

    def test_empty_http_host_preserves_local_path_and_cosine_collection(self):
        with patch.dict("os.environ", {"CHROMA_HTTP_HOST": "  ", "CHROMA_HTTP_PORT": "invalid"}):
            result = vector_store.get_chroma_collection()
        self.assertIs(result, self.collection)
        self.remote.assert_not_called()
        self.assertEqual(self.local.call_args.kwargs["path"], vector_store.settings.CHROMA_PERSIST_DIR)
        self.assertFalse(self.local.call_args.kwargs["settings"].anonymized_telemetry)
        self.local.return_value.get_or_create_collection.assert_called_once_with(
            name="documents", metadata={"hnsw:space": "cosine"},
        )

    def test_explicit_http_host_uses_shared_server_without_local_persistence(self):
        with patch.dict("os.environ", {"CHROMA_HTTP_HOST": " 127.0.0.1 ", "CHROMA_HTTP_PORT": "18090", "CHROMA_HTTP_SSL": "true"}):
            result = vector_store.get_chroma_collection()
        self.assertIs(result, self.collection)
        self.local.assert_not_called()
        options = self.remote.call_args.kwargs
        self.assertEqual((options["host"], options["port"], options["ssl"]), ("127.0.0.1", 18090, True))
        self.assertFalse(options["settings"].anonymized_telemetry)
        self.remote.return_value.get_or_create_collection.assert_called_once_with(
            name="documents", metadata={"hnsw:space": "cosine"},
        )

    def test_http_defaults_use_port_8000_without_ssl(self):
        with patch.dict("os.environ", {"CHROMA_HTTP_HOST": "chroma"}):
            vector_store.get_chroma_collection()
        self.assertEqual(self.remote.call_args.kwargs["port"], 8000)
        self.assertFalse(self.remote.call_args.kwargs["ssl"])

    def test_http_ssl_accepts_normal_boolean_environment_spellings(self):
        for value, expected in [("1", True), (" YES ", True), ("on", True), ("false", False), ("0", False), ("OFF", False)]:
            with self.subTest(value=value), patch.object(vector_store, "_chroma_collection", None), \
                    patch.dict("os.environ", {"CHROMA_HTTP_HOST": "chroma", "CHROMA_HTTP_SSL": value}):
                vector_store.get_chroma_collection()
                self.assertIs(self.remote.call_args.kwargs["ssl"], expected)

    def test_http_factory_failure_propagates_without_local_fallback_or_cached_collection(self):
        self.remote.side_effect = RuntimeError("synthetic server unavailable")
        with patch.dict("os.environ", {"CHROMA_HTTP_HOST": "chroma"}), \
                self.assertRaisesRegex(RuntimeError, "synthetic server unavailable"):
            vector_store.get_chroma_collection()
        self.local.assert_not_called()
        self.assertIsNone(vector_store._chroma_collection)

    def test_http_collection_failure_does_not_switch_to_an_empty_local_corpus(self):
        self.remote.return_value.get_or_create_collection.side_effect = RuntimeError("synthetic access denied")
        with patch.dict("os.environ", {"CHROMA_HTTP_HOST": "chroma"}), \
                self.assertRaisesRegex(RuntimeError, "synthetic access denied"):
            vector_store.get_chroma_collection()
        self.local.assert_not_called()
        self.assertIsNone(vector_store._chroma_collection)

    def test_cached_collection_is_reused_without_creating_another_client(self):
        with patch.dict("os.environ", {"CHROMA_HTTP_HOST": "chroma"}):
            first = vector_store.get_chroma_collection()
            second = vector_store.get_chroma_collection()
        self.assertIs(first, second)
        self.remote.assert_called_once()
        self.remote.return_value.get_or_create_collection.assert_called_once()


if __name__ == "__main__":
    unittest.main()
