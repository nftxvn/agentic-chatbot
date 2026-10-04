import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import ReactDOM from 'react-dom'
import { useSearchParams } from 'react-router-dom'
import gsap from 'gsap'
import { apiKeysApi } from '../api/apiKeys'
import { 
  getWhatsappSettings, 
  updateWhatsappSettings, 
  testWhatsappConnection,
  getTelegramSettings,
  updateTelegramSettings,
  testTelegramConnection,
  setTelegramWebhook
} from '../api/settings'
import ConfirmModal from '../components/ConfirmModal'
import { addAppNotification } from '../utils/notifications'
import { SlidingTabs } from '../components/UI/SlidingTabs'
import { FloatingSaveBar } from '../components/UI/FloatingSaveBar'
import { InfoTooltip } from '../components/UI/InfoTooltip'

export default function IntegrationsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const tabParam = searchParams.get('tab')
  const validTabs = ['apikeys', 'whatsapp', 'telegram', 'docs']
  const activeTab = validTabs.includes(tabParam) ? tabParam : 'apikeys'

  const setActiveTab = (newTab) => {
    setSearchParams({ tab: newTab }, { replace: true })
  }

  const [loading, setLoading] = useState(true)
  const [statusMsg, setStatusMsg] = useState(null)

  // ── STATE: API KEYS ──────────────────────────────────────────
  const [keys, setKeys] = useState([])
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false)
  const [keyName, setKeyName] = useState('')
  const [creatingKey, setCreatingKey] = useState(false)
  const [newlyCreatedKey, setNewlyCreatedKey] = useState(null)
  const [copiedKey, setCopiedKey] = useState(false)
  const [deleteKeyTarget, setDeleteKeyTarget] = useState(null)
  const [deletingKey, setDeletingKey] = useState(false)
  const [webhookTarget, setWebhookTarget] = useState(null)
  const [webhookForm, setWebhookForm] = useState({ webhook_url: '', webhook_enabled: false })
  const [savingWebhook, setSavingWebhook] = useState(false)
  const [rotatingWebhookSecret, setRotatingWebhookSecret] = useState(false)
  const [webhookSecretOnce, setWebhookSecretOnce] = useState('')
  const [webhookDeliveries, setWebhookDeliveries] = useState([])

  // ── STATE: WHATSAPP SETTINGS ─────────────────────────────────
  const [initialWaForm, setInitialWaForm] = useState(null)
  const [waForm, setWaForm] = useState({
    wa_status: false,
    wa_api_url: '',
    wa_token: '',
    wa_phone_number: '',
    wa_webhook_verify_token: 'diskominfo_wa_rag_token',
    webhook_url: '',
  })
  const isWaDirty = Boolean(
    initialWaForm && JSON.stringify(waForm) !== JSON.stringify(initialWaForm)
  )
  const [savingWa, setSavingWa] = useState(false)
  const [showWaToken, setShowWaToken] = useState(false)
  const [testPhone, setTestPhone] = useState('')
  const [testMsgText, setTestMsgText] = useState('Halo! Ini adalah pesan uji coba koneksi gateway WhatsApp resmi Layanan Informasi Diskominfotik Kota Banda Aceh.')
  const [testingSend, setTestingSend] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [copiedWebhook, setCopiedWebhook] = useState(false)
  const [copiedVerifyToken, setCopiedVerifyToken] = useState(false)

  // ── STATE: TELEGRAM SETTINGS ─────────────────────────────────
  const [initialTgForm, setInitialTgForm] = useState(null)
  const [tgForm, setTgForm] = useState({
    telegram_status: false,
    telegram_bot_token: '',
    telegram_bot_username: '',
    webhook_url: '',
  })
  const isTgDirty = Boolean(
    initialTgForm && JSON.stringify(tgForm) !== JSON.stringify(initialTgForm)
  )
  const [savingTg, setSavingTg] = useState(false)
  const [showTgToken, setShowTgToken] = useState(false)
  const [tgTestChatId, setTgTestChatId] = useState('')
  const [tgTestMsg, setTgTestMsg] = useState('Halo! Ini adalah pesan uji coba koneksi Telegram Bot resmi Layanan Informasi Diskominfotik Kota Banda Aceh.')
  const [testingTgSend, setTestingTgSend] = useState(false)
  const [tgTestResult, setTgTestResult] = useState(null)
  const [copiedTgWebhook, setCopiedTgWebhook] = useState(false)
  const [registeringWebhook, setRegisteringWebhook] = useState(false)
  const [webhookResult, setWebhookResult] = useState(null)

  // ── STATE: CODE SNIPPET DOCS ─────────────────────────────────
  const [docLang, setDocLang] = useState('curl')
  const [copiedCode, setCopiedCode] = useState(false)

  const headerRef = useRef(null)

  useEffect(() => {
    fetchAllData()
  }, [])

  useLayoutEffect(() => {
    if (headerRef.current?.children?.length) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  async function fetchAllData() {
    const startTime = Date.now()
    try {
      setLoading(true)
      const [keysRes, waRes, tgRes] = await Promise.all([
        apiKeysApi.list().catch(() => ({ data: [] })),
        getWhatsappSettings().catch(() => ({})),
        getTelegramSettings().catch(() => ({})),
      ])
      const keysList = Array.isArray(keysRes?.data) ? keysRes.data : Array.isArray(keysRes) ? keysRes : []
      setKeys(keysList)
      const loadedWa = {
        wa_status: waRes?.wa_status || false,
        wa_api_url: waRes?.wa_api_url || '',
        wa_token: waRes?.wa_token || '',
        wa_phone_number: waRes?.wa_phone_number || '',
        wa_webhook_verify_token: waRes?.wa_webhook_verify_token || 'diskominfo_wa_rag_token',
        webhook_url: waRes?.webhook_url || `${window.location.origin}/api/v1/webhook/whatsapp`,
      }
      setWaForm(loadedWa)
      setInitialWaForm(loadedWa)

      const loadedTg = {
        telegram_status: tgRes?.telegram_status || false,
        telegram_bot_token: tgRes?.telegram_bot_token || '',
        telegram_bot_username: tgRes?.telegram_bot_username || '',
        webhook_url: tgRes?.webhook_url || `${window.location.origin}/api/v1/webhook/telegram`,
      }
      setTgForm(loadedTg)
      setInitialTgForm(loadedTg)
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal memuat data integrasi dari server.' })
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => setLoading(false), Math.max(0, 200 - elapsed))
    }
  }

  // ── API KEY HANDLERS ─────────────────────────────────────────
  const handleCreateKey = async (e) => {
    e.preventDefault()
    if (!keyName || !keyName.trim()) {
      setStatusMsg({ type: 'error', text: 'Nama aplikasi / klien pemanggil wajib diisi.' })
      return
    }
    setCreatingKey(true)
    setStatusMsg(null)
    try {
      const res = await apiKeysApi.create(keyName.trim())
      setShowCreateKeyModal(false)
      setKeyName('')
      setNewlyCreatedKey(res.data)
      const listRes = await apiKeysApi.list()
      const listData = Array.isArray(listRes?.data) ? listRes.data : Array.isArray(listRes) ? listRes : []
      setKeys(listData)
      addAppNotification({
        title: 'Manajemen Kunci API',
        message: `Kunci API "${res.data.name}" berhasil dibuat.`,
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal membuat API Key baru.' })
    } finally {
      setCreatingKey(false)
    }
  }

  const handleToggleKey = async (key) => {
    try {
      await apiKeysApi.toggle(key.id)
      setKeys((prev) =>
        prev.map((k) => (k.id === key.id ? { ...k, is_active: !k.is_active } : k))
      )
      addAppNotification({
        title: 'Status Kunci API',
        message: `Kunci API "${key.name}" telah ${!key.is_active ? 'diaktifkan' : 'dinonaktifkan'}.`,
        type: 'info',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal mengubah status API Key.' })
    }
  }

  const handleDeleteKey = async () => {
    if (!deleteKeyTarget) return
    setDeletingKey(true)
    try {
      await apiKeysApi.delete(deleteKeyTarget.id)
      setKeys((prev) => prev.filter((k) => k.id !== deleteKeyTarget.id))
      setDeleteKeyTarget(null)
      addAppNotification({
        title: 'Kunci API Dicabut',
        message: `Kunci API "${deleteKeyTarget.name}" telah dihapus permanen.`,
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal menghapus API Key.' })
    } finally {
      setDeletingKey(false)
    }
  }

  const openWebhookSettings = async (key) => {
    setWebhookTarget(key)
    setWebhookForm({
      webhook_url: key.webhook_url || '',
      webhook_enabled: Boolean(key.webhook_enabled),
    })
    setWebhookSecretOnce('')
    setWebhookDeliveries([])
    try {
      const result = await apiKeysApi.webhookDeliveries(key.id)
      setWebhookDeliveries(Array.isArray(result?.data) ? result.data : [])
    } catch (err) {
      console.error(err)
    }
  }

  const handleSaveWebhook = async (e) => {
    e.preventDefault()
    if (!webhookTarget) return
    setSavingWebhook(true)
    try {
      const result = await apiKeysApi.updateWebhook(webhookTarget.id, webhookForm)
      setKeys((prev) => prev.map((key) => key.id === webhookTarget.id ? { ...key, ...result.data } : key))
      setWebhookTarget((prev) => prev ? { ...prev, ...result.data } : prev)
      setStatusMsg({ type: 'success', text: result.message || 'Konfigurasi webhook tersimpan.' })
      setWebhookTarget(null)
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal menyimpan webhook.' })
    } finally {
      setSavingWebhook(false)
    }
  }

  const handleRotateWebhookSecret = async () => {
    if (!webhookTarget) return
    setRotatingWebhookSecret(true)
    try {
      const result = await apiKeysApi.rotateWebhookSecret(webhookTarget.id)
      setWebhookSecretOnce(result.data.plain_secret)
      setKeys((prev) => prev.map((key) => key.id === webhookTarget.id ? { ...key, webhook_secret_configured: true } : key))
      setWebhookTarget((prev) => prev ? { ...prev, webhook_secret_configured: true } : prev)
    } catch (err) {
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal membuat secret webhook.' })
    } finally {
      setRotatingWebhookSecret(false)
    }
  }

  // ── WHATSAPP HANDLERS ────────────────────────────────────────
  function handleWaChange(e) {
    const { name, value, type, checked } = e.target
    setWaForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const handleDiscardWa = () => {
    if (initialWaForm) {
      setWaForm(initialWaForm)
    }
  }

  async function handleWaSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    setSavingWa(true)
    setStatusMsg(null)
    try {
      const res = await updateWhatsappSettings(waForm)
      setInitialWaForm(waForm)
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
      setSavingWa(false)
    }
  }

  async function handleTestSendWa(e) {
    e.preventDefault()
    if (!testPhone || !testPhone.trim()) {
      setTestResult({
        type: 'error',
        text: 'Nomor WhatsApp tujuan wajib diisi.',
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

  // ── TELEGRAM HANDLERS ────────────────────────────────────────
  function handleTgChange(e) {
    const { name, value, type, checked } = e.target
    setTgForm((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }))
  }

  const handleDiscardTg = () => {
    if (initialTgForm) {
      setTgForm(initialTgForm)
    }
  }

  async function handleTgSubmit(e) {
    if (e && e.preventDefault) e.preventDefault()
    setSavingTg(true)
    setStatusMsg(null)
    try {
      const res = await updateTelegramSettings(tgForm)
      const updatedTg = {
        ...tgForm,
        telegram_bot_username: res.telegram_bot_username || tgForm.telegram_bot_username,
      }
      setTgForm(updatedTg)
      setInitialTgForm(updatedTg)
      setStatusMsg({ type: 'success', text: res.message || 'Pengaturan Telegram berhasil disimpan.' })
      addAppNotification({
        title: 'Integrasi Telegram',
        message: 'Konfigurasi kredensial bot Telegram telah diperbarui.',
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal menyimpan pengaturan Telegram.' })
    } finally {
      setSavingTg(false)
    }
  }

  async function handleTestSendTg(e) {
    e.preventDefault()
    setTestingTgSend(true)
    setTgTestResult(null)
    try {
      const res = await testTelegramConnection({
        chat_id: tgTestChatId.trim(),
        test_message: tgTestMsg.trim(),
      })
      setTgTestResult({
        type: res.success ? 'success' : 'error',
        text: res.message,
      })
    } catch (err) {
      console.error(err)
      setTgTestResult({
        type: 'error',
        text: err.response?.data?.message || 'Gagal menguji koneksi Telegram.',
      })
    } finally {
      setTestingTgSend(false)
    }
  }

  async function handleAutoRegisterWebhook(action = 'set') {
    setRegisteringWebhook(true)
    setWebhookResult(null)
    try {
      const res = await setTelegramWebhook({
        webhook_url: tgForm.webhook_url,
        action: action,
      })
      setWebhookResult({
        type: res.success ? 'success' : 'error',
        text: res.message,
      })
      addAppNotification({
        title: 'Webhook Telegram',
        message: res.message,
        type: res.success ? 'system' : 'error',
      })
    } catch (err) {
      console.error(err)
      setWebhookResult({
        type: 'error',
        text: err.response?.data?.message || 'Gagal mendaftarkan webhook ke Telegram.',
      })
    } finally {
      setRegisteringWebhook(false)
    }
  }

  const handleCopy = (text, type) => {
    navigator.clipboard.writeText(text)
    if (type === 'webhook') {
      setCopiedWebhook(true)
      setTimeout(() => setCopiedWebhook(false), 2000)
    } else if (type === 'tg_webhook') {
      setCopiedTgWebhook(true)
      setTimeout(() => setCopiedTgWebhook(false), 2000)
    } else if (type === 'verify') {
      setCopiedVerifyToken(true)
      setTimeout(() => setCopiedVerifyToken(false), 2000)
    } else if (type === 'secret') {
      setCopiedKey(true)
      setTimeout(() => setCopiedKey(false), 2000)
    } else if (type === 'code') {
      setCopiedCode(true)
      setTimeout(() => setCopiedCode(false), 2000)
    }
  }

  const generateSnippet = () => {
    if (docLang === 'curl') {
      return `curl -X POST "${window.location.origin}/api/v1/chat" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk_live_YOUR_API_KEY" \\
  -d '{
    "session_id": "client-session-123",
    "query": "Bagaimana prosedur permohonan subdomain acehkota.go.id?"
  }'`
    }
    if (docLang === 'python') {
      return `import requests

url = "${window.location.origin}/api/v1/chat"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk_live_YOUR_API_KEY"
}
payload = {
    "session_id": "client-session-123",
    "query": "Bagaimana prosedur permohonan subdomain acehkota.go.id?"
}

response = requests.post(url, headers=headers, json=payload, timeout=30)
data = response.json()

print("Jawaban AI:", data.get("answer"))
print("Rujukan SOP:", data.get("sources"))`
    }
    return `// JavaScript (Fetch API)
const response = await fetch("${window.location.origin}/api/v1/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer sk_live_YOUR_API_KEY",
  },
  body: JSON.stringify({
    session_id: "client-session-123",
    query: "Bagaimana prosedur permohonan subdomain acehkota.go.id?",
  }),
});

const data = await response.json();
console.log("Jawaban:", data.answer);
console.log("Rujukan:", data.sources);`
  }

  if (loading) {
    return (
      <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5">
        <div className="p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm space-y-2">
          <div className="skeleton h-6 w-64 rounded-md" />
          <div className="skeleton h-4 w-96 rounded-md" />
        </div>
        <div className="p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm space-y-3">
          <div className="skeleton h-10 w-full rounded-xl" />
          <div className="skeleton h-64 w-full rounded-xl" />
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5 pb-20">
      {/* ── HEADER BANNER ───────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div ref={headerRef} className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
            <span>INTEGRASI & API GATEWAY</span>
            <InfoTooltip size="lg" content="Pusat manajemen pintu gerbang API, token autentikasi, serta webhook WhatsApp dan Telegram untuk menghubungkan sistem eksternal ke mesin RAG." />
          </h1>
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

      {/* ── SEGMENTED NAVIGATION TABS ───────────────────────────── */}
      <SlidingTabs
        tabs={[
          { id: 'apikeys', label: `Kunci Akses API (${keys.length})` },
          { id: 'whatsapp', label: 'Gateway WhatsApp' },
          { id: 'telegram', label: 'Gateway Telegram' },
          { id: 'docs', label: 'Panduan & Spesifikasi Endpoint' },
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
        variant="underline"
      />

      {/* ── TAB CONTENT CONTAINER (FADE ANIMATED) ─────────────── */}
      <div key={activeTab} className="animate-fade-in">
        {/* ── TAB 1: KUNCI AKSES API ──────────────────────────────── */}
        {activeTab === 'apikeys' && (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-4">
          <div className="p-4 sm:p-5 border-b border-[var(--border-color)] flex items-center justify-between flex-wrap gap-3">
            <div>
              <h2 className="text-sm font-bold text-[var(--text-primary)] flex items-center">
                <span>Daftar Kunci Akses API (Bearer Token)</span>
                <InfoTooltip content="Kunci otorisasi Bearer Token untuk mengamankan komunikasi dan pembatasan akses antar API." />
              </h2>
              <p className="text-xs text-[var(--text-muted)] mt-0.5">
                Gunakan token ini pada header <code>Authorization: Bearer &lt;API_KEY&gt;</code> saat memanggil endpoint <code>POST /api/v1/chat</code>.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setShowCreateKeyModal(true)}
              className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-md transition-all duration-200 hover:scale-[1.02] shrink-0 cursor-pointer"
            >
              <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              <span>Buat Kunci API Baru</span>
            </button>
          </div>

          {keys.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <p className="text-xs font-semibold text-[var(--text-primary)]">Belum ada Kunci API yang dibuat</p>
              <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
                Klik tombol "Buat Kunci API Baru" untuk mengizinkan aplikasi eksternal memanggil endpoint RAG.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-[var(--border-color)] bg-[var(--bg-input)] text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                    <th className="py-3 px-4">Nama Aplikasi / Klien</th>
                    <th className="py-3 px-4">Token Akses</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Webhook Balasan</th>
                    <th className="py-3 px-4">Terakhir Digunakan</th>
                    <th className="py-3 px-4">Dibuat Pada</th>
                    <th className="py-3 px-4 text-right">Aksi</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-color)] text-xs text-[var(--text-primary)]">
                  {keys.map((key) => (
                    <tr key={key.id} className="hover:bg-[var(--bg-input)] transition-colors">
                      <td className="py-3.5 px-4 font-semibold">{key.name}</td>
                      <td className="py-3.5 px-4 font-mono text-xs text-[var(--text-secondary)]">{key.masked_key}</td>
                      <td className="py-3.5 px-4">
                        <button
                          type="button"
                          onClick={() => handleToggleKey(key)}
                          className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors cursor-pointer ${
                            key.is_active
                              ? 'border-[var(--border-color)] text-emerald-600 dark:text-emerald-400 bg-[var(--bg-card)]'
                              : 'border-[var(--border-color)] text-[var(--text-muted)] bg-[var(--bg-input)]'
                          }`}
                        >
                          {key.is_active ? 'Aktif' : 'Nonaktif'}
                        </button>
                      </td>
                      <td className="py-3.5 px-4">
                        <button
                          type="button"
                          onClick={() => openWebhookSettings(key)}
                          className="px-2.5 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] hover:border-sky-500 text-[var(--text-secondary)] hover:text-sky-500 transition-colors cursor-pointer whitespace-nowrap"
                        >
                          {key.webhook_enabled ? 'Aktif' : 'Atur Webhook'}
                        </button>
                        {key.last_webhook_delivery && (
                          <span className={`block mt-1 text-[11px] ${key.last_webhook_delivery.status === 'delivered' ? 'text-emerald-600 dark:text-emerald-400' : key.last_webhook_delivery.status === 'failed' ? 'text-rose-500' : 'text-amber-600 dark:text-amber-400'}`}>
                            Terakhir: {key.last_webhook_delivery.status}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-[var(--text-muted)]">
                        {key.last_used_at ? new Date(key.last_used_at).toLocaleString('id-ID') : 'Belum pernah'}
                      </td>
                      <td className="py-3.5 px-4 text-xs text-[var(--text-muted)]">
                        {new Date(key.created_at).toLocaleDateString('id-ID')}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          type="button"
                          onClick={() => setDeleteKeyTarget(key)}
                          className="p-1.5 text-zinc-400 hover:text-rose-500 hover:bg-[var(--bg-input)] rounded-lg transition-colors cursor-pointer"
                          title="Cabut Kunci"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ── TAB 2: GATEWAY WHATSAPP ─────────────────────────────── */}
      {activeTab === 'whatsapp' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Form Kredensial (7/12) */}
          <div className="lg:col-span-7 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-4">
            <div className="border-b border-[var(--border-color)] pb-3">
              <h2 className="text-sm font-bold text-[var(--text-primary)] flex items-center">
                <span>Kredensial Gateway WhatsApp</span>
                <InfoTooltip
                  align="left"
                  content="Pengaturan token akses dan endpoint API WhatsApp Gateway untuk membalas pesan masuk warga/ASN secara otomatis."
                />
              </h2>
            </div>

            <form onSubmit={handleWaSubmit} className="space-y-4">
              {/* Status Toggle */}
              <div className="flex items-center justify-between p-3.5 rounded-lg bg-[var(--bg-input)]/50 border border-[var(--border-color)]">
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                    <span>Status Layanan Bot WhatsApp</span>
                    <InfoTooltip
                      align="left"
                      content="Aktifkan atau nonaktifkan pembalasan otomatis pesan WhatsApp oleh mesin AI."
                    />
                  </span>
                  <span className="text-xs text-[var(--text-muted)] block">
                    Jika dinonaktifkan, pesan WhatsApp masuk tidak akan dibalas otomatis oleh AI.
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="wa_status"
                    checked={waForm.wa_status}
                    onChange={handleWaChange}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-zinc-300 dark:bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-sky-600"></div>
                </label>
              </div>

              {/* Endpoint API */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                  <span>URL Endpoint API Gateway Pengirim</span>
                  <InfoTooltip
                    align="left"
                    content="Alamat endpoint server gateway (misal Fonnte, Wablas, atau Cloud API) untuk mengirim respon balik ke warga."
                  />
                </label>
                <input
                  type="url"
                  name="wa_api_url"
                  value={waForm.wa_api_url}
                  onChange={handleWaChange}
                  placeholder="Contoh: https://graph.facebook.com/v19.0/PHONE_NUMBER_ID/messages atau https://api.fonnte.com/send"
                  className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                />
              </div>

              {/* Token Akses */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                  <span>Bearer Access Token Gateway</span>
                  <InfoTooltip
                    align="left"
                    content="Token API rahasia untuk autentikasi ke penyedia gateway WhatsApp."
                  />
                </label>
                <div className="relative">
                  <input
                    type={showWaToken ? 'text' : 'password'}
                    name="wa_token"
                    value={waForm.wa_token}
                    onChange={handleWaChange}
                    placeholder="Masukkan token akses API WhatsApp"
                    className="w-full px-3.5 py-2 pr-10 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowWaToken(!showWaToken)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors cursor-pointer"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      {showWaToken ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178zM15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      )}
                    </svg>
                  </button>
                </div>
              </div>

              {/* Sender Phone */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                  <span>Nomor WhatsApp Dinas Pengirim (Opsional)</span>
                  <InfoTooltip
                    align="left"
                    content="Nomor resmi instansi yang didaftarkan pada akun gateway WhatsApp."
                  />
                </label>
                <input
                  type="text"
                  name="wa_phone_number"
                  value={waForm.wa_phone_number}
                  onChange={handleWaChange}
                  placeholder="Contoh: 6281234567890"
                  className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
                />
              </div>

              {/* Verify Token */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                  <span>Webhook Verify Token (Meta Cloud API)</span>
                  <InfoTooltip
                    align="left"
                    content="Token verifikasi rahasia untuk mengamankan komunikasi payload webhook masuk."
                  />
                </label>
                <input
                  type="text"
                  name="wa_webhook_verify_token"
                  value={waForm.wa_webhook_verify_token}
                  onChange={handleWaChange}
                  className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                />
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={savingWa}
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-md shadow-sky-500/25 transition-all duration-200 hover:scale-[1.01] cursor-pointer disabled:opacity-50"
                >
                  {savingWa ? 'Menyimpan...' : 'Simpan Kredensial WhatsApp'}
                </button>
              </div>
            </form>
          </div>

          {/* Webhook & Uji Coba (5/12) */}
          <div className="lg:col-span-5 space-y-5">
            {/* Webhook Info Card */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-3">
              <div className="border-b border-[var(--border-color)] pb-3">
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  Endpoint Webhook Masuk
                </h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Salin URL ini ke pengaturan Webhook Meta WhatsApp / Gateway.
                </p>
              </div>

              <div className="space-y-2.5 text-xs">
                <div>
                  <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                    Callback URL
                  </span>
                  <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] break-all flex items-center justify-between gap-2">
                    <span>{waForm.webhook_url}</span>
                    <button
                      type="button"
                      onClick={() => handleCopy(waForm.webhook_url, 'webhook')}
                      className="shrink-0 p-1 text-[var(--text-muted)] hover:text-sky-500 transition-colors cursor-pointer"
                    >
                      {copiedWebhook ? 'Tersalin' : 'Salin'}
                    </button>
                  </div>
                </div>

                <div>
                  <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block mb-1">
                    Verify Token
                  </span>
                  <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] flex items-center justify-between gap-2">
                    <span>{waForm.wa_webhook_verify_token}</span>
                    <button
                      type="button"
                      onClick={() => handleCopy(waForm.wa_webhook_verify_token, 'verify')}
                      className="shrink-0 p-1 text-[var(--text-muted)] hover:text-sky-500 transition-colors cursor-pointer"
                    >
                      {copiedVerifyToken ? 'Tersalin' : 'Salin'}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Diagnostic Send Test Card */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-3">
              <div className="border-b border-[var(--border-color)] pb-3">
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  Uji Coba Pengiriman Langsung
                </h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Verifikasi apakah kredensial API WhatsApp mampu mengirim pesan.
                </p>
              </div>

              <form noValidate onSubmit={handleTestSendWa} className="space-y-3 text-xs">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-[var(--text-primary)] block">
                    Nomor WhatsApp Tujuan
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
                    Pesan Uji Coba
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
                  {testingSend ? 'Mengirim Pesan...' : 'Kirim Pesan Uji Coba'}
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
      )}

      {/* ── TAB 3: GATEWAY TELEGRAM ─────────────────────────────── */}
      {activeTab === 'telegram' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* Form Kredensial (7/12) */}
          <div className="lg:col-span-7 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-4">
            <div className="border-b border-[var(--border-color)] pb-3 flex items-center justify-between flex-wrap gap-2">
              <div>
                <h2 className="text-sm font-bold text-[var(--text-primary)] flex items-center">
                  <span>Kredensial Gateway Bot Telegram</span>
                  <InfoTooltip
                    align="left"
                    content="Konfigurasi token resmi dari @BotFather untuk menghubungkan bot Telegram ke mesin AI RAG."
                  />
                </h2>
              </div>
              {tgForm.telegram_bot_username && (
                <span className="px-2.5 py-1 rounded-full text-xs font-mono font-bold bg-[var(--bg-card)] text-sky-600 dark:text-sky-400 border border-[var(--border-color)]">
                  {tgForm.telegram_bot_username}
                </span>
              )}
            </div>

            <form onSubmit={handleTgSubmit} className="space-y-4">
              {/* Status Toggle */}
              <div className="flex items-center justify-between p-3.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)]">
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                    <span>Status Layanan Bot Telegram</span>
                    <InfoTooltip
                      align="left"
                      content="Aktifkan atau nonaktifkan penerimaan dan pembalasan pesan Telegram otomatis oleh AI."
                    />
                  </span>
                  <span className="text-xs text-[var(--text-muted)] block">
                    Jika dinonaktifkan, pesan Telegram masuk tidak akan dibalas otomatis oleh mesin AI.
                  </span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    name="telegram_status"
                    checked={tgForm.telegram_status}
                    onChange={handleTgChange}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-zinc-300 dark:bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-zinc-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-sky-600"></div>
                </label>
              </div>

              {/* Bot Username */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                  <span>Username Bot (Opsional)</span>
                  <InfoTooltip
                    align="left"
                    content="Nama akun @username bot Telegram resmi instansi."
                  />
                </label>
                <input
                  type="text"
                  name="telegram_bot_username"
                  value={tgForm.telegram_bot_username}
                  onChange={handleTgChange}
                  placeholder="Contoh: @DiskominfotikBandaAcehBot"
                  className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                />
              </div>

              {/* Bot Token */}
              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[var(--text-primary)] flex items-center">
                  <span>Telegram Bot API Token (dari @BotFather)</span>
                  <InfoTooltip
                    align="left"
                    content="Token otorisasi rahasia bot yang diperoleh langsung dari @BotFather di aplikasi Telegram."
                  />
                </label>
                <div className="relative">
                  <input
                    type={showTgToken ? 'text' : 'password'}
                    name="telegram_bot_token"
                    value={tgForm.telegram_bot_token}
                    onChange={handleTgChange}
                    placeholder="Contoh: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ"
                    className="w-full px-3.5 py-2 pr-10 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setShowTgToken(!showTgToken)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors cursor-pointer"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      {showTgToken ? (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243m4.242 4.242L9.88 9.88" />
                      ) : (
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178zM15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      )}
                    </svg>
                  </button>
                </div>
                <p className="text-[11px] text-[var(--text-muted)]">
                  Dapatkan token resmi dengan membuka Telegram &rarr; cari akun terverifikasi <strong>@BotFather</strong> &rarr; kirim perintah <code>/newbot</code>.
                </p>
              </div>

              <div className="pt-2">
                <button
                  type="submit"
                  disabled={savingTg}
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-md transition-all duration-200 hover:scale-[1.01] cursor-pointer disabled:opacity-50"
                >
                  {savingTg ? 'Menyimpan...' : 'Simpan Kredensial Telegram'}
                </button>
              </div>
            </form>
          </div>

          {/* Webhook & Uji Coba (5/12) */}
          <div className="lg:col-span-5 space-y-5">
            {/* Local Polling Mode Card (Best for Laptop Development) */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-3">
              <div className="border-b border-[var(--border-color)] pb-2.5">
                <span className="text-xs font-bold text-sky-600 dark:text-sky-400 uppercase tracking-wider block">
                  Mode 1: Long Polling (Khusus Laptop / Tanpa Domain)
                </span>
                <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                  Jika berjalan di <code>localhost</code> tanpa IP publik / HTTPS, jalankan runner terminal berikut. Bot akan langsung aktif dan merespon pesan Telegram secara real-time!
                </p>
              </div>

              <div className="space-y-2">
                <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] flex items-center justify-between gap-2">
                  <span>php artisan telegram:poll</span>
                  <button
                    type="button"
                    onClick={() => handleCopy('php artisan telegram:poll', 'code')}
                    className="shrink-0 px-2.5 py-1 rounded bg-sky-500 text-white font-bold text-[11px] hover:bg-sky-600 transition-colors cursor-pointer"
                  >
                    {copiedCode ? 'Tersalin' : 'Salin'}
                  </button>
                </div>
              </div>
            </div>

            {/* Webhook Info Card (For Production / HTTPS) */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-3">
              <div className="border-b border-[var(--border-color)] pb-3">
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  Mode 2: Webhook Masuk (Wajib HTTPS Publik)
                </h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Telegram mewajibkan URL berawalan <code>https://</code> publik (contoh via Ngrok atau Domain Instansi).
                </p>
              </div>

              <div className="space-y-2.5 text-xs">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-[var(--text-primary)] block">
                    URL Webhook Publik (HTTPS)
                  </label>
                  <input
                    type="url"
                    name="webhook_url"
                    value={tgForm.webhook_url}
                    onChange={handleTgChange}
                    placeholder="https://domain-resmi.go.id/api/v1/webhook/telegram atau https://xxx.ngrok-free.app/api/v1/webhook/telegram"
                    className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                  />
                </div>

                {/* Auto Register Webhook Button */}
                <div className="pt-2 space-y-2">
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => handleAutoRegisterWebhook('set')}
                      disabled={registeringWebhook}
                      className="flex-1 py-2 px-3 rounded-lg text-xs font-bold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-sky-600 dark:text-sky-400 border border-[var(--border-color)] transition-colors cursor-pointer flex items-center justify-center gap-1.5 disabled:opacity-50"
                    >
                      <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                      </svg>
                      <span>{registeringWebhook ? 'Memproses...' : 'Daftarkan Webhook'}</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleAutoRegisterWebhook('delete')}
                      disabled={registeringWebhook}
                      title="Hapus webhook untuk kembali ke mode Long Polling"
                      className="py-2 px-3 rounded-lg text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] hover:text-rose-500 border border-[var(--border-color)] transition-colors cursor-pointer disabled:opacity-50"
                    >
                      Hapus Webhook
                    </button>
                  </div>

                  {webhookResult && (
                    <div
                      className={`p-2.5 rounded-lg text-xs border ${
                        webhookResult.type === 'success'
                          ? 'bg-[var(--bg-input)] text-emerald-600 dark:text-emerald-400 border-[var(--border-color)]'
                          : 'bg-[var(--bg-input)] text-rose-600 dark:text-rose-400 border-[var(--border-color)]'
                      }`}
                    >
                      <p className="font-semibold leading-relaxed">{webhookResult.text}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Diagnostic Send Test Card */}
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-3">
              <div className="border-b border-[var(--border-color)] pb-3">
                <h2 className="text-sm font-bold text-[var(--text-primary)]">
                  Uji Coba Koneksi & Pengiriman
                </h2>
                <p className="text-xs text-[var(--text-muted)] mt-0.5">
                  Verifikasi konektivitas token ke Telegram atau kirim pesan uji coba ke Chat ID Anda.
                </p>
              </div>

              <form onSubmit={handleTestSendTg} className="space-y-3 text-xs">
                <div className="space-y-1">
                  <label className="text-xs font-bold text-[var(--text-primary)] block">
                    Chat ID Telegram Tujuan (Opsional)
                  </label>
                  <input
                    type="text"
                    value={tgTestChatId}
                    onChange={(e) => setTgTestChatId(e.target.value)}
                    placeholder="Contoh: 123456789 (kosongkan untuk cek info bot saja)"
                    className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors font-mono"
                  />
                  <p className="text-[11px] text-[var(--text-muted)]">
                    Ketik <code>/start</code> ke <strong>@userinfobot</strong> di Telegram untuk mengetahui Chat ID Anda.
                  </p>
                </div>

                {tgTestChatId && (
                  <div className="space-y-1">
                    <label className="text-xs font-bold text-[var(--text-primary)] block">
                      Pesan Uji Coba
                    </label>
                    <textarea
                      value={tgTestMsg}
                      onChange={(e) => setTgTestMsg(e.target.value)}
                      rows={2}
                      className="w-full px-3.5 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors resize-none"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={testingTgSend}
                  className="w-full py-2 px-3 rounded-lg text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  {testingTgSend ? 'Menguji Koneksi...' : tgTestChatId ? 'Kirim Pesan Uji Coba' : 'Uji Validitas Token Bot'}
                </button>

                {tgTestResult && (
                  <div
                    className={`p-3 rounded-lg text-xs border ${
                      tgTestResult.type === 'success'
                        ? 'bg-[var(--bg-input)] text-emerald-600 dark:text-emerald-400 border-[var(--border-color)]'
                        : 'bg-[var(--bg-input)] text-rose-600 dark:text-rose-400 border-[var(--border-color)]'
                    }`}
                  >
                    <p className="font-semibold">{tgTestResult.text}</p>
                  </div>
                )}
              </form>
            </div>
          </div>
        </div>
      )}

      {/* ── TAB 4: DOKUMENTASI & SPESIFIKASI ENDPOINT ───────────── */}
      {activeTab === 'docs' && (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-5 shadow-xs space-y-5">
          <div className="border-b border-[var(--border-color)] pb-3">
            <h2 className="text-sm font-bold text-[var(--text-primary)] flex items-center">
              <span>Spesifikasi Pemanggilan Public API (V1)</span>
              <InfoTooltip content="Dokumentasi teknis pemanggilan endpoint POST /api/v1/chat dan POST /api/v1/chat/stream untuk sistem eksternal." />
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-lg bg-[var(--bg-input)]/40 border border-[var(--border-color)] space-y-2">
              <span className="font-bold text-sky-600 dark:text-sky-400 block">
                1. Mode JSON Sinkron (Standard)
              </span>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Endpoint: <code className="font-mono font-semibold">POST /api/v1/chat</code><br />
                Merespons dengan satu payload JSON lengkap berisi jawaban AI, rujukan dokumen SOP, nomor halaman, dan waktu inferensi.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-[var(--bg-input)]/40 border border-[var(--border-color)] space-y-2">
              <span className="font-bold text-purple-600 dark:text-purple-400 block">
                2. Mode Realtime Streaming (SSE)
              </span>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                Endpoint: <code className="font-mono font-semibold">POST /api/v1/chat/stream</code><br />
                Merespons dengan aliran <em>Server-Sent Events (SSE)</em> kata-per-kata untuk widget interaktif.
              </p>
            </div>
          </div>

          {/* Code Snippet Box */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-[var(--text-primary)]">
                Contoh Pemanggilan Kode
              </span>
              <SlidingTabs
                tabs={[
                  { id: 'curl', label: 'CURL' },
                  { id: 'python', label: 'PYTHON' },
                  { id: 'javascript', label: 'JAVASCRIPT' },
                ]}
                activeTab={docLang}
                onChange={setDocLang}
                variant="pill"
                size="xs"
                className="bg-[var(--bg-input)]"
              />
            </div>

            <div key={docLang} className="animate-fade-in relative p-4 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] overflow-x-auto">
              <button
                type="button"
                onClick={() => handleCopy(generateSnippet(), 'code')}
                className="absolute right-3 top-3 px-3 py-1.5 rounded-lg text-xs font-bold bg-gradient-to-r from-sky-500 to-sky-400 dark:from-sky-500 dark:to-blue-600 text-white transition-all hover:scale-105 cursor-pointer shadow-sm"
              >
                {copiedCode ? 'Tersalin' : 'Salin Kode'}
              </button>
              <pre className="whitespace-pre">{generateSnippet()}</pre>
            </div>
          </div>
        </div>
      )}
      </div>

      {/* ── MODAL: BUAT KUNCI API (PORTAL KE DOCUMENT.BODY) ────── */}
      {showCreateKeyModal &&
        ReactDOM.createPortal(
          <div className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl max-w-md w-full p-5 shadow-xl space-y-4">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Buat Kunci API Baru
                </h3>
                <p className="text-xs text-[var(--text-muted)]">
                  Beri nama identifikasi untuk aplikasi atau layanan yang akan menggunakan kunci ini.
                </p>
              </div>

              <form noValidate onSubmit={handleCreateKey} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[var(--text-primary)] block">
                    Nama Aplikasi / Klien Pemanggil
                  </label>
                  <input
                    type="text"
                    value={keyName}
                    onChange={(e) => setKeyName(e.target.value)}
                    placeholder="Contoh: Portal Web Resmi Dinas, WhatsApp Bot Gateway"
                    autoFocus
                    className="w-full px-3.5 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
                  />
                </div>

                <div className="flex justify-end gap-2.5 pt-2 border-t border-[var(--border-color)]">
                  <button
                    type="button"
                    onClick={() => setShowCreateKeyModal(false)}
                    disabled={creatingKey}
                    className="px-3.5 py-2 rounded-xl text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-input)] transition-colors cursor-pointer"
                  >
                    Batal
                  </button>
                  <button
                    type="submit"
                    disabled={creatingKey || !keyName.trim()}
                    className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white transition-all hover:scale-[1.02] cursor-pointer shadow-md shadow-sky-500/25 disabled:opacity-50"
                  >
                    {creatingKey ? 'Membuat...' : 'Buat Token'}
                  </button>
                </div>
              </form>
            </div>
          </div>,
          document.body
        )}

      {/* ── MODAL: VIEW TOKEN RAHASIA SATU KALI (PORTAL KE DOCUMENT.BODY) ── */}
      {newlyCreatedKey &&
        ReactDOM.createPortal(
          <div className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl max-w-lg w-full p-5 shadow-2xl space-y-4">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Simpan Kunci API "{newlyCreatedKey.name}"
                </h3>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
                  Harap salin dan simpan token ini sekarang. Demi keamanan, token lengkap <strong>hanya ditampilkan satu kali ini</strong>.
                </p>
              </div>

              <div className="p-3.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] font-mono text-xs text-[var(--text-primary)] break-all select-all flex items-center justify-between gap-3">
                <span>{newlyCreatedKey.plain_key}</span>
                <button
                  type="button"
                  onClick={() => handleCopy(newlyCreatedKey.plain_key, 'secret')}
                  className="shrink-0 px-3 py-1.5 rounded-lg text-xs font-bold bg-gradient-to-r from-sky-500 to-sky-400 dark:from-sky-500 dark:to-blue-600 text-white transition-all hover:scale-105 cursor-pointer shadow-sm"
                >
                  {copiedKey ? 'Tersalin' : 'Salin Token'}
                </button>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setNewlyCreatedKey(null)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer"
                >
                  Saya Sudah Menyimpan Token Ini
                </button>
              </div>
            </div>
          </div>,
          document.body
        )}

      {webhookTarget &&
        ReactDOM.createPortal(
          <div className="fixed inset-0 z-[99999] flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-fade-in">
            <form onSubmit={handleSaveWebhook} className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl max-w-xl w-full p-5 shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">Webhook Balasan Petugas</h3>
                <p className="text-xs text-[var(--text-muted)]">Klien: <strong>{webhookTarget.name}</strong>. Balasan non-internal dari petugas akan dikirim ke URL ini.</p>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-bold text-[var(--text-primary)]">URL Penerima</label>
                <input
                  type="url"
                  value={webhookForm.webhook_url}
                  onChange={(e) => setWebhookForm((prev) => ({ ...prev, webhook_url: e.target.value }))}
                  placeholder="https://sistem-anda.go.id/webhooks/sapa"
                  className="w-full px-3 py-2.5 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 font-mono"
                />
                <p className="text-[11px] text-[var(--text-muted)]">HTTP lokal diizinkan untuk demo; gunakan HTTPS untuk server publik.</p>
              </div>

              <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-[var(--bg-input)]/50 border border-[var(--border-color)]">
                <div>
                  <p className="text-xs font-semibold text-[var(--text-primary)]">Aktifkan pengiriman event</p>
                  <p className="text-[11px] text-[var(--text-muted)]">Event: ticket.reply.created</p>
                </div>
                <input
                  type="checkbox"
                  checked={webhookForm.webhook_enabled}
                  onChange={(e) => setWebhookForm((prev) => ({ ...prev, webhook_enabled: e.target.checked }))}
                  className="w-4 h-4 accent-sky-500 cursor-pointer"
                />
              </div>

              <div className="space-y-2 p-3 rounded-lg border border-[var(--border-color)]">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold text-[var(--text-primary)]">Secret tanda tangan</p>
                    <p className="text-[11px] text-[var(--text-muted)]">{webhookTarget.webhook_secret_configured ? 'Secret sudah tersimpan.' : 'Belum ada secret.'} Nilai baru hanya ditampilkan sekali.</p>
                  </div>
                  <button
                    type="button"
                    onClick={handleRotateWebhookSecret}
                    disabled={rotatingWebhookSecret}
                    className="shrink-0 px-3 py-1.5 rounded-lg text-[11px] font-semibold border border-[var(--border-color)] hover:border-sky-500 hover:text-sky-500 disabled:opacity-50 cursor-pointer"
                  >
                    {rotatingWebhookSecret ? 'Membuat...' : webhookTarget.webhook_secret_configured ? 'Ganti Secret' : 'Buat Secret'}
                  </button>
                </div>
                {webhookSecretOnce && (
                  <div className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] flex items-start gap-2">
                    <code className="text-[11px] font-mono text-[var(--text-primary)] break-all flex-1">{webhookSecretOnce}</code>
                    <button type="button" onClick={() => handleCopy(webhookSecretOnce, 'secret')} className="shrink-0 px-2 py-1 rounded-md bg-sky-600 text-white text-[11px] font-semibold cursor-pointer">{copiedKey ? 'Tersalin' : 'Salin'}</button>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <p className="text-xs font-bold text-[var(--text-primary)]">Riwayat pengiriman terbaru</p>
                {webhookDeliveries.length ? (
                  <div className="max-h-32 overflow-y-auto divide-y divide-[var(--border-color)] border border-[var(--border-color)] rounded-lg px-3">
                    {webhookDeliveries.map((delivery) => (
                      <div key={delivery.id} className="py-2 flex items-start justify-between gap-3 text-[11px]">
                        <div><span className="font-mono">{delivery.event_type}</span><span className="block text-[var(--text-muted)]">{delivery.created_at ? new Date(delivery.created_at).toLocaleString('id-ID') : ''}</span>{delivery.last_error && <span className="block text-rose-500 break-all">{delivery.last_error}</span>}</div>
                        <span className={delivery.status === 'delivered' ? 'text-emerald-600 dark:text-emerald-400' : delivery.status === 'failed' ? 'text-rose-500' : 'text-amber-600 dark:text-amber-400'}>{delivery.status}{delivery.response_status ? ` · ${delivery.response_status}` : ''}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-[11px] text-[var(--text-muted)]">Belum ada pengiriman webhook.</p>}
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-[var(--border-color)]">
                <button type="button" onClick={() => setWebhookTarget(null)} className="px-3.5 py-2 rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-input)] cursor-pointer">Tutup</button>
                <button type="submit" disabled={savingWebhook} className="px-4 py-2 rounded-lg text-xs font-bold bg-sky-600 text-white hover:bg-sky-500 disabled:opacity-50 cursor-pointer">{savingWebhook ? 'Menyimpan...' : 'Simpan Webhook'}</button>
              </div>
            </form>
          </div>,
          document.body
        )}

      {/* ── MODAL: DELETE KEY CONFIRMATION ──────────────────────── */}
      <ConfirmModal
        isOpen={Boolean(deleteKeyTarget)}
        title="Cabut Kunci API?"
        message={`Apakah Anda yakin ingin mencabut dan menghapus Kunci API "${deleteKeyTarget?.name}"? Aplikasi atau layanan yang menggunakan kunci ini akan langsung ditolak aksesnya.`}
        confirmText="Ya, Cabut Kunci"
        cancelText="Batal"
        danger={true}
        onConfirm={handleDeleteKey}
        onCancel={() => setDeleteKeyTarget(null)}
      />

      {/* Floating Save Bar for WhatsApp & Telegram settings dirty state */}
      <FloatingSaveBar
        show={(activeTab === 'whatsapp' && isWaDirty) || (activeTab === 'telegram' && isTgDirty)}
        onSave={activeTab === 'whatsapp' ? handleWaSubmit : handleTgSubmit}
        onDiscard={activeTab === 'whatsapp' ? handleDiscardWa : handleDiscardTg}
        saving={activeTab === 'whatsapp' ? savingWa : savingTg}
        message={activeTab === 'whatsapp' ? "Perubahan konfigurasi WhatsApp belum disimpan" : "Perubahan konfigurasi Telegram belum disimpan"}
      />
    </div>
  )
}
