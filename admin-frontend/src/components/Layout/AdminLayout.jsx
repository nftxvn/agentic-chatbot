import { useState, useEffect, useRef } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import styles from './AdminLayout.module.css'
import ConfirmModal from '../ConfirmModal'

const NAV_ITEMS = [
  {
    to: '/dashboard',
    label: 'Dashboard',
    icon: (
      <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
      </svg>
    ),
  },
  {
    to: '/categories',
    label: 'Kategori',
    icon: (
      <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
      </svg>
    ),
  },
  {
    to: '/settings/whatsapp',
    label: 'API',
    icon: (
      <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
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
    if (savedTheme) {
      return savedTheme === 'dark'
    }
    // Default to dark mode
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

    const navTexts = sidebarRef.current.querySelectorAll('p, a, button, .avatar, .userInfo')
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

    // Animate Top Progress Bar
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

    // Animate H1 (Judul Menu) every time page changes
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
      <div ref={progressBarRef} className={styles.topProgressBar}></div>
      <div className={styles.wrapper} ref={wrapperRef}>
      {/* ── Sidebar ── */}
      <aside className={styles.sidebar} ref={sidebarRef}>


        {/* Nav */}
        <nav className={styles.nav}>
          <p className={styles.navSection}>MAIN MENU</p>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.label}
              to={item.to}
              className={({ isActive }) =>
                [styles.navLink, isActive ? styles.navLinkActive : ''].join(' ')
              }
            >
              {item.icon}
              {item.label}
            </NavLink>
          ))}
          
          {/* Removed Chat Button from sidebar */}
        </nav>

        {/* User section */}
        <div className={styles.userSection}>
          <div className={styles.avatar}>{initial}</div>
          <div className={styles.userInfo}>
            <p className={styles.userName}>{user?.name}</p>
            <p className={styles.userEmail}>{user?.email}</p>
          </div>
          <button className={styles.logoutBtn} onClick={() => setIsDarkMode(!isDarkMode)} title={isDarkMode ? 'Mode Terang' : 'Mode Gelap'}>
            {isDarkMode ? (
              <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>
            ) : (
              <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
            )}
          </button>
          <button className={styles.logoutBtn} onClick={() => setShowLogoutModal(true)} title="Keluar">
            <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className={`${styles.main} ${isChatOpen ? styles.mainWithChat : ''}`} ref={mainRef}>
        <Outlet />
      </main>

      {/* ── Chat Panel ── */}
      {isChatOpen && (
        <aside className={styles.chatPanel}>
          <div className={styles.chatHeader}>
            <h3>Test Chatbot</h3>
            <button onClick={() => setIsChatOpen(false)}>✕</button>
          </div>
          <iframe 
            src="http://localhost:3000" 
            className={styles.chatIframe}
            title="Chat Widget Test"
          />
        </aside>
      )}

      {/* Floating Action Button (Radial Chat Button) */}
      <button 
        className={styles.fabChat} 
        onClick={() => setIsChatOpen(!isChatOpen)}
        title="Buka Chatbot"
      >
        <svg width="28" height="28" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
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
