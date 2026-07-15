import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { authApi } from '../api/auth'
import styles from './LoginPage.module.css'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const email = searchParams.get('email')

  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password !== passwordConfirm) {
      return setError('Konfirmasi password tidak cocok.')
    }

    setError('')
    setLoading(true)

    try {
      await authApi.resetPassword(token, email, password, passwordConfirm)
      // Login langsung atau arahkan ke login dengan success state?
      // Arahkan ke login saja.
      navigate('/login') // Idealnya kirim state message success
    } catch (err) {
      setError(err.response?.data?.message || 'Gagal mereset password.')
    } finally {
      setLoading(false)
    }
  }

  if (!token || !email) {
    return (
      <div className={`fade-in ${styles.container}`}>
        <div className={styles.card} style={{ textAlign: 'center' }}>
          <h2 className={styles.title}>Link Tidak Valid</h2>
          <p className={styles.subtitle} style={{ marginBottom: '20px' }}>Token atau email tidak ditemukan di URL.</p>
          <button className={styles.submitBtn} onClick={() => navigate('/login')}>
            Kembali ke Login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className={`fade-in ${styles.container}`}>
      <div className={styles.glowBg}></div>
      <div className={styles.card}>
        <div className={styles.header}>
          <div className={styles.logoBox}>
            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <h1 className={styles.title}>Buat Password Baru</h1>
          <p className={styles.subtitle}>Masukkan password baru untuk {email}</p>
        </div>

        {error && <div className={styles.alert}>{error}</div>}

        <form onSubmit={handleSubmit} className={styles.form}>
          <div className={styles.formGroup}>
            <label htmlFor="password">Password Baru</label>
            <div className={styles.inputWrapper}>
              <input
                id="password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Minimal 8 karakter"
                required
                disabled={loading}
              />
              <button type="button" className={styles.eyeBtn} onClick={() => setShowPassword(!showPassword)} tabIndex="-1">
                {showPassword ? (
                  <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" /></svg>
                ) : (
                  <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                )}
              </button>
            </div>
          </div>

          <div className={styles.formGroup}>
            <label htmlFor="passwordConfirm">Konfirmasi Password</label>
            <div className={styles.inputWrapper}>
              <input
                id="passwordConfirm"
                type={showPassword ? 'text' : 'password'}
                value={passwordConfirm}
                onChange={(e) => setPasswordConfirm(e.target.value)}
                placeholder="Ketik ulang password baru"
                required
                disabled={loading}
              />
            </div>
          </div>

          <button type="submit" className={styles.submitBtn} disabled={loading} style={{ marginTop: '32px' }}>
            {loading ? <span className={styles.spinner}></span> : 'Reset Password'}
          </button>
        </form>
      </div>
    </div>
  )
}
