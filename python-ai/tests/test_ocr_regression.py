"""Regresi OCR dengan HTTP, model, PDF, dan waktu tunggu yang diganti mock."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from app.services.ocr import cleanup, pdf_io, pipeline, prompts, sop, vision


class VisionRegressionTest(unittest.TestCase):
    def test_explicit_model_bypasses_database_and_autodetection(self):
        with patch("app.database.get_app_setting") as setting, patch.object(vision, "get_installed_vision_models") as tags:
            self.assertEqual(vision.resolve_vision_model("  category-model  "), "category-model")
        setting.assert_not_called()
        tags.assert_not_called()

    def test_global_model_takes_precedence_over_cached_autodetection(self):
        with patch("app.database.get_app_setting", side_effect=[None, "global-model"]), \
                patch.object(vision, "_CACHED_AUTO_VISION_MODEL", ("cached", 100)), \
                patch.object(vision, "get_installed_vision_models") as tags:
            self.assertEqual(vision.resolve_vision_model(), "global-model")
        tags.assert_not_called()

    def test_auto_model_cache_expires_after_sixty_seconds(self):
        with patch("app.database.get_app_setting", return_value=None), \
                patch.object(vision, "_CACHED_AUTO_VISION_MODEL", None), \
                patch.object(vision, "time", SimpleNamespace(time=Mock(side_effect=[100, 159, 161]))), \
                patch.object(vision, "get_installed_vision_models", side_effect=[["first-vl"], ["second-vl"]]) as tags:
            self.assertEqual(vision.resolve_vision_model(), "first-vl")
            self.assertEqual(vision.resolve_vision_model(), "first-vl")
            self.assertEqual(vision.resolve_vision_model(), "second-vl")
            self.assertEqual(tags.call_count, 2)

    def test_model_falls_back_to_configuration_when_autodetection_is_empty(self):
        with patch("app.database.get_app_setting", side_effect=RuntimeError("db unavailable")), \
                patch.object(vision, "_CACHED_AUTO_VISION_MODEL", None), \
                patch.object(vision, "get_installed_vision_models", return_value=[]), \
                patch.object(vision.settings, "VISION_MODEL_NAME", "configured-vl"):
            self.assertEqual(vision.resolve_vision_model(), "configured-vl")

    def test_installed_model_filter_keeps_server_order(self):
        response = Mock(status_code=200)
        response.json.return_value = {"models": [{"name": "text:7b"}, {"name": "qwen-vl:7b"}, {}, {"name": "llava:latest"}]}
        with patch.object(vision.requests, "get", return_value=response) as get:
            self.assertEqual(vision.get_installed_vision_models(), ["qwen-vl:7b", "llava:latest"])
        self.assertEqual(get.call_args.kwargs["timeout"], 3)

    def test_prompt_layers_aliases_and_ollama_payload_are_preserved(self):
        response = Mock()
        response.json.return_value = {"response": "```text\nIsi dokumen\n```"}
        with patch.object(vision, "resolve_vision_model", return_value="mock-vl"), \
                patch.object(vision.requests, "post", return_value=response) as post:
            answer = vision.vision_extract_general(
                "encoded-image", category_prompt="Kategori {job_titles}", job_titles="Petugas TI",
                petunjuk="PETUNJUK", custom_prompts={"dasar": "DASAR"},
            )
        self.assertEqual(answer, "Isi dokumen")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["model"], "mock-vl")
        self.assertEqual(payload["images"], ["encoded-image"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"], {"num_ctx": 8192, "num_predict": 2048, "temperature": 0.1})
        self.assertTrue(payload["prompt"].startswith("DASAR"))
        self.assertIn("Kategori Petugas TI", payload["prompt"])
        self.assertTrue(payload["prompt"].endswith("PETUNJUK"))

    def test_default_prompt_is_used_when_custom_base_is_empty(self):
        response = Mock()
        response.json.return_value = {"response": "Teks"}
        with patch.object(vision, "resolve_vision_model", return_value="mock"), \
                patch.object(vision.requests, "post", return_value=response) as post:
            vision.vision_extract_general("image", custom_prompts={"dasar": ""})
        self.assertEqual(post.call_args.kwargs["json"]["prompt"], prompts._PROMPT_OCR_DASAR)

    def test_request_exception_retries_without_real_sleep(self):
        response = Mock()
        response.json.return_value = {"response": "Sukses"}
        with patch.object(vision, "resolve_vision_model", return_value="mock"), \
                patch.object(vision.requests, "post", side_effect=[requests.Timeout("temporary"), response]) as post, \
                patch.object(vision.time, "sleep") as sleep:
            self.assertEqual(vision.vision_extract_general("image"), "Sukses")
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_empty_result_stops_at_configured_retry_limit(self):
        response = Mock()
        response.json.return_value = {"response": " "}
        with patch.object(vision, "resolve_vision_model", return_value="mock"), \
                patch.object(vision.requests, "post", return_value=response) as post, \
                patch.object(vision.time, "sleep"):
            with self.assertRaisesRegex(RuntimeError, "teks kosong"):
                vision.vision_extract_general("image", retries=2)
        self.assertEqual(post.call_count, 2)


class OcrGuardRegressionTest(unittest.TestCase):
    def test_generic_document_does_not_trigger_sop_retry(self):
        with patch.object(sop, "vision_extract_general", return_value="Notulen rapat umum") as extract:
            self.assertEqual(sop._ocr_dengan_penjaga("image", 1), "Notulen rapat umum")
        extract.assert_called_once()

    def test_complete_header_is_preferred_over_longer_incomplete_result(self):
        complete = "Nomor SOP: 1\nNama SOP: Izin\nNIP. 123456789"
        with patch.object(sop, "vision_extract_general", side_effect=["Nomor SOP: 1\n" + "x" * 200, complete]) as extract:
            self.assertEqual(sop._ocr_dengan_penjaga("image", 3), complete)
        self.assertEqual(extract.call_count, 2)

    def test_incomplete_header_returns_longest_result_after_three_attempts(self):
        results = ["Nomor SOP: 1", "Nomor SOP: 1\nNama SOP: Layanan panjang", "Nomor SOP: 2"]
        with patch.object(sop, "vision_extract_general", side_effect=results) as extract:
            with self.assertLogs(sop.logger, level="WARNING"):
                self.assertEqual(sop._ocr_dengan_penjaga("image", 3), results[1])
        self.assertEqual(extract.call_count, 3)

    def test_keyword_placeholders_keep_legacy_and_current_aliases(self):
        for alias in ("{kata_kunci}", "{job_titles}"):
            with self.subTest(alias=alias):
                self.assertEqual(prompts._sisipkan_kata_kunci(alias, "Operator"), "Operator")
        # Legacy behavior replaces the first matching alias, then returns.
        self.assertEqual(prompts._sisipkan_kata_kunci("{kata_kunci} / {job_titles}", "Operator"), "Operator / {job_titles}")

    def test_cleaning_keeps_markdown_table_and_removes_image_tag(self):
        self.assertEqual(cleanup._strip_garbage('```markdown\n| A | B |\n<img src="x"/>\n```'), "| A | B |")

    def test_list_repair_carries_sequence_across_page_boundary(self):
        pages = [{"text": "aa. Satu\nbb. Dua\ncc. Tiga"}, {"text": "d. Empat\ne. Lima"}]
        self.assertEqual(cleanup.perbaiki_penanda_daftar(pages), 2)
        self.assertEqual(pages[1]["text"], "dd. Empat\nee. Lima")

    def test_editor_render_caps_size_and_keeps_jpeg_quality(self):
        page = Mock(rect=SimpleNamespace(width=2000, height=1000))
        page.get_pixmap.return_value = Mock(width=2560, height=1280)
        page.get_pixmap.return_value.tobytes.return_value = b"jpeg"
        doc = Mock()
        doc.__len__ = Mock(return_value=1)
        doc.__getitem__ = Mock(return_value=page)
        with patch.object(pdf_io, "_resolve_pdf_path", return_value="resolved.pdf"), patch.object(pdf_io, "fitz") as fitz:
            fitz.open.return_value.__enter__.return_value = doc
            self.assertEqual(pdf_io.render_halaman("file", 1, 4), (b"jpeg", 2560, 1280))
            fitz.Matrix.assert_called_once_with(1.28, 1.28)
        page.get_pixmap.return_value.tobytes.assert_called_once_with("jpeg", jpg_quality=80)

    def test_invalid_zoom_is_rejected_before_accessing_file(self):
        with patch.object(pdf_io, "_resolve_pdf_path") as resolve:
            with self.assertRaises(ValueError):
                pdf_io.render_halaman("file", 1, 50)
        resolve.assert_not_called()

    def test_native_page_keeps_embedded_image_text_and_skips_full_page_ocr(self):
        with patch.object(pipeline, "_extract_text_from_page", return_value="a" * 300), \
                patch.object(pipeline, "_ekstrak_gambar_tersemat", return_value="\nBagan"), \
                patch.object(pipeline, "vision_extract_general") as extract:
            text, hint = pipeline._ekstrak_halaman(Mock(), 1, "existing-hint")
        self.assertEqual(text, "a" * 300 + "\nBagan")
        self.assertEqual(hint, "existing-hint")
        extract.assert_not_called()


if __name__ == "__main__":
    unittest.main()
