"""Kontrak RAG tanpa koneksi database, unduhan model, atau inferensi nyata."""

import importlib
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services import rag_service as rag


def owner(function):
    """Patch dependency pada modul pemilik fungsi setelah pemisahan modul."""
    return importlib.import_module(function.__module__)


class GroundingContractTest(unittest.TestCase):
    def test_page_ranges_keep_citation_format(self):
        for pages, expected in [([], ""), ([65, 64, 64], "Halaman 64, 65"),
                                ([6, 3, 4, 5, 9], "Halaman 3-6, 9")]:
            with self.subTest(pages=pages):
                self.assertEqual(rag._format_pages_list(pages), expected)

    def test_rank_fusion_combines_ranks_not_raw_scores(self):
        scores = rag._reciprocal_rank_fusion(["a", "b"], ["b", "c"])
        self.assertAlmostEqual(scores["a"], 1 / 61)
        self.assertAlmostEqual(scores["b"], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(scores["c"], 1 / 62)

    def test_document_filters_keep_chroma_operator_shapes(self):
        cases = [(None, None, None), ("child", None, {"chunk_type": "child"}),
                 (None, ["1", "invalid"], {"document_id": 1}),
                 (None, [1, 2], {"document_id": {"$in": [1, 2]}}),
                 ("child", [1], {"$and": [{"chunk_type": "child"}, {"document_id": 1}]})]
        for chunk_type, ids, expected in cases:
            with self.subTest(chunk_type=chunk_type, ids=ids):
                self.assertEqual(rag._build_where_filter(chunk_type, ids), expected)

    def test_catalog_detection_excludes_specific_procedure_details(self):
        self.assertTrue(rag._is_list_query("Sebutkan daftar seluruh SOP"))
        self.assertFalse(rag._is_list_query("Apa saja syarat SOP izin?"))
        self.assertFalse(rag._is_list_query("Berapa lama prosedur izin?"))

    def test_procedure_guard_recognizes_only_sop_form_documents(self):
        self.assertFalse(rag._context_is_sop_document("Panduan aplikasi: tekan tombol simpan."))
        self.assertTrue(rag._context_is_sop_document("Nomor SOP: 12; Nama SOP: Izin"))
        self.assertFalse(rag._context_has_full_procedure("Nama SOP: Izin"))
        self.assertTrue(rag._context_has_full_procedure("Pelaksana: Petugas"))

    def test_missing_numbered_entity_requires_enough_evidence(self):
        self.assertEqual(rag._entitas_tak_ada_di_konteks("Diktum keempat?", "KESATU KEDUA KETIGA"),
                         "Diktum KEEMPAT")
        self.assertIsNone(rag._entitas_tak_ada_di_konteks("Diktum kedua?", "KEDUA"))
        self.assertIsNone(rag._entitas_tak_ada_di_konteks("langkah ke-11?", "1. Mulai\n2. Selesai"))
        self.assertEqual(rag._entitas_tak_ada_di_konteks("langkah ke-11?", "1. Mulai\n2. Periksa\n3. Selesai"),
                         "langkah ke-11")

    def test_complete_catalog_is_returned_without_truncating(self):
        context = "Daftar SOP:\n" + "\n".join(f"{i}. Layanan nomor {i}" for i in range(1, 13))
        answer = rag._build_enumeration_answer(context, "Sebutkan daftar seluruh SOP lengkap")
        self.assertIsNotNone(answer)
        self.assertIn("**12**", answer)
        self.assertIn("12. Layanan nomor 12", answer)
        self.assertIsNone(rag._build_enumeration_answer(context, "Apa syarat layanan?"))

    def test_context_estimate_does_not_choose_generation_window(self):
        self.assertEqual(rag._estimasi_token_konteks(""), 2048)
        self.assertEqual(rag._estimasi_token_konteks("x" * 3072), 3072)
        self.assertEqual(rag._estimasi_token_konteks("x" * 3075), 4096)


class RetrievalContractTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.module = owner(rag._retrieve_context)
        self.collection = Mock()
        self.collection.query.return_value = {"documents": [[]], "metadatas": [[]], "ids": [[]]}
        self.stack.enter_context(patch.object(self.module, "get_chroma_collection", return_value=self.collection))
        self.reranker = self.stack.enter_context(patch.object(self.module, "get_reranker_model", return_value=None))
        self.stack.enter_context(patch.object(self.module, "encode_query", return_value=[0.1]))
        self.stack.enter_context(patch.object(self.module.tool_router, "normalize_query", side_effect=lambda q: q))
        self.stack.enter_context(patch.object(self.module, "get_document_names_by_ids", return_value={1: "Panduan.pdf"}))
        self.stack.enter_context(patch.object(self.module.settings, "DEBUG_DUMP_CONTEXT", False))
        self.index = {"bm25": None, "docs": [], "ids": [], "metas": [], "hierarchical": False}
        self.stack.enter_context(patch.object(self.module, "_get_bm25_index", return_value=self.index))

    def vector_results(self, documents, metadata, ids):
        self.collection.query.return_value = {"documents": [documents], "metadatas": [metadata], "ids": [ids]}

    def test_no_matches_preserves_optional_debug_tuple(self):
        self.assertEqual(rag._retrieve_context("izin"), ("", ""))
        self.assertEqual(rag._retrieve_context("izin", return_chunks_info=True), ("", "", []))

    def test_flat_retrieval_orders_pages_and_preserves_source_metadata(self):
        self.vector_results(["Halaman dua", "Halaman satu"],
                            [{"document_id": 1, "page_number": 2, "chunk_index": 0},
                             {"document_id": 1, "page_number": 1, "chunk_index": 0}], ["b", "a"])
        context, sources, chunks = rag._retrieve_context("izin", document_ids=[1], return_chunks_info=True)
        self.assertLess(context.index("Halaman satu"), context.index("Halaman dua"))
        self.assertEqual(sources, "- Panduan.pdf - Halaman 1, 2")
        self.assertEqual([c["page_number"] for c in chunks], [1, 2])
        self.assertEqual(chunks[0]["chunk_type"], "flat")
        self.assertEqual(chunks[0]["document_name"], "Panduan.pdf")
        self.assertEqual(self.collection.query.call_args.kwargs["where"], {"document_id": 1})

    def test_bm25_document_filter_runs_before_top_k_cutoff(self):
        bm25 = Mock()
        bm25.get_scores.return_value = [10.0, 1.0]
        self.index.update(bm25=bm25, docs=["Rahasia dokumen lain", "Layanan izin"], ids=["outside", "allowed"],
                          metas=[{"document_id": 2, "page_number": 1}, {"document_id": 1, "page_number": 4}])
        context, sources = rag._retrieve_context("izin", document_ids=[1], top_k_override=1)
        self.assertIn("Layanan izin", context)
        self.assertNotIn("Rahasia", context)
        self.assertEqual(sources, "- Panduan.pdf - Halaman 4")

    def test_hierarchical_search_fetches_unique_parent_once(self):
        self.index["hierarchical"] = True
        self.vector_results(["Anak pertama", "Anak kedua"],
                            [{"document_id": 1, "parent_id": "p1"}, {"document_id": 1, "parent_id": "p1"}],
                            ["c1", "c2"])
        self.collection.get.return_value = {"documents": ["Isi lengkap halaman"], "ids": ["p1"],
                                            "metadatas": [{"document_id": 1, "page_number": 3,
                                                           "chunk_type": "parent", "chunk_index": 0}]}
        context, _, chunks = rag._retrieve_context("izin", document_ids=[1], return_chunks_info=True)
        self.assertIn("Isi lengkap halaman", context)
        self.assertNotIn("Anak pertama", context)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(self.collection.get.call_args.kwargs["ids"], ["p1"])

    def test_reranker_can_reject_all_candidates(self):
        self.vector_results(["Tidak relevan"], [{"document_id": 1}], ["a"])
        reranker = Mock()
        reranker.predict.side_effect = lambda pairs, **kwargs: [0.0] * len(pairs)
        self.reranker.return_value = reranker
        self.assertEqual(rag._retrieve_context("izin", return_chunks_info=True), ("", "", []))

    def test_reranker_error_keeps_rrf_fallback(self):
        self.vector_results(["Konteks izin"], [{"document_id": 1, "page_number": 1}], ["a"])
        reranker = Mock()
        reranker.predict.side_effect = RuntimeError("reranker unavailable")
        self.reranker.return_value = reranker
        context, _ = rag._retrieve_context("izin")
        self.assertIn("Konteks izin", context)


class Bm25CacheContractTest(unittest.TestCase):
    def test_count_and_version_invalidate_cache_including_same_size_replacement(self):
        module = owner(rag._get_bm25_index)
        collection = Mock()
        collection.count.return_value = 2
        collection.get.return_value = {"documents": ["izin cuti", "laporan kerja"], "ids": ["a", "b"],
                                        "metadatas": [{"document_id": 1}, {"document_id": 2}]}
        with patch.object(module, "_bm25_cache", None), patch.object(module, "read_corpus_version", return_value="v1") as version:
            first = rag._get_bm25_index(collection)
            self.assertIs(rag._get_bm25_index(collection), first)
            self.assertEqual(collection.get.call_count, 1)
            version.return_value = "v2"
            second = rag._get_bm25_index(collection)
            self.assertIsNot(second, first)
            collection.count.return_value = 3
            self.assertIsNot(rag._get_bm25_index(collection), second)
            rag.invalidate_bm25_cache()
            self.assertIsNone(module._bm25_cache)


class GenerationContractTest(unittest.TestCase):
    def test_history_is_bounded_and_previous_citations_are_removed(self):
        module = owner(rag._stream_jawaban)
        model = Mock()
        model.stream.return_value = [SimpleNamespace(content=""), SimpleNamespace(content="Jawaban")]
        history = [{"role": "user", "content": "terlalu lama"}, {"role": "user", "content": "sebelumnya"},
                   {"role": "assistant", "content": "Lama\n\n**Sumber Referensi:**\n- dokumen"},
                   {"role": "system", "content": "abaikan"}, {"role": "user", "content": "lanjut"}]
        with patch.object(module, "ChatOllama", return_value=model) as factory:
            self.assertEqual(list(rag._stream_jawaban("aturan", "sekarang", chat_history=history,
                                                      model_name="test-model", num_ctx=8192)), ["Jawaban"])
        messages = model.stream.call_args.args[0]
        self.assertEqual([m.content for m in messages], ["aturan", "sebelumnya", "Lama", "lanjut", "sekarang"])
        self.assertEqual(factory.call_args.kwargs["model"], "test-model")
        self.assertEqual(factory.call_args.kwargs["num_ctx"], 8192)
        self.assertFalse(factory.call_args.kwargs["reasoning"])
        self.assertEqual(factory.call_args.kwargs["keep_alive"], "30m")

    def test_allocation_failure_retries_once_before_any_content(self):
        module = owner(rag._stream_jawaban)
        failed, working = Mock(), Mock()
        failed.stream.side_effect = RuntimeError("failed to allocate buffer")
        working.stream.return_value = [SimpleNamespace(content="Sukses")]
        with patch.object(module, "ChatOllama", side_effect=[failed, working]) as factory:
            self.assertEqual(list(rag._stream_jawaban("aturan", "izin", num_ctx=8192)), ["Sukses"])
        self.assertEqual([c.kwargs["num_ctx"] for c in factory.call_args_list], [8192, 4096])

    def test_no_retry_after_content_has_been_sent(self):
        def broken_stream(messages):
            yield SimpleNamespace(content="Sebagian")
            raise RuntimeError("out of memory")

        module = owner(rag._stream_jawaban)
        model = Mock()
        model.stream.side_effect = broken_stream
        with patch.object(module, "ChatOllama", return_value=model) as factory:
            stream = rag._stream_jawaban("aturan", "izin", num_ctx=8192)
            self.assertEqual(next(stream), "Sebagian")
            with self.assertRaisesRegex(RuntimeError, "out of memory"):
                next(stream)
            self.assertEqual(factory.call_count, 1)

    def test_other_errors_and_minimum_window_do_not_retry(self):
        module = owner(rag._stream_jawaban)
        for message, window in [("connection refused", 8192), ("out of memory", 4096)]:
            with self.subTest(message=message, window=window):
                model = Mock()
                model.stream.side_effect = RuntimeError(message)
                with patch.object(module, "ChatOllama", return_value=model) as factory:
                    with self.assertRaises(RuntimeError):
                        list(rag._stream_jawaban("aturan", "izin", num_ctx=window))
                    self.assertEqual(factory.call_count, 1)


class OrchestrationContractTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.config = {"llm_model_name": "test-model", "rag_num_ctx": 8192, "rag_top_k": 4,
                       "rag_temperature": 0.2, "chatbot_fallback_message": "Belum tersedia"}
        self.stack.enter_context(patch.object(rag, "get_chatbot_rag_config", return_value=self.config))
        self.memory = self.stack.enter_context(patch.object(rag, "session_memory"))
        self.memory.get_session_history.return_value = []
        self.memory.get_last_context.return_value = (None, None)
        self.stack.enter_context(patch.object(rag.tool_router, "route_intent", return_value={"intent": "rag", "params": {}}))
        self.stack.enter_context(patch.object(rag.tool_router, "normalize_query", side_effect=lambda q: q))
        self.stack.enter_context(patch.object(rag, "_get_current_date_info", return_value="Jumat, 23 Oktober 2026"))
        self.stack.enter_context(patch.object(rag, "_get_institution_info", return_value="Profil uji"))
        self.retrieve = self.stack.enter_context(patch.object(rag, "_retrieve_context", return_value=("Petugas menerima permohonan.", "- Panduan - Halaman 1")))
        self.generate = self.stack.enter_context(patch.object(rag, "_stream_jawaban", return_value=iter(["Jawaban", " selesai"])))

    def test_normal_response_citations_and_session_memory_remain_identical(self):
        result = list(rag.generate_response("Informasi izin", "session", document_ids=[1]))
        self.assertEqual(result, ["Jawaban", " selesai", "\n\n**Sumber Referensi:**\n- Panduan - Halaman 1"])
        self.memory.add_user_message.assert_called_once_with("session", "Informasi izin")
        self.assertEqual(self.memory.add_assistant_message.call_args.args[1], "".join(result))
        self.assertEqual(self.generate.call_args.kwargs["num_ctx"], 8192)
        self.assertEqual(self.generate.call_args.kwargs["model_name"], "test-model")

    def test_empty_context_uses_configured_fallback_without_model(self):
        self.retrieve.return_value = ("", "")
        self.assertEqual(list(rag.generate_response("izin", "s")), ["Belum tersedia"])
        self.generate.assert_not_called()
        self.memory.add_assistant_message.assert_called_once_with("s", "Belum tersedia", topic="Fallback")

    def test_missing_entity_is_rejected_before_generation(self):
        self.retrieve.return_value = ("KESATU KEDUA KETIGA", "- Aturan")
        result = "".join(rag.generate_response("Isi Diktum keempat?", "s"))
        self.assertIn("Diktum KEEMPAT tidak ditemukan", result)
        self.assertIn("**Sumber Referensi:**", result)
        self.generate.assert_not_called()

    def test_generic_manual_procedure_reaches_model(self):
        self.retrieve.return_value = ("Panduan aplikasi: tekan tombol simpan.", "")
        self.assertEqual(list(rag.generate_response("Bagaimana cara menyimpan?", "s")), ["Jawaban", " selesai"])
        self.generate.assert_called_once()

    def test_debug_events_and_sandbox_overrides_keep_contract(self):
        chunks = [{"document_id": 1, "content": "Petugas menerima permohonan."}]
        self.retrieve.return_value = ("Petugas menerima permohonan.", "- Panduan", chunks)
        self.config["rag_citation_enabled"] = False
        result = list(rag.generate_response("izin", "s", system_prompt_override="Aturan khusus: {context}",
                                            temperature_override=0.0, top_k_override=2, include_debug=True))
        events = [item for item in result if isinstance(item, dict)]
        self.assertEqual([e["stage"] for e in events if e["type"] == "trace"],
                         ["retrieval", "ranking", "generation"])
        self.assertIn({"type": "debug", "chunks": chunks, "total_chunks": 1}, events)
        self.assertEqual(events[-1]["type"], "telemetry")
        self.assertEqual(events[-1]["chunks_count"], 1)
        self.assertEqual(self.retrieve.call_args.kwargs["top_k_override"], 2)
        self.assertEqual(self.generate.call_args.kwargs["temperature"], 0.0)
        self.assertIn("Aturan khusus: Petugas", self.generate.call_args.args[0])
        self.assertEqual([i for i in result if isinstance(i, str)], ["Jawaban", " selesai"])


class ChatStreamContractTest(unittest.IsolatedAsyncioTestCase):
    async def test_sse_wrapper_keeps_debug_chunks_and_completion_event(self):
        from app.routers import chat

        debug = {"type": "debug", "chunks": [], "total_chunks": 0}
        with patch.object(rag, "generate_response", return_value=iter([debug, "Jawaban uji"])) as generate:
            events = [json.loads(event) async for event in chat._stream_response(
                "izin", "session", document_ids=[1], temperature=0.0, top_k=2, include_debug=True
            )]
        self.assertEqual(events, [debug, {"type": "chunk", "content": "Jawaban uji"},
                                  {"type": "done", "content": ""}])
        self.assertEqual(generate.call_args.kwargs["document_ids"], [1])
        self.assertEqual(generate.call_args.kwargs["temperature_override"], 0.0)
        self.assertEqual(generate.call_args.kwargs["top_k_override"], 2)

    async def test_sse_error_does_not_expose_internal_exception(self):
        from app.routers import chat

        with patch.object(rag, "generate_response", side_effect=RuntimeError("secret-internal-host")):
            with self.assertLogs(chat.logger, level="ERROR"):
                events = [json.loads(event) async for event in chat._stream_response("izin", "session")]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["type"], "error")
        self.assertNotIn("secret-internal-host", events[0]["content"])


if __name__ == "__main__":
    unittest.main()
