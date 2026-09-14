import { useState, useEffect } from 'react';

export default function GlobalErrorToast() {
  const [error, setError] = useState(null);

  useEffect(() => {
    const handleError = (e) => {
      setError(e.detail);
      setTimeout(() => setError(null), 5000);
    };
    window.addEventListener('backend-error', handleError);
    return () => window.removeEventListener('backend-error', handleError);
  }, []);

  if (!error) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[99999] animate-in fade-in slide-in-from-bottom-5 duration-300">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-2xl p-4 flex items-start gap-3.5 max-w-[400px]">
        <div className="w-8 h-8 rounded-xl bg-[var(--bg-input)] text-[var(--red-color)] border border-[var(--border-color)] flex items-center justify-center shrink-0 mt-0.5">
          <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <path d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <div className="flex-1 pr-1">
          <h4 className="text-[var(--text-primary)] text-sm font-bold">Koneksi Bermasalah</h4>
          <p className="text-[var(--text-secondary)] text-xs leading-relaxed font-medium mt-0.5">{error}</p>
        </div>
        <button
          className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg text-sm transition-colors cursor-pointer"
          onClick={() => setError(null)}
          title="Tutup"
        >
          ✕
        </button>
      </div>
    </div>
  );
}
