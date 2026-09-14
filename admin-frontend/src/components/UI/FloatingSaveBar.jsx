import React, { useEffect, useRef } from 'react'
import gsap from 'gsap'

/**
 * FloatingSaveBar - Unified Floating Dirty-State Action Bar
 * Displays a smooth GSAP-animated floating bar when unsaved changes exist in forms/settings.
 */
export function FloatingSaveBar({
  show = false,
  onSave,
  onDiscard,
  saving = false,
  message = 'Perubahan belum disimpan',
  saveText = 'Simpan Perubahan',
  discardText = 'Batalkan',
  className = '',
}) {
  const barRef = useRef(null)

  useEffect(() => {
    if (!barRef.current) return
    if (show) {
      gsap.killTweensOf(barRef.current)
      gsap.fromTo(
        barRef.current,
        { y: 35, opacity: 0, scale: 0.97 },
        { y: 0, opacity: 1, scale: 1, duration: 0.35, ease: 'power3.out' }
      )
    }
  }, [show])

  if (!show) return null

  return (
    <div
      ref={barRef}
      className={`fixed bottom-6 inset-x-4 sm:inset-x-0 mx-auto max-w-lg px-4 py-3 rounded-xl bg-[var(--bg-card)]/95 backdrop-blur-md border border-[var(--border-color)] shadow-xl z-50 flex items-center justify-between gap-4 animate-fade-in ${className}`}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center">
        <span className="text-xs font-semibold text-[var(--text-primary)]">
          {message}
        </span>
      </div>

      <div className="flex items-center gap-2">
        {onDiscard && (
          <button
            type="button"
            onClick={onDiscard}
            disabled={saving}
            className="px-3 py-1.5 rounded-lg text-xs font-medium text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-input)] transition-colors cursor-pointer disabled:opacity-50"
          >
            {discardText}
          </button>
        )}
        <button
          type="button"
          onClick={onSave}
          disabled={saving}
          className="px-4 py-1.5 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 transition-all hover:scale-[1.02] flex items-center gap-1.5 cursor-pointer disabled:opacity-50 shadow-md shadow-sky-500/25"
        >
          {saving ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin shrink-0" />
              <span>Menyimpan...</span>
            </>
          ) : (
            <span>{saveText}</span>
          )}
        </button>
      </div>
    </div>
  )
}

export default FloatingSaveBar
