import { useState } from "react";
import { updateTelegramSettings, testTelegramConnection, setTelegramWebhook } from "../../api/settings";
import { addAppNotification } from "../../utils/notifications";

/** Snapshot form Telegram, dirty state, uji koneksi, dan registrasi webhook. */
export function useIntegrationTelegram({ setStatusMsg }) {
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

  return {
    setInitialTgForm,
    tgForm,
    setTgForm,
    isTgDirty,
    savingTg,
    showTgToken,
    setShowTgToken,
    tgTestChatId,
    setTgTestChatId,
    tgTestMsg,
    setTgTestMsg,
    testingTgSend,
    tgTestResult,
    setCopiedTgWebhook,
    registeringWebhook,
    webhookResult,
    handleTgChange,
    handleDiscardTg,
    handleTgSubmit,
    handleTestSendTg,
    handleAutoRegisterWebhook,
  };
}
