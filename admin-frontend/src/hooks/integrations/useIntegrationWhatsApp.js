import { useState } from "react";
import { updateWhatsappSettings, testWhatsappConnection } from "../../api/settings";
import { addAppNotification } from "../../utils/notifications";

/** Snapshot form WhatsApp, dirty state, simpan/batal, dan uji koneksi. */
export function useIntegrationWhatsApp({ setStatusMsg }) {
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

  return {
    setInitialWaForm,
    waForm,
    setWaForm,
    isWaDirty,
    savingWa,
    showWaToken,
    setShowWaToken,
    testPhone,
    setTestPhone,
    testMsgText,
    setTestMsgText,
    testingSend,
    testResult,
    copiedWebhook,
    setCopiedWebhook,
    copiedVerifyToken,
    setCopiedVerifyToken,
    handleWaChange,
    handleDiscardWa,
    handleWaSubmit,
    handleTestSendWa,
  };
}
