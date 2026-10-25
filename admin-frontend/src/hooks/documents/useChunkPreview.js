import { useState } from "react";
import { documentsApi } from "../../api/documents";

/**
 * State dan request pratinjau chunk untuk editor koreksi.
 * JSX, animasi, filter tampilan, clipboard, dan penyimpanan korpus tetap di komponen.
 * Tidak memiliki effect: urutan effect editor dan lifecycle request tetap sama.
 */
export function useChunkPreview(documentId) {
  const [showChunksModal, setShowChunksModal] = useState(false);
  const [chunksPreview, setChunksPreview] = useState(null);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState("sop");
  const [parentSize, setParentSize] = useState(1500);
  const [parentOverlap, setParentOverlap] = useState(200);
  const [childSize, setChildSize] = useState(300);
  const [childOverlap, setChildOverlap] = useState(50);

  const CHUNK_PRESETS = [
    {
      id: "sop",
      label: "SOP & Prosedur",
      desc: "Menjaga keutuhan tiap langkah, waktu, dan pelaksana.",
      parentSize: 1500,
      parentOverlap: 200,
      childSize: 300,
      childOverlap: 50,
      strategy: "sop",
    },
    {
      id: "general",
      label: "Deskriptif / Laporan",
      desc: "Buku panduan, narasi, dan kajian umum.",
      parentSize: 2000,
      parentOverlap: 250,
      childSize: 400,
      childOverlap: 60,
      strategy: "general",
    },
    {
      id: "regulasi",
      label: "Regulasi & Pasal",
      desc: "Menjaga keutuhan pasal, ayat, dan pertimbangan hukum.",
      parentSize: 1800,
      parentOverlap: 200,
      childSize: 350,
      childOverlap: 50,
      strategy: "regulasi",
    },
    {
      id: "faq",
      label: "FAQ / Butir Singkat",
      desc: "Potongan ringkas dan tajam untuk tanya-jawab cepat.",
      parentSize: 1000,
      parentOverlap: 150,
      childSize: 200,
      childOverlap: 40,
      strategy: "faq",
    },
  ];

  const fetchChunksPreviewWithParams = async (customParams = {}) => {
    setLoadingChunks(true);
    try {
      const payload = {
        parent_chunk_size: customParams.parent_chunk_size ?? parentSize,
        parent_chunk_overlap:
          customParams.parent_chunk_overlap ?? parentOverlap,
        child_chunk_size: customParams.child_chunk_size ?? childSize,
        child_chunk_overlap: customParams.child_chunk_overlap ?? childOverlap,
        strategy: customParams.strategy ?? selectedPreset,
      };
      const res = await documentsApi.getChunksPreview(documentId, payload);
      const data = res.data || null;
      setChunksPreview(data);
    } catch (err) {
      alert(err.response?.data?.message || "Gagal memuat pratinjau potongan.");
    } finally {
      setLoadingChunks(false);
    }
  };

  const handlePreviewChunks = async () => {
    setShowChunksModal(true);
    fetchChunksPreviewWithParams();
  };

  const handleSelectPreset = (presetId) => {
    setSelectedPreset(presetId);
    const p = CHUNK_PRESETS.find((x) => x.id === presetId);
    if (p) {
      setParentSize(p.parentSize);
      setParentOverlap(p.parentOverlap);
      setChildSize(p.childSize);
      setChildOverlap(p.childOverlap);
      fetchChunksPreviewWithParams({
        parent_chunk_size: p.parentSize,
        parent_chunk_overlap: p.parentOverlap,
        child_chunk_size: p.childSize,
        child_chunk_overlap: p.childOverlap,
        strategy: p.strategy,
      });
    }
  };

  return {
    showChunksModal,
    setShowChunksModal,
    chunksPreview,
    loadingChunks,
    selectedPreset,
    setSelectedPreset,
    parentSize,
    setParentSize,
    parentOverlap,
    setParentOverlap,
    childSize,
    setChildSize,
    childOverlap,
    setChildOverlap,
    CHUNK_PRESETS,
    fetchChunksPreviewWithParams,
    handlePreviewChunks,
    handleSelectPreset,
  };
}
