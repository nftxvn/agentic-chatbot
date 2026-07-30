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
    <div className="fixed bottom-6 right-6 z-[99999]" style={{ animation: 'slideIn 0.4s ease-in-out' }}>
      <div className="bg-[var(--error-bg)] border border-[var(--error-border)] shadow-[0_8px_30px_rgba(0,0,0,0.1)] p-4 flex items-start gap-3 max-w-[360px]">
        <div className="text-[var(--error-title)] shrink-0 mt-0.5">
          <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" viewBox="0 0 24 24">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
        </div>
        <div className="flex-1">
          <h4 className="text-[var(--error-title)] text-sm font-bold mb-1">Koneksi Bermasalah</h4>
          <p className="text-[var(--error-text)] text-[13px] leading-snug font-medium">{error}</p>
        </div>
        <button
          className="text-[var(--error-title)] opacity-60 cursor-pointer p-1 text-base transition-opacity duration-200 hover:opacity-100"
          onClick={() => setError(null)}
        >
          ✕
        </button>
      </div>
    </div>
  );
}
