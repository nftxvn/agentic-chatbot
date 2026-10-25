import { useEffect, useCallback, useRef } from "react";
import { documentsApi } from "../../api/documents";

/** Autosave, simpan manual, navigasi halaman, URL/history, dan shortcut editor; dependency tetap mengikuti lifecycle semula. */
export function useCorrectionPersistence({
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
}) {
  const saveQueueRef = useRef(Promise.resolve());
  const savePageText = useCallback(
    (textToSave, pageNum, isSilent = false) => {
      // Send corrections in request order so a slow autosave cannot overwrite
      // a newer manual save or the save required before page navigation.
      const performSave = async () => {
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
      };
      const pending = saveQueueRef.current.then(performSave, performSave);
      saveQueueRef.current = pending;
      return pending;
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
        const saved = await savePageText(currentText, currentPage, true);
        if (!saved) {
          // History navigation already changed the URL; restore its page when
          // persistence fails so the address and the retained draft agree.
          if (!syncUrl) {
            setSearchParams(
              (prev) => {
                const nextParams = new URLSearchParams(prev);
                nextParams.set("page", String(currentPage));
                return nextParams;
              },
              { replace: true },
            );
          }
          return false;
        }
      }

      resetViewport();
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

  return {
    savePageText,
    handlePageChange,
  };
}
