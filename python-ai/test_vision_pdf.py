"""
Test script untuk validasi penggantian Tesseract OCR dengan Vision Model.

Skenario yang ditest:
  Unit test (tidak butuh Ollama aktif):
    1. _vision_extract_page sukses mengembalikan teks (mock Ollama)
    2. _vision_extract_page retry saat timeout, percobaan ke-2 sukses
    3. _vision_extract_page return "" kalau semua retry gagal (tidak raise exception)
    4. _vision_extract_page return "" saat response Ollama berisi spasi saja
    5. URL yang dikirim ke Ollama berakhiran /api/generate
    6. extract_text() memanggil _vision_extract_page untuk halaman scan
    7. extract_text() TIDAK memanggil _vision_extract_page untuk halaman teks

  Integration test (butuh Ollama aktif + model ter-pull):
    8.  Koneksi ke Ollama berhasil
    9.  Model vision yang dikonfigurasi tersedia di Ollama
    10. _vision_extract_page berjalan dengan Ollama real
    11. extract_text() pada PDF teks biasa tidak memanggil vision model

Prasyarat untuk integration test:
  - Ollama berjalan di URL sesuai .env (default: http://localhost:11434)
  - Model vision sudah di-pull: ollama pull llava

Jalankan (dari folder python-ai/):
  python test_vision_pdf.py            # semua test
  python test_vision_pdf.py unit       # hanya unit test (tanpa Ollama)
  python test_vision_pdf.py integ      # hanya integration test
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# --- Helpers ------------------------------------------------------------------

def _make_mock_response(text):
    """Membuat mock requests.Response sukses untuk Ollama /api/generate."""
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"response": text, "done": True}
    return mock_resp


def _make_mock_page():
    """
    Membuat mock fitz.Page dengan pixmap PNG yang valid (dibuat via PyMuPDF).
    Menghasilkan halaman putih kosong berukuran kecil agar cepat diproses
    tapi tetap merupakan file PNG yang sah untuk dikirim ke vision model.
    """
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=100, height=50)
    page.insert_text((10, 30), "Test")
    pix = page.get_pixmap()
    png_bytes = pix.tobytes("png")
    doc.close()

    mock_pixmap = MagicMock()
    mock_pixmap.tobytes.return_value = png_bytes
    mock_page = MagicMock()
    mock_page.get_pixmap.return_value = mock_pixmap
    return mock_page


# --- Unit Tests ---------------------------------------------------------------

class TestVisionExtractPageUnit(unittest.TestCase):
    """Unit test _vision_extract_page menggunakan mock Ollama (tanpa koneksi nyata)."""

    def setUp(self):
        from app.services import pdf_processor
        self.pdf_processor = pdf_processor

    @patch("app.services.pdf_processor.requests.post")
    def test_1_sukses_kembalikan_teks(self, mock_post):
        """Skenario normal: Ollama merespons dengan teks valid."""
        teks = "Hasil ekstraksi teks oleh vision model."
        mock_post.return_value = _make_mock_response(teks)

        hasil = self.pdf_processor._vision_extract_page(_make_mock_page())

        self.assertEqual(hasil, teks)
        mock_post.assert_called_once()
        payload = mock_post.call_args[1]["json"]
        self.assertIn("model", payload)
        self.assertIn("prompt", payload)
        self.assertIn("images", payload)
        self.assertFalse(payload["stream"])
        self.assertIsInstance(payload["images"], list)
        self.assertEqual(len(payload["images"]), 1)

    @patch("app.services.pdf_processor.requests.post")
    def test_2_retry_percobaan_kedua_sukses(self, mock_post):
        """Percobaan 1 timeout, percobaan 2 sukses -> teks dikembalikan."""
        import requests as req
        teks_sukses = "Teks dari percobaan ke-2."
        mock_post.side_effect = [
            req.exceptions.Timeout("Connection timed out"),
            _make_mock_response(teks_sukses),
        ]

        hasil = self.pdf_processor._vision_extract_page(_make_mock_page(), retries=2)

        self.assertEqual(hasil, teks_sukses)
        self.assertEqual(mock_post.call_count, 2)

    @patch("app.services.pdf_processor.requests.post")
    def test_3_semua_retry_gagal_return_string_kosong(self, mock_post):
        """Semua retry gagal -> return string kosong, tidak raise exception."""
        import requests as req
        mock_post.side_effect = req.exceptions.ConnectionError("Cannot connect")

        hasil = self.pdf_processor._vision_extract_page(_make_mock_page(), retries=2)

        self.assertEqual(hasil, "")
        self.assertEqual(mock_post.call_count, 2)

    @patch("app.services.pdf_processor.requests.post")
    def test_4_response_spasi_return_string_kosong(self, mock_post):
        """Response Ollama berisi spasi saja -> strip() -> return string kosong."""
        mock_post.return_value = _make_mock_response("   ")

        hasil = self.pdf_processor._vision_extract_page(_make_mock_page())

        self.assertEqual(hasil, "")

    @patch("app.services.pdf_processor.requests.post")
    def test_5_url_berakhiran_api_generate(self, mock_post):
        """URL request ke Ollama harus berakhiran /api/generate."""
        mock_post.return_value = _make_mock_response("ok")

        self.pdf_processor._vision_extract_page(_make_mock_page())

        url = mock_post.call_args[0][0]
        self.assertTrue(
            url.endswith("/api/generate"),
            f"URL harus berakhiran '/api/generate', tapi: {url!r}",
        )


class TestExtractTextUnit(unittest.TestCase):
    """Unit test extract_text() - fokus pada alur pemanggilan _vision_extract_page."""

    def setUp(self):
        from app.services import pdf_processor
        self.pdf_processor = pdf_processor

    @patch("app.services.pdf_processor._vision_extract_page")
    @patch("app.services.pdf_processor.fitz.open")
    def test_6_halaman_scan_memanggil_vision(self, mock_fitz_open, mock_vision):
        """Halaman teks < 30 karakter harus memanggil _vision_extract_page."""
        mock_vision.return_value = "Hasil teks vision model yang cukup panjang."
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Teks"  # < 30 karakter -> scan
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz_open.return_value = mock_doc

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = self.pdf_processor.extract_text(tmp_path)
            mock_vision.assert_called_once_with(mock_page)
            self.assertEqual(result[0]["text"], "Hasil teks vision model yang cukup panjang.")
        finally:
            os.unlink(tmp_path)

    @patch("app.services.pdf_processor._vision_extract_page")
    @patch("app.services.pdf_processor.fitz.open")
    def test_7_halaman_teks_tidak_memanggil_vision(self, mock_fitz_open, mock_vision):
        """Halaman teks >= 30 karakter TIDAK boleh memanggil _vision_extract_page."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "A" * 50  # >= 30 karakter -> teks biasa
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=1)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_fitz_open.return_value = mock_doc

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            self.pdf_processor.extract_text(tmp_path)
            mock_vision.assert_not_called()
        finally:
            os.unlink(tmp_path)


# --- Integration Tests --------------------------------------------------------

class TestIntegrationOllama(unittest.TestCase):
    """Integration test - butuh Ollama aktif dan model vision ter-pull."""

    @classmethod
    def setUpClass(cls):
        import requests
        from app.config import settings
        cls.settings = settings
        cls.ollama_url = settings.OLLAMA_BASE_URL
        cls.vision_model = settings.VISION_MODEL_NAME
        try:
            resp = requests.get(f"{cls.ollama_url}/api/tags", timeout=5)
            resp.raise_for_status()
            cls.ollama_ok = True
            cls.available_models = [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            cls.ollama_ok = False
            cls.available_models = []

    def _skip_if_no_ollama(self):
        if not self.ollama_ok:
            self.skipTest(f"Ollama tidak aktif di {self.ollama_url}")

    def _skip_if_no_model(self):
        self._skip_if_no_ollama()
        if not any(self.vision_model in m for m in self.available_models):
            self.skipTest(
                f"Model '{self.vision_model}' belum di-pull. "
                f"Jalankan: ollama pull {self.vision_model}. "
                f"Model tersedia: {self.available_models}"
            )

    def test_8_koneksi_ollama(self):
        """Ollama harus bisa dijangkau dan merespons /api/tags."""
        self._skip_if_no_ollama()
        import requests
        resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
        self.assertEqual(resp.status_code, 200)

    def test_9_model_vision_tersedia(self):
        """Model vision yang dikonfigurasi harus tersedia di Ollama."""
        self._skip_if_no_model()

    def test_10_vision_extract_real(self):
        """_vision_extract_page tidak boleh raise exception dengan Ollama real."""
        self._skip_if_no_model()
        from app.services.pdf_processor import _vision_extract_page
        hasil = _vision_extract_page(_make_mock_page(), retries=1)
        self.assertIsInstance(hasil, str)

    def test_11_extract_text_pdf_teks_biasa(self):
        """extract_text() pada PDF teks biasa tidak boleh memanggil vision model."""
        self._skip_if_no_ollama()
        import fitz
        from app.services.pdf_processor import extract_text

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "Dokumen PDF pengujian dengan teks yang panjang dan bisa terbaca.",
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        doc.save(tmp_path)
        doc.close()

        try:
            with patch("app.services.pdf_processor._vision_extract_page") as mock_vision:
                result = extract_text(tmp_path)
                mock_vision.assert_not_called()
                self.assertGreater(len(result), 0)
                self.assertIn("page_number", result[0])
                self.assertIn("text", result[0])
        finally:
            os.unlink(tmp_path)


# --- Runner -------------------------------------------------------------------

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    valid_modes = ("all", "unit", "integ")
    if mode not in valid_modes:
        print(f"Mode tidak valid: '{mode}'. Pilihan: {', '.join(valid_modes)}")
        sys.exit(1)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    if mode in ("all", "unit"):
        suite.addTests(loader.loadTestsFromTestCase(TestVisionExtractPageUnit))
        suite.addTests(loader.loadTestsFromTestCase(TestExtractTextUnit))
    if mode in ("all", "integ"):
        suite.addTests(loader.loadTestsFromTestCase(TestIntegrationOllama))

    print("=" * 65)
    print(f"  TEST VISION PDF PROCESSOR  [mode: {mode}]")
    print("=" * 65)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)