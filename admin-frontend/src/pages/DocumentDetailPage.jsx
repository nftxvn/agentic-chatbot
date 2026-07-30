import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import gsap from 'gsap'
import { documentsApi } from '../api/documents'
import ConfirmModal from '../components/ConfirmModal'

export default function DocumentDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [replaceFile, setReplaceFile] = useState(null)
  const [replacing, setReplacing] = useState(false)
  const [pdfTimestamp, setPdfTimestamp] = useState(Date.now())

  const [chunks, setChunks] = useState([])
  const [showChunks, setShowChunks] = useState(false)
  const [loadingChunks, setLoadingChunks] = useState(false)

  const [showDeleteModal, setShowDeleteModal] = useState(false)
  const [showReplaceModal, setShowReplaceModal] = useState(false)

  const [leftColWidth, setLeftColWidth] = useState(65)
  const isDragging = useRef(false)
  const isMounted = useRef(true)
  const containerRef = useRef(null)
  const timelineRef = useRef(null)
  const fetchTimeout = useRef(null)

  const fetchDocument = async () => {
    try {
      const res = await documentsApi.get(id)
      if (!isMounted.current) return
      setDocument(res.data.document)
      if (res.data.document.status === 'processing' || res.data.document.status === 'pending') {
        if (fetchTimeout.current) clearTimeout(fetchTimeout.current)
        fetchTimeout.current = setTimeout(fetchDocument, 5000)
      }
    } catch (err) {
      if (!isMounted.current) return
      setError(err.response?.data?.message || 'Gagal memuat detail dokumen.')
    } finally {
      if (isMounted.current) setLoading(false)
    }
  }

  const fetchChunks = async () => {
    setLoadingChunks(true)
    try {
      const res = await documentsApi.getChunks(id)
      if (!isMounted.current) return
      setChunks(res.chunks || res.data?.chunks || [])
    } catch (err) {
      if (!isMounted.current) return
      console.error('Gagal memuat chunks', err)
      setChunks([])
    } finally {
      if (isMounted.current) setLoadingChunks(false)
    }
  }

  useEffect(() => {
    isMounted.current = true
    fetchDocument()
    return () => {
      isMounted.current = false
      if (fetchTimeout.current) clearTimeout(fetchTimeout.current)
    }
  }, [id])

  useEffect(() => {
    if (document?.logs?.length && timelineRef.current) {
      const items = timelineRef.current.querySelectorAll('.gsap-timeline-item')
      const lines = timelineRef.current.querySelectorAll('.gsap-timeline-line')
      const icons = timelineRef.current.querySelectorAll('.gsap-timeline-icon')

      gsap.fromTo(items,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.4, stagger: 0.1, ease: 'power2.out' }
      )
      if (lines.length) {
        gsap.fromTo(lines,
          { height: '0%' },
          { height: '100%', duration: 0.5, stagger: 0.1, delay: 0.2, ease: 'power1.inOut' }
        )
      }
      if (icons.length) {
        gsap.fromTo(icons,
          { scale: 0 },
          { scale: 1, duration: 0.3, stagger: 0.1, ease: 'back.out(1.5)' }
        )
      }
    }
  }, [document?.logs])

  const startDrag = (e) => {
    e.preventDefault()
    isDragging.current = true
    window.document.body.style.cursor = 'col-resize'
    window.document.body.style.userSelect = 'none'
    if (containerRef.current) containerRef.current.style.pointerEvents = 'none'
  }

  const onDrag = (e) => {
    if (!isDragging.current || !containerRef.current) return
    const containerRect = containerRef.current.getBoundingClientRect()
    const newWidth = ((e.clientX - containerRect.left) / containerRect.width) * 100
    if (newWidth >= 20 && newWidth <= 80) setLeftColWidth(newWidth)
  }

  const stopDrag = () => {
    if (isDragging.current) {
      isDragging.current = false
      window.document.body.style.cursor = 'default'
      window.document.body.style.userSelect = 'auto'
      if (containerRef.current) containerRef.current.style.pointerEvents = 'auto'
    }
  }

  useEffect(() => {
    window.addEventListener('mousemove', onDrag)
    window.addEventListener('mouseup', stopDrag)
    return () => {
      window.removeEventListener('mousemove', onDrag)
      window.removeEventListener('mouseup', stopDrag)
    }
  }, [])

  const handleReplace = (e) => {
    e.preventDefault()
    if (!replaceFile) return
    setShowReplaceModal(true)
  }

  const confirmReplace = async () => {
    setShowReplaceModal(false)
    setReplacing(true)
    try {
      await documentsApi.replace(id, replaceFile)
      setReplaceFile(null)
      setPdfTimestamp(Date.now())
      fetchDocument()
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal mengganti file.')
    } finally {
      setReplacing(false)
    }
  }

  const handleDelete = () => setShowDeleteModal(true)

  const confirmDelete = async () => {
    try {
      await documentsApi.destroy(id)
      navigate('/dashboard')
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal menghapus dokumen.')
    }
  }

  const handlePause = async () => {
    if (!window.confirm('Yakin ingin menunda pemrosesan AI?')) return
    try {
      await documentsApi.pause(id)
      fetchDocument()
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal menunda pemrosesan')
    }
  }

  const handleResume = async () => {
    try {
      await documentsApi.resume(id)
      fetchDocument()
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal melanjutkan pemrosesan')
    }
  }

  const handleCancel = async () => {
    if (!window.confirm('Yakin ingin membatalkan pemrosesan ini secara permanen?')) return
    try {
      await documentsApi.cancel(id)
      fetchDocument()
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal membatalkan pemrosesan')
    }
  }

  const formatDate = (isoString) => {
    if (!isoString) return '-'
    return new Date(isoString).toLocaleDateString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    })
  }

  const getLogColor = (action) => {
    switch (action) {
      case 'uploaded':   return '#3b82f6'
      case 'processing': return '#f59e0b'
      case 'completed':  return '#10b981'
      case 'failed':     return '#ef4444'
      case 'replaced':   return '#f97316'
      default:           return 'var(--text-muted)'
    }
  }

  const getLogIcon = (action) => {
    switch (action) {
      case 'uploaded':   return <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
      case 'processing': return <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      case 'completed':  return <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      case 'failed':     return <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      case 'replaced':   return <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      default:           return <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    }
  }

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed': return { bg: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-500' }
      case 'processing': return { bg: 'bg-amber-500/10 border-amber-500/20 text-amber-500' }
      case 'failed': return { bg: 'bg-red-500/10 border-red-500/20 text-red-500' }
      default: return { bg: 'bg-[var(--bg-input)] border-[var(--border-color)] text-[var(--text-muted)]' }
    }
  }

  if (loading) {
    return (
      <div className="p-4 sm:p-6 lg:p-8 max-w-[1600px] mx-auto space-y-6">
        {/* Top Header Skeleton */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm">
          <div className="flex items-center gap-4">
            <div className="skeleton w-10 h-10 rounded-xl" />
            <div className="space-y-2">
              <div className="skeleton h-6 w-64 rounded-lg" />
              <div className="skeleton h-4 w-36 rounded-md" />
            </div>
          </div>
          <div className="skeleton h-8 w-32 rounded-full" />
        </div>

        {/* Two-Column Grid Skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 border border-[var(--border-color)] rounded-2xl p-6 bg-[var(--bg-card)] shadow-sm">
          {/* Left Column Skeleton */}
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div className="skeleton h-5 w-32 rounded-md" />
              <div className="skeleton h-4 w-28 rounded-md" />
            </div>
            <div className="skeleton h-[480px] w-full rounded-xl" />
            <div className="flex justify-between items-center pt-2">
              <div className="skeleton h-5 w-48 rounded-md" />
              <div className="skeleton h-8 w-40 rounded-lg" />
            </div>
            <div className="space-y-3">
              <div className="skeleton h-24 w-full rounded-xl" />
              <div className="skeleton h-24 w-full rounded-xl" />
            </div>
          </div>

          {/* Right Column Skeleton */}
          <div className="space-y-6 divide-y divide-[var(--border-color)]">
            <div className="space-y-4">
              <div className="skeleton h-5 w-44 rounded-md" />
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="flex justify-between items-center py-1">
                  <div className="skeleton h-4 w-28 rounded-md" />
                  <div className="skeleton h-4 w-36 rounded-md" />
                </div>
              ))}
            </div>
            <div className="pt-6 space-y-3">
              <div className="flex justify-between">
                <div className="skeleton h-4 w-36 rounded-md" />
                <div className="skeleton h-4 w-20 rounded-md" />
              </div>
              <div className="skeleton h-3 w-full rounded-full" />
            </div>
            <div className="pt-6 space-y-3">
              <div className="skeleton h-5 w-32 rounded-md" />
              <div className="skeleton h-10 w-full rounded-xl" />
              <div className="skeleton h-10 w-full rounded-xl" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className="p-4 sm:p-6 lg:p-8 max-w-xl mx-auto space-y-4">
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-500 rounded-2xl text-sm font-medium">
          {error || 'Dokumen tidak ditemukan'}
        </div>
        <Link to="/dashboard" className="inline-flex items-center gap-2 text-sm font-bold text-sky-500 hover:text-sky-400">
          ← Kembali ke Dashboard
        </Link>
      </div>
    )
  }

  const statusBadge = getStatusBadge(document.status)

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-[1600px] mx-auto space-y-6">
      {/* Sticky Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm">
        <div className="flex items-center gap-4">
          <Link
            to="/dashboard"
            title="Kembali ke Dashboard"
            className="flex items-center justify-center w-10 h-10 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:scale-105 transition-all"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
            </svg>
          </Link>
          <div>
            <h1 className="text-xl font-black text-[var(--text-primary)] tracking-tight">{document.title}</h1>
            <p className="text-xs text-[var(--text-muted)] font-mono mt-0.5">ID: {document.id}</p>
          </div>
        </div>
        <div>
          <span className={`px-4 py-1.5 rounded-full text-xs font-bold border inline-flex items-center gap-1.5 ${statusBadge.bg}`}>
            {document.status === 'processing' && (
              <svg className="spin w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            )}
            {document.status_label}
          </span>
        </div>
      </div>

      {/* Two-Column Grid with Draggable Divider */}
      <div
        ref={containerRef}
        className="grid border border-[var(--border-color)] rounded-2xl overflow-hidden bg-[var(--bg-card)] shadow-sm"
        style={{
          gridTemplateColumns: `calc(${leftColWidth}% - 4px) 8px calc(${100 - leftColWidth}% - 4px)`,
          alignItems: 'stretch'
        }}
      >
        {/* LEFT COLUMN */}
        <div className="flex flex-col border-r border-[var(--border-color)] divide-y divide-[var(--border-color)] min-h-[700px]">

          {/* PDF Viewer Section */}
          <div className="p-6 flex flex-col h-[520px]">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">Pratinjau PDF</h2>
              <a
                href={`${documentsApi.pdfUrl(id)}?t=${pdfTimestamp}`}
                target="_blank"
                rel="noopener"
                className="text-xs font-bold text-sky-500 hover:text-sky-400 inline-flex items-center gap-1"
              >
                Buka Tab Baru
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                </svg>
              </a>
            </div>
            <div className="flex-1 rounded-xl overflow-hidden border border-[var(--border-color)] bg-slate-950">
              <iframe
                src={`${documentsApi.pdfUrl(id)}?t=${pdfTimestamp}`}
                className="w-full h-full border-none block"
                title={document.title}
              />
            </div>
          </div>

          {/* ChromaDB Chunks */}
          <div className="p-6">
            <div className="flex justify-between items-center">
              <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">ChromaDB Vector Chunks</h2>
              <button
                onClick={() => {
                  setShowChunks(!showChunks)
                  if (!showChunks && chunks.length === 0) fetchChunks()
                }}
                className="px-3 py-1.5 rounded-lg text-xs font-bold bg-sky-500/10 text-sky-500 hover:bg-sky-500 hover:text-white transition-colors"
              >
                {showChunks ? 'Sembunyikan Chunks' : 'Tampilkan Teks OCR Chunks'}
              </button>
            </div>

            {showChunks && (
              <div className="mt-4 max-h-96 overflow-y-auto space-y-3 pr-2">
                {loadingChunks ? (
                  <p className="text-xs text-[var(--text-muted)] italic text-center py-4">Memuat data chunks OCR...</p>
                ) : chunks.length === 0 ? (
                  <p className="text-xs text-[var(--text-muted)] italic text-center py-4">Tidak ada data chunks.</p>
                ) : (
                  chunks.map(c => (
                    <div key={c.id} className="p-4 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs space-y-2">
                      <div className="flex justify-between items-center text-[var(--text-muted)] font-mono text-[11px]">
                        <span>ID: {c.id}</span>
                        <span className="px-2 py-0.5 rounded-full bg-sky-500 text-white font-bold">
                          Halaman {c.metadata.page_number}
                        </span>
                      </div>
                      <p className="whitespace-pre-wrap break-words text-[var(--text-primary)] leading-relaxed font-sans">
                        {c.text}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Timeline Logs */}
          <div className="p-6 flex-1 flex flex-col">
            <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-5">Riwayat Pemrosesan Dokumen</h2>
            <div className="space-y-6 overflow-y-auto flex-1 pr-2" ref={timelineRef}>
              {document.logs && document.logs.length > 0 ? (
                document.logs.map((log, index) => (
                  <div key={log.id} className="flex gap-4 relative gsap-timeline-item">
                    <div
                      className="w-7 h-7 rounded-full flex items-center justify-center shrink-0 z-10 gsap-timeline-icon text-white shadow-sm"
                      style={{ background: getLogColor(log.action) }}
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        {getLogIcon(log.action)}
                      </svg>
                    </div>
                    {index < document.logs.length - 1 && (
                      <div className="absolute left-3.5 top-7 w-0.5 bottom-0 bg-[var(--border-color)] gsap-timeline-line" />
                    )}
                    <div className="flex-1 pb-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[var(--text-primary)]">{log.action_label || log.action}</span>
                        <span className="text-[10px] text-[var(--text-muted)]">{formatDate(log.created_at)}</span>
                      </div>
                      {log.detail && (
                        <p className="text-xs text-[var(--text-secondary)] mt-1 font-mono bg-[var(--bg-input)] p-2 rounded-lg border border-[var(--border-color)]">
                          {log.detail}
                        </p>
                      )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-[var(--text-muted)] italic text-center py-4">Belum ada log aktivitas.</p>
              )}
            </div>
          </div>
        </div>

        {/* RESIZER BAR */}
        <div
          className="cursor-col-resize flex justify-center bg-transparent w-full h-full hover:bg-sky-500/20 transition-colors select-none"
          onMouseDown={startDrag}
        >
          <div className="w-0.5 h-full bg-[var(--border-color)]" />
        </div>

        {/* RIGHT COLUMN */}
        <div className="flex flex-col divide-y divide-[var(--border-color)]">

          {/* Info Details */}
          <div className="p-6 space-y-4">
            <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider mb-2">Informasi Dokumen</h2>

            {[
              { label: 'File Asli', value: document.original_filename },
              { label: 'Tipe PDF', value: document.pdf_type_label },
              { label: 'Halaman / Chunks', value: `${document.total_pages || '-'} / ${document.total_chunks || '-'}` },
              { label: 'Diunggah Oleh', value: document.uploaded_by || '-' },
              { label: 'Waktu Unggah', value: formatDate(document.created_at) },
              { label: 'Selesai Diproses', value: formatDate(document.processed_at) },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between items-center py-1.5 text-xs">
                <span className="text-[var(--text-muted)] font-semibold">{label}</span>
                <span className="text-[var(--text-primary)] font-bold text-right truncate max-w-[60%]">{value}</span>
              </div>
            ))}

            {document.error_message && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-xl text-xs leading-relaxed">
                <strong>Error:</strong> {document.error_message}
              </div>
            )}

            {/* AI Extraction Progress */}
            {(document.status === 'processing' || document.status === 'paused' || (document.status === 'completed' && document.processed_pages > 0)) && document.total_pages > 0 && (
              <div className="p-4 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] space-y-3 mt-2">
                <div className="flex justify-between text-xs font-bold">
                  <span>Progres AI Extraksi</span>
                  <span>{document.processed_pages || 0} / {document.total_pages} ({(((document.processed_pages || 0) / document.total_pages) * 100).toFixed(0)}%)</span>
                </div>
                <div className="h-2 rounded-full bg-[var(--border-color)] overflow-hidden">
                  <div
                    className="h-full transition-all duration-500 rounded-full"
                    style={{
                      width: `${((document.processed_pages || 0) / document.total_pages * 100)}%`,
                      background: document.status === 'paused' ? '#f97316' : document.status === 'completed' ? '#10b981' : '#0ea5e9',
                    }}
                  />
                </div>

                {(document.status === 'processing' || document.status === 'paused') && (
                  <div className="flex gap-2 pt-2">
                    {document.status === 'processing' ? (
                      <button
                        onClick={handlePause}
                        className="flex-1 py-2 text-xs font-bold bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors"
                      >
                        Tunda / Pause
                      </button>
                    ) : (
                      <button
                        onClick={handleResume}
                        className="flex-1 py-2 text-xs font-bold bg-sky-600 text-white rounded-xl hover:bg-sky-500 transition-colors"
                      >
                        Lanjutkan
                      </button>
                    )}
                    <button
                      onClick={handleCancel}
                      className="flex-1 py-2 text-xs font-bold bg-red-500/10 text-red-500 border border-red-500/20 rounded-xl hover:bg-red-500 hover:text-white transition-all"
                    >
                      Batalkan
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Replace PDF File */}
          <div className="p-6 space-y-4">
            <h2 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider">Ganti File PDF</h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Mengganti file akan menghapus indexing lama dan mengulang proses OCR & RAG.
            </p>
            <form onSubmit={handleReplace} className="space-y-3">
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setReplaceFile(e.target.files[0])}
                disabled={replacing || document.status === 'processing'}
                className="w-full text-xs text-[var(--text-secondary)] file:mr-4 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-sky-500/10 file:text-sky-500"
              />
              <button
                type="submit"
                className="w-full py-2.5 rounded-xl bg-[var(--bg-input)] border border-[var(--border-color)] text-xs font-bold text-[var(--text-primary)] hover:bg-sky-600 hover:text-white hover:border-sky-600 transition-all disabled:opacity-50"
                disabled={!replaceFile || replacing || document.status === 'processing'}
              >
                {replacing ? 'Mengunggah...' : 'Ganti & Proses Ulang'}
              </button>
            </form>
          </div>

          {/* Danger Zone */}
          <div className="p-6 bg-red-500/5 space-y-4">
            <h2 className="text-sm font-bold text-red-500 uppercase tracking-wider">Zona Berbahaya</h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Menghapus dokumen bersifat permanen dan akan menghapus semua vektor ChromaDB terkait.
            </p>
            <button
              onClick={handleDelete}
              className="w-full py-2.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 hover:bg-red-600 hover:text-white font-bold text-xs transition-all"
            >
              Hapus Dokumen Permanen
            </button>
          </div>
        </div>
      </div>

      <ConfirmModal
        isOpen={showDeleteModal}
        title="Hapus Dokumen Permanen"
        message="PERINGATAN: Dokumen ini akan dihapus permanen. AI tidak akan bisa lagi mencari jawaban dari dokumen ini. Lanjutkan?"
        onConfirm={confirmDelete}
        onCancel={() => setShowDeleteModal(false)}
        confirmText="Hapus"
      />

      <ConfirmModal
        isOpen={showReplaceModal}
        title="Konfirmasi Ganti File"
        message="Yakin ingin mengganti file ini? Proses indexing akan diulang dari awal."
        onConfirm={confirmReplace}
        onCancel={() => setShowReplaceModal(false)}
        confirmText="Ganti & Proses Ulang"
      />
    </div>
  )
}
