import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authApi } from '../api/auth'
import styles from './LoginPage.module.css' // Reusing LoginPage styles for consistency

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)

    try {
      const res = await authApi.forgotPassword(email)
      setMessage(res.message)
      setEmail('')
    } catch (err) {
      setError(err.response?.data?.message || 'Terjadi kesalahan saat mengirim link.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={`fade-in ${styles.container}`}>
      <div className={styles.glowBg}></div>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.logoBox}>
            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
            </svg>
          </div>
          <h1 className={styles.title}>Lupa Password?</h1>
          <p className={styles.subtitle}>Masukkan email Anda untuk menerima link reset password.</p>
        </div>

        {error && <div className={styles.alert}>{error}</div>}
        {message && (
          <div className={styles.alert} style={{ background: 'var(--green-bg)', color: 'var(--green-400)', borderColor: 'var(--green-border)' }}>
            {message}
          </div>
        )}

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.formGroup}>
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@diskominfotik.go.id"
              required
              disabled={loading}
            />
          </div>

          <button type="submit" className={styles.submitBtn} disabled={loading} style={{ marginBottom: '20px' }}>
            {loading ? <span className={styles.spinner}></span> : 'Kirim Link Reset'}
          </button>

          <div style={{ textAlign: 'center' }}>
            <Link to="/login" className={styles.link}>
              &larr; Kembali ke Login
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
