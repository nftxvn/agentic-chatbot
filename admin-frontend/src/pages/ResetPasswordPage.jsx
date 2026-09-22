import { useState, useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import gsap from 'gsap'
import { useTheme } from '../context/ThemeContext'
import { authApi } from '../api/auth'
import { Input } from '@/components/ui/input'
import komdigiLogo from '../assets/komdigi-logo.svg'
import bandaAcehLogo from '../assets/banda-aceh-logo.svg'

export default function ResetPasswordPage() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const email = searchParams.get('email')

  const [password, setPassword] = useState('')
  const [passwordConfirm, setPasswordConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  const heroTextRef = useRef(null)
  const replacementRef = useRef(null)
  const cursorRef = useRef(null)
  const glowShape1Ref = useRef(null)
  const glowShape2Ref = useRef(null)

  const { theme, toggleTheme } = useTheme()
  const isDark = theme === 'dark'
  const navigate = useNavigate()

  const textParagraph = "Sistem manajemen dokumen cerdas berbasis RAG dan LLM untuk pelayanan publik yang responsif & terotomatisasi."
  const words = textParagraph.split(' ')
  const replacementPhrases = [
    'AI Support',
    'Layanan Publik',
    'Dokumen RAG',
    'Sistem Pintar'
  ]

  useEffect(() => {
    // Smooth random floating animation for glowing background shapes
    const floatRandomly = (element, bounds) => {
      if (!element) return
      gsap.to(element, {
        x: gsap.utils.random(-bounds.x, bounds.x),
        y: gsap.utils.random(-bounds.y, bounds.y),
        scale: gsap.utils.random(0.85, 1.25),
        duration: gsap.utils.random(4, 7),
        ease: 'sine.inOut',
        onComplete: () => floatRandomly(element, bounds)
      })
    }

    if (glowShape1Ref.current) floatRandomly(glowShape1Ref.current, { x: 80, y: 60 })
    if (glowShape2Ref.current) floatRandomly(glowShape2Ref.current, { x: 70, y: 50 })

    if (cursorRef.current) {
      gsap.to(cursorRef.current, {
        opacity: 0,
        repeat: -1,
        yoyo: true,
        duration: 0.75,
        ease: 'steps(1)'
      })
    }

    if (heroTextRef.current) {
      const lineElements = heroTextRef.current.querySelectorAll('.hero-word-inner')
      if (lineElements.length > 0) {
        gsap.fromTo(
          lineElements,
          {
            yPercent: 120,
            opacity: 0,
          },
          {
            yPercent: 0,
            opacity: 1,
            duration: 0.8,
            stagger: 0.04,
            ease: 'power3.out',
            delay: 0.1
          }
        )
      }
    }

    // GSAP Typewriter Animation Loop with Blinking Text Cursor
    let isCancelled = false
    const masterTimeline = gsap.timeline({ repeat: -1 })

    replacementPhrases.forEach((phrase) => {
      // Type text character by character
      masterTimeline.to({}, {
        duration: phrase.length * 0.08,
        onUpdate: function () {
          if (isCancelled || !replacementRef.current) return
          const progress = this.progress()
          const currentLength = Math.floor(progress * phrase.length)
          replacementRef.current.textContent = phrase.slice(0, currentLength)
        }
      })

      // Hold phrase for 2.2 seconds
      masterTimeline.to({}, { duration: 2.2 })

      // Erase text character by character
      masterTimeline.to({}, {
        duration: phrase.length * 0.04,
        onUpdate: function () {
          if (isCancelled || !replacementRef.current) return
          const progress = 1 - this.progress()
          const currentLength = Math.floor(progress * phrase.length)
          replacementRef.current.textContent = phrase.slice(0, currentLength)
        }
      })

      // Pause briefly before typing next phrase
      masterTimeline.to({}, { duration: 0.3 })
    })

    return () => {
      isCancelled = true
      masterTimeline.kill()
    }
  }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setSuccessMessage('')

    if (!password.trim()) {
      return setError('Password baru wajib diisi.')
    }
    if (password.length < 8) {
      return setError('Password minimal harus 8 karakter.')
    }
    if (password !== passwordConfirm) {
      return setError('Konfirmasi password tidak cocok.')
    }

    setLoading(true)
    try {
      const res = await authApi.resetPassword(token, email, password, passwordConfirm)
      setSuccessMessage(res.message || 'Password berhasil direset. Mengalihkan ke halaman login...')
      setTimeout(() => {
        navigate('/login')
      }, 2000)
    } catch (err) {
      setError(err.response?.data?.message || 'Gagal mereset password. Silakan coba lagi.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-[65%_35%] bg-[var(--bg-main)] overflow-hidden relative">
      {/* Theme Toggle Button */}
      <button
        onClick={toggleTheme}
        className="absolute top-6 right-6 z-20 p-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-card)]/80 backdrop-blur-md text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all flex items-center justify-center shadow-sm cursor-pointer"
        title={isDark ? 'Mode Terang' : 'Mode Gelap'}
      >
        {isDark ? (
          <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
          </svg>
        ) : (
          <svg className="w-5 h-5 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
          </svg>
        )}
      </button>

      {/* Left side hero branding (65% width) */}
      <div className={`hidden lg:flex relative flex-col justify-center p-12 lg:p-16 overflow-hidden transition-colors duration-300 ${
        isDark 
          ? 'bg-gradient-to-br from-sky-500 via-blue-600 to-blue-800 text-white' 
          : 'bg-gradient-to-br from-white via-sky-300 to-sky-500 text-sky-950'
      }`}>
        {/* Glowing background shapes */}
        <div
          ref={glowShape1Ref}
          className={`absolute -top-10 -left-10 w-96 h-96 rounded-full blur-3xl pointer-events-none opacity-30 ${
            isDark ? 'bg-sky-300' : 'bg-white'
          }`}
        />
        <div
          ref={glowShape2Ref}
          className={`absolute bottom-10 right-10 w-80 h-80 rounded-full blur-3xl pointer-events-none opacity-30 ${
            isDark ? 'bg-blue-400' : 'bg-sky-200'
          }`}
        />

        {/* Center Hero Text */}
        <div className="relative z-10 max-w-2xl my-auto">
          <h1 className={`text-4xl font-extrabold tracking-tight leading-tight mb-4 ${
            isDark ? 'text-white drop-shadow-sm' : 'text-sky-950'
          }`}>
            <div>
              Kelola Pengetahuan &{' '}
              <span className="inline-flex items-baseline">
                <span
                  ref={replacementRef}
                  className={`font-black ${
                    isDark ? 'text-sky-300' : 'text-sky-700'
                  }`}
                >
                  AI Support
                </span>
                <span
                  ref={cursorRef}
                  className="font-mono text-white font-bold select-none ml-0.5"
                >
                  |
                </span>
              </span>
            </div>
            <div>Dalam Satu Tempat.</div>
          </h1>
          <p
            ref={heroTextRef}
            className={`text-base leading-relaxed font-medium flex flex-wrap gap-x-1.5 gap-y-0.5 ${
              isDark ? 'text-sky-100' : 'text-sky-900'
            }`}
          >
            {words.map((word, idx) => (
              <span key={idx} className="inline-block overflow-hidden py-0.5">
                <span className="hero-word-inner inline-block transform-gpu origin-bottom">
                  {word}
                </span>
              </span>
            ))}
          </p>
        </div>
      </div>

      {/* Right side Form Panel (35% width) */}
      <div className="flex items-center justify-center p-8 lg:p-10 bg-[var(--bg-card)]">
        <div className="w-full max-w-md">
          {/* Header Logos & Branding */}
          <div className="flex items-center gap-4 justify-center mb-10 sm:mb-12">
            <div className="flex items-center gap-2.5 shrink-0">
              <div className="rounded-2xl flex items-center justify-center p-1">
                <img src={bandaAcehLogo} alt="Logo Kota Banda Aceh" className="h-20 w-auto object-contain" />
              </div>
              <div className="rounded-2xl flex items-center justify-center p-1">
                <img src={komdigiLogo} alt="Logo Komdigi" className="h-15 w-auto object-contain" />
              </div>
            </div>

            <div className="text-left border-l border-[var(--border-color)] pl-3.5">
              <h1 className="text-xl font-black tracking-wider text-[var(--text-primary)] leading-tight">
                DISKOMINFOTIK
              </h1>
              <p className="text-xs font-semibold text-[var(--text-secondary)] leading-snug">
                Pemerintah Kota Banda Aceh
              </p>
            </div>
          </div>

          {!token || !email ? (
            /* ───── INVALID / MISSING TOKEN VIEW ───── */
            <div className="space-y-6 text-center">
              <div className="w-14 h-14 bg-red-500/10 text-red-500 rounded-2xl flex items-center justify-center mx-auto border border-red-500/20">
                <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>

              <div>
                <h2 className="text-2xl font-extrabold text-[var(--text-primary)] tracking-tight">Link Tidak Valid</h2>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  Token atau alamat email tidak ditemukan di URL, atau tautan reset password telah kedaluwarsa.
                </p>
              </div>

              <button
                type="button"
                onClick={() => navigate('/login')}
                className="w-full py-3.5 px-4 bg-gradient-to-r from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold rounded-xl shadow-lg shadow-sky-500/20 transition-all duration-200 flex items-center justify-center cursor-pointer"
              >
                Kembali ke Login
              </button>
            </div>
          ) : (
            /* ───── RESET PASSWORD FORM VIEW ───── */
            <div className="space-y-6">
              <div className="text-center lg:text-left mb-6">
                <h2 className="text-3xl font-extrabold text-[var(--text-primary)] tracking-tight">Buat Password Baru</h2>
                <p className="mt-2 text-sm text-[var(--text-secondary)]">
                  Masukkan password baru untuk <span className="font-semibold text-sky-600 dark:text-sky-400">{email}</span>
                </p>
              </div>

              {error && (
                <div className="bg-[var(--bg-input)] border border-[var(--border-color)] text-red-500 px-4 py-3 rounded-xl text-sm font-medium">
                  {error}
                </div>
              )}

              {successMessage && (
                <div className="bg-[var(--bg-input)] border border-[var(--border-color)] text-emerald-500 px-4 py-3 rounded-xl text-sm font-medium">
                  {successMessage}
                </div>
              )}

              <form noValidate onSubmit={handleSubmit} className="space-y-5">
                <div>
                  <label htmlFor="password" className="block text-sm font-semibold text-[var(--text-primary)] mb-2">
                    Password Baru
                  </label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? 'text' : 'password'}
                      className="pr-12"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Minimal 8 karakter"
                      disabled={loading || !!successMessage}
                    />
                    <button
                      type="button"
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex="-1"
                    >
                      {showPassword ? (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="passwordConfirm" className="block text-sm font-semibold text-[var(--text-primary)] mb-2">
                    Konfirmasi Password
                  </label>
                  <div className="relative">
                    <Input
                      id="passwordConfirm"
                      type={showConfirmPassword ? 'text' : 'password'}
                      className="pr-12"
                      value={passwordConfirm}
                      onChange={(e) => setPasswordConfirm(e.target.value)}
                      placeholder="Ketik ulang password baru"
                      disabled={loading || !!successMessage}
                    />
                    <button
                      type="button"
                      className="absolute right-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors p-1"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      tabIndex="-1"
                    >
                      {showConfirmPassword ? (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                        </svg>
                      ) : (
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  className="w-full py-3.5 px-4 bg-gradient-to-r from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold rounded-xl shadow-lg shadow-sky-500/20 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center cursor-pointer"
                  disabled={loading || !!successMessage}
                >
                  {loading ? (
                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : (
                    'Simpan Password Baru'
                  )}
                </button>

                <div className="text-center pt-2">
                  <button
                    type="button"
                    onClick={() => navigate('/login')}
                    className="text-sm font-semibold text-sky-600 hover:text-sky-500 transition-colors inline-flex items-center gap-1 cursor-pointer"
                  >
                    ← Kembali ke Login
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
