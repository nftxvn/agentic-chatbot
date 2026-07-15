import { useState, useEffect } from 'react'
import { getWhatsappSettings, updateWhatsappSettings } from '../api/settings'
import styles from './WhatsappSettingsPage.module.css'

export default function WhatsappSettingsPage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showToken, setShowToken] = useState(false)
  const [statusMsg, setStatusMsg] = useState(null)
  
  const [form, setForm] = useState({
    wa_status: false,
    wa_api_url: '',
    wa_token: '',
    wa_phone_number: ''
  })

  useEffect(() => {
    fetchSettings()
  }, [])

  async function fetchSettings() {
    try {
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
      setLoading(false)
    }
  }

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }))
    setStatusMsg(null) // clear status when user types
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSaving(true)
    setStatusMsg(null)
    try {
      const res = await updateWhatsappSettings(form)
      setStatusMsg({ type: 'success', text: res.message || 'Pengaturan berhasil disimpan!' })
      // re-fetch to get masked token
      await fetchSettings()
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: err.response?.data?.message || 'Gagal menyimpan pengaturan.' })
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className={styles.container}>Loading settings...</div>

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1>Pengaturan WhatsApp</h1>
        <p>Konfigurasi endpoint dan kredensial WhatsApp Business API Anda.</p>
      </div>

      <div className={styles.card}>
        <form onSubmit={handleSubmit}>
          
          <div className={styles.toggleContainer}>
            <div className={styles.toggleLabel}>
              <span className={styles.toggleTitle}>Aktifkan Chatbot WhatsApp</span>
              <span className={styles.toggleDesc}>Jika dimatikan, sistem tidak akan merespon pesan WhatsApp secara otomatis.</span>
            </div>
            <label className={styles.switch}>
              <input 
                type="checkbox" 
                name="wa_status"
                checked={form.wa_status}
                onChange={handleChange}
              />
              <span className={styles.slider}></span>
            </label>
          </div>

          <div className={styles.formGroup}>
            <label>WhatsApp API URL Endpoint</label>
            <input 
              className={styles.input}
              type="url"
              name="wa_api_url"
              value={form.wa_api_url}
              onChange={handleChange}
              placeholder="https://graph.facebook.com/v17.0/PHONE_NUMBER_ID/messages"
              required={form.wa_status} // required if enabled
            />
          </div>

          <div className={styles.formGroup}>
            <label>API Bearer Token</label>
            <div className={styles.inputWrapper}>
              <input 
                className={styles.input}
                type={showToken ? "text" : "password"}
                name="wa_token"
                value={form.wa_token}
                onChange={handleChange}
                placeholder="EAAI..."
                required={form.wa_status && !form.wa_token.includes('••••')}
              />
              <button 
                type="button" 
                className={styles.passwordToggle}
                onClick={() => setShowToken(!showToken)}
                title={showToken ? "Sembunyikan Token" : "Lihat Token"}
              >
                {showToken ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                )}
              </button>
            </div>
          </div>

          <div className={styles.formGroup}>
            <label>Nomor WhatsApp Pengirim (Opsional)</label>
            <input 
              className={styles.input}
              type="text"
              name="wa_phone_number"
              value={form.wa_phone_number}
              onChange={handleChange}
              placeholder="Misal: +6281234567890"
            />
          </div>

          <button 
            type="submit" 
            className={styles.submitBtn}
            disabled={saving}
          >
            {saving ? 'Menyimpan...' : 'Simpan Pengaturan'}
          </button>

          {statusMsg && (
            <div className={`${styles.statusMessage} ${statusMsg.type === 'success' ? styles.statusSuccess : styles.statusError}`}>
              {statusMsg.text}
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
