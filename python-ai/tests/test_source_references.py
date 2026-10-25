"""JSON citation contracts using the source text emitted by real retrieval.

The generator and name repository are mocked; these tests use no model or DB.
"""

import unittest
from unittest.mock import patch

from app.routers import chat
from app.schemas import ChatMessageRequest


class SourceReferenceContractTest(unittest.IsolatedAsyncioTestCase):
    async def message(self, source_line, document_ids=None, names=None):
        request = ChatMessageRequest(message="Berapa lama pengarsipan?", document_ids=document_ids)
        chunks = ["Jawaban tetap.", "\n\n**Sumber Referensi:**\n" + source_line]
        with patch.object(chat.rag_service, "generate_response", return_value=iter(chunks)), \
                patch.object(chat, "get_document_names", return_value=names or {}) as lookup:
            result = await chat.chat_message(request, _token="synthetic")
        self.assertEqual(result.reply, "Jawaban tetap.")
        return result.sources, lookup

    async def test_retrieval_hyphen_source_resolves_unique_title_within_requested_ids(self):
        sources, lookup = await self.message("- Panduan Arsip - Halaman 1, 2", [7], {7: "Panduan Arsip"})
        self.assertEqual(sources[0].model_dump(), {"doc_name": "Panduan Arsip", "document_id": 7, "page": 1})
        lookup.assert_called_once_with([7])

    async def test_numeric_document_source_supports_actual_retrieval_separator(self):
        sources, lookup = await self.message("- Dokumen #7 - Halaman 3-5, 9", names={7: "Panduan"})
        self.assertEqual(sources[0].model_dump(), {"doc_name": "Panduan", "document_id": 7, "page": 3})
        lookup.assert_called_once_with([7])

    async def test_legacy_emdash_document_source_keeps_existing_id_name_and_page(self):
        sources, _ = await self.message("- Dokumen #7 — Halaman 4", names={7: "Panduan"})
        self.assertEqual(sources[0].model_dump(), {"doc_name": "Panduan", "document_id": 7, "page": 4})

    async def test_hyphenated_title_and_year_remain_intact(self):
        title = "Panduan - Arsip 2024 - Halaman 2025"
        sources, _ = await self.message(f"- {title} - Halaman 3-6, 9", [7], {7: title})
        self.assertEqual(sources[0].model_dump(), {"doc_name": title, "document_id": 7, "page": 3})

    async def test_duplicate_titles_within_scope_are_not_assigned_an_arbitrary_id(self):
        sources, _ = await self.message("- Panduan - Halaman 2", [7, 8], {7: "Panduan", 8: "Panduan"})
        self.assertEqual(sources[0].model_dump(), {"doc_name": "Panduan", "document_id": None, "page": 2})

    async def test_unscoped_named_reference_keeps_optional_id_without_a_global_lookup(self):
        sources, lookup = await self.message("- Panduan - Halaman 2")
        self.assertEqual(sources[0].model_dump(), {"doc_name": "Panduan", "document_id": None, "page": 2})
        lookup.assert_not_called()

    async def test_unmatched_title_is_not_assigned_the_only_scoped_document(self):
        sources, _ = await self.message("- Sumber Lain - Halaman 2", [7], {7: "Panduan"})
        self.assertEqual(sources[0].model_dump(), {"doc_name": "Sumber Lain", "document_id": None, "page": 2})

    async def test_name_resolution_ignores_ids_outside_the_request_scope(self):
        sources, _ = await self.message("- Panduan - Halaman 2", [7], {7: "Nama lain", 8: "Panduan"})
        self.assertIsNone(sources[0].document_id)

    async def test_non_numeric_page_suffix_is_not_mistaken_for_a_title_year(self):
        text = "Panduan 2024 - Halaman belum diketahui"
        sources, lookup = await self.message(f"- {text}")
        self.assertEqual(sources[0].model_dump(), {"doc_name": text, "document_id": None, "page": None})
        lookup.assert_not_called()

    async def test_unknown_page_from_retrieval_keeps_the_document_reference(self):
        sources, _ = await self.message("- Panduan — Halaman ?", [7], {7: "Panduan"})
        self.assertEqual(sources[0].model_dump(), {"doc_name": "Panduan", "document_id": 7, "page": None})

    async def test_empty_reference_list_does_not_query_document_names(self):
        with patch.object(chat, "get_document_names") as lookup:
            self.assertEqual(chat._build_source_references([]), [])
        lookup.assert_not_called()

    async def test_failed_lookup_preserves_numeric_source_id_and_page(self):
        with patch.object(chat, "get_document_names", side_effect=RuntimeError("synthetic unavailable")):
            with self.assertLogs(chat.logger, level="WARNING"):
                sources = chat._build_source_references([(7, 4)])
        self.assertEqual(sources[0].model_dump(), {"doc_name": None, "document_id": 7, "page": 4})


if __name__ == "__main__":
    unittest.main()
