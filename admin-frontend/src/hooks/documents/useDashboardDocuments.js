import { useState, useEffect, useRef, useLayoutEffect } from "react";
import { documentsApi } from "../../api/documents";
import { categoriesApi } from "../../api/categories";
import gsap from "gsap";
import { addAppNotification } from "../../utils/notifications";

/** Daftar/statistik dokumen, polling, kategori, upload, jeda/resume, dan lifecycle modal dashboard. */
export function useDashboardDocuments() {
  const [data, setData] = useState({ documents: [], stats: {}, meta: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadCategoryId, setUploadCategoryId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStage, setUploadStage] = useState("idle");

  // idle | uploading | done

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [categories, setCategories] = useState([]);
  const fetchTimeout = useRef(null);
  const statsGridRef = useRef(null);
  const modalRef = useRef(null);
  const headerRef = useRef(null);

  const fetchData = async (page = 1) => {
    const startTime = Date.now();
    try {
      const res = await documentsApi.list(page);
      if (res && res.data) {
        setData({
          documents: res.data.documents || [],
          stats: res.data.stats || {},
          meta: res.data.meta || {},
          has_processing: !!res.data.has_processing,
        });
      }
      if (res?.data?.has_processing) {
        fetchTimeout.current = setTimeout(() => fetchData(page), 10000);
      }
    } catch (err) {
      setError(err.response?.data?.message || "Gagal memuat data dokumen.");
    } finally {
      const elapsed = Date.now() - startTime;
      setTimeout(() => setLoading(false), Math.max(0, 350 - elapsed));
    }
  };

  const fetchCategories = async () => {
    try {
      const res = await categoriesApi.list();
      setCategories(res.data);
      if (res.data && res.data.length > 0) {
        setUploadCategoryId(res.data[0].id);
      }
    } catch (err) {
      console.error("Failed to load categories", err);
    }
  };

  useEffect(() => {
    fetchData();
    fetchCategories();
    return () => clearTimeout(fetchTimeout.current);
  }, []);

  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -20 },
        {
          opacity: 1,
          x: 0,
          duration: 0.6,
          stagger: 0.1,
          ease: "power2.out",
          clearProps: "all",
        },
      );
    }
    if (!loading && statsGridRef.current) {
      const cards = statsGridRef.current.children;
      gsap.fromTo(
        cards,
        { opacity: 0, scale: 0.98 },
        {
          opacity: 1,
          scale: 1,
          duration: 0.4,
          stagger: 0.05,
          ease: "power2.out",
          clearProps: "all",
        },
      );
    }
  }, [loading]);

  useEffect(() => {
    if (showModal && modalRef.current) {
      gsap.fromTo(
        modalRef.current,
        { opacity: 0, scale: 0.9, y: 30 },
        { opacity: 1, scale: 1, y: 0, duration: 0.4, ease: "power2.inOut" },
      );
    }
  }, [showModal]);

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    if (!uploadTitle || !uploadTitle.trim()) {
      alert("Judul dokumen wajib diisi.");
      return;
    }
    if (!uploadCategoryId) {
      alert("Kategori AI prompt wajib dipilih.");
      return;
    }
    if (!uploadFile) {
      alert("File dokumen atau gambar wajib dipilih.");
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setUploadStage("uploading");

    try {
      await documentsApi.upload(
        uploadTitle,
        uploadFile,
        uploadCategoryId,
        (progressEvent) => {
          if (progressEvent.lengthComputable ?? progressEvent.total > 0) {
            const percent = Math.round(
              (progressEvent.loaded / progressEvent.total) * 100,
            );
            setUploadProgress(percent);
          }
        },
      );

      // Best Practice: Langsung transisi ke Selesai saat file berhasil disimpan backend
      setUploadProgress(100);
      setUploadStage("done");
      addAppNotification({
        title: "Dokumen Berhasil Diunggah",
        message: `Dokumen "${uploadTitle}" berhasil ditambahkan dan masuk antrean ekstraksi.`,
        type: "info",
      });
      await new Promise((r) => setTimeout(r, 600));
      setShowModal(false);
      setUploadTitle("");
      setUploadFile(null);
      setUploadProgress(0);
      setUploadStage("idle");
      fetchData();
    } catch (err) {
      alert(
        err.response?.data?.message ||
          err.message ||
          "Gagal mengunggah dokumen.",
      );
      setUploadStage("idle");
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const docTitle =
      deleteTarget.title || deleteTarget.original_filename || "Dokumen";
    try {
      await documentsApi.destroy(deleteTarget.id);
      addAppNotification({
        title: "Dokumen Dihapus",
        message: `Anda baru saja menghapus dokumen "${docTitle}"`,
        type: "warning",
      });
      fetchData(data.meta?.current_page || 1);
    } catch (err) {
      addAppNotification({
        title: "Gagal Menghapus",
        message: err.response?.data?.message || "Gagal menghapus dokumen.",
        type: "warning",
      });
    } finally {
      setDeleteTarget(null);
    }
  };

  const handlePauseProcess = async (docId, title) => {
    try {
      await documentsApi.pause(docId);
      addAppNotification({
        title: "Permintaan Jeda",
        message: `Pemrosesan dokumen "${title}" dijeda di batas halaman aktif.`,
        type: "info",
      });
      fetchData(data.meta?.current_page || 1);
    } catch (err) {
      addAppNotification({
        title: "Gagal Menjeda",
        message: err.response?.data?.message || "Server AI tidak merespons.",
        type: "warning",
      });
    }
  };

  const handleResumeProcess = async (docId, title) => {
    try {
      await documentsApi.resume(docId);
      addAppNotification({
        title: "Proses Dilanjutkan (Cicil)",
        message: `Pemrosesan AI dokumen "${title}" dilanjutkan kembali.`,
        type: "info",
      });
      fetchData(data.meta?.current_page || 1);
    } catch (err) {
      const msg =
        err.response?.data?.message ||
        err.message ||
        "Server AI (Python Uvicorn / Celery) sedang tidak berjalan.";
      addAppNotification({
        title: "Server AI Offline",
        message: msg,
        type: "warning",
      });
      alert(msg);
      fetchData(data.meta?.current_page || 1);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "-";
    try {
      const str = typeof dateString === "string" ? dateString : String(dateString);
      const localStr = str.replace("Z", "").replace("+00:00", "");
      const d = new Date(localStr);
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

  return {
    data,
    loading,
    error,
    showModal,
    setShowModal,
    uploadTitle,
    setUploadTitle,
    uploadFile,
    setUploadFile,
    uploadCategoryId,
    setUploadCategoryId,
    uploading,
    uploadProgress,
    uploadStage,
    deleteTarget,
    setDeleteTarget,
    categories,
    statsGridRef,
    modalRef,
    headerRef,
    fetchData,
    handleUploadSubmit,
    confirmDelete,
    handlePauseProcess,
    handleResumeProcess,
    formatDate,
  };
}
