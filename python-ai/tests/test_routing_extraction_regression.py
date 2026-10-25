"""Regresi keputusan routing dan ekstraksi tanpa database, broker, atau model."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from app.services.extraction import contracts, workflow
from app.services.extraction.memory_storage import PenyimpananMemori
from app.services.routing import calendar, citizen, dispatch, language, semantic


class RoutingRegressionTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(dispatch, "classify_semantic_intent", return_value=None))
        self.directories = self.stack.enter_context(patch.object(dispatch, "get_active_directories", return_value=[]))
        self.faq = self.stack.enter_context(patch.object(dispatch, "get_active_fast_paths", return_value=[]))
        self.stack.enter_context(patch("app.services.session_memory.resolve_contextual_query", side_effect=lambda q, sid: (q, False)))
        self.stack.enter_context(patch("app.services.session_memory.get_last_context", return_value=(None, None)))

    def test_unknown_query_falls_through_to_rag_with_original_query(self):
        result = dispatch.route_intent("Informasi pengadaan aplikasi")
        self.assertEqual(result["intent"], "rag")
        self.assertEqual(result["params"], {"query": "Informasi pengadaan aplikasi", "raw_query": "Informasi pengadaan aplikasi"})

    def test_explicit_handoff_precedes_calculator(self):
        self.assertEqual(dispatch.route_intent("Hubungkan saya dengan petugas, hitung 3 hari kerja")["intent"], "human_escalation")
        self.directories.assert_not_called()

    def test_greeting_precedes_directory_lookup(self):
        self.assertEqual(dispatch.route_intent("Halo")["intent"], "chitchat")
        self.directories.assert_not_called()

    def test_directory_wins_over_general_faq(self):
        self.directories.return_value = [{"keywords": ["statistik"], "nama_bidang": "Bidang Statistik", "lokasi": "Gedung C",
                                          "email": "data@example.test", "layanan_utama": "Data", "daftar_tugas": ["Publikasi"]}]
        result = dispatch.route_intent("alamat statistik")
        self.assertEqual(result["intent"], "augmented_knowledge")
        self.assertEqual(result["params"]["category"], "direktori")
        self.faq.assert_not_called()

    def test_sop_detail_guard_skips_directory(self):
        self.directories.return_value = [{"keywords": ["statistik"]}]
        self.assertEqual(dispatch.route_intent("bagaimana prosedur statistik")["intent"], "rag")

    def test_dynamic_faq_payload_retains_source_and_original_query(self):
        self.faq.return_value = [{"keywords": ["kontak"], "title": "Kontak Resmi", "response_text": "Telepon 112", "category": "general"}]
        result = dispatch.route_intent("kontak")
        self.assertEqual(result["intent"], "augmented_knowledge")
        self.assertEqual(result["params"]["source_title"], "Kontak Resmi")
        self.assertIn("Telepon 112", result["params"]["facts_context"])

    def test_doubt_on_previous_document_topic_precedes_other_sources(self):
        with patch("app.services.session_memory.get_last_context", return_value=("Dokumen SOP", "Layanan")):
            result = dispatch.route_intent("yakin itu benar?", session_id="session")
        self.assertEqual(result["intent"], "rag")
        self.directories.assert_not_called()

    def test_citizen_form_extracts_name_agency_and_issue(self):
        result = citizen.extract_citizen_escalation_details("Nama: Naufal / Instansi: Dinas Kesehatan / Kendala: Aplikasi tidak bisa dibuka")
        self.assertEqual(result["citizen_name"], "Naufal")
        self.assertIn("Kesehatan", result["citizen_agency"])
        self.assertIn("Aplikasi tidak bisa dibuka", result["issue_summary"])

    def test_normalization_keeps_domain_expansion_and_removes_filler(self):
        self.assertEqual(language.normalize_query("Tolong RENSTRA"), "rencana strategis renstra")

    def test_workday_calculator_skips_weekend_and_excludes_start_day(self):
        result = calendar.hitung_estimasi_selesai(1, "2026-10-23")
        self.assertIn("26 Oktober 2026", result["tanggal_selesai"])
        self.assertEqual(result["weekend_days"], 2)
        self.assertEqual(result["total_calendar_days"], 3)


class SemanticCacheRegressionTest(unittest.TestCase):
    def test_anchor_vectors_are_built_once_per_process(self):
        with patch.object(semantic, "_SEMANTIC_INTENT_VECTORS", None), \
                patch("app.services.embedding_service.encode_texts", side_effect=lambda texts: [[3, 4]] * len(texts)) as encode:
            first = semantic._get_semantic_intent_vectors()
            self.assertIs(semantic._get_semantic_intent_vectors(), first)
        self.assertEqual(encode.call_count, 3)
        self.assertEqual(first["human_escalation"][0], [0.6, 0.8])

    def test_failed_anchor_load_is_cached_without_repeated_model_calls(self):
        with patch.object(semantic, "_SEMANTIC_INTENT_VECTORS", None), \
                patch("app.services.embedding_service.encode_texts", side_effect=RuntimeError("unavailable")) as encode:
            with self.assertLogs(semantic.logger, level="WARNING"):
                self.assertEqual(semantic._get_semantic_intent_vectors(), {})
            self.assertEqual(semantic._get_semantic_intent_vectors(), {})
        encode.assert_called_once()

    def test_information_question_cannot_become_semantic_handoff(self):
        with patch.object(semantic, "_get_semantic_intent_vectors", return_value={"human_escalation": [[1, 0]]}), \
                patch("app.services.embedding_service.encode_query", return_value=[1, 0]):
            self.assertIsNone(semantic.classify_semantic_intent("Bagaimana prosedur layanan?"))
            self.assertEqual(semantic.classify_semantic_intent("hubungkan ke petugas"), "human_escalation")


class ExtractionRegressionTest(unittest.TestCase):
    def setUp(self):
        self.storage = PenyimpananMemori()
        patcher = patch.object(workflow, "flush_ollama_cache")
        self.flush = patcher.start()
        self.addCleanup(patcher.stop)

    def test_pause_preserves_page_and_format_hint_before_stopping(self):
        def ocr(number, hint):
            self.storage.minta_jeda(1)
            return "Halaman satu", "format baru"

        result = workflow.ekstrak_bertahap(1, 3, ocr, self.storage)
        self.assertEqual(result.status, contracts.STATUS_JEDA)
        self.assertEqual(self.storage.halaman_tersimpan(1), {1})
        self.assertEqual(self.storage.baca_petunjuk(1), "format baru")
        self.assertFalse(self.storage.jeda_diminta(1))

    def test_resume_skips_saved_pages_and_reuses_format_hint(self):
        self.storage.simpan_halaman(1, 1, "Teks tersimpan")
        self.storage.simpan_petunjuk(1, "format tersimpan")
        ocr = Mock(return_value=("Halaman dua", "format lanjut"))
        result = workflow.ekstrak_bertahap(1, 2, ocr, self.storage)
        ocr.assert_called_once_with(2, "format tersimpan")
        self.assertEqual(result.status, contracts.STATUS_SELESAI)
        self.assertEqual(self.storage.halaman[1][1], "Teks tersimpan")

    def test_page_limit_leaves_remaining_work_for_next_task(self):
        ocr = Mock(return_value=("Teks", None))
        result = workflow.ekstrak_bertahap(1, 4, ocr, self.storage, maks_halaman=1)
        self.assertEqual(result.status, contracts.STATUS_BERJALAN)
        self.assertEqual(result.halaman_selesai, 1)
        ocr.assert_called_once_with(1, None)

    def test_failure_preserves_previous_page_and_stops_future_pages(self):
        ocr = Mock(side_effect=[("Teks", "format"), RuntimeError("page error")])
        with self.assertLogs(workflow.logger, level="ERROR"):
            result = workflow.ekstrak_bertahap(1, 3, ocr, self.storage)
        self.assertEqual(result.status, contracts.STATUS_GAGAL)
        self.assertEqual(self.storage.halaman_tersimpan(1), {1})
        self.assertEqual(ocr.call_count, 2)
        self.assertIn("Halaman 2 gagal", result.pesan)

    def test_queued_pause_is_respected_before_first_ocr_call(self):
        self.storage.minta_jeda(1)
        ocr = Mock()
        self.assertEqual(workflow.ekstrak_bertahap(1, 3, ocr, self.storage).status, contracts.STATUS_JEDA)
        ocr.assert_not_called()

    def test_deleted_document_is_not_processed(self):
        self.storage.dokumen_valid.add(99)
        ocr = Mock()
        self.assertEqual(workflow.ekstrak_bertahap(1, 3, ocr, self.storage).status, contracts.STATUS_GAGAL)
        ocr.assert_not_called()

    def test_finished_document_does_not_repeat_ocr(self):
        self.storage.simpan_halaman(1, 1, "Teks")
        ocr = Mock()
        self.assertEqual(workflow.ekstrak_bertahap(1, 1, ocr, self.storage).status, contracts.STATUS_SELESAI)
        ocr.assert_not_called()


class CeleryRetryRegressionTest(unittest.TestCase):
    def setUp(self):
        from app.tasks import ekstraksi

        self.tasks = ekstraksi
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.guard = Mock()
        self.stack.enter_context(patch("app.services.document_operations.OperationGuard", return_value=self.guard))
        self.storage = Mock()
        self.storage.dokumen_ada.return_value = True
        self.storage.teks_terkumpul.return_value = [{"page_number": 1, "text": "Isi halaman"}]
        self.stack.enter_context(patch.object(ekstraksi.eb, "PenyimpananMySQL", return_value=self.storage))
        self.update = self.stack.enter_context(patch("app.database.update_document_status"))
        self.log = self.stack.enter_context(patch("app.database.record_document_log"))
        self.stack.enter_context(patch("app.services.embedding_service.derive_document_title", return_value="Layanan"))
        self.stack.enter_context(patch("app.services.embedding_service.chunk_text_hierarchical", return_value=([{"text": "parent"}], [{"text": "child"}])))
        self.stack.enter_context(patch("app.services.embedding_service.delete_document_vectors", return_value=2))
        self.store = self.stack.enter_context(patch("app.services.embedding_service.embed_and_store_hierarchical", return_value=2))

    def test_embedding_success_keeps_result_and_final_database_status(self):
        result = self.tasks.potong_dan_embed_task.run(1, _operation_token="synthetic")
        self.assertEqual(result, {"status": "selesai", "induk": 1, "anak": 1, "vektor": 2})
        self.assertEqual(self.update.call_args.kwargs["status"], "completed")
        self.assertEqual(self.update.call_args.kwargs["total_chunks"], 2)
        self.assertEqual(self.storage.catat_kemajuan_embed.call_args.kwargs["persen"], 100)

    def test_retryable_embedding_error_keeps_progress_without_final_failure(self):
        task = self.tasks.potong_dan_embed_task
        task.push_request(retries=0)
        self.addCleanup(task.pop_request)
        self.store.side_effect = RuntimeError("CUDA error: synthetic failure")
        with patch.object(task, "retry", side_effect=RuntimeError("retry scheduled")) as retry:
            with self.assertLogs(self.tasks.logger, level="ERROR"):
                with self.assertRaisesRegex(RuntimeError, "retry scheduled"):
                    task.run(1, _operation_token="synthetic")
        retry.assert_called_once()
        self.storage.catat_status.assert_not_called()
        self.update.assert_not_called()
        progress = self.storage.catat_kemajuan_embed.call_args.kwargs
        self.assertEqual(progress["status"], "berjalan")
        self.assertEqual(progress["persen"], 45)
        self.assertIn("Kendala GPU CUDA", progress["pesan"])

    def test_exhausted_embedding_retry_records_failure_before_raising(self):
        task = self.tasks.potong_dan_embed_task
        task.push_request(retries=3)
        self.addCleanup(task.pop_request)
        self.store.side_effect = RuntimeError("synthetic failure")
        with patch.object(task, "retry", side_effect=RuntimeError("retry exhausted")):
            with self.assertLogs(self.tasks.logger, level="ERROR"):
                with self.assertRaisesRegex(RuntimeError, "retry exhausted"):
                    task.run(1, _operation_token="synthetic")
        self.assertEqual(self.storage.catat_status.call_args.args[1], "gagal")
        self.assertEqual(self.update.call_args.kwargs["status"], "failed")

    def test_page_batch_requeues_with_category_options_without_real_broker(self):
        from unittest.mock import MagicMock

        progress = contracts.Kemajuan(1, "berjalan", 3, 1, [1])
        document = MagicMock()
        document.__len__.return_value = 3
        with patch("fitz.open") as open_pdf, \
                patch("app.services.pdf_processor._resolve_pdf_path", return_value="resolved.pdf"), \
                patch.object(self.tasks.eb, "ekstrak_bertahap", return_value=progress), \
                patch.object(self.tasks.ekstrak_dokumen_task, "delay") as delay:
            open_pdf.return_value.__enter__.return_value = document
            result = self.tasks.ekstrak_dokumen_task.run(
                1, "document.pdf", 1, category_prompt="kategori", job_titles="Operator",
                vision_model="mock-vl", custom_prompts={"dasar": "aturan"}, _operation_token="synthetic",
            )
        self.assertEqual(result["status"], "berjalan")
        delay.assert_called_once_with(
            1, "document.pdf", 1, category_prompt="kategori", job_titles="Operator",
            vision_model="mock-vl", custom_prompts={"dasar": "aturan"}, _operation_token="synthetic",
        )


if __name__ == "__main__":
    unittest.main()
