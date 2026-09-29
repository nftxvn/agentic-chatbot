import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import gsap from "gsap";
import { documentsApi } from "../api/documents";
import { FloatingSaveBar } from "./UI/FloatingSaveBar";
import ConfirmModal from "./ConfirmModal";
import EmbedProgressModal from "./EmbedProgressModal";
import { InfoTooltip } from "./UI/InfoTooltip";
import { addAppNotification } from "../utils/notifications";
import { trackActiveEmbedding, clearActiveEmbedding } from "../utils/activeEmbedding";

export default function ManualCorrectionEditor({
  documentId,
  documentTitle = "",
  totalPages = 1,
  isExtractionCompleted = false,
  status = "",
  timestamp = null,
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
  const [imageState, setImageState] = useState("loading"); // 'loading' | 'loaded' | 'error'
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
  const [saveStatus, setSaveStatus] = useState("idle"); // 'idle' | 'saved' | 'saving' | 'unsaved' | 'error'
  const [lastSavedTime, setLastSavedTime] = useState("");
  const autoSaveTimerRef = useRef(null);
  const savedFadeTimerRef = useRef(null);

  // Chunks Preview & Customization State
  const [showChunksModal, setShowChunksModal] = useState(false);
  const [chunksPreview, setChunksPreview] = useState(null);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [selectedPreset, setSelectedPreset] = useState("sop");
  const [parentSize, setParentSize] = useState(1500);
  const [parentOverlap, setParentOverlap] = useState(200);
  const [childSize, setChildSize] = useState(300);
  const [childOverlap, setChildOverlap] = useState(50);
  const [activeChunkTab, setActiveChunkTab] = useState("all"); // 'all' | 'child' | 'parent'
  const [selectedParentFilter, setSelectedParentFilter] = useState(null); // number (parent_index) | null
  const [highlightedParentIndex, setHighlightedParentIndex] = useState(null);
  const [expandedParents, setExpandedParents] = useState(new Set());
  const [chunkSearchQuery, setChunkSearchQuery] = useState("");
  const [copiedContext, setCopiedContext] = useState(false);

  // Save to Corpus State
  const [isSavingCorpus, setIsSavingCorpus] = useState(false);
  const [showSaveCorpusConfirm, setShowSaveCorpusConfirm] = useState(false);
  const [showEmbedProgressModal, setShowEmbedProgressModal] = useState(false);
  const [corpusMsg, setCorpusMsg] = useState("");

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
  const savePageText = useCallback(
    async (textToSave, pageNum, isSilent = false) => {
      if (!documentId || !pageNum) return false;
      setIsSavingText(true);
      setSaveStatus("saving");
      try {
        await documentsApi.savePageCorrection(documentId, pageNum, textToSave);
        setOriginalSavedText(textToSave);
        setSaveStatus("saved");
        const now = new Date();
        setLastSavedTime(
          now.toLocaleTimeString("id-ID", {
            hour: "2-digit",
            minute: "2-digit",
          }),
        );
        // Option 1: Flash for 3 seconds then fade out to idle
        if (savedFadeTimerRef.current) clearTimeout(savedFadeTimerRef.current);
        savedFadeTimerRef.current = setTimeout(() => {
          setSaveStatus("idle");
        }, 3000);

        if (!isSilent) {
          setSaveSuccessMsg("Tersimpan!");
          setTimeout(() => setSaveSuccessMsg(""), 2500);
        }

        // Update local pages list
        setPages((prev) =>
          prev.map((p) =>
            p.page_number === pageNum ? { ...p, text: textToSave } : p,
          ),
        );
        return true;
      } catch (err) {
        setSaveStatus("error");
        if (!isSilent) {
          alert(
            err.response?.data?.message || "Gagal menyimpan perubahan teks.",
          );
        }
        return false;
      } finally {
        setIsSavingText(false);
      }
    },
    [documentId],
  );

  // Debounced Auto-Save (1.8 detik setelah user selesai mengetik)
  useEffect(() => {
    if (currentText !== originalSavedText) {
      if (savedFadeTimerRef.current) clearTimeout(savedFadeTimerRef.current);
      setSaveStatus("unsaved");
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
      autoSaveTimerRef.current = setTimeout(() => {
        savePageText(currentText, currentPage, true);
      }, 1800);
    }

    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, [currentText, originalSavedText, currentPage, savePageText]);

  // Navigate page (Otomatis simpan halaman saat ini sebelum berpindah & sinkronisasi URL)
  const handlePageChange = useCallback(
    async (nextPage, syncUrl = true) => {
      if (nextPage < 1 || nextPage > maxPages || nextPage === currentPage)
        return;

      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
      if (savedFadeTimerRef.current) {
        clearTimeout(savedFadeTimerRef.current);
      }
      setSaveStatus("idle");

      // Auto-save perubahan yang masih ada sebelum pindah halaman
      if (currentText !== originalSavedText) {
        await savePageText(currentText, currentPage, true);
      }

      setFitMode("auto");
      setZoomScale(100);
      setCurrentPage(nextPage);

      // Persist to LocalStorage
      try {
        localStorage.setItem(`doc_${documentId}_last_page`, String(nextPage));
      } catch (e) {}

      // Persist to URL SearchParams
      if (syncUrl) {
        setSearchParams(
          (prev) => {
            const nextParams = new URLSearchParams(prev);
            nextParams.set("page", String(nextPage));
            return nextParams;
          },
          { replace: true },
        );
      }

      const targetPage = pages.find((p) => p.page_number === nextPage);
      const text = targetPage ? targetPage.text : "";
      setCurrentText(text);
      setOriginalSavedText(text);
      setSaveStatus("saved");
      setLastSavedTime("");
    },
    [
      maxPages,
      currentPage,
      currentText,
      originalSavedText,
      pages,
      savePageText,
      documentId,
      setSearchParams,
    ],
  );

  // Sync initial URL param if opened without query parameter
  useEffect(() => {
    const param = searchParams.get("page") || searchParams.get("hal");
    if (!param && currentPage >= 1) {
      setSearchParams(
        (prev) => {
          const nextParams = new URLSearchParams(prev);
          nextParams.set("page", String(currentPage));
          return nextParams;
        },
        { replace: true },
      );
    }
  }, []);

  // Listen to browser Back / Forward history buttons
  useEffect(() => {
    const param = searchParams.get("page") || searchParams.get("hal");
    const parsed = parseInt(param, 10);
    if (parsed && parsed >= 1 && parsed !== currentPage && parsed <= maxPages) {
      handlePageChange(parsed, false);
    }
  }, [searchParams]);

  // Manual save current page (dengan opsi lanjut ke halaman berikutnya)
  const handleSavePage = useCallback(
    async (andNext = false) => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
        autoSaveTimerRef.current = null;
      }
      const ok = await savePageText(currentText, currentPage, false);
      if (ok && andNext && currentPage < maxPages) {
        handlePageChange(currentPage + 1);
      }
    },
    [currentText, currentPage, maxPages, savePageText, handlePageChange],
  );

  // Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (showChunksModal) return;

      // Ctrl+S or Cmd+S -> Save
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        handleSavePage(false);
      }
      // Ctrl+Enter or Cmd+Enter -> Save & Next
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleSavePage(true);
      }
      // Alt+Left -> Prev Page
      if (e.altKey && e.key === "ArrowLeft") {
        e.preventDefault();
        handlePageChange(currentPage - 1);
      }
      // Alt+Right -> Next Page
      if (e.altKey && e.key === "ArrowRight") {
        e.preventDefault();
        handlePageChange(currentPage + 1);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showChunksModal, handleSavePage, handlePageChange, currentPage]);

  // Presets definition
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

  // Calculate Chunks with custom params
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

  // Preview chunks modal opener
  const handlePreviewChunks = async () => {
    setShowChunksModal(true);
    fetchChunksPreviewWithParams();
  };

  // Apply preset selection
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

  // Finalize & save to ChromaDB corpus trigger
  const handleSaveToCorpus = () => {
    setShowSaveCorpusConfirm(true);
  };

  const executeSaveToCorpus = async () => {
    setShowSaveCorpusConfirm(false);
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
  const [fitMode, setFitMode] = useState("auto"); // 'auto' | 'width' | 'custom'
  const [zoomScale, setZoomScale] = useState(100); // Percentage: 25% - 400%
  const [splitViewMode, setSplitViewMode] = useState("split"); // 'split' | 'image' | 'editor'
  const [imgNaturalDim, setImgNaturalDim] = useState({ width: 0, height: 0 });
  const hasUnsavedChanges = currentText !== originalSavedText;

  // Mouse Pan / Dragging & Zooming State
  const imageContainerRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(600);
  const [containerHeight, setContainerHeight] = useState(700);
  const [isPanning, setIsPanning] = useState(false);
  const panStartRef = useRef({
    startX: 0,
    startY: 0,
    scrollLeft: 0,
    scrollTop: 0,
  });

  // Measure container dimensions accurately for pixel-perfect zoom calculations
  useEffect(() => {
    const container = imageContainerRef.current;
    if (!container) return;

    const updateDimensions = () => {
      if (imageContainerRef.current) {
        setContainerWidth(imageContainerRef.current.clientWidth);
        setContainerHeight(imageContainerRef.current.clientHeight);
      }
    };
    updateDimensions();

    const ro = new ResizeObserver(updateDimensions);
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  // Determine current page orientation (Landscape vs Portrait)
  const currentPageSize = pageSizes.find((p) => p.page_number === currentPage);
  const isLandscape =
    currentPageSize?.orientasi === "lanskap" ||
    (currentPageSize
      ? currentPageSize.lebar >= currentPageSize.tinggi
      : false) ||
    (imgNaturalDim.width > 0 && imgNaturalDim.width >= imgNaturalDim.height);

  // Natural or fallback dimensions (2x default render scale)
  const natW = imgNaturalDim.width || (currentPageSize?.lebar ? currentPageSize.lebar * 2 : 800);
  const natH = imgNaturalDim.height || (currentPageSize?.tinggi ? currentPageSize.tinggi * 2 : 1130);

  // Available viewport space with padding (p-6 => 48px padding total)
  const availW = Math.max(200, containerWidth - 48);
  const availH = Math.max(200, containerHeight - 48);

  // Base scale to fit entirely within viewport (100% Fit Page)
  const fitPageScale = Math.min(availW / natW, availH / natH, 1.0);
  const fitWidthScale = availW / natW;

  let computedWidth = Math.round(natW * fitPageScale);
  let computedHeight = Math.round(natH * fitPageScale);

  if (fitMode === "width") {
    computedWidth = Math.round(natW * fitWidthScale);
    computedHeight = Math.round(natH * fitWidthScale);
  } else if (fitMode === "custom") {
    const effectiveScale = fitPageScale * (zoomScale / 100);
    computedWidth = Math.round(natW * effectiveScale);
    computedHeight = Math.round(natH * effectiveScale);
  }

  const handleZoomIn = () => {
    setFitMode("custom");
    setZoomScale((prev) => Math.min(400, (Math.floor(prev / 25) + 1) * 25));
  };

  const handleZoomOut = () => {
    setFitMode("custom");
    setZoomScale((prev) => Math.max(25, (Math.ceil(prev / 25) - 1) * 25));
  };

  const handleResetZoom = () => {
    setFitMode("auto");
    setZoomScale(100);
  };

  // Mouse Drag / Pan handlers
  const handleMouseDown = (e) => {
    if (e.button !== 0 || !imageContainerRef.current) return;
    setIsPanning(true);
    panStartRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      scrollLeft: imageContainerRef.current.scrollLeft,
      scrollTop: imageContainerRef.current.scrollTop,
    };
  };

  useEffect(() => {
    if (!isPanning) return;

    const handleMouseMove = (e) => {
      if (!imageContainerRef.current) return;
      e.preventDefault();
      const deltaX = e.clientX - panStartRef.current.startX;
      const deltaY = e.clientY - panStartRef.current.startY;
      imageContainerRef.current.scrollLeft =
        panStartRef.current.scrollLeft - deltaX;
      imageContainerRef.current.scrollTop =
        panStartRef.current.scrollTop - deltaY;
    };

    const handleMouseUp = () => {
      setIsPanning(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isPanning]);

  const handleDoubleClick = () => {
    if (fitMode === "auto") {
      setFitMode("custom");
      setZoomScale(150);
    } else {
      handleResetZoom();
    }
  };

  // Non-passive wheel zoom & boundary scroll isolation listener
  useEffect(() => {
    const container = imageContainerRef.current;
    if (!container) return;

    const onWheel = (e) => {
      if (e.ctrlKey || e.metaKey) {
        // Zoom on Ctrl + Wheel or Pinch
        e.preventDefault();
        const delta = e.deltaY < 0 ? 20 : -20;
        setFitMode("custom");
        setZoomScale((prev) => Math.max(25, Math.min(400, prev + delta)));
      } else {
        // Prevent scroll chaining to parent page when reaching top or bottom boundary
        const { scrollTop, scrollHeight, clientHeight } = container;
        const isAtTop = scrollTop <= 0;
        const isAtBottom =
          Math.ceil(scrollTop + clientHeight) >= scrollHeight - 1;

        if ((e.deltaY < 0 && isAtTop) || (e.deltaY > 0 && isAtBottom)) {
          e.preventDefault();
        }
      }
    };

    container.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      container.removeEventListener("wheel", onWheel);
    };
  }, []);

  return (
    <div className="flex flex-col h-full bg-[var(--bg-card)] overflow-hidden text-[var(--text-primary)]">
      {/* Warning banner if suspicious (Top) */}
      {isCurrentPageSuspicious && (
        <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg-input)] border-b border-[var(--border-color)] text-xs text-amber-500 font-medium shrink-0">
          <div className="flex items-center gap-2">
            <svg
              className="w-4 h-4 text-amber-500 shrink-0"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
            <span>
              <strong>Perhatian Hal. {currentPage}:</strong>{" "}
              {suspiciousReason || "Format mencurigakan"}
            </span>
          </div>
          <span className="text-xs bg-[var(--bg-card)] border border-[var(--border-color)] text-amber-500 px-2 py-0.5 rounded-full font-bold">
            Periksa Teks
          </span>
        </div>
      )}

      {/* 2. Split-View: Left (Image Pane) vs Right (Editor Pane) */}
      <div
        className={`grid flex-1 min-h-0 overflow-hidden divide-y lg:divide-y-0 ${
          splitViewMode === "image"
            ? "grid-cols-1"
            : splitViewMode === "editor"
              ? "grid-cols-1"
              : "grid-cols-1 lg:grid-cols-2 lg:divide-x divide-[var(--border-color)]"
        }`}
      >
        {/* LEFT: Document Image Viewer with Floating Zoom Overlay */}
        {(splitViewMode === "split" || splitViewMode === "image") && (
          <div className="flex flex-col bg-[var(--bg-card)] relative h-full overflow-hidden">
            <div className="px-4 py-2.5 bg-[var(--bg-input)] border-b border-[var(--border-color)] flex justify-between items-center gap-2 text-xs shrink-0 min-h-[45px]">
              <div className="flex items-center gap-2.5">
                <span className="font-bold text-[var(--text-primary)] text-sm">
                  Dokumen Asli
                </span>
                {splitViewMode === "image" && (
                  <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                    Layar Penuh
                  </span>
                )}
              </div>

              <div className="flex items-center gap-1.5">
                {/* Focus / Split Toggle */}
                <button
                  onClick={() =>
                    setSplitViewMode(
                      splitViewMode === "image" ? "split" : "image",
                    )
                  }
                  title={
                    splitViewMode === "image"
                      ? "Kembali ke Tampilan Berdampingan"
                      : "Perluas Dokumen ke Layar Penuh"
                  }
                  className={`p-1.5 rounded-lg border transition-all flex items-center justify-center cursor-pointer ${
                    splitViewMode === "image"
                      ? "bg-sky-500 text-white border-sky-500 shadow-xs"
                      : "bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-sky-500"
                  }`}
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    {splitViewMode === "image" ? (
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 14h6m0 0v6m0-6L3 21m17-7h-6m0 0v6m0-6l7 7M4 10h6m0 0V4m0 6L3 3m17 7h-6m0 0V4m0 6l7-7"
                      />
                    ) : (
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
                      />
                    )}
                  </svg>
                </button>

                {/* Open in New Tab Icon Button */}
                <a
                  href={documentsApi.pageImageUrl(
                    documentId,
                    currentPage,
                    zoom,
                  )}
                  target="_blank"
                  rel="noopener"
                  className={`p-1.5 rounded-lg border bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-sky-500 hover:border-sky-500 transition-all flex items-center justify-center cursor-pointer ${
                    imageState === "loaded"
                      ? "opacity-100"
                      : "opacity-30 pointer-events-none"
                  }`}
                  title="Buka dokumen di tab baru"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                    />
                  </svg>
                </a>
              </div>
            </div>

            {/* Image Viewport: Perfectly Centered with Mouse Drag & Wheel Zoom */}
            <div
              ref={imageContainerRef}
              onMouseDown={handleMouseDown}
              className={`flex-1 overflow-auto overscroll-contain bg-[var(--bg-main)] relative min-h-0 select-none ${
                isPanning ? "cursor-grabbing" : "cursor-grab"
              }`}
              style={{ overscrollBehavior: "contain" }}
              title="Klik dan geser (drag) untuk menggeser dokumen. Gunakan Ctrl + Scroll mouse untuk zoom."
            >
              {/* Loading Indicator */}
              {imageState === "loading" && (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2.5 bg-[var(--bg-main)] z-10">
                  <span className="spin w-6 h-6 border-2 border-[var(--border-color)] border-t-sky-500 rounded-full" />
                  <span className="text-xs text-[var(--text-muted)] font-medium">
                    Memuat citra halaman {currentPage}...
                  </span>
                </div>
              )}

              {/* Error / Missing Image Fallback State */}
              {imageState === "error" ? (
                <div className="min-w-full min-h-full flex items-center justify-center p-6 text-center space-y-3 max-w-sm m-auto">
                  <div className="w-12 h-12 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-color)] flex items-center justify-center text-amber-500 shrink-0 mx-auto">
                    <svg
                      className="w-6 h-6"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={1.5}
                        d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                      />
                    </svg>
                  </div>
                  <div className="space-y-1">
                    <h4 className="text-sm font-bold text-[var(--text-primary)]">
                      Citra Tidak Dapat Dirender
                    </h4>
                    <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                      Citra halaman {currentPage} belum diproses oleh server AI
                      atau format dokumen tidak dapat dibaca.
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setImageState("loading");
                      setImageRetryKey((prev) => prev + 1);
                    }}
                    className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all flex items-center gap-1.5 shadow-sm hover:scale-105 mx-auto cursor-pointer"
                  >
                    <svg
                      className="w-3.5 h-3.5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                      />
                    </svg>
                    <span>Coba Muat Ulang</span>
                  </button>
                </div>
              ) : (
                <div
                  className={`min-w-full min-h-full flex p-6 transition-all duration-75 ${
                    computedHeight > availH ? "items-start" : "items-center"
                  } ${
                    computedWidth > availW ? "justify-start" : "justify-center"
                  }`}
                >
                  <div className="m-auto shrink-0 flex items-center justify-center">
                    <img
                      ref={imgRef}
                      key={`${documentId}-${currentPage}-${zoom}-${timestamp || 0}-${imageRetryKey}`}
                      src={`${documentsApi.pageImageUrl(documentId, currentPage, zoom)}${timestamp ? `&t=${timestamp}` : ""}${imageRetryKey ? `&retry=${imageRetryKey}` : ""}`}
                      alt={`Halaman ${currentPage}`}
                      draggable={false}
                      onDoubleClick={handleDoubleClick}
                      onLoad={(e) => {
                        setImgNaturalDim({
                          width: e.currentTarget.naturalWidth || 0,
                          height: e.currentTarget.naturalHeight || 0,
                        });
                        setImageState("loaded");
                      }}
                      onError={() => setImageState("error")}
                      className={`shadow-md rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] transition-all duration-75 block select-none pointer-events-auto shrink-0 ${
                        isPanning ? "cursor-grabbing" : "cursor-grab"
                      } ${imageState === "loaded" ? "opacity-100" : "opacity-0"}`}
                      style={{
                        width: `${computedWidth}px`,
                        height: `${computedHeight}px`,
                        maxWidth: "none",
                        maxHeight: "none",
                      }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Floating Zoom & Fit Pill Controls (Bottom-Center Overlay) */}
            {imageState === "loaded" && (
              <div className="absolute bottom-3.5 left-1/2 -translate-x-1/2 z-20 flex items-center gap-1 p-1 rounded-xl bg-[var(--bg-card)]/90 backdrop-blur-md border border-[var(--border-color)] shadow-lg select-none">
                <button
                  onClick={handleZoomOut}
                  disabled={fitMode === "custom" && zoomScale <= 25}
                  title="Perkecil (-)"
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-input)] disabled:opacity-30 transition-all cursor-pointer"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      d="M20 12H4"
                    />
                  </svg>
                </button>

                <button
                  onClick={handleResetZoom}
                  title="Klik untuk kembali ke mode Auto"
                  className={`px-2 py-1 rounded-lg text-xs font-bold transition-all min-w-[50px] text-center cursor-pointer ${
                    fitMode === "auto"
                      ? "bg-sky-500 text-white shadow-xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-input)]"
                  }`}
                >
                  {fitMode === "auto" ? "Auto" : `${zoomScale}%`}
                </button>

                <button
                  onClick={handleZoomIn}
                  disabled={fitMode === "custom" && zoomScale >= 400}
                  title="Perbesar (+)"
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-input)] disabled:opacity-30 transition-all cursor-pointer"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      d="M12 4v16m8-8H4"
                    />
                  </svg>
                </button>

                <div className="w-px h-4 bg-[var(--border-color)] mx-0.5" />

                <button
                  onClick={() => {
                    if (fitMode === "width") {
                      handleResetZoom();
                    } else {
                      setFitMode("width");
                    }
                  }}
                  title="Pas Lebar (Lebar penuh 100%, nyaman digulir vertikal)"
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    fitMode === "width"
                      ? "bg-sky-500 text-white shadow-xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-input)]"
                  }`}
                >
                  Pas Lebar
                </button>
              </div>
            )}
          </div>
        )}

        {/* RIGHT: Textarea Editor */}
        {(splitViewMode === "split" || splitViewMode === "editor") && (
          <div className="flex flex-col bg-[var(--bg-card)] h-full overflow-hidden">
            <div className="px-4 py-2.5 bg-[var(--bg-input)] border-b border-[var(--border-color)] flex justify-between items-center text-xs shrink-0 min-h-[45px]">
              <div className="flex items-center gap-2.5">
                <span className="font-bold text-[var(--text-primary)] text-sm flex items-center">
                  <span>Hasil Ekstraksi</span>
                  <InfoTooltip content="Teks ekstraksi halaman ini yang akan dipecah menjadi chunk dan di-embedding ke database vektor." />
                </span>
                {splitViewMode === "editor" && (
                  <span className="px-2 py-0.5 text-xs font-medium bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                    Layar Penuh
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                {saveStatus === "saving" && (
                  <span
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-amber-600 dark:text-amber-400"
                    title="Sedang mengirim perubahan ke database..."
                  >
                    <svg
                      className="w-3.5 h-3.5 text-amber-500 animate-spin shrink-0"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8v8H4z"
                      ></path>
                    </svg>
                    <span>Menyimpan...</span>
                  </span>
                )}

                {saveStatus === "saved" && (
                  <span
                    className="inline-flex items-center text-xs font-medium text-emerald-600 dark:text-emerald-400"
                    title="Semua perubahan pada halaman ini telah tersimpan ke database"
                  >
                    Tersimpan {lastSavedTime ? `(${lastSavedTime})` : ""}
                  </span>
                )}

                {saveStatus === "error" && (
                  <div className="inline-flex items-center gap-1.5 text-xs">
                    <span className="text-rose-600 dark:text-rose-400 font-medium">
                      Gagal menyimpan
                    </span>
                    <button
                      onClick={() =>
                        savePageText(currentText, currentPage, false)
                      }
                      className="px-2 py-0.5 rounded-md text-xs font-semibold bg-[var(--bg-card)] text-red-500 border border-[var(--border-color)] hover:bg-[var(--bg-input)] transition-all cursor-pointer shadow-2xs"
                      title="Klik untuk mencoba simpan ulang ke database sekarang"
                    >
                      Coba Lagi
                    </button>
                  </div>
                )}

                {/* Focus / Split Toggle */}
                <button
                  onClick={() =>
                    setSplitViewMode(
                      splitViewMode === "editor" ? "split" : "editor",
                    )
                  }
                  title={
                    splitViewMode === "editor"
                      ? "Kembali ke Tampilan Berdampingan"
                      : "Perluas Editor ke Layar Penuh"
                  }
                  className={`p-1.5 rounded-lg border transition-all flex items-center justify-center cursor-pointer ${
                    splitViewMode === "editor"
                      ? "bg-sky-500 text-white border-sky-500 shadow-xs"
                      : "bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-sky-500"
                  }`}
                >
                  <svg
                    className="w-3.5 h-3.5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    {splitViewMode === "editor" ? (
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 14h6m0 0v6m0-6L3 21m17-7h-6m0 0v6m0-6l7 7M4 10h6m0 0V4m0 6L3 3m17 7h-6m0 0V4m0 6l7-7"
                      />
                    ) : (
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"
                      />
                    )}
                  </svg>
                </button>
              </div>
            </div>

            <div className="flex-1 flex flex-col min-h-0 bg-[var(--bg-card)]">
              {(() => {
                const extractedPageNumbers = new Set(
                  pages
                    .filter((p) => p.text && p.text.trim().length > 0)
                    .map((p) => p.page_number),
                );
                const activeProcessingPage =
                  Array.from({ length: maxPages }, (_, i) => i + 1).find(
                    (num) => !extractedPageNumbers.has(num),
                  ) || pages.length + 1;
                const isCurrentPageBeingExtracted =
                  currentPage === activeProcessingPage;

                if (!extractedPageNumbers.has(currentPage) && !currentText) {
                  return (
                    <div className="flex-1 flex flex-col items-center justify-center p-6 text-center space-y-3 bg-[var(--bg-main)]">
                      <span className="spin w-7 h-7 border-2 border-[var(--border-color)] border-t-sky-500 rounded-full" />
                      <div className="space-y-1">
                        <h4 className="text-xs font-bold text-[var(--text-primary)]">
                          {isCurrentPageBeingExtracted
                            ? `AI Sedang Mengekstrak Halaman ${currentPage}...`
                            : `Halaman ${currentPage} Menunggu Antrean`}
                        </h4>
                        <p className="text-xs text-[var(--text-muted)] max-w-xs leading-relaxed">
                          {isCurrentPageBeingExtracted
                            ? "Model Vision AI sedang membaca citra halaman ini. Teks Markdown akan otomatis muncul di sini begitu selesai."
                            : `Halaman ini akan diekstrak secara otomatis setelah Halaman ${activeProcessingPage} selesai.`}
                        </p>
                      </div>
                    </div>
                  );
                }

                return (
                  <textarea
                    value={currentText}
                    onChange={(e) => setCurrentText(e.target.value)}
                    placeholder="Teks hasil ekstraksi halaman ini..."
                    spellCheck={false}
                    autoCorrect="off"
                    autoCapitalize="off"
                    className="w-full flex-1 p-4 text-xs font-mono bg-[var(--bg-card)] !border-0 text-[var(--text-primary)] focus:!outline-none focus:!ring-0 focus:!shadow-none resize-none leading-relaxed overscroll-contain !rounded-none !shadow-none"
                    style={{ overscrollBehavior: "contain", borderRadius: 0, border: "none", outline: "none", boxShadow: "none" }}
                  />
                );
              })()}

              {/* Editor Footer Info */}
              <div className="flex justify-between items-center px-4 py-2 border-t border-[var(--border-color)] text-xs text-[var(--text-muted)] font-mono shrink-0">
                <span>
                  {currentText.length.toLocaleString("id-ID")} karakter
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 2. BOTTOM NAV BAR: Navigation Toolbar below both sub-cards */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2 bg-[var(--bg-input)] border-t border-[var(--border-color)] shrink-0">
        {/* Left Spacer for true center alignment on desktop */}
        <div className="hidden md:flex items-center gap-2 flex-1" />

        {/* Center: Page Nav */}
        <div className="flex items-center justify-center gap-2 flex-1 md:flex-initial">
          <button
            onClick={() => handlePageChange(currentPage - 1)}
            disabled={currentPage <= 1}
            title="Halaman Sebelumnya (Alt + ←)"
            className="px-3.5 py-1.5 rounded-lg text-sm font-semibold bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 disabled:opacity-40 transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
            <span>Prev</span>
          </button>

          <div className="flex items-center gap-2 text-sm font-semibold text-[var(--text-secondary)] px-1">
            <span>Halaman</span>
            <div className="relative inline-flex items-center group">
              {/* Visible Custom Styled Badge (Pure Flexbox, Zero Collisions) */}
              <div className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] group-hover:border-sky-500 group-hover:text-sky-500 text-[var(--text-primary)] text-sm font-semibold shadow-xs transition-colors pointer-events-none">
                <span>{currentPage}</span>
                {suspiciousPages.some((s) => s.page_number === currentPage) && (
                  <span className="text-xs text-amber-500 font-medium">
                    (Perlu Cek)
                  </span>
                )}
                <svg
                  className="w-4 h-4 text-inherit shrink-0 ml-1"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>

              {/* Invisible native select on top */}
              <select
                value={currentPage}
                onChange={(e) => handlePageChange(Number(e.target.value))}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer text-sm"
                title="Pilih Halaman"
              >
                {Array.from({ length: maxPages }, (_, i) => i + 1).map(
                  (num) => {
                    const isSaved = pages.some((p) => p.page_number === num);
                    const isSuspicious = suspiciousPages.some(
                      (s) => s.page_number === num,
                    );
                    const isNextActive = !isSaved && num === pages.length + 1;
                    let tag = "";
                    if (isSuspicious) tag = " (Perlu Cek)";
                    else if (isSaved) tag = " (Siap)";
                    else if (isNextActive) tag = " (Proses)";

                    return (
                      <option
                        key={num}
                        value={num}
                        className="bg-[var(--bg-card)] text-[var(--text-primary)] text-sm"
                      >
                        Halaman {num} {tag}
                      </option>
                    );
                  },
                )}
              </select>
            </div>
            <span className="text-[var(--text-muted)] font-normal text-sm">
              dari{" "}
              <strong className="text-[var(--text-primary)] font-semibold text-sm">
                {maxPages}
              </strong>
            </span>
          </div>

          <button
            onClick={() => handlePageChange(currentPage + 1)}
            disabled={currentPage >= maxPages}
            title="Halaman Berikutnya (Alt + →)"
            className="px-3.5 py-1.5 rounded-lg text-sm font-semibold bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 disabled:opacity-40 transition-colors flex items-center gap-1.5 shadow-xs cursor-pointer"
          >
            <span>Next</span>
            <svg
              className="w-4 h-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 5l7 7-7 7"
              />
            </svg>
          </button>
        </div>

        {/* Right: Suspicious Filter */}
        <div className="flex items-center justify-end gap-3 flex-1">
          {suspiciousPages.length > 0 && (
            <label className="flex items-center gap-1.5 text-xs font-semibold text-amber-500 cursor-pointer bg-[var(--bg-card)] px-2.5 py-1 rounded-lg border border-[var(--border-color)] shadow-xs">
              <input
                type="checkbox"
                checked={onlySuspicious}
                onChange={(e) => setOnlySuspicious(e.target.checked)}
                className="rounded text-amber-500 cursor-pointer"
              />
              <span>Perlu Cek ({suspiciousPages.length})</span>
            </label>
          )}
        </div>
      </div>
      <div className="flex flex-wrap justify-between items-center gap-2.5 px-4 py-2.5 bg-[var(--bg-input)] border-t border-[var(--border-color)] shrink-0">
        <div>
          <button
            onClick={handlePreviewChunks}
            className="px-3.5 py-1.5 rounded-xl text-xs font-bold bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all inline-flex items-center gap-1.5 shadow-sm"
          >
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 6h16M4 10h16M4 14h16M4 18h16"
              />
            </svg>
            Pratinjau Potongan
          </button>
          {corpusMsg && (
            <span className="ml-3 text-xs font-bold text-emerald-500">
              {corpusMsg}
            </span>
          )}
        </div>

        <button
          onClick={handleSaveToCorpus}
          disabled={!isReadyToSave || isSavingCorpus}
          title={
            !isReadyToSave
              ? `Tombol aktif setelah seluruh halaman selesai diekstrak (${pages.length}/${maxPages})`
              : "Simpan ke Korpus (ChromaDB)"
          }
          className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-all shadow-md hover:scale-[1.01] flex items-center gap-2"
        >
          {isSavingCorpus ? (
            <>
              <span className="spin w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" />
              <span>Menyimpan ke ChromaDB...</span>
            </>
          ) : (
            <>
              <svg
                className="w-4 h-4"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
              <span>Simpan ke Korpus (ChromaDB)</span>
            </>
          )}
        </button>
      </div>

      {/* Modal Pratinjau & Kustomisasi Potongan (Chunks) - Spacious Version */}
      {showChunksModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-2 sm:p-4 md:p-6">
          <div ref={chunksModalRef} className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl w-full max-w-[1520px] max-h-[94vh] h-[92vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="px-5 py-3 border-b border-[var(--border-color)] flex justify-between items-center bg-[var(--bg-input)] shrink-0">
              <div className="flex items-center gap-2.5">
                <span className="font-bold text-sm text-[var(--text-primary)]">
                  Kustomisasi Potongan (Chunks)
                </span>
                {chunksPreview && chunksPreview.siap && (
                  <span className="text-xs text-[var(--text-muted)] font-mono">
                    • {chunksPreview.jumlah_induk} Induk, {chunksPreview.jumlah_anak} Anak
                  </span>
                )}
              </div>

              <button
                onClick={() => setShowChunksModal(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 rounded-lg hover:bg-[var(--bg-card)] transition-colors cursor-pointer"
                title="Tutup"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Modal Body: 2-Sided Split (Side Kiri: Kustomisasi, Side Kanan: Preview ChromaDB) */}
            <div className="flex-1 flex flex-col lg:flex-row min-h-0 overflow-hidden bg-[var(--bg-card)]">
              {/* SIDE KIRI: Parameter & Strategi */}
              <div className="w-full lg:w-[380px] xl:w-[400px] shrink-0 border-b lg:border-b-0 lg:border-r border-[var(--border-color)] flex flex-col min-h-0 bg-[var(--bg-card)]">
                <div className="flex-1 overflow-y-auto p-4 pb-16 space-y-4">
                  {/* 1. Preset Selector (4-Button Grid) */}
                  <div className="space-y-2">
                    <div className="text-[11px] font-bold text-[var(--text-secondary)] uppercase tracking-wider">
                      Preset Strategi
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      {CHUNK_PRESETS.map((preset) => {
                        const isActive = selectedPreset === preset.id;
                        return (
                          <button
                            key={preset.id}
                            onClick={() => handleSelectPreset(preset.id)}
                            className={`p-2.5 rounded-xl border text-left transition-all cursor-pointer ${
                              isActive
                                ? "bg-sky-500 text-white border-sky-500 shadow-xs"
                                : "bg-[var(--bg-input)] border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500"
                            }`}
                          >
                            <div className="font-bold text-xs truncate">{preset.label}</div>
                            <div className={`text-[11px] font-mono ${isActive ? "text-sky-100" : "text-[var(--text-muted)]"}`}>
                              {preset.parentSize} / {preset.childSize} kar
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* 2. Sliders (Spacious & Stacked Layout) */}
                  <div className="p-3.5 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-2xl space-y-3.5">
                    <div className="flex justify-between items-center">
                      <span className="text-xs font-bold text-[var(--text-primary)]">
                        Ukuran Karakter
                      </span>
                      <button
                        onClick={() => fetchChunksPreviewWithParams()}
                        disabled={loadingChunks}
                        className="px-3 py-1.5 rounded-xl text-xs font-bold bg-sky-500 text-white shadow-xs hover:bg-sky-600 disabled:opacity-50 transition-all flex items-center gap-1.5 cursor-pointer"
                      >
                        <svg
                          className={`w-3.5 h-3.5 ${loadingChunks ? "spin" : ""}`}
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        <span>Hitung Ulang</span>
                      </button>
                    </div>

                    {/* Induk: Size & Overlap */}
                    <div className="space-y-2 bg-[var(--bg-card)] p-3 rounded-xl border border-[var(--border-color)]">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-bold text-[var(--text-primary)]">Induk (LLM)</span>
                        <span className="font-mono text-sky-500 font-bold">
                          {parentSize} kar <span className="text-[var(--text-muted)] font-normal text-[11px]">(overlap: {parentOverlap})</span>
                        </span>
                      </div>
                      <div className="space-y-2 pt-1">
                        <div>
                          <div className="flex justify-between text-[11px] text-[var(--text-muted)] pb-1">
                            <span>Ukuran Induk</span>
                            <span className="font-mono text-[var(--text-primary)] font-bold">{parentSize} kar</span>
                          </div>
                          <input
                            type="range"
                            min="500"
                            max="3500"
                            step="50"
                            value={parentSize}
                            title={`Ukuran Induk: ${parentSize}`}
                            onChange={(e) => {
                              setSelectedPreset("custom");
                              setParentSize(Number(e.target.value));
                            }}
                            className="w-full accent-sky-500 cursor-pointer h-2"
                          />
                        </div>
                        <div>
                          <div className="flex justify-between text-[11px] text-[var(--text-muted)] pb-1">
                            <span>Overlap Induk</span>
                            <span className="font-mono text-[var(--text-primary)] font-bold">{parentOverlap} kar</span>
                          </div>
                          <input
                            type="range"
                            min="50"
                            max="500"
                            step="10"
                            value={parentOverlap}
                            title={`Overlap Induk: ${parentOverlap}`}
                            onChange={(e) => {
                              setSelectedPreset("custom");
                              setParentOverlap(Number(e.target.value));
                            }}
                            className="w-full accent-sky-500 cursor-pointer h-2"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Anak: Size & Overlap */}
                    <div className="space-y-2 bg-[var(--bg-card)] p-3 rounded-xl border border-[var(--border-color)]">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-bold text-[var(--text-primary)]">Anak (Vektor)</span>
                        <span className="font-mono text-emerald-500 font-bold">
                          {childSize} kar <span className="text-[var(--text-muted)] font-normal text-[11px]">(overlap: {childOverlap})</span>
                        </span>
                      </div>
                      <div className="space-y-2 pt-1">
                        <div>
                          <div className="flex justify-between text-[11px] text-[var(--text-muted)] pb-1">
                            <span>Ukuran Anak</span>
                            <span className="font-mono text-[var(--text-primary)] font-bold">{childSize} kar</span>
                          </div>
                          <input
                            type="range"
                            min="150"
                            max="800"
                            step="25"
                            value={childSize}
                            title={`Ukuran Anak: ${childSize}`}
                            onChange={(e) => {
                              setSelectedPreset("custom");
                              setChildSize(Number(e.target.value));
                            }}
                            className="w-full accent-emerald-500 cursor-pointer h-2"
                          />
                        </div>
                        <div>
                          <div className="flex justify-between text-[11px] text-[var(--text-muted)] pb-1">
                            <span>Overlap Anak</span>
                            <span className="font-mono text-[var(--text-primary)] font-bold">{childOverlap} kar</span>
                          </div>
                          <input
                            type="range"
                            min="20"
                            max="250"
                            step="10"
                            value={childOverlap}
                            title={`Overlap Anak: ${childOverlap}`}
                            onChange={(e) => {
                              setSelectedPreset("custom");
                              setChildOverlap(Number(e.target.value));
                            }}
                            className="w-full accent-emerald-500 cursor-pointer h-2"
                          />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 3. Ringkasan Parameter */}
                  <div className="p-3.5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl space-y-2.5 text-xs">
                    <div className="font-bold text-[var(--text-secondary)] uppercase tracking-wider text-[11px]">
                      Ringkasan Potongan
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                      <div className="p-2.5 bg-[var(--bg-input)] rounded-xl border border-[var(--border-color)]">
                        <div className="text-[11px] text-[var(--text-muted)]">Potongan Induk</div>
                        <div className="text-base font-bold text-sky-500">{chunksPreview?.induk?.length || 0}</div>
                      </div>
                      <div className="p-2.5 bg-[var(--bg-input)] rounded-xl border border-[var(--border-color)]">
                        <div className="text-[11px] text-[var(--text-muted)]">Potongan Anak</div>
                        <div className="text-base font-bold text-emerald-500">{chunksPreview?.anak?.length || 0}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* SIDE KANAN: Preview Live (Identik dengan ChromaDB Chunks) */}
              {(() => {
                const parentChunks = chunksPreview?.induk || [];
                const childChunks = chunksPreview?.anak || [];
                const totalChunksCount = parentChunks.length + childChunks.length;

                let activeTabChunks = parentChunks.length > 0 ? parentChunks : childChunks;
                if (activeChunkTab === "child") {
                  activeTabChunks = selectedParentFilter !== null
                    ? childChunks.filter(
                        (c) => (c.parent_index ?? c.metadata?.parent_index) === selectedParentFilter
                      )
                    : childChunks;
                } else if (activeChunkTab === "parent") {
                  activeTabChunks = parentChunks;
                } else if (activeChunkTab === "all") {
                  activeTabChunks = parentChunks.length > 0 ? parentChunks : childChunks;
                }

                const filteredChunks = activeTabChunks.filter((c) => {
                  if (!chunkSearchQuery.trim()) return true;
                  const searchLower = chunkSearchQuery.toLowerCase();
                  const textStr = (c.teks || c.text || "").toLowerCase();
                  const pageStr = String(c.halaman || c.page_number || c.metadata?.page_number || "");
                  const matchesSelf = textStr.includes(searchLower) || pageStr.includes(searchLower);

                  if (matchesSelf) return true;

                  if (activeChunkTab === "all" && parentChunks.length > 0) {
                    const pIndex = c.chunk_index !== undefined ? c.chunk_index : parentChunks.indexOf(c);
                    const children = childChunks.filter(
                      (ch) => (ch.parent_index ?? ch.metadata?.parent_index) === pIndex
                    );
                    return children.some((ch) =>
                      (ch.teks || ch.text || "").toLowerCase().includes(searchLower)
                    );
                  }

                  return false;
                });

                return (
                  <div className="flex-1 flex flex-col min-h-0 bg-[var(--bg-card)] overflow-hidden">
                    {/* Toolbar Atas: Chroma-Style Tabs, Dropdown Filter, Search */}
                    <div className="px-3.5 py-2.5 border-b border-[var(--border-color)] bg-[var(--bg-input)] flex flex-wrap items-center justify-between gap-2.5 shrink-0">
                      {/* Tabs Bar */}
                      <div className="flex items-center gap-1 bg-[var(--bg-card)] p-1 rounded-xl border border-[var(--border-color)] text-xs font-bold">
                        <button
                          onClick={() => {
                            setActiveChunkTab("all");
                            setSelectedParentFilter(null);
                          }}
                          className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                            activeChunkTab === "all"
                              ? "bg-sky-500 text-white shadow-2xs"
                              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          Semua ({totalChunksCount})
                        </button>
                        <button
                          onClick={() => {
                            setActiveChunkTab("child");
                          }}
                          className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                            activeChunkTab === "child"
                              ? "bg-sky-500 text-white shadow-2xs"
                              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          Potongan Anak ({childChunks.length})
                        </button>
                        <button
                          onClick={() => {
                            setActiveChunkTab("parent");
                            setSelectedParentFilter(null);
                          }}
                          className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                            activeChunkTab === "parent"
                              ? "bg-sky-500 text-white shadow-2xs"
                              : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          Potongan Induk ({parentChunks.length})
                        </button>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {/* Parent Dropdown Filter (Tab Anak) */}
                        {activeChunkTab === "child" && parentChunks.length > 0 && (
                          <div className="relative inline-flex items-center">
                            <select
                              value={selectedParentFilter ?? "all"}
                              onChange={(e) => {
                                setSelectedParentFilter(
                                  e.target.value === "all" ? null : parseInt(e.target.value, 10)
                                );
                              }}
                              className="text-xs bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-sky-500 cursor-pointer font-medium"
                            >
                              <option value="all">
                                Semua Induk ({childChunks.length} Anak)
                              </option>
                              {parentChunks.map((p, pIdx) => {
                                const pIndex = p.chunk_index !== undefined ? p.chunk_index : pIdx;
                                const cCount = childChunks.filter(
                                  (ch) => (ch.parent_index ?? ch.metadata?.parent_index) === pIndex
                                ).length;
                                const pageN = p.halaman || p.page_number || p.metadata?.page_number || "-";
                                return (
                                  <option key={pIdx} value={pIndex}>
                                    Induk #{pIndex + 1} (Hal. {pageN} • {cCount} anak)
                                  </option>
                                );
                              })}
                            </select>
                          </div>
                        )}

                        {/* Search Input */}
                        <div className="relative">
                          <input
                            type="text"
                            value={chunkSearchQuery}
                            onChange={(e) => setChunkSearchQuery(e.target.value)}
                            placeholder="Cari chunk..."
                            className="px-3 pr-7 py-1.5 rounded-xl text-xs bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-sky-500 w-36 sm:w-44"
                          />
                          {chunkSearchQuery && (
                            <button
                              onClick={() => setChunkSearchQuery("")}
                              className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                            >
                              ✕
                            </button>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Content Area */}
                    <div ref={chunksListRef} className="flex-1 overflow-y-auto p-3.5 pb-16 space-y-3.5">
                      {/* Active Filter Banner (Tab Anak) */}
                      {activeChunkTab === "child" && selectedParentFilter !== null && (
                        <div className="flex items-center justify-between px-3.5 py-2.5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] font-semibold shadow-xs animate-in fade-in duration-150">
                          <div className="flex items-center gap-2.5">
                            <div className="w-6 h-6 rounded-lg bg-sky-500 text-white flex items-center justify-center shrink-0 shadow-2xs font-bold">
                              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                              </svg>
                            </div>
                            <span className="text-[var(--text-primary)]">
                              Memfilter potongan anak dari:{" "}
                              <strong className="text-white font-bold px-2 py-0.5 rounded-lg bg-sky-500 shadow-2xs">
                                Induk #{selectedParentFilter + 1}
                              </strong>{" "}
                              ({activeTabChunks.length} potongan anak)
                            </span>
                          </div>
                          <button
                            onClick={() => setSelectedParentFilter(null)}
                            className="px-3 py-1.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 text-xs font-bold transition-colors cursor-pointer flex items-center gap-1.5 shadow-2xs"
                          >
                            <span>✕ Tampilkan Semua Anak</span>
                          </button>
                        </div>
                      )}

                      {loadingChunks ? (
                        <div className="py-12 text-center text-xs text-[var(--text-muted)] italic flex flex-col items-center justify-center gap-2.5">
                          <span className="spin w-5 h-5 border-2 border-[var(--border-color)] border-t-sky-500 rounded-full" />
                          <span>Menghitung ulang potongan...</span>
                        </div>
                      ) : !chunksPreview || !chunksPreview.siap ? (
                        <div className="py-12 text-center text-xs text-[var(--text-muted)] italic">
                          Belum ada teks halaman yang diekstrak.
                        </div>
                      ) : filteredChunks.length === 0 ? (
                        <div className="py-10 text-center text-xs text-[var(--text-muted)] italic">
                          Tidak ada chunk yang cocok dengan kriteria filter.
                        </div>
                      ) : activeChunkTab === "all" && parentChunks.length > 0 ? (
                        /* TAB SEMUA: HIERARCHICAL ACCORDION VIEW */
                        <div className="space-y-3.5">
                          {filteredChunks.map((c, idx) => {
                            const parentIdx = c.chunk_index !== undefined ? c.chunk_index : idx;
                            const isExpanded = expandedParents.has(parentIdx);
                            const relatedChildren = childChunks.filter(
                              (ch) => (ch.parent_index ?? ch.metadata?.parent_index) === parentIdx
                            );
                            const rawText = c.teks || c.text || "";
                            const pageNum = c.halaman || c.page_number || c.metadata?.page_number || "-";

                            return (
                              <div
                                key={parentIdx}
                                className="chunk-card-anim rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] transition-all shadow-xs overflow-hidden"
                              >
                                {/* Accordion Header */}
                                <div
                                  onClick={() => {
                                    setExpandedParents((prev) => {
                                      const next = new Set(prev);
                                      if (next.has(parentIdx)) next.delete(parentIdx);
                                      else next.add(parentIdx);
                                      return next;
                                    });
                                  }}
                                  className="p-3 sm:p-3.5 flex items-center justify-between gap-2.5 cursor-pointer select-none bg-[var(--bg-card)] hover:bg-[var(--bg-input)] transition-colors"
                                >
                                  <div className="flex items-center gap-2.5 min-w-0">
                                    <div className="w-6 h-6 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] flex items-center justify-center text-[var(--text-secondary)] shrink-0">
                                      <svg
                                        className={`w-3.5 h-3.5 transition-transform duration-200 ${
                                          isExpanded ? "rotate-180 text-sky-500" : ""
                                        }`}
                                        fill="none"
                                        stroke="currentColor"
                                        viewBox="0 0 24 24"
                                      >
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                      </svg>
                                    </div>

                                    <span className="font-bold text-[var(--text-primary)] text-xs truncate">
                                      Hal. {pageNum}
                                    </span>

                                    <span className="text-xs font-mono text-[var(--text-muted)] hidden sm:inline">
                                      ({rawText.length} karakter)
                                    </span>
                                  </div>

                                  <div className="flex items-center gap-2 shrink-0">
                                    <span className="px-2.5 py-0.5 rounded-full bg-sky-500 text-white font-bold text-xs shadow-2xs">
                                      Induk #{parentIdx + 1}
                                    </span>
                                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500 text-white font-bold text-xs shadow-2xs">
                                      {relatedChildren.length} Potongan Anak
                                    </span>
                                  </div>
                                </div>

                                {/* Accordion Body */}
                                {isExpanded && (
                                  <div className="p-3.5 sm:p-4 border-t border-[var(--border-color)] bg-[var(--bg-card)] animate-in fade-in duration-150">
                                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 items-start">
                                      {/* Kolom 1: Konteks Induk */}
                                      <div className="space-y-1.5 flex flex-col">
                                        <div className="h-7 flex items-center justify-between gap-2">
                                          <div className="flex items-center gap-1.5">
                                            <span className="w-4 h-4 rounded-md bg-sky-500 text-white flex items-center justify-center font-bold text-[10px] shrink-0 shadow-2xs">
                                              1
                                            </span>
                                            <span className="text-xs font-bold text-sky-500">
                                              Konteks Induk
                                            </span>
                                          </div>
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation();
                                              handleCopyText(rawText, parentIdx);
                                            }}
                                            className="px-2.5 py-0.5 rounded-md bg-[var(--bg-input)] border border-[var(--border-color)] hover:border-sky-500 hover:text-sky-500 text-[11px] font-bold transition-colors cursor-pointer"
                                          >
                                            {copiedContext === parentIdx ? "✓ Tersalin" : "Salin Teks"}
                                          </button>
                                        </div>

                                        <div className="p-3 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-xl text-xs space-y-2 shadow-2xs transition-all max-h-[380px] flex flex-col">
                                          <div className="h-6 flex justify-between items-center text-xs font-mono text-[var(--text-muted)] shrink-0">
                                            <div className="flex items-center gap-2">
                                              <span className="px-2 py-0.5 rounded-md bg-sky-500 text-white font-bold text-xs shadow-2xs">
                                                Induk #{parentIdx + 1}
                                              </span>
                                              <span className="font-bold text-[var(--text-primary)]">
                                                Hal. {pageNum}
                                              </span>
                                            </div>
                                            <span className="text-xs text-[var(--text-muted)]">
                                              {rawText.length} kar.
                                            </span>
                                          </div>
                                          <p className="whitespace-pre-wrap text-[var(--text-primary)] font-mono leading-relaxed bg-[var(--bg-card)] p-3 rounded-lg border border-[var(--border-color)] select-text text-xs overflow-y-auto pr-1.5 flex-1">
                                            {rawText}
                                          </p>
                                        </div>
                                      </div>

                                      {/* Kolom 2: Potongan Anak */}
                                      <div className="space-y-1.5 flex flex-col">
                                        <div className="h-7 flex items-center justify-between gap-2">
                                          <div className="flex items-center gap-1.5">
                                            <span className="w-4 h-4 rounded-md bg-emerald-500 text-white flex items-center justify-center font-bold text-[10px] shrink-0 shadow-2xs">
                                              2
                                            </span>
                                            <span className="text-xs font-bold text-emerald-500">
                                              Potongan Anak
                                            </span>
                                          </div>
                                          <span className="text-[11px] font-mono text-[var(--text-muted)] shrink-0">
                                            {relatedChildren.length} bagian
                                          </span>
                                        </div>

                                        <div className="space-y-2 max-h-[380px] overflow-y-auto pr-1.5">
                                          {relatedChildren.length === 0 ? (
                                            <div className="py-6 text-center text-xs text-[var(--text-muted)] italic bg-[var(--bg-input)] rounded-xl border border-[var(--border-color)]">
                                              Tidak ada potongan anak untuk induk ini.
                                            </div>
                                          ) : (
                                            relatedChildren.map((ch, chIdx) => {
                                              const chText = ch.teks || ch.text || "";
                                              const chPage = ch.halaman || ch.page_number || ch.metadata?.page_number || "-";
                                              return (
                                                <div
                                                  key={chIdx}
                                                  className="p-3 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-xl text-xs space-y-2 shadow-2xs transition-all"
                                                >
                                                  <div className="h-6 flex justify-between items-center text-xs font-mono text-[var(--text-muted)]">
                                                    <div className="flex items-center gap-2">
                                                      <span className="px-2 py-0.5 rounded-md bg-emerald-500 text-white font-bold text-xs shadow-2xs">
                                                        Bagian {chIdx + 1} dari {relatedChildren.length}
                                                      </span>
                                                      <span className="font-bold text-[var(--text-primary)]">
                                                        Hal. {chPage}
                                                      </span>
                                                    </div>
                                                    <span className="text-xs text-[var(--text-muted)]">
                                                      {chText.length} kar.
                                                    </span>
                                                  </div>
                                                  <p className="whitespace-pre-wrap text-[var(--text-primary)] font-mono leading-relaxed bg-[var(--bg-card)] p-3 rounded-lg border border-[var(--border-color)] select-text text-xs">
                                                    {chText}
                                                  </p>
                                                </div>
                                              );
                                            })
                                          )}
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        /* TAB ANAK & INDUK: GRID CARDS VIEW */
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
                          {filteredChunks.map((c, idx) => {
                            const isParent = activeChunkTab === "parent";
                            const rawText = c.teks || c.text || "";
                            const pageNum = c.halaman || c.page_number || c.metadata?.page_number || "-";
                            const parentIdx = isParent
                              ? (c.chunk_index !== undefined ? c.chunk_index : idx)
                              : (c.parent_index !== undefined ? c.parent_index : c.metadata?.parent_index);
                            const relatedChildren = isParent
                              ? childChunks.filter(
                                  (ch) => (ch.parent_index ?? ch.metadata?.parent_index) === parentIdx
                                )
                              : [];
                            const isHighlighted = isParent && highlightedParentIndex === parentIdx;

                            return (
                              <div
                                key={idx}
                                className={`chunk-card-anim p-3.5 rounded-xl transition-all flex flex-col justify-between space-y-2.5 shadow-xs ${
                                  isHighlighted
                                    ? "bg-[var(--bg-card)] border-2 border-sky-500 shadow-sm"
                                    : "bg-[var(--bg-input)] border border-[var(--border-color)] hover:border-[var(--border-hover)]"
                                }`}
                              >
                                <div className="flex justify-between items-center text-xs font-mono text-[var(--text-muted)] pb-2 border-b border-[var(--border-color)]">
                                  <div className="flex items-center gap-2">
                                    <span className="font-bold text-[var(--text-primary)]">
                                      Hal. {pageNum}
                                    </span>
                                    <span className="text-xs text-[var(--text-muted)]">
                                      ({rawText.length} kar.)
                                    </span>
                                  </div>

                                  <div className="flex items-center gap-1.5">
                                    {isHighlighted && (
                                      <span className="text-xs px-2.5 py-0.5 rounded-full bg-sky-500 text-white font-bold animate-pulse">
                                        Induk Terpilih
                                      </span>
                                    )}

                                    {isParent ? (
                                      <span className="px-2.5 py-0.5 rounded-full bg-sky-500 text-white font-bold text-xs shadow-2xs">
                                        Induk #{parentIdx + 1}
                                      </span>
                                    ) : parentIdx !== undefined ? (
                                      <button
                                        onClick={() => {
                                          setSelectedParentFilter(null);
                                          setActiveChunkTab("parent");
                                          setHighlightedParentIndex(parentIdx);
                                        }}
                                        className="px-2.5 py-1 rounded-lg bg-sky-500 text-white hover:bg-sky-600 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer group shadow-2xs"
                                        title={`Klik untuk melihat Potongan Induk #${parentIdx + 1}`}
                                      >
                                        <span>Induk #{parentIdx + 1}</span>
                                        <svg
                                          className="w-3 h-3 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform"
                                          fill="none"
                                          stroke="currentColor"
                                          viewBox="0 0 24 24"
                                        >
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                                        </svg>
                                      </button>
                                    ) : (
                                      <span className="px-2 py-0.5 rounded-md bg-[var(--bg-card)] text-[var(--text-secondary)] font-mono font-medium border border-[var(--border-color)] text-xs">
                                        Chunk #{idx + 1}
                                      </span>
                                    )}
                                  </div>
                                </div>

                                <p className="whitespace-pre-wrap break-words text-xs text-[var(--text-primary)] leading-relaxed font-sans flex-1 max-h-56 overflow-y-auto pr-1 select-text">
                                  {rawText}
                                </p>

                                {isParent ? (
                                  <div className="pt-2 border-t border-[var(--border-color)] flex justify-between items-center text-xs">
                                    <span className="font-mono text-[var(--text-muted)]">
                                      {relatedChildren.length} potongan anak
                                    </span>
                                    <button
                                      onClick={() => {
                                        setSelectedParentFilter(parentIdx);
                                        setActiveChunkTab("child");
                                        setHighlightedParentIndex(null);
                                      }}
                                      disabled={relatedChildren.length === 0}
                                      className="px-3 py-1.5 rounded-lg text-xs font-bold bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-40 disabled:pointer-events-none transition-all flex items-center gap-1.5 cursor-pointer shadow-xs"
                                      title={`Lihat potongan anak dari Induk #${parentIdx + 1}`}
                                    >
                                      <span>Lihat {relatedChildren.length} Potongan Anak</span>
                                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                                      </svg>
                                    </button>
                                  </div>
                                ) : (
                                  <div className="pt-2 border-t border-[var(--border-color)] flex justify-between items-center text-xs font-mono text-[var(--text-muted)]">
                                    <span>Potongan Anak #{idx + 1}</span>
                                    <span>{rawText.length} kar.</span>
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>

            {/* Modal Bottom Footer */}
            <div className="px-4 py-2.5 border-t border-[var(--border-color)] bg-[var(--bg-input)] flex justify-between items-center gap-2 shrink-0">
              <span className="text-[11px] text-[var(--text-muted)]">
                Parameter tersimpan digunakan saat Simpan ke ChromaDB.
              </span>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowChunksModal(false)}
                  className="px-3 py-1 rounded-lg text-xs font-bold bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors cursor-pointer"
                >
                  Tutup
                </button>

                <button
                  onClick={handleSaveToCorpus}
                  disabled={!isReadyToSave || isSavingCorpus}
                  title={
                    !isReadyToSave
                      ? `Tombol aktif setelah seluruh halaman selesai diekstrak (${pages.length}/${maxPages})`
                      : "Simpan ke ChromaDB"
                  }
                  className="px-3.5 py-1 rounded-lg text-xs font-bold bg-sky-500 text-white hover:bg-sky-600 shadow-xs transition-all disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 cursor-pointer"
                >
                  {isSavingCorpus ? (
                    <>
                      <span className="spin w-3 h-3 border-2 border-white/30 border-t-white rounded-full" />
                      <span>Menyimpan...</span>
                    </>
                  ) : (
                    <>
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                      <span>Simpan ke ChromaDB</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Floating Save Bar for Unsaved Page Corrections */}
      <FloatingSaveBar
        show={hasUnsavedChanges}
        onSave={() => savePageText(currentText, currentPage, false)}
        onDiscard={() => setCurrentText(originalSavedText)}
        saving={isSavingText}
        message={`Perubahan teks halaman ${currentPage} belum disimpan`}
        saveText="Simpan Teks Halaman"
        discardText="Batalkan"
      />

      {/* Confirmation Modal for Saving to ChromaDB */}
      <ConfirmModal
        isOpen={showSaveCorpusConfirm}
        title="Simpan ke Korpus Vektor ChromaDB"
        message="Dokumen ini akan diindeks agar dapat digunakan chatbot untuk menjawab pertanyaan. Lanjutkan?"
        confirmText="Ya, Simpan"
        cancelText="Batal"
        isDanger={false}
        onConfirm={executeSaveToCorpus}
        onCancel={() => setShowSaveCorpusConfirm(false)}
      />

      {/* Live 1-100% Progress Modal for Saving to ChromaDB */}
      <EmbedProgressModal
        isOpen={showEmbedProgressModal}
        documentId={documentId}
        onComplete={() => {
          clearActiveEmbedding(documentId);
          setShowEmbedProgressModal(false);
          setCorpusMsg("Berhasil disimpan ke ChromaDB!");
          if (onSaveToCorpusSuccess) onSaveToCorpusSuccess();
        }}
        onClose={() => setShowEmbedProgressModal(false)}
      />
    </div>
  );
}
