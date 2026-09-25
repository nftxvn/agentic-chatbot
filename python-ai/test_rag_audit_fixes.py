import unittest
import os
import sys

# Ensure environment
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.tool_router import (
    parse_and_sum_durations_from_context,
    _enrich_facts_with_date_calculations,
    _parse_days_count,
    route_intent,
)
from app.services.session_memory import (
    clean_context_subject,
    add_user_message,
    add_assistant_message,
    resolve_contextual_query,
)
from app.services.pdf_processor import _strip_garbage
from app.services.embedding_service import _split_list_preserving_items


class TestRAGFixes(unittest.TestCase):

    def test_duration_parsing_combined_days_and_minutes(self):
        context = """
        Langkah 1: Penyusunan draft membutuhkan waktu 5 hari kerja.
        Langkah 2: Review teknis membutuhkan waktu 60 menit.
        Langkah 3: Persetujuan final memerlukan waktu 60 menit.
        Langkah 4: Pengesahan dokumen memakan waktu 20 hari.
        """
        result = parse_and_sum_durations_from_context(context)
        self.assertIsNotNone(result)
        self.assertEqual(result["total_hari"], 25)
        self.assertEqual(result["total_menit"], 120)
        self.assertIn("25 hari", result["formatted_total"])
        self.assertIn("2 jam", result["formatted_total"])

    def test_date_countdown_enrichment(self):
        text = "Pelaksanaan kegiatan dijadwalkan pada 31 Desember 2026."
        enriched = _enrich_facts_with_date_calculations(text)
        self.assertIn("Estimasi Waktu ke Depan", enriched)
        self.assertIn("hari lagi dari hari ini", enriched)

    def test_parse_days_count_strict(self):
        self.assertIsNone(_parse_days_count("ada 5 berkas yang diajukan"))
        self.assertEqual(_parse_days_count("butuh 14 hari kerja"), 14)
        self.assertEqual(_parse_days_count("dalam durasi 7 hari"), 7)

    def test_chitchat_filter_preserves_document_queries(self):
        # Queries about health or validity should route to RAG, not chitchat
        res_doc1 = route_intent("Bagaimana prosedur izin cuti melahirkan agar tetap sehat?")
        self.assertNotEqual(res_doc1["intent"], "chitchat")

        res_doc2 = route_intent("Masa berlaku sertifikat tanda tangan elektronik berapa tahun?")
        self.assertNotEqual(res_doc2["intent"], "chitchat")

        # True greetings/chitchat
        res_greet = route_intent("Halo selamat pagi")
        self.assertEqual(res_greet["intent"], "chitchat")

        res_thanks = route_intent("terima kasih banyak")
        self.assertEqual(res_thanks["intent"], "chitchat")

    def test_session_memory_anaphora_and_pronouns(self):
        session_id = "test_sess_123"
        add_user_message(session_id, "Bagaimana SOP Pelayanan Informasi Publik?")
        add_assistant_message(
            session_id,
            "SOP Pelayanan Informasi Publik mengatur tata cara permohonan informasi publik.",
            topic="Layanan Informasi",
            entity="SOP Pelayanan Informasi Publik",
        )

        resolved_query, is_res = resolve_contextual_query("apa saja syaratnya?", session_id)
        self.assertTrue(is_res)
        self.assertIn("SOP Pelayanan Informasi Publik", resolved_query)

        resolved_pronoun, is_res2 = resolve_contextual_query("dokumen ini untuk siapa?", session_id)
        self.assertTrue(is_res2)
        self.assertIn("SOP Pelayanan Informasi Publik", resolved_pronoun)

    def test_pdf_processor_strip_garbage(self):
        markdown_wrapped = "```markdown\n| No | Prosedur |\n| 1 | Pengajuan |\n```"
        cleaned = _strip_garbage(markdown_wrapped)
        self.assertFalse(cleaned.startswith("```"))
        self.assertFalse(cleaned.endswith("```"))
        self.assertIn("| No | Prosedur |", cleaned)

    def test_split_list_preserving_items_large_item_fallback(self):
        huge_item = "- " + ("Kata-kata panjang sekali dalam satu item daftar. " * 60)
        chunks = _split_list_preserving_items(huge_item, max_size=200)
        self.assertGreater(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
