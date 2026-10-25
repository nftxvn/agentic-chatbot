import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { ticketsApi } from '../../api/tickets'
import { loadTicketQueue, loadTicketMessages } from '../../services/liveChatService'
import { addAppNotification } from '../../utils/notifications'
import { useConversationScroll } from './useConversationScroll'
import { useTicketAttachment } from './useTicketAttachment'

/**
 * State dan tindakan halaman live chat. Polling tetap 5 detik; pembaruan sidebar
 * tetap memakai app-tickets-updated. Rendering dan animasi dimiliki halaman.
 */
export function useLiveChat() {
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
  const [ticketToDelete, setTicketToDelete] = useState(null)
  const [isDeleting, setIsDeleting] = useState(false)

  const { selectedFile, filePreviewUrl, fileInputRef, handleFileChange, handleClearFile } = useTicketAttachment()

  const replyInputRef = useRef(null)
  const shouldRefocusReplyInputRef = useRef(false)
  const sendingTicketIdRef = useRef(null)
  const activeTicketIdRef = useRef(null)
  const messagesRequestRef = useRef(0)
  const queueRequestRef = useRef(0)

  useLayoutEffect(() => {
    activeTicketIdRef.current = selectedTicket?.id ?? null
  }, [selectedTicket?.id])

  useLayoutEffect(() => {
    if (sending || !shouldRefocusReplyInputRef.current) return

    if (sendingTicketIdRef.current === selectedTicket?.id && selectedTicket?.status !== 'resolved') {
      replyInputRef.current?.focus()
    }

    shouldRefocusReplyInputRef.current = false
    sendingTicketIdRef.current = null
  }, [sending, selectedTicket?.id, selectedTicket?.status])

  // Pembaruan antrean dan pesan tetap mempunyai state loading yang terpisah.
  const fetchTickets = async (showLoading = false) => {
    const requestId = ++queueRequestRef.current
    if (showLoading) setLoading(true)
    setIsRefreshing(true)
    try {
      const { tickets: list, stats: nextStats } = await loadTicketQueue(activeTab, searchQuery)
      if (requestId !== queueRequestRef.current) return
      setTickets(list)

      if (nextStats) {
        setStats(nextStats)
        window.dispatchEvent(new CustomEvent('app-tickets-updated'))
      }

      // If a ticket is currently selected, refresh its detail
      if (activeTicketIdRef.current !== null) {
        setSelectedTicket(current => list.find(t => t.id === current?.id) || current)
      } else if (list.length > 0) {
        handleSelectTicket(list[0])
      }
    } catch (err) {
      console.error('Failed to load tickets:', err)
    } finally {
      if (requestId === queueRequestRef.current) {
        setLoading(false)
        setTimeout(() => {
          if (requestId === queueRequestRef.current) setIsRefreshing(false)
        }, 400)
      }
    }
  }

  const fetchMessages = async (ticketId, isInitial = false) => {
    if (activeTicketIdRef.current !== ticketId) return
    const requestId = ++messagesRequestRef.current
    if (isInitial) {
      setLoadingMessages(true)
      setUnreadWhileScrolled(0)
      setShowScrollBottomBtn(false)
      isNearBottomRef.current = true
    }
    try {
      const msgList = await loadTicketMessages(ticketId)
      if (activeTicketIdRef.current !== ticketId || requestId !== messagesRequestRef.current) return
      setMessages(msgList)
      if (isInitial) {
        prevMessagesLengthRef.current = msgList.length
        setTimeout(() => {
          if (activeTicketIdRef.current === ticketId && requestId === messagesRequestRef.current)
            scrollToBottom('auto')
        }, 50)
      }
    } catch (err) {
      console.error('Failed to load messages for ticket:', ticketId, err)
    } finally {
      if (activeTicketIdRef.current === ticketId && requestId === messagesRequestRef.current)
        setLoadingMessages(false)
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

  const {
    showScrollBottomBtn,
    unreadWhileScrolled,
    messagesContainerRef,
    messagesEndRef,
    isNearBottomRef,
    prevMessagesLengthRef,
    setShowScrollBottomBtn,
    setUnreadWhileScrolled,
    handleScroll,
    scrollToBottom,
  } = useConversationScroll(messages)

  // Sinkronisasi latar belakang dengan interval dan dependency yang sama.
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
    activeTicketIdRef.current = t?.id ?? null
    setSelectedTicket(t)
  }

  const handleSendReply = async (e) => {
    e?.preventDefault()
    if ((!replyText.trim() && !selectedFile) || !selectedTicket || sending) return

    shouldRefocusReplyInputRef.current = true
    sendingTicketIdRef.current = selectedTicket.id
    setSending(true)
    try {
      await ticketsApi.reply(selectedTicket.id, replyText.trim(), selectedFile)
      setReplyText('')
      handleClearFile()
      if (activeTicketIdRef.current === selectedTicket.id) {
        await fetchMessages(selectedTicket.id, false)
        if (activeTicketIdRef.current === selectedTicket.id) scrollToBottom()
      }
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
      if (activeTicketIdRef.current === selectedTicket.id)
        setSelectedTicket((prev) => ({ ...prev, status: newStatus }))
      fetchTickets(false)
      addAppNotification({
        title: 'Status Tiket Diperbarui',
        message: `Tiket ${selectedTicket.ticket_number || `#${selectedTicket.id}`} sekarang berstatus ${newStatus.toUpperCase()}.`,
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
        message: `Tiket ${ticket.ticket_number || `#${ticket.id}`} (${ticket.citizen_name || 'Warga'}) telah dihapus secara permanen.`,
        type: 'success',
      })

      // Update local state
      setTickets((prev) => prev.filter((t) => t.id !== ticket.id))
      setStats((prev) => ({
        ...prev,
        total: Math.max(0, (prev.total || 1) - 1),
        [ticket.status]: Math.max(0, (prev[ticket.status] || 1) - 1),
      }))

      if (activeTicketIdRef.current === ticket.id) {
        activeTicketIdRef.current = null
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

  return {
    activeTab,
    setActiveTab,
    tickets,
    selectedTicket,
    messages,
    replyText,
    setReplyText,
    loading,
    loadingMessages,
    sending,
    isRefreshing,
    searchQuery,
    setSearchQuery,
    showScrollBottomBtn,
    unreadWhileScrolled,
    selectedFile,
    filePreviewUrl,
    ticketToDelete,
    setTicketToDelete,
    isDeleting,
    messagesContainerRef,
    messagesEndRef,
    replyInputRef,
    fileInputRef,
    handleScroll,
    scrollToBottom,
    fetchTickets,
    handleSelectTicket,
    handleFileChange,
    handleClearFile,
    handleSendReply,
    handleStatusChange,
    handleDeleteTicket,
  }
}
