import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import gsap from 'gsap'
import { ticketsApi } from '../api/tickets'
import { InfoTooltip } from '../components/UI/InfoTooltip'
import { SlidingTabs } from '../components/UI/SlidingTabs'
import { addAppNotification } from '../utils/notifications'

export default function LiveChatPage() {
  const [activeTab, setActiveTab] = useState('all') // all | open | in_progress | resolved
  const [tickets, setTickets] = useState([])
  const [stats, setStats] = useState({ open: 0, in_progress: 0, resolved: 0, total: 0 })
  const [selectedTicket, setSelectedTicket] = useState(null)
  const [messages, setMessages] = useState([])
  const [replyText, setReplyText] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const [sending, setSending] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showScrollBottomBtn, setShowScrollBottomBtn] = useState(false)
  const [unreadWhileScrolled, setUnreadWhileScrolled] = useState(0)
  const [selectedFile, setSelectedFile] = useState(null)
  const [filePreviewUrl, setFilePreviewUrl] = useState(null)
  const [previewModalImg, setPreviewModalImg] = useState(null)
  const [ticketToDelete, setTicketToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const statsGridRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const messagesEndRef = useRef(null)
  const isNearBottomRef = useRef(true)
  const prevMessagesLengthRef = useRef(0)
  const fileInputRef = useRef(null)

  const handleScroll = () => {
    if (!messagesContainerRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight
    const isNear = distanceFromBottom < 100

    isNearBottomRef.current = isNear

    if (isNear) {
      setShowScrollBottomBtn(false)
      setUnreadWhileScrolled(0)
    } else {
      setShowScrollBottomBtn(true)
    }
  }

  const scrollToBottom = (behavior = 'smooth') => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior,
      })
    } else if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior })
    }
    isNearBottomRef.current = true
    setShowScrollBottomBtn(false)
    setUnreadWhileScrolled(0)
  }

  // Fetch ticket lists & stats
  const fetchTickets = async (showLoading = false) => {
    if (showLoading) setLoading(true)
    setIsRefreshing(true)
    try {
      const [ticketRes, statRes] = await Promise.all([
        ticketsApi.list({
          status: activeTab !== 'all' ? activeTab : undefined,
          search: searchQuery.trim() || undefined,
        }),
        ticketsApi.getStats().catch(() => null),
      ])

      const list = ticketRes?.data || ticketRes?.tickets || (Array.isArray(ticketRes) ? ticketRes : [])
      setTickets(list)

      if (statRes?.data || statRes) {
        setStats(statRes?.data || statRes)
      }

      // If a ticket is currently selected, refresh its detail
      if (selectedTicket) {
        const updated = list.find((t) => t.id === selectedTicket.id)
        if (updated) setSelectedTicket(updated)
      } else if (list.length > 0 && !selectedTicket) {
        handleSelectTicket(list[0])
      }
    } catch (err) {
      console.error('Failed to load tickets:', err)
    } finally {
      if (showLoading) setLoading(false)
      setTimeout(() => setIsRefreshing(false), 400)
    }
  }

  // Fetch messages for selected ticket
  const fetchMessages = async (ticketId, isInitial = false) => {
    if (isInitial) {
      setLoadingMessages(true)
      setUnreadWhileScrolled(0)
      setShowScrollBottomBtn(false)
      isNearBottomRef.current = true
    }
    try {
      const res = await ticketsApi.getMessages(ticketId)
      const msgList = res?.data || res?.messages || (Array.isArray(res) ? res : [])
      setMessages(msgList)
      if (isInitial) {
        prevMessagesLengthRef.current = msgList.length
        setTimeout(() => scrollToBottom('auto'), 50)
      }
    } catch (err) {
      console.error('Failed to load messages for ticket:', ticketId, err)
    } finally {
      if (isInitial) setLoadingMessages(false)
    }
  }

  useEffect(() => {
    fetchTickets(true)
  }, [activeTab])

  useEffect(() => {
    if (selectedTicket?.id) {
      fetchMessages(selectedTicket.id, true)
    }
  }, [selectedTicket?.id])

  // Auto-scroll to bottom like WhatsApp when new messages arrive
  useEffect(() => {
    if (messages.length === 0) return

    const diff = messages.length - prevMessagesLengthRef.current
    prevMessagesLengthRef.current = messages.length

    if (diff > 0) {
      if (isNearBottomRef.current) {
        const timer = setTimeout(() => {
          scrollToBottom('smooth')
        }, 50)
        return () => clearTimeout(timer)
      } else {
        // User is scrolled up reading previous history -> don't yank view, show unread badge!
        setUnreadWhileScrolled((prev) => prev + diff)
        setShowScrollBottomBtn(true)
      }
    }
  }, [messages])

  // GSAP animation for Stats Cards on first load
  useLayoutEffect(() => {
    if (!loading && statsGridRef.current) {
      const cards = statsGridRef.current.children
      gsap.fromTo(
        cards,
        { opacity: 0, scale: 0.98 },
        {
          opacity: 1,
          scale: 1,
          duration: 0.4,
          stagger: 0.05,
          ease: 'power2.out',
          clearProps: 'all',
        },
      )
    }
  }, [loading])

  // Real-time background sync timer (5s)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchTickets(false)
      if (selectedTicket?.id) {
        fetchMessages(selectedTicket.id, false)
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [selectedTicket?.id, activeTab, searchQuery])

  const handleSelectTicket = (t) => {
    setSelectedTicket(t)
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (file.size > 10 * 1024 * 1024) {
      addAppNotification({
        title: 'Ukuran File Terlalu Besar',
        message: 'Maksimal ukuran file lampiran adalah 10 MB.',
        type: 'warning',
      })
      return
    }
    setSelectedFile(file)
    if (file.type.startsWith('image/')) {
      setFilePreviewUrl(URL.createObjectURL(file))
    } else {
      setFilePreviewUrl(null)
    }
  }

  const handleClearFile = () => {
    setSelectedFile(null)
    if (filePreviewUrl) {
      URL.revokeObjectURL(filePreviewUrl)
      setFilePreviewUrl(null)
    }
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSendReply = async (e) => {
    e?.preventDefault()
    if ((!replyText.trim() && !selectedFile) || !selectedTicket || sending) return

    setSending(true)
    try {
      await ticketsApi.reply(selectedTicket.id, replyText.trim(), selectedFile)
      setReplyText('')
      handleClearFile()
      await fetchMessages(selectedTicket.id, false)
      scrollToBottom()
      addAppNotification({
        title: 'Balasan Terkirim',
        message: `Pesan resmi telah dikirimkan kepada ${selectedTicket.citizen_name || 'Warga'}.`,
        type: 'success',
      })
    } catch (err) {
      console.error('Failed to send reply:', err)
      addAppNotification({
        title: 'Gagal Mengirim Balasan',
        message: err?.response?.data?.message || 'Terjadi kesalahan saat mengirim pesan balasan.',
        type: 'warning',
      })
    } finally {
      setSending(false)
    }
  }

  const handleStatusChange = async (newStatus) => {
    if (!selectedTicket) return
    try {
      await ticketsApi.updateStatus(selectedTicket.id, newStatus)
      setSelectedTicket((prev) => ({ ...prev, status: newStatus }))
      fetchTickets(false)
      addAppNotification({
        title: 'Status Tiket Diperbarui',
        message: `Tiket #${selectedTicket.id} sekarang berstatus ${newStatus.toUpperCase()}.`,
        type: 'info',
      })
    } catch (err) {
      console.error('Failed to update status:', err)
    }
  }

  const handleDeleteTicket = async (ticket) => {
    if (!ticket) return
    setIsDeleting(true)
    try {
      await ticketsApi.delete(ticket.id)
      addAppNotification({
        title: 'Tiket Berhasil Dihapus',
        message: `Tiket #${ticket.id} (${ticket.citizen_name || 'Warga'}) telah dihapus secara permanen.`,
        type: 'success',
      })

      // Update local state
      setTickets((prev) => prev.filter((t) => t.id !== ticket.id))
      setStats((prev) => ({
        ...prev,
        total: Math.max(0, (prev.total || 1) - 1),
        [ticket.status]: Math.max(0, (prev[ticket.status] || 1) - 1),
      }))

      if (selectedTicket?.id === ticket.id) {
        setSelectedTicket(null)
        setMessages([])
      }

      setTicketToDelete(null)
    } catch (err) {
      console.error('Failed to delete ticket:', err)
      addAppNotification({
        title: 'Gagal Menghapus Tiket',
        message: err?.response?.data?.message || 'Terjadi kesalahan saat menghapus tiket.',
        type: 'warning',
      })
    } finally {
      setIsDeleting(false)
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'open':
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20">
            Terbuka
          </span>
        )
      case 'in_progress':
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-sky-500/10 text-sky-500 border border-sky-500/20">
            Diproses
          </span>
        )
      case 'resolved':
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
            Selesai
          </span>
        )
      default:
        return (
          <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
            {status}
          </span>
        )
    }
  }

  return (
    <div className="p-3 sm:p-4.5 max-w-[1700px] mx-auto flex flex-col h-[calc(100vh-76px)] overflow-hidden gap-3">
      {/* ── HEADER BANNER (CLEAN & COMPACT) ───────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 p-3 px-4 sm:px-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs shrink-0">
        <div className="flex items-center gap-2">
          <h1 className="text-lg sm:text-xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
            <span>LIVE CHAT & TIKET</span>
            <InfoTooltip
              size="lg"
              content="Antarmuka terpadu untuk merespons percakapan warga yang dialihkan (Human Handoff) secara real-time dari WhatsApp, Telegram, maupun Portal Web."
            />
          </h1>
        </div>

        {/* Best Practice: Clean Live Status Indicator + Sync Button */}
        <div className="flex items-center gap-2 self-start sm:self-auto">
          <div
            className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-semibold border border-emerald-500/20 shadow-xs"
            title="Sistem terhubung dan otomatis memperbarui pesan setiap 5 detik"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>Live</span>
          </div>

          <button
            onClick={() => fetchTickets(false)}
            className="p-1.5 rounded-xl bg-[var(--bg-input)] hover:bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-sky-500 border border-[var(--border-color)] transition-all duration-200 cursor-pointer shadow-xs active:scale-95"
            title="Perbarui Data Manual"
          >
            <svg
              className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-sky-500' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── STATS CARDS (COMPACT FIT) ──── */}
      <div
        className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-3 shrink-0"
        ref={statsGridRef}
      >
        {[
          {
            label: 'Tiket Terbuka',
            value: stats.open || 0,
            dotColor: 'bg-amber-500',
            tooltip: 'Percakapan warga yang baru masuk dan sedang menunggu respon pertama dari petugas.',
          },
          {
            label: 'Sedang Diproses',
            value: stats.in_progress || 0,
            dotColor: 'bg-sky-500',
            tooltip: 'Tiket yang telah diambil dan sedang dalam proses penanganan aktif oleh admin helpdesk.',
          },
          {
            label: 'Tiket Selesai',
            value: stats.resolved || 0,
            dotColor: 'bg-emerald-500',
            tooltip: 'Percakapan kendala warga yang telah berhasil diselesaikan dan ditutup secara tuntas.',
          },
          {
            label: 'Total Seluruh Tiket',
            value: stats.total || 0,
            dotColor: 'bg-purple-500',
            tooltip: 'Akumulasi seluruh riwayat tiket bantuan yang tercatat pada sistem.',
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] p-2.5 px-3.5 rounded-xl flex items-center justify-between hover:border-[var(--text-muted)]/40 transition-all duration-200 shadow-xs"
          >
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center">
                <span>{stat.label}</span>
                <InfoTooltip content={stat.tooltip} />
              </span>
              <h3 className="text-lg sm:text-xl font-black text-[var(--text-primary)] tracking-tight mt-0.5">
                {loading ? <div className="skeleton h-5 w-12" /> : stat.value}
              </h3>
            </div>
            <span className={`w-2.5 h-2.5 rounded-full ${stat.dotColor} shrink-0`} />
          </div>
        ))}
      </div>

      {/* ── SPLIT MAIN CHAT & QUEUE WORKSPACE (AUTO-FIT VIEWPORT) ───────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 flex-1 min-h-0 overflow-hidden">
        {/* Left Side: Ticket Queue List Card */}
        <div className="lg:col-span-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex flex-col h-full overflow-hidden shadow-xs">
          {/* 1. Card Header: Daftar Antrean Tiket */}
          <div className="p-2.5 px-3.5 border-b border-[var(--border-color)] bg-[var(--bg-input)] flex items-center justify-between shrink-0">
            <span className="font-bold text-xs uppercase tracking-wider text-[var(--text-muted)] flex items-center gap-2">
              <span>Daftar Antrean Tiket</span>
              <span className="px-2 py-0.5 rounded-full bg-[var(--bg-card)] text-[10px] font-black text-[var(--text-primary)] border border-[var(--border-color)]">
                {tickets.length}
              </span>
            </span>
          </div>

          {/* 2. Integrated Filter Tabs (BELOW DAFTAR ANTREAN TIKET) */}
          <div className="p-2 border-b border-[var(--border-color)] bg-[var(--bg-card)] shrink-0">
            <SlidingTabs
              tabs={[
                { id: 'all', label: 'Semua' },
                { id: 'open', label: 'Terbuka' },
                { id: 'in_progress', label: 'Diproses' },
                { id: 'resolved', label: 'Selesai' },
              ]}
              activeTab={activeTab}
              onChange={setActiveTab}
              variant="pill"
              fullWidth={true}
              className="w-full justify-between"
            />
          </div>

          {/* 2. Integrated Search Input (BELOW TABS) */}
          <div className="p-2.5 px-3 border-b border-[var(--border-color)] bg-[var(--bg-card)] shrink-0">
            <div className="relative w-full">
              <input
                type="text"
                placeholder="Cari nama warga atau ID tiket..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8.5 pr-3 py-1.5 text-xs bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
              />
              <svg className="w-3.5 h-3.5 absolute left-3 top-2.5 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
          </div>

          {/* Ticket List Stream */}
          <div className="flex-1 overflow-y-auto divide-y divide-[var(--border-color)]">
            {loading ? (
              <div className="p-8 text-center text-xs text-[var(--text-secondary)]">Memuat antrean...</div>
            ) : tickets.length === 0 ? (
              <div className="p-8 text-center text-xs text-[var(--text-secondary)] space-y-1">
                <p>Tidak ada tiket pada kategori ini.</p>
              </div>
            ) : (
              tickets.map((t) => {
                const isSelected = selectedTicket?.id === t.id
                return (
                  <div
                    key={t.id}
                    onClick={() => handleSelectTicket(t)}
                    className={`group p-3.5 cursor-pointer transition-colors flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-sky-500/10 border-l-4 border-l-sky-500'
                        : 'hover:bg-[var(--bg-input)]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-bold text-xs text-[var(--text-primary)] truncate flex items-center gap-1.5">
                        <span>{t.citizen_name || 'Warga / Anonim'}</span>
                        {t.citizen_agency && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-600 dark:text-sky-400 font-medium truncate max-w-[110px]">
                            {t.citizen_agency}
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] uppercase font-semibold text-[var(--text-muted)] shrink-0">
                        {t.channel || 'web'}
                      </span>
                    </div>

                    <div className="text-xs text-[var(--text-secondary)] line-clamp-2 leading-relaxed">
                      {t.issue_summary || t.last_message || 'Permintaan bantuan langsung dari warga.'}
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      {getStatusBadge(t.status)}
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">
                        #{t.id}
                      </span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right Side: Interactive Conversation Thread & Action Panel */}
        <div className="lg:col-span-8 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex flex-col h-full overflow-hidden shadow-xs relative">
          {selectedTicket ? (
            <>
              {/* Chat Thread Header */}
              <div className="p-3.5 px-5 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-card)] shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-sky-500/20 text-sky-500 flex items-center justify-center font-bold text-sm shrink-0">
                    {(selectedTicket.citizen_name?.charAt(0) || 'W').toUpperCase()}
                  </div>
                  <div>
                    <div className="font-bold text-sm text-[var(--text-primary)] flex items-center gap-2">
                      <span>{selectedTicket.citizen_name || 'Warga / Anonim'}</span>
                      {selectedTicket.citizen_agency && (
                        <span className="text-xs px-2 py-0.5 rounded-md bg-sky-500/10 text-sky-600 dark:text-sky-400 font-medium border border-sky-500/20">
                          {selectedTicket.citizen_agency}
                        </span>
                      )}
                      {getStatusBadge(selectedTicket.status)}
                    </div>
                    <div className="text-xs text-[var(--text-secondary)] flex items-center gap-2 mt-0.5">
                      <span>Kontak: {selectedTicket.citizen_contact || 'Via Chatbot'}</span>
                      <span>•</span>
                      <span>Kanal: {selectedTicket.channel || 'Web Portal'}</span>
                    </div>
                  </div>
                </div>

                {/* Status & Delete Action Buttons */}
                <div className="flex items-center gap-2">
                  {selectedTicket.status === 'open' && (
                    <button
                      onClick={() => handleStatusChange('in_progress')}
                      className="px-3.5 py-2 text-xs font-bold rounded-xl bg-sky-500 text-white hover:bg-sky-600 transition-colors shadow-sm cursor-pointer"
                    >
                      Ambil Tiket
                    </button>
                  )}
                  {selectedTicket.status !== 'resolved' && (
                    <button
                      onClick={() => handleStatusChange('resolved')}
                      className="px-3.5 py-2 text-xs font-bold rounded-xl bg-emerald-500 text-white hover:bg-emerald-600 transition-colors shadow-sm cursor-pointer"
                    >
                      Tandai Selesai
                    </button>
                  )}
                  {selectedTicket.status === 'resolved' && (
                    <button
                      onClick={() => handleStatusChange('in_progress')}
                      className="px-3.5 py-2 text-xs font-bold rounded-xl bg-[var(--bg-input)] text-[var(--text-secondary)] hover:text-sky-500 border border-[var(--border-color)] transition-colors cursor-pointer"
                    >
                      Buka Kembali
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setTicketToDelete(selectedTicket)}
                    title="Hapus Tiket"
                    className="px-3.5 py-2 text-xs font-bold rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400 hover:bg-rose-500 hover:text-white border border-rose-500/30 transition-all shadow-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    <span>Hapus Tiket</span>
                  </button>
                </div>
              </div>

              {/* Chat Message Stream */}
              <div
                ref={messagesContainerRef}
                onScroll={handleScroll}
                className="flex-1 p-5 overflow-y-auto space-y-4 bg-[var(--bg-main)] scroll-smooth"
              >
                {loadingMessages ? (
                  <div className="p-8 text-center text-xs text-[var(--text-secondary)]">Memuat percakapan...</div>
                ) : messages.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[var(--text-secondary)]">
                    Belum ada riwayat pesan percakapan pada tiket ini.
                  </div>
                ) : (
                  messages.map((msg, idx) => {
                    const rawText = (msg.message || msg.content || '').trim()
                    const isSystem = msg.sender_type === 'system'
                      || msg.sender === 'system'
                      || rawText.startsWith('Ticket Opened:')
                      || rawText.startsWith('Ticket Closed:')
                      || rawText.startsWith('Ticket Re-opened:')
                      || rawText.includes('── Ticket')

                    if (isSystem) {
                      const timeStr = msg.created_at
                        ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        : ''

                      let label = rawText
                      let icon = null
                      let badgeStyle = ''

                      if (rawText.includes('Closed')) {
                        const ticketNum = rawText.match(/TICK-[\w-]+/)?.[0] || selectedTicket?.ticket_number || ''
                        label = `Tiket Diselesaikan ${ticketNum ? `(${ticketNum})` : ''}`
                        badgeStyle = 'bg-[var(--bg-card)] border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                        icon = (
                          <svg className="w-3.5 h-3.5 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                        )
                      } else if (rawText.includes('Re-opened')) {
                        const ticketNum = rawText.match(/TICK-[\w-]+/)?.[0] || selectedTicket?.ticket_number || ''
                        label = `Tiket Dibuka Kembali ${ticketNum ? `(${ticketNum})` : ''}`
                        badgeStyle = 'bg-[var(--bg-card)] border-amber-500/30 text-amber-600 dark:text-amber-400'
                        icon = (
                          <svg className="w-3.5 h-3.5 text-amber-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                        )
                      } else if (rawText.includes('Opened')) {
                        const ticketNum = rawText.match(/TICK-[\w-]+/)?.[0] || selectedTicket?.ticket_number || ''
                        label = `Sesi Tiket Dimulai ${ticketNum ? `(${ticketNum})` : ''}`
                        badgeStyle = 'bg-[var(--bg-card)] border-sky-500/30 text-sky-600 dark:text-sky-400'
                        icon = (
                          <span className="w-1.5 h-1.5 rounded-full bg-sky-500 shrink-0 animate-pulse" />
                        )
                      } else {
                        badgeStyle = 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-muted)]'
                        icon = <span className="w-1.5 h-1.5 rounded-full bg-slate-400 shrink-0" />
                      }

                      return (
                        <div key={msg.id || idx} className="relative flex items-center justify-center my-3.5 w-full select-none animate-in fade-in zoom-in-95">
                          {/* Garis Horizontal Halus */}
                          <div className="absolute inset-0 flex items-center" aria-hidden="true">
                            <div className="w-full border-t border-[var(--border-color)]/70"></div>
                          </div>

                          {/* Floating Center Pill */}
                          <div className={`relative z-10 flex items-center gap-2 px-3.5 py-1 rounded-full border text-[11px] font-semibold shadow-xs transition-all ${badgeStyle}`}>
                            {icon}
                            <span>{label}</span>
                            {timeStr && (
                              <span className="text-[10px] font-mono opacity-60 font-normal">
                                • {timeStr}
                              </span>
                            )}
                          </div>
                        </div>
                      )
                    }

                    const isCitizen = msg.sender_type === 'citizen' || msg.sender === 'citizen' || msg.sender === 'user'
                    const isSystemAI = msg.sender_type === 'ai' || msg.sender === 'ai' || msg.sender === 'bot'
                    
                    let attachments = []
                    try {
                      if (typeof msg.attachments === 'string') {
                        attachments = JSON.parse(msg.attachments || '[]')
                      } else if (Array.isArray(msg.attachments)) {
                        attachments = msg.attachments
                      }
                    } catch (e) {
                      attachments = []
                    }

                    return (
                      <div
                        key={msg.id || idx}
                        className={`flex flex-col ${isCitizen ? 'items-start' : 'items-end'}`}
                      >
                        <div className="text-[10px] font-semibold text-[var(--text-muted)] mb-1 px-1">
                          {isCitizen
                            ? selectedTicket.citizen_name || 'Warga'
                            : isSystemAI
                            ? 'Asisten AI Diskominfotik'
                            : 'Petugas / Helpdesk'}
                        </div>
                        <div
                          className={`max-w-[80%] rounded-2xl p-3.5 text-xs leading-relaxed shadow-xs ${
                            isCitizen
                              ? 'bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-tl-sm'
                              : isSystemAI
                              ? 'bg-slate-500/10 text-[var(--text-primary)] border border-slate-500/20 rounded-tr-sm'
                              : 'bg-sky-600 text-white rounded-tr-sm'
                          }`}
                        >
                          {/* Text Message */}
                          {msg.message && msg.message !== '[Lampiran Foto]' && msg.message !== '[Lampiran Berkas]' && (
                            <div className="whitespace-pre-wrap">{msg.message || msg.content}</div>
                          )}

                          {/* Image & File Attachments */}
                          {attachments.length > 0 && (
                            <div className={`flex flex-col gap-2 ${msg.message && msg.message !== '[Lampiran Foto]' && msg.message !== '[Lampiran Berkas]' ? 'mt-2.5 pt-2 border-t border-current/10' : ''}`}>
                              {attachments.map((att, attIdx) => {
                                const isImg = (att.mime_type && att.mime_type.startsWith('image/'))
                                  || att.type === 'image'
                                  || att.type === 'photo'
                                  || /\.(jpg|jpeg|png|webp|gif)$/i.test(att.name || att.file_name || '')
                                
                                const fileUrl = att.url || `/api/tickets/${selectedTicket.id}/attachments/${att.file_name || att.name}`

                                if (isImg) {
                                  return (
                                    <div key={att.id || attIdx} className="relative group overflow-hidden rounded-xl border border-black/10 dark:border-white/10 shadow-xs max-w-xs">
                                      <img
                                        src={fileUrl}
                                        alt={att.name || 'Lampiran Gambar'}
                                        className="max-h-60 w-auto object-cover rounded-xl cursor-pointer hover:scale-102 transition-transform duration-200"
                                        onClick={() => setPreviewModalImg(fileUrl)}
                                        loading="lazy"
                                      />
                                      <div
                                        onClick={() => setPreviewModalImg(fileUrl)}
                                        className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2 text-white text-xs font-semibold cursor-pointer"
                                      >
                                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                                        </svg>
                                        <span>Perbesar Foto</span>
                                      </div>
                                    </div>
                                  )
                                }

                                return (
                                  <a
                                    key={att.id || attIdx}
                                    href={fileUrl}
                                    target="_blank"
                                    rel="noreferrer"
                                    download={att.name || 'berkas'}
                                    className={`flex items-center gap-2.5 p-2.5 rounded-xl border transition-colors ${
                                      isCitizen
                                        ? 'bg-[var(--bg-input)] border-[var(--border-color)] hover:border-sky-500'
                                        : 'bg-white/10 border-white/20 hover:bg-white/20 text-white'
                                    }`}
                                  >
                                    <svg className="w-5 h-5 text-sky-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                    </svg>
                                    <div className="flex-1 min-w-0">
                                      <div className="font-semibold text-xs truncate">{att.name || att.file_name || 'Dokumen Lampiran'}</div>
                                      {att.size && (
                                        <div className="text-[10px] opacity-70 font-mono">{(att.size / 1024).toFixed(1)} KB</div>
                                      )}
                                    </div>
                                    <svg className="w-4 h-4 shrink-0 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                    </svg>
                                  </a>
                                )
                              })}
                            </div>
                          )}
                        </div>
                        <span className="text-[9px] text-[var(--text-muted)] mt-1 px-1 font-mono">
                          {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </div>
                    )
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Floating WhatsApp-Style Scroll to Bottom Button (Centered) */}
              {showScrollBottomBtn && (
                <button
                  type="button"
                  onClick={() => scrollToBottom('smooth')}
                  className="absolute left-1/2 -translate-x-1/2 bottom-20 z-20 flex items-center gap-2 px-3.5 py-2 rounded-full bg-[var(--bg-card)]/95 backdrop-blur-md border border-[var(--border-color)] shadow-xl hover:border-sky-500 hover:shadow-sky-500/15 text-[var(--text-primary)] text-xs font-semibold transition-all duration-200 cursor-pointer group animate-in fade-in zoom-in-95"
                  title="Gulir ke pesan terbaru"
                >
                  <svg
                    className="w-4 h-4 text-sky-500 group-hover:translate-y-0.5 transition-transform"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                  </svg>
                  {unreadWhileScrolled > 0 ? (
                    <span className="flex items-center gap-1.5">
                      <span className="px-1.5 py-0.2 rounded-full bg-sky-500 text-white text-[10px] font-bold">
                        {unreadWhileScrolled}
                      </span>
                      <span className="text-[11px] text-sky-500 font-bold">Pesan Baru</span>
                    </span>
                  ) : (
                    <span className="text-[11px] text-[var(--text-secondary)]">Ke Bawah</span>
                  )}
                </button>
              )}

              {/* Reply Input Box */}
              <div className="bg-[var(--bg-card)] border-t border-[var(--border-color)] flex flex-col">
                {/* File Attachment Chip Preview */}
                {selectedFile && (
                  <div className="px-4 pt-3 pb-1 flex items-center gap-2 animate-in fade-in">
                    <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-sky-500/10 border border-sky-500/30 text-sky-600 dark:text-sky-400 text-xs font-medium">
                      {filePreviewUrl ? (
                        <img src={filePreviewUrl} alt="Preview" className="w-6 h-6 rounded-md object-cover" />
                      ) : (
                        <svg className="w-4 h-4 text-sky-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                        </svg>
                      )}
                      <span className="truncate max-w-[200px]">{selectedFile.name}</span>
                      <span className="text-[10px] opacity-75 font-mono">({(selectedFile.size / 1024).toFixed(0)} KB)</span>
                      <button
                        type="button"
                        onClick={handleClearFile}
                        className="ml-1 p-0.5 hover:bg-sky-500/20 rounded-md transition-colors cursor-pointer text-slate-500 hover:text-rose-500"
                        title="Batal lampirkan file"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </div>
                )}

                <form onSubmit={handleSendReply} className="p-3.5 px-4 flex items-center gap-2">
                  {/* Hidden File Input */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileChange}
                    accept="image/*,.pdf"
                    className="hidden"
                  />

                  {/* Attachment Button */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={sending || selectedTicket.status === 'resolved'}
                    className="p-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-secondary)] hover:text-sky-500 hover:border-sky-500/40 disabled:opacity-50 transition-colors cursor-pointer shrink-0"
                    title="Lampirkan Gambar atau Berkas PDF (Maks 10 MB)"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                    </svg>
                  </button>

                  <input
                    type="text"
                    placeholder={selectedFile ? "Tambahkan pesan atau kirim lampiran..." : "Ketik balasan resmi petugas di sini..."}
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    disabled={sending || selectedTicket.status === 'resolved'}
                    className="flex-1 px-4 py-2.5 text-xs bg-[var(--bg-input)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] focus:outline-none focus:border-sky-500 disabled:opacity-50 transition-colors"
                  />

                  <button
                    type="submit"
                    disabled={(!replyText.trim() && !selectedFile) || sending || selectedTicket.status === 'resolved'}
                    className="px-4 py-2.5 text-xs font-bold rounded-xl bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-40 transition-colors flex items-center gap-1.5 shrink-0 shadow-sm cursor-pointer"
                  >
                    {sending ? (
                      <span>Mengirim...</span>
                    ) : (
                      <>
                        <span>Kirim</span>
                        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                        </svg>
                      </>
                    )}
                  </button>
                </form>
              </div>
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-[var(--text-secondary)]">
              <svg className="w-12 h-12 mb-3 text-slate-400 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-sm font-medium">Pilih tiket di sebelah kiri untuk melihat percakapan</p>
            </div>
          )}
        </div>
      </div>

      {/* Delete Ticket Confirmation Modal */}
      {ticketToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs animate-in fade-in duration-150">
          <div
            className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-5 sm:p-6 max-w-md w-full shadow-2xl space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-rose-500/10 text-rose-500 flex items-center justify-center shrink-0">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <div>
                <h3 className="text-base font-bold text-[var(--text-primary)]">Hapus Tiket Antrean</h3>
                <p className="text-xs text-[var(--text-secondary)]">Konfirmasi penghapusan tiket bantuan</p>
              </div>
            </div>

            <div className="p-3.5 bg-[var(--bg-input)] rounded-xl border border-[var(--border-color)] text-xs space-y-1.5">
              <div className="flex justify-between text-[var(--text-secondary)]">
                <span>Nomor Tiket:</span>
                <span className="font-mono font-bold text-[var(--text-primary)]">{ticketToDelete.ticket_number || `#${ticketToDelete.id}`}</span>
              </div>
              <div className="flex justify-between text-[var(--text-secondary)]">
                <span>Warga / Pengirim:</span>
                <span className="font-bold text-[var(--text-primary)]">{ticketToDelete.citizen_name || 'Warga / Anonim'}</span>
              </div>
              {ticketToDelete.citizen_agency && (
                <div className="flex justify-between text-[var(--text-secondary)]">
                  <span>Instansi:</span>
                  <span className="font-semibold text-sky-500">{ticketToDelete.citizen_agency}</span>
                </div>
              )}
              <div className="flex justify-between text-[var(--text-secondary)]">
                <span>Kanal:</span>
                <span className="uppercase font-semibold text-[var(--text-muted)]">{ticketToDelete.channel || 'web'}</span>
              </div>
            </div>

            <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
              Apakah Anda yakin ingin menghapus tiket ini? Seluruh riwayat obrolan, catatan internal, dan berkas lampiran pada tiket ini akan dihapus secara permanen dari basis data.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setTicketToDelete(null)}
                className="px-4 py-2 text-xs font-semibold rounded-lg bg-[var(--bg-input)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer"
              >
                Batal
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => handleDeleteTicket(ticketToDelete)}
                className="px-4 py-2 text-xs font-bold rounded-lg bg-rose-500 text-white hover:bg-rose-600 disabled:opacity-50 transition-colors shadow-sm flex items-center gap-1.5 cursor-pointer"
              >
                {isDeleting ? (
                  <>
                    <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>Menghapus...</span>
                  </>
                ) : (
                  <span>Ya, Hapus Tiket</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Image Lightbox Modal Zoom */}
      {previewModalImg && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center p-4 animate-in fade-in duration-200"
          onClick={() => setPreviewModalImg(null)}
        >
          <div className="relative max-w-4xl max-h-[90vh] flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            <div className="absolute top-3 right-3 flex items-center gap-2 z-10">
              <a
                href={previewModalImg}
                download="lampiran-tiket.jpg"
                target="_blank"
                rel="noreferrer"
                className="p-2 rounded-full bg-black/60 hover:bg-black/80 text-white transition-colors cursor-pointer shadow-md"
                title="Unduh Gambar"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                </svg>
              </a>
              <button
                type="button"
                onClick={() => setPreviewModalImg(null)}
                className="p-2 rounded-full bg-black/60 hover:bg-black/80 text-white transition-colors cursor-pointer shadow-md"
                title="Tutup (Esc)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <img
              src={previewModalImg}
              alt="Pratinjau Foto"
              className="max-h-[85vh] max-w-full object-contain rounded-xl shadow-2xl border border-white/10"
            />
          </div>
        </div>
      )}
    </div>
  )
}
