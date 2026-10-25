"""Kontrak router dokumen/ekstraksi dengan database, broker, dan OCR tiruan."""

import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi.testclient import TestClient

from app.routers import documents, ekstraksi
from app.services import ekstraksi_bertahap as eb


def namespace(router, name):
    """The same contracts run before and after moving endpoint implementations."""
    return getattr(router, name, router)


class CancellationRegressionTest(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_fences_only_this_generation_without_purge_or_model_unload(self):
        from app.celery_app import celery_app
        from app.services.document_workflows import document_lifecycle

        order = []
        with patch.object(document_lifecycle, "cancel_operation", side_effect=lambda *a: order.append("fence") or "old-operation") as cancel, \
                patch.object(document_lifecycle, "drain_cleanups", side_effect=lambda **kw: order.append("cleanup")) as cleanup, \
                patch.object(celery_app.control, "purge") as purge, patch("httpx.AsyncClient") as client:
            result = await documents.cancel_document_processing(7, _token="synthetic")

        self.assertEqual(order, ["fence", "cleanup"])
        cancel.assert_called_once_with(7)
        cleanup.assert_called_once_with(document_id=7, due_only=False)
        purge.assert_not_called()
        client.assert_not_called()
        self.assertEqual(result, {
            "document_id": 7, "status": "cancelled",
            "message": "Permintaan pembatalan dokumen diterima. Operasi aktif berhenti pada batas aman berikutnya.",
        })

    async def test_cancel_keeps_durable_fence_when_vector_cleanup_is_unavailable(self):
        from app.services.document_workflows import document_lifecycle
        with patch.object(document_lifecycle, "cancel_operation", return_value="old-operation"), \
                patch.object(document_lifecycle, "drain_cleanups", side_effect=RuntimeError("offline")):
            with self.assertLogs(document_lifecycle.logger, level="WARNING"):
                result = await documents.cancel_document_processing(7, _token="synthetic")
        self.assertEqual(result["status"], "cancelled")

    async def test_cancel_does_not_remove_already_completed_corpus(self):
        from app.services.document_workflows import document_lifecycle
        with patch.object(document_lifecycle, "cancel_operation", return_value=None), \
                patch.object(document_lifecycle, "drain_cleanups") as cleanup:
            await documents.cancel_document_processing(7, _token="synthetic")
        cleanup.assert_not_called()

    async def test_cancel_database_failure_does_not_acknowledge_or_cleanup(self):
        from app.services.document_workflows import document_lifecycle
        with patch.object(document_lifecycle, "cancel_operation", side_effect=RuntimeError("database unavailable")), \
                patch.object(document_lifecycle, "drain_cleanups") as cleanup:
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                await documents.cancel_document_processing(7, _token="synthetic")
        cleanup.assert_not_called()

    async def test_sse_deduplicates_status_and_page_count_then_closes_on_pause(self):
        storage = Mock()
        storage.keadaan.side_effect = [
            {"status": "berjalan", "halaman_selesai": 1, "halaman_total": 3, "persen": 33},
            {"status": "berjalan", "halaman_selesai": 1, "halaman_total": 3, "persen": 34},
            {"status": "jeda", "halaman_selesai": 1, "halaman_total": 3, "persen": 34},
        ]
        control = namespace(ekstraksi, "extraction_control")
        with patch.object(control, "get_document_by_id", return_value={"file_path": "synthetic.pdf"}), \
                patch.object(eb, "PenyimpananMySQL", return_value=storage), \
                patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
            response = await ekstraksi.aliran_ekstraksi(7, _token="synthetic")
            events = [json.loads(item) async for item in response.body_iterator]
        self.assertEqual([event["type"] for event in events], ["kemajuan", "kemajuan", "selesai"])
        self.assertEqual(events[-1]["content"], "jeda")
        self.assertEqual(sleep.await_count, 2)
        sleep.assert_awaited_with(2.0)


class DocumentHttpContractTest(unittest.TestCase):
    def setUp(self):
        from app.main import app

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(documents.settings, "INTERNAL_API_TOKEN", "document-test-token"))
        self.queries = namespace(documents, "document_queries")
        self.page_views = namespace(documents, "document_pages")
        self.lifecycle = namespace(documents, "document_lifecycle")
        self.control = namespace(ekstraksi, "extraction_control")
        self.begin = self.stack.enter_context(patch.object(self.control, "start_operation", return_value="synthetic"))
        self.lookup = Mock(return_value={"id": 7, "status": "pending", "file_path": "synthetic.pdf"})
        for module in {self.queries, self.page_views, self.control}:
            self.stack.enter_context(patch.object(module, "get_document_by_id", self.lookup))
        self.storage = MagicMock()
        self.stack.enter_context(patch.object(eb, "PenyimpananMySQL", return_value=self.storage))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.headers = {"Authorization": "Bearer document-test-token"}

    def get(self, path):
        return self.client.get(path, headers=self.headers)

    def post(self, path, payload=None):
        return self.client.post(path, headers=self.headers, json=payload or {})

    def test_protected_endpoints_reject_credentials_before_database_or_storage(self):
        for method, path, body in [
            ("GET", "/api/docs", None), ("GET", "/api/docs/7/status", None),
            ("GET", "/api/docs/7/pages/1/image", None), ("GET", "/api/docs/7/pages/dimensions", None),
            ("POST", "/api/docs/7/extraction", {}), ("GET", "/api/docs/7/pages", None),
            ("PUT", "/api/docs/7/pages/1", {"text": "Teks"}), ("POST", "/api/docs/7/embed", {}),
        ]:
            with self.subTest(path=path):
                response = self.client.request(method, path, json=body)
                self.assertEqual(response.status_code, 401)
        self.lookup.assert_not_called()
        self.assertEqual(self.storage.mock_calls, [])

    def test_document_listing_and_status_keep_response_models(self):
        with patch.object(self.queries, "get_all_documents", return_value=[{"id": 7, "status": "completed", "original_name": "sop.pdf"}]):
            response = self.get("/api/docs")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["documents"][0]["original_name"], "sop.pdf")
        self.lookup.return_value = {"id": 7, "status": "completed", "total_pages": 2}
        self.assertEqual(self.get("/api/docs/7/status").json()["total_pages"], 2)

    def test_missing_document_returns_404_before_extraction_or_editor_operations(self):
        self.lookup.return_value = None
        for method, path, payload in [
            ("POST", "/api/docs/7/extraction", {}), ("GET", "/api/docs/7/pages", None),
            ("PUT", "/api/docs/7/pages/1", {"text": " "}), ("POST", "/api/docs/7/embed", {}),
        ]:
            with self.subTest(path=path):
                response = self.client.request(method, path, headers=self.headers, json=payload)
                self.assertEqual(response.status_code, 404)
        self.assertEqual(self.storage.mock_calls, [])

    def test_start_resolves_category_aliases_then_clears_pause_before_enqueue(self):
        self.lookup.return_value.update({
            "category_vision_prompt": "Kategori", "category_vision_model": " category-vl ",
            "category_prompt_variables": json.dumps({"kata_kunci": ["Kepala", "Operator"], "custom_prompts": {"dasar": "Instruksi"}}),
        })
        order = []
        self.storage.batalkan_jeda.side_effect = lambda *a: order.append("clear-pause")
        with patch("app.tasks.ekstraksi.ekstrak_dokumen_task.delay", side_effect=lambda *a, **k: order.append("enqueue")) as delay:
            response = self.post("/api/docs/7/extraction", {"maks_halaman": 0})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"document_id": 7, "status": "antre"})
        self.assertEqual(order, ["clear-pause", "enqueue"])
        delay.assert_called_once_with(7, "synthetic.pdf", 0, category_prompt="Kategori", job_titles="Kepala, Operator", vision_model="category-vl", custom_prompts={"dasar": "Instruksi"}, _operation_token="synthetic")
        self.begin.assert_called_once_with(7, kind="extraction")

    def test_start_explicit_values_override_category_defaults_and_malformed_json_falls_back(self):
        self.lookup.return_value.update({"category_vision_prompt": "DB", "category_prompt_variables": "not-json"})
        with patch("app.tasks.ekstraksi.ekstrak_dokumen_task.delay") as delay:
            response = self.post("/api/docs/7/extraction", {"category_prompt": "Request", "job_titles": "Admin", "vision_model": " mock-vl ", "custom_prompts": {"dasar": "Custom"}})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(delay.call_args.kwargs, {"category_prompt": "Request", "job_titles": "Admin", "vision_model": "mock-vl", "custom_prompts": {"dasar": "Custom"}, "_operation_token": "synthetic"})

    def test_pause_and_initial_status_keep_acknowledgement_and_default_fields(self):
        self.assertEqual(self.post("/api/docs/7/extraction/pause").json(), {"document_id": 7, "jeda_diminta": True})
        self.storage.minta_jeda.assert_called_once_with(7)
        self.storage.keadaan.return_value = None
        self.assertEqual(self.get("/api/docs/7/extraction").json(), {
            "document_id": 7, "status": "antre", "jeda_diminta": False,
            "halaman_total": 0, "halaman_selesai": 0, "persen": 0, "pesan": None,
        })

    def test_page_text_preserves_whitespace_and_empty_correction_is_rejected(self):
        text = "  # Judul\n\nIsi halaman é  "
        response = self.client.put("/api/docs/7/pages/2", headers=self.headers, json={"text": text})
        self.assertEqual(response.status_code, 200)
        self.storage.simpan_halaman.assert_called_once_with(7, 2, text)
        self.storage.simpan_halaman.reset_mock()
        self.assertEqual(self.client.put("/api/docs/7/pages/2", headers=self.headers, json={"text": " \n "}).status_code, 400)
        self.storage.simpan_halaman.assert_not_called()

    def test_suspicious_page_filter_keeps_reason_only_response(self):
        self.storage.teks_terkumpul.return_value = [{"page_number": 2, "text": "rusak"}, {"page_number": 3, "text": "baik"}]
        with patch("app.services.pdf_processor._header_sop_tidak_lengkap", side_effect=lambda t: t == "rusak"), \
                patch("app.services.pdf_processor._bagian_kepala_hilang", return_value="Nama SOP"):
            response = self.get("/api/docs/7/pages?perlu_diperiksa=true")
        self.assertEqual(response.json(), {"document_id": 7, "jumlah": 1, "halaman": [{"page_number": 2, "alasan": "Nama SOP hilang"}]})

    def test_preview_body_zero_overlap_is_preserved_while_query_zero_uses_existing_default(self):
        self.storage.teks_terkumpul.return_value = [{"page_number": 1, "text": "Isi dokumen"}]
        with patch("app.services.embedding_service.derive_document_title", return_value="Judul"), \
                patch("app.services.embedding_service.chunk_text_hierarchical", return_value=([{"text": "parent"}], [])) as chunks:
            body = self.post("/api/docs/7/chunks/preview", {"parent_chunk_overlap": 0, "child_chunk_overlap": 0, "strategy": "faq"})
            self.assertEqual(body.status_code, 200)
            self.assertEqual(chunks.call_args.kwargs["parent_chunk_overlap"], 0)
            self.assertEqual(chunks.call_args.kwargs["strategy"], "faq")
            query = self.get("/api/docs/7/chunks/preview?parent_chunk_overlap=0&child_chunk_overlap=0")
            self.assertEqual(query.status_code, 200)
            self.assertEqual(chunks.call_args.kwargs["parent_chunk_overlap"], 200)
            self.assertEqual(chunks.call_args.kwargs["child_chunk_overlap"], 50)

    def test_preview_without_pages_returns_not_ready_without_chunking(self):
        self.storage.teks_terkumpul.return_value = []
        with patch("app.services.embedding_service.chunk_text_hierarchical") as chunks:
            self.assertEqual(self.get("/api/docs/7/chunks/preview").json(), {"document_id": 7, "induk": [], "anak": [], "siap": False})
        chunks.assert_not_called()

    def test_embedding_rejects_incomplete_extraction_and_promotes_complete_running_state(self):
        with patch("app.tasks.ekstraksi.potong_dan_embed_task.delay") as delay:
            self.storage.keadaan.return_value = {"status": "berjalan", "halaman_selesai": 1, "halaman_total": 2}
            self.assertEqual(self.post("/api/docs/7/embed").status_code, 409)
            delay.assert_not_called()
            self.storage.keadaan.return_value = {"status": "berjalan", "halaman_selesai": 2, "halaman_total": 2}
            response = self.post("/api/docs/7/embed", {"child_chunk_overlap": 0})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"document_id": 7, "status": "diantrekan"})
        self.storage.catat_status.assert_called_once_with(7, "menunggu_koreksi")
        self.assertEqual(self.storage.catat_kemajuan_embed.call_args.kwargs["persen"], 5)
        self.assertEqual(delay.call_args.args[1]["child_chunk_overlap"], 0)
        self.assertEqual(delay.call_args.kwargs["_operation_token"], "synthetic")
        self.begin.assert_called_once_with(7, kind="embedding")

    def test_page_image_keeps_binary_body_dimensions_cache_and_etag(self):
        with patch.object(documents.pdf_processor, "render_halaman", return_value=(b"synthetic-jpeg", 800, 1130)) as render, \
                patch("pathlib.Path.stat", return_value=SimpleNamespace(st_mtime=123)):
            response = self.get("/api/docs/7/pages/2/image?zoom=2")
        self.assertEqual(response.content, b"synthetic-jpeg")
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.headers["etag"], '"7-2-2.0-123"')
        self.assertEqual(response.headers["x-lebar-piksel"], "800")
        self.assertEqual(response.headers["cache-control"], "public, max-age=31536000, immutable")
        render.assert_called_once_with("synthetic.pdf", 2, 2.0)

    def test_render_error_mapping_keeps_zoom_400_page_404_and_masked_internal_500(self):
        for error, status in [(ValueError("zoom terlarang"), 400), (ValueError("halaman tidak ada"), 404),
                              (FileNotFoundError("private path"), 404), (RuntimeError("synthetic-private-detail"), 500)]:
            with self.subTest(error=type(error).__name__), patch.object(documents.pdf_processor, "render_halaman", side_effect=error):
                response = self.get("/api/docs/7/pages/2/image?zoom=2")
                self.assertEqual(response.status_code, status)
                self.assertNotIn("synthetic-private-detail", response.text)

    def test_vector_counts_keep_total_metadata_count_and_integer_document_ids(self):
        collection = Mock()
        collection.get.return_value = {"metadatas": [{"document_id": "7"}, None, {}, {"document_id": 7}, {"document_id": 8}]}
        with patch("app.services.embedding_service.get_chroma_collection", return_value=collection):
            self.assertEqual(self.get("/api/docs/vector-counts").json(), {"total_vectors": 5, "counts": {"7": 2, "8": 1}})

    def test_vector_delete_still_succeeds_when_local_extraction_cleanup_fails(self):
        self.storage.reset_ekstraksi.side_effect = RuntimeError("synthetic cleanup failure")
        with patch.object(self.lifecycle, "request_document_cleanup") as enqueue, \
                patch.object(self.lifecycle, "drain_cleanups", return_value={"failed": 0, "deleted_vectors": 4}):
            response = self.client.delete("/api/docs/7", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_vectors"], 4)
        enqueue.assert_called_once_with(7)

    def test_full_cleanup_still_pending_returns_503_without_dispatching_new_work(self):
        from app.services.document_operations import DocumentCleanupPending
        self.begin.side_effect = DocumentCleanupPending("cleanup pending")
        with patch("app.services.vector_cleanup.drain_cleanups", return_value={"failed": 1}), \
                patch("app.tasks.ekstraksi.ekstrak_dokumen_task.delay") as dispatch:
            response = self.post("/api/docs/7/extraction")
        self.assertEqual(response.status_code, 503)
        self.assertIn("Pembersihan vektor", response.json()["detail"])
        dispatch.assert_not_called()

    def test_start_retries_after_full_cleanup_recovers_and_dispatches_new_generation(self):
        from app.services.document_operations import DocumentCleanupPending
        self.begin.side_effect = [DocumentCleanupPending("cleanup pending"), "recovered-generation"]
        with patch("app.services.vector_cleanup.drain_cleanups", return_value={"failed": 0}) as drain, \
                patch("app.tasks.ekstraksi.ekstrak_dokumen_task.delay") as dispatch:
            response = self.post("/api/docs/7/extraction")
        self.assertEqual(response.status_code, 202)
        drain.assert_called_once_with(document_id=7, due_only=False)
        self.assertEqual(dispatch.call_args.kwargs["_operation_token"], "recovered-generation")


class WorkerWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        from app.tasks import ekstraksi as tasks
        from app.tasks.process_document import process_document_task

        self.tasks = tasks
        self.legacy = process_document_task
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.storage = MagicMock()
        self.storage.dokumen_ada.return_value = True
        self.guard = self.stack.enter_context(patch("app.services.document_operations.OperationGuard")).return_value
        self.stack.enter_context(patch.object(eb, "PenyimpananMySQL", return_value=self.storage))
        self.update = self.stack.enter_context(patch("app.database.update_document_status"))
        self.stack.enter_context(patch("app.database.record_document_log"))
        self.stack.enter_context(patch("app.services.document_processor.detect_document_type", return_value="text"))
        self.stack.enter_context(patch("app.services.document_processor.get_total_pages", return_value=1))
        self.extract = self.stack.enter_context(patch("app.services.document_processor.extract_document", return_value=[]))

    def test_legacy_empty_document_completes_without_embedding(self):
        self.storage.teks_terkumpul.return_value = []
        with patch("app.services.embedding_service.embed_and_store_hierarchical") as embed:
            result = self.legacy.run(7, "synthetic.pdf", "new", _operation_token="synthetic")
        self.assertEqual(result["total_chunks"], 0)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.update.call_args.kwargs["total_pages"], 0)
        embed.assert_not_called()

    def test_legacy_overwrite_prefers_saved_corrections_and_deletes_only_after_chunking(self):
        self.extract.return_value = [{"page_number": 1, "text": "OCR"}]
        corrected = [{"page_number": 1, "text": "Koreksi manual"}]
        self.storage.teks_terkumpul.return_value = corrected
        order = []
        with patch("app.services.embedding_service.chunk_text_hierarchical", side_effect=lambda pages: (order.append("chunk") or ([{"text": "parent"}], [{"text": "child"}]))) as chunk, \
                patch("app.services.embedding_service.delete_document_vectors", side_effect=lambda *a, **k: order.append("delete") or 4), \
                patch("app.services.embedding_service.embed_and_store_hierarchical", side_effect=lambda *a, **k: order.append("embed") or 2):
            result = self.legacy.run(7, "synthetic.pdf", "overwrite", _operation_token="synthetic")
        chunk.assert_called_once_with(corrected)
        self.assertEqual(order, ["chunk", "delete", "embed"])
        self.assertEqual(result, {"document_id": 7, "status": "completed", "pdf_type": "text", "total_pages": 1, "total_chunks": 2})

    def test_legacy_retry_keeps_linear_countdown_before_final_failure(self):
        error = RuntimeError("synthetic extraction failure")
        self.extract.side_effect = error
        self.legacy.push_request(retries=1)
        self.addCleanup(self.legacy.pop_request)
        with patch.object(self.legacy, "retry", side_effect=RuntimeError("retry scheduled")) as retry:
            with self.assertLogs("app.tasks.process_document", level="ERROR"), self.assertRaisesRegex(RuntimeError, "retry scheduled"):
                self.legacy.run(7, "synthetic.pdf", "new", _operation_token="synthetic")
        retry.assert_called_once_with(exc=error, countdown=120, kwargs={"_operation_token": "synthetic"})
        self.assertNotIn("failed", [call.kwargs["status"] for call in self.update.call_args_list])

    def test_legacy_exhausted_retry_records_truncated_error_and_reraises(self):
        self.extract.side_effect = RuntimeError("e" * 600)
        self.legacy.push_request(retries=3)
        self.addCleanup(self.legacy.pop_request)
        with patch.object(self.legacy, "retry") as retry:
            with self.assertLogs("app.tasks.process_document", level="ERROR"), self.assertRaises(RuntimeError):
                self.legacy.run(7, "synthetic.pdf", "new", _operation_token="synthetic")
        self.assertEqual(self.update.call_args.kwargs, {"status": "failed", "error_message": "e" * 500, "operation_token": "synthetic"})
        retry.assert_not_called()

    def test_image_removed_during_ocr_returns_cancelled_before_writing_pages(self):
        self.storage.dokumen_ada.side_effect = [True, False]
        self.extract.return_value = [{"page_number": 1, "text": "Gambar"}]
        result = self.tasks.ekstrak_dokumen_task.run(7, "synthetic.png", vision_model="mock-vl", _operation_token="synthetic")
        self.assertEqual(result, {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"})
        self.storage.simpan_halaman.assert_not_called()
        self.update.assert_not_called()

    def test_celery_entrypoints_keep_shared_app_names_and_retry_configuration(self):
        from app.celery_app import celery_app
        for task, name in [(self.legacy, "process_document_task"),
                           (self.tasks.ekstrak_dokumen_task, "ekstrak_dokumen_task"),
                           (self.tasks.potong_dan_embed_task, "potong_dan_embed_task")]:
            with self.subTest(name=name):
                self.assertIs(task.app, celery_app)
                self.assertEqual(task.name, name)
                self.assertEqual(task.max_retries, 3)
                self.assertEqual(task.default_retry_delay, 60)


if __name__ == "__main__":
    unittest.main()
