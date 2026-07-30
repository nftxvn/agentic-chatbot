import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import ConfirmModal from '../ConfirmModal'
import komdigiLogo from '../../assets/komdigi-logo.svg'
import bandaAcehLogo from '../../assets/banda-aceh-logo.svg'

const NAV_ITEMS = [
  {
    to: '/dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75}
          d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
  },
  {
    to: '/categories',
    label: 'Kategori AI',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    ),
  },
  {
    to: '/settings/whatsapp',
    label: 'Pengaturan API',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  }
]

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [showLogoutModal, setShowLogoutModal] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const savedTheme = localStorage.getItem('theme')
    if (savedTheme) return savedTheme === 'dark'
    return true
  })

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.setAttribute('data-theme', 'dark')
      localStorage.setItem('theme', 'dark')
    } else {
      document.documentElement.setAttribute('data-theme', 'light')
      localStorage.setItem('theme', 'light')
    }
  }, [isDarkMode])

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const wrapperRef = useRef(null)
  const sidebarRef = useRef(null)
  const mainRef = useRef(null)
  const progressBarRef = useRef(null)

  useEffect(() => {
    const gsap = window.gsap
    if (!gsap) return

    gsap.fromTo(sidebarRef.current,
      { x: -50, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.6, ease: "power3.out" }
    )

    const navTexts = sidebarRef.current.querySelectorAll('p, a, button')
    gsap.fromTo(navTexts,
      { x: -20, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.4, stagger: 0.05, ease: "power2.out", delay: 0.2 }
    )

    gsap.fromTo(mainRef.current,
      { y: 30, opacity: 0 },
      { y: 0, opacity: 1, duration: 0.6, ease: "power3.out", delay: 0.2 }
    )
  }, [])

  useEffect(() => {
    const gsap = window.gsap
    if (!gsap) return

    if (progressBarRef.current) {
      gsap.killTweensOf(progressBarRef.current)
      gsap.set(progressBarRef.current, { width: '0%', opacity: 1 })
      gsap.to(progressBarRef.current, {
        width: '70%',
        duration: 0.4,
        ease: 'power2.out'
      })

      setTimeout(() => {
        gsap.to(progressBarRef.current, {
          width: '100%',
          duration: 0.3,
          ease: 'power2.in',
          onComplete: () => {
            gsap.to(progressBarRef.current, { opacity: 0, duration: 0.2 })
          }
        })
      }, 400)
    }

    if (!mainRef.current) return

    const h1 = mainRef.current.querySelector('h1')
    if (h1) {
      gsap.fromTo(h1,
        { opacity: 0, x: -30 },
        { opacity: 1, x: 0, duration: 0.5, ease: "power2.out", clearProps: "all" }
      )
    }
  }, [location.pathname])

  const initial = user?.name?.charAt(0).toUpperCase() ?? 'A'

  return (
    <>
      {/* Top Progress Bar */}
      <div
        ref={progressBarRef}
        className="fixed top-0 left-0 z-[9999] h-[3px] bg-gradient-to-r from-sky-400 via-blue-500 to-blue-600 w-0 opacity-0"
      />

      <div className="flex min-h-screen bg-[var(--bg-main)]" ref={wrapperRef}>
        {/* ── Sidebar ── */}
        <aside
          className="w-[260px] bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] flex flex-col fixed h-screen z-30 top-0 left-0 shadow-sm"
          ref={sidebarRef}
        >
          {/* Brand Header */}
          <div className="p-4 border-b border-[var(--border-color)] flex items-center gap-1">
            <div className="p-0 rounded-xl flex items-center justify-center shrink-0">
              <img src={bandaAcehLogo} alt="Logo Kota Banda Aceh" className="h-12 w-auto object-contain" />
            </div>
            <div className="p-1 rounded-xl flex items-center justify-center shrink-0">
              <img src={komdigiLogo} alt="Logo Komdigi" className="h-10 w-auto object-contain" />
            </div>
            <div className="overflow-hidden">
              <h2 className="text-xs font-black text-[var(--text-primary)] leading-tight tracking-tight uppercase">DISKOMINFOTIK</h2>
              <p className="text-[9px] text-[var(--text-muted)] font-semibold leading-tight">Pemerintah Kota Banda Aceh</p>
            </div>
          </div>

          {/* User section (Above Menu Utama) */}
          <div className="px-4 py-3.5 border-b border-[var(--border-color)] flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-sky-400 to-blue-600 flex items-center justify-center text-sm font-bold text-white shadow-sm shrink-0">
              {initial}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-[var(--text-primary)] truncate">
                {user?.name || 'Admin Diskominfotik'}
              </p>
              <p className="text-[11px] text-[var(--text-muted)] truncate">
                {user?.email || 'admin@diskominfotik.go.id'}
              </p>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <button
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 rounded-lg transition-colors"
                onClick={() => setIsDarkMode(!isDarkMode)}
                title={isDarkMode ? 'Mode Terang' : 'Mode Gelap'}
              >
                {isDarkMode ? (
                  <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
                ) : (
                  <svg className="w-4 h-4 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
                )}
              </button>
              <button
                className="text-[var(--text-muted)] hover:text-red-500 p-1.5 rounded-lg transition-colors"
                onClick={() => setShowLogoutModal(true)}
                title="Keluar"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
              </button>
            </div>
          </div>

          {/* Nav */}
          <nav className="flex-1 px-3 py-3 flex flex-col gap-1 overflow-y-auto">
            <p className="text-[11px] font-bold text-[var(--text-muted)] uppercase tracking-wider px-3 mb-2">
              MENU UTAMA
            </p>
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.label}
                to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-semibold transition-all duration-200 relative group ` +
                  (isActive
                    ? 'text-white bg-gradient-to-r from-sky-500 via-blue-600 to-blue-700 shadow-md shadow-sky-500/25'
                    : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-input)]')
                }
              >
                {item.icon}
                <span>{item.label}</span>
              </NavLink>
            ))}
          </nav>
        </aside>

        {/* ── Main Content Area ── */}
        <main
          className={`ml-[260px] flex-1 min-h-screen transition-all duration-300 ${isChatOpen ? 'mr-[400px]' : ''}`}
          ref={mainRef}
        >
          <Outlet />
        </main>

        {/* ── Chat Panel ── */}
        {isChatOpen && (
          <aside className="w-[400px] bg-[var(--bg-sidebar)] border-l border-[var(--border-color)] fixed right-0 top-0 h-screen flex flex-col z-40 shadow-2xl" ref={chatRef}>
            <div className="px-5 py-4 border-b border-[var(--border-color)] flex justify-between items-center bg-black/5 dark:bg-white/5">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
                <h3 className="text-base font-bold text-[var(--text-primary)] m-0">Test Chatbot Assistant</h3>
              </div>
              <button
                onClick={() => setIsChatOpen(false)}
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors"
              >
                ✕
              </button>
            </div>
            <iframe
              src="http://localhost:3000"
              className="flex-1 w-full border-none bg-transparent"
              title="Chat Widget Test"
            />
          </aside>
        )}

        {/* Floating Chat Button */}
        <button
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-tr from-sky-500 via-blue-600 to-blue-700 text-white flex items-center justify-center shadow-xl shadow-sky-500/30 transition-all duration-300 hover:scale-110 hover:shadow-2xl"
          onClick={() => setIsChatOpen(!isChatOpen)}
          title="Buka Chatbot"
        >
          <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>

        <ConfirmModal
          isOpen={showLogoutModal}
          title="Konfirmasi Keluar"
          message="Apakah Anda yakin ingin keluar dari aplikasi?"
          onConfirm={handleLogout}
          onCancel={() => setShowLogoutModal(false)}
          confirmText="Keluar"
        />
      </div>
    </>
  )
}
