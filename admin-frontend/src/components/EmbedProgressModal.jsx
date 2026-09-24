import React, { useEffect, useState } from "react";
import ReactDOM from "react-dom";
import { documentsApi } from "../api/documents";

export default function EmbedProgressModal({
  isOpen,
  documentId,
  onComplete,
  onClose,
}) {
  const [progress, setProgress] = useState(0);
  const [statusMessage, setStatusMessage] = useState("Menyiapkan proses penyimpanan...");
  const [isDone, setIsDone] = useState(false);
  const [isFailed, setIsFailed] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!isOpen || !documentId) return;

    let isMounted = true;
    let pollInterval = null;

    setIsDone(false);
    setIsFailed(false);
    setProgress(5);
    setStatusMessage("Mengirim permintaan ke worker antrean...");

    const checkStatus = async () => {
      try {
        const res = await documentsApi.getExtractionStatus(documentId);
        const data = res?.data || res;

        if (!isMounted || !data) return;

        const currentStatus = data.status;
        const currentPersen = typeof data.persen === "number" ? data.persen : 0;
        const currentPesan = data.pesan || "Sedang memproses penyimpanan korpus...";

        if (currentPersen > 0) {
          setProgress(currentPersen);
        }
        if (currentPesan) {
          setStatusMessage(currentPesan);
        }

        if (currentStatus === "selesai" || currentStatus === "completed" || currentPersen >= 100) {
          setProgress(100);
          setIsDone(true);
          setStatusMessage(currentPesan || "Selesai! Seluruh vektor berhasil disimpan ke ChromaDB.");
          if (pollInterval) clearInterval(pollInterval);
        } else if (currentStatus === "gagal" || currentStatus === "failed") {
          setIsFailed(true);
          setErrorMessage(currentPesan || "Terjadi kesalahan saat memotong atau menyimpan vektor.");
          if (pollInterval) clearInterval(pollInterval);
        }
      } catch (err) {
        // Abaikan transient network error saat polling
      }
    };

    // Jalankan segera dan set interval tiap 1 detik
    checkStatus();
    pollInterval = setInterval(checkStatus, 1000);

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [isOpen, documentId]);

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-[9999] flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] max-w-lg w-full rounded-2xl shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--border-color)] flex justify-between items-center bg-[var(--bg-input)] rounded-t-2xl">
          <div className="flex items-center gap-3">
            <div
              className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${
                isDone
                  ? "bg-[var(--bg-card)] border-[var(--border-color)] text-emerald-500"
                  : isFailed
                  ? "bg-[var(--bg-card)] border-[var(--border-color)] text-red-500"
                  : "bg-[var(--bg-card)] border-[var(--border-color)] text-sky-500"
              }`}
            >
              {isDone ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                </svg>
              ) : isFailed ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <span className="spin w-4.5 h-4.5 border-2 border-[var(--border-color)] border-t-sky-500 rounded-full" />
              )}
            </div>
            <div>
              <h3 className="text-sm font-bold text-[var(--text-primary)] m-0">
                {isDone
                  ? "Penyimpanan Korpus Berhasil"
                  : isFailed
                  ? "Gagal Menyimpan Korpus"
                  : "Menyimpan ke Korpus Vektor ChromaDB"}
              </h3>
              <p className="text-xs text-[var(--text-muted)] m-0 font-medium">
                {isDone
                  ? "Dokumen telah terindeks dan siap digunakan"
                  : "Model: BAAI/bge-m3 | Target: ChromaDB"}
              </p>
            </div>
          </div>
          {isDone && (
            <button
              onClick={() => {
                if (onComplete) onComplete();
                if (onClose) onClose();
              }}
              className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors cursor-pointer"
              title="Tutup"
            >
              ✕
            </button>
          )}
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-5">
          {/* Progress Percentage Display */}
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
              {isDone ? "Status" : "Progres Embedding"}
            </span>
            <span
              className={`text-lg font-black font-mono ${
                isDone
                  ? "text-emerald-500"
                  : isFailed
                  ? "text-red-500"
                  : "text-sky-500"
              }`}
            >
              {progress}%
            </span>
          </div>

          {/* Animated Progress Bar */}
          <div className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] h-3 rounded-full overflow-hidden p-0.5">
            <div
              className={`h-full rounded-full transition-all duration-300 ease-out ${
                isDone
                  ? "bg-emerald-500"
                  : isFailed
                  ? "bg-red-500"
                  : "bg-gradient-to-r from-sky-500 via-sky-400 to-sky-600"
              }`}
              style={{ width: `${Math.max(3, Math.min(100, progress))}%` }}
            />
          </div>

          {/* Status Message (Clean Text tanpa Dot Pulse) */}
          <div className="pt-1 space-y-1">
            <p
              className={`text-sm font-semibold m-0 leading-snug ${
                isDone
                  ? "text-emerald-600 dark:text-emerald-400"
                  : isFailed
                  ? "text-rose-600 dark:text-rose-400"
                  : "text-[var(--text-primary)]"
              }`}
            >
              {isFailed ? errorMessage : statusMessage}
            </p>
            {!isDone && !isFailed && (
              <p className="text-xs text-[var(--text-muted)] m-0 font-medium">
                Proses berjalan di antrean background worker. Halaman tidak perlu di-refresh.
              </p>
            )}
          </div>

          {/* Action Button when Done or Failed */}
          {(isDone || isFailed) && (
            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => {
                  if (onComplete) onComplete();
                  if (onClose) onClose();
                }}
                className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all hover:scale-[1.01] cursor-pointer shadow-md ${
                  isDone
                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                    : "bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)]"
                }`}
              >
                {isDone ? "Selesai & Lihat Status Dokumen" : "Tutup"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
