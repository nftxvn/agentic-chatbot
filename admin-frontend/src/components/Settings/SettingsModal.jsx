import { useState, useEffect, useRef } from 'react'
import { useTheme } from '../../context/ThemeContext'
import { authApi } from '../../api/auth'
import { addAppNotification } from '../../utils/notifications'
import { SlidingTabs } from '../UI/SlidingTabs'

const SETTINGS_TABS = [
  { id: 'profile', label: 'Profil Akun' },
  { id: 'security', label: 'Keamanan Sandi' },
  { id: 'preferences', label: 'Preferensi Sistem' },
]

export default function SettingsModal({
  isOpen,
  onClose,
  initialTab = 'profile',
  user = null,
}) {
  const { theme, toggleTheme } = useTheme()
  const [activeTab, setActiveTab] = useState(initialTab)
  const modalRef = useRef(null)

  // Password Form State
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    new_password_confirmation: '',
  })
  const [showCurrentPass, setShowCurrentPass] = useState(false)
  const [showNewPass, setShowNewPass] = useState(false)
  const [showConfirmPass, setShowConfirmPass] = useState(false)
  const [changingPass, setChangingPass] = useState(false)
  const [passError, setPassError] = useState('')
  const [passSuccess, setPassSuccess] = useState('')

  // Sync initialTab when modal opens
  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab)
      setPassError('')
      setPassSuccess('')
      setPasswordForm({
        current_password: '',
        new_password: '',
        new_password_confirmation: '',
      })
    }
  }, [isOpen, initialTab])

  // Escape key listener & Body scroll lock
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && !changingPass) {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    document.body.style.overflow = 'hidden'

    return () => {
      document.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = ''
    }
  }, [isOpen, changingPass, onClose])

  const handleChangePasswordSubmit = async (e) => {
    e.preventDefault()
    setPassError('')
    setPassSuccess('')

    if (passwordForm.new_password !== passwordForm.new_password_confirmation) {
      setPassError('Konfirmasi password baru tidak cocok.')
      return
    }

    if (passwordForm.new_password.length < 8) {
      setPassError('Password baru minimal 8 karakter.')
      return
    }

    setChangingPass(true)
    try {
      const res = await authApi.changePassword(
        passwordForm.current_password,
        passwordForm.new_password,
        passwordForm.new_password_confirmation
      )
      const successMessage = res.message || 'Password berhasil diperbarui.'
      setPassSuccess(successMessage)
      addAppNotification({
        title: 'Keamanan Akun',
        message: 'Password akun Anda berhasil diperbarui.',
        type: 'success',
      })
      setPasswordForm({
        current_password: '',
        new_password: '',
        new_password_confirmation: '',
      })
      setTimeout(() => {
        onClose()
        setPassSuccess('')
      }, 1400)
    } catch (err) {
      setPassError(
        err.response?.data?.message ||
          'Gagal mengubah password. Pastikan password saat ini benar.'
      )
    } finally {
      setChangingPass(false)
    }
  }

  if (!isOpen) return null

  const userInitial = user?.name ? user.name.charAt(0).toUpperCase() : 'A'

  return (
    <div
      className="fixed inset-0 bg-black/60 backdrop-blur-xs z-[100] flex items-center justify-center p-4 animate-fade-in"
      onClick={(e) => {
        if (e.target === e.currentTarget && !changingPass) onClose()
      }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
    >
      <div
        ref={modalRef}
        className="bg-[var(--bg-card)] border border-[var(--border-color)] w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-fade-in"
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-[var(--border-color)] flex justify-between items-center bg-[var(--bg-input)]">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-sky-500 flex items-center justify-center shrink-0">
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </div>
            <div>
              <h3 id="settings-modal-title" className="text-base font-bold text-[var(--text-primary)]">
                Pengaturan Akun & Sistem
              </h3>
              <p className="text-xs text-[var(--text-muted)]">
                Informasi profil dinas, keamanan, dan preferensi antarmuka.
              </p>
            </div>
          </div>
          <button
            type="button"
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 rounded-lg transition-colors cursor-pointer disabled:opacity-30 disabled:pointer-events-none"
            onClick={onClose}
            disabled={changingPass}
            title="Tutup"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Navigation Tabs in Modal with GSAP Fluid Slider */}
        <div className="px-6 pt-3 bg-[var(--bg-card)]">
          <SlidingTabs
            tabs={SETTINGS_TABS}
            activeTab={activeTab}
            onChange={setActiveTab}
            variant="underline"
          />
        </div>

        {/* Modal Body */}
        <div className="p-6">
          {/* ── TAB 1: PROFIL PENGGUNA ──────────────────────────── */}
          {activeTab === 'profile' && (
            <div key="tab-profile" className="animate-fade-in space-y-4">
              <div className="flex items-center gap-4 p-4 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]">
                <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 text-xl font-bold flex items-center justify-center shrink-0 shadow-md">
                  {userInitial}
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-bold text-[var(--text-primary)] truncate">
                      {user?.name || 'Administrator Diskominfotik'}
                    </h4>
                    <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-[var(--bg-card)] text-emerald-600 dark:text-emerald-400 border border-[var(--border-color)]">
                      Aktif
                    </span>
                  </div>
                  <p className="text-xs text-[var(--text-muted)] truncate">
                    {user?.email || 'admin@diskominfotik.go.id'}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                <div className="p-3.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                    Instansi Dinas
                  </span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    Diskominfotik Kota Banda Aceh
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                    Peran Akses
                  </span>
                  <span className="font-semibold text-[var(--text-primary)]">
                    Super Admin (Full RAG Hub)
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                    Status Sesi
                  </span>
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                    Terotentikasi Aman
                  </span>
                </div>
                <div className="p-3.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)]">
                  <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] block mb-1">
                    Hak Akses AI
                  </span>
                  <span className="font-semibold text-sky-600 dark:text-sky-400">
                    Vision OCR + LLM Inference
                  </span>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors cursor-pointer"
                >
                  Tutup
                </button>
              </div>
            </div>
          )}

          {/* ── TAB 2: KEAMANAN & GANTI SANDI ───────────────────── */}
          {activeTab === 'security' && (
            <form key="tab-security" onSubmit={handleChangePasswordSubmit} className="animate-fade-in space-y-4">
              {passSuccess && (
                <div className="p-3 bg-[var(--bg-input)] border border-[var(--border-color)] text-emerald-500 rounded-xl text-xs font-semibold flex items-center gap-2">
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  <span>{passSuccess}</span>
                </div>
              )}

              {passError && (
                <div className="p-3 bg-[var(--bg-input)] border border-[var(--border-color)] text-red-500 rounded-xl text-xs font-semibold flex items-center gap-2">
                  <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                  </svg>
                  <span>{passError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                  Password Saat Ini
                </label>
                <div className="relative">
                  <input
                    type={showCurrentPass ? 'text' : 'password'}
                    required
                    value={passwordForm.current_password}
                    onChange={(e) => {
                      setPassError('')
                      setPasswordForm({ ...passwordForm, current_password: e.target.value })
                    }}
                    placeholder="Masukkan password lama"
                    disabled={changingPass}
                    className="w-full pr-10 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPass(!showCurrentPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors cursor-pointer"
                    title={showCurrentPass ? 'Sembunyikan Password' : 'Lihat Password'}
                  >
                    {showCurrentPass ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                  Password Baru
                </label>
                <div className="relative">
                  <input
                    type={showNewPass ? 'text' : 'password'}
                    required
                    minLength={8}
                    value={passwordForm.new_password}
                    onChange={(e) => {
                      setPassError('')
                      setPasswordForm({ ...passwordForm, new_password: e.target.value })
                    }}
                    placeholder="Minimal 8 karakter"
                    disabled={changingPass}
                    className="w-full pr-10 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPass(!showNewPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors cursor-pointer"
                    title={showNewPass ? 'Sembunyikan Password' : 'Lihat Password'}
                  >
                    {showNewPass ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">
                  Konfirmasi Password Baru
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPass ? 'text' : 'password'}
                    required
                    minLength={8}
                    value={passwordForm.new_password_confirmation}
                    onChange={(e) => {
                      setPassError('')
                      setPasswordForm({ ...passwordForm, new_password_confirmation: e.target.value })
                    }}
                    placeholder="Ketik ulang password baru"
                    disabled={changingPass}
                    className="w-full pr-10 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPass(!showConfirmPass)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors cursor-pointer"
                    title={showConfirmPass ? 'Sembunyikan Password' : 'Lihat Password'}
                  >
                    {showConfirmPass ? (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <div className="flex justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors cursor-pointer"
                  onClick={onClose}
                  disabled={changingPass}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className={`px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white shadow-md shadow-sky-500/25 transition-all hover:scale-[1.01] cursor-pointer flex items-center justify-center gap-2 ${
                    changingPass ? 'cursor-wait opacity-90' : 'disabled:opacity-50'
                  }`}
                  disabled={
                    changingPass ||
                    !passwordForm.current_password ||
                    !passwordForm.new_password ||
                    !passwordForm.new_password_confirmation
                  }
                >
                  {changingPass ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Menyimpan...</span>
                    </>
                  ) : (
                    <span>Simpan Password Baru</span>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* ── TAB 3: PREFERENSI TEMA & SISTEM ─────────────────── */}
          {activeTab === 'preferences' && (
            <div key="tab-preferences" className="animate-fade-in space-y-4 text-xs">
              <div className="p-4 rounded-xl bg-[var(--bg-input)]/50 border border-[var(--border-color)] space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-bold text-[var(--text-primary)] block">
                      Tema Tampilan Antarmuka
                    </span>
                    <p className="text-xs text-[var(--text-muted)] mt-0.5">
                      Pilih mode tampilan yang nyaman untuk operasional portal.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={toggleTheme}
                    className="px-3.5 py-2 rounded-xl font-bold text-xs bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-all cursor-pointer flex items-center gap-2 shadow-xs"
                  >
                    <svg className="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      {theme === 'dark' ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M21.752 15.002A9.718 9.718 0 0118 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 003 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 009.002-5.998z" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z" />
                      )}
                    </svg>
                    <span>{theme === 'dark' ? 'Mode Gelap' : 'Mode Terang'}</span>
                  </button>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-[var(--bg-input)]/50 border border-[var(--border-color)] space-y-2.5">
                <span className="font-bold text-[var(--text-primary)] block">
                  Spesifikasi Engine RAG & AI Hub
                </span>
                <div className="space-y-1.5 font-mono text-xs text-[var(--text-secondary)]">
                  <div className="flex justify-between py-1 border-b border-[var(--border-color)]/60">
                    <span className="text-[var(--text-muted)]">Versi Portal:</span>
                    <span className="text-sky-600 dark:text-sky-400 font-bold">v2.4.0 (Enterprise)</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[var(--border-color)]/60">
                    <span className="text-[var(--text-muted)]">Vector Engine:</span>
                    <span className="font-medium text-[var(--text-primary)]">ChromaDB + Hybrid BM25</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-[var(--border-color)]/60">
                    <span className="text-[var(--text-muted)]">Vision OCR:</span>
                    <span className="font-medium text-[var(--text-primary)]">Qwen2-VL / Llama-Vision</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-[var(--text-muted)]">Integrasi Gateway:</span>
                    <span className="font-medium text-emerald-600 dark:text-emerald-400">Public API + WhatsApp Cloud</span>
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-bold bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors cursor-pointer"
                >
                  Selesai
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
