import React, { useEffect } from 'react';
import ReactDOM from 'react-dom';

const ConfirmModal = ({ isOpen, title, message, onConfirm, onCancel, confirmText = 'Ya', cancelText = 'Batal', isDanger = true }) => {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return ReactDOM.createPortal(
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[9999] flex items-center justify-center p-4 transition-all duration-300">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] max-w-md w-full rounded-2xl shadow-2xl overflow-hidden transform transition-all duration-300 scale-100 animate-fadeIn">
        {/* Header */}
        <div className="px-6 py-5 border-b border-[var(--border-color)] flex justify-between items-center bg-black/5 dark:bg-white/5">
          <div className="flex items-center gap-3">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${isDanger ? 'bg-red-500/10 text-red-500' : 'bg-sky-500/10 text-sky-500'}`}>
              {isDanger ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              )}
            </div>
            <h3 className="text-lg font-bold text-[var(--text-primary)] m-0">{title}</h3>
          </div>
          <button
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 rounded-lg transition-colors"
            onClick={onCancel}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          <p className="text-sm text-[var(--text-secondary)] leading-relaxed m-0">{message}</p>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-[var(--border-color)] bg-black/5 dark:bg-white/5 flex justify-end gap-3">
          <button
            className="px-4 py-2.5 rounded-xl text-[var(--text-primary)] text-sm font-semibold border border-[var(--border-color)] bg-[var(--bg-input)] hover:bg-[var(--border-color)] transition-all duration-200"
            onClick={onCancel}
          >
            {cancelText}
          </button>
          <button
            className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 shadow-md hover:shadow-lg ${
              isDanger
                ? 'bg-red-600 hover:bg-red-700 text-white'
                : 'bg-sky-600 hover:bg-sky-700 text-white'
            }`}
            onClick={onConfirm}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>,
    document.body
  );
};

export default ConfirmModal;
