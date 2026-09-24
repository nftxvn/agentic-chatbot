import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import gsap from 'gsap'
import { getChatbotSettings, updateChatbotSettings, resetChatbotSettings, getAvailableModels, getHardwareStatus, benchmarkModel } from '../api/settings'
import { documentsApi } from '../api/documents'
import { mesinApi } from '../api/mesin'
import { addAppNotification } from '../utils/notifications'
import { SlidingTabs } from '../components/UI/SlidingTabs'
import { FloatingSaveBar } from '../components/UI/FloatingSaveBar'
import { aiChatService } from '../services/aiChatService'
import { FastPathSettings } from '../components/Settings/FastPathSettings'
import { DirectorySettings } from '../components/Settings/DirectorySettings'
import { InfoTooltip } from '../components/UI/InfoTooltip'

export default function ChatbotSettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)
  const [mainSection, setMainSection] = useState('studio') // 'studio' | 'fastpaths' | 'directories'
  const [activeConfigTab, setActiveConfigTab] = useState('prompt') // 'prompt' | 'identity' | 'params'
  const [activePlaygroundTab, setActivePlaygroundTab] = useState('chat') // 'chat' | 'chunks' | 'api'
  const [showResetModal, setShowResetModal] = useState(false)

  // Hardware Auto-Detection & Live Telemetry State
  const [hardwareData, setHardwareData] = useState(null)
  const [detectingHardware, setDetectingHardware] = useState(false)
  const [showHardwareDetails, setShowHardwareDetails] = useState(false)

  // Benchmark State
  const [benchmarking, setBenchmarking] = useState(false)
  const [benchmarkResult, setBenchmarkResult] = useState(null)

  // Available Ollama Models State
  const [availableModels, setAvailableModels] = useState([])
  const [loadingModels, setLoadingModels] = useState(false)

  // Document Scope Filtering
  const [availableDocs, setAvailableDocs] = useState([])
  const [selectedDocIds, setSelectedDocIds] = useState([])

  // Live Chat Sandbox State managed via aiChatService
  const [chatState, setChatState] = useState(() => aiChatService.getState())
  const [chatInput, setChatInput] = useState('')
  const [lastQuery, setLastQuery] = useState('')
  const [apiCodeLang, setApiCodeLang] = useState('curl') // 'curl' | 'python' | 'js'
  const [copiedCode, setCopiedCode] = useState(false)

  const headerRef = useRef(null)
  const leftCardRef = useRef(null)
  const rightCardRef = useRef(null)
  const promptTextareaRef = useRef(null)
  const chatBottomRef = useRef(null)

  const { chatMessages, retrievedChunks, isStreaming } = chatState

  // Subscribe to background AI Chat Service updates
  useEffect(() => {
    const unsubscribe = aiChatService.subscribe((state) => {
      setChatState(state)
    })
    return unsubscribe
  }, [])

  const [initialForm, setInitialForm] = useState(null)
  const [form, setForm] = useState({
    llm_model_name: 'qwen2.5:7b',
    chatbot_name: '',
    chatbot_persona: '',
    rag_system_prompt: '',
    rag_temperature: 0.2,
    rag_top_k: 8,
    rag_num_ctx: 6144,
    chatbot_greeting: '',
    chatbot_fallback_message: '',
    rag_citation_enabled: true,
    default_rag_prompt: '',
  })

  // Dirty state tracking for configuration changes
  const isDirty = Boolean(
    initialForm && JSON.stringify(form) !== JSON.stringify(initialForm)
  )

  useEffect(() => {
    fetchInitialData()
  }, [])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chatMessages])

  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  async function fetchInitialData() {
    const startTime = Date.now()
    try {
      setLoading(true)
      const [settingsData, docsData, modelsData, hwData] = await Promise.all([
        getChatbotSettings(),
        documentsApi.list(1).catch(() => ({ data: { documents: [] } })),
        getAvailableModels().catch(() => ({ models: [] })),
        getHardwareStatus().catch(() => null),
      ])

      const loaded = {
        llm_model_name: settingsData.llm_model_name || 'qwen2.5:7b',
        chatbot_name: settingsData.chatbot_name || 'Asisten Virtual Diskominfotik',
        chatbot_persona: settingsData.chatbot_persona || 'Asisten AI Resmi Layanan Informasi Diskominfotik',
        rag_system_prompt: settingsData.rag_system_prompt || '',
        rag_temperature: typeof settingsData.rag_temperature === 'number' ? settingsData.rag_temperature : 0.2,
        rag_top_k: typeof settingsData.rag_top_k === 'number' ? settingsData.rag_top_k : 8,
        rag_num_ctx: typeof settingsData.rag_num_ctx === 'number' ? settingsData.rag_num_ctx : 6144,
        chatbot_greeting: settingsData.chatbot_greeting || 'Selamat datang di Layanan Informasi SOP Dinas Komunikasi, Informatika dan Statistik Kota Banda Aceh. Silakan sampaikan pertanyaan Anda.',
        chatbot_fallback_message: settingsData.chatbot_fallback_message || 'Maaf, informasi mengenai hal tersebut tidak ditemukan di dalam dokumen SOP yang tersedia.',
        rag_citation_enabled: settingsData.rag_citation_enabled ?? true,
        default_rag_prompt: settingsData.default_rag_prompt || '',
      }

      setForm(loaded)
      setInitialForm(loaded)

      if (modelsData?.models && Array.isArray(modelsData.models)) {
        setAvailableModels(modelsData.models)
      }

      if (hwData?.data) {
        setHardwareData(hwData.data)
      }

      // Initial Greeting in Chat Sandbox (only if no existing messages in session)
      if (loaded.chatbot_greeting) {
        aiChatService.setInitialGreeting(loaded.chatbot_greeting)
      }

      // Populate Documents for filtering
      const docs = docsData?.data?.documents || docsData?.documents || []
      setAvailableDocs(docs)
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal memuat konfigurasi dari server.' })
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => setLoading(false), Math.max(0, 200 - elapsed))
    }
  }

  const handleDetectHardware = async (showNotification = true, modelOverride = null) => {
    setDetectingHardware(true)
    try {
      const modelToUse = modelOverride || form.llm_model_name || 'qwen2.5:7b'
      const res = await getHardwareStatus(modelToUse)
      if (res?.data) {
        setHardwareData(res.data)
        if (showNotification && res.data?.rekomendasi?.recommended_num_ctx) {
          addAppNotification({
            title: 'Telemetri Hardware Real-time',
            message: `Spesifikasi server terdeteksi: ${res.data.rekomendasi.ringkasan_hardware}`,
            type: 'system',
          })
        }
      }
    } catch (err) {
      console.error('Gagal deteksi hardware:', err)
      if (showNotification) {
        setStatusMsg({
          type: 'error',
          text: 'Gagal mendeteksi spesifikasi server AI. Pastikan layanan AI berjalan.',
        })
      }
    } finally {
      setDetectingHardware(false)
    }
  }

  const handleRefreshAll = async () => {
    setLoadingModels(true)
    setDetectingHardware(true)
    try {
      const [modelsRes, hwRes] = await Promise.all([
        getAvailableModels().catch(() => ({ models: [] })),
        getHardwareStatus(form.llm_model_name).catch(() => null),
      ])
      if (modelsRes?.models && Array.isArray(modelsRes.models)) {
        setAvailableModels(modelsRes.models)
      }
      if (hwRes?.data) {
        setHardwareData(hwRes.data)
      }
      addAppNotification({
        title: 'Status Diselaraskan',
        message: `Model terdeteksi: ${modelsRes?.models?.length || 0} | VRAM Bebas: ${((hwRes?.data?.gpu?.vram_bebas_mib || 0) / 1024).toFixed(1)} GB`,
        type: 'system',
      })
    } catch (err) {
      console.error('Gagal menyegarkan status:', err)
    } finally {
      setLoadingModels(false)
      setDetectingHardware(false)
    }
  }


  const handleModelSelectChange = (e) => {
    const newModel = e.target.value
    handleChange(e)
    handleDetectHardware(false, newModel)
    if (benchmarkResult && benchmarkResult.model !== newModel) {
      setBenchmarkResult(null)
    }
  }

  const handleRunBenchmark = async () => {
    const currentModel = form.llm_model_name || 'qwen2.5:7b'
    setBenchmarking(true)
    try {
      const res = await benchmarkModel(currentModel)
      if (res && res.success) {
        setBenchmarkResult(res)
        addAppNotification({
          title: 'Benchmark Selesai',
          message: `Model ${currentModel}: ${res.tokens_per_second} tok/s (Latency: ${res.time_to_first_token_ms} ms)`,
          type: 'system',
        })
        handleDetectHardware(false, currentModel)
      } else {
        addAppNotification({
          title: 'Benchmark Gagal',
          message: res?.message || 'Gagal menjalankan inferensi benchmark.',
          type: 'error',
        })
      }
    } catch (err) {
      console.error('Gagal benchmark model:', err)
      addAppNotification({
        title: 'Benchmark Gagal',
        message: err.response?.data?.message || 'Gagal menghubungi server inferensi Ollama.',
        type: 'error',
      })
    } finally {
      setBenchmarking(false)
    }
  }

  const handleApplyRecommendation = (recCtx) => {
    setForm((prev) => ({ ...prev, rag_num_ctx: recCtx }))
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setForm((prev) => ({
      ...prev,
      [name]:
        type === 'checkbox'
          ? checked
          : type === 'number' || type === 'range'
            ? parseFloat(value)
            : value,
    }))
    setStatusMsg(null)
  }

  const handleInsertTag = (tag) => {
    if (!promptTextareaRef.current) return
    const el = promptTextareaRef.current
    const start = el.selectionStart
    const end = el.selectionEnd
    const text = form.rag_system_prompt
    const before = text.substring(0, start)
    const after = text.substring(end, text.length)
    const updated = before + tag + after
    setForm((prev) => ({ ...prev, rag_system_prompt: updated }))
    setTimeout(() => {
      el.focus()
      el.setSelectionRange(start + tag.length, start + tag.length)
    }, 50)
  }

  const handleDiscard = () => {
    if (initialForm) {
      setForm({ ...initialForm })
      setStatusMsg(null)
    }
  }

  const handleSubmit = async (e) => {
    if (e) e.preventDefault()
    if (!form.rag_system_prompt || !form.rag_system_prompt.trim()) {
      setStatusMsg({
        type: 'error',
        text: 'System prompt wajib diisi.',
      })
      return
    }
    setSaving(true)
    setStatusMsg(null)
    try {
      const res = await updateChatbotSettings(form)
      setInitialForm({ ...form })
      setStatusMsg({ type: 'success', text: res.message || 'Konfigurasi berhasil disimpan ke sistem produksi.' })
      addAppNotification({
        title: 'Pengaturan AI',
        message: 'Konfigurasi prompt dan parameter RAG telah diperbarui.',
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({
        type: 'error',
        text: err.response?.data?.message || 'Gagal menyimpan konfigurasi.',
      })
    } finally {
      setSaving(false)
    }
  }

  const handleTestQuery = (queryText) => {
    setChatInput(queryText)
    setActivePlaygroundTab('chat')
    setTimeout(() => {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, 100)
  }

  const handleReset = async () => {
    setResetting(true)
    setShowResetModal(false)
    try {
      await resetChatbotSettings()
      setStatusMsg({ type: 'success', text: 'Konfigurasi dikembalikan ke pengaturan standar.' })
      await fetchInitialData()
      addAppNotification({
        title: 'Pengaturan AI',
        message: 'Pengaturan chatbot dikembalikan ke bawaan sistem.',
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal mengembalikan konfigurasi ke standar.' })
    } finally {
      setResetting(false)
    }
  }

  // ── LIVE CHAT SSE STREAMING (SANDBOX) ───────────────────────────
  // ── LIVE CHAT SSE STREAMING VIA PERSISTENT aiChatService ───────
  const handleSendChat = (queryToSend) => {
    const q = (queryToSend || chatInput).trim()
    if (!q || isStreaming) return

    setLastQuery(q)
    setChatInput('')

    aiChatService.sendMessage({
      query: q,
      systemPrompt: form.rag_system_prompt || undefined,
      temperature: form.rag_temperature,
      topK: form.rag_top_k,
      selectedDocIds: selectedDocIds.length > 0 ? selectedDocIds : undefined,
    })
  }

  const handleStopStream = () => {
    aiChatService.stopStream()
  }

  const handleClearChat = () => {
    aiChatService.clearChat(form.chatbot_greeting || 'Sesi pengujian baru telah dimulai.')
  }

  const handleCopyCode = (text) => {
    navigator.clipboard.writeText(text)
    setCopiedCode(true)
    setTimeout(() => setCopiedCode(false), 2000)
  }

  const quickQuestions = [
    'Bagaimana prosedur permohonan izin penyelenggaraan reklame?',
    'Apa saja persyaratan pengajuan subdomain acehkota.go.id?',
    'Sebutkan dasar hukum dan nomor SOP Dinas Kominfo',
    'Berapa lama waktu penyelesaian layanan penanganan insiden siber?',
  ]

  const approxPromptTokens = Math.round((form.rag_system_prompt?.length || 0) / 3.5)

  // API Code Snippet Generator
  const generateApiSnippet = () => {
    const q = lastQuery || 'Bagaimana prosedur permohonan subdomain?'
    const docParam = selectedDocIds.length > 0 ? selectedDocIds : null

    if (apiCodeLang === 'curl') {
      return `curl -X POST "http://localhost:8000/api/v1/chat" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <API_KEY>" \\
  -d '{
    "session_id": "client-session-123",
    "query": "${q.replace(/"/g, '\\"')}",
    "document_ids": ${docParam ? JSON.stringify(docParam) : 'null'}
  }'`
    }

    if (apiCodeLang === 'python') {
      return `import requests

url = "http://localhost:8000/api/v1/chat"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer <API_KEY>"
}
payload = {
    "session_id": "client-session-123",
    "query": "${q.replace(/"/g, '\\"')}",
    "document_ids": ${docParam ? JSON.stringify(docParam) : 'None'}
}

response = requests.post(url, headers=headers, json=payload)
data = response.json()

print("Jawaban:", data.get("answer"))
print("Rujukan:", data.get("sources"))`
    }

    return `// JavaScript (Fetch JSON)
const response = await fetch("http://localhost:8000/api/v1/chat", {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    "Authorization": "Bearer <API_KEY>",
  },
  body: JSON.stringify({
    session_id: "client-session-123",
    query: "${q.replace(/"/g, '\\"')}",
    document_ids: ${docParam ? JSON.stringify(docParam) : 'null'}
  }),
});

const data = await response.json();
console.log("Jawaban:", data.answer);
console.log("Rujukan:", data.sources);`
  }

  if (loading) {
    return (
      <div className="p-4 sm:p-5 max-w-7xl mx-auto space-y-4">
        <div className="p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-2">
          <div className="skeleton h-6 w-64 rounded-md" />
          <div className="skeleton h-4 w-96 rounded-md" />
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          <div className="xl:col-span-6 p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl space-y-4">
            <div className="skeleton h-10 w-full rounded-lg" />
            <div className="skeleton h-96 w-full rounded-lg" />
          </div>
          <div className="xl:col-span-6 p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl space-y-4">
            <div className="skeleton h-10 w-full rounded-lg" />
            <div className="skeleton h-96 w-full rounded-lg" />
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5 pb-28 relative">
      {/* ── TOP HEADER BANNER ───────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div ref={headerRef} className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
            <span>CHATBOT & RAG PLAYGROUND</span>
            <InfoTooltip size="lg" content="Pusat konfigurasi prompt instruksi AI, parameter inferensi LLM, serta sandbox simulasi pengujian retrieval korpus dokumen RAG secara live." />
          </h1>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 self-start md:self-auto">
          <button
            type="button"
            onClick={() => setShowResetModal(true)}
            disabled={resetting || saving}
            className="px-3.5 py-2 text-xs font-semibold rounded-xl text-[var(--text-secondary)] hover:text-[var(--red-color)] hover:bg-[var(--bg-input)] border border-[var(--border-color)] transition-colors cursor-pointer disabled:opacity-50"
          >
            Reset
          </button>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving || !isDirty}
            className={`px-4 py-2.5 rounded-xl text-xs sm:text-sm font-bold text-white transition-all duration-200 flex items-center justify-center gap-2 cursor-pointer shadow-md ${
              isDirty
                ? 'bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 shadow-sky-500/25 hover:scale-[1.02]'
                : 'bg-[var(--bg-input)] border border-[var(--border-color)] !text-[var(--text-muted)] cursor-not-allowed opacity-60'
            }`}
          >
            {saving ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Menyimpan...</span>
              </>
            ) : isDirty ? (
              <span>Simpan Perubahan</span>
            ) : (
              <span>Tersimpan</span>
            )}
          </button>
        </div>
      </div>

      {/* ── NOTIFICATION TOAST ─────────────────────────────────── */}
      {statusMsg && (
        <div
          className={`px-4 py-3 rounded-lg text-xs font-medium flex items-center justify-between border transition-all ${
            statusMsg.type === 'success'
              ? 'bg-[var(--bg-card)] text-[var(--action-green)] border-[var(--border-color)]'
              : 'bg-[var(--bg-card)] text-[var(--red-color)] border-[var(--border-color)]'
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

      {/* ── TOP SECTION SWITCHER ─────────────────────────────────── */}
      <div className="bg-[var(--bg-card)] p-2 sm:p-2.5 rounded-xl border border-[var(--border-color)] shadow-xs">
        <SlidingTabs
          tabs={[
            { id: 'studio', label: 'Studio Prompt & Sandbox Live' },
            { id: 'fastpaths', label: 'Fast-Path & FAQ Dinamis' },
            { id: 'directories', label: 'Direktori Unit Kerja' },
          ]}
          activeTab={mainSection}
          onChange={setMainSection}
          variant="pill"
        />
      </div>

      {/* ── UNIFIED TWO-COLUMN WORKSPACE ───────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* ── LEFT COLUMN: CONFIGURATION & PARAMETERS ──────────── */}
        <div
          ref={leftCardRef}
          className={`${
            mainSection === 'studio'
              ? 'lg:col-span-6 xl:col-span-5'
              : 'lg:col-span-7 xl:col-span-7'
          } bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-4 sm:p-5 shadow-xs space-y-4`}
        >
          {mainSection === 'studio' && (
            <>
              {/* Config Tabs */}
              <SlidingTabs
                tabs={[
                  { id: 'prompt', label: 'System Prompt' },
                  { id: 'identity', label: 'Identitas & Cakupan' },
                  { id: 'params', label: 'Parameter Model' },
                ]}
                activeTab={activeConfigTab}
                onChange={setActiveConfigTab}
                variant="underline"
              />

              {/* ── LEFT TABS CONTENT CONTAINER (FADE ANIMATED) ──────── */}
              <div key={activeConfigTab} className="animate-fade-in">
                {/* TAB CONTENT: PROMPT SYSTEM */}
                {activeConfigTab === 'prompt' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center">
                    <label className="text-xs font-bold text-[var(--text-primary)]">
                      Instruksi Prompt Sistem
                    </label>
                    <InfoTooltip content="Instruksi sistem baku yang mendefinisikan persona bot, batasan fakta dokumen SOP, format rujukan, dan aturan salam multi-turn." />
                  </div>
                </div>

                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => handleInsertTag('{context}')}
                    className="px-2 py-1 text-xs font-mono font-semibold rounded-md bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer"
                    title="Sisipkan variabel penampung konteks dokumen"
                  >
                    + {'{context}'}
                  </button>
                  <span className="text-xs font-mono text-[var(--text-muted)] px-1.5 py-0.5 rounded bg-[var(--bg-input)]">
                    ~{approxPromptTokens} token
                  </span>
                </div>
              </div>

              <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] focus-within:border-sky-500 focus-within:ring-1 focus-within:ring-sky-500 transition-all overflow-hidden">
                <textarea
                  ref={promptTextareaRef}
                  name="rag_system_prompt"
                  value={form.rag_system_prompt}
                  onChange={handleChange}
                  rows={14}
                  placeholder="Tuliskan system prompt di sini..."
                  className="w-full p-3 font-mono text-xs leading-relaxed bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none resize-y"
                  spellCheck={false}
                />
              </div>
            </div>
          )}

          {/* TAB CONTENT: PARAMETER MODEL */}
          {activeConfigTab === 'params' && (
            <div className="space-y-4 divide-y divide-[var(--border-color)]">
              {/* LLM Model Selection & Actions */}
              <div className="pt-1 first:pt-0 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <label className="text-xs font-bold text-[var(--text-primary)]">
                      Model LLM (Ollama Engine)
                    </label>
                    <InfoTooltip content="Model bahasa kecerdasan buatan lokal yang bertugas menganalisis pertanyaan dan merumuskan jawaban berdasarkan dokumen SOP." />
                  </div>
                  <button
                    type="button"
                    onClick={handleRefreshAll}
                    disabled={loadingModels || detectingHardware}
                    title="Segarkan daftar model dan telemetri hardware"
                    className="p-1.5 rounded-md border border-[var(--border-color)] bg-[var(--bg-input)] hover:bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer flex items-center gap-1.5 text-xs"
                  >
                    <svg className={`w-3.5 h-3.5 ${(loadingModels || detectingHardware) ? 'animate-spin text-sky-500' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    <span className="text-[11px] font-medium hidden sm:inline">Segarkan</span>
                  </button>
                </div>

                {/* Model Select Dropdown & Benchmark Action Row */}
                <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
                  <div className="sm:col-span-8 relative">
                    <select
                      name="llm_model_name"
                      value={form.llm_model_name || 'qwen2.5:7b'}
                      onChange={handleModelSelectChange}
                      className="w-full px-3 py-2 text-xs font-semibold rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 cursor-pointer appearance-none pr-8 transition-colors"
                    >
                      {availableModels.length > 0 ? (
                        availableModels.map((m) => (
                          <option key={m.name} value={m.name}>
                            {m.name} ({m.size_gb} GB) — {m.badge}
                          </option>
                        ))
                      ) : (
                        <>
                          <option value="qwen2.5:3b">qwen2.5:3b (1.9 GB) — Sangat Ringan (Rekomendasi 3–5 User Bersamaan)</option>
                          <option value="qwen3:8b">qwen3:8b (5.2 GB) — Sedang (Kualitas Tinggi, 1–2 User)</option>
                        </>
                      )}
                    </select>
                    <div className="absolute inset-y-0 right-0 flex items-center px-2.5 pointer-events-none text-[var(--text-muted)]">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleRunBenchmark}
                    disabled={benchmarking}
                    className="sm:col-span-4 px-3 py-2 rounded-lg font-medium text-xs transition-colors flex items-center justify-center gap-1.5 bg-[var(--bg-input)] hover:bg-[var(--bg-hover)] border border-[var(--border-color)] text-[var(--text-primary)] cursor-pointer disabled:opacity-50"
                  >
                    {benchmarking ? (
                      <>
                        <span className="w-3.5 h-3.5 border-2 border-[var(--text-muted)] border-t-[var(--brand-primary)] rounded-full animate-spin" />
                        <span className="truncate">Menguji 40 Token...</span>
                      </>
                    ) : (
                      <>
                        <svg className="w-3.5 h-3.5 text-[var(--brand-primary)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        <span className="truncate">Uji Kecepatan Nyata</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Benchmark Result View (Flat Structure - No nested cards) */}
                {benchmarkResult && (
                  <div className="p-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] space-y-2 text-xs animate-fade-in">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5 font-semibold text-[var(--text-primary)]">
                        <svg className="w-3.5 h-3.5 text-[var(--brand-primary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        <span>Benchmark: <span className="font-mono text-[var(--brand-primary)]">{benchmarkResult.model}</span></span>
                      </div>
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">
                        {benchmarkResult.tested_at}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-3 pt-2 border-t border-[var(--border-color)]">
                      <div>
                        <span className="text-[10px] text-[var(--text-muted)] block">Kecepatan Nyata</span>
                        <span className="text-base font-bold text-[var(--action-green)] font-mono block">
                          {benchmarkResult.tokens_per_second} <span className="text-[11px] font-normal text-[var(--text-muted)]">tok/s</span>
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[var(--text-muted)] block">First-Token (TTFT)</span>
                        <span className="text-base font-bold text-[var(--text-primary)] font-mono block">
                          {benchmarkResult.time_to_first_token_ms} <span className="text-[11px] font-normal text-[var(--text-muted)]">ms</span>
                        </span>
                      </div>
                      <div>
                        <span className="text-[10px] text-[var(--text-muted)] block">Durasi Inferensi</span>
                        <span className="text-base font-bold text-[var(--text-primary)] font-mono block">
                          {(benchmarkResult.eval_duration_ms / 1000).toFixed(2)} <span className="text-[11px] font-normal text-[var(--text-muted)]">detik</span>
                        </span>
                      </div>
                    </div>

                    {benchmarkResult.sample_output && (
                      <div className="p-2 rounded bg-[var(--bg-card)] border border-[var(--border-color)] text-[11px] font-mono text-[var(--text-secondary)] italic line-clamp-2">
                        "{benchmarkResult.sample_output}"
                      </div>
                    )}
                  </div>
                )}

                {/* Telemetri Hardware (Flat Structure with Progressive Disclosure) */}
                {hardwareData && (
                  <div className="p-3 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] space-y-2.5 text-xs animate-fade-in">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <svg className="w-3.5 h-3.5 text-[var(--brand-primary)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                        </svg>
                        <span className="font-bold text-[var(--text-primary)]">
                          Telemetri Hardware
                        </span>
                        <InfoTooltip content="Pemantauan alokasi VRAM GPU dan RAM sistem server secara langsung." />
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[var(--bg-card)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                        {hardwareData.gpu?.nama || 'Mode CPU'} • {hardwareData.sistem?.is_wsl ? 'WSL2' : 'Bare-Metal'}
                      </span>
                    </div>

                    {/* GPU VRAM & System RAM Live Meters */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1 border-t border-[var(--border-color)]">
                      {/* GPU VRAM Meter */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-medium text-[var(--text-primary)]">
                            VRAM GPU: <span className="font-mono text-[var(--text-secondary)]">{((hardwareData.gpu?.vram_dipakai_mib || 0)/1024).toFixed(1)} / {((hardwareData.gpu?.vram_total_mib || 0)/1024).toFixed(1)} GB</span>
                          </span>
                          <span className="font-mono text-[10px] text-[var(--action-green)] font-semibold">
                            Bebas {((hardwareData.gpu?.vram_bebas_mib || 0)/1024).toFixed(1)} GB
                          </span>
                        </div>
                        {hardwareData.gpu ? (
                          <div className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-full h-1.5 overflow-hidden flex">
                            <div
                              className={`h-full transition-all ${
                                (hardwareData.gpu.vram_dipakai_mib / (hardwareData.gpu.vram_total_mib || 1)) > 0.85
                                  ? 'bg-[var(--red-color)]'
                                  : (hardwareData.gpu.vram_dipakai_mib / (hardwareData.gpu.vram_total_mib || 1)) > 0.65
                                    ? 'bg-[var(--yellow-color)]'
                                    : 'bg-[var(--brand-primary)]'
                              }`}
                              style={{ width: `${Math.min(100, Math.round((hardwareData.gpu.vram_dipakai_mib / (hardwareData.gpu.vram_total_mib || 1)) * 100))}%` }}
                            />
                          </div>
                        ) : null}
                      </div>

                      {/* System RAM Meter */}
                      <div className="space-y-1">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-medium text-[var(--text-primary)]">
                            RAM Sistem: <span className="font-mono text-[var(--text-secondary)]">{((hardwareData.ram?.ram_dipakai_mib || 0)/1024).toFixed(1)} / {((hardwareData.ram?.ram_total_mib || 0)/1024).toFixed(1)} GB</span>
                          </span>
                          <span className="font-mono text-[10px] text-[var(--action-green)] font-semibold">
                            Bebas {((hardwareData.ram?.ram_bebas_mib || 0)/1024).toFixed(1)} GB
                          </span>
                        </div>
                        {hardwareData.ram && (
                          <div className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-full h-1.5 overflow-hidden flex">
                            <div
                              className="bg-[var(--brand-primary)] h-full transition-all"
                              style={{ width: `${Math.min(100, Math.round((hardwareData.ram.ram_dipakai_mib / (hardwareData.ram.ram_total_mib || 1)) * 100))}%` }}
                            />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Model Fit Summary & Progressive Disclosure Toggle */}
                    {hardwareData.model_fit && (
                      <div className="pt-1.5 border-t border-[var(--border-color)] space-y-1.5">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-1.5 font-medium text-[var(--text-primary)] text-[11px]">
                            {hardwareData.model_fit.fit_status === 'optimal' ? (
                              <svg className="w-3.5 h-3.5 text-[var(--action-green)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                              </svg>
                            ) : hardwareData.model_fit.fit_status === 'shared_warning' ? (
                              <svg className="w-3.5 h-3.5 text-[var(--yellow-color)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                              </svg>
                            ) : hardwareData.model_fit.fit_status === 'exceeds_gpu' ? (
                              <svg className="w-3.5 h-3.5 text-[var(--red-color)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            ) : (
                              <svg className="w-3.5 h-3.5 text-[var(--brand-primary)] shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                            )}
                            <span>{hardwareData.model_fit.fit_badge}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => setShowHardwareDetails((prev) => !prev)}
                            className="text-[10px] font-mono text-[var(--text-muted)] hover:text-[var(--brand-primary)] transition-colors cursor-pointer"
                          >
                            {showHardwareDetails ? 'Tutup Rincian ▲' : 'Rincian Kalkulasi ▼'}
                          </button>
                        </div>

                        {showHardwareDetails && (
                          <div className="p-2 rounded bg-[var(--bg-card)] border border-[var(--border-color)] space-y-1.5 text-[11px] animate-fade-in">
                            <p className="text-[var(--text-secondary)] leading-relaxed m-0">
                              {hardwareData.model_fit.fit_message}
                            </p>
                            <div className="flex flex-wrap items-center gap-3 text-[10px] font-mono text-[var(--text-muted)] pt-1 border-t border-[var(--border-color)]">
                              <span>Bobot Model: ~{(hardwareData.model_fit.model_weight_mib / 1024).toFixed(1)} GB</span>
                              <span>•</span>
                              <span>KV Cache ({form.rag_num_ctx || 6144} ctx): ~{(hardwareData.model_fit.kv_cache_mib / 1024).toFixed(1)} GB</span>
                              <span>•</span>
                              <span>Total Kebutuhan: ~{hardwareData.model_fit.total_required_gb} GB</span>
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Temperature (Kreativitas Jawaban) */}
              <div className="pt-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <label className="text-xs font-bold text-[var(--text-primary)]">
                      Kreativitas (Temperature)
                    </label>
                    <InfoTooltip content="Mengontrol variasi jawaban. Nilai rendah (0.0–0.2) sangat patuh dan faktual terhadap teks SOP. Nilai tinggi membuat bahasa lebih luwes dan variatif." />
                  </div>
                  <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)]">
                    {form.rag_temperature <= 0.1
                      ? `${form.rag_temperature} • Sangat Faktual`
                      : form.rag_temperature <= 0.3
                        ? `${form.rag_temperature} • Rekomendasi SOP`
                        : form.rag_temperature <= 0.6
                          ? `${form.rag_temperature} • Seimbang`
                          : `${form.rag_temperature} • Kreatif`}
                  </span>
                </div>
                <input
                  type="range"
                  name="rag_temperature"
                  min="0"
                  max="1"
                  step="0.05"
                  value={form.rag_temperature}
                  onChange={handleChange}
                  className="w-full accent-sky-500 cursor-pointer"
                />
              </div>

              {/* Top-K Chunks (Rujukan Dokumen) */}
              <div className="pt-3 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <label className="text-xs font-bold text-[var(--text-primary)]">
                      Rujukan Dokumen (Top-K)
                    </label>
                    <InfoTooltip content="Jumlah potongan (chunk) teks dokumen SOP paling relevan yang diambil dari basis data vektor untuk dijadikan bahan referensi LLM." />
                  </div>
                  <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)]">
                    {form.rag_top_k <= 4
                      ? `${form.rag_top_k} Chunks • Ringkas`
                      : form.rag_top_k <= 10
                        ? `${form.rag_top_k} Chunks • Rekomendasi`
                        : `${form.rag_top_k} Chunks • Daftar Panjang`}
                  </span>
                </div>
                <input
                  type="range"
                  name="rag_top_k"
                  min="1"
                  max="20"
                  step="1"
                  value={form.rag_top_k}
                  onChange={handleChange}
                  className="w-full accent-sky-500 cursor-pointer"
                />
              </div>

              {/* Context Window (Jendela Konteks) */}
              <div className="pt-3 space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <label className="text-xs font-bold text-[var(--text-primary)]">
                      Jendela Konteks (Context Window)
                    </label>
                    <InfoTooltip content="Kapasitas memori token input dokumen + teks jawaban dalam 1 sesi inferensi." />
                  </div>
                  <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)]">
                    {(form.rag_num_ctx || 6144).toLocaleString('id-ID')} Token
                  </span>
                </div>

                {/* Segmented Pill Selector (1-Click Presets) */}
                <div className="grid grid-cols-5 gap-1.5">
                  {[
                    { ctx: 2048, label: 'Hemat' },
                    { ctx: 4096, label: 'Standar' },
                    { ctx: 6144, label: hardwareData?.rekomendasi?.recommended_num_ctx === 6144 ? 'Optimal GPU' : 'GPU 6GB' },
                    { ctx: 8192, label: 'Panjang' },
                    { ctx: 16384, label: 'Maksimal' },
                  ].map((item) => {
                    const isSelected = form.rag_num_ctx === item.ctx
                    return (
                      <button
                        key={item.ctx}
                        type="button"
                        onClick={() => setForm((prev) => ({ ...prev, rag_num_ctx: item.ctx }))}
                        className={`py-1.5 px-1 text-center rounded-md border text-xs transition-colors cursor-pointer ${
                          isSelected
                            ? 'bg-[var(--brand-primary)] text-white border-[var(--brand-primary)] font-semibold'
                            : 'bg-[var(--bg-input)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-secondary)]'
                        }`}
                      >
                        <span className="block text-[11px] font-mono font-semibold">{item.ctx >= 1024 ? `${item.ctx / 1024}K` : item.ctx}</span>
                        <span className="block text-[9px] opacity-80 truncate">{item.label}</span>
                      </button>
                    )
                  })}
                </div>

                {/* Slider fine-tuning */}
                <input
                  type="range"
                  name="rag_num_ctx"
                  min="1024"
                  max="16384"
                  step="1024"
                  value={form.rag_num_ctx || 6144}
                  onChange={handleChange}
                  className="w-full accent-sky-500 cursor-pointer"
                />
              </div>

              {/* Citations Toggle */}
              <div className="pt-3 flex items-center justify-between">
                <div className="flex items-center">
                  <label className="text-xs font-bold text-[var(--text-primary)] cursor-pointer" htmlFor="citation_toggle">
                    Sitasi Rujukan Dokumen
                  </label>
                  <InfoTooltip content="Sertakan nama berkas SOP dan nomor halaman rujukan di akhir teks jawaban chatbot." />
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    id="citation_toggle"
                    type="checkbox"
                    name="rag_citation_enabled"
                    checked={form.rag_citation_enabled}
                    onChange={handleChange}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-[var(--bg-input)] peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-sky-600 border border-[var(--border-color)]"></div>
                  <span className="ml-3 text-xs text-[var(--text-secondary)] font-medium">
                    {form.rag_citation_enabled ? 'Aktif' : 'Nonaktif'}
                  </span>
                </label>
              </div>

              {/* Fallback Message */}
              <div className="pt-3 space-y-1.5">
                <div className="flex items-center">
                  <label className="text-xs font-bold text-[var(--text-primary)]">
                    Pesan Jawaban Fallback
                  </label>
                  <InfoTooltip content="Pesan standar yang dikirimkan kepada pengguna jika informasi yang dicari tidak ditemukan di dokumen SOP manapun." />
                </div>
                <textarea
                  name="chatbot_fallback_message"
                  value={form.chatbot_fallback_message}
                  onChange={handleChange}
                  rows={2}
                  className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors resize-y leading-relaxed"
                />
              </div>
            </div>
          )}

          {/* TAB CONTENT: IDENTITAS & FILTER DOKUMEN */}
          {activeConfigTab === 'identity' && (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <div className="flex items-center">
                  <label className="text-xs font-bold text-[var(--text-primary)]">
                    Nama Asisten
                  </label>
                  <InfoTooltip content="Nama identitas chatbot resmi yang ditampilkan kepada masyarakat dan ASN saat berinteraksi." />
                </div>
                <input
                  type="text"
                  name="chatbot_name"
                  value={form.chatbot_name}
                  onChange={handleChange}
                  placeholder="Asisten Virtual Diskominfotik"
                  className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
                />
              </div>

              <div className="space-y-1.5">
                <div className="flex items-center">
                  <label className="text-xs font-bold text-[var(--text-primary)]">
                    Pesan Sambutan Awal
                  </label>
                  <InfoTooltip content="Pesan pembuka otomatis yang dikirimkan oleh asisten virtual pada awal sesi percakapan baru." />
                </div>
                <textarea
                  name="chatbot_greeting"
                  value={form.chatbot_greeting}
                  onChange={handleChange}
                  rows={2}
                  className="w-full px-3 py-2 text-xs rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors resize-y leading-relaxed"
                />
              </div>

              {/* Scope Document Filter for Testing */}
              <div className="pt-2 border-t border-[var(--border-color)] space-y-2">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="flex items-center">
                      <label className="text-xs font-bold text-[var(--text-primary)]">
                        Batasan Dokumen Pengujian (Scope)
                      </label>
                      <InfoTooltip content="Pilih satu atau beberapa dokumen SOP spesifik untuk mengisolasi dan menguji akurasi retrieval pada berkas tertentu saja." />
                    </div>
                  </div>
                  {selectedDocIds.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedDocIds([])}
                      className="text-xs font-semibold text-rose-500 hover:underline cursor-pointer"
                    >
                      Reset Filter
                    </button>
                  )}
                </div>

                <div className="max-h-36 overflow-y-auto space-y-1.5 p-2 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)]/50">
                  {availableDocs.length === 0 ? (
                    <p className="text-xs text-[var(--text-muted)] py-2 text-center">
                      Belum ada dokumen aktif di database.
                    </p>
                  ) : (
                    availableDocs.map((doc) => {
                      const docId = Number(doc.id)
                      const isChecked = selectedDocIds.map(Number).includes(docId)
                      return (
                        <label
                          key={doc.id}
                          className="flex items-center gap-2 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-input)] p-1 rounded cursor-pointer select-none transition-colors"
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedDocIds([...selectedDocIds, docId])
                              } else {
                                setSelectedDocIds(selectedDocIds.filter((id) => Number(id) !== docId))
                              }
                            }}
                            className="rounded border-[var(--border-color)] text-sky-500 focus:ring-sky-500"
                          />
                          <span className="truncate font-medium flex-1">
                            {doc.title || doc.original_filename}
                          </span>
                          <span className="text-xs text-[var(--text-muted)] px-1.5 py-0.5 rounded bg-[var(--bg-input)]">
                            ID #{doc.id}
                          </span>
                        </label>
                      )
                    })
                  )}
                </div>

                <p className="text-xs text-[var(--text-muted)]">
                  {selectedDocIds.length === 0
                    ? 'Mencari di seluruh dokumen korpus (Default).'
                    : `Dibatasi pada ${selectedDocIds.length} dokumen terpilih.`}
                </p>
              </div>
            </div>
          )}
          </div>
        </>
      )}

      {/* SECTION CONTENT: FAST-PATH & FAQ DINAMIS */}
      {mainSection === 'fastpaths' && (
        <div key="fastpaths" className="animate-fade-in">
          <FastPathSettings />
        </div>
      )}

      {/* SECTION CONTENT: DIREKTORI UNIT KERJA & BIDANG */}
      {mainSection === 'directories' && (
        <div key="directories" className="animate-fade-in">
          <DirectorySettings />
        </div>
      )}
    </div>

    {/* ── RIGHT COLUMN: INTERACTIVE PLAYGROUND & INSPECTOR ─── */}
    <div
      ref={rightCardRef}
      className={`${
        mainSection === 'studio'
          ? 'lg:col-span-6 xl:col-span-7'
          : 'lg:col-span-5 xl:col-span-5'
      } bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs overflow-hidden flex flex-col min-h-[560px]`}
    >
          {/* Top Tabs */}
          <div className="p-3 sm:px-4 bg-[var(--bg-input)]/40 border-b border-[var(--border-color)] flex items-center justify-between gap-2 flex-wrap">
            <SlidingTabs
              tabs={[
                { id: 'chat', label: 'Simulasi Obrolan' },
                {
                  id: 'chunks',
                  label: `Inspeksi Retrieval (${retrievedChunks.length})`,
                },
                { id: 'api', label: 'Contoh Integrasi' },
              ]}
              activeTab={activePlaygroundTab}
              onChange={setActivePlaygroundTab}
              variant="pill"
            />

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleClearChat}
                className="px-2.5 py-1.5 text-xs font-medium rounded-lg text-[var(--text-secondary)] hover:text-[var(--red-color)] hover:bg-[var(--bg-input)] border border-[var(--border-color)] transition-colors cursor-pointer flex items-center gap-1.5"
                title="Bersihkan riwayat obrolan"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                </svg>
                <span>Bersihkan</span>
              </button>
            </div>
          </div>

          {/* ── RIGHT TABS CONTENT CONTAINER (FADE ANIMATED) ───────── */}
          <div key={activePlaygroundTab} className="animate-fade-in flex-1 flex flex-col justify-between">
            {/* TAB 1: LIVE CHAT SIMULATOR */}
            {activePlaygroundTab === 'chat' && (
            <div className="flex-1 flex flex-col justify-between p-4 sm:p-5 space-y-4">
              {/* Message Feed */}
              <div className="space-y-3.5 overflow-y-auto max-h-[400px] pr-1.5">
                {chatMessages.map((msg) => {
                  const isUser = msg.role === 'user'
                  return (
                    <div
                      key={msg.id}
                      className={`flex gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
                    >
                      {!isUser && (
                        <div className="w-7 h-7 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] flex items-center justify-center shrink-0">
                          <svg className="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <rect x="3" y="11" width="18" height="10" rx="2" strokeWidth={1.75} />
                            <circle cx="12" cy="5" r="3" strokeWidth={1.75} />
                            <line x1="8" y1="16" x2="8" y2="16.01" strokeWidth={2} strokeLinecap="round" />
                            <line x1="16" y1="16" x2="16" y2="16.01" strokeWidth={2} strokeLinecap="round" />
                          </svg>
                        </div>
                      )}

                      <div
                        className={`max-w-[85%] rounded-xl px-4 py-3 text-xs leading-relaxed transition-all shadow-xs ${
                          isUser
                            ? 'bg-sky-600 text-white rounded-tr-none font-normal'
                            : msg.isError
                              ? 'bg-[var(--bg-input)] text-[var(--red-color)] border border-[var(--border-color)] rounded-tl-none'
                              : 'bg-[var(--bg-input)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-tl-none'
                        }`}
                      >
                        {msg.content ? (
                          <div className="whitespace-pre-wrap">{msg.content}</div>
                        ) : msg.isStreaming ? (
                          <div className="text-[var(--text-muted)] italic text-[11px]">
                            Memulai pipeline retrieval dan inferensi AI...
                          </div>
                        ) : null}

                        {/* Live Pipeline Tracing Stepper */}
                        {msg.isStreaming && (
                          <div className="mt-3 pt-2.5 border-t border-[var(--border-color)] space-y-2">
                            <div className="p-2.5 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] space-y-2">
                              <div className="flex items-center justify-between text-[11px] font-bold text-[var(--text-primary)]">
                                <span className="uppercase tracking-wider">Tahapan Pipeline AI</span>
                                <span className="font-mono text-[var(--text-muted)]">
                                  Langkah {msg.trace?.step || 1} dari {msg.trace?.totalSteps || 3}
                                </span>
                              </div>

                              <div className="grid grid-cols-3 gap-1.5">
                                {[
                                  { step: 1, label: '1. Retrieval' },
                                  { step: 2, label: '2. Reranking' },
                                  { step: 3, label: '3. LLM Gen' },
                                ].map((s) => {
                                  const currentStep = msg.trace?.step || 1
                                  const isCurrent = currentStep === s.step
                                  const isPassed = currentStep > s.step
                                  return (
                                    <div
                                      key={s.step}
                                      className={`px-1.5 py-1 rounded text-[10px] font-semibold text-center border transition-all truncate ${
                                        isPassed
                                          ? 'bg-[var(--bg-input)] text-[var(--action-green)] border-[var(--border-color)]'
                                          : isCurrent
                                            ? 'bg-[var(--brand-primary)] text-white border-[var(--brand-primary)] font-bold'
                                            : 'bg-[var(--bg-input)] text-[var(--text-muted)] border-[var(--border-color)] opacity-60'
                                      }`}
                                    >
                                      {s.label}
                                    </div>
                                  )
                                })}
                              </div>

                              <div className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)]">
                                <div className="w-3 h-3 border-2 border-[var(--text-muted)] border-t-[var(--brand-primary)] rounded-full animate-spin shrink-0" />
                                <span className="truncate font-medium">
                                  {msg.trace?.detail || 'Menghubungkan ke basis data vektor...'}
                                </span>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Completed Telemetry Footer */}
                        {!msg.isStreaming && !isUser && !msg.isError && msg.content && msg.content.trim().length > 0 && msg.id !== 'init-greeting' && msg.id !== 'new-session' && (
                          <div className="mt-2.5 pt-2 border-t border-[var(--border-color)]/50 flex items-center justify-between gap-2 text-[10px] font-mono text-[var(--text-muted)] flex-wrap">
                            <div className="flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 font-semibold text-[var(--text-secondary)]">
                                <svg className="w-3 h-3 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4.5 12.75l6 6 9-13.5" />
                                </svg>
                                {msg.telemetry?.isFallback ? 'Fallback (Luar SOP)' : 'Terjawab dari Korpus'}
                              </span>
                              <span>•</span>
                              <span>{msg.telemetry?.modelName || form.llm_model_name || 'qwen2.5:7b'}</span>
                              {typeof msg.telemetry?.contextTokens === 'number' && msg.telemetry.contextTokens > 0 && (
                                <>
                                  <span>•</span>
                                  <span>~{msg.telemetry.contextTokens} token</span>
                                </>
                              )}
                            </div>
                            <div className="flex items-center gap-2">
                              {typeof msg.telemetry?.chunksCount === 'number' && msg.telemetry.chunksCount > 0 && (
                                <button
                                  type="button"
                                  onClick={() => setActivePlaygroundTab('chunks')}
                                  className="text-sky-500 hover:underline cursor-pointer"
                                  title="Lihat potongan teks yang terambil di tab Inspeksi Retrieval"
                                >
                                  {msg.telemetry.chunksCount} Chunk Terambil
                                </button>
                              )}
                              {msg.elapsedMs && (
                                <span className="px-1.5 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border-color)]">
                                  {msg.elapsedMs} ms
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
                <div ref={chatBottomRef} />
              </div>

              {/* Quick Questions Pills */}
              <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]">
                <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">
                  Contoh Pertanyaan Pengujian:
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {quickQuestions.map((q, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => handleSendChat(q)}
                      disabled={isStreaming}
                      className="px-2.5 py-1 rounded-md text-xs font-medium bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-secondary)] border border-[var(--border-color)] transition-colors cursor-pointer disabled:opacity-50 text-left"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>

              {/* Chat Input Bar */}
              <form
                onSubmit={(e) => {
                  e.preventDefault()
                  handleSendChat()
                }}
                className="flex items-center gap-2 pt-2"
              >
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ketik pertanyaan untuk menguji RAG secara langsung..."
                  disabled={isStreaming}
                  className="flex-1 px-3.5 py-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
                />

                {isStreaming ? (
                  <button
                    type="button"
                    onClick={handleStopStream}
                    className="px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all hover:scale-105 cursor-pointer shadow-sm"
                  >
                    Hentikan
                  </button>
                ) : (
                  <button
                    type="submit"
                    disabled={!chatInput.trim() || isStreaming}
                    className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 font-bold text-xs shadow-md shadow-sky-500/25 transition-all hover:scale-[1.02] disabled:opacity-50 cursor-pointer flex items-center gap-1.5"
                  >
                    <span>Kirim</span>
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                    </svg>
                  </button>
                )}
              </form>
            </div>
          )}

          {/* TAB 2: RETRIEVAL CHUNKS INSPECTOR */}
          {activePlaygroundTab === 'chunks' && (
            <div className="p-4 sm:p-5 flex-1 overflow-y-auto max-h-[500px] space-y-3.5">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center">
                    <span>Potongan Dokumen Terambil (Two-Stage RAG)</span>
                    <InfoTooltip content="Daftar teks konteks asli dari ChromaDB dan BGE-Reranker yang disuntikkan ke variabel {context} LLM untuk menjawab pertanyaan terakhir." />
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">
                    Daftar teks konteks asli dari ChromaDB dan BGE-Reranker untuk pertanyaan terakhir.
                  </p>
                </div>
                <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)]">
                  {retrievedChunks.length} Chunks
                </span>
              </div>

              {retrievedChunks.length === 0 ? (
                <div className="p-8 text-center bg-[var(--bg-input)]/30 border border-dashed border-[var(--border-color)] rounded-xl space-y-1.5">
                  <p className="text-xs font-semibold text-[var(--text-primary)]">Belum ada data retrieval</p>
                  <p className="text-xs text-[var(--text-muted)] max-w-sm mx-auto">
                    Kirim pertanyaan di tab Simulasi Obrolan untuk memeriksa transparansi potongan teks yang diambil.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {retrievedChunks.map((chunk, idx) => (
                    <div
                      key={chunk.id || idx}
                      className="p-3.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] space-y-2"
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2">
                          <span className="w-5 h-5 rounded bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-secondary)] text-xs font-mono font-semibold flex items-center justify-center">
                            {idx + 1}
                          </span>
                          <span className="text-xs font-semibold text-[var(--text-primary)]">
                            {chunk.document_name || `Dokumen #${chunk.document_id}`}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium px-2 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-secondary)]">
                            Halaman {chunk.page_number}
                          </span>
                          {chunk.rerank_score !== undefined && (
                            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-[var(--bg-card)] text-[var(--brand-primary)] border border-[var(--border-color)]">
                              Rerank: {chunk.rerank_score}
                            </span>
                          )}
                          {chunk.rrf_score !== undefined && (
                            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded bg-[var(--bg-card)] text-[var(--action-green)] border border-[var(--border-color)]">
                              RRF: {chunk.rrf_score}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="p-3 rounded bg-[var(--bg-card)] border border-[var(--border-color)] text-xs font-mono leading-relaxed text-[var(--text-secondary)] max-h-40 overflow-y-auto whitespace-pre-wrap">
                        {chunk.content}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: API CODE EXPORTER */}
          {activePlaygroundTab === 'api' && (
            <div className="p-4 sm:p-5 flex-1 overflow-y-auto max-h-[500px] space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-xs font-bold text-[var(--text-primary)] uppercase tracking-wider flex items-center">
                    <span>Contoh Integrasi API</span>
                    <InfoTooltip content="Cuplikan kode pemanggilan API mikroservis AI untuk pengembang sistem lain (WhatsApp, Telegram, atau Web Widget)." />
                  </h3>
                  <p className="text-xs text-[var(--text-muted)]">
                    Cuplikan kode pemanggilan API mikroservis AI untuk pengembang sistem lain.
                  </p>
                </div>

                {/* Language Switcher */}
                <SlidingTabs
                  tabs={[
                    { id: 'curl', label: 'CURL' },
                    { id: 'python', label: 'PYTHON' },
                    { id: 'js', label: 'JS' },
                  ]}
                  activeTab={apiCodeLang}
                  onChange={setApiCodeLang}
                  variant="pill"
                  size="xs"
                  className="bg-[var(--bg-input)]"
                />
              </div>

              <div key={apiCodeLang} className="animate-fade-in relative rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)]/80 p-4 font-mono text-xs leading-relaxed text-[var(--text-primary)] overflow-x-auto">
                <button
                  type="button"
                  onClick={() => handleCopyCode(generateApiSnippet())}
                  className="absolute top-3 right-3 px-3 py-1.5 rounded-md text-xs font-medium bg-[var(--bg-card)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    {copiedCode ? (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.5 12.75l6 6 9-13.5" />
                    ) : (
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                    )}
                  </svg>
                  <span>{copiedCode ? 'Tersalin' : 'Salin Kode'}</span>
                </button>
                <pre className="whitespace-pre">{generateApiSnippet()}</pre>
              </div>

              <div className="p-3.5 bg-[var(--bg-input)]/40 border border-[var(--border-color)] rounded-lg text-xs space-y-1 text-[var(--text-secondary)]">
                <div className="font-semibold text-[var(--text-primary)]">Catatan Teknis Integrasi:</div>
                <p className="text-xs leading-relaxed text-[var(--text-muted)]">
                  Gunakan endpoint <code className="font-mono bg-[var(--bg-card)] px-1 py-0.5 rounded border border-[var(--border-color)]">POST /api/v1/chat</code> (format JSON standar) untuk WhatsApp bot dan integrasi backend. Untuk widget web interaktif dengan streaming kata-per-kata, gunakan endpoint <code className="font-mono bg-[var(--bg-card)] px-1 py-0.5 rounded border border-[var(--border-color)]">POST /api/v1/chat/stream</code> (SSE). Kunci API dapat dikelola pada menu <strong>Kunci API</strong>.
                </p>
              </div>
            </div>
          )}
          </div>
        </div>
      </div>

      {/* ── FLOATING SAVE BAR (DIRTY STATE) ─────────────────────── */}
      <FloatingSaveBar
        show={isDirty && mainSection === 'studio'}
        onSave={handleSubmit}
        onDiscard={handleDiscard}
        saving={saving}
      />

      {/* ── RESET CONFIRMATION MODAL ────────────────────────────── */}
      {showResetModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl max-w-sm w-full p-5 shadow-xl space-y-4">
            <div className="space-y-1.5">
              <h3 className="text-sm font-bold text-[var(--text-primary)]">
                Reset Konfigurasi?
              </h3>
              <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                Seluruh konfigurasi prompt, persona, dan parameter inferensi AI akan dikembalikan ke pengaturan bawaan awal.
              </p>
            </div>
            <div className="flex justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowResetModal(false)}
                className="px-3.5 py-1.5 rounded-lg text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-input)] transition-colors cursor-pointer"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white transition-colors cursor-pointer shadow-xs"
              >
                Ya, Reset
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
