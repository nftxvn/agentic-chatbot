import { useState, useEffect, useRef, useMemo } from 'react'
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom'
import gsap from 'gsap'
import { useAuth } from '../../context/AuthContext'
import { useTheme } from '../../context/ThemeContext'
import ConfirmModal from '../ConfirmModal'
import komdigiLogo from '../../assets/komdigi-logo.svg'
import bandaAcehLogo from '../../assets/banda-aceh-logo.svg'
import { documentsApi } from '../../api/documents'
import { categoriesApi } from '../../api/categories'
import { getWhatsappSettings } from '../../api/settings'
import { authApi } from '../../api/auth'

function formatRelativeTime(dateString) {
  if (!dateString) return 'Baru saja'
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return 'Baru saja'
  const diffSec = Math.floor((Date.now() - date.getTime()) / 1000)
  if (diffSec < 60) return 'Baru saja'
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)} menit lalu`
  if (diffSec < 86400) return `${Math.floor(diffSec / 3600)} jam lalu`
  return `${Math.floor(diffSec / 86400)} hari lalu`
}

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

const QUICK_FEATURES = [
  { id: 'f-dashboard', label: 'Dashboard Utama', desc: 'Ringkasan dokumen RAG & statistik pengindeksan', to: '/dashboard' },
  { id: 'f-categories', label: 'Kategori Dokumen AI', desc: 'Kelola kategori, prompt LLM & model vision', to: '/categories' },
  { id: 'f-whatsapp', label: 'Pengaturan WhatsApp API', desc: 'Konfigurasi bot WhatsApp & akses token API', to: '/settings/whatsapp' },
  { id: 'f-theme', label: 'Ganti Mode Tampilan', desc: 'Beralih antara mode gelap & terang', action: 'toggle-theme' },
  { id: 'f-logout', label: 'Keluar dari Sistem', desc: 'Logout dari akun administrator', action: 'logout' },
]

export default function AdminLayout() {
  const { user, logout, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [isChatOpen, setIsChatOpen] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [showLogoutModal, setShowLogoutModal] = useState(false)
  const [isNotificationOpen, setIsNotificationOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [readIds, setReadIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('read_notifications') || '[]')
    } catch {
      return []
    }
  })
  const [clearedIds, setClearedIds] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('cleared_notifications') || '[]')
    } catch {
      return []
    }
  })

  // Search System States & Optimization
  const [searchQuery, setSearchQuery] = useState('')
  const [isSearchOpen, setIsSearchOpen] = useState(false)
  const [searchIndexData, setSearchIndexData] = useState({ documents: [], categories: [] })

  const { theme, toggleTheme, isDark } = useTheme()
  const isDarkMode = isDark

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)
  const userMenuRef = useRef(null)
  const userMenuDropdownRef = useRef(null)
  const isUserMenuClosingRef = useRef(false)

  // Change Password Settings Modal States
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    new_password_confirmation: '',
  })
  const [showCurrentPass, setShowCurrentPass] = useState(false)
  const [showNewPass, setShowNewPass] = useState(false)
  const [showConfirmPass, setShowConfirmPass] = useState(false)
  const [changingPass, setChangingPass] = useState(false)
  const [passError, setPassError] = useState('')
  const [passSuccess, setPassSuccess] = useState('')
  const passwordModalRef = useRef(null)

  const handleChangePasswordSubmit = async (e) => {
    e.preventDefault()
    setPassError('')
    setPassSuccess('')

    if (passwordForm.new_password !== passwordForm.new_password_confirmation) {
      setPassError('Konfirmasi password baru tidak cocok.')
      return
    }

    if (passwordForm.new_password.length < 8) {
      setPassError('Password baru minimal 8 karakter.')
      return
    }

    setChangingPass(true)
    try {
      const res = await authApi.changePassword(
        passwordForm.current_password,
        passwordForm.new_password,
        passwordForm.new_password_confirmation
      )
      setPassSuccess(res.message || 'Password berhasil diperbarui.')
      setPasswordForm({
        current_password: '',
        new_password: '',
        new_password_confirmation: '',
      })
      setTimeout(() => {
        setShowPasswordModal(false)
        setPassSuccess('')
      }, 1500)
    } catch (err) {
      setPassError(err.response?.data?.message || 'Gagal mengubah password. Pastikan password saat ini benar.')
    } finally {
      setChangingPass(false)
    }
  }

  const wrapperRef = useRef(null)
  const sidebarRef = useRef(null)
  const mainRef = useRef(null)
  const progressBarRef = useRef(null)
  const chatRef = useRef(null)
  const notificationRef = useRef(null)
  const dropdownRef = useRef(null)
  const chatButtonRef = useRef(null)
  const contentRef = useRef(null)
  const navRef = useRef(null)
  const navItemsRef = useRef([])
  const activePillRef = useRef(null)
  const searchContainerRef = useRef(null)
  const searchIconRef = useRef(null)
  const searchCardRef = useRef(null)

  // Pre-fetch search index asynchronously in background
  useEffect(() => {
    let isMounted = true
    const prepareSearchIndex = async () => {
      try {
        const [docRes, catRes] = await Promise.all([
          documentsApi.list(1).catch(() => null),
          categoriesApi.list().catch(() => null),
        ])
        if (!isMounted) return
        const docs = docRes?.data?.documents || docRes?.documents || []
        const cats = catRes?.data || catRes || []
        setSearchIndexData({
          documents: docs,
          categories: Array.isArray(cats) ? cats : (cats.data || [])
        })
      } catch (e) {
        console.error('Failed to prepare search index', e)
      }
    }
    prepareSearchIndex()
    return () => { isMounted = false }
  }, [location.pathname])

  // Fast In-Memory Search Filtering
  const filteredSearchResults = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) {
      return {
        features: QUICK_FEATURES,
        documents: searchIndexData.documents.slice(0, 4),
        categories: searchIndexData.categories.slice(0, 3)
      }
    }

    const matchedFeatures = QUICK_FEATURES.filter(f => 
      f.label.toLowerCase().includes(q) || f.desc.toLowerCase().includes(q)
    )

    const matchedDocs = searchIndexData.documents.filter(doc => 
      (doc.title && doc.title.toLowerCase().includes(q)) ||
      (doc.original_filename && doc.original_filename.toLowerCase().includes(q)) ||
      (doc.category_name && doc.category_name.toLowerCase().includes(q))
    ).slice(0, 5)

    const matchedCats = searchIndexData.categories.filter(cat =>
      (cat.name && cat.name.toLowerCase().includes(q)) ||
      (cat.description && cat.description.toLowerCase().includes(q))
    ).slice(0, 4)

    return {
      features: matchedFeatures,
      documents: matchedDocs,
      categories: matchedCats
    }
  }, [searchQuery, searchIndexData])

  const isSearchClosingRef = useRef(false)

  const closeSearch = () => {
    if (isSearchClosingRef.current) return
    if (searchCardRef.current) {
      isSearchClosingRef.current = true
      gsap.killTweensOf(searchCardRef.current)
      gsap.to(searchCardRef.current, {
        opacity: 0,
        scale: 0.85,
        y: -14,
        duration: 0.22,
        ease: 'power2.in',
        onComplete: () => {
          setIsSearchOpen(false)
          isSearchClosingRef.current = false
        },
      })
    } else {
      setIsSearchOpen(false)
    }
  }

  // GSAP animation for Search Dropdown Card (Spring back.out interaction identical to Notification)
  useEffect(() => {
    if (isSearchOpen && searchCardRef.current) {
      isSearchClosingRef.current = false
      gsap.killTweensOf(searchCardRef.current)
      gsap.fromTo(
        searchCardRef.current,
        { opacity: 0, scale: 0.85, y: -14, transformOrigin: 'top center' },
        { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: 'back.out(1.7)' }
      )
    }
  }, [isSearchOpen])

  const closeUserMenu = () => {
    if (isUserMenuClosingRef.current) return
    if (userMenuDropdownRef.current) {
      isUserMenuClosingRef.current = true
      gsap.killTweensOf(userMenuDropdownRef.current)
      gsap.to(userMenuDropdownRef.current, {
        opacity: 0,
        scale: 0.85,
        y: -14,
        duration: 0.22,
        ease: 'power2.in',
        onComplete: () => {
          setIsUserMenuOpen(false)
          isUserMenuClosingRef.current = false
        },
      })
    } else {
      setIsUserMenuOpen(false)
    }
  }

  const toggleUserMenu = () => {
    if (isUserMenuOpen) {
      closeUserMenu()
    } else {
      isUserMenuClosingRef.current = false
      setIsUserMenuOpen(true)
    }
  }

  // GSAP animation for User Profile Dropdown Menu (Spring back.out interaction)
  useEffect(() => {
    if (isUserMenuOpen && userMenuDropdownRef.current) {
      isUserMenuClosingRef.current = false
      gsap.killTweensOf(userMenuDropdownRef.current)
      gsap.fromTo(
        userMenuDropdownRef.current,
        { opacity: 0, scale: 0.85, y: -14, transformOrigin: 'top right' },
        { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: 'back.out(1.7)' }
      )
    }
  }, [isUserMenuOpen])

  // GSAP Smooth Route Transition Animation on Menu Switch
  useEffect(() => {
    if (!contentRef.current) return

    gsap.killTweensOf(contentRef.current)
    gsap.fromTo(
      contentRef.current,
      {
        opacity: 0,
        scale: 0.99,
      },
      {
        opacity: 1,
        scale: 1,
        duration: 0.35,
        ease: 'power2.out',
        clearProps: 'all',
      }
    )
  }, [location.pathname])

  // GSAP Fluid Active Menu Highlight Pill Slider
  useEffect(() => {
    if (authLoading) return
    const activeIndex = NAV_ITEMS.findIndex((item) => {
      if (item.to === '/dashboard') return location.pathname === '/dashboard' || location.pathname === '/'
      return location.pathname.startsWith(item.to)
    })

    if (activeIndex !== -1 && navItemsRef.current[activeIndex] && activePillRef.current) {
      const targetEl = navItemsRef.current[activeIndex]
      gsap.killTweensOf(activePillRef.current)
      gsap.to(activePillRef.current, {
        top: targetEl.offsetTop,
        height: targetEl.offsetHeight,
        opacity: 1,
        duration: 0.38,
        ease: 'power3.out',
      })
    } else if (activePillRef.current) {
      gsap.to(activePillRef.current, { opacity: 0, duration: 0.2 })
    }
  }, [location.pathname, authLoading])

  // GSAP animation for Notification Dropdown (Spring back.out interaction)
  useEffect(() => {
    if (isNotificationOpen && dropdownRef.current) {
      gsap.killTweensOf(dropdownRef.current)
      gsap.fromTo(
        dropdownRef.current,
        { opacity: 0, scale: 0.85, y: -14, transformOrigin: 'top right' },
        { opacity: 1, scale: 1, y: 0, duration: 0.38, ease: 'back.out(1.7)' }
      )
    }
  }, [isNotificationOpen])

  // GSAP animation for Chatbot Panel & Floating Button (Spring back.out interaction)
  useEffect(() => {
    if (isChatOpen && chatRef.current) {
      gsap.killTweensOf(chatRef.current)
      gsap.fromTo(
        chatRef.current,
        { x: 360, opacity: 0 },
        { x: 0, opacity: 1, duration: 0.45, ease: 'back.out(1.2)' }
      )
    }
    if (chatButtonRef.current) {
      gsap.killTweensOf(chatButtonRef.current)
      gsap.fromTo(
        chatButtonRef.current,
        { scale: 0.82 },
        { scale: 1, duration: 0.35, ease: 'back.out(2.2)' }
      )
    }
  }, [isChatOpen])

  const fetchRealNotifications = async () => {
    try {
      const docRes = await documentsApi.list(1).catch(() => null)
      const docs = docRes?.data?.documents || docRes?.documents || []

      const catRes = await categoriesApi.list().catch(() => null)
      const cats = catRes?.data || catRes || []

      const waRes = await getWhatsappSettings().catch(() => null)

      const realList = []

      docs.forEach((doc) => {
        if (doc.status === 'completed') {
          realList.push({
            id: `doc-${doc.id}-completed`,
            title: `Dokumen "${doc.title}" Ter-index`,
            message: `Dokumen ${doc.original_filename} (${doc.total_chunks || 0} chunks) siap digunakan AI.`,
            time: formatRelativeTime(doc.updated_at || doc.created_at),
            type: 'success',
          })
        } else if (doc.status === 'processing') {
          realList.push({
            id: `doc-${doc.id}-processing`,
            title: `Memproses "${doc.title}"`,
            message: `Proses ekstraksi RAG & OCR sedang berjalan ke ChromaDB.`,
            time: formatRelativeTime(doc.created_at),
            type: 'info',
          })
        } else if (doc.status === 'failed') {
          realList.push({
            id: `doc-${doc.id}-failed`,
            title: `Gagal Memproses Dokumen`,
            message: `Dokumen "${doc.title}" mengalami kesalahan saat di-index.`,
            time: formatRelativeTime(doc.updated_at || doc.created_at),
            type: 'warning',
          })
        }
      })

      if (waRes) {
        realList.push({
          id: 'wa-status-notification',
          title: `WhatsApp Bot ${waRes.wa_status ? 'Aktif' : 'Nonaktif'}`,
          message: waRes.wa_status
            ? `Layanan otomatis WhatsApp Diskominfo (${waRes.wa_phone_number || 'API Connected'}) siap melayani masyarakat.`
            : `Layanan WhatsApp Bot saat ini dinonaktifkan di sistem.`,
          time: 'Realtime',
          type: waRes.wa_status ? 'system' : 'warning',
        })
      }

      if (cats && (cats.length > 0 || (cats.data && cats.data.length > 0))) {
        const catList = cats.data || cats
        catList.forEach((cat) => {
          realList.push({
            id: `cat-${cat.id}-added`,
            title: `Kategori AI Baru`,
            message: `Anda baru saja menambahkan kategori "${cat.name}"`,
            time: formatRelativeTime(cat.created_at || cat.updated_at),
            type: 'info',
          })
        })
      }

      const actionLogs = JSON.parse(localStorage.getItem('action_notifications') || '[]')
      const formattedActions = actionLogs.map((item) => ({
        ...item,
        time: formatRelativeTime(item.timestamp),
      }))

      const combined = [...formattedActions, ...realList]

      const savedReadIds = JSON.parse(localStorage.getItem('read_notifications') || '[]')
      const savedClearedIds = JSON.parse(localStorage.getItem('cleared_notifications') || '[]')

      // Filter out cleared items & limit to top 15 most recent notifications
      const visibleList = combined
        .filter((item) => !savedClearedIds.includes(item.id))
        .slice(0, 15)
        .map((item) => ({
          ...item,
          unread: !savedReadIds.includes(item.id),
        }))

      setNotifications(visibleList)
    } catch (err) {
      console.error('Failed to fetch real notifications:', err)
    }
  }

  useEffect(() => {
    fetchRealNotifications()
    const interval = setInterval(fetchRealNotifications, 10000)

    const handleUpdateEvent = () => fetchRealNotifications()
    window.addEventListener('app-notification-update', handleUpdateEvent)

    return () => {
      clearInterval(interval)
      window.removeEventListener('app-notification-update', handleUpdateEvent)
    }
  }, [])

  const isClosingRef = useRef(false)

  const closeNotification = () => {
    if (isClosingRef.current) return
    if (dropdownRef.current) {
      isClosingRef.current = true
      gsap.killTweensOf(dropdownRef.current)
      gsap.to(dropdownRef.current, {
        opacity: 0,
        scale: 0.85,
        y: -14,
        duration: 0.22,
        ease: 'power2.in',
        onComplete: () => {
          setIsNotificationOpen(false)
          isClosingRef.current = false
        },
      })
    } else {
      setIsNotificationOpen(false)
    }
  }

  const toggleNotification = () => {
    if (isNotificationOpen) {
      closeNotification()
    } else {
      isClosingRef.current = false
      setIsNotificationOpen(true)
    }
  }

  const closeChat = () => {
    if (chatRef.current) {
      gsap.killTweensOf(chatRef.current)
      gsap.to(chatRef.current, {
        x: 380,
        opacity: 0,
        duration: 0.3,
        ease: 'power2.in',
        onComplete: () => setIsChatOpen(false),
      })
    } else {
      setIsChatOpen(false)
    }
  }

  const toggleChat = () => {
    if (isChatOpen) {
      closeChat()
    } else {
      setIsChatOpen(true)
    }
  }

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (
        isNotificationOpen &&
        notificationRef.current &&
        !notificationRef.current.contains(event.target)
      ) {
        closeNotification()
      }
      if (
        isSearchOpen &&
        searchContainerRef.current &&
        !searchContainerRef.current.contains(event.target)
      ) {
        closeSearch()
      }
      if (
        isUserMenuOpen &&
        userMenuRef.current &&
        !userMenuRef.current.contains(event.target)
      ) {
        closeUserMenu()
      }
    }
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        closeSearch()
        closeUserMenu()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isNotificationOpen, isSearchOpen, isUserMenuOpen])

  const unreadCount = notifications.filter((n) => n.unread).length

  const markAllAsRead = () => {
    const allIds = notifications.map((n) => n.id)
    localStorage.setItem('read_notifications', JSON.stringify(allIds))
    setReadIds(allIds)
    setNotifications((prev) => prev.map((n) => ({ ...n, unread: false })))
  }

  const clearAllNotifications = () => {
    const allCurrentIds = notifications.map((n) => n.id)
    const updatedCleared = Array.from(new Set([...clearedIds, ...allCurrentIds]))
    localStorage.setItem('cleared_notifications', JSON.stringify(updatedCleared))
    setClearedIds(updatedCleared)
    setNotifications([])
  }

  const markAsRead = (id) => {
    const updated = [...readIds, id]
    localStorage.setItem('read_notifications', JSON.stringify(updated))
    setReadIds(updated)
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, unread: false } : n))
    )
  }



  useEffect(() => {
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
  }, [location.pathname])

  const initial = user?.name?.charAt(0).toUpperCase() ?? 'A'

  return (
    <>
      <div
        ref={progressBarRef}
        className="fixed top-0 left-0 z-[9999] h-[3px] bg-gradient-to-r from-sky-400 via-blue-500 to-blue-600 w-0 opacity-0"
      />

      <div className="flex min-h-screen bg-[var(--bg-main)] overflow-x-hidden" ref={wrapperRef}>
        {mobileMenuOpen && (
          <div
            className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}

        <aside
          className={`w-[285px] bg-[var(--bg-sidebar)] border-r border-[var(--border-color)] flex flex-col fixed h-screen z-50 top-0 left-0 transition-transform duration-300 ${
            mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
          }`}
          ref={sidebarRef}
        >
          <div className="h-[85px] px-2 border-b border-[var(--border-color)] flex items-center justify-center gap-1">
            <div className="flex items-center gap-1">
              <div className="p-2 rounded-xl flex items-center justify-center shrink-0">
                <img src={bandaAcehLogo} alt="Logo Kota Banda Aceh" className="h-12.5 w-auto object-contain" />
              </div>
              <div className="p-1 rounded-xl flex items-center justify-center shrink-0">
                <img src={komdigiLogo} alt="Logo Komdigi" className="h-9 w-auto object-contain" />
              </div>
              <div className="overflow-hidden">
                <h2 className="text-[19px] font-black text-[var(--text-primary)] leading-tight tracking-tight uppercase">DISKOMINFOTIK</h2>
                <p className="text-[11px] text-[var(--text-muted)] font-semibold leading-tight">Pemerintah Kota Banda Aceh</p>
              </div>
            </div>
            <button
              onClick={() => setMobileMenuOpen(false)}
              className="lg:hidden text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg"
            >
              ✕
            </button>
          </div>

          <nav className="flex-1 px-3 py-4 flex flex-col gap-1 overflow-y-auto relative" ref={navRef}>
            <p className="text-SM font-bold text-[var(--text-muted)] uppercase tracking-wider px-3 mb-2">
              MENU UTAMA
            </p>

            {/* Fluid Sliding Active Highlight Pill */}
            <div
              ref={activePillRef}
              className="absolute left-3 right-3 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-200 dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 shadow-md shadow-sky-500/25 pointer-events-none transition-opacity opacity-0 z-0 border-0 outline-none"
            />

            {authLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-3.5 py-3 rounded-xl bg-[var(--bg-input)]/40 border border-[var(--border-color)]/30">
                    <div className="skeleton w-5 h-5 rounded-md shrink-0" />
                    <div className="skeleton h-4 w-32 rounded-md" />
                  </div>
                ))}
              </div>
            ) : (
              NAV_ITEMS.map((item, index) => (
                <NavLink
                  key={item.label}
                  to={item.to}
                  ref={(el) => (navItemsRef.current[index] = el)}
                  onClick={(e) => {
                    setMobileMenuOpen(false)
                    gsap.fromTo(
                      e.currentTarget,
                      { scale: 0.96 },
                      { scale: 1, duration: 0.3, ease: 'back.out(2)' }
                    )
                  }}
                  onMouseEnter={(e) => {
                    gsap.to(e.currentTarget, { scale: 1.025, duration: 0.2, ease: 'power2.out' })
                  }}
                  onMouseLeave={(e) => {
                    gsap.to(e.currentTarget, { scale: 1, duration: 0.2, ease: 'power2.out' })
                  }}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 py-3 rounded-xl text-sm font-bold border-0 outline-none focus:outline-none focus:ring-0 relative z-10 group select-none ` +
                    (isActive
                      ? 'text-white font-extrabold'
                      : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]')
                  }
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))
            )}
          </nav>
        </aside>

        <main
          className={`ml-0 lg:ml-[285px] flex-1 min-h-screen transition-all duration-300 w-full ${isChatOpen ? 'lg:mr-[400px]' : ''}`}
          ref={mainRef}
        >
          <header className="sticky top-0 z-20 h-[85px] px-4 lg:px-6 bg-[var(--bg-sidebar)]/80 backdrop-blur-md border-b border-[var(--border-color)] flex items-center justify-between gap-3">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] hover:text-sky-500 transition-colors shrink-0"
              title="Buka Navigasi"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            
            <div ref={searchContainerRef} className="relative w-full max-w-md mx-auto">
              <svg
                ref={searchIconRef}
                className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none z-10"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <input
                type="text"
                placeholder="Cari dokumen, kategori, atau fitur..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value)
                  if (!isSearchOpen) setIsSearchOpen(true)
                }}
                onFocus={() => {
                  setIsSearchOpen(true)
                  if (!searchContainerRef.current || !searchIconRef.current) return
                  gsap.killTweensOf([searchContainerRef.current, searchIconRef.current])
                  const tl = gsap.timeline()
                  tl.to(searchContainerRef.current, { scale: 1.02, duration: 0.25, ease: 'power2.out' })
                  tl.to(searchIconRef.current, { scale: 1.15, rotate: 90, color: '#0ea5e9', duration: 0.25 }, '-=0.2')
                }}
                onBlur={() => {
                  if (!searchContainerRef.current || !searchIconRef.current) return
                  gsap.killTweensOf([searchContainerRef.current, searchIconRef.current])
                  const tl = gsap.timeline()
                  tl.to(searchContainerRef.current, { scale: 1.0, duration: 0.25, ease: 'power2.out' })
                  tl.to(searchIconRef.current, { scale: 1.0, rotate: 0, color: 'var(--text-muted)', duration: 0.2 }, '-=0.2')
                }}
                className="w-full !pl-11 pr-8 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 transition-all shadow-sm"
              />
              {searchQuery && (
                <button
                  onClick={() => { setSearchQuery(''); closeSearch() }}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] text-xs font-bold z-10"
                >
                  ✕
                </button>
              )}

              {/* Floating Search Results Dropdown Card */}
              {isSearchOpen && (
                <div
                  ref={searchCardRef}
                  className="absolute left-0 right-0 top-full mt-2 bg-[var(--bg-card)] border border-[var(--border-color)] shadow-2xl rounded-xl overflow-hidden z-50 divide-y divide-[var(--border-color)]"
                >
                  <div className="max-h-96 overflow-y-auto p-2 space-y-3">
                    {/* Check if all empty */}
                    {filteredSearchResults.features.length === 0 &&
                     filteredSearchResults.documents.length === 0 &&
                     filteredSearchResults.categories.length === 0 ? (
                      <div className="p-6 text-center text-xs text-[var(--text-muted)]">
                        <p className="font-semibold text-[var(--text-primary)] mb-1">Hasil Tidak Ditemukan</p>
                        <p>Tidak ada dokumen, kategori, atau fitur yang cocok dengan "<span className="text-sky-500 font-bold">{searchQuery}</span>".</p>
                      </div>
                    ) : (
                      <>
                        {/* FITUR & MENU */}
                        {filteredSearchResults.features.length > 0 && (
                          <div>
                            <p className="text-[10px] font-extrabold uppercase tracking-wider text-[var(--text-muted)] px-3 py-1">
                              FITUR & AKSI
                            </p>
                            <div className="space-y-0.5">
                              {filteredSearchResults.features.map((feat) => (
                                <button
                                  key={feat.id || feat.label}
                                  onClick={() => {
                                    closeSearch()
                                    if (feat.to) navigate(feat.to)
                                    else if (feat.action === 'toggle-theme') toggleTheme()
                                    else if (feat.action === 'logout') setShowLogoutModal(true)
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-sky-500/10 dark:hover:bg-sky-500/15 transition-colors flex items-center justify-between group cursor-pointer"
                                >
                                  <div>
                                    <p className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors">
                                      {feat.label}
                                    </p>
                                    <p className="text-[11px] text-[var(--text-muted)] truncate max-w-[280px]">
                                      {feat.desc}
                                    </p>
                                  </div>
                                  <span className="text-[10px] font-semibold text-sky-500 opacity-0 group-hover:opacity-100 transition-opacity">
                                    Buka →
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* DOKUMEN RAG */}
                        {filteredSearchResults.documents.length > 0 && (
                          <div>
                            <p className="text-[10px] font-extrabold uppercase tracking-wider text-[var(--text-muted)] px-3 py-1">
                              DOKUMEN RAG
                            </p>
                            <div className="space-y-0.5">
                              {filteredSearchResults.documents.map((doc) => (
                                <button
                                  key={doc.id}
                                  onClick={() => {
                                    closeSearch()
                                    navigate(`/documents/${doc.id}`)
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-sky-500/10 dark:hover:bg-sky-500/15 transition-colors flex items-center justify-between group cursor-pointer"
                                >
                                  <div className="min-w-0 pr-2">
                                    <p className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors truncate">
                                      {doc.title}
                                    </p>
                                    <p className="text-[11px] text-[var(--text-muted)] font-mono truncate">
                                      {doc.original_filename} • {doc.category_name}
                                    </p>
                                  </div>
                                  <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-sky-500/15 text-sky-500 shrink-0">
                                    {doc.status_label || doc.status}
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* KATEGORI AI */}
                        {filteredSearchResults.categories.length > 0 && (
                          <div>
                            <p className="text-[10px] font-extrabold uppercase tracking-wider text-[var(--text-muted)] px-3 py-1">
                              KATEGORI AI
                            </p>
                            <div className="space-y-0.5">
                              {filteredSearchResults.categories.map((cat) => (
                                <button
                                  key={cat.id}
                                  onClick={() => {
                                    closeSearch()
                                    navigate('/categories')
                                  }}
                                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-sky-500/10 dark:hover:bg-sky-500/15 transition-colors flex items-center justify-between group cursor-pointer"
                                >
                                  <div className="min-w-0 pr-2">
                                    <p className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors">
                                      {cat.name}
                                    </p>
                                    <p className="text-[11px] text-[var(--text-muted)] truncate max-w-[280px]">
                                      {cat.description || 'Kategori dokumen'}
                                    </p>
                                  </div>
                                  <span className="text-[10px] font-semibold text-sky-500 opacity-0 group-hover:opacity-100 transition-opacity">
                                    Buka →
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  {/* Search Card Footer */}
                  <div className="px-3 py-2 bg-black/5 dark:bg-white/5 flex items-center justify-between text-[10px] text-[var(--text-muted)] font-medium">
                    <span>{searchQuery ? `Hasil pencarian: "${searchQuery}"` : 'Pencarian Instan'}</span>
                    <span className="font-mono">Esc untuk menutup</span>
                  </div>
                </div>
              )}
            </div>

            {/* Top Header Right Actions (Notification + Theme Switch + User Account Info) */}
            <div className="flex items-center gap-3 shrink-0">
              {/* Notification Dropdown Button */}
              <div className="relative" ref={notificationRef}>
                <button
                  onClick={(e) => {
                    toggleNotification()
                    gsap.fromTo(
                      e.currentTarget,
                      { scale: 0.85 },
                      { scale: 1, duration: 0.35, ease: 'back.out(2.2)' }
                    )
                  }}
                  className="p-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all flex items-center justify-center cursor-pointer relative"
                  title="Notifikasi"
                >
                  <svg className="w-4.5 h-4.5 text-[var(--text-primary)] hover:text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 01-6 0v-1m6 0H9"
                    />
                  </svg>
                  {unreadCount > 0 && (
                    <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-black flex items-center justify-center shadow-md animate-pulse">
                      {unreadCount}
                    </span>
                  )}
                </button>

                {/* Notification Dropdown Window */}
                {isNotificationOpen && (
                  <div ref={dropdownRef} className="absolute right-0 mt-3 w-80 sm:w-96 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-2xl z-50 overflow-hidden">
                    {/* Header */}
                    <div className="p-4 border-b border-[var(--border-color)] flex items-center justify-between bg-black/5 dark:bg-white/5">
                      <div className="flex items-center gap-2">
                        <h3 className="font-bold text-sm text-[var(--text-primary)]">Notifikasi</h3>
                        {unreadCount > 0 && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-extrabold bg-sky-500/15 text-sky-500 border border-sky-500/30">
                            {unreadCount} Baru
                          </span>
                        )}
                      </div>
                      {notifications.length > 0 && (
                        <div className="flex items-center gap-3">
                          {unreadCount > 0 && (
                            <button
                              onClick={markAllAsRead}
                              className="text-xs font-semibold text-sky-600 hover:text-sky-500 dark:text-sky-400 transition-colors"
                            >
                              Tandai Dibaca
                            </button>
                          )}
                          <button
                            onClick={clearAllNotifications}
                            className="text-xs font-semibold text-[var(--text-muted)] hover:text-red-500 transition-colors"
                          >
                            Bersihkan
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Notification List */}
                    <div className="max-h-80 overflow-y-auto divide-y divide-[var(--border-color)]">
                      {notifications.length === 0 ? (
                        <div className="p-8 text-center flex flex-col items-center justify-center">
                          <div className="w-14 h-14 rounded-2xl bg-sky-500/10 border border-sky-500/20 text-sky-500 flex items-center justify-center mb-3">
                            <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 01-6 0v-1m6 0H9" />
                            </svg>
                          </div>
                          <h4 className="text-sm font-bold text-[var(--text-primary)]">Belum Ada Notifikasi Baru</h4>
                          <p className="text-xs text-[var(--text-muted)] mt-1 max-w-[240px] leading-relaxed">
                            Tidak ada pemberitahuan atau riwayat aktivitas dokumen saat ini.
                          </p>
                        </div>
                      ) : (
                        notifications.map((item) => (
                          <div
                            key={item.id}
                            onClick={() => markAsRead(item.id)}
                            className={`p-4 transition-colors cursor-pointer flex gap-3 items-start ${
                              item.unread
                                ? 'bg-sky-500/5 hover:bg-sky-500/10'
                                : 'hover:bg-black/5 dark:hover:bg-white/5 opacity-75'
                            }`}
                          >
                            {/* Status Icon */}
                            <div className="shrink-0 mt-0.5">
                              {item.type === 'success' && (
                                <div className="w-8 h-8 rounded-xl bg-emerald-500/15 text-emerald-500 flex items-center justify-center">
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                  </svg>
                                </div>
                              )}
                              {item.type === 'info' && (
                                <div className="w-8 h-8 rounded-xl bg-sky-500/15 text-sky-500 flex items-center justify-center">
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                  </svg>
                                </div>
                              )}
                              {item.type === 'warning' && (
                                <div className="w-8 h-8 rounded-xl bg-amber-500/15 text-amber-500 flex items-center justify-center">
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                  </svg>
                                </div>
                              )}
                              {item.type === 'system' && (
                                <div className="w-8 h-8 rounded-xl bg-purple-500/15 text-purple-500 flex items-center justify-center">
                                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                                  </svg>
                                </div>
                              )}
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between gap-2">
                                <p className="text-xs font-bold text-[var(--text-primary)] truncate">{item.title}</p>
                                <span className="text-[10px] text-[var(--text-muted)] shrink-0 font-medium">{item.time}</span>
                              </div>
                              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-snug">{item.message}</p>
                            </div>

                            {/* Unread Indicator */}
                            {item.unread && (
                              <span className="w-2 h-2 rounded-full bg-sky-500 shrink-0 mt-2" />
                            )}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Dark & Light Mode Toggle Button */}
              <button
                onClick={(e) => {
                  toggleTheme()
                  gsap.fromTo(
                    e.currentTarget,
                    { scale: 0.82, rotate: -15 },
                    { scale: 1, rotate: 0, duration: 0.35, ease: 'back.out(2.2)' }
                  )
                }}
                className="p-3 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] hover:border-sky-500 hover:text-sky-500 transition-all flex items-center justify-center cursor-pointer"
                title={isDarkMode ? 'Mode Terang' : 'Mode Gelap'}
              >
                {isDarkMode ? (
                  <svg className="w-4.5 h-4.5 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                ) : (
                  <svg className="w-4.5 h-4.5 text-sky-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                )}
              </button>

              {/* User Account Info & Interactive Profile Dropdown Menu */}
              {authLoading ? (
                <div className="flex items-center gap-3 pl-3 border-l border-[var(--border-color)]">
                  <div className="skeleton w-10 h-10 rounded-xl shrink-0" />
                  <div className="hidden sm:flex flex-col space-y-1.5 min-w-0">
                    <div className="skeleton h-4 w-28 rounded-md" />
                    <div className="skeleton h-3 w-36 rounded-md" />
                  </div>
                </div>
              ) : (
                <div className="relative" ref={userMenuRef}>
                  <button
                    onClick={(e) => {
                      toggleUserMenu()
                      gsap.fromTo(
                        e.currentTarget,
                        { scale: 0.95 },
                        { scale: 1, duration: 0.3, ease: 'back.out(2)' }
                      )
                    }}
                    className="flex items-center gap-2.5 pl-3 border-l border-[var(--border-color)] text-left hover:opacity-90 transition-opacity cursor-pointer group"
                    title="Menu Akun Admin"
                  >
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 text-sm font-bold flex items-center justify-center shadow-sm shrink-0">
                      {initial}
                    </div>
                    <div className="hidden sm:flex flex-col min-w-0">
                      <span className="text-xs font-bold text-[var(--text-primary)] group-hover:text-sky-500 transition-colors truncate max-w-[140px]">
                        {user?.name || 'Admin Diskominfotik'}
                      </span>
                      <span className="text-[11px] text-[var(--text-muted)] truncate max-w-[140px]">
                        {user?.email || 'admin@diskominfotik.go.id'}
                      </span>
                    </div>
                    <svg
                      className={`w-4 h-4 text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-transform duration-200 ${
                        isUserMenuOpen ? 'rotate-180 text-sky-500' : ''
                      }`}
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>

                  {/* User Profile Dropdown Menu Window */}
                  {isUserMenuOpen && (
                    <div
                      ref={userMenuDropdownRef}
                      className="absolute right-0 mt-3 w-64 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-2xl z-50 overflow-hidden divide-y divide-[var(--border-color)]"
                    >
                      {/* User Header Info in Dropdown */}
                      <div className="p-3.5 bg-black/5 dark:bg-white/5 flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 text-sm font-bold flex items-center justify-center shrink-0 shadow-sm">
                          {initial}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-[var(--text-primary)] truncate">
                            {user?.name || 'Admin Diskominfotik'}
                          </p>
                          <p className="text-[11px] text-[var(--text-muted)] truncate">
                            {user?.email || 'admin@diskominfotik.go.id'}
                          </p>
                        </div>
                      </div>

                      {/* Navigation Actions */}
                      <div className="p-1.5 space-y-0.5">
                        <button
                          onClick={() => {
                            closeUserMenu()
                            setPassError('')
                            setPassSuccess('')
                            setShowPasswordModal(true)
                          }}
                          className="w-full px-3 py-2 rounded-lg text-xs font-semibold text-[var(--text-primary)] hover:bg-sky-500/10 hover:text-sky-500 transition-colors flex items-center gap-2.5 text-left group cursor-pointer"
                        >
                          <svg className="w-4 h-4 text-sky-500 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          <span>Settings</span>
                        </button>
                      </div>

                      {/* Logout Action */}
                      <div className="p-1.5">
                        <button
                          onClick={() => {
                            closeUserMenu()
                            setShowLogoutModal(true)
                          }}
                          className="w-full px-3 py-2 rounded-lg text-xs font-bold text-red-500 hover:bg-red-500/10 transition-colors flex items-center gap-2.5 text-left group cursor-pointer"
                        >
                          <svg className="w-4 h-4 text-red-500 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                          </svg>
                          <span>Keluar / Logout</span>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </header>

          <div ref={contentRef} key={location.pathname}>
            <Outlet />
          </div>
        </main>

        {/* ── Chat Panel ── */}
        {isChatOpen && (
          <aside className="w-full sm:w-[400px] bg-[var(--bg-sidebar)] border-l border-[var(--border-color)] fixed right-0 top-0 h-screen flex flex-col z-50 shadow-2xl" ref={chatRef}>
            <div className="px-5 py-7 border-b border-[var(--border-color)] flex justify-between items-center bg-black/5 dark:bg-white/5">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse" />
                <h3 className="text-base font-bold text-[var(--text-primary)] m-0">Test Chatbot Assistant</h3>
              </div>
              <button
                onClick={closeChat}
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
          ref={chatButtonRef}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-gradient-to-tr from-sky-500 via-blue-600 to-blue-700 text-white flex items-center justify-center shadow-xl shadow-sky-500/30 transition-all duration-300 hover:scale-110 hover:shadow-2xl"
          onClick={toggleChat}
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

        {/* Settings Change Password Modal */}
        {showPasswordModal && (
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
            onClick={(e) => { if (e.target === e.currentTarget && !changingPass) setShowPasswordModal(false) }}
          >
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] w-full max-w-md rounded-2xl shadow-2xl overflow-hidden" ref={passwordModalRef}>
              <div className="px-6 py-5 border-b border-[var(--border-color)] flex justify-between items-center bg-black/5 dark:bg-white/5">
                <div className="flex items-center gap-2.5">
                  <div className="w-8 h-8 rounded-xl bg-sky-500/10 text-sky-500 flex items-center justify-center">
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  </div>
                  <h3 className="text-base font-bold text-[var(--text-primary)]">Settings</h3>
                </div>
                <button
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors disabled:opacity-30 disabled:pointer-events-none"
                  onClick={() => !changingPass && setShowPasswordModal(false)}
                  disabled={changingPass}
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleChangePasswordSubmit}>
                <div className="p-6 space-y-4">
                  {passSuccess && (
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 rounded-xl text-xs font-semibold flex items-center gap-2">
                      <span>✓</span>
                      <span>{passSuccess}</span>
                    </div>
                  )}

                  {passError && (
                    <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl text-xs font-semibold flex items-center gap-2">
                      <span>⚠️</span>
                      <span>{passError}</span>
                    </div>
                  )}

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">Password Saat Ini</label>
                    <div className="relative">
                      <input
                        type={showCurrentPass ? 'text' : 'password'}
                        required
                        value={passwordForm.current_password}
                        onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                        placeholder="Masukkan password lama"
                        disabled={changingPass}
                        className="w-full pr-10 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowCurrentPass(!showCurrentPass)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors"
                        title={showCurrentPass ? 'Sembunyikan Password' : 'Lihat Password'}
                      >
                        {showCurrentPass ? (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">Password Baru</label>
                    <div className="relative">
                      <input
                        type={showNewPass ? 'text' : 'password'}
                        required
                        minLength={8}
                        value={passwordForm.new_password}
                        onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                        placeholder="Minimal 8 karakter"
                        disabled={changingPass}
                        className="w-full pr-10 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPass(!showNewPass)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors"
                        title={showNewPass ? 'Sembunyikan Password' : 'Lihat Password'}
                      >
                        {showNewPass ? (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">Konfirmasi Password Baru</label>
                    <div className="relative">
                      <input
                        type={showConfirmPass ? 'text' : 'password'}
                        required
                        minLength={8}
                        value={passwordForm.new_password_confirmation}
                        onChange={(e) => setPasswordForm({ ...passwordForm, new_password_confirmation: e.target.value })}
                        placeholder="Ketik ulang password baru"
                        disabled={changingPass}
                        className="w-full pr-10 py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowConfirmPass(!showConfirmPass)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 transition-colors"
                        title={showConfirmPass ? 'Sembunyikan Password' : 'Lihat Password'}
                      >
                        {showConfirmPass ? (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                          </svg>
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-[var(--border-color)] bg-black/5 dark:bg-white/5 flex justify-end gap-3">
                  <button
                    type="button"
                    className="px-4 py-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-xs font-semibold text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors"
                    onClick={() => setShowPasswordModal(false)}
                    disabled={changingPass}
                  >
                    Batal
                  </button>
                  <button
                    type="submit"
                    className={`px-5 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 font-bold text-xs shadow-lg shadow-sky-500/25 transition-all relative overflow-hidden flex items-center justify-center gap-2 ${
                      changingPass ? 'btn-light-sweep cursor-wait opacity-95' : 'hover:scale-[1.02] disabled:opacity-50'
                    }`}
                    disabled={changingPass || !passwordForm.current_password || !passwordForm.new_password || !passwordForm.new_password_confirmation}
                  >
                    {changingPass ? (
                      <>
                        <span className="spin w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full shrink-0" />
                        <span>Menyimpan Password...</span>
                      </>
                    ) : (
                      'Simpan Password Baru'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
