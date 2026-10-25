import { useCorrectionPersistence } from "./useCorrectionPersistence";
import { useSearchParams } from "react-router-dom";
import { useState, useEffect, useCallback, useRef } from "react";
import { useChunkPreview } from "./useChunkPreview";
import { useCorpusEmbedding } from "./useCorpusEmbedding";
import gsap from "gsap";
import { documentsApi } from "../../api/documents";
import { useCorrectionViewport } from "./useCorrectionViewport";

/** Orkestrasi data halaman, draft, autosave, navigasi, dan komposisi hook editor. */
export function useCorrectionEditor({
  documentId,
  documentTitle,
  totalPages,
  isExtractionCompleted,
  status,
  timestamp,
  onSaveToCorpusSuccess,
}) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Read initial page: URL param (?page=X or ?hal=X) -> localStorage -> default 1
  const getInitialPage = () => {
    const param = searchParams.get("page") || searchParams.get("hal");
    const parsedParam = parseInt(param, 10);
    if (parsedParam && parsedParam >= 1) return parsedParam;

    try {
      const saved = parseInt(
        localStorage.getItem(`doc_${documentId}_last_page`),
        10,
      );
      if (saved && saved >= 1) return saved;
    } catch (e) {}

    return 1;
  };

  const [currentPage, setCurrentPage] = useState(getInitialPage);
  const [zoom, setZoom] = useState(2.0);
  const [allowedZooms, setAllowedZooms] = useState([1.5, 2.0, 3.0, 4.0]);
  const [pageSizes, setPageSizes] = useState([]);

  // Image loading & error state
  const [imageState, setImageState] = useState("loading");

  // 'loading' | 'loaded' | 'error'
  const [imageRetryKey, setImageRetryKey] = useState(0);
  const imgRef = useRef(null);

  // Pages data & inspection filter
  const [pages, setPages] = useState([]);
  const [onlySuspicious, setOnlySuspicious] = useState(false);
  const [suspiciousPages, setSuspiciousPages] = useState([]);
  const [currentText, setCurrentText] = useState("");
  const [originalSavedText, setOriginalSavedText] = useState("");
  const [isSavingText, setIsSavingText] = useState(false);
  const [saveSuccessMsg, setSaveSuccessMsg] = useState("");
  const [saveStatus, setSaveStatus] = useState("idle");

  // 'idle' | 'saved' | 'saving' | 'unsaved' | 'error'
  const [lastSavedTime, setLastSavedTime] = useState("");
  const autoSaveTimerRef = useRef(null);
  const savedFadeTimerRef = useRef(null);

  // Chunks Preview & Customization State
  const {
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
  } = useChunkPreview(documentId);

  const [activeChunkTab, setActiveChunkTab] = useState("all");

  // 'all' | 'child' | 'parent'
  const [selectedParentFilter, setSelectedParentFilter] = useState(null);

  // number (parent_index) | null
  const [highlightedParentIndex, setHighlightedParentIndex] = useState(null);
  const [expandedParents, setExpandedParents] = useState(new Set());
  const [chunkSearchQuery, setChunkSearchQuery] = useState("");
  const [copiedContext, setCopiedContext] = useState(false);

  const {
    isSavingCorpus,
    showSaveCorpusConfirm,
    setShowSaveCorpusConfirm,
    showEmbedProgressModal,
    setShowEmbedProgressModal,
    corpusMsg,
    setCorpusMsg,
    handleSaveToCorpus,
    executeSaveToCorpus,
  } = useCorpusEmbedding({
    documentId,
    parentSize,
    parentOverlap,
    childSize,
    childOverlap,
    selectedPreset,
    setShowChunksModal,
    documentTitle,
    persistCorrection: () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
      // Await queued writes too, including autosaves already in flight.
      return savePageText(currentText, currentPage, true);
    },
  });

  const chunksModalRef = useRef(null);
  const chunksListRef = useRef(null);

  // GSAP: Animate Chunks Modal Entrance
  useEffect(() => {
    if (showChunksModal && chunksModalRef.current) {
      gsap.killTweensOf(chunksModalRef.current);
      gsap.fromTo(
        chunksModalRef.current,
        { scale: 0.94, opacity: 0, y: 16 },
        { scale: 1, opacity: 1, y: 0, duration: 0.32, ease: "power3.out" }
      );
    }
  }, [showChunksModal]);

  // GSAP: Stagger Animate Chunks Cards on Tab/Filter Change
  useEffect(() => {
    if (showChunksModal && chunksListRef.current) {
      const items = chunksListRef.current.querySelectorAll(".chunk-card-anim");
      if (items && items.length > 0) {
        gsap.killTweensOf(items);
        gsap.fromTo(
          items,
          { opacity: 0, y: 12 },
          {
            opacity: 1,
            y: 0,
            duration: 0.28,
            stagger: 0.025,
            ease: "power2.out",
            clearProps: "transform,opacity",
          }
        );
      }
    }
  }, [showChunksModal, activeChunkTab, selectedParentFilter, chunkSearchQuery, chunksPreview]);

  const maxPages = pageSizes.length || totalPages || 1;

  // Clamp currentPage if totalPages/maxPages shrinks (e.g. after replacing file with fewer pages)
  useEffect(() => {
    if (maxPages > 0 && currentPage > maxPages) {
      setCurrentPage(1);
    }
  }, [maxPages, currentPage]);

  // Tombol simpan ke korpus hanya aktif jika seluruh halaman sudah selesai diekstrak
  const isReadyToSave =
    isExtractionCompleted ||
    status === "completed" ||
    status === "selesai" ||
    status === "menunggu_koreksi" ||
    (pages.length >= maxPages &&
      maxPages > 0 &&
      status !== "processing" &&
      status !== "berjalan" &&
      status !== "pending");

  // Reset image state and scroll position on page or zoom change
  useEffect(() => {
    // If the image is already cached or completed by browser, immediately mark loaded
    if (
      imgRef.current &&
      imgRef.current.complete &&
      imgRef.current.naturalWidth > 0
    ) {
      setImgNaturalDim({
        width: imgRef.current.naturalWidth,
        height: imgRef.current.naturalHeight,
      });
      setImageState("loaded");
    } else {
      setImageState("loading");
    }

    if (imageContainerRef.current) {
      imageContainerRef.current.scrollTop = 0;
      imageContainerRef.current.scrollLeft = 0;
    }
  }, [currentPage, zoom, documentId, timestamp, imageRetryKey]);

  // Fetch page dimensions once on mount / documentId change / timestamp change
  const fetchPageSizes = useCallback(async () => {
    try {
      const res = await documentsApi.getPageSizes(documentId);
      if (res.data) {
        if (res.data.zoom_diizinkan) setAllowedZooms(res.data.zoom_diizinkan);
        if (res.data.zoom_bawaan)
          setZoom((prev) => prev || res.data.zoom_bawaan);
        if (res.data.halaman) setPageSizes(res.data.halaman);
      }
    } catch (err) {
      console.warn("Gagal memuat ukuran halaman:", err);
    }
  }, [documentId]);

  // Fetch list of pages
  const fetchPages = useCallback(async () => {
    try {
      const res = await documentsApi.getPages(documentId, onlySuspicious);
      if (res.data && res.data.halaman) {
        const fetchedPages = res.data.halaman;
        setPages(fetchedPages);

        // Suspicious list
        if (res.data.halaman_mencurigakan) {
          setSuspiciousPages(res.data.halaman_mencurigakan);
        }
      }
    } catch (err) {
      console.error("Gagal mengambil daftar halaman:", err);
    }
  }, [documentId, onlySuspicious]);

  // Initial load
  useEffect(() => {
    fetchPageSizes();
    fetchPages();
  }, [fetchPageSizes, fetchPages, timestamp]);

  // Sync initial currentText when pages are first fetched
  useEffect(() => {
    if (pages.length > 0) {
      const found = pages.find((p) => p.page_number === currentPage);
      if (found && !currentText) {
        setCurrentText(found.text || "");
        setOriginalSavedText(found.text || "");
      }
    }
  }, [pages, currentPage]);

  // Auto-polling for in-flight extraction progress (only if not completed)
  useEffect(() => {
    if (isReadyToSave) return; // No polling needed if extraction already done

    let intervalId = null;
    const pollExtractionPages = async () => {
      try {
        const res = await documentsApi.getPages(documentId, onlySuspicious);
        if (res.data && res.data.halaman) {
          const fetchedPages = res.data.halaman;
          setPages(fetchedPages);

          const found = fetchedPages.find((p) => p.page_number === currentPage);
          if (found) {
            setCurrentText((prev) => {
              if (!prev || prev === originalSavedText) {
                setOriginalSavedText(found.text);
                return found.text;
              }
              return prev;
            });
          }

          if (res.data.halaman_mencurigakan) {
            setSuspiciousPages(res.data.halaman_mencurigakan);
          }
        }
      } catch (err) {
        // Silent failure in background polling
      }
    };

    intervalId = setInterval(pollExtractionPages, 3500);
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [
    documentId,
    currentPage,
    originalSavedText,
    onlySuspicious,
    isReadyToSave,
  ]);

  // Save page text (used by manual save, auto-save debounce, and save-before-navigation)
  // React setters stay stable; this lazy callback preserves the existing hook order.
  const resetViewport = () => {
    setFitMode("auto");
    setZoomScale(100);
  };

  const {
    savePageText,
    handlePageChange,
  } = useCorrectionPersistence({
    documentId,
    setIsSavingText,
    setSaveStatus,
    setOriginalSavedText,
    setLastSavedTime,
    savedFadeTimerRef,
    setSaveSuccessMsg,
    setPages,
    currentText,
    originalSavedText,
    autoSaveTimerRef,
    currentPage,
    maxPages,
    resetViewport,
    setCurrentPage,
    setSearchParams,
    pages,
    setCurrentText,
    searchParams,
    showChunksModal,
  });

  const handleCopyText = (text, key) => {
    if (!text) return;
    try {
      navigator.clipboard.writeText(text);
      setCopiedContext(key !== undefined ? key : true);
      setTimeout(() => setCopiedContext(null), 2000);
    } catch (e) {
      console.warn("Gagal menyalin teks:", e);
    }
  };

  // Dengarkan event penyelesaian embedding background secara real-time
  useEffect(() => {
    const handleSuccess = (e) => {
      if (Number(e.detail?.documentId) === Number(documentId)) {
        setCorpusMsg("Berhasil disimpan ke ChromaDB!");
        if (onSaveToCorpusSuccess) onSaveToCorpusSuccess();
      }
    };
    const handleFailed = (e) => {
      if (Number(e.detail?.documentId) === Number(documentId)) {
        setCorpusMsg("Gagal menyimpan ke korpus.");
      }
    };

    window.addEventListener("document-embedded-success", handleSuccess);
    window.addEventListener("document-embedded-failed", handleFailed);

    return () => {
      window.removeEventListener("document-embedded-success", handleSuccess);
      window.removeEventListener("document-embedded-failed", handleFailed);
    };
  }, [documentId, onSaveToCorpusSuccess]);

  const isCurrentPageSuspicious = suspiciousPages.some(
    (sp) => sp.page_number === currentPage,
  );

  const suspiciousReason = suspiciousPages.find(
    (sp) => sp.page_number === currentPage,
  )?.alasan;

  const {
    fitMode,
    setFitMode,
    zoomScale,
    setZoomScale,
    splitViewMode,
    setSplitViewMode,
    setImgNaturalDim,
    hasUnsavedChanges,
    imageContainerRef,
    isPanning,
    availW,
    availH,
    computedWidth,
    computedHeight,
    handleZoomIn,
    handleZoomOut,
    handleResetZoom,
    handleMouseDown,
    handleDoubleClick,
  } = useCorrectionViewport({ currentText, originalSavedText, pageSizes, currentPage });

  return {
    currentPage,
    zoom,
    imageState,
    setImageState,
    imageRetryKey,
    setImageRetryKey,
    imgRef,
    pages,
    onlySuspicious,
    setOnlySuspicious,
    suspiciousPages,
    currentText,
    setCurrentText,
    originalSavedText,
    isSavingText,
    saveStatus,
    lastSavedTime,
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
    activeChunkTab,
    setActiveChunkTab,
    selectedParentFilter,
    setSelectedParentFilter,
    highlightedParentIndex,
    setHighlightedParentIndex,
    expandedParents,
    setExpandedParents,
    chunkSearchQuery,
    setChunkSearchQuery,
    copiedContext,
    isSavingCorpus,
    showSaveCorpusConfirm,
    setShowSaveCorpusConfirm,
    showEmbedProgressModal,
    setShowEmbedProgressModal,
    corpusMsg,
    setCorpusMsg,
    handleSaveToCorpus,
    executeSaveToCorpus,
    chunksModalRef,
    chunksListRef,
    maxPages,
    isReadyToSave,
    savePageText,
    handlePageChange,
    handleCopyText,
    isCurrentPageSuspicious,
    suspiciousReason,
    fitMode,
    setFitMode,
    zoomScale,
    splitViewMode,
    setSplitViewMode,
    setImgNaturalDim,
    hasUnsavedChanges,
    imageContainerRef,
    isPanning,
    availW,
    availH,
    computedWidth,
    computedHeight,
    handleZoomIn,
    handleZoomOut,
    handleResetZoom,
    handleMouseDown,
    handleDoubleClick,
  };
}
