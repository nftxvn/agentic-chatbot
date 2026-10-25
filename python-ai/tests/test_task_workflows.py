"""Kontrak batas worker: penghentian dokumen, penyelesaian OCR, dan retry.

Semua database, OCR, embedding, serta penjadwalan task diganti mock.
"""

import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from app.tasks import ekstraksi as tasks
from app.services.document_operations import DocumentOperationCancelled


class TaskWorkflowBoundaryTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.guard = MagicMock()
        self.stack.enter_context(patch("app.services.document_operations.OperationGuard", return_value=self.guard))
        self.storage = Mock()
        self.storage.dokumen_ada.return_value = True
        self.storage.teks_terkumpul.return_value = [{"page_number": 1, "text": "Koreksi"}]
        self.stack.enter_context(patch.object(tasks.eb, "PenyimpananMySQL", return_value=self.storage))
        self.update = self.stack.enter_context(patch("app.database.update_document_status"))
        self.log = self.stack.enter_context(patch("app.database.record_document_log"))

    def test_completed_pdf_runs_cross_page_cleanup_before_review_status(self):
        progress = SimpleNamespace(status=tasks.eb.STATUS_SELESAI, halaman_total=2)
        pdf = MagicMock()
        pdf.__len__.return_value = 2
        order = []
        self.storage.catat_status.side_effect = lambda *a: order.append("review")
        with patch("fitz.open") as open_pdf, \
                patch("app.services.pdf_processor._resolve_pdf_path", return_value="synthetic.pdf"), \
                patch.object(tasks.eb, "ekstrak_bertahap", return_value=progress), \
                patch.object(tasks, "_rapikan_lintas_halaman", side_effect=lambda *a: order.append("cleanup")) as cleanup:
            open_pdf.return_value.__enter__.return_value = pdf
            result = tasks.ekstrak_dokumen_task.run(7, "synthetic.pdf", _operation_token="synthetic")
        self.assertEqual(result, {"status": "menunggu_koreksi", "halaman": 2})
        self.assertEqual(order, ["cleanup", "review"])
        cleanup.assert_called_once_with(7, self.storage)
        self.assertEqual(self.update.call_args.kwargs["status"], "menunggu_koreksi")
        self.assertEqual(self.log.call_args.kwargs["action"], "ocr_completed")

    def test_image_retry_exhaustion_records_failure_then_uses_task_retry(self):
        task = tasks.ekstrak_dokumen_task
        task.push_request(retries=3)
        self.addCleanup(task.pop_request)
        error = RuntimeError("synthetic vision failure")
        with patch("app.services.document_processor.extract_document", side_effect=error), \
                patch.object(task, "retry", side_effect=RuntimeError("retry exhausted")) as retry:
            with self.assertRaisesRegex(RuntimeError, "retry exhausted"):
                task.run(7, "synthetic.png", _operation_token="synthetic")
        self.storage.catat_status.assert_called_once_with(7, tasks.eb.STATUS_GAGAL, str(error))
        self.assertEqual(self.update.call_args.kwargs, {
            "status": "failed", "error_message": str(error), "total_pages": 1, "processed_pages": 0, "operation_token": "synthetic",
        })
        retry.assert_called_once_with(exc=error, kwargs={"_operation_token": "synthetic"})

    def test_deleted_during_chunking_does_not_delete_or_write_vectors(self):
        self.storage.dokumen_ada.side_effect = [True, False]
        with patch("app.services.embedding_service.derive_document_title", return_value="Judul"), \
                patch("app.services.embedding_service.chunk_text_hierarchical", return_value=([{}], [{}])), \
                patch("app.services.embedding_service.delete_document_vectors") as delete, \
                patch("app.services.embedding_service.embed_and_store_hierarchical") as store:
            result = tasks.potong_dan_embed_task.run(7, _operation_token="synthetic")
        self.assertEqual(result, {"status": "dibatalkan", "pesan": "Dokumen telah dihapus"})
        delete.assert_not_called()
        store.assert_not_called()
        self.update.assert_not_called()

    def test_embedding_progress_stops_writing_after_document_is_deleted(self):
        self.storage.dokumen_ada.side_effect = [True, True, False, False]

        def embed(*args, progress_callback, operation_guard):
            progress_callback(75, "synthetic progress")
            return 2

        with patch("app.services.embedding_service.derive_document_title", return_value="Judul"), \
                patch("app.services.embedding_service.chunk_text_hierarchical", return_value=([{}], [{}])), \
                patch("app.services.embedding_service.delete_document_vectors"), \
                patch("app.services.embedding_service.embed_and_store_hierarchical", side_effect=embed):
            result = tasks.potong_dan_embed_task.run(7, _operation_token="synthetic")
        self.assertEqual(result["status"], "dibatalkan")
        self.assertEqual([c.kwargs["persen"] for c in self.storage.catat_kemajuan_embed.call_args_list], [10, 25])
        self.update.assert_not_called()
        self.log.assert_not_called()

    def test_cancel_during_image_ocr_discards_result_without_retry_or_status_overwrite(self):
        active = [True]
        def checkpoint():
            if not active[0]:
                raise DocumentOperationCancelled("cancelled generation")
        def extract(*args, **kwargs):
            active[0] = False
            return [{"page_number": 1, "text": "obsolete OCR"}]
        self.guard.checkpoint.side_effect = checkpoint
        with patch("app.services.document_processor.extract_document", side_effect=extract), \
                patch.object(tasks.ekstrak_dokumen_task, "retry") as retry:
            result = tasks.ekstrak_dokumen_task.run(7, "synthetic.png", _operation_token="synthetic")
        self.assertEqual(result["status"], "dibatalkan")
        self.storage.simpan_halaman.assert_not_called()
        self.storage.catat_status.assert_not_called()
        self.update.assert_not_called()
        self.log.assert_not_called()
        retry.assert_not_called()

    def test_cancel_concurrent_with_image_failure_does_not_schedule_retry(self):
        active = [True]
        def checkpoint():
            if not active[0]:
                raise DocumentOperationCancelled("cancelled generation")
        def extract(*args, **kwargs):
            active[0] = False
            raise RuntimeError("model request ended after cancellation")
        self.guard.checkpoint.side_effect = checkpoint
        with patch("app.services.document_processor.extract_document", side_effect=extract), \
                patch.object(tasks.ekstrak_dokumen_task, "retry") as retry:
            result = tasks.ekstrak_dokumen_task.run(7, "synthetic.png", _operation_token="synthetic")
        self.assertEqual(result["status"], "dibatalkan")
        self.storage.catat_status.assert_not_called()
        self.update.assert_not_called()
        retry.assert_not_called()

    def test_cancel_during_chunking_does_not_replace_vectors(self):
        active = [True]
        def checkpoint():
            if not active[0]:
                raise DocumentOperationCancelled("superseded by resume")
        def chunks(*args, **kwargs):
            active[0] = False
            return ([{}], [{}])
        self.guard.checkpoint.side_effect = checkpoint
        with patch("app.services.embedding_service.derive_document_title", return_value="Judul"), \
                patch("app.services.embedding_service.chunk_text_hierarchical", side_effect=chunks), \
                patch("app.services.embedding_service.delete_document_vectors") as delete, \
                patch("app.services.embedding_service.embed_and_store_hierarchical") as store, \
                patch.object(tasks.potong_dan_embed_task, "retry") as retry:
            result = tasks.potong_dan_embed_task.run(7, _operation_token="synthetic")
        self.assertEqual(result["status"], "dibatalkan")
        delete.assert_not_called()
        store.assert_not_called()
        self.update.assert_not_called()
        retry.assert_not_called()

    def test_cancel_after_embedding_does_not_report_completion(self):
        active = [True]
        def checkpoint():
            if not active[0]:
                raise DocumentOperationCancelled("cancelled generation")
        def embed(*args, **kwargs):
            active[0] = False
            return 2
        self.guard.checkpoint.side_effect = checkpoint
        with patch("app.services.embedding_service.derive_document_title", return_value="Judul"), \
                patch("app.services.embedding_service.chunk_text_hierarchical", return_value=([{}], [{}])), \
                patch("app.services.embedding_service.delete_document_vectors"), \
                patch("app.services.embedding_service.embed_and_store_hierarchical", side_effect=embed), \
                patch.object(tasks.potong_dan_embed_task, "retry") as retry:
            result = tasks.potong_dan_embed_task.run(7, _operation_token="synthetic")
        self.assertEqual(result["status"], "dibatalkan")
        self.assertNotIn(100, [c.kwargs["persen"] for c in self.storage.catat_kemajuan_embed.call_args_list])
        self.update.assert_not_called()
        self.log.assert_not_called()
        retry.assert_not_called()

    def test_cancel_before_batch_continuation_does_not_requeue(self):
        active = [True]
        def checkpoint():
            if not active[0]:
                raise DocumentOperationCancelled("cancelled generation")
        def extract(*args, **kwargs):
            active[0] = False
            return SimpleNamespace(status=tasks.eb.STATUS_BERJALAN, halaman_total=2, halaman_selesai=1)
        self.guard.checkpoint.side_effect = checkpoint
        pdf = MagicMock()
        pdf.__len__.return_value = 2
        with patch("fitz.open") as open_pdf, \
                patch("app.services.pdf_processor._resolve_pdf_path", return_value="synthetic.pdf"), \
                patch.object(tasks.eb, "ekstrak_bertahap", side_effect=extract), \
                patch.object(tasks.ekstrak_dokumen_task, "delay") as delay:
            open_pdf.return_value.__enter__.return_value = pdf
            result = tasks.ekstrak_dokumen_task.run(7, "synthetic.pdf", _operation_token="synthetic")
        self.assertEqual(result["status"], "dibatalkan")
        delay.assert_not_called()
        self.storage.catat_status.assert_not_called()

    def test_embedding_retry_preserves_operation_and_request_options(self):
        task = tasks.potong_dan_embed_task
        task.push_request(retries=0, kwargs={"custom_kwargs": {"child_chunk_overlap": 0}, "_operation_token": "synthetic"})
        self.addCleanup(task.pop_request)
        error = RuntimeError("temporary model error")
        with patch("app.services.embedding_service.derive_document_title", return_value="Judul"), \
                patch("app.services.embedding_service.chunk_text_hierarchical", return_value=([{}], [{}])), \
                patch("app.services.embedding_service.delete_document_vectors"), \
                patch("app.services.embedding_service.embed_and_store_hierarchical", side_effect=error), \
                patch.object(task, "retry", side_effect=RuntimeError("scheduled")) as retry:
            with self.assertLogs(tasks.logger, "ERROR"), self.assertRaisesRegex(RuntimeError, "scheduled"):
                task.run(7, _operation_token="synthetic")
        retry.assert_called_once_with(exc=error, kwargs={"custom_kwargs": {"child_chunk_overlap": 0}, "_operation_token": "synthetic"})


class UntrackedTaskCancellationTest(unittest.TestCase):
    def test_old_queue_messages_require_resubmission_without_accessing_database_or_models(self):
        from app.tasks.process_document import process_document_task
        with patch("app.services.document_operations.get_engine", side_effect=AssertionError("must not access DB")), \
                patch.object(tasks.eb, "PenyimpananMySQL") as storage, \
                patch("app.services.document_processor.extract_document") as extract:
            for task, args in [(tasks.ekstrak_dokumen_task, (7, "synthetic.pdf")),
                               (tasks.potong_dan_embed_task, (7,)),
                               (process_document_task, (7, "synthetic.pdf", "new"))]:
                with self.subTest(task=task.name):
                    result = task.run(*args)
                    self.assertEqual(result["status"], "dibatalkan")
        storage.assert_not_called()
        extract.assert_not_called()


class PageCancellationBoundaryTest(unittest.TestCase):
    def test_staged_ocr_does_not_save_an_inflight_page_after_cancel(self):
        from app.services.extraction import workflow
        from app.services.extraction.memory_storage import PenyimpananMemori
        storage = PenyimpananMemori()
        active = [True]
        def checkpoint():
            if not active[0]:
                raise DocumentOperationCancelled("cancelled generation")
        def ocr(*args):
            active[0] = False
            return "obsolete text", None
        with patch.object(workflow, "flush_ollama_cache") as flush:
            with self.assertRaises(DocumentOperationCancelled):
                workflow.ekstrak_bertahap(7, 2, ocr, storage, check_cancelled=checkpoint)
        self.assertEqual(storage.halaman_tersimpan(7), set())
        flush.assert_not_called()

    def test_legacy_pdf_propagates_cancellation_and_closes_before_next_page(self):
        from app.services.ocr import pipeline
        pdf = MagicMock()
        pdf.__len__.return_value = 2
        callback = Mock(side_effect=DocumentOperationCancelled("cancelled generation"))
        with patch.object(pipeline, "_resolve_pdf_path", return_value="synthetic.pdf"), \
                patch.object(pipeline.fitz, "open", return_value=pdf), \
                patch.object(pipeline, "_ekstrak_halaman", return_value=("text", None)) as ocr, \
                patch.object(pipeline, "perbaiki_penanda_daftar") as cleanup:
            with self.assertRaises(DocumentOperationCancelled):
                pipeline.extract_text("synthetic.pdf", progress_callback=callback)
        self.assertEqual(ocr.call_count, 1)
        callback.assert_called_once_with(1, 2, 1, "text")
        pdf.close.assert_called_once()
        cleanup.assert_not_called()

    def test_legacy_two_argument_callback_also_propagates_cancellation(self):
        from app.services.ocr import pipeline
        pdf = MagicMock()
        pdf.__len__.return_value = 2
        def callback(processed, total):
            raise DocumentOperationCancelled("cancelled generation")
        with patch.object(pipeline, "_resolve_pdf_path", return_value="synthetic.pdf"), \
                patch.object(pipeline.fitz, "open", return_value=pdf), \
                patch.object(pipeline, "_ekstrak_halaman", return_value=("text", None)) as ocr:
            with self.assertRaises(DocumentOperationCancelled):
                pipeline.extract_text("synthetic.pdf", progress_callback=callback)
        self.assertEqual(ocr.call_count, 1)
        pdf.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
