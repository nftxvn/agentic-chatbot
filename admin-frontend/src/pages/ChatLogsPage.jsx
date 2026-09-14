import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import gsap from 'gsap'
import { chatLogsApi } from '../api/chatLogs'
import ConfirmModal from '../components/ConfirmModal'
import { addAppNotification } from '../utils/notifications'
import { InfoTooltip } from '../components/UI/InfoTooltip'

export default function ChatLogsPage() {
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

  // Modals & Drawers
  const [selectedLog, setSelectedLog] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [showPurgeModal, setShowPurgeModal] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const headerRef = useRef(null)
  const statsRef = useRef(null)

  useEffect(() => {
    fetchLogs()
    fetchAnalytics()
  }, [page, channelFilter, fallbackFilter])

  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -16 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out', clearProps: 'all' }
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
      setStatusMsg({ type: 'error', text: 'Gagal memuat riwayat percakapan dari server.' })
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
        title: 'Riwayat Dihapus',
        message: 'Entri log percakapan telah dihapus.',
        type: 'info',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal menghapus log percakapan.' })
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
        title: 'Riwayat Dikosongkan',
        message: 'Seluruh data riwayat percakapan telah dibersihkan.',
        type: 'system',
      })
    } catch (err) {
      console.error(err)
      setStatusMsg({ type: 'error', text: 'Gagal membersihkan riwayat percakapan.' })
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5 pb-20">
      {/* ── HEADER BANNER ───────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div ref={headerRef} className="space-y-1">
          <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight flex items-center">
            <span>RIWAYAT & ANALITIK PERCAKAPAN</span>
            <InfoTooltip size="lg" content="Pantau seluruh riwayat interaksi AI, audit pertanyaan masyarakat dari WhatsApp, Telegram, dan API pihak ketiga, serta identifikasi materi SOP yang perlu dilengkapi." />
          </h1>
        </div>

        <div className="flex items-center gap-2.5 shrink-0 self-start md:self-auto">
          {logs.length > 0 && (
            <button
              type="button"
              onClick={() => setShowPurgeModal(true)}
              className="px-3.5 py-2 rounded-xl text-xs font-semibold text-[var(--red-color)] hover:bg-[var(--bg-card)] bg-[var(--bg-input)] border border-[var(--border-color)] transition-colors cursor-pointer flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
              </svg>
              <span>Bersihkan Riwayat</span>
            </button>
          )}
        </div>
      </div>

      {/* ── TOP STATS ANALYTICS ─────────────────────────────────── */}
      <div ref={statsRef} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5 sm:gap-4">
        {[
          {
            label: 'Total Pertanyaan',
            value: analytics ? analytics.total_queries.toLocaleString('id-ID') : '0',
            dotColor: 'bg-sky-500',
            tooltip: 'Jumlah total seluruh interaksi pesan yang diproses oleh sistem AI.',
          },
          {
            label: 'Kanal WhatsApp',
            value: analytics ? analytics.whatsapp_count.toLocaleString('id-ID') : '0',
            dotColor: 'bg-emerald-500',
            tooltip: 'Akumulasi pesan yang masuk dan dijawab melalui integrasi WhatsApp Gateway.',
          },
          {
            label: 'Kanal Telegram',
            value: analytics ? (analytics.telegram_count ?? 0).toLocaleString('id-ID') : '0',
            dotColor: 'bg-cyan-500',
            tooltip: 'Akumulasi pesan yang masuk dan dijawab melalui bot Telegram resmi.',
          },
          {
            label: 'Public API Gateway',
            value: analytics ? analytics.api_count.toLocaleString('id-ID') : '0',
            dotColor: 'bg-indigo-400',
            tooltip: 'Jumlah pemanggilan endpoint API /api/v1/chat dari aplikasi eksternal.',
          },
          {
            label: 'Rasio Tidak Ditemukan',
            value: analytics ? `${analytics.fallback_rate_pct}%` : '0%',
            dotColor: 'bg-amber-500',
            tooltip: 'Persentase pertanyaan yang tidak menemukan fakta di SOP sehingga memicu pesan fallback.',
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 sm:p-5 rounded-xl flex flex-col justify-between hover:border-[var(--text-muted)]/40 transition-all duration-200 shadow-xs"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] flex items-center">
                <span>{stat.label}</span>
                <InfoTooltip content={stat.tooltip} />
              </span>
              <span className={`w-2 h-2 rounded-full ${stat.dotColor} shrink-0`} />
            </div>
            <div className="text-2xl sm:text-3xl font-black text-[var(--text-primary)] tracking-tight mt-3">
              {stat.value}
            </div>
          </div>
        ))}
      </div>

      {/* ── UNANSWERED / FALLBACK INTELLIGENCE CARD ─────────────── */}
      {analytics && analytics.recent_fallbacks && analytics.recent_fallbacks.length > 0 && (
        <div className="p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl space-y-3">
          <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
            <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <h3 className="text-xs font-bold uppercase tracking-wider">
              Evaluasi SOP: Pertanyaan yang Belum Ditemukan Jawabannya di Korpus
            </h3>
          </div>
          <p className="text-xs text-[var(--text-secondary)] leading-relaxed">
            Masyarakat atau aplikasi menanyakan hal berikut, namun informasi belum termuat dalam dokumen SOP yang diunggah. Jadikan daftar ini sebagai panduan untuk menambahkan dokumen SOP baru:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-1">
            {analytics.recent_fallbacks.map((item) => (
              <div
                key={item.id}
                className="p-3 rounded-lg bg-[var(--bg-input)]/50 border border-[var(--border-color)] text-xs space-y-1"
              >
                <p className="font-semibold text-[var(--text-primary)] line-clamp-2">
                  "{item.query}"
                </p>
                <div className="flex items-center justify-between text-xs text-[var(--text-muted)]">
                  <span className="capitalize">{item.channel}</span>
                  <span>{new Date(item.created_at).toLocaleString('id-ID')}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── FILTER & SEARCH BAR ─────────────────────────────────── */}
      <div className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs space-y-3">
        <form onSubmit={handleSearchSubmit} className="flex flex-col md:flex-row gap-3 items-center justify-between">
          <div className="w-full md:w-80 relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Cari pertanyaan, pengirim, atau jawaban..."
              className="w-full pl-9 pr-3.5 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 transition-colors"
            />
            <svg className="w-4 h-4 text-[var(--text-muted)] absolute left-3 top-1/2 -translate-y-1/2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
            </svg>
          </div>

          <div className="flex items-center gap-2.5 w-full md:w-auto justify-end flex-wrap">
            {/* Channel filter */}
            <select
              value={channelFilter}
              onChange={(e) => {
                setChannelFilter(e.target.value)
                setPage(1)
              }}
              className="px-3 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none cursor-pointer"
            >
              <option value="all">Semua Kanal</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="telegram">Telegram</option>
              <option value="api_v1">Public API</option>
            </select>

            {/* Fallback filter */}
            <select
              value={fallbackFilter}
              onChange={(e) => {
                setFallbackFilter(e.target.value)
                setPage(1)
              }}
              className="px-3 py-2 text-xs rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-primary)] focus:outline-none cursor-pointer"
            >
              <option value="all">Semua Status</option>
              <option value="success">Terjawab dari SOP</option>
              <option value="fallback">Fallback (Tidak Ditemukan)</option>
            </select>

            <button
              type="submit"
              className="px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white transition-all hover:scale-[1.02] cursor-pointer shadow-md shadow-sky-500/25"
            >
              Cari
            </button>
          </div>
        </form>
      </div>

      {/* ── LOGS TABLE CARD ─────────────────────────────────────── */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xs overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-[var(--border-color)] flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-[var(--text-primary)]">
              Daftar Interaksi Chatbot
            </h2>
            <p className="text-xs text-[var(--text-muted)] mt-0.5">
              Total {pagination.total} riwayat pertanyaan tercatat.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="p-8 space-y-3">
            <div className="skeleton h-8 w-full rounded-lg" />
            <div className="skeleton h-8 w-full rounded-lg" />
            <div className="skeleton h-8 w-full rounded-lg" />
          </div>
        ) : logs.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <p className="text-xs font-semibold text-[var(--text-primary)]">Belum ada riwayat percakapan</p>
            <p className="text-xs text-[var(--text-muted)]">
              Interaksi dari WhatsApp bot, Telegram bot, atau Public API akan otomatis tercatat di sini.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[var(--border-color)] bg-[var(--bg-input)]/40 text-xs font-bold uppercase tracking-wider text-[var(--text-muted)]">
                  <th className="py-3 px-4">Waktu</th>
                  <th className="py-3 px-4">Kanal</th>
                  <th className="py-3 px-4">Pengirim / Klien</th>
                  <th className="py-3 px-4">Pertanyaan</th>
                  <th className="py-3 px-4">Status & Sumber</th>
                  <th className="py-3 px-4">Durasi</th>
                  <th className="py-3 px-4 text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)] text-xs text-[var(--text-primary)]">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-[var(--bg-input)] transition-colors">
                    <td className="py-3.5 px-4 text-xs text-[var(--text-muted)] whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString('id-ID')}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {log.channel === 'whatsapp' ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border border-[var(--border-color)] text-[var(--action-green)] bg-[var(--bg-input)]">
                          WhatsApp
                        </span>
                      ) : log.channel === 'telegram' ? (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border border-[var(--border-color)] text-[var(--brand-primary)] bg-[var(--bg-input)]">
                          Telegram
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs font-semibold border border-[var(--border-color)] text-[var(--text-secondary)] bg-[var(--bg-input)]">
                          Public API
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 font-mono text-xs text-[var(--text-secondary)] whitespace-nowrap">
                      {log.sender_identifier || '-'}
                    </td>
                    <td className="py-3.5 px-4 font-medium max-w-xs truncate" title={log.query}>
                      {log.query}
                    </td>
                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {log.is_fallback ? (
                        <span className="text-xs font-semibold text-amber-600 dark:text-amber-400">
                          Informasi Tidak Ada
                        </span>
                      ) : (
                        <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                          {log.sources_json && log.sources_json.length > 0
                            ? `${log.sources_json.length} Dokumen Terbit`
                            : 'Terjawab'}
                        </span>
                      )}
                    </td>
                    <td className="py-3.5 px-4 text-xs font-mono text-[var(--text-muted)] whitespace-nowrap">
                      {log.response_time_ms ? `${log.response_time_ms} ms` : '-'}
                    </td>
                    <td className="py-3.5 px-4 text-right space-x-1 whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => setSelectedLog(log)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors cursor-pointer"
                      >
                        Detail
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeleteTarget(log)}
                        className="p-1 text-zinc-400 hover:text-rose-500 rounded transition-colors cursor-pointer"
                        title="Hapus Log"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination footer */}
        {pagination.last_page > 1 && (
          <div className="p-4 border-t border-[var(--border-color)] flex items-center justify-between text-xs">
            <span className="text-[var(--text-muted)]">
              Halaman {pagination.current_page} dari {pagination.last_page}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] disabled:opacity-50 cursor-pointer"
              >
                Sebelumnya
              </button>
              <button
                type="button"
                disabled={page >= pagination.last_page}
                onClick={() => setPage((p) => p + 1)}
                className="px-3 py-1.5 rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] disabled:opacity-50 cursor-pointer"
              >
                Berikutnya
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── MODAL DETAIL PERCAKAPAN ─────────────────────────────── */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl max-w-2xl w-full p-5 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-[var(--border-color)] pb-3">
              <div className="space-y-0.5">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  Detail Interaksi Chatbot #{selectedLog.id}
                </h3>
                <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                  <span>Kanal: <strong className="capitalize text-[var(--text-primary)]">{selectedLog.channel}</strong></span>
                  <span>•</span>
                  <span>{new Date(selectedLog.created_at).toLocaleString('id-ID')}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedLog(null)}
                className="p-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] cursor-pointer"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Query */}
            <div className="space-y-1.5">
              <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">
                Pertanyaan Pengguna
              </span>
              <div className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] font-medium">
                {selectedLog.query}
              </div>
            </div>

            {/* Answer */}
            <div className="space-y-1.5">
              <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">
                Jawaban AI (SOP Response)
              </span>
              <div className="p-3.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-primary)] whitespace-pre-wrap leading-relaxed">
                {selectedLog.answer}
              </div>
            </div>

            {/* Cited Sources */}
            {selectedLog.sources_json && selectedLog.sources_json.length > 0 && (
              <div className="space-y-1.5">
                <span className="text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider block">
                  Dokumen SOP yang Dirujuk ({selectedLog.sources_json.length})
                </span>
                <div className="space-y-1.5">
                  {selectedLog.sources_json.map((s, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 rounded bg-[var(--bg-card)] border border-[var(--border-color)] text-xs flex items-center justify-between"
                    >
                      <span className="font-semibold text-[var(--text-primary)]">
                        {s.doc_name || `Dokumen #${s.document_id}`}
                      </span>
                      {s.page && (
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-[var(--bg-input)] text-[var(--brand-primary)] border border-[var(--border-color)]">
                          Halaman {s.page}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Technical Metadata */}
            <div className="pt-2 border-t border-[var(--border-color)] flex items-center justify-between text-xs text-[var(--text-muted)]">
              <div>
                Session ID: <code className="font-mono">{selectedLog.session_id}</code>
              </div>
              <div>
                Durasi: <strong className="font-mono text-[var(--text-primary)]">{selectedLog.response_time_ms ? `${selectedLog.response_time_ms} ms` : '-'}</strong>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── MODAL DELETE SINGLE ─────────────────────────────────── */}
      <ConfirmModal
        isOpen={Boolean(deleteTarget)}
        title="Hapus Log Percakapan?"
        message="Apakah Anda yakin ingin menghapus catatan percakapan ini?"
        confirmText="Ya, Hapus"
        cancelText="Batal"
        danger={true}
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* ── MODAL PURGE ALL ─────────────────────────────────────── */}
      <ConfirmModal
        isOpen={showPurgeModal}
        title="Bersihkan Seluruh Riwayat Percakapan?"
        message="Tindakan ini akan mengosongkan seluruh data audit log percakapan dari database secara permanen."
        confirmText="Ya, Bersihkan Semua"
        cancelText="Batal"
        danger={true}
        onConfirm={handlePurge}
        onCancel={() => setShowPurgeModal(false)}
      />
    </div>
  )
}
