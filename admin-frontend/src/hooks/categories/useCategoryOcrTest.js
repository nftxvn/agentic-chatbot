import { useState } from "react";
import { categoriesApi } from "../../api/categories";

/** Sampel gambar OCR, request uji prompt, hasil raw/final, durasi, dan clipboard hasil. */
export function useCategoryOcrTest({ formData, jobTitlesList, customPrompts }) {
  const [testImageBase64, setTestImageBase64] = useState("");
  const [testResult, setTestResult] = useState("");
  const [rawOcrResult, setRawOcrResult] = useState("");
  const [testDuration, setTestDuration] = useState(null);
  const [isTesting, setIsTesting] = useState(false);
  const [activeTestTab, setActiveTestTab] = useState("final");
  const [copied, setCopied] = useState(false);
  const [isDragOver, setIsDragOver] = useState(false);

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

  return {
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
  };
}
