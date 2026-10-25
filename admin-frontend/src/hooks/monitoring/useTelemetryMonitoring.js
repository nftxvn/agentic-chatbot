import { useState, useEffect, useRef, useLayoutEffect } from "react";
import gsap from "gsap";
import { chatLogsApi } from "../../api/chatLogs";
import { addAppNotification } from "../../utils/notifications";

/** Data telemetri/analitik, filter, pagination, pencarian, serta tindakan hapus/purge. */
export function useTelemetryMonitoring() {
  const [logs, setLogs] = useState([])
  const [analytics, setAnalytics] = useState(null)
  const [pagination, setPagination] = useState({ current_page: 1, last_page: 1, total: 0 })
  const [loading, setLoading] = useState(true)
  const [statusMsg, setStatusMsg] = useState(null)

  // Filters
  const [channelFilter, setChannelFilter] = useState('all')
  const [fallbackFilter, setFallbackFilter] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [page, setPage] = useState(1)

  // Modals
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [showPurgeModal, setShowPurgeModal] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const statsRef = useRef(null)

  useEffect(() => {
    fetchLogs()
    fetchAnalytics()
  }, [page, channelFilter, fallbackFilter])

  useLayoutEffect(() => {
    if (!loading && statsRef.current) {
      gsap.fromTo(
        statsRef.current.children,
        { opacity: 0, y: 10, scale: 0.98 },
        { opacity: 1, y: 0, scale: 1, duration: 0.35, stagger: 0.04, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  async function fetchLogs() {
    try {
      setLoading(true)
      const params = {
        page,
        per_page: 15,
        search: searchQuery || undefined,
        channel: channelFilter !== 'all' ? channelFilter : undefined,
        is_fallback: fallbackFilter === 'fallback' ? 1 : fallbackFilter === 'success' ? 0 : undefined,
      }
      const res = await chatLogsApi.list(params)
      setLogs(res.data || [])
      setPagination(res.pagination || { current_page: 1, last_page: 1, total: 0 })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal memuat catatan telemetri dari server.' })
    } finally {
      setLoading(false)
    }
  }

  async function fetchAnalytics() {
    try {
      const res = await chatLogsApi.analytics()
      setAnalytics(res.data || null)
    } catch (err) {
      console.error('Failed to load analytics:', err)
    }
  }

  const handleSearchSubmit = (e) => {
    e.preventDefault()
    setPage(1)
    fetchLogs()
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setDeleting(true)
    try {
      await chatLogsApi.delete(deleteTarget.id)
      setLogs((prev) => prev.filter((l) => l.id !== deleteTarget.id))
      setDeleteTarget(null)
      fetchAnalytics()
      addAppNotification({
        title: 'Telemetri Dihapus',
        message: 'Baris catatan telemetri telah dihapus.',
        type: 'info',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal menghapus catatan telemetri.' })
    } finally {
      setDeleting(false)
    }
  }

  const handlePurge = async () => {
    setDeleting(true)
    try {
      await chatLogsApi.purge()
      setLogs([])
      setShowPurgeModal(false)
      fetchAnalytics()
      addAppNotification({
        title: 'Telemetri Dikosongkan',
        message: 'Seluruh data telemetri interaksi telah dibersihkan.',
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal membersihkan data telemetri.' })
    } finally {
      setDeleting(false)
    }
  }

  return {
    logs,
    analytics,
    pagination,
    loading,
    statusMsg,
    setStatusMsg,
    channelFilter,
    setChannelFilter,
    fallbackFilter,
    setFallbackFilter,
    searchQuery,
    setSearchQuery,
    page,
    setPage,
    deleteTarget,
    setDeleteTarget,
    showPurgeModal,
    setShowPurgeModal,
    statsRef,
    handleSearchSubmit,
    handleDelete,
    handlePurge,
  };
}
