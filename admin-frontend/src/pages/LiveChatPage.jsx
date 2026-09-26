import { useState, useEffect, useRef } from 'react'
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
  const [searchQuery, setSearchQuery] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(true)

  const messagesEndRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Fetch ticket lists & stats
  const fetchTickets = async (showLoading = false) => {
    if (showLoading) setLoading(true)
    try {
      const [ticketRes, statRes] = await Promise.all([
        ticketsApi.list({
          status: activeTab !== 'all' ? activeTab : undefined,
          search: searchQuery || undefined,
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
    }
  }

  // Fetch messages for selected ticket
  const fetchMessages = async (ticketId, isInitial = false) => {
    if (isInitial) setLoadingMessages(true)
    try {
      const res = await ticketsApi.getMessages(ticketId)
      const msgList = res?.data || res?.messages || (Array.isArray(res) ? res : [])
      setMessages(msgList)
      if (isInitial) {
        setTimeout(scrollToBottom, 100)
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

  // Real-time polling timer (5s)
  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      fetchTickets(false)
      if (selectedTicket?.id) {
        fetchMessages(selectedTicket.id, false)
      }
    }, 5000)
    return () => clearInterval(interval)
  }, [autoRefresh, selectedTicket?.id, activeTab, searchQuery])

  const handleSelectTicket = (t) => {
    setSelectedTicket(t)
  }

  const handleSendReply = async (e) => {
    e?.preventDefault()
    if (!replyText.trim() || !selectedTicket || sending) return

    setSending(true)
    try {
      const res = await ticketsApi.reply(selectedTicket.id, replyText.trim())
      setReplyText('')
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

  const getStatusBadge = (status) => {
    switch (status) {
      case 'open':
        return (
          <span className="px-2.5 py-0.5 text-xs font-bold rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20 animate-pulse">
            Terbuka (Menunggu)
          </span>
        )
      case 'in_progress':
        return (
          <span className="px-2.5 py-0.5 text-xs font-bold rounded-full bg-sky-500/10 text-sky-500 border border-sky-500/20">
            Sedang Ditangani
          </span>
        )
      case 'resolved':
        return (
          <span className="px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20">
            Selesai
          </span>
        )
      default:
        return (
          <span className="px-2.5 py-0.5 text-xs font-bold rounded-full bg-slate-500/10 text-slate-400 border border-slate-500/20">
            {status}
          </span>
        )
    }
  }

  return (
    <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5 pb-16">
      {/* ── HEADER BANNER ───────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div>
          <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
            <span>LIVE CHAT & HELPDESK TIKET</span>
            <InfoTooltip
              size="lg"
              content="Antarmuka terpadu untuk merespons percakapan warga yang dialihkan (Human Handoff) secara real-time dari WhatsApp, Telegram, maupun Portal Web."
            />
          </h1>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)] mt-0.5">
            Kelola dan balas pertanyaan warga yang membutuhkan bantuan langsung dari staf Diskominfotik Kota Banda Aceh.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg border transition-colors flex items-center gap-1.5 ${
              autoRefresh
                ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20'
                : 'bg-[var(--bg-input)] text-[var(--text-secondary)] border-[var(--border-color)]'
            }`}
          >
            <span className={`w-2 h-2 rounded-full ${autoRefresh ? 'bg-emerald-500 animate-ping' : 'bg-slate-400'}`} />
            <span>{autoRefresh ? 'Live Sync Aktif' : 'Sync Dijeda'}</span>
          </button>
          <button
            onClick={() => fetchTickets(true)}
            className="p-2 rounded-lg bg-[var(--bg-input)] hover:bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-sky-500 border border-[var(--border-color)] transition-colors"
            title="Refresh Manual"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>
      </div>

      {/* ── STATS SUMMARY CARDS ─────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-lg bg-amber-500/10 text-amber-500 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <div className="text-xs text-[var(--text-secondary)] font-medium">Tiket Terbuka</div>
            <div className="text-xl font-bold text-[var(--text-primary)]">{stats.open || 0}</div>
          </div>
        </div>

        <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-lg bg-sky-500/10 text-sky-500 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
          </div>
          <div>
            <div className="text-xs text-[var(--text-secondary)] font-medium">Sedang Diproses</div>
            <div className="text-xl font-bold text-[var(--text-primary)]">{stats.in_progress || 0}</div>
          </div>
        </div>

        <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 text-emerald-500 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div>
            <div className="text-xs text-[var(--text-secondary)] font-medium">Tiket Selesai</div>
            <div className="text-xl font-bold text-[var(--text-primary)]">{stats.resolved || 0}</div>
          </div>
        </div>

        <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex items-center gap-3.5">
          <div className="w-10 h-10 rounded-lg bg-purple-500/10 text-purple-500 flex items-center justify-center shrink-0">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
          </div>
          <div>
            <div className="text-xs text-[var(--text-secondary)] font-medium">Total Seluruh Tiket</div>
            <div className="text-xl font-bold text-[var(--text-primary)]">{stats.total || 0}</div>
          </div>
        </div>
      </div>

      {/* ── FILTER & SEARCH TABS ────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <SlidingTabs
          tabs={[
            { id: 'all', label: 'Semua Tiket' },
            { id: 'open', label: 'Terbuka' },
            { id: 'in_progress', label: 'Diproses' },
            { id: 'resolved', label: 'Selesai' },
          ]}
          activeTab={activeTab}
          onChange={setActiveTab}
          variant="pill"
        />

        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="Cari nama atau nomor..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3.5 py-2 text-xs bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
          />
          <svg className="w-4 h-4 absolute left-3 top-2.5 text-[var(--text-secondary)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* ── SPLIT MAIN CHAT & QUEUE WORKSPACE ───────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 h-[700px]">
        {/* Left Side: Ticket Queue List */}
        <div className="lg:col-span-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex flex-col h-full overflow-hidden">
          <div className="p-3.5 border-b border-[var(--border-color)] font-bold text-xs uppercase tracking-wider text-[var(--text-secondary)] flex items-center justify-between">
            <span>Daftar Antrean Tiket ({tickets.length})</span>
          </div>

          <div className="flex-1 overflow-y-auto divide-y divide-[var(--border-color)]">
            {loading ? (
              <div className="p-8 text-center text-xs text-[var(--text-secondary)]">Memuat daftar tiket...</div>
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
                    className={`p-3.5 cursor-pointer transition-colors flex flex-col gap-1.5 ${
                      isSelected
                        ? 'bg-sky-500/10 border-l-4 border-l-sky-500'
                        : 'hover:bg-[var(--bg-input)]'
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="font-bold text-xs text-[var(--text-primary)] truncate">
                        {t.citizen_name || 'Warga / Anonim'}
                      </div>
                      <span className="text-[10px] text-[var(--text-secondary)] shrink-0">
                        {t.channel || 'web'}
                      </span>
                    </div>

                    <div className="text-xs text-[var(--text-secondary)] line-clamp-2">
                      {t.issue_summary || t.last_message || 'Permintaan bantuan langsung dari warga.'}
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      {getStatusBadge(t.status)}
                      <span className="text-[10px] text-[var(--text-secondary)]">
                        Tiket #{t.id}
                      </span>
                    </div>
                  </div>
                )
              })
            )}
          </div>
        </div>

        {/* Right Side: Conversation Thread & Action Panel */}
        <div className="lg:col-span-8 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl flex flex-col h-full overflow-hidden">
          {selectedTicket ? (
            <>
              {/* Chat Thread Header */}
              <div className="p-3.5 px-5 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-card)] shrink-0">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-sky-500/20 text-sky-500 flex items-center justify-center font-bold text-sm">
                    {(selectedTicket.citizen_name?.charAt(0) || 'W').toUpperCase()}
                  </div>
                  <div>
                    <div className="font-bold text-sm text-[var(--text-primary)] flex items-center gap-2">
                      <span>{selectedTicket.citizen_name || 'Warga / Anonim'}</span>
                      {getStatusBadge(selectedTicket.status)}
                    </div>
                    <div className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
                      <span>Kontak: {selectedTicket.citizen_contact || 'Via Chatbot'}</span>
                      <span>•</span>
                      <span>Kanal: {selectedTicket.channel || 'Web Portal'}</span>
                    </div>
                  </div>
                </div>

                {/* Status Action Buttons */}
                <div className="flex items-center gap-2">
                  {selectedTicket.status === 'open' && (
                    <button
                      onClick={() => handleStatusChange('in_progress')}
                      className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-500 text-white hover:bg-sky-600 transition-colors shadow-sm"
                    >
                      Ambil Tiket
                    </button>
                  )}
                  {selectedTicket.status !== 'resolved' && (
                    <button
                      onClick={() => handleStatusChange('resolved')}
                      className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-500 text-white hover:bg-emerald-600 transition-colors shadow-sm"
                    >
                      Tandai Selesai
                    </button>
                  )}
                  {selectedTicket.status === 'resolved' && (
                    <button
                      onClick={() => handleStatusChange('in_progress')}
                      className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--bg-input)] text-[var(--text-secondary)] hover:text-sky-500 border border-[var(--border-color)] transition-colors"
                    >
                      Buka Kembali
                    </button>
                  )}
                </div>
              </div>

              {/* Chat Message Stream */}
              <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-[var(--bg-main)]">
                {loadingMessages ? (
                  <div className="p-8 text-center text-xs text-[var(--text-secondary)]">Memuat percakapan...</div>
                ) : messages.length === 0 ? (
                  <div className="p-8 text-center text-xs text-[var(--text-secondary)]">
                    Belum ada riwayat pesan percakapan pada tiket ini.
                  </div>
                ) : (
                  messages.map((msg, idx) => {
                    const isCitizen = msg.sender_type === 'citizen' || msg.sender === 'citizen' || msg.sender === 'user'
                    const isSystemAI = msg.sender_type === 'ai' || msg.sender === 'ai' || msg.sender === 'bot'
                    return (
                      <div
                        key={msg.id || idx}
                        className={`flex flex-col ${isCitizen ? 'items-start' : 'items-end'}`}
                      >
                        <div className="text-[10px] text-[var(--text-secondary)] mb-1 px-1">
                          {isCitizen
                            ? selectedTicket.citizen_name || 'Warga'
                            : isSystemAI
                            ? 'Asisten AI Diskominfotik'
                            : 'Petugas / Helpdesk'}
                        </div>
                        <div
                          className={`max-w-[80%] rounded-2xl p-3.5 text-xs leading-relaxed shadow-sm ${
                            isCitizen
                              ? 'bg-[var(--bg-card)] text-[var(--text-primary)] border border-[var(--border-color)] rounded-tl-sm'
                              : isSystemAI
                              ? 'bg-slate-500/10 text-[var(--text-primary)] border border-slate-500/20 rounded-tr-sm'
                              : 'bg-sky-600 text-white rounded-tr-sm'
                          }`}
                        >
                          {msg.message || msg.content}
                        </div>
                        <span className="text-[9px] text-[var(--text-secondary)] mt-1 px-1">
                          {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                      </div>
                    )
                  })
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Reply Input Box */}
              <form onSubmit={handleSendReply} className="p-3.5 px-4 bg-[var(--bg-card)] border-t border-[var(--border-color)] flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Ketik balasan resmi petugas di sini..."
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  disabled={sending || selectedTicket.status === 'resolved'}
                  className="flex-1 px-4 py-2.5 text-xs bg-[var(--bg-input)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] focus:outline-none focus:border-sky-500 disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!replyText.trim() || sending || selectedTicket.status === 'resolved'}
                  className="px-4 py-2.5 text-xs font-bold rounded-xl bg-sky-500 text-white hover:bg-sky-600 disabled:opacity-40 transition-colors flex items-center gap-1.5 shrink-0 shadow-sm"
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
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-[var(--text-secondary)]">
              <svg className="w-12 h-12 mb-3 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="text-sm font-medium">Pilih tiket di sebelah kiri untuk melihat percakapan</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
