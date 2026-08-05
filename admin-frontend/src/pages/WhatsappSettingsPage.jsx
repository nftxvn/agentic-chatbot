import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import gsap from 'gsap'
import { getWhatsappSettings, updateWhatsappSettings } from '../api/settings'
import { addAppNotification } from '../utils/notifications'

export default function WhatsappSettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showToken, setShowToken] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)

  const headerRef = useRef(null)
  const formCardRef = useRef(null)

  const [form, setForm] = useState({
    wa_status: false,
    wa_api_url: '',
    wa_token: '',
    wa_phone_number: ''
  })

  useEffect(() => {
    fetchSettings()
  }, [])

  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -20 },
        { opacity: 1, x: 0, duration: 0.6, stagger: 0.1, ease: 'power2.out', clearProps: 'all' }
      )
    }
    if (!loading && formCardRef.current) {
      gsap.fromTo(
        formCardRef.current,
        { opacity: 0, scale: 0.98 },
        { opacity: 1, scale: 1, duration: 0.4, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  async function fetchSettings() {
    const startTime = Date.now()
    try {
      setLoading(true)
      const data = await getWhatsappSettings()
      setForm({
        wa_status: data.wa_status,
        wa_api_url: data.wa_api_url || '',
        wa_token: data.wa_token || '',
        wa_phone_number: data.wa_phone_number || ''
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal mengambil pengaturan. Pastikan server berjalan.' })
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => setLoading(false), Math.max(0, 350 - elapsed))
    }
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }))
    setStatusMsg(null)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setStatusMsg(null)
    try {
      const res = await updateWhatsappSettings(form)
      setStatusMsg({ type: 'success', text: res.message || 'Pengaturan berhasil disimpan!' })
      await fetchSettings()
      addAppNotification({
        title: 'Pengaturan API',
        message: 'Anda baru saja memperbarui Pengaturan API WhatsApp',
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal menyimpan pengaturan.' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="p-4 sm:p-5 max-w-5xl mx-auto space-y-4 sm:space-y-5">
        <div className="p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm space-y-2">
          <div className="skeleton h-6 w-64 rounded-md" />
          <div className="skeleton h-4 w-96 rounded-md" />
        </div>
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 sm:p-6 shadow-sm space-y-5">
          <div className="flex justify-between items-center pb-4 border-b border-[var(--border-color)]">
            <div className="space-y-1.5">
              <div className="skeleton h-5 w-48 rounded-md" />
              <div className="skeleton h-4 w-80 rounded-md" />
            </div>
            <div className="skeleton w-12 h-6 rounded-full" />
          </div>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="space-y-1.5">
              <div className="skeleton h-4 w-40 rounded-md" />
              <div className="skeleton h-10 w-full rounded-lg" />
            </div>
          ))}
          <div className="skeleton h-11 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-5 max-w-5xl mx-auto space-y-4 sm:space-y-5">
      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div ref={headerRef} className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight">
            Pengaturan API WhatsApp
          </h1>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)] font-medium">
            Konfigurasi endpoint, akses token, dan kredensial WhatsApp Business Cloud API.
          </p>
        </div>
      </div>

      {/* Settings Card */}
      <div
        ref={formCardRef}
        className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 sm:p-6 shadow-sm"
      >
        <form onSubmit={handleSubmit} className="space-y-4 sm:space-y-5">
          {/* Status Toggle Row */}
          <div className="flex items-center justify-between pb-4 border-b border-[var(--border-color)]">
            <div className="flex flex-col">
              <span className="text-sm font-bold text-[var(--text-primary)]">Aktifkan Chatbot WhatsApp</span>
              <span className="text-sm text-[var(--text-secondary)] mt-0.5">
                Jika dimatikan, sistem tidak akan merespon pesan WhatsApp masuk secara otomatis.
              </span>
            </div>
            <label className="switch">
              <input
                type="checkbox"
                name="wa_status"
                checked={form.wa_status}
                onChange={handleChange}
              />
              <span className="slider" />
            </label>
          </div>

          {/* API Endpoint */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
              WhatsApp API URL Endpoint
            </label>
            <input
              type="url"
              name="wa_api_url"
              className="w-full"
              value={form.wa_api_url}
              onChange={handleChange}
              placeholder="https://graph.facebook.com/v17.0/PHONE_NUMBER_ID/messages"
              required={form.wa_status}
            />
          </div>

          {/* Token */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
              API Bearer Access Token
            </label>
            <div className="relative">
              <input
                type={showToken ? 'text' : 'password'}
                name="wa_token"
                className="w-full pr-12 font-mono text-xs"
                value={form.wa_token}
                onChange={handleChange}
                placeholder="EAAI..."
                required={form.wa_status && !form.wa_token.includes('••••')}
              />
              <button
                type="button"
                className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 transition-colors"
                onClick={() => setShowToken(!showToken)}
                title={showToken ? 'Sembunyikan Token' : 'Lihat Token'}
              >
                {showToken ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>

          {/* Sender Phone Number */}
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">
              Nomor WhatsApp Pengirim (Opsional)
            </label>
            <input
              type="text"
              name="wa_phone_number"
              className="w-full"
              value={form.wa_phone_number}
              onChange={handleChange}
              placeholder="Misal: +6281234567890"
            />
          </div>

          {/* Action button */}
          <button
            type="submit"
            className={`w-full py-3.5 px-4 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-sm shadow-md shadow-sky-600/20 transition-all relative overflow-hidden flex items-center justify-center gap-2 ${
              saving ? 'btn-light-sweep cursor-wait opacity-95' : 'disabled:opacity-50 hover:scale-[1.01]'
            }`}
            disabled={saving}
          >
            {saving ? (
              <>
                <span className="spin w-4 h-4 border-2 border-white/30 border-t-white rounded-full shrink-0" />
                <span>Menyimpan & Memproses...</span>
              </>
            ) : (
              'Simpan Pengaturan WhatsApp'
            )}
          </button>

          {/* Alert Message */}
          {statusMsg && (
            <div
              className={`p-4 rounded-xl text-sm font-medium border ${
                statusMsg.type === 'success'
                  ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                  : 'bg-red-500/10 text-red-500 border-red-500/20'
              }`}
            >
              {statusMsg.text}
            </div>
          )}

          {loading && (
            <div className="space-y-3 pt-2">
              <div className="skeleton h-10 w-full" />
              <div className="skeleton h-10 w-full" />
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
