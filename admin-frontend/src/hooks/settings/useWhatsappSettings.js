import { useState, useEffect } from 'react'
import { getWhatsappSettings, updateWhatsappSettings, testWhatsappConnection } from '../../api/settings'
import { addAppNotification } from '../../utils/notifications'

/**
 * Form kredensial, dirty state, simpan/batal, dan uji koneksi WhatsApp.
 * Masker token diteruskan utuh ke API; salinan data awal hanya berubah saat
 * pengambilan atau penyimpanan berhasil. UI tetap memiliki clipboard dan animasi.
 */
export function useWhatsappSettings() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)

  const [testPhone, setTestPhone] = useState('')
  const [testMsgText, setTestMsgText] = useState('Halo! Ini adalah pesan uji coba koneksi gateway WhatsApp resmi Layanan Informasi Diskominfotik Kota Banda Aceh.')
  const [testingSend, setTestingSend] = useState(false)
  const [testResult, setTestResult] = useState(null)

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

  return {
    loading,
    saving,
    statusMsg,
    setStatusMsg,
    testPhone,
    setTestPhone,
    testMsgText,
    setTestMsgText,
    testingSend,
    testResult,
    form,
    isDirty,
    handleChange,
    handleDiscard,
    handleSubmit,
    handleTestSend,
  }
}
