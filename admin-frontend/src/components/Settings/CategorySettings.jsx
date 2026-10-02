import { useState, useEffect, useRef, useLayoutEffect, forwardRef, useImperativeHandle } from "react";
import ReactDOM from "react-dom";
import gsap from "gsap";
import { categoriesApi } from "../../api/categories";
import ConfirmModal from "../ConfirmModal";
import { Badge } from "@/components/ui/badge";
import { addAppNotification } from "../../utils/notifications";
import { SlidingTabs } from "../UI/SlidingTabs";
import { InfoTooltip } from "../UI/InfoTooltip";

const PRESETS = {
  general: {
    description:
      "Untuk peraturan, surat keputusan, notulen rapat, manual teknis, dan dokumen teks umum.",
    vision_prompt: `Anda adalah sistem OCR. Salin SELURUH teks yang terlihat pada gambar ini apa adanya.

ATURAN:
- Pertahankan urutan baca: atas ke bawah, kiri ke kanan.
- Pertahankan penomoran daftar dan struktur hierarki teks (\`1.\`, \`a.\`, \`aa.\`, \`iii.\`).
- Tulis isi tabel sebagai teks biasa atau daftar. JANGAN memakai tabel Markdown (tanda |).
- Bila sebuah sel kosong, biarkan kosong. Jangan menebak isinya.
- HANYA keluarkan teks hasil ekstraksi tanpa penjelasan atau komentar pembuka.`,
    job_titles: [],
  },
  sop: {
    description:
      "Untuk Standar Operasional Prosedur (SOP) dengan matriks tabel flowchart, pelaksana, dan mutu baku.",
    vision_prompt: `Anda adalah sistem OCR khusus formulir SOP pemerintah. Salin seluruh isi dokumen dengan aturan:

BAGIAN TABEL PROSEDUR (Uraian Prosedur / Langkah-langkah):
HANYA UNTUK TABEL YANG MEMILIKI KOLOM 'Uraian Prosedur', 'Pelaksana', dan 'Mutu Baku', gunakan format ini PERSIS untuk setiap langkah:
- <Nomor>. <Uraian Prosedur>
  - Pelaksana: <nama jabatan yang ada centang/simbol di kolomnya>
  - Kelengkapan: <isi kolom Kelengkapan>
  - Waktu: <isi kolom Waktu>
  - Output: <isi kolom Output>

ATURAN TAMBAHAN:
- Pelaksana ditentukan dari POSISI simbol flowchart (kotak/belah ketupat). Lihat simbol berada di bawah kolom jabatan mana.
- Waktu dan Output adalah DUA kolom BERBEDA. JANGAN digabung. (Contoh BENAR: Waktu: 30 menit / Output: Disposisi).
- HANYA keluarkan teks hasil ekstraksi tanpa komentar.`,
    job_titles: [
      "Kepala Dinas",
      "Sekretaris",
      "Kepala Bidang",
      "Kasubbag Umum & Kepegawaian",
      "Kasubbag Keuangan & Program",
      "Pranata Komputer",
      "Staf Pelaksana",
      "Pengguna Layanan",
    ],
  },
};

export const CategorySettings = forwardRef(function CategorySettings({ hideActionBar = false }, ref) {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);

  useImperativeHandle(ref, () => ({
    openCreateModal: () => handleOpenModal(),
  }));

  const [formData, setFormData] = useState({
    name: "",
    description: PRESETS.general.description,
    ui_layout: "general",
    vision_prompt: "",
    prompt_variables: "",
    vision_model: "",
  });

  const [isCustomVision, setIsCustomVision] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [jobTitlesList, setJobTitlesList] = useState([]);
  const [newJobInput, setNewJobInput] = useState("");
  const [isRawJsonMode, setIsRawJsonMode] = useState(false);

  const [promptBawaan, setPromptBawaan] = useState(null);
  const [bagianDisalin, setBagianDisalin] = useState(null);
  const [customPrompts, setCustomPrompts] = useState({});
  const [editingBlocks, setEditingBlocks] = useState({});

  const [ollamaModels, setOllamaModels] = useState([]);
  const [testImageBase64, setTestImageBase64] = useState("");
  const [testResult, setTestResult] = useState("");
  const [rawOcrResult, setRawOcrResult] = useState("");
  const [testDuration, setTestDuration] = useState(null);
  const [isTesting, setIsTesting] = useState(false);
  const [activeTestTab, setActiveTestTab] = useState("final");
  const [copied, setCopied] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

  const gridRef = useRef(null);
  const modalRef = useRef(null);
  const headerRef = useRef(null);

  useEffect(() => {
    fetchCategories();
    fetchOllamaModels();
    fetchPromptBawaan();
  }, []);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (showModal) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
    };
  }, [showModal]);

  // Escape key listener
  useEffect(() => {
    if (!showModal) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !isTesting) {
        setShowModal(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showModal, isTesting]);

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
    if (!loading && categories.length > 0 && gridRef.current) {
      const elements = gridRef.current.children;
      gsap.fromTo(
        elements,
        { opacity: 0, scale: 0.98 },
        {
          opacity: 1,
          scale: 1,
          duration: 0.4,
          stagger: 0.08,
          ease: "power2.out",
          clearProps: "all",
        },
      );
    }
  }, [loading, categories.length]);

  useEffect(() => {
    if (showModal && modalRef.current) {
      gsap.fromTo(
        modalRef.current,
        { opacity: 0, scale: 0.95, y: 20 },
        { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: "power2.out" },
      );
    }
  }, [showModal]);

  const fetchPromptBawaan = async () => {
    try {
      setPromptBawaan(await categoriesApi.promptEkstraksi());
    } catch (err) {
      console.error("Gagal mengambil prompt bawaan", err);
      setPromptBawaan(false);
    }
  };

  const salinTeks = async (kunci, teks) => {
    try {
      await navigator.clipboard.writeText(teks);
      setBagianDisalin(kunci);
      setTimeout(() => setBagianDisalin(null), 1600);
    } catch {
      /* clipboard ditolak browser */
    }
  };

  const fetchOllamaModels = async () => {
    try {
      const res = await categoriesApi.ollamaTags();
      if (res && res.models) {
        setOllamaModels(res.models.map((m) => m.name));
      }
    } catch (err) {
      console.error("Failed to load Ollama tags", err);
    }
  };

  const fetchCategories = async () => {
    const startTime = Date.now();
    try {
      setLoading(true);
      const res = await categoriesApi.list();
      setCategories(res.data);
    } catch (err) {
      console.error("Failed to load categories", err);
    } finally {
      const elapsed = Date.now() - startTime;
      setTimeout(() => setLoading(false), Math.max(0, 350 - elapsed));
    }
  };

  const handleOpenModal = (category = null) => {
    if (category) {
      setEditingCategory(category);
      const layout = category.ui_layout || "general";
      const preset = PRESETS[layout] || PRESETS.general;

      const hasCustomVision = Boolean(
        category.vision_prompt &&
        category.vision_prompt.trim() !== "" &&
        category.vision_prompt !== preset.vision_prompt,
      );

      const pv = category.prompt_variables || {};
      const tersimpan = pv.kata_kunci ?? pv.job_titles;
      let extractedJobTitles = [];
      if (tersimpan) {
        extractedJobTitles = Array.isArray(tersimpan) ? tersimpan : [];
      } else if (layout === "sop") {
        extractedJobTitles = PRESETS.sop.job_titles;
      }

      setIsCustomVision(hasCustomVision);
      setShowAdvanced(Boolean(category.vision_model));
      setJobTitlesList(extractedJobTitles);
      setIsRawJsonMode(false);
      setNewJobInput("");
      setCustomPrompts(pv.custom_prompts || {});
      setEditingBlocks({});

      setFormData({
        name: category.name || "",
        description: category.description || preset.description,
        ui_layout: layout,
        vision_prompt: hasCustomVision ? category.vision_prompt : "",
        prompt_variables: category.prompt_variables
          ? JSON.stringify(category.prompt_variables, null, 2)
          : "",
        vision_model: category.vision_model || "",
      });
    } else {
      setEditingCategory(null);
      setIsCustomVision(false);
      setShowAdvanced(false);
      setJobTitlesList(PRESETS.sop.job_titles);
      setIsRawJsonMode(false);
      setNewJobInput("");
      setCustomPrompts({});
      setEditingBlocks({});

      setFormData({
        name: "",
        description: PRESETS.general.description,
        ui_layout: "general",
        vision_prompt: "",
        prompt_variables: "",
        vision_model: "",
      });
    }
    setTestImageBase64("");
    setTestResult("");
    setRawOcrResult("");
    setTestDuration(null);
    setActiveTestTab("final");
    setCopied(false);
    setShowModal(true);
  };

  const handleLayoutChange = (newLayout) => {
    const preset = PRESETS[newLayout] || PRESETS.general;
    setFormData((prev) => ({
      ...prev,
      ui_layout: newLayout,
      description:
        prev.description === PRESETS.general.description ||
        prev.description === PRESETS.sop.description ||
        !prev.description
          ? preset.description
          : prev.description,
    }));

    if (newLayout === "sop" && jobTitlesList.length === 0) {
      setJobTitlesList(PRESETS.sop.job_titles);
    }
  };

  const handleAddJobTitle = (e) => {
    if (e.key === "Enter" || e.type === "click") {
      e.preventDefault();
      const val = newJobInput.trim();
      if (val && !jobTitlesList.includes(val)) {
        setJobTitlesList([...jobTitlesList, val]);
        setNewJobInput("");
      }
    }
  };

  const handleRemoveJobTitle = (titleToRemove) => {
    setJobTitlesList(jobTitlesList.filter((t) => t !== titleToRemove));
  };

  const handleCopyResult = () => {
    const textToCopy = activeTestTab === "raw" ? rawOcrResult : testResult;
    if (!textToCopy) return;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleTestPrompt = async () => {
    if (!testImageBase64) {
      alert("Silakan unggah gambar sampel terlebih dahulu untuk diuji.");
      return;
    }
    setIsTesting(true);
    setTestResult("");
    setRawOcrResult("");
    setTestDuration(null);
    setActiveTestTab("final");
    try {
      let baseVars = {};
      if (formData.prompt_variables && formData.prompt_variables.trim() !== "") {
        try {
          baseVars = JSON.parse(formData.prompt_variables);
        } catch {
          baseVars = {};
        }
      } else if (jobTitlesList.length > 0) {
        baseVars = { kata_kunci: jobTitlesList };
      }

      if (Object.keys(customPrompts).length > 0) {
        baseVars.custom_prompts = customPrompts;
      }

      const payload = {
        image_base64: testImageBase64.split(",")[1] || testImageBase64,
        category: {
          ...formData,
          prompt_variables: Object.keys(baseVars).length > 0 ? baseVars : null,
        },
      };
      const res = await categoriesApi.testPrompt(payload);
      if (res.success) {
        setTestResult(res.result || "");
        setRawOcrResult(res.raw_ocr || "");
        setTestDuration(res.duration || null);
      } else {
        setTestResult(
          "Error: " + (res.error || "Gagal menjalankan uji coba prompt."),
        );
      }
    } catch (err) {
      console.error(err);
      setTestResult(
        "Terjadi kesalahan saat memanggil test API. Pastikan server AI aktif.",
      );
    } finally {
      setIsTesting(false);
    }
  };

  const handleImageUpload = (e) => {
    const file = e.target.files ? e.target.files[0] : null;
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setTestImageBase64(reader.result);
      setTestResult("");
      setRawOcrResult("");
      setTestDuration(null);
    };
    reader.readAsDataURL(file);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = () => {
          setTestImageBase64(reader.result);
          setTestResult("");
          setRawOcrResult("");
          setTestDuration(null);
        };
        reader.readAsDataURL(file);
      } else {
        alert("Harap unggah berkas gambar (.jpg, .png, .jpeg, .webp).");
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!formData.name || !formData.name.trim()) {
      alert("Nama kategori wajib diisi.");
      return;
    }

    const layout = formData.ui_layout || "general";
    let finalPromptVariables = null;

    if (layout === "sop") {
      if (isRawJsonMode) {
        if (
          formData.prompt_variables &&
          formData.prompt_variables.trim() !== ""
        ) {
          try {
            finalPromptVariables = JSON.parse(formData.prompt_variables.trim());
          } catch (jsonErr) {
            alert(
              "Format JSON Prompt Variables tidak valid: " + jsonErr.message,
            );
            return;
          }
        }
      } else {
        finalPromptVariables =
          jobTitlesList.length > 0 ? { kata_kunci: jobTitlesList } : null;
      }
    } else {
      if (
        formData.prompt_variables &&
        formData.prompt_variables.trim() !== ""
      ) {
        try {
          finalPromptVariables = JSON.parse(formData.prompt_variables.trim());
        } catch (jsonErr) {
          alert("Format JSON Prompt Variables tidak valid: " + jsonErr.message);
          return;
        }
      }
    }

    if (Object.keys(customPrompts).length > 0) {
      finalPromptVariables = {
        ...(finalPromptVariables || {}),
        custom_prompts: customPrompts,
      };
    }

    try {
      const payload = {
        ...formData,
        vision_prompt:
          isCustomVision && formData.vision_prompt.trim() !== ""
            ? formData.vision_prompt.trim()
            : null,
        prompt_variables: finalPromptVariables,
      };

      if (editingCategory) {
        await categoriesApi.update(editingCategory.id, payload);
        addAppNotification({
          title: "Kategori AI Diperbarui",
          message: `Anda baru saja memperbarui kategori "${formData.name}"`,
          type: "info",
        });
      } else {
        await categoriesApi.create(payload);
        addAppNotification({
          title: "Kategori AI Baru",
          message: `Anda baru saja menambahkan kategori "${formData.name}"`,
          type: "info",
        });
      }
      setShowModal(false);
      fetchCategories();
    } catch (err) {
      console.error("Save failed", err);
      alert(err.response?.data?.message || "Gagal menyimpan kategori.");
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    const targetCat = categories.find((c) => c.id === deleteTarget);
    const catName = targetCat ? targetCat.name : "";
    try {
      await categoriesApi.destroy(deleteTarget);
      fetchCategories();
      addAppNotification({
        title: "Kategori AI Dihapus",
        message: `Anda baru saja menghapus kategori "${catName}"`,
        type: "warning",
      });
    } catch (err) {
      console.error("Delete failed", err);
      alert("Gagal menghapus kategori.");
    } finally {
      setDeleteTarget(null);
    }
  };

  return (
    <div className="space-y-4 sm:space-y-5 animate-in fade-in duration-300">
      {/* Action Bar (hanya tampil jika tidak disatukan di card atas) */}
      {!hideActionBar && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs">
          <div>
            <h2 className="text-base sm:text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
              <span>Manajemen Kategori & Aturan OCR</span>
              <InfoTooltip content="Pengaturan profil vision OCR, instruksi pembersih teks tabel SOP, dan variabel spesifik per kategori dokumen." />
            </h2>
          </div>
          <button
            className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-200 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-md shadow-sky-500/25 transition-all duration-200 hover:scale-[1.02] shrink-0 cursor-pointer"
            onClick={() => handleOpenModal()}
          >
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
                d="M12 4v16m8-8H4"
              />
            </svg>
            Tambah Kategori Baru
          </button>
        </div>
      )}

      {/* Grid of Categories */}
      <div>
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="bg-[var(--bg-card)] border border-[var(--border-color)] p-5 rounded-xl space-y-3"
              >
                <div className="skeleton h-6 w-1/2" />
                <div className="skeleton h-4 w-full" />
                <div className="skeleton h-4 w-3/4" />
                <div className="flex gap-3 pt-4">
                  <div className="skeleton h-10 flex-1" />
                  <div className="skeleton h-10 flex-1" />
                </div>
              </div>
            ))}
          </div>
        ) : categories.length === 0 ? (
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-12 text-center text-[var(--text-secondary)]">
            <div className="w-16 h-16 rounded-2xl bg-[var(--bg-input)] text-[var(--brand-primary)] border border-[var(--border-color)] flex items-center justify-center mx-auto mb-4">
              <svg
                className="w-8 h-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-1">
              Belum Ada Kategori
            </h3>
            <p className="text-sm">
              Tambahkan kategori pertama Anda untuk mulai mengatur prompt AI.
            </p>
          </div>
        ) : (
          <div
            className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5"
            ref={gridRef}
          >
            {categories.map((cat) => (
              <div
                key={cat.id}
                className="bg-[var(--bg-card)] border border-[var(--border-color)] p-5 rounded-2xl flex flex-col justify-between hover:border-sky-500 transition-all duration-200 shadow-xs"
              >
                <div>
                  <div className="flex justify-between items-start gap-3 mb-2">
                    <h2 className="text-base font-bold text-[var(--text-primary)] leading-tight">
                      {cat.name}
                    </h2>
                    <span className="px-2 py-0.5 rounded-md text-xs font-medium bg-[var(--bg-input)] text-[var(--text-secondary)] border border-[var(--border-color)] shrink-0">
                      {cat.ui_layout === "sop"
                        ? "SOP & Flowchart"
                        : "Teks Standar"}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-secondary)] leading-relaxed mb-3.5 line-clamp-2">
                    {cat.description || "Tidak ada deskripsi."}
                  </p>

                  {/* Parameter Info Chips */}
                  <div className="flex flex-wrap items-center gap-1.5 mb-4 text-xs text-[var(--text-muted)] font-mono">
                    <span className="inline-flex items-center gap-1 bg-[var(--bg-input)] px-2 py-0.5 rounded-md border border-[var(--border-color)]">
                      <svg
                        className="w-3 h-3 text-sky-500"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                        />
                      </svg>
                      Vision: {cat.vision_model || "qwen2.5vl"}
                    </span>
                    {cat.vision_prompt && (
                      <span className="inline-flex items-center gap-1 bg-[var(--bg-input)] px-2 py-0.5 rounded-md border border-[var(--border-color)] text-sky-500 font-medium">
                        Custom Prompt
                      </span>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between gap-2 pt-3.5 border-t border-[var(--border-color)]">
                  <button
                    className="flex-1 py-2 px-3.5 rounded-xl text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
                    onClick={() => handleOpenModal(cat)}
                  >
                    <svg
                      className="w-3.5 h-3.5 text-sky-500"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                      />
                    </svg>
                    Edit Konfigurasi
                  </button>

                  <button
                    className="p-2 rounded-xl text-[var(--text-muted)] hover:text-[var(--red-color)] hover:bg-[var(--bg-input)] transition-colors inline-flex items-center cursor-pointer shrink-0"
                    onClick={() => setDeleteTarget(cat.id)}
                    title="Hapus Kategori"
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
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Prompt Editor & Sandbox Modal (PORTAL KE DOCUMENT.BODY) */}
      {showModal &&
        ReactDOM.createPortal(
          <div
            className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-[99999] p-2 sm:p-4 md:p-6 animate-fade-in"
            onClick={(e) => {
              if (e.target === e.currentTarget && !isTesting) setShowModal(false);
            }}
          >
            <form
              noValidate
              className="bg-[var(--bg-card)] border border-[var(--border-color)] w-full max-w-7xl h-[92vh] max-h-[92vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden"
              onSubmit={handleSubmit}
              ref={modalRef}
            >
              {/* Modal Header */}
              <div className="px-6 py-3.5 border-b border-[var(--border-color)] flex justify-between items-center bg-[var(--bg-input)] rounded-t-2xl shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-sky-500 flex items-center justify-center shrink-0">
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
                        d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"
                      />
                    </svg>
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-[var(--text-primary)]">
                      {editingCategory
                        ? `${formData.name || "AI"}`
                        : "Kategori AI Baru"}
                    </h3>
                  </div>
                </div>
                <button
                  type="button"
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 rounded-lg hover:bg-[var(--border-color)] transition-colors cursor-pointer"
                  onClick={() => setShowModal(false)}
                  title="Tutup"
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
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </button>
              </div>

              {/* Modal Body: 2-Kolom Split Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-12 overflow-hidden flex-1 divide-y lg:divide-y-0 lg:divide-x divide-[var(--border-color)]">
                {/* SISI KIRI (7 Kolom): Form Konfigurasi Kategori & Prompt */}
                <div className="lg:col-span-7 overflow-y-auto p-6 space-y-6">
                  {/* 1. Informasi Kategori */}
                  <div className="space-y-4 pb-5 border-b border-[var(--border-color)]">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center">
                        <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                          Informasi Kategori
                        </h4>
                        <InfoTooltip
                          align="left"
                          content="Nama, layout antarmuka, dan deskripsi fungsi peruntukan kategori dokumen."
                        />
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                          Nama Kategori
                        </label>
                        <input
                          type="text"
                          className="w-full text-xs"
                          value={formData.name}
                          onChange={(e) =>
                            setFormData({ ...formData, name: e.target.value })
                          }
                          placeholder="Contoh: SOP Pelayanan Masyarakat"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                          UI Layout & Preset
                        </label>
                        <select
                          className="w-full text-xs"
                          value={formData.ui_layout}
                          onChange={(e) => handleLayoutChange(e.target.value)}
                        >
                          <option value="general">
                            Standard (Teks & OCR) — Dokumen Umum
                          </option>
                          <option value="sop">
                            SOP & Regulasi (Tabel & Daftar) — Flowchart
                          </option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                        Deskripsi Singkat
                      </label>
                      <input
                        type="text"
                        className="w-full text-xs"
                        value={formData.description}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            description: e.target.value,
                          })
                        }
                        placeholder="Deskripsi singkat peruntukan kategori dokumen ini"
                      />
                    </div>
                  </div>

                  {/* 2. Vision Prompt Section */}
                  <div className="space-y-3 pb-5 border-b border-[var(--border-color)]">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <div className="flex items-center">
                          <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                            Prompt Ekstraksi (Vision OCR)
                          </label>
                          <InfoTooltip
                            align="left"
                            content="Instruksi sistem kepada vision LLM saat melakukan OCR pada berkas atau gambar SOP."
                          />
                        </div>
                      </div>

                      <div className="inline-flex p-1 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            setIsCustomVision(false);
                            setFormData((p) => ({ ...p, vision_prompt: "" }));
                          }}
                          className={`px-3 py-1 rounded-lg text-xs transition-all cursor-pointer ${
                            !isCustomVision
                              ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm font-bold"
                              : "text-[var(--text-muted)] hover:text-[var(--text-primary)] font-medium"
                          }`}
                        >
                          Bawaan Sistem
                        </button>
                        <button
                          type="button"
                          onClick={() => setIsCustomVision(true)}
                          className={`px-3 py-1 rounded-lg text-xs transition-all cursor-pointer ${
                            isCustomVision
                              ? "bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm font-bold"
                              : "text-[var(--text-muted)] hover:text-[var(--text-primary)] font-medium"
                          }`}
                        >
                          + Tambahan Kustom
                        </button>
                      </div>
                    </div>

                    {!isCustomVision ? (
                      <div className="space-y-2.5">
                        {promptBawaan === null && (
                          <p className="text-xs text-[var(--text-muted)] m-0">
                            Memuat prompt bawaan…
                          </p>
                        )}
                        {promptBawaan === false && (
                          <p className="text-xs text-amber-500 m-0">
                            Teks prompt bawaan tidak bisa diambil — layanan AI
                            sedang tidak dapat dihubungi. Ekstraksi tetap memakai
                            aturan ini.
                          </p>
                        )}
                        {promptBawaan &&
                          Object.entries(promptBawaan)
                            .filter(([kunci]) =>
                              formData.ui_layout === "general"
                                ? kunci === "dasar"
                                : kunci !== "dasar"
                            )
                            .map(([kunci, bagian]) => {
                              const activeText =
                                customPrompts[kunci] !== undefined
                                  ? customPrompts[kunci]
                                  : bagian.teks;
                              const isCustomized =
                                customPrompts[kunci] !== undefined &&
                                customPrompts[kunci] !== bagian.teks;
                              const isEditing = Boolean(editingBlocks[kunci]);

                              return (
                                <div
                                  key={kunci}
                                  className={`rounded-xl border transition-all overflow-hidden ${
                                    isCustomized
                                      ? "border-sky-500 bg-[var(--bg-card)]"
                                      : "border-[var(--border-color)] bg-[var(--bg-input)]"
                                  }`}
                                >
                                  <div className="flex items-start justify-between gap-3 px-3.5 py-2.5 border-b border-[var(--border-color)]">
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2">
                                        <p className="text-xs font-bold text-[var(--text-primary)] m-0">
                                          {bagian.judul}
                                        </p>
                                        {isCustomized && (
                                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-md bg-[var(--bg-input)] text-sky-500 border border-[var(--border-color)]">
                                            Disesuaikan
                                          </span>
                                        )}
                                      </div>
                                      <p className="text-[11px] text-[var(--text-muted)] m-0 mt-0.5">
                                        {bagian.penjelasan}
                                      </p>
                                    </div>

                                    <div className="flex items-center gap-1 shrink-0">
                                      <button
                                        type="button"
                                        onClick={() => salinTeks(kunci, activeText)}
                                        className="px-2 py-1 text-[11px] font-medium rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)] transition-colors cursor-pointer"
                                        title="Salin isi aturan ini"
                                      >
                                        {bagianDisalin === kunci
                                          ? "Tersalin!"
                                          : "Salin"}
                                      </button>
                                      <button
                                        type="button"
                                        onClick={() =>
                                          setEditingBlocks((p) => ({
                                            ...p,
                                            [kunci]: !p[kunci],
                                          }))
                                        }
                                        className="px-2.5 py-1 text-[11px] font-semibold rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:border-sky-500 transition-colors cursor-pointer"
                                      >
                                        {isEditing ? "Tutup" : "Sesuaikan"}
                                      </button>
                                    </div>
                                  </div>

                                  {isEditing ? (
                                    <div className="p-3 space-y-2 bg-[var(--bg-card)]">
                                      <textarea
                                        rows={7}
                                        className="w-full text-xs font-mono p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                                        value={activeText}
                                        onChange={(e) =>
                                          setCustomPrompts((p) => ({
                                            ...p,
                                            [kunci]: e.target.value,
                                          }))
                                        }
                                      />
                                      {isCustomized && (
                                        <div className="flex justify-end">
                                          <button
                                            type="button"
                                            onClick={() =>
                                              setCustomPrompts((p) => {
                                                const n = { ...p };
                                                delete n[kunci];
                                                return n;
                                              })
                                            }
                                            className="text-[11px] font-medium text-[var(--text-muted)] hover:text-[var(--red-color)] cursor-pointer"
                                          >
                                            Kembalikan ke Teks Asli
                                          </button>
                                        </div>
                                      )}
                                    </div>
                                  ) : (
                                    <pre className="p-3 m-0 text-[11px] font-mono leading-relaxed text-[var(--text-secondary)] whitespace-pre-wrap max-h-36 overflow-y-auto">
                                      {activeText}
                                    </pre>
                                  )}
                                </div>
                              );
                            })}
                      </div>
                    ) : (
                      <div>
                        <textarea
                          rows={6}
                          className="w-full text-xs font-mono p-3 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                          value={formData.vision_prompt}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              vision_prompt: e.target.value,
                            })
                          }
                          placeholder="Tulis instruksi ekstraksi OCR khusus di sini..."
                        />
                      </div>
                    )}
                  </div>

                  {/* 3. Job Titles Section (For SOP Layout) */}
                  {formData.ui_layout === "sop" && (
                    <div className="space-y-3 pb-5 border-b border-[var(--border-color)]">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <label className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)]">
                            Nama Jabatan Pelaksana (SOP)
                          </label>
                          <InfoTooltip
                            align="left"
                            content="Daftar nama jabatan pelaksana yang akan dicocokkan otomatis dengan kolom flowchart SOP."
                          />
                        </div>
                        <button
                          type="button"
                          onClick={() => setIsRawJsonMode(!isRawJsonMode)}
                          className="text-[11px] font-semibold text-sky-500 hover:underline cursor-pointer"
                        >
                          {isRawJsonMode ? "Mode Tag Sederhana" : "Mode Raw JSON"}
                        </button>
                      </div>

                      {!isRawJsonMode ? (
                        <div className="space-y-2.5">
                          <div className="flex gap-2">
                            <input
                              type="text"
                              className="flex-1 text-xs"
                              value={newJobInput}
                              onChange={(e) => setNewJobInput(e.target.value)}
                              onKeyDown={handleAddJobTitle}
                              placeholder="Ketik nama jabatan lalu tekan Enter..."
                            />
                            <button
                              type="button"
                              onClick={handleAddJobTitle}
                              className="px-4 py-2 rounded-xl bg-[var(--bg-input)] hover:bg-[var(--border-color)] border border-[var(--border-color)] text-xs font-bold text-[var(--text-primary)] cursor-pointer"
                            >
                              Tambah
                            </button>
                          </div>

                          <div className="flex flex-wrap gap-1.5 min-h-[32px] p-2 bg-[var(--bg-input)]/50 rounded-xl border border-[var(--border-color)]">
                            {jobTitlesList.length === 0 ? (
                              <span className="text-xs text-[var(--text-muted)] italic p-1">
                                Belum ada jabatan yang ditentukan.
                              </span>
                            ) : (
                              jobTitlesList.map((job, idx) => (
                                <span
                                  key={idx}
                                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] text-xs font-medium text-[var(--text-primary)] shadow-xs"
                                >
                                  {job}
                                  <button
                                    type="button"
                                    onClick={() => handleRemoveJobTitle(job)}
                                    className="text-[var(--text-muted)] hover:text-rose-500 cursor-pointer"
                                  >
                                    ×
                                  </button>
                                </span>
                              ))
                            )}
                          </div>
                        </div>
                      ) : (
                        <div>
                          <textarea
                            rows={4}
                            className="w-full text-xs font-mono p-3 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]"
                            value={formData.prompt_variables}
                            onChange={(e) =>
                              setFormData({
                                ...formData,
                                prompt_variables: e.target.value,
                              })
                            }
                            placeholder='{"kata_kunci": ["Kepala Dinas", "Sekretaris"]}'
                          />
                        </div>
                      )}
                    </div>
                  )}

                  {/* 4. Advanced: Vision Model Selector */}
                  <div className="space-y-3">
                    <button
                      type="button"
                      onClick={() => setShowAdvanced(!showAdvanced)}
                      className="flex items-center gap-1.5 text-xs font-bold text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
                    >
                      <svg
                        className={`w-4 h-4 transition-transform duration-200 ${showAdvanced ? "rotate-90" : ""}`}
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
                      <span>Pengaturan Lanjutan: Vision Model Ekstraksi</span>
                    </button>

                    {showAdvanced && (
                      <div className="p-4 rounded-xl bg-[var(--bg-input)]/50 border border-[var(--border-color)] space-y-2">
                        <label className="block text-xs font-bold text-[var(--text-muted)]">
                          Model Vision Ollama
                        </label>
                        <select
                          className="w-full text-xs"
                          value={formData.vision_model}
                          onChange={(e) =>
                            setFormData({
                              ...formData,
                              vision_model: e.target.value,
                            })
                          }
                        >
                          <option value="">Bawaan Sistem (.env)</option>
                          {ollamaModels.map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                </div>

                {/* SISI KANAN (5 Kolom): Live OCR Tester & Sandbox */}
                <div className="lg:col-span-5 overflow-y-auto p-6 space-y-4 bg-[var(--bg-input)]/20">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-primary)] flex items-center gap-1.5">
                      <span>Uji Coba Ekstraksi OCR</span>
                      <InfoTooltip content="Unggah 1 gambar/scan sampel dokumen untuk menguji efektivitas prompt ekstraksi secara langsung." />
                    </h4>
                    {testDuration && (
                      <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-md bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--action-green)]">
                        {(testDuration / 1000).toFixed(2)}s
                      </span>
                    )}
                  </div>

                  {/* Drop Zone */}
                  <div
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsDragOver(true);
                    }}
                    onDragLeave={() => setIsDragOver(false)}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-xl p-4 text-center transition-all ${
                      isDragOver
                        ? "border-sky-500 bg-sky-500/10"
                        : "border-[var(--border-color)] bg-[var(--bg-card)]"
                    }`}
                  >
                    {testImageBase64 ? (
                      <div className="space-y-3">
                        <img
                          src={testImageBase64}
                          alt="Sampel Uji Coba"
                          className="max-h-40 mx-auto rounded-lg border border-[var(--border-color)] object-contain shadow-xs"
                        />
                        <div className="flex justify-center gap-2">
                          <label className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] cursor-pointer">
                            Ganti Gambar
                            <input
                              type="file"
                              accept="image/*"
                              onChange={handleImageUpload}
                              className="hidden"
                            />
                          </label>
                          <button
                            type="button"
                            onClick={() => {
                              setTestImageBase64("");
                              setTestResult("");
                              setRawOcrResult("");
                            }}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-rose-500 hover:bg-rose-500/10 transition-colors cursor-pointer"
                          >
                            Hapus
                          </button>
                        </div>
                      </div>
                    ) : (
                      <label className="block cursor-pointer py-4">
                        <svg
                          className="w-8 h-8 text-[var(--text-muted)] mx-auto mb-2"
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
                        <span className="text-xs font-bold text-[var(--text-primary)] block">
                          Klik atau Tarik Berkas Gambar Sampel ke Sini
                        </span>
                        <span className="text-[11px] text-[var(--text-muted)] block mt-0.5">
                          JPG, PNG, JPEG, atau WebP
                        </span>
                        <input
                          type="file"
                          accept="image/*"
                          onChange={handleImageUpload}
                          className="hidden"
                        />
                      </label>
                    )}
                  </div>

                  {/* Run Test Button */}
                  <button
                    type="button"
                    onClick={handleTestPrompt}
                    disabled={isTesting || !testImageBase64}
                    className="w-full py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white font-bold text-xs shadow-md shadow-sky-500/25 transition-all hover:scale-[1.01] disabled:opacity-50 cursor-pointer flex items-center justify-center gap-2"
                  >
                    {isTesting ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        <span>Sedang Mengekstraksi Teks...</span>
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
                            d="M13 10V3L4 14h7v7l9-11h-7z"
                          />
                        </svg>
                        <span>Uji Coba Prompt Sekarang</span>
                      </>
                    )}
                  </button>

                  {/* Result Inspector */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between border-b border-[var(--border-color)] pb-1.5">
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => setActiveTestTab("final")}
                          className={`text-xs font-bold pb-1 cursor-pointer transition-colors ${
                            activeTestTab === "final"
                              ? "text-sky-500 border-b-2 border-sky-500"
                              : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          Hasil Ekstraksi Bersih
                        </button>
                        <button
                          type="button"
                          onClick={() => setActiveTestTab("raw")}
                          className={`text-xs font-bold pb-1 cursor-pointer transition-colors ${
                            activeTestTab === "raw"
                              ? "text-sky-500 border-b-2 border-sky-500"
                              : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
                          }`}
                        >
                          Mentah (Raw OCR)
                        </button>
                      </div>

                      {(testResult || rawOcrResult) && (
                        <button
                          type="button"
                          onClick={handleCopyResult}
                          className="text-[11px] font-semibold text-sky-500 hover:underline cursor-pointer"
                        >
                          {copied ? "Tersalin!" : "Salin Hasil"}
                        </button>
                      )}
                    </div>

                    <div className="p-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] whitespace-pre-wrap max-h-56 overflow-y-auto leading-relaxed">
                      {isTesting ? (
                        <p className="text-[var(--text-muted)] italic text-center py-4">
                          Memproses gambar dengan Vision Model...
                        </p>
                      ) : (activeTestTab === "raw" ? rawOcrResult : testResult) ? (
                        activeTestTab === "raw" ? rawOcrResult : testResult
                      ) : (
                        <p className="text-[var(--text-muted)] text-center py-6 text-xs">
                          Hasil uji coba ekstraksi OCR akan muncul di sini.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>

              {/* Modal Footer */}
              <div className="px-6 py-3.5 border-t border-[var(--border-color)] flex justify-end gap-2.5 bg-[var(--bg-input)] rounded-b-2xl shrink-0">
                <button
                  type="button"
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors cursor-pointer"
                  onClick={() => setShowModal(false)}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white shadow-md shadow-sky-500/25 transition-all hover:scale-[1.01] cursor-pointer flex items-center gap-1.5"
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
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                  Simpan Kategori
                </button>
              </div>
            </form>
          </div>,
          document.body
        )}

      <ConfirmModal
        isOpen={!!deleteTarget}
        title="Hapus Kategori"
        message="Yakin ingin menghapus kategori ini? Data yang terkait mungkin akan ikut terpengaruh."
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
        confirmText="Hapus"
      />
    </div>
  );
});

export default CategorySettings;
