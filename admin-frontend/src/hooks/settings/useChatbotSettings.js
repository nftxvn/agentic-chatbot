import { useState, useEffect } from 'react'
import {
  getChatbotSettings,
  updateChatbotSettings,
  resetChatbotSettings,
  getAvailableModels,
  getHardwareStatus,
  benchmarkModel,
} from '../../api/settings'
import { documentsApi } from '../../api/documents'
import { addAppNotification } from '../../utils/notifications'
import { aiChatService } from '../../services/aiChatService'

/**
 * Konfigurasi chatbot, snapshot form, katalog model, dan diagnostik hardware.
 * Greeting awal tetap diberikan ke service SSE yang persisten. Halaman tetap
 * memiliki subscription stream, navigasi tab, posisi kursor, dan animasi.
 */
export function useChatbotSettings() {

  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)

  const [showResetModal, setShowResetModal] = useState(false)

  const [hardwareData, setHardwareData] = useState(null)
  const [detectingHardware, setDetectingHardware] = useState(false)

  const [benchmarking, setBenchmarking] = useState(false)
  const [benchmarkResult, setBenchmarkResult] = useState(null)

  const [availableModels, setAvailableModels] = useState([])
  const [loadingModels, setLoadingModels] = useState(false)

  const [availableDocs, setAvailableDocs] = useState([])

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

  return {
    loading,
    saving,
    resetting,
    statusMsg,
    setStatusMsg,
    showResetModal,
    setShowResetModal,
    hardwareData,
    detectingHardware,
    benchmarking,
    benchmarkResult,
    availableModels,
    loadingModels,
    availableDocs,
    form,
    setForm,
    isDirty,
    handleDetectHardware,
    handleRefreshAll,
    handleModelSelectChange,
    handleRunBenchmark,
    handleApplyRecommendation,
    handleChange,
    handleDiscard,
    handleSubmit,
    handleReset,
  }
}
