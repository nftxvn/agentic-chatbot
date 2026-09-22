import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import gsap from 'gsap'
import { getWhatsappSettings, updateWhatsappSettings, testWhatsappConnection } from '../api/settings'
import { addAppNotification } from '../utils/notifications'
import { FloatingSaveBar } from '../components/UI/FloatingSaveBar'

export default function WhatsappSettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showToken, setShowToken] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)

  // Test message state
  const [testPhone, setTestPhone] = useState('')
  const [testMsgText, setTestMsgText] = useState('Halo! Ini adalah pesan uji coba koneksi gateway WhatsApp resmi Layanan Informasi Diskominfotik Kota Banda Aceh.')
  const [testingSend, setTestingSend] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [copiedWebhook, setCopiedWebhook] = useState(false)
  const [copiedVerifyToken, setCopiedVerifyToken] = useState(false)

  const headerRef = useRef(null)
  const formCardRef = useRef(null)

  const [initialForm, setInitialForm] = useState(null)
  const [form, setForm] = useState({
    wa_status: false,
    wa_api_url: '',
    wa_token: '',
    wa_phone_number: '',
    wa_webhook_verify_token: 'diskominfo_wa_rag_token',
    webhook_url: '',
  })
  const isDirty = Boolean(
    initialForm && JSON.stringify(form) !== JSON.stringify(initialForm)
  )

  useEffect(() => {
    fetchSettings()
  }, [])

  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  async function fetchSettings() {
    const startTime = Date.now()
    try {
      setLoading(true)
      const data = await getWhatsappSettings()
      const loadedData = {
        wa_status: data.wa_status,
        wa_api_url: data.wa_api_url || '',
        wa_token: data.wa_token || '',
        wa_phone_number: data.wa_phone_number || '',
        wa_webhook_verify_token: data.wa_webhook_verify_token || 'diskominfo_wa_rag_token',
        webhook_url: data.webhook_url || `${window.location.origin}/api/v1/webhook/whatsapp`,
      }
      setForm(loadedData)
      setInitialForm(loadedData)
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal mengambil pengaturan WhatsApp dari server.' })
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => setLoading(false), Math.max(0, 200 - elapsed))
    }
  }

  function handleChange(e) {
    const { name, value, type, checked } = e.target
    setForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const handleDiscard = () => {
    if (initialForm) {
      setForm(initialForm)
    }
  }

  async function handleSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    setSaving(true)
    setStatusMsg(null)
    try {
      const res = await updateWhatsappSettings(form)
      setInitialForm(form)
      setStatusMsg({ type: 'success', text: res.message || 'Pengaturan WhatsApp berhasil disimpan.' })
      addAppNotification({
        title: 'Integrasi WhatsApp',
        message: 'Konfigurasi kredensial gateway WhatsApp telah diperbarui.',
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal menyimpan pengaturan WhatsApp.' })
    } finally {
      setSaving(false)
    }
  }

  async function handleTestSend(e) {
    e.preventDefault()
    if (!testPhone || !testPhone.trim()) {
      setTestResult({
        type: 'error',
        text: 'Nomor WhatsApp tujuan uji wajib diisi.',
      })
      return
    }

    setTestingSend(true)
    setTestResult(null)
    try {
      const res = await testWhatsappConnection({
        target_phone: testPhone.trim(),
        test_message: testMsgText.trim(),
      })
      setTestResult({
        type: res.success ? 'success' : 'error',
        text: res.message,
      })
    } catch (err) {
      console.error(err)
      setTestResult({
        type: 'error',
        text: err.response?.data?.message || 'Gagal mengirim pesan uji coba ke gateway.',
      })
    } finally {
      setTestingSend(false)
    }
  }

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    if (type === 'webhook') {
      setCopiedWebhook(true)
      setTimeout(() => setCopiedWebhook(false), 2000)
    } else {
      setCopiedVerifyToken(true)
      setTimeout(() => setCopiedVerifyToken(false), 2000)
    }
  }

  if (loading) {
    return (
      <div className="p-4 sm:p-5 max-w-6xl mx-auto space-y-4">
        <div className="p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-2">
          <div className="skeleton h-6 w-64 rounded-md" />
          <div className="skeleton h-4 w-96 rounded-md" />
        </div>
        <div className="p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-3">
          <div className="skeleton h-10 w-full rounded-lg" />
          <div className="skeleton h-64 w-full rounded-lg" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-5 max-w-6xl mx-auto space-y-5 pb-20">
      {/* ── HEADER BANNER ───────────────────────────────────────── */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs">
        <div ref={headerRef} className="space-y-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl sm:text-2xl font-bold text-[var(--text-primary)] tracking-tight">
              Integrasi Gateway WhatsApp
            </h1>
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold border ${
              form.wa_status
                ? 'bg-[var(--bg-card)] text-emerald-600 dark:text-emerald-400 border-[var(--border-color)]'
                : 'bg-[var(--bg-input)] text-[var(--text-muted)] border-[var(--border-color)]'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${form.wa_status ? 'bg-emerald-500' : 'bg-zinc-400'}`} />
              <span>{form.wa_status ? 'Layanan Bot Aktif' : 'Layanan Bot Nonaktif'}</span>
            </div>
          </div>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)]">
            Konfigurasi kredensial gateway, token akses webhook, dan endpoint balasan otomatis WhatsApp resmi Diskominfotik Kota Banda Aceh.
          </p>
        </div>
      </div>

      {/* ── NOTIFICATION TOAST ─────────────────────────────────── */}
      {statusMsg && (
        <div
          className={`px-4 py-3 rounded-lg text-xs font-medium flex items-center justify-between transition-all border ${
            statusMsg.type === 'success'
              ? 'bg-[var(--bg-input)] text-emerald-600 dark:text-emerald-400 border-[var(--border-color)]'
              : 'bg-[var(--bg-input)] text-rose-600 dark:text-rose-400 border-[var(--border-color)]'
          }`}
        >
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {statusMsg.type === 'success' ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              )}
            </svg>
            <span>{statusMsg.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setStatusMsg(null)}
            className="text-inherit opacity-60 hover:opacity-100 p-1 cursor-pointer"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* ── MAIN GRID: CONFIGURATION (LEFT) & WEBHOOK/DIAGNOSTIC (RIGHT) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* ── LEFT COLUMN: CREDENTIAL SETTINGS (7/12) ───────────── */}
        <div
          ref={formCardRef}
          className="lg:col-span-7 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-5"
        >
          <div className="border-b border-[var(--border-color)] pb-3">
            <h2 className="text-sm font-bold text-[var(--text-primary)]">
              Kredensial Gateway & Akun Pengirim
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Pengaturan akun WhatsApp Business API atau WhatsApp Gateway resmi.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Status Toggle Row */}
            <div className="flex items-center justify-between p-3.5 rounded-lg bg-[var(--bg-input)]/50 border border-[var(--border-color)]">
              <div className="space-y-0.5">
                <span className="text-xs font-bold text-[var(--text-primary)] block">
                  Status Chatbot WhatsApp
                </span>
                <span className="text-xs text-[var(--text-muted)] block">
                  Bila dimatikan, pesan masuk tidak akan dibalas otomatis oleh mesin AI.
                </span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  name="wa_status"
                  checked={form.wa_status}
                  onChange={handleChange}
                  className="sr-only peer"
                />
                <div className="w-10 h-5 bg-zinc-300 dark:bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-sky-600"></div>
              </label>
            </div>

            {/* API Endpoint URL */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-[var(--text-primary)]">
                URL Endpoint API Gateway Pengirim
              </label>
              <input
                type="url"
                name="wa_api_url"
                value={form.wa_api_url}
                onChange={handleChange}
                placeholder="Contoh: https://graph.facebook.com/v19.0/PHONE_NUMBER_ID/messages atau https://api.fonnte.com/send"
                className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
              />
              <p className="text-xs text-[var(--text-muted)]">
                Mendukung Meta Cloud API, Fonnte, Wablas, atau gateway HTTP POST standar.
              </p>
            </div>

            {/* Token */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-[var(--text-primary)]">
                Bearer Access Token Gateway
              </label>
              <div className="relative">
                <input
                  type={showToken ? 'text' : 'password'}
                  name="wa_token"
                  value={form.wa_token}
                  onChange={handleChange}
                  placeholder="Masukkan token akses API WhatsApp"
                  className="w-full px-3.5 py-2 pr-10 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                />
                <button
                  type="button"
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors cursor-pointer"
                  title={showToken ? 'Sembunyikan' : 'Tampilkan'}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {showToken ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178zM15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    )}
                  </svg>
                </button>
              </div>
            </div>

            {/* Sender Phone Number */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-[var(--text-primary)]">
                Nomor WhatsApp Dinas Pengirim (Opsional)
              </label>
              <input
                type="text"
                name="wa_phone_number"
                value={form.wa_phone_number}
                onChange={handleChange}
                placeholder="Contoh: 6281234567890"
                className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
              />
            </div>

            {/* Webhook Verify Token */}
            <div className="space-y-1.5">
              <label className="block text-xs font-bold text-[var(--text-primary)]">
                Webhook Verify Token (Meta Cloud API)
              </label>
              <input
                type="text"
                name="wa_webhook_verify_token"
                value={form.wa_webhook_verify_token}
                onChange={handleChange}
                placeholder="diskominfo_wa_rag_token"
                className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
              />
            </div>

            {/* Submit Button */}
            <div className="pt-2">
              <button
                type="submit"
                disabled={saving}
                className="w-full py-2.5 px-4 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white text-xs font-semibold transition-colors cursor-pointer flex items-center justify-center gap-2 shadow-xs"
              >
                {saving ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Menyimpan Pengaturan...</span>
                  </>
                ) : (
                  <span>Simpan Perubahan Kredensial</span>
                )}
              </button>
            </div>
          </form>
        </div>

        {/* ── RIGHT COLUMN: WEBHOOK INFO & LIVE TEST (5/12) ───────── */}
        <div className="lg:col-span-5 space-y-5">
          {/* Webhook Configuration Card */}
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-3.5">
            <div className="border-b border-[var(--border-color)] pb-3">
              <h2 className="text-sm font-bold text-[var(--text-primary)]">
                Endpoint Webhook Masuk
              </h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Salin endpoint ini ke dashboard Meta WhatsApp Cloud API atau WhatsApp Gateway Anda.
              </p>
            </div>

            <div className="space-y-3 text-xs">
              <div className="space-y-1">
                <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">
                  Callback Webhook URL
                </span>
                <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] break-all flex items-center justify-between gap-2">
                  <span>{form.webhook_url || `${window.location.origin}/api/v1/webhook/whatsapp`}</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(form.webhook_url || `${window.location.origin}/api/v1/webhook/whatsapp`, 'webhook')}
                    className="shrink-0 p-1 text-[var(--text-muted)] hover:text-sky-500 transition-colors cursor-pointer"
                    title="Salin Webhook URL"
                  >
                    {copiedWebhook ? (
                      <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              <div className="space-y-1">
                <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">
                  Verify Token
                </span>
                <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] flex items-center justify-between gap-2">
                  <span>{form.wa_webhook_verify_token}</span>
                  <button
                    type="button"
                    onClick={() => handleCopy(form.wa_webhook_verify_token, 'verify')}
                    className="shrink-0 p-1 text-[var(--text-muted)] hover:text-sky-500 transition-colors cursor-pointer"
                    title="Salin Token Verifikasi"
                  >
                    {copiedVerifyToken ? (
                      <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    ) : (
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Test WhatsApp Delivery Diagnostic Card */}
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-3.5">
            <div className="border-b border-[var(--border-color)] pb-3">
              <h2 className="text-sm font-bold text-[var(--text-primary)]">
                Uji Coba Pengiriman Gateway
              </h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Kirim pesan uji coba langsung ke nomor WhatsApp untuk memverifikasi kredensial.
              </p>
            </div>

            <form noValidate onSubmit={handleTestSend} className="space-y-3 text-xs">
              <div className="space-y-1">
                <label className="text-xs font-bold text-[var(--text-primary)] block">
                  Nomor WhatsApp Tujuan Uji
                </label>
                <input
                  type="text"
                  value={testPhone}
                  onChange={(e) => setTestPhone(e.target.value)}
                  placeholder="Contoh: 6281234567890"
                  className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-bold text-[var(--text-primary)] block">
                  Isi Pesan Uji Coba
                </label>
                <textarea
                  value={testMsgText}
                  onChange={(e) => setTestMsgText(e.target.value)}
                  rows={2}
                  className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={testingSend || !testPhone.trim()}
                className="w-full py-2 px-3 rounded-lg text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {testingSend ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-[var(--border-color)] border-t-sky-500 rounded-full animate-spin" />
                    <span>Mengirim Pesan Uji...</span>
                  </>
                ) : (
                  <span>Kirim Pesan Uji Coba</span>
                )}
              </button>

              {testResult && (
                <div
                  className={`p-3 rounded-lg text-xs border ${
                    testResult.type === 'success'
                      ? 'bg-[var(--bg-input)] text-emerald-600 dark:text-emerald-400 border-[var(--border-color)]'
                      : 'bg-[var(--bg-input)] text-rose-600 dark:text-rose-400 border-[var(--border-color)]'
                  }`}
                >
                  <p className="font-semibold">{testResult.text}</p>
                </div>
              )}
            </form>
          </div>
        </div>
      </div>

      {/* Floating Save Bar for WhatsApp settings dirty state */}
      <FloatingSaveBar
        show={isDirty}
        onSave={handleSubmit}
        onDiscard={handleDiscard}
        saving={saving}
        message="Perubahan konfigurasi WhatsApp belum disimpan"
      />
    </div>
  )
}
