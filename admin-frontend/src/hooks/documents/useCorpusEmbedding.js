import { useState } from "react";
import { documentsApi } from "../../api/documents";
import { trackActiveEmbedding, clearActiveEmbedding } from "../../utils/activeEmbedding";

/** State dan request penyimpanan korpus; listener hasil tetap di orkestrator editor. */
export function useCorpusEmbedding({
  documentId,
  parentSize,
  parentOverlap,
  childSize,
  childOverlap,
  selectedPreset,
  setShowChunksModal,
  documentTitle,
  persistCorrection,
}) {
  // Save to Corpus State
  const [isSavingCorpus, setIsSavingCorpus] = useState(false);
  const [showSaveCorpusConfirm, setShowSaveCorpusConfirm] = useState(false);
  const [showEmbedProgressModal, setShowEmbedProgressModal] = useState(false);
  const [corpusMsg, setCorpusMsg] = useState("");

  // Finalize & save to ChromaDB corpus trigger
  const handleSaveToCorpus = () => {
    setShowSaveCorpusConfirm(true);
  };

  const executeSaveToCorpus = async () => {
    setShowSaveCorpusConfirm(false);
    if (!(await persistCorrection())) return;
    setShowEmbedProgressModal(true);
    setIsSavingCorpus(true);
    try {
      await documentsApi.saveToCorpus(documentId, {
        parent_chunk_size: parentSize,
        parent_chunk_overlap: parentOverlap,
        child_chunk_size: childSize,
        child_chunk_overlap: childOverlap,
        strategy: selectedPreset,
      });
      setShowChunksModal(false);

      // Daftarkan ke background tracker HANYA setelah antrean berhasil dibuat di backend
      const resolvedTitle = documentTitle || `Dokumen #${documentId}`;
      trackActiveEmbedding({ documentId, title: resolvedTitle });
    } catch (err) {
      clearActiveEmbedding(documentId);
      alert(err.response?.data?.message || "Gagal menyimpan ke korpus.");
      setShowEmbedProgressModal(false);
    } finally {
      setIsSavingCorpus(false);
    }
  };

  return {
    isSavingCorpus,
    showSaveCorpusConfirm,
    setShowSaveCorpusConfirm,
    showEmbedProgressModal,
    setShowEmbedProgressModal,
    corpusMsg,
    setCorpusMsg,
    handleSaveToCorpus,
    executeSaveToCorpus,
  };
}
