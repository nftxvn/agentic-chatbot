"""Cancellation fences at the encoder/Chroma boundary, without live services."""

import unittest
from contextlib import ExitStack, contextmanager
from unittest.mock import Mock, patch

from app.services.document_operations import DocumentOperationCancelled
from app.services.embeddings import vector_store


class Guard:
    def __init__(self, document_id=7, token="old-generation"):
        self.document_id = document_id
        self.token = token
        self.cancelled = False
        self.locked = False
        self.cancel_on_write = False
        self.writes = 0

    def checkpoint(self):
        if self.cancelled:
            raise DocumentOperationCancelled("synthetic cancellation")

    @contextmanager
    def write(self):
        if self.cancel_on_write:
            self.cancelled = True
        self.checkpoint()
        assert not self.locked
        self.locked = True
        self.writes += 1
        try:
            yield None
        finally:
            self.locked = False


class VectorCancellationTest(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.guard = Guard()
        self.collection = Mock()
        self.get_collection = self.stack.enter_context(patch.object(
            vector_store, "get_chroma_collection", return_value=self.collection,
        ))
        self.encode = self.stack.enter_context(patch.object(
            vector_store, "encode_texts", side_effect=lambda texts: [[0.1, 0.2] for _ in texts],
        ))
        self.invalidate = self.stack.enter_context(patch.object(vector_store, "_invalidate_search_index"))
        self.progress = []
        self.parents = [{"text": "Parent", "page_number": 1, "chunk_index": 0}]
        self.children = [{"text": "Child", "page_number": 1, "chunk_index": 0, "parent_index": 0}]

    def progress_callback(self, percent, message):
        self.assertFalse(self.guard.locked, "progress callback opened while document row was locked")
        self.progress.append(percent)

    def run_embedding(self, guarded=True):
        return vector_store.embed_and_store_hierarchical(
            7, self.parents, self.children, self.progress_callback,
            operation_guard=self.guard if guarded else None,
        )

    def test_unguarded_call_preserves_legacy_ids_metadata_and_progress(self):
        self.assertEqual(self.run_embedding(guarded=False), 2)
        parent, child = self.collection.upsert.call_args_list
        self.assertEqual(parent.kwargs["ids"], ["doc_7_parent_0"])
        self.assertEqual(parent.kwargs["metadatas"], [{
            "document_id": 7, "page_number": 1, "chunk_index": 0, "chunk_type": "parent",
        }])
        self.assertEqual(child.kwargs["ids"], ["doc_7_child_0"])
        self.assertEqual(child.kwargs["metadatas"], [{
            "document_id": 7, "page_number": 1, "chunk_index": 0,
            "chunk_type": "child", "parent_id": "doc_7_parent_0",
        }])
        self.assertEqual(self.progress, [35, 45, 55, 95, 100])
        self.invalidate.assert_called_once_with()

    def test_guarded_batches_are_locked_and_tagged_but_progress_is_outside_lock(self):
        def upsert(**kwargs):
            self.assertTrue(self.guard.locked)
            self.assertTrue(all(meta["operation_token"] == "old-generation" for meta in kwargs["metadatas"]))

        self.collection.upsert.side_effect = upsert
        self.assertEqual(self.run_embedding(), 2)
        self.assertEqual(self.guard.writes, 2)
        self.assertFalse(self.guard.locked)
        self.assertEqual(self.progress, [35, 45, 55, 95, 100])

    def test_cancellation_during_parent_encoding_discards_computed_embeddings(self):
        def encode(texts):
            self.guard.cancelled = True
            return [[0.1, 0.2] for _ in texts]

        self.encode.side_effect = encode
        with self.assertRaises(DocumentOperationCancelled):
            self.run_embedding()
        self.collection.upsert.assert_not_called()
        self.assertNotIn(100, self.progress)
        self.invalidate.assert_not_called()

    def test_cancellation_during_child_encoding_does_not_commit_child_batch(self):
        def encode(texts):
            if self.encode.call_count == 2:
                self.guard.cancelled = True
            return [[0.1, 0.2] for _ in texts]

        self.encode.side_effect = encode
        with self.assertRaises(DocumentOperationCancelled):
            self.run_embedding()
        self.assertEqual(self.collection.upsert.call_count, 1)
        self.assertEqual(self.collection.upsert.call_args.kwargs["ids"], ["doc_7_parent_0"])
        self.assertNotIn(95, self.progress)
        self.assertNotIn(100, self.progress)
        self.invalidate.assert_not_called()

    def test_cancellation_between_parent_batches_stops_remaining_writes_and_child_encoding(self):
        self.parents = [{"text": f"Parent {i}", "page_number": 1, "chunk_index": i} for i in range(51)]
        self.collection.upsert.side_effect = lambda **kwargs: setattr(self.guard, "cancelled", True)
        with self.assertRaises(DocumentOperationCancelled):
            self.run_embedding()
        self.assertEqual(self.collection.upsert.call_count, 1)
        self.assertEqual(len(self.collection.upsert.call_args.kwargs["ids"]), 50)
        self.assertEqual(self.encode.call_count, 1)
        self.assertNotIn(100, self.progress)

    def test_cancel_after_final_batch_prevents_completion_progress(self):
        def upsert(**kwargs):
            if kwargs["ids"] == ["doc_7_child_0"]:
                self.guard.cancelled = True

        self.collection.upsert.side_effect = upsert
        with self.assertRaises(DocumentOperationCancelled):
            self.run_embedding()
        self.assertEqual(self.collection.upsert.call_count, 2)
        self.assertNotIn(95, self.progress)
        self.assertNotIn(100, self.progress)

    def test_cancel_at_locked_write_revalidates_after_checkpoint(self):
        self.guard.cancel_on_write = True
        with self.assertRaises(DocumentOperationCancelled):
            self.run_embedding()
        self.collection.upsert.assert_not_called()
        self.assertNotIn(100, self.progress)

    def test_guard_for_another_document_cannot_authorize_embedding(self):
        self.guard.document_id = 8
        with self.assertRaisesRegex(ValueError, "different document"):
            self.run_embedding()
        self.get_collection.assert_not_called()
        self.encode.assert_not_called()

    def test_guarded_delete_holds_write_lock(self):
        self.collection.get.return_value = {"ids": ["doc_7_parent_0"]}
        self.collection.delete.side_effect = lambda **kwargs: self.assertTrue(self.guard.locked)
        self.assertEqual(vector_store.delete_document_vectors(7, operation_guard=self.guard), 1)
        self.collection.delete.assert_called_once_with(where={"document_id": 7})
        self.assertFalse(self.guard.locked)

    def test_cancel_before_delete_does_not_open_collection(self):
        self.guard.cancelled = True
        with self.assertRaises(DocumentOperationCancelled):
            vector_store.delete_document_vectors(7, operation_guard=self.guard)
        self.get_collection.assert_not_called()

    def test_generation_cleanup_deletes_only_old_token_under_document_lock(self):
        rows = {
            "old-parent": {"document_id": 7, "operation_token": "old-generation"},
            "new-child": {"document_id": 7, "operation_token": "new-generation"},
            "other-doc": {"document_id": 8, "operation_token": "old-generation"},
        }
        locked = []

        @contextmanager
        def lock(document_id):
            self.assertEqual(document_id, 7)
            locked.append(True)
            try:
                yield None
            finally:
                locked.pop()

        def matches(metadata, where):
            return all(all(metadata.get(key) == value for key, value in clause.items()) for clause in where["$and"])

        def get(**kwargs):
            self.assertTrue(locked)
            return {"ids": [row_id for row_id, metadata in rows.items() if matches(metadata, kwargs["where"])]}

        def delete(**kwargs):
            self.assertTrue(locked)
            self.assertNotIn("ids", kwargs)
            for row_id in [row_id for row_id, metadata in rows.items() if matches(metadata, kwargs["where"])]:
                del rows[row_id]

        self.collection.get.side_effect = get
        self.collection.delete.side_effect = delete
        self.invalidate.side_effect = lambda: self.assertFalse(locked)
        with patch.object(vector_store, "lock_document", side_effect=lock):
            self.assertEqual(vector_store.delete_operation_vectors(7, "old-generation"), 1)
        self.assertEqual(set(rows), {"new-child", "other-doc"})
        self.collection.delete.assert_called_once_with(where={"$and": [
            {"document_id": 7}, {"operation_token": "old-generation"},
        ]})
        self.invalidate.assert_called_once_with()

    def test_generation_cleanup_with_no_matching_vectors_does_not_delete_or_invalidate(self):
        self.collection.get.return_value = {"ids": []}
        with patch.object(vector_store, "lock_document", return_value=Guard().write()):
            self.assertEqual(vector_store.delete_operation_vectors(7, "old-generation"), 0)
        self.collection.delete.assert_not_called()
        self.invalidate.assert_not_called()

    def test_generation_cleanup_requires_token_instead_of_broad_document_delete(self):
        with self.assertRaisesRegex(ValueError, "token is required"):
            vector_store.delete_operation_vectors(7, "")
        self.get_collection.assert_not_called()


if __name__ == "__main__":
    unittest.main()
