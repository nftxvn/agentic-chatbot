"""
Test untuk app/services/pdf_processor.py
Memverifikasi bahwa:
  1. cv_parser / extract_pelaksana_mapping sudah tidak dipakai
  2. Deteksi tipe PDF berjalan benar
  3. Ekstraksi teks native (PyMuPDF) berjalan tanpa error
  4. Vision pipeline dipanggil dengan benar untuk halaman scan
  5. Tidak ada referensi ke flowchart / shape drawing
"""

import sys
import os
import types
import unittest
from unittest.mock import MagicMock, patch


# ─────────────────────────────────────────────
# Pastikan root project ada di sys.path
# ─────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ─────────────────────────────────────────────
# Stub app.config sebelum import app.services
# ─────────────────────────────────────────────
def _bootstrap_stubs():
    # Stub app (package)
    app_mod = types.ModuleType("app")
    app_mod.__path__ = [os.path.join(ROOT, "app")]
    app_mod.__package__ = "app"
    sys.modules.setdefault("app", app_mod)

    # Stub app.config
    cfg_mod = types.ModuleType("app.config")
    cfg_mod.__package__ = "app"
    settings_mock = MagicMock()
    settings_mock.OLLAMA_BASE_URL = "http://localhost:11434"
    settings_mock.VISION_MODEL_NAME = "llava"
    settings_mock.LLM_MODEL_NAME = "mistral"
    settings_mock.VISION_TIMEOUT = 120
    cfg_mod.settings = settings_mock
    sys.modules["app.config"] = cfg_mod

    # Stub app.services (subpackage) — tanpa stub ini Python tidak mau cari submodul
    svc_mod = types.ModuleType("app.services")
    svc_mod.__path__ = [os.path.join(ROOT, "app", "services")]
    svc_mod.__package__ = "app.services"
    sys.modules.setdefault("app.services", svc_mod)

    # Attach sebagai atribut agar unittest.mock.patch bisa resolve traversal
    app_mod = sys.modules["app"]
    app_mod.services = svc_mod


_bootstrap_stubs()

# Sekarang aman import
import importlib
pdf_processor = importlib.import_module("app.services.pdf_processor")

# Attach ke sys.modules["app"].services agar patch path bisa resolve
sys.modules["app"].services = pdf_processor.__class__.__module__ and sys.modules.get("app.services")


# ─────────────────────────────────────────────
# Unit Tests
# ─────────────────────────────────────────────
class TestNoCvParserImport(unittest.TestCase):
    """Memastikan cv_parser sudah dihapus dari pdf_processor."""

    def test_no_cv_parser_import(self):
        """pdf_processor tidak boleh mengimpor cv_parser sama sekali."""
        import importlib, ast, inspect
        source = inspect.getsource(pdf_processor)
        self.assertNotIn(
            "cv_parser",
            source,
            "cv_parser masih dipakai di pdf_processor — harus dihapus!",
        )

    def test_no_extract_pelaksana_mapping(self):
        """Fungsi extract_pelaksana_mapping tidak boleh dipanggil di pdf_processor."""
        import inspect
        source = inspect.getsource(pdf_processor)
        self.assertNotIn(
            "extract_pelaksana_mapping",
            source,
            "extract_pelaksana_mapping masih direferensikan di pdf_processor!",
        )

    def test_no_flowchart_shape_detection(self):
        """Logika get_drawings / shape detection sudah tidak ada."""
        import inspect
        source = inspect.getsource(pdf_processor)
        self.assertNotIn(
            "get_drawings",
            source,
            "get_drawings masih dipanggil — shape detection belum dihapus!",
        )


class TestStripGarbage(unittest.TestCase):
    """Test helper _strip_garbage."""

    def test_removes_img_tag(self):
        raw = 'Teks biasa <img src="data:image/png;base64,abc123"/> selesai'
        result = pdf_processor._strip_garbage(raw)
        self.assertNotIn("<img", result)
        self.assertIn("Teks biasa", result)

    def test_strips_markdown_fence(self):
        raw = "```markdown\n# Judul\nIsi\n```"
        result = pdf_processor._strip_garbage(raw)
        self.assertNotIn("```", result)
        self.assertIn("# Judul", result)

    def test_plain_text_unchanged(self):
        raw = "Teks normal tanpa fence"
        self.assertEqual(pdf_processor._strip_garbage(raw), raw)


class TestExtractTextFromPage(unittest.TestCase):
    """Test _extract_text_from_page dengan mock fitz.Page."""

    def _make_page(self, text="", tables=None, blocks=None):
        page = MagicMock()
        page.get_text.return_value = text

        # Mock find_tables()
        tabs_result = MagicMock()
        if tables is None:
            tabs_result.tables = []
        else:
            tabs_result.tables = tables
        page.find_tables.return_value = tabs_result

        # Mock get_text("blocks")
        page.get_text.side_effect = lambda fmt=None, **kw: (
            blocks if fmt == "blocks" else text
        )
        return page

    def test_no_table_returns_plain_text(self):
        page = MagicMock()
        page.find_tables.return_value = MagicMock(tables=[])
        page.get_text.return_value = "Isi halaman biasa"

        result = pdf_processor._extract_text_from_page(page)
        self.assertEqual(result, "Isi halaman biasa")

    def test_page_not_call_get_drawings(self):
        """get_drawings tidak boleh dipanggil sama sekali."""
        page = MagicMock()
        page.find_tables.return_value = MagicMock(tables=[])
        page.get_text.return_value = "Teks"

        pdf_processor._extract_text_from_page(page)
        page.get_drawings.assert_not_called()


class TestVisionExtractGeneral(unittest.TestCase):
    """Test vision_extract_general tidak pakai cv_parser / header_y_hint."""

    def test_signature_no_header_y_hint(self):
        """Fungsi tidak boleh punya parameter header_y_hint."""
        import inspect
        sig = inspect.signature(pdf_processor.vision_extract_general)
        self.assertNotIn(
            "header_y_hint",
            sig.parameters,
            "Parameter header_y_hint masih ada di vision_extract_general!",
        )

    def test_returns_text_on_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "Teks hasil OCR"}
        mock_resp.raise_for_status.return_value = None

        with patch.object(pdf_processor.requests, "post", return_value=mock_resp):
            result = pdf_processor.vision_extract_general("base64string")
        self.assertEqual(result, "Teks hasil OCR")

    def test_returns_empty_on_failure(self):
        import requests as req

        with patch.object(pdf_processor.requests, "post",
                          side_effect=req.exceptions.RequestException("timeout")):
            result = pdf_processor.vision_extract_general("base64string", retries=2)
        self.assertEqual(result, "")

    def test_prompt_no_cheatsheet(self):
        """Prompt ke model tidak boleh menyebut cheat sheet atau cv_parser."""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "ok"}
        mock_resp.raise_for_status.return_value = None

        with patch.object(pdf_processor.requests, "post", return_value=mock_resp) as mock_post:
            pdf_processor.vision_extract_general("img")
            call_args = mock_post.call_args
            payload = call_args[1]["json"] if call_args[1] else call_args[0][1]
            prompt_sent = payload["prompt"].lower()

        self.assertNotIn("cheat sheet", prompt_sent)
        self.assertNotIn("extract_pelaksana_mapping", prompt_sent)
        self.assertNotIn("cv_parser", prompt_sent)


# ─────────────────────────────────────────────
# Integration Test (opsional, jalankan dengan file PDF nyata)
# ─────────────────────────────────────────────
class TestIntegration(unittest.TestCase):
    """
    Jalankan test ini hanya jika ada file PDF nyata.
    Lewati otomatis jika file tidak ditemukan.
    """

    PDF_PATH = "test_files/SOP_diskominfotik_2025.pdf"
    OUTPUT_PATH = "hasil_test_pdf_processor.md"

    def setUp(self):
        from pathlib import Path
        if not Path(self.PDF_PATH).exists():
            self.skipTest(f"File PDF tidak ditemukan: {self.PDF_PATH}")

    def test_detect_pdf_type(self):
        pdf_type = pdf_processor.detect_pdf_type(self.PDF_PATH)
        self.assertIn(pdf_type, ["text", "scanned", "mixed"])
        print(f"\n[Integration] Tipe PDF: {pdf_type}")

    def test_extract_text_first_page(self):
        """Ekstrak halaman pertama saja, pastikan tidak error dan ada teks."""
        pages = pdf_processor.extract_text(self.PDF_PATH, page_num=0)
        self.assertIsInstance(pages, list)
        self.assertGreater(len(pages), 0)
        first = pages[0]
        self.assertIn("page_number", first)
        self.assertIn("text", first)
        self.assertGreater(len(first["text"]), 0)
        print(f"\n[Integration] Halaman 1 OK — {len(first['text'])} karakter")

    def test_extract_full_and_save(self):
        """Ekstrak seluruh halaman dan simpan ke file output untuk dicek manual."""
        pages = pdf_processor.extract_text(self.PDF_PATH)
        self.assertGreater(len(pages), 0)

        with open(self.OUTPUT_PATH, "w", encoding="utf-8") as f:
            for p in pages:
                f.write(f"## Halaman {p['page_number']}\n\n")
                f.write(p["text"])
                f.write("\n\n---\n\n")

        print(f"\n[Integration] {len(pages)} halaman diekstrak → {self.OUTPUT_PATH}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
