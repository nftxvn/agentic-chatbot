import React, { useEffect, useState, useRef } from "react";
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
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const [isStalled, setIsStalled] = useState(false);

  const lastProgressRef = useRef({ progress: 0, time: Date.now() });

  useEffect(() => {
    if (!isOpen || !documentId) return;

    let isMounted = true;
    let pollInterval = null;

    setIsDone(false);
    setIsFailed(false);
    setErrorMessage("");
    setShowTechnicalDetails(false);
    setIsStalled(false);
    setProgress(5);
    setStatusMessage("Mengirim permintaan ke worker antrean...");
    lastProgressRef.current = { progress: 5, time: Date.now() };

    const checkStatus = async () => {
      try {
        const res = await documentsApi.getExtractionStatus(documentId);
        const data = res?.data || res;

        if (!isMounted || !data) return;

        const currentStatus = data.status;
        const currentPersen = typeof data.persen === "number" ? data.persen : 0;
        const currentPesan = data.pesan || "Sedang memproses penyimpanan korpus...";

        if (currentPersen > 0) {
          setProgress((prev) => {
            if (prev !== currentPersen) {
              lastProgressRef.current = { progress: currentPersen, time: Date.now() };
              setIsStalled(false);
            }
            return currentPersen;
          });
        }

        if (currentPesan) {
          setStatusMessage(currentPesan);
        }

        // Cek jika proses terhenti lebih dari 60 detik tanpa perubahan
        if (
          !isDone &&
          !isFailed &&
          Date.now() - lastProgressRef.current.time > 60000
        ) {
          setIsStalled(true);
        }

        // Embedding selesai HANYA jika persentase sudah 100%
        // atau status selesai dengan persentase >= 95%
        const isCompleted =
          currentPersen >= 100 ||
          ((currentStatus === "selesai" || currentStatus === "completed") &&
            currentPersen >= 95);

        if (isCompleted) {
          setProgress(100);
          setIsDone(true);
          setIsFailed(false);
          setStatusMessage("Selesai! Seluruh vektor berhasil disimpan ke ChromaDB.");
          if (pollInterval) clearInterval(pollInterval);
        } else if (currentStatus === "gagal" || currentStatus === "failed") {
          setIsFailed(true);
          setIsDone(false);
          setErrorMessage(
            currentPesan || "Terjadi kesalahan saat memotong atau menyimpan vektor."
          );
          if (pollInterval) clearInterval(pollInterval);
        } else {
          // Masih dalam progres pemrosesan (misal 5%, 25%, 45%, dsb.)
          setIsDone(false);
          setIsFailed(false);
        }
      } catch (err) {
        // Abaikan transient network error saat polling
      }
    };

    // Jalankan segera dan set interval tiap 1.5 detik
    checkStatus();
    pollInterval = setInterval(checkStatus, 1500);

    return () => {
      isMounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [isOpen, documentId]);

  if (!isOpen) return null;

  // Deteksi status retry/peringatan di latar belakang
  const isRetrying =
    !isDone &&
    !isFailed &&
    (statusMessage.toLowerCase().includes("gagal") ||
      statusMessage.toLowerCase().includes("percobaan") ||
      statusMessage.toLowerCase().includes("menjadwalkan ulang") ||
      statusMessage.toLowerCase().includes("retry"));

  // Ekstrak pesan bersih untuk tampilan yang ramah pengguna
  const getFriendlyMessage = () => {
    const raw = isFailed ? errorMessage : statusMessage;

    if (raw.toLowerCase().includes("cuda")) {
      return {
        title: "Kendala Akselerasi GPU (CUDA)",
        desc: "Sistem mengalami kendala pada alokasi VRAM GPU CUDA. Worker sedang mencoba ulang otomatis.",
        tip: "Pastikan model bge-m3 tersedia di Ollama atau atur EMBEDDING_DEVICE=cpu di berkas .env.",
        isWarning: true,
      };
    }
    if (
      raw.toLowerCase().includes("connection") &&
      (raw.toLowerCase().includes("refused") || raw.toLowerCase().includes("ollama"))
    ) {
      return {
        title: "Koneksi ke Ollama Terputus",
        desc: "Layanan Ollama tidak merespons atau sedang offline.",
        tip: "Pastikan engine Ollama sudah aktif dan dapat diakses.",
        isWarning: true,
      };
    }
    if (isRetrying) {
      return {
        title: "Sedang Menjadwalkan Ulang...",
        desc: raw,
        tip: "Worker latar belakang akan mencoba kembali hingga 3 kali secara otomatis.",
        isWarning: true,
      };
    }
    if (isFailed) {
      return {
        title: "Proses Embedding Gagal",
        desc: raw,
        tip: "Anda dapat menutup dialog ini dan mencoba kembali setelah memeriksa model Ollama.",
        isWarning: false,
      };
    }

    return null;
  };

  const friendly = getFriendlyMessage();

  const handleClose = () => {
    if (isDone && onComplete) {
      onComplete();
    }
    if (onClose) {
      onClose();
    }
  };

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-[9999] flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] max-w-lg w-full rounded-2xl shadow-2xl animate-in fade-in zoom-in-95 duration-200 overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-[var(--border-color)] flex justify-between items-center bg-[var(--bg-input)]">
          <div className="flex items-center gap-3">
            <div
              className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${
                isDone
                  ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-500"
                  : isFailed
                  ? "bg-rose-500/10 border-rose-500/20 text-rose-500"
                  : isRetrying
                  ? "bg-amber-500/10 border-amber-500/20 text-amber-500"
                  : "bg-sky-500/10 border-sky-500/20 text-sky-500"
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
              ) : isRetrying ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
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
                  : isRetrying
                  ? "Mengalami Kendala (Sedang Mencoba Ulang)"
                  : "Menyimpan ke Korpus Vektor ChromaDB"}
              </h3>
              <p className="text-xs text-[var(--text-muted)] m-0 font-medium">
                {isDone
                  ? "Dokumen telah terindeks dan siap digunakan"
                  : isFailed
                  ? "Pemrosesan embedding terhenti"
                  : "Model: BAAI/bge-m3 | Target: ChromaDB"}
              </p>
            </div>
          </div>
        </div>

        {/* Body Content */}
        <div className="p-6 space-y-5">
          {/* Progress Percentage Display */}
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider">
              {isDone ? "Status Akhir" : isFailed ? "Status Gagal" : "Progres Embedding"}
            </span>
            <span
              className={`text-lg font-black font-mono ${
                isDone
                  ? "text-emerald-500"
                  : isFailed
                  ? "text-rose-500"
                  : isRetrying
                  ? "text-amber-500"
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
                  ? "bg-rose-500"
                  : isRetrying
                  ? "bg-gradient-to-r from-amber-500 to-amber-600"
                  : "bg-gradient-to-r from-sky-500 via-sky-400 to-sky-600"
              }`}
              style={{ width: `${Math.max(3, Math.min(100, progress))}%` }}
            />
          </div>

          {/* Kotak Peringatan / Kendala Ramah Pengguna */}
          {friendly ? (
            <div
              className={`p-3.5 rounded-xl border text-xs space-y-1.5 ${
                isFailed
                  ? "bg-rose-500/10 border-rose-500/20 text-rose-600 dark:text-rose-400"
                  : "bg-amber-500/10 border-amber-500/20 text-amber-700 dark:text-amber-300"
              }`}
            >
              <div className="flex items-center gap-2 font-bold">
                <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <span>{friendly.title}</span>
              </div>
              <p className="m-0 leading-relaxed opacity-95">{friendly.desc}</p>
              {friendly.tip && (
                <p className="m-0 pt-0.5 font-medium opacity-90 text-[11px]">
                  💡 <strong>Saran:</strong> {friendly.tip}
                </p>
              )}

              {/* Toggle Detail Teknis */}
              <div className="pt-1">
                <button
                  type="button"
                  onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
                  className="underline hover:opacity-80 text-[11px] font-semibold cursor-pointer"
                >
                  {showTechnicalDetails ? "Sembunyikan log teknis" : "Lihat pesan log teknis"}
                </button>
                {showTechnicalDetails && (
                  <pre className="mt-2 p-2 rounded bg-black/30 text-[10px] font-mono whitespace-pre-wrap break-all max-h-28 overflow-y-auto">
                    {isFailed ? errorMessage : statusMessage}
                  </pre>
                )}
              </div>
            </div>
          ) : (
            /* Status Pesan Normal */
            <div className="pt-1 space-y-1">
              <p
                className={`text-sm font-semibold m-0 leading-snug ${
                  isDone ? "text-emerald-600 dark:text-emerald-400" : "text-[var(--text-primary)]"
                }`}
              >
                {statusMessage}
              </p>
              {!isDone && (
                <p className="text-xs text-[var(--text-muted)] m-0 font-medium">
                  Proses berjalan di antrean background worker. Halaman tidak perlu di-refresh.
                </p>
              )}
            </div>
          )}

          {/* Notifikasi jika stuck lama */}
          {isStalled && !isDone && !isFailed && !friendly && (
            <div className="p-3 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-muted)]">
              ℹ️ Proses memerlukan waktu lebih lama dari biasanya. Anda dapat menutup dialog ini dan memeriksa statusnya nanti dari daftar dokumen.
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-2">
            {!isDone && !isFailed ? (
              <>
                <span className="text-[11px] text-[var(--text-muted)] italic">
                  Background task tetap berjalan jika ditutup
                </span>
                <button
                  type="button"
                  onClick={handleClose}
                  className="px-4 py-2 rounded-xl text-xs font-semibold bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors cursor-pointer"
                >
                  Tutup Dialog
                </button>
              </>
            ) : (
              <div className="flex justify-end w-full">
                <button
                  type="button"
                  onClick={handleClose}
                  className={`px-5 py-2.5 rounded-xl text-xs font-bold transition-all hover:scale-[1.01] cursor-pointer shadow-md ${
                    isDone
                      ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                      : "bg-rose-600 hover:bg-rose-700 text-white"
                  }`}
                >
                  {isDone ? "Selesai & Lihat Status Dokumen" : "Tutup (Gagal)"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}
