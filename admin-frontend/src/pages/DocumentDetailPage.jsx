import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import gsap from "gsap";
import { documentsApi } from "../api/documents";
import { useDocumentDetail } from "../hooks/documents/useDocumentDetail";
import ConfirmModal from "../components/ConfirmModal";
import ManualCorrectionEditor from "../components/ManualCorrectionEditor";
import { InfoTooltip } from "../components/UI/InfoTooltip";

export default function DocumentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();

  const [replaceFile, setReplaceFile] = useState(null);
  const [replacing, setReplacing] = useState(false);
  const [pdfTimestamp, setPdfTimestamp] = useState(Date.now());

  const [showChunks, setShowChunks] = useState(false);
  const [chunkSearch, setChunkSearch] = useState("");
  const [chromaActiveTab, setChromaActiveTab] = useState("all"); // 'all' | 'child' | 'parent'
  const [selectedChromaParentId, setSelectedChromaParentId] = useState(null);
  const [highlightedChromaChunkId, setHighlightedChromaChunkId] = useState(null);
  const [expandedChromaParents, setExpandedChromaParents] = useState(new Set());

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showReplaceModal, setShowReplaceModal] = useState(false);
  const [showAllLogs, setShowAllLogs] = useState(false);

  // Collapsible Sidebar Sections
  const [isInfoOpen, setIsInfoOpen] = useState(true);
  const [isLogsOpen, setIsLogsOpen] = useState(false);
  const [isManagementOpen, setIsManagementOpen] = useState(false);

  // Floating Toast State (Solid Opaque Card)
  const [toast, setToast] = useState(null);
  const toastTimeoutRef = useRef(null);
  const [copiedContext, setCopiedContext] = useState(null);

  const handleCopyText = (text, key) => {
    if (!text) return;
    try {
      navigator.clipboard.writeText(text);
      setCopiedContext(key);
      setTimeout(() => setCopiedContext(null), 2000);
    } catch (e) {
      console.warn("Gagal menyalin teks:", e);
    }
  };

  const showToast = (type, title, message) => {
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    setToast({ type, title, message });
    toastTimeoutRef.current = setTimeout(() => setToast(null), 4500);
  };

  const [leftColWidth, setLeftColWidth] = useState(65);
  const [isResizing, setIsResizing] = useState(false);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(true);
  const isDragging = useRef(false);
  const containerRef = useRef(null);
  const timelineRef = useRef(null);
  const infoContentRef = useRef(null);
  const logsContentRef = useRef(null);
  const managementContentRef = useRef(null);
  const isInitialMount = useRef(true);

  const {
    document,
    loading,
    error,
    chunks,
    loadingChunks,
    fetchDocument,
    fetchChunks,
  } = useDocumentDetail(id);

  // Pertahankan pembersihan toast saat ID berganti dan halaman ditutup.
  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, [id]);

  useEffect(() => {
    if (document?.logs?.length && timelineRef.current) {
      const items = timelineRef.current.querySelectorAll(".gsap-timeline-item");
      const lines = timelineRef.current.querySelectorAll(".gsap-timeline-line");
      const icons = timelineRef.current.querySelectorAll(".gsap-timeline-icon");

      gsap.fromTo(
        items,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.4, stagger: 0.1, ease: "power2.out" },
      );
      if (lines.length) {
        gsap.fromTo(
          lines,
          { height: "0%" },
          {
            height: "100%",
            duration: 0.5,
            stagger: 0.1,
            delay: 0.2,
            ease: "power1.inOut",
          },
        );
      }
      if (icons.length) {
        gsap.fromTo(
          icons,
          { scale: 0 },
          { scale: 1, duration: 0.3, stagger: 0.1, ease: "back.out(1.5)" },
        );
      }
    }
  }, [document?.logs, isLogsOpen]);

  // GSAP Smooth Accordion Animations for Sidebar Sections (Cepat di awal, pelan di akhir / power3.out)
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    const el = infoContentRef.current;
    if (el) {
      gsap.killTweensOf(el);
      if (isInfoOpen) {
        const targetHeight = el.scrollHeight;
        gsap.fromTo(
          el,
          { height: 0, opacity: 0, overflow: "hidden" },
          {
            height: targetHeight,
            opacity: 1,
            duration: 0.38,
            ease: "power3.out",
            onComplete: () => {
              gsap.set(el, { clearProps: "height,overflow" });
            },
          },
        );
      } else {
        const currentHeight = el.scrollHeight;
        gsap.fromTo(
          el,
          { height: currentHeight, opacity: 1, overflow: "hidden" },
          {
            height: 0,
            opacity: 0,
            duration: 0.36,
            ease: "power3.out",
            overflow: "hidden",
          },
        );
      }
    }
  }, [isInfoOpen]);

  useEffect(() => {
    if (isInitialMount.current) return;

    const el = logsContentRef.current;
    if (el) {
      gsap.killTweensOf(el);
      if (isLogsOpen) {
        const targetHeight = el.scrollHeight;
        gsap.fromTo(
          el,
          { height: 0, opacity: 0, overflow: "hidden" },
          {
            height: targetHeight,
            opacity: 1,
            duration: 0.38,
            ease: "power3.out",
            onComplete: () => {
              gsap.set(el, { clearProps: "height,overflow" });
            },
          },
        );
      } else {
        const currentHeight = el.scrollHeight;
        gsap.fromTo(
          el,
          { height: currentHeight, opacity: 1, overflow: "hidden" },
          {
            height: 0,
            opacity: 0,
            duration: 0.36,
            ease: "power3.out",
            overflow: "hidden",
          },
        );
      }
    }
  }, [isLogsOpen]);

  useEffect(() => {
    if (isInitialMount.current) return;

    const el = managementContentRef.current;
    if (el) {
      gsap.killTweensOf(el);
      if (isManagementOpen) {
        const targetHeight = el.scrollHeight;
        gsap.fromTo(
          el,
          { height: 0, opacity: 0, overflow: "hidden" },
          {
            height: targetHeight,
            opacity: 1,
            duration: 0.38,
            ease: "power3.out",
            onComplete: () => {
              gsap.set(el, { clearProps: "height,overflow" });
            },
          },
        );
      } else {
        const currentHeight = el.scrollHeight;
        gsap.fromTo(
          el,
          { height: currentHeight, opacity: 1, overflow: "hidden" },
          {
            height: 0,
            opacity: 0,
            duration: 0.36,
            ease: "power3.out",
            overflow: "hidden",
          },
        );
      }
    }
  }, [isManagementOpen]);

  const chromaChunksListRef = useRef(null);

  // GSAP: Stagger Animate ChromaDB Chunks Cards on Show/Tab/Filter/Search Change
  useEffect(() => {
    if (showChunks && chromaChunksListRef.current) {
      const items = chromaChunksListRef.current.querySelectorAll(".chroma-chunk-anim");
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
  }, [showChunks, chromaActiveTab, selectedChromaParentId, chunkSearch, chunks]);

  const startDrag = (e) => {
    e.preventDefault();
    isDragging.current = true;
    setIsResizing(true);
    window.document.body.style.cursor = "col-resize";
    window.document.body.style.userSelect = "none";
    if (containerRef.current) containerRef.current.style.pointerEvents = "none";
  };

  const onDrag = (e) => {
    if (!isDragging.current || !containerRef.current) return;
    const containerRect = containerRef.current.getBoundingClientRect();
    const newWidth =
      ((e.clientX - containerRect.left) / containerRect.width) * 100;
    if (newWidth >= 25 && newWidth <= 75) setLeftColWidth(newWidth);
  };

  const stopDrag = () => {
    if (isDragging.current) {
      isDragging.current = false;
      setIsResizing(false);
      window.document.body.style.cursor = "default";
      window.document.body.style.userSelect = "auto";
      if (containerRef.current)
        containerRef.current.style.pointerEvents = "auto";
    }
  };

  const handleResetSplit = () => {
    setLeftColWidth(65);
  };

  useEffect(() => {
    window.addEventListener("mousemove", onDrag);
    window.addEventListener("mouseup", stopDrag);
    return () => {
      window.removeEventListener("mousemove", onDrag);
      window.removeEventListener("mouseup", stopDrag);
    };
  }, []);

  const confirmReplace = async (e) => {
    if (e) e.preventDefault();
    if (!replaceFile) {
      showToast("error", "Pilih File", "Pilih file PDF terlebih dahulu.");
      return;
    }

    setReplacing(true);
    try {
      await documentsApi.replace(id, replaceFile);
      setReplaceFile(null);
      setShowReplaceModal(false);
      try {
        localStorage.removeItem(`doc_${id}_last_page`);
      } catch (e) {}
      setPdfTimestamp(Date.now());
      showToast(
        "success",
        "File Diganti",
        "File berhasil diunggah dan proses ekstraksi diulang dari awal.",
      );
      fetchDocument();
    } catch (err) {
      showToast(
        "error",
        "Gagal Mengganti File",
        err.response?.data?.message ||
          "Terjadi kesalahan saat mengunggah file.",
      );
    } finally {
      setReplacing(false);
    }
  };

  const handleDelete = () => setShowDeleteModal(true);

  const confirmDelete = async () => {
    try {
      await documentsApi.destroy(id);
      navigate("/dashboard");
    } catch (err) {
      showToast(
        "error",
        "Gagal Menghapus",
        err.response?.data?.message || "Gagal menghapus dokumen.",
      );
    }
  };

  const handlePause = async () => {
    try {
      const res = await documentsApi.pause(id);
      showToast(
        "info",
        "Permintaan Jeda",
        res.message ||
          "Proses ekstraksi akan dijeda setelah halaman aktif selesai.",
      );
      fetchDocument();
    } catch (err) {
      showToast(
        "error",
        "Gagal Meminta Jeda",
        err.response?.data?.message || "Server AI tidak merespons.",
      );
    }
  };

  const handleResume = async () => {
    try {
      await documentsApi.resume(id);
      showToast(
        "success",
        "Ekstraksi Dimulai",
        "Pemrosesan halaman AI sedang berjalan.",
      );
      fetchDocument();
    } catch (err) {
      const msg =
        err.response?.data?.message ||
        err.message ||
        "Server AI (Python Uvicorn / Celery) sedang tidak berjalan. Silakan aktifkan service AI terlebih dahulu.";
      showToast("error", "Server AI Offline", msg);
      fetchDocument();
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return "-";
      return d.toLocaleDateString("id-ID", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return "-";
    }
  };

  const formatTime = (isoString) => {
    if (!isoString) return "-";
    try {
      const d = new Date(isoString);
      if (isNaN(d.getTime())) return "-";
      return d.toLocaleTimeString("id-ID", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return "-";
    }
  };

  const resolveLogAction = (log) => {
    if (!log) return "unknown";
    const action = (typeof log === "string" ? log : log.action || "")
      .toLowerCase()
      .trim();
    const details = (
      typeof log === "object" && log.details ? log.details : ""
    ).toLowerCase();

    // 1. Exact action code matching (Highest Priority)
    if (["uploaded"].includes(action)) return "uploaded";
    if (["processing", "started"].includes(action)) return "processing";
    if (["paused", "jeda"].includes(action)) return "paused";
    if (["resumed", "dilanjutkan"].includes(action)) return "resumed";
    if (["ocr_completed"].includes(action)) return "ocr_completed";
    if (["correction_saved", "koreksi_disimpan", "corrected"].includes(action))
      return "correction_saved";
    if (["chunked", "chunking_completed"].includes(action)) return "chunked";
    if (["embedding_completed", "indexed"].includes(action))
      return "embedding_completed";
    if (["completed", "selesai"].includes(action)) return "completed";
    if (["cancelled", "dibatalkan"].includes(action)) return "cancelled";
    if (["failed", "gagal"].includes(action)) return "failed";
    if (["replaced", "diganti"].includes(action)) return "replaced";

    // 2. Heuristic fallback only if action is generic or missing
    if (details.includes("ocr selesai") || details.includes("siap ditinjau"))
      return "ocr_completed";
    if (details.includes("chunking") || details.includes("pemotongan teks"))
      return "chunked";
    if (details.includes("chromadb") || details.includes("vektor embedding"))
      return "embedding_completed";
    if (
      details.includes("koreksi manual") ||
      details.includes("halaman dikoreksi")
    )
      return "correction_saved";
    if (details.includes("jeda") || details.includes("pause")) return "paused";
    if (details.includes("dilanjutkan") || details.includes("resume"))
      return "resumed";
    if (details.includes("dibatalkan") || details.includes("batal"))
      return "cancelled";
    if (details.includes("difinalisasi")) return "completed";
    if (details.includes("diganti")) return "replaced";
    if (details.includes("diunggah")) return "uploaded";
    if (details.includes("gagal") || details.includes("error")) return "failed";

    return action || "processing";
  };

  const getLogColor = (log) => {
    const act = resolveLogAction(log);
    switch (act) {
      case "uploaded":
        return "#0284c7"; // sky-600
      case "processing":
      case "started":
        return "#f59e0b"; // amber-500
      case "paused":
      case "jeda":
        return "#f97316"; // orange-500
      case "resumed":
      case "dilanjutkan":
        return "#06b6d4"; // cyan-500
      case "correction_saved":
      case "koreksi_disimpan":
      case "corrected":
        return "#8b5cf6"; // violet-500
      case "ocr_completed":
        return "#0d9488"; // teal-600
      case "chunked":
        return "#6366f1"; // indigo-500
      case "embedding_completed":
        return "#3b82f6"; // blue-500
      case "completed":
      case "selesai":
        return "#10b981"; // emerald-500
      case "replaced":
        return "#d97706"; // amber-600
      case "cancelled":
      case "dibatalkan":
        return "#e11d48"; // rose-600
      case "failed":
      case "gagal":
        return "#ef4444"; // red-500
      default:
        return "var(--text-muted)";
    }
  };

  const getLogIcon = (log) => {
    const act = resolveLogAction(log);
    switch (act) {
      case "uploaded":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        );
      case "processing":
      case "started":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"
          />
        );
      case "paused":
      case "jeda":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M15.75 5.25v13.5m-7.5-13.5v13.5"
          />
        );
      case "resumed":
      case "dilanjutkan":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z"
          />
        );
      case "correction_saved":
      case "koreksi_disimpan":
      case "corrected":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"
          />
        );
      case "ocr_completed":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
          />
        );
      case "chunked":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
          />
        );
      case "embedding_completed":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 5.625c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125"
          />
        );
      case "completed":
      case "selesai":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        );
      case "replaced":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7c-.017.22-.032.441-.046.662M19.5 12l3-3m-3 3l-3-3m-12 3c0 1.232.046 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.017-.22.032-.441.046-.662M4.5 12l3 3m-3-3l-3 3"
          />
        );
      case "cancelled":
      case "dibatalkan":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
          />
        );
      case "failed":
      case "gagal":
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
          />
        );
      default:
        return (
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.75}
            d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
          />
        );
    }
  };

  const getLogLabel = (log) => {
    const act = resolveLogAction(log);
    switch (act) {
      case "uploaded":
        return "Dokumen Diunggah";
      case "processing":
        return "Ekstraksi Dimulai";
      case "paused":
        return "Ekstraksi Dijeda";
      case "resumed":
        return "Ekstraksi Dilanjutkan";
      case "correction_saved":
        return "Koreksi Manual Disimpan";
      case "ocr_completed":
        return "Ekstraksi OCR Selesai";
      case "chunked":
        return "Pemotongan Teks (Chunking)";
      case "embedding_completed":
        return "Embedding Vektor Disimpan";
      case "completed":
        return "Dokumen Berhasil Diindeks";
      case "replaced":
        return "File Dokumen Diganti";
      case "cancelled":
        return "Ekstraksi Dibatalkan";
      case "failed":
        return "Ekstraksi Gagal";
      default:
        return log.action_label || log.action || "Aktivitas";
    }
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case "completed":
      case "selesai":
        return { dot: "bg-emerald-500", label: "Selesai" };
      case "processing":
      case "berjalan":
        return { dot: "bg-amber-500", label: "Memproses OCR" };
      case "jeda":
      case "paused":
        return { dot: "bg-orange-500", label: "Dijeda" };
      case "menunggu_koreksi":
        return { dot: "bg-sky-500", label: "Menunggu Verifikasi" };
      case "failed":
      case "gagal":
        return { dot: "bg-rose-500", label: "Gagal" };
      default:
        return { dot: "bg-[var(--text-muted)]", label: "Menunggu" };
    }
  };

  if (loading) {
    return (
      <div className="p-4 sm:p-6 lg:p-8 max-w-[1600px] mx-auto space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm">
          <div className="flex items-center gap-4">
            <div className="skeleton w-10 h-10 rounded-xl" />
            <div className="space-y-2">
              <div className="skeleton h-6 w-64 rounded-lg" />
              <div className="skeleton h-4 w-36 rounded-md" />
            </div>
          </div>
          <div className="skeleton h-8 w-32 rounded-full" />
        </div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="p-4 sm:p-6 lg:p-8 max-w-xl mx-auto space-y-4">
        <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--red-color)] rounded-2xl text-sm font-medium">
          {error || "Dokumen tidak ditemukan"}
        </div>
        <Link
          to="/dashboard"
          className="inline-flex items-center gap-2 text-sm font-bold text-[var(--brand-primary)] hover:text-[var(--brand-hover)]"
        >
          ← Kembali ke Dashboard
        </Link>
      </div>
    );
  }

  const currentStatus = document.ekstraksi_status || document.status;
  const statusBadge = getStatusBadge(currentStatus);

  const parentChunks = chunks.filter(
    (c) => c.metadata?.chunk_type === "parent" || String(c.id).includes("_parent_")
  );
  const childChunks = chunks.filter(
    (c) => c.metadata?.chunk_type === "child" || String(c.id).includes("_child_")
  );

  let activeTabChunks = chunks;
  if (chromaActiveTab === "child") {
    activeTabChunks = selectedChromaParentId
      ? childChunks.filter(
          (c) =>
            c.metadata?.parent_id === selectedChromaParentId ||
            String(c.metadata?.parent_id).endsWith(`_${selectedChromaParentId}`)
        )
      : childChunks;
  } else if (chromaActiveTab === "parent") {
    activeTabChunks = parentChunks;
  } else if (chromaActiveTab === "all") {
    activeTabChunks = parentChunks.length > 0 ? parentChunks : chunks;
  }

  const filteredChunks = activeTabChunks.filter((c) => {
    if (!chunkSearch.trim()) return true;
    const searchLower = chunkSearch.toLowerCase();
    const matchesSelf =
      c.text?.toLowerCase().includes(searchLower) ||
      String(c.id).toLowerCase().includes(searchLower) ||
      String(c.metadata?.page_number).includes(searchLower);

    if (matchesSelf) return true;

    if (chromaActiveTab === "all" && parentChunks.length > 0) {
      const pIndex = c.metadata?.chunk_index;
      const children = childChunks.filter(
        (ch) =>
          ch.metadata?.parent_id === c.id ||
          (pIndex !== undefined && ch.metadata?.parent_id === `doc_${document.id}_parent_${pIndex}`)
      );
      return children.some(
        (ch) =>
          ch.text?.toLowerCase().includes(searchLower) ||
          String(ch.id).toLowerCase().includes(searchLower)
      );
    }

    return false;
  });

  return (
    <div className="p-3 sm:p-4 lg:p-4.5 w-full space-y-3.5 bg-[var(--bg-main)] text-[var(--text-primary)] relative">
      {/* Solid Opaque Floating Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-[99999] max-w-[420px] animate-in fade-in slide-in-from-bottom-5 duration-300">
          <div
            className={`p-4 rounded-2xl border shadow-2xl bg-[var(--bg-card)] flex items-start gap-3.5 ${
              toast.type === "error"
                ? "border-[var(--border-color)] text-[var(--red-color)]"
                : toast.type === "success"
                  ? "border-[var(--border-color)] text-[var(--action-green)]"
                  : "border-[var(--border-color)] text-[var(--brand-primary)]"
            }`}
          >
            <div
              className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
                toast.type === "error"
                  ? "bg-[var(--bg-input)] text-[var(--red-color)]"
                  : toast.type === "success"
                    ? "bg-[var(--bg-input)] text-[var(--action-green)]"
                    : "bg-[var(--bg-input)] text-[var(--brand-primary)]"
              }`}
            >
              {toast.type === "error" ? (
                <svg
                  className="w-4.5 h-4.5"
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
              ) : toast.type === "success" ? (
                <svg
                  className="w-4.5 h-4.5"
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
              ) : (
                <svg
                  className="w-4.5 h-4.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              )}
            </div>
            <div className="flex-1 pr-1">
              <h4 className="text-sm font-bold text-[var(--text-primary)]">
                {toast.title}
              </h4>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed font-medium">
                {toast.message}
              </p>
            </div>
            <button
              onClick={() => setToast(null)}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors cursor-pointer"
              title="Tutup"
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
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-4 py-3 sm:px-5 sm:py-3.5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-xs">
        <div className="flex items-center gap-3.5">
          <Link
            to="/dashboard"
            title="Kembali ke Dashboard"
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-sky-500 hover:scale-105 transition-all"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
          </Link>
          <div>
            <h1 className="text-xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
              <span>{document.title}</span>
              <InfoTooltip size="lg" content="Detail berkas dokumen, visualisasi per halaman, status ekstraksi OCR, perbaikan typo LLM, dan embedding vektor." />
            </h1>
            <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">
              {document.original_name || document.original_filename}
            </p>
          </div>
        </div>

        {/* Action Button Strip */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Segment 1: Live Status Indicator Pill */}
          <div className="flex items-center">
            <span
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-semibold border bg-[var(--bg-input)] border-[var(--border-color)] text-[var(--text-primary)] transition-all shadow-2xs"
            >
              <span className={`w-2 h-2 rounded-full ${statusBadge.dot}`} />
              <span>{statusBadge.label}</span>
            </span>
          </div>

          {/* Hairline Divider */}
          <div className="hidden sm:block h-5 w-px bg-[var(--border-color)]" />

          {/* Segment 2: Document Utility Action (Buka PDF Asli) */}
          <a
            href={`${documentsApi.pdfUrl(id)}?t=${pdfTimestamp}`}
            target="_blank"
            rel="noopener"
            className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-sky-500 transition-all inline-flex items-center gap-1.5 shadow-2xs cursor-pointer"
            title="Buka File PDF Asli di Tab Baru"
          >
            <svg
              className="w-3.5 h-3.5 text-inherit"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <span>PDF Asli</span>
          </a>

          {/* Hairline Divider */}
          <div className="hidden sm:block h-5 w-px bg-[var(--border-color)]" />

          {/* Sidebar Toggle Icon Button */}
          <button
            type="button"
            onClick={() => setIsRightSidebarOpen(!isRightSidebarOpen)}
            className={`p-1.5 rounded-xl border transition-all inline-flex items-center justify-center cursor-pointer ${
              isRightSidebarOpen
                ? "bg-[var(--bg-input)] border-[var(--border-color)] text-sky-500 hover:text-sky-400 hover:border-sky-500 shadow-2xs"
                : "bg-[var(--bg-input)] border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-sky-500 shadow-2xs"
            }`}
            title={
              isRightSidebarOpen
                ? "Sembunyikan Panel Informasi"
                : "Tampilkan Panel Informasi"
            }
          >
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
            >
              {/* Outer Window Outline */}
              <rect
                x="3"
                y="3"
                width="18"
                height="18"
                rx="4"
                strokeWidth="2"
              />
              {/* Sidebar Pane Division Line */}
              <path
                d="M15 3V21"
                strokeWidth="2"
                strokeDasharray="0"
              />
              {/* Sidebar Content Bars */}
              <path
                d="M18 7H19M18 10H19M18 13H19"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Main Split-Screen Workspace (PDF vs Inspector / Chunks) */}
      <div
        ref={containerRef}
        className="relative flex flex-col md:flex-row items-stretch bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm overflow-hidden min-h-[750px] lg:h-[calc(100vh-185px)] select-none"
      >
        {/* LEFT COLUMN: PDF Preview & Manual OCR Correction */}
        <div
          style={{ width: isRightSidebarOpen ? `${leftColWidth}%` : "100%" }}
          className="flex flex-col h-full self-stretch min-h-0 overflow-hidden transition-[width] duration-75"
        >
          <ManualCorrectionEditor
            key={`${document.id}-${pdfTimestamp}`}
            documentId={document.id}
            documentTitle={document.title || document.original_name || document.original_filename}
            totalPages={document.total_pages || 1}
            isExtractionCompleted={
              currentStatus === "completed" ||
              currentStatus === "selesai" ||
              currentStatus === "menunggu_koreksi" ||
              ((document.halaman_selesai ?? document.processed_pages ?? 0) >=
                (document.total_pages || 1) &&
                (document.total_pages || 0) > 0)
            }
            status={currentStatus}
            timestamp={pdfTimestamp}
            onSaveToCorpusSuccess={fetchDocument}
          />
        </div>

        {/* Resizer Divider (Option B: Center Grip Pill + Glow Line + Double-Click Reset) */}
        {isRightSidebarOpen && (
          <div
            className={`group relative flex items-center justify-center cursor-col-resize select-none self-stretch w-4 -mx-2 shrink-0 transition-colors z-20 ${
              isResizing ? "bg-sky-500/10" : "hover:bg-sky-500/5"
            }`}
            onMouseDown={startDrag}
            onDoubleClick={handleResetSplit}
            title="Geser untuk mengatur lebar kolom (Klik 2x untuk reset ke 65%)"
          >
            {/* 1px Center Line with Hover/Active Glow */}
            <div
              className={`w-[1px] h-full transition-colors duration-150 ${
                isResizing
                  ? "bg-sky-500"
                  : "bg-[var(--border-color)] group-hover:bg-sky-500"
              }`}
            />

            {/* Center Floating Pill Grip Handle */}
            <div
              className={`absolute top-1/2 -translate-y-1/2 pointer-events-none flex flex-col items-center justify-center gap-0.5 w-3.5 h-8 rounded-full border shadow-sm transition-all duration-150 ${
                isResizing
                  ? "bg-sky-500 border-sky-500 text-white scale-110 shadow-md"
                  : "bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-muted)] group-hover:border-sky-500 group-hover:text-sky-500 group-hover:scale-105"
              }`}
            >
              <div className="w-0.5 h-0.5 rounded-full bg-current opacity-80" />
              <div className="w-0.5 h-0.5 rounded-full bg-current opacity-80" />
              <div className="w-0.5 h-0.5 rounded-full bg-current opacity-80" />
            </div>
          </div>
        )}

        {/* RIGHT COLUMN: Sidebar */}
        {isRightSidebarOpen && (
          <div className="flex-1 min-w-[280px] self-stretch flex flex-col min-h-0 overflow-y-auto divide-y divide-[var(--border-color)] bg-[var(--bg-card)]">
            {/* 1. Document Metadata & Extraction Controls */}
            <div>
              <button
                type="button"
                onClick={() => setIsInfoOpen(!isInfoOpen)}
                className={`w-full px-4 py-2.5 bg-[var(--bg-input)]/40 hover:bg-[var(--bg-input)]/70 flex justify-between items-center text-xs shrink-0 min-h-[45px] transition-colors cursor-pointer group text-left ${
                  isInfoOpen ? "border-b border-[var(--border-color)]" : ""
                }`}
              >
                <span className="font-bold text-[var(--text-primary)] text-sm group-hover:text-sky-500 transition-colors flex items-center">
                  <span>Informasi Dokumen</span>
                  <InfoTooltip content="Ringkasan metadata file asli, jumlah halaman, dan parameter ekstraksi dokumen." />
                </span>
                <svg
                  className={`w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-sky-500 transition-transform duration-300 ${
                    isInfoOpen ? "rotate-180 text-sky-500" : ""
                  }`}
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
              </button>

              <div
                ref={infoContentRef}
                style={isInfoOpen ? undefined : { height: 0, opacity: 0, overflow: "hidden" }}
              >
                <div className="p-4 sm:p-5 space-y-4">
                  <div className="space-y-1">
                    {[
                      {
                        label: "Kategori AI",
                        value:
                          document.category_name || document.category?.name || "Umum",
                      },
                      { label: "Tipe Dokumen", value: document.pdf_type_label },
                      {
                        label: "Halaman / Vektor",
                        value: `${document.total_pages || "-"} hal / ${document.total_chunks !== null && document.total_chunks !== undefined ? `${document.total_chunks} vektor` : "-"}`,
                      },
                      { label: "Pengunggah", value: document.uploaded_by || "-" },
                      {
                        label: "Waktu Unggah",
                        value: formatDate(document.created_at),
                      },
                    ].map(({ label, value }) => (
                      <div
                        key={label}
                        className="flex justify-between items-center py-1.5"
                      >
                        <span className="text-xs font-medium text-[var(--text-muted)]">
                          {label}
                        </span>
                        <span className="text-xs font-bold text-[var(--text-primary)] text-right truncate max-w-[60%]">
                          {label === "Kategori AI" ? (
                            <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-[var(--bg-input)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                              {value}
                            </span>
                          ) : (
                            value
                          )}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* AI Extraction Progress & Action Controls */}
                  <div className="pt-3.5 border-t border-[var(--border-color)] space-y-3">
                    <div className="flex justify-between text-xs font-bold">
                      <span className="text-[var(--text-secondary)]">
                        Progres Ekstraksi
                      </span>
                      <span className="text-sky-500 font-mono font-bold">
                        {document.halaman_selesai ?? document.processed_pages ?? 0}{" "}
                        / {document.total_pages || 0} (
                        {document.persen_ekstraksi ??
                          (document.total_pages
                            ? Math.round(
                                ((document.halaman_selesai ??
                                  document.processed_pages ??
                                  0) /
                                  document.total_pages) *
                                  100,
                              )
                            : 0)}
                        %)
                      </span>
                    </div>

                    <div className="h-2 rounded-full bg-[var(--bg-input)] border border-[var(--border-color)] overflow-hidden">
                      <div
                        className="h-full transition-all duration-500 rounded-full"
                        style={{
                          width: `${document.persen_ekstraksi ?? (document.total_pages ? Math.min(100, Math.round(((document.halaman_selesai ?? document.processed_pages ?? 0) / document.total_pages) * 100)) : 0)}%`,
                          background:
                            currentStatus === "jeda" || currentStatus === "paused"
                              ? "#f97316"
                              : currentStatus === "completed" ||
                                  currentStatus === "selesai"
                                ? "#10b981"
                                : "#0ea5e9",
                        }}
                      />
                    </div>

                    {/* Contextual Status for Non-Technical Admins */}
                    {(currentStatus === "processing" ||
                      currentStatus === "berjalan") && (
                      <div className="flex items-center text-xs text-[var(--text-secondary)]">
                        <span>
                          Sedang mengekstrak{" "}
                          <strong className="text-[var(--text-primary)] font-semibold">
                            Halaman{" "}
                            {Math.min(
                              document.total_pages || 171,
                              (document.halaman_selesai ??
                                document.processed_pages ??
                                0) + 1,
                            )}
                          </strong>{" "}
                          dari {document.total_pages || 0}
                        </span>
                      </div>
                    )}

                    {/* Extraction Action Buttons */}
                    <div className="flex gap-2 pt-1">
                      {currentStatus === "processing" ||
                      currentStatus === "berjalan" ? (
                        <button
                          onClick={handlePause}
                          disabled={document.jeda_diminta}
                          className="w-full py-2.5 text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-amber-600 dark:text-amber-400 border border-[var(--border-color)] rounded-xl transition-colors flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer shadow-2xs"
                        >
                          <svg
                            className="w-3.5 h-3.5"
                            fill="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <rect x="6" y="4" width="4" height="16" rx="1" />
                            <rect x="14" y="4" width="4" height="16" rx="1" />
                          </svg>
                          <span>{document.jeda_diminta ? "Menjeda..." : "Jeda Ekstraksi"}</span>
                        </button>
                      ) : currentStatus === "completed" ||
                        currentStatus === "selesai" ? (
                        <div className="flex-1 py-2 px-3 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-emerald-600 dark:text-emerald-400 font-semibold text-xs flex items-center justify-center shadow-2xs">
                          <span>Dokumen Berhasil Diindeks</span>
                        </div>
                      ) : currentStatus === "menunggu_koreksi" ||
                        (document.total_pages > 0 &&
                          (document.halaman_selesai ??
                            document.processed_pages ??
                            0) >= document.total_pages) ? (
                        <div className="flex-1 py-2 px-3 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] font-semibold text-xs flex items-center justify-center gap-2 shadow-2xs">
                          <span>Ekstraksi Selesai (Menunggu Verifikasi)</span>
                        </div>
                      ) : (
                        <button
                          onClick={handleResume}
                          className="flex-1 py-2 text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white rounded-xl shadow-md shadow-sky-500/25 transition-all duration-200 hover:scale-[1.01] flex items-center justify-center gap-1.5"
                        >
                          <svg
                            className="w-4 h-4"
                            fill="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path d="M8 5v14l11-7z" />
                          </svg>
                          {currentStatus === "jeda" || currentStatus === "paused"
                            ? "Lanjutkan Ekstraksi"
                            : "Mulai Ekstraksi"}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* 2. Activity Logs Section */}
            <div>
              <button
                type="button"
                onClick={() => setIsLogsOpen(!isLogsOpen)}
                className={`w-full px-4 py-2.5 bg-[var(--bg-input)] hover:bg-[var(--bg-card)] flex justify-between items-center text-xs shrink-0 min-h-[45px] transition-colors cursor-pointer group text-left ${
                  isLogsOpen ? "border-b border-[var(--border-color)]" : ""
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-bold text-[var(--text-primary)] text-sm group-hover:text-sky-500 transition-colors flex items-center">
                    <span>Riwayat Aktivitas</span>
                    <InfoTooltip content="Catatan kronologis log eksekusi proses OCR Vision, post-processing LLM, dan vektorisasi." />
                  </span>
                  {document.logs && document.logs.length > 0 && (
                    <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                      {document.logs.length} Log
                    </span>
                  )}
                </div>
                <svg
                  className={`w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-sky-500 transition-transform duration-300 ${
                    isLogsOpen ? "rotate-180 text-sky-500" : ""
                  }`}
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
              </button>

              <div
                ref={logsContentRef}
                style={isLogsOpen ? undefined : { height: 0, opacity: 0, overflow: "hidden" }}
              >
                <div className="p-4 sm:p-5 space-y-3 relative">
                  {document.logs && document.logs.length > 0 ? (
                    <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[var(--border-color)]">
                      {document.logs.map((log, idx) => (
                        <div key={idx} className="relative group text-xs">
                          <div
                            className={`absolute -left-6 top-0.5 w-2.5 h-2.5 rounded-full border-2 border-[var(--bg-card)] ${
                              log.level === "error"
                                ? "bg-red-500 ring-2 ring-red-500/20"
                                : log.level === "warn"
                                  ? "bg-amber-500 ring-2 ring-amber-500/20"
                                  : "bg-sky-500"
                            }`}
                          />
                          <div className="flex justify-between items-start gap-2">
                            <span className="font-bold text-[var(--text-primary)] leading-tight">
                              {log.message}
                            </span>
                            <span className="text-[10px] text-[var(--text-muted)] shrink-0 font-mono">
                              {formatTime(log.timestamp || log.created_at)}
                            </span>
                          </div>
                          {log.details && (
                            <p className="mt-1 text-[11px] text-[var(--text-secondary)] font-mono bg-[var(--bg-card)] p-2 rounded-lg border border-[var(--border-color)] break-words">
                              {typeof log.details === "object"
                                ? JSON.stringify(log.details, null, 2)
                                : log.details}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-[var(--text-muted)] italic py-2 text-center">
                      Belum ada catatan aktivitas sistem.
                    </p>
                  )}
                </div>
              </div>
            </div>

            {/* 3. Consolidated Document Management Card */}
            <div>
              <button
                type="button"
                onClick={() => setIsManagementOpen(!isManagementOpen)}
                className={`w-full px-4 py-2.5 bg-[var(--bg-input)] hover:bg-[var(--bg-card)] flex justify-between items-center text-xs shrink-0 min-h-[45px] transition-colors cursor-pointer group text-left ${
                  isManagementOpen ? "border-b border-[var(--border-color)]" : ""
                }`}
              >
                <span className="font-bold text-[var(--text-primary)] text-sm group-hover:text-sky-500 transition-colors flex items-center">
                  <span>Pengelolaan Dokumen</span>
                  <InfoTooltip content="Tindakan pembaruan file PDF atau penghapusan dokumen secara permanen dari basis korpus." />
                </span>
                <svg
                  className={`w-3.5 h-3.5 text-[var(--text-muted)] group-hover:text-sky-500 transition-transform duration-300 ${
                    isManagementOpen ? "rotate-180 text-sky-500" : ""
                  }`}
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
              </button>

              <div
                ref={managementContentRef}
                style={isManagementOpen ? undefined : { height: 0, opacity: 0, overflow: "hidden" }}
              >
                <div className="p-4 sm:p-5 space-y-2">
                  <button
                    onClick={() => {
                      setReplaceFile(null);
                      setShowReplaceModal(true);
                    }}
                    disabled={
                      currentStatus === "processing" ||
                      currentStatus === "berjalan"
                    }
                    className="w-full py-2.5 px-3.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 font-bold text-xs transition-all flex items-center justify-center gap-2 shadow-xs disabled:opacity-50 hover:scale-[1.01]"
                  >
                    <svg
                      className="w-4 h-4 text-inherit"
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
                    <span>Ganti File PDF</span>
                  </button>

                  <button
                    onClick={handleDelete}
                    className="w-full py-2.5 px-3.5 rounded-xl bg-red-500 border border-red-500 text-white hover:bg-red-600 font-bold text-xs transition-all flex items-center justify-center gap-2 hover:scale-[1.01]"
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
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                    <span>Hapus Dokumen</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* FULL-WIDTH: ChromaDB Vector Chunks */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[var(--border-color)] flex flex-col md:flex-row md:items-center justify-between gap-3 bg-[var(--bg-input)]">
          <div className="flex flex-wrap items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] flex items-center justify-center text-sky-500 shrink-0">
              <svg
                className="w-4.5 h-4.5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
            </div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-sm font-black text-[var(--text-primary)] tracking-tight">
                ChromaDB Chunks
              </h2>
              {chunks.length > 0 && (
                <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                  {chunks.length} Vektor
                </span>
              )}
            </div>

            {/* Chroma Tabs */}
            {showChunks && chunks.length > 0 && (
              <div className="flex items-center gap-1 bg-[var(--bg-card)] p-1 rounded-xl border border-[var(--border-color)] text-xs font-bold">
                <button
                  onClick={() => {
                    setChromaActiveTab("all");
                    setSelectedChromaParentId(null);
                  }}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                    chromaActiveTab === "all"
                      ? "bg-sky-500 text-white shadow-2xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  Semua ({chunks.length})
                </button>
                <button
                  onClick={() => {
                    setChromaActiveTab("child");
                  }}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                    chromaActiveTab === "child"
                      ? "bg-sky-500 text-white shadow-2xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  Potongan Anak ({childChunks.length})
                </button>
                <button
                  onClick={() => {
                    setChromaActiveTab("parent");
                    setSelectedChromaParentId(null);
                  }}
                  className={`px-2.5 py-1 rounded-lg transition-all cursor-pointer ${
                    chromaActiveTab === "parent"
                      ? "bg-sky-500 text-white shadow-2xs"
                      : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                  }`}
                >
                  Potongan Induk ({parentChunks.length})
                </button>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Parent Dropdown Filter (Tab Anak) */}
            {showChunks && chromaActiveTab === "child" && parentChunks.length > 0 && (
              <div className="relative inline-flex items-center">
                <select
                  value={selectedChromaParentId ?? "all"}
                  onChange={(e) => {
                    setSelectedChromaParentId(
                      e.target.value === "all" ? null : e.target.value
                    );
                  }}
                  className="text-xs bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] rounded-xl px-2.5 py-1.5 focus:outline-none focus:border-sky-500 cursor-pointer font-medium"
                >
                  <option value="all">
                    Semua Induk ({childChunks.length} Anak)
                  </option>
                  {parentChunks.map((p, pIdx) => {
                    const pIndex =
                      p.metadata?.chunk_index !== undefined
                        ? p.metadata.chunk_index
                        : pIdx;
                    const pId = p.id || `doc_${document.id}_parent_${pIndex}`;
                    const cCount = childChunks.filter(
                      (ch) =>
                        ch.metadata?.parent_id === pId ||
                        ch.metadata?.parent_id === `doc_${document.id}_parent_${pIndex}`
                    ).length;
                    const pageN = p.metadata?.page_number || "-";
                    return (
                      <option key={pId || pIdx} value={pId}>
                        Induk #{pIndex + 1} (Hal. {pageN} • {cCount} anak)
                      </option>
                    );
                  })}
                </select>
              </div>
            )}

            {showChunks && chunks.length > 0 && (
              <div className="relative">
                <input
                  type="text"
                  value={chunkSearch}
                  onChange={(e) => setChunkSearch(e.target.value)}
                  placeholder="Cari chunk..."
                  className="px-3 pr-7 py-1.5 rounded-xl text-xs bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-sky-500 w-40 sm:w-48"
                />
                {chunkSearch && (
                  <button
                    onClick={() => setChunkSearch("")}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                  >
                    ✕
                  </button>
                )}
              </div>
            )}

            <button
              onClick={() => {
                setShowChunks(!showChunks);
                if (!showChunks && chunks.length === 0) fetchChunks();
              }}
              className="px-3.5 py-2 rounded-xl text-xs font-bold bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all flex items-center gap-1.5 cursor-pointer shadow-xs"
            >
              <svg
                className={`w-3.5 h-3.5 text-inherit transition-transform duration-200 ${showChunks ? "rotate-180 text-sky-500" : ""}`}
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
              <span>{showChunks ? "Tutup Vektor" : "Lihat Vektor"}</span>
            </button>
          </div>
        </div>

        {showChunks && (
          <div className="p-4 sm:p-5">
            {/* Active Parent Filter Banner (ChromaDB Solid Opaque High-Contrast) */}
            {chromaActiveTab === "child" && selectedChromaParentId && (
              <div className="flex items-center justify-between px-3.5 py-2.5 bg-[var(--bg-card)] border-2 border-sky-500 rounded-xl text-xs text-[var(--text-primary)] font-semibold shadow-sm animate-in fade-in duration-150 mb-3.5">
                <div className="flex items-center gap-2.5">
                  <div className="w-6 h-6 rounded-lg bg-sky-500 text-white flex items-center justify-center shrink-0 shadow-2xs font-bold">
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
                    </svg>
                  </div>
                  <span className="text-[var(--text-primary)]">
                    Memfilter potongan anak dari:{" "}
                    <strong className="text-sky-500 font-bold px-2 py-0.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)]">
                      {(() => {
                        const m = String(selectedChromaParentId).match(/_parent_(\d+)$/);
                        if (m) return `Induk #${parseInt(m[1], 10) + 1}`;
                        const foundIdx = parentChunks.findIndex((p) => p.id === selectedChromaParentId);
                        if (foundIdx !== -1) return `Induk #${foundIdx + 1}`;
                        return selectedChromaParentId;
                      })()}
                    </strong>{" "}
                    ({activeTabChunks.length} potongan anak)
                  </span>
                </div>
                <button
                  onClick={() => setSelectedChromaParentId(null)}
                  className="px-3 py-1.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 text-xs font-bold transition-colors cursor-pointer flex items-center gap-1.5 shadow-2xs"
                >
                  <span>✕ Tampilkan Semua Anak</span>
                </button>
              </div>
            )}

            {loadingChunks ? (
              <div className="py-12 text-center text-xs text-[var(--text-muted)] italic flex flex-col items-center justify-center gap-2.5">
                <span className="spin w-5 h-5 border-2 border-[var(--border-color)] border-t-sky-500 rounded-full" />
                <span>Memuat data vektor dari ChromaDB...</span>
              </div>
            ) : chunks.length === 0 ? (
              <div className="py-12 text-center text-xs text-[var(--text-muted)] italic">
                Belum ada vektor tersimpan di ChromaDB untuk dokumen ini.
              </div>
            ) : filteredChunks.length === 0 ? (
              <div className="py-10 text-center text-xs text-[var(--text-muted)] italic">
                Tidak ada chunk yang cocok dengan kriteria filter.
              </div>
            ) : (
              <div ref={chromaChunksListRef} className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3.5">
                {filteredChunks.map((c, idx) => {
                  const isParent =
                    c.metadata?.chunk_type === "parent" || String(c.id).includes("_parent_");
                  const isChild =
                    c.metadata?.chunk_type === "child" || String(c.id).includes("_child_");

                  // Parent chunk index / label
                  const parentIdx =
                    c.metadata?.chunk_index !== undefined
                      ? c.metadata.chunk_index
                      : (() => {
                          const m = String(c.id).match(/_parent_(\d+)$/);
                          return m ? parseInt(m[1], 10) : idx;
                        })();

                  // Child's parent index
                  let childParentNumber = null;
                  if (isChild) {
                    if (c.metadata?.parent_index !== undefined) {
                      childParentNumber = c.metadata.parent_index + 1;
                    } else if (c.metadata?.parent_id) {
                      const m = String(c.metadata.parent_id).match(/_parent_(\d+)$/);
                      if (m) childParentNumber = parseInt(m[1], 10) + 1;
                    }
                  }

                  // Related children for parent chunk
                  const relatedChildren = isParent
                    ? childChunks.filter(
                        (ch) =>
                          ch.metadata?.parent_id === c.id ||
                          ch.metadata?.parent_id === `doc_${document.id}_parent_${parentIdx}`
                      )
                    : [];

                  // TAB 1: CHROMA HIERARCHICAL ACCORDION (TAB "Semua")
                  if (chromaActiveTab === "all" && parentChunks.length > 0) {
                    const pKey = c.id || `doc_${document.id}_parent_${parentIdx}`;
                    const isExpanded =
                      expandedChromaParents.has(pKey) || expandedChromaParents.has(c.id);

                    return (
                      <div
                        key={c.id || idx}
                        className="chroma-chunk-anim col-span-1 md:col-span-2 xl:col-span-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)] transition-all shadow-xs overflow-hidden"
                      >
                        {/* Accordion Header */}
                        <div
                          onClick={() => {
                            setExpandedChromaParents((prev) => {
                              const next = new Set(prev);
                              if (next.has(pKey) || next.has(c.id)) {
                                next.delete(pKey);
                                next.delete(c.id);
                              } else {
                                next.add(pKey);
                                next.add(c.id);
                              }
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
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  strokeWidth={2}
                                  d="M19 9l-7 7-7-7"
                                />
                              </svg>
                            </div>

                            <span className="font-bold text-[var(--text-primary)] text-xs truncate">
                              Hal. {c.metadata?.page_number || "-"}
                            </span>

                            <span className="text-xs font-mono text-[var(--text-muted)] hidden sm:inline">
                              ({c.text?.length || 0} karakter)
                            </span>

                            <span className="text-xs font-mono text-[var(--text-muted)] hidden md:inline truncate max-w-[160px]">
                              • ID: {String(c.id).substring(0, 16)}...
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
                                      handleCopyText(c.text, c.id || parentIdx);
                                    }}
                                    className="px-2.5 py-0.5 rounded-md bg-[var(--bg-input)] border border-[var(--border-color)] hover:border-sky-500 hover:text-sky-500 text-[11px] font-bold transition-colors cursor-pointer"
                                  >
                                    {copiedContext === (c.id || parentIdx) ? "✓ Tersalin" : "Salin Teks"}
                                  </button>
                                </div>

                                <div className="p-3 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-xl text-xs space-y-2 shadow-2xs transition-all max-h-[380px] flex flex-col">
                                  <div className="h-6 flex justify-between items-center text-xs font-mono text-[var(--text-muted)] shrink-0">
                                    <div className="flex items-center gap-2">
                                      <span className="px-2 py-0.5 rounded-md bg-sky-500 text-white font-bold text-xs shadow-2xs">
                                        Induk #{parentIdx + 1}
                                      </span>
                                      <span className="font-bold text-[var(--text-primary)]">
                                        Hal. {c.metadata?.page_number || "-"}
                                      </span>
                                    </div>
                                    <span className="text-xs text-[var(--text-muted)]">
                                      {c.text?.length || 0} kar.
                                    </span>
                                  </div>
                                  <p className="whitespace-pre-wrap text-[var(--text-primary)] font-mono leading-relaxed bg-[var(--bg-card)] p-3 rounded-lg border border-[var(--border-color)] select-text text-xs overflow-y-auto pr-1.5 flex-1">
                                    {c.text}
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
                                    relatedChildren.map((ch, chIdx) => (
                                      <div
                                        key={ch.id || chIdx}
                                        className="p-3 bg-[var(--bg-input)] border border-[var(--border-color)] rounded-xl text-xs space-y-2 shadow-2xs transition-all"
                                      >
                                        <div className="h-6 flex justify-between items-center text-xs font-mono text-[var(--text-muted)]">
                                          <div className="flex items-center gap-2">
                                            <span className="px-2 py-0.5 rounded-md bg-emerald-500 text-white font-bold text-xs shadow-2xs">
                                              Bagian {chIdx + 1} dari {relatedChildren.length}
                                            </span>
                                            <span className="font-bold text-[var(--text-primary)]">
                                              Hal. {ch.metadata?.page_number || "-"}
                                            </span>
                                          </div>
                                          <span className="text-xs text-[var(--text-muted)]">
                                            {ch.text?.length || 0} kar.
                                          </span>
                                        </div>
                                        <p className="whitespace-pre-wrap text-[var(--text-primary)] font-mono leading-relaxed bg-[var(--bg-card)] p-3 rounded-lg border border-[var(--border-color)] select-text text-xs">
                                          {ch.text}
                                        </p>
                                      </div>
                                    ))
                                  )}
                                </div>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  }

                  // Highlight detection
                  const isHighlighted =
                    highlightedChromaChunkId &&
                    (highlightedChromaChunkId === c.id ||
                      (isParent &&
                        highlightedChromaChunkId === `doc_${document.id}_parent_${parentIdx}`));

                  return (
                    <div
                      key={c.id || idx}
                      className={`chroma-chunk-anim p-3.5 rounded-xl transition-all flex flex-col justify-between space-y-2.5 shadow-xs ${
                        isHighlighted
                          ? "bg-[var(--bg-card)] border-2 border-sky-500 shadow-sm"
                          : "bg-[var(--bg-input)] border border-[var(--border-color)] hover:border-[var(--border-hover)]"
                      }`}
                    >
                      <div className="flex justify-between items-center text-xs font-mono text-[var(--text-muted)] pb-2 border-b border-[var(--border-color)]">
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-[var(--text-primary)]">
                            Hal. {c.metadata?.page_number || "-"}
                          </span>
                          <span className="text-xs text-[var(--text-muted)]">
                            ({c.text?.length || 0} kar.)
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
                          ) : isChild && childParentNumber !== null ? (
                            <button
                              onClick={() => {
                                setSelectedChromaParentId(null);
                                setChromaActiveTab("parent");
                                setHighlightedChromaChunkId(
                                  c.metadata?.parent_id || `doc_${document.id}_parent_${childParentNumber - 1}`
                                );
                              }}
                              className="px-2.5 py-1 rounded-lg bg-sky-500 text-white hover:bg-sky-600 font-bold text-xs transition-all flex items-center gap-1.5 cursor-pointer group shadow-2xs"
                              title={`Klik untuk melihat Potongan Induk #${childParentNumber}`}
                            >
                              <span>Induk #{childParentNumber}</span>
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
                        {c.text}
                      </p>

                      {/* Parent Card Action: Lihat X Potongan Anak */}
                      {isParent && (
                        <div className="pt-2 border-t border-[var(--border-color)] flex justify-between items-center text-xs">
                          <span className="font-mono text-[var(--text-muted)]">
                            {relatedChildren.length} potongan anak
                          </span>
                          <button
                            onClick={() => {
                              setSelectedChromaParentId(
                                c.id || `doc_${document.id}_parent_${parentIdx}`
                              );
                              setChromaActiveTab("child");
                              setHighlightedChromaChunkId(null);
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
                      )}

                      {/* Child Card Footer */}
                      {!isParent && (
                        <div className="pt-2 border-t border-[var(--border-color)] flex justify-between items-center text-xs font-mono text-[var(--text-muted)]">
                          <span className="truncate max-w-[140px]" title={String(c.id)}>
                            ID: {String(c.id).substring(0, 14)}...
                          </span>
                          <span>{c.text?.length || 0} kar.</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Modal Hapus Dokumen */}
      <ConfirmModal
        isOpen={showDeleteModal}
        title="Hapus Dokumen"
        message="Dokumen dan seluruh vektor terkait akan dihapus secara permanen. Lanjutkan?"
        onConfirm={confirmDelete}
        onCancel={() => setShowDeleteModal(false)}
        confirmText="Hapus"
      />


      {/* Modal Ganti File Dokumen Dedicated */}
      {showReplaceModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center p-4">
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] max-w-md w-full rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-4 border-b border-[var(--border-color)] flex justify-between items-center bg-[var(--bg-input)]">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-sky-500 flex items-center justify-center">
                  <svg
                    className="w-4.5 h-4.5"
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
                </div>
                <h3 className="text-base font-bold text-[var(--text-primary)]">
                  Ganti File Dokumen
                </h3>
              </div>
              <button
                onClick={() => setShowReplaceModal(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors"
              >
                ✕
              </button>
            </div>

            <form onSubmit={confirmReplace} className="p-6 space-y-4">
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Mengganti file akan menghapus indeks lama dan mengulang seluruh
                proses ekstraksi dokumen. Format yang didukung: PDF, DOCX, XLSX,
                CSV, TXT, MD, PNG, JPG, JPEG, WEBP.
              </p>

              <div className="p-4 rounded-xl border border-dashed border-[var(--border-color)] bg-[var(--bg-input)]">
                <input
                  type="file"
                  accept=".pdf,.docx,.xlsx,.xls,.csv,.txt,.md,.png,.jpg,.jpeg,.webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv,text/plain,text/markdown,image/png,image/jpeg,image/webp"
                  onChange={(e) => setReplaceFile(e.target.files[0])}
                  disabled={replacing}
                  className="w-full text-xs text-[var(--text-secondary)] file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-[var(--bg-card)] file:border file:border-[var(--border-color)] file:text-sky-500 cursor-pointer"
                />
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowReplaceModal(false)}
                  disabled={replacing}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={!replaceFile || replacing}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white shadow-md shadow-sky-500/25 transition-all hover:scale-[1.01] disabled:opacity-50 flex items-center gap-2"
                >
                  {replacing ? (
                    <>
                      <span className="spin w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full" />
                      <span>Mengunggah...</span>
                    </>
                  ) : (
                    "Ganti & Proses Ulang"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
