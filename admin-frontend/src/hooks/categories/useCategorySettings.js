import { useState, useEffect, useRef, useLayoutEffect, useImperativeHandle } from "react";
import { useCategoryOcrTest } from "./useCategoryOcrTest";
import gsap from "gsap";
import { categoriesApi } from "../../api/categories";
import { addAppNotification } from "../../utils/notifications";

/** Data kategori, editor prompt/pelaksana, CRUD, dan lifecycle modal pengaturan kategori. */
export function useCategorySettings({ ref, PRESETS }) {
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

  const {
    testImageBase64,
    setTestImageBase64,
    testResult,
    setTestResult,
    rawOcrResult,
    setRawOcrResult,
    testDuration,
    setTestDuration,
    isTesting,
    activeTestTab,
    setActiveTestTab,
    copied,
    setCopied,
    isDragOver,
    setIsDragOver,
    handleCopyResult,
    handleTestPrompt,
    handleImageUpload,
    handleDrop,
  } = useCategoryOcrTest({ formData, jobTitlesList, customPrompts });

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

  return {
    categories,
    loading,
    showModal,
    setShowModal,
    editingCategory,
    deleteTarget,
    setDeleteTarget,
    formData,
    setFormData,
    isCustomVision,
    setIsCustomVision,
    showAdvanced,
    setShowAdvanced,
    jobTitlesList,
    newJobInput,
    setNewJobInput,
    isRawJsonMode,
    setIsRawJsonMode,
    promptBawaan,
    bagianDisalin,
    customPrompts,
    setCustomPrompts,
    editingBlocks,
    setEditingBlocks,
    ollamaModels,
    testImageBase64,
    setTestImageBase64,
    testResult,
    setTestResult,
    rawOcrResult,
    setRawOcrResult,
    testDuration,
    isTesting,
    activeTestTab,
    setActiveTestTab,
    copied,
    isDragOver,
    setIsDragOver,
    handleCopyResult,
    handleTestPrompt,
    handleImageUpload,
    handleDrop,
    gridRef,
    modalRef,
    salinTeks,
    handleOpenModal,
    handleLayoutChange,
    handleAddJobTitle,
    handleRemoveJobTitle,
    handleSubmit,
    confirmDelete,
  };
}
