import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { Link } from 'react-router-dom'
import gsap from 'gsap'
import { documentsApi } from '../api/documents'
import { categoriesApi } from '../api/categories'
import ConfirmModal from '../components/ConfirmModal'
import { addAppNotification } from '../utils/notifications'

export default function DashboardPage() {
  const [data, setData] = useState({ documents: [], stats: {}, meta: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [showModal, setShowModal] = useState(false)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadCategoryId, setUploadCategoryId] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStage, setUploadStage] = useState('idle') // idle | uploading | processing | done
  const [processingSeconds, setProcessingSeconds] = useState(5)

  const [deleteTarget, setDeleteTarget] = useState(null)
  const [categories, setCategories] = useState([])

  const fetchTimeout = useRef(null)
  const statsGridRef = useRef(null)
  const modalRef = useRef(null)
  const headerRef = useRef(null)

  const fetchData = async (page = 1) => {
    const startTime = Date.now()
    try {
      const res = await documentsApi.list(page)
      if (res && res.data) {
        setData({
          documents: res.data.documents || [],
          stats: res.data.stats || {},
          meta: res.data.meta || {},
          has_processing: !!res.data.has_processing
        })
      }
      if (res?.data?.has_processing) {
        fetchTimeout.current = setTimeout(() => fetchData(page), 10000)
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Gagal memuat data dokumen.')
    } finally {
      const elapsed = Date.now() - startTime
      setTimeout(() => setLoading(false), Math.max(0, 350 - elapsed))
    }
  }

  const fetchCategories = async () => {
    try {
      const res = await categoriesApi.list()
      setCategories(res.data)
      if (res.data && res.data.length > 0) {
        setUploadCategoryId(res.data[0].id)
      }
    } catch (err) {
      console.error('Failed to load categories', err)
    }
  }

  useEffect(() => {
    fetchData()
    fetchCategories()
    return () => clearTimeout(fetchTimeout.current)
  }, [])



  useLayoutEffect(() => {
    if (headerRef.current) {
      gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -20 },
        { opacity: 1, x: 0, duration: 0.6, stagger: 0.1, ease: 'power2.out', clearProps: 'all' }
      )
    }
    if (!loading && statsGridRef.current) {
      const cards = statsGridRef.current.children
      gsap.fromTo(
        cards,
        { opacity: 0, scale: 0.98 },
        { opacity: 1, scale: 1, duration: 0.4, stagger: 0.05, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  useEffect(() => {
    if (showModal && modalRef.current) {
      gsap.fromTo(
        modalRef.current,
        { opacity: 0, scale: 0.9, y: 30 },
        { opacity: 1, scale: 1, y: 0, duration: 0.4, ease: 'power2.inOut' }
      )
    }
  }, [showModal])

  const handleUploadSubmit = async (e) => {
    e.preventDefault()
    if (!uploadFile || !uploadTitle || !uploadCategoryId) return

    setUploading(true)
    setUploadProgress(0)
    setUploadStage('uploading')
    setProcessingSeconds(5)

    try {
      await documentsApi.upload(uploadTitle, uploadFile, uploadCategoryId, (progressEvent) => {
        if (progressEvent.lengthComputable ?? progressEvent.total > 0) {
          const percent = Math.round((progressEvent.loaded / progressEvent.total) * 100)
          setUploadProgress(percent)
        }
      })

      // Step 2: Smooth 5-second countdown & progress fill for certainty
      setUploadStage('processing')
      for (let s = 5; s >= 1; s--) {
        setProcessingSeconds(s)
        await new Promise(r => setTimeout(r, 1000))
      }

      setUploadStage('done')
      addAppNotification({
        title: 'Dokumen Baru',
        message: `Anda baru saja mengunggah dokumen "${uploadTitle}"`,
        type: 'info',
      })
      await new Promise(r => setTimeout(r, 800))
      setShowModal(false)
      setUploadTitle('')
      setUploadFile(null)
      setUploadProgress(0)
      setUploadStage('idle')
      fetchData()
    } catch (err) {
      alert(err.response?.data?.message || err.message || 'Gagal mengunggah dokumen.')
      setUploadStage('idle')
      setUploadProgress(0)
    } finally {
      setUploading(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    const docTitle = deleteTarget.title || deleteTarget.original_filename || 'Dokumen'
    try {
      await documentsApi.destroy(deleteTarget.id)
      addAppNotification({
        title: 'Dokumen Dihapus',
        message: `Anda baru saja menghapus dokumen "${docTitle}"`,
        type: 'warning',
      })
      fetchData(data.meta?.current_page || 1)
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal menghapus dokumen.')
    } finally {
      setDeleteTarget(null)
    }
  }

  const handleCancelProcess = async (docId, title) => {
    if (!window.confirm(`Yakin ingin membatalkan pemrosesan dokumen "${title}"?`)) return
    try {
      await documentsApi.cancel(docId)
      addAppNotification({
        title: 'Proses Dibatalkan',
        message: `Pemrosesan dokumen "${title}" telah dibatalkan.`,
        type: 'warning',
      })
      fetchData(data.meta?.current_page || 1)
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal membatalkan pemrosesan.')
    }
  }

  const handleResumeProcess = async (docId, title) => {
    try {
      await documentsApi.resume(docId)
      addAppNotification({
        title: 'Proses Dilanjutkan (Cicil)',
        message: `Pemrosesan AI dokumen "${title}" dilanjutkan kembali.`,
        type: 'info',
      })
      fetchData(data.meta?.current_page || 1)
    } catch (err) {
      const msg = err.response?.data?.message || err.message || 'Server AI (Python Uvicorn / Celery) sedang tidak berjalan.'
      addAppNotification({
        title: '⚠️ Server AI Offline',
        message: msg,
        type: 'warning',
      })
      alert(`⚠️ ${msg}`)
      fetchData(data.meta?.current_page || 1)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return '-'
    const localStr = dateString.replace('Z', '').replace('+00:00', '')
    return new Date(localStr).toLocaleDateString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    })
  }

  const getBadgeClass = (status) => {
    switch (status) {
      case 'completed': return 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20'
      case 'processing': return 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
      case 'paused': return 'bg-orange-500/10 text-orange-500 border border-orange-500/20'
      case 'failed':     return 'bg-red-500/10 text-red-500 border border-red-500/20'
      default:           return 'bg-[var(--bg-input)] text-[var(--text-muted)] border border-[var(--border-color)]'
    }
  }

  return (
    <div className="p-4 sm:p-5 max-w-[1600px] mx-auto space-y-4 sm:space-y-5">
      {/* Top Banner & Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 p-4 sm:p-5 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-sm">
        <div ref={headerRef}>
          <div className="flex items-center gap-2">
            <h1 className="text-xl sm:text-2xl font-black text-[var(--text-primary)] tracking-tight">MANAJEMEN DOKUMEN RAG</h1>
          </div>
          <p className="text-xs sm:text-sm text-[var(--text-secondary)] mt-0.5">
            Kelola basis pengetahuan (knowledge base) dokumen PDF untuk AI Assistant.
          </p>
        </div>
        <button
          className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-xs sm:text-sm flex items-center justify-center gap-2 shadow-md shadow-sky-500/25 transition-all duration-200 hover:scale-[1.02] shrink-0"
          onClick={() => setShowModal(true)}
        >
          <svg className="w-4.5 h-4.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Unggah Dokumen Baru
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 text-red-500 p-3.5 rounded-xl border border-red-500/20 text-sm font-medium">
          {error}
        </div>
      )}

      {/* Stats Cards */}
      <div
        className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3.5 sm:gap-4"
        ref={statsGridRef}
      >
        {[
          {
            icon: <svg className="w-5.5 h-5.5 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
            bg: 'bg-sky-500/10 border-sky-500/20',
            label: 'Total Dokumen',
            value: data.stats?.total || 0,
          },
          {
            icon: <svg className="w-5.5 h-5.5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>,
            bg: 'bg-emerald-500/10 border-emerald-500/20',
            label: 'Selesai Ter-index',
            value: data.stats?.completed || 0,
          },
          {
            icon: <svg className="w-5.5 h-5.5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>,
            bg: 'bg-amber-500/10 border-amber-500/20',
            label: 'Dalam Pemrosesan',
            value: data.stats?.processing || 0,
          },
          {
            icon: <svg className="w-5.5 h-5.5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>,
            bg: 'bg-red-500/10 border-red-500/20',
            label: 'Gagal Ter-index',
            value: data.stats?.failed || 0,
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] p-4 sm:p-5 rounded-xl flex items-center gap-3.5 transition-all duration-200 hover:shadow-md hover:-translate-y-0.5"
          >
            <div className={`w-11 h-11 rounded-xl border ${stat.bg} flex items-center justify-center shrink-0`}>
              {stat.icon}
            </div>
            <div>
              <p className="text-[11px] text-[var(--text-muted)] font-semibold uppercase tracking-wider">{stat.label}</p>
              <h3 className="text-xl font-black text-[var(--text-primary)] mt-0.5">
                {loading ? <div className="skeleton h-6 w-14" /> : stat.value}
              </h3>
            </div>
          </div>
        ))}
      </div>

      {/* Table Section */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black/5 dark:bg-white/5 border-b border-[var(--border-color)]">
                {['Judul Dokumen', 'File Asli', 'Status', 'Kategori AI', 'Chunks', 'Waktu Unggah', 'Aksi'].map((h, i) => (
                  <th
                    key={h}
                    className={`px-4.5 py-3 text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider ${i === 6 ? 'text-right' : ''}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)] text-xs sm:text-sm">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-4.5 py-3"><div className="skeleton h-5 w-4/5" /></td>
                    <td className="px-4.5 py-3"><div className="skeleton h-5 w-3/5" /></td>
                    <td className="px-4.5 py-3"><div className="skeleton h-6 w-20 rounded-full" /></td>
                    <td className="px-4.5 py-3"><div className="skeleton h-5 w-16" /></td>
                    <td className="px-4.5 py-3"><div className="skeleton h-5 w-10" /></td>
                    <td className="px-4.5 py-3"><div className="skeleton h-5 w-24" /></td>
                    <td className="px-4.5 py-3 text-right"><div className="skeleton h-8 w-24 ml-auto" /></td>
                  </tr>
                ))
              ) : !data?.documents || data.documents.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-12 text-[var(--text-muted)] font-medium">
                    Belum ada dokumen yang diunggah. Klik tombol diatas untuk mengunggah dokumen baru.
                  </td>
                </tr>
              ) : (
                (data.documents || []).map((doc) => (
                  <tr key={doc.id} className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4 font-bold text-[var(--text-primary)]">{doc.title}</td>
                    <td className="px-4.5 py-3 text-[var(--text-secondary)] font-mono text-xs">{doc.original_filename}</td>
                    <td className="px-4.5 py-3">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${getBadgeClass(doc.status)}`}>
                        {doc.status === 'processing' && (
                          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                        )}
                        {doc.status_label}
                      </span>
                    </td>
                    <td className="px-4.5 py-3">
                      <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-[var(--bg-input)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                        {doc.category_name || doc.category?.name || 'Umum'}
                      </span>
                    </td>
                    <td className="px-4.5 py-3 font-semibold text-[var(--text-primary)]">{doc.total_chunks || '-'}</td>
                    <td className="px-4.5 py-3 text-xs text-[var(--text-muted)] font-medium">{formatDate(doc.created_at)}</td>
                    <td className="px-4.5 py-3 text-right">
                      <div className="flex gap-1.5 justify-end flex-wrap">
                        {doc.status === 'processing' || doc.status === 'pending' ? (
                          <button
                            onClick={() => handleCancelProcess(doc.id, doc.title)}
                            className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-500/10 text-amber-500 hover:bg-amber-500 hover:text-white transition-all duration-200 inline-flex items-center gap-1.5"
                            title="Hentikan (Stop) proses AI dokumen ini"
                          >
                            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                              <rect x="6" y="6" width="12" height="12" rx="1.5" />
                            </svg>
                            Stop
                          </button>
                        ) : (doc.status === 'failed' || doc.status === 'paused') ? (
                          <button
                            onClick={() => handleResumeProcess(doc.id, doc.title)}
                            className="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500 hover:text-white transition-all duration-200 inline-flex items-center gap-1.5"
                            title="Lanjutkan (Resume) pemrosesan AI dokumen ini"
                          >
                            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                              <path d="M8 5v14l11-7z" />
                            </svg>
                            Resume
                          </button>
                        ) : null}
                        <Link
                          to={`/documents/${doc.id}`}
                          className="px-3 py-1.5 rounded-lg text-xs font-bold bg-sky-500/10 text-sky-500 hover:bg-sky-500 hover:text-white transition-all duration-200"
                        >
                          Detail
                        </Link>
                        <button
                          onClick={() => setDeleteTarget(doc)}
                          className="px-3 py-1.5 rounded-lg text-xs font-bold bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white transition-all duration-200"
                        >
                          Hapus
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {!loading && data.meta?.last_page > 1 && (
          <div className="flex justify-between items-center px-4.5 py-3 border-t border-[var(--border-color)] bg-black/5 dark:bg-white/5">
            <button
              disabled={data.meta.current_page === 1}
              onClick={() => fetchData(data.meta.current_page - 1)}
              className="px-4 py-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-xs font-bold text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Sebelumnya
            </button>
            <span className="text-xs font-bold text-[var(--text-muted)]">
              Halaman {data.meta.current_page} dari {data.meta.last_page}
            </span>
            <button
              disabled={data.meta.current_page === data.meta.last_page}
              onClick={() => fetchData(data.meta.current_page + 1)}
              className="px-4 py-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-xs font-bold text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Berikutnya →
            </button>
          </div>
        )}
      </div>

      {/* Upload Modal */}
      {showModal && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget && !uploading) setShowModal(false) }}
        >
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden" ref={modalRef}>
            <div className="px-6 py-5 border-b border-[var(--border-color)] flex justify-between items-center bg-black/5 dark:bg-white/5">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-sky-500/10 text-sky-500 flex items-center justify-center">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <h3 className="text-lg font-bold text-[var(--text-primary)]">Unggah Dokumen Baru</h3>
              </div>
              <button
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed disabled:pointer-events-none"
                onClick={() => !uploading && setShowModal(false)}
                disabled={uploading}
                title={uploading ? 'Sedang memproses dokumen...' : 'Tutup'}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleUploadSubmit}>
              <div className="p-6 space-y-5">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Judul Dokumen</label>
                  <input
                    type="text"
                    className="w-full"
                    value={uploadTitle}
                    onChange={e => setUploadTitle(e.target.value)}
                    placeholder="Contoh: SK Pelayanan Publik 2024"
                    required
                    disabled={uploading}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Kategori AI Prompt</label>
                  <select
                    className="w-full"
                    value={uploadCategoryId}
                    onChange={e => setUploadCategoryId(e.target.value)}
                    required
                    disabled={uploading || categories.length === 0}
                  >
                    {categories.length === 0 ? (
                      <option value="" disabled>-- Kategori kosong / Tidak ada --</option>
                    ) : (
                      categories.map(cat => (
                        <option key={cat.id} value={cat.id}>{cat.name}</option>
                      ))
                    )}
                  </select>
                  {categories.length === 0 && (
                    <p className="text-xs text-amber-500 font-semibold mt-1.5 flex items-center gap-1">
                      ⚠️ Kategori AI masih kosong. Silakan buat kategori baru terlebih dahulu di menu Kategori AI.
                    </p>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">File PDF Dokumen</label>
                  <input
                    type="file"
                    accept="application/pdf"
                    onChange={e => setUploadFile(e.target.files[0])}
                    required
                    disabled={uploading}
                    className="w-full text-xs text-[var(--text-secondary)] file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-sky-500/10 file:text-sky-500 hover:file:bg-sky-500/20"
                  />
                  <p className="text-xs text-[var(--text-muted)] mt-1.5">Maksimal ukuran file: 50MB (Format PDF)</p>
                </div>
              </div>

              {/* Progress & Status Section */}
              {uploading && (
                <div className="px-6 pb-5">
                  <div className="rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] p-4 space-y-3">
                    
                    {/* Stage 1: Uploading (0% - 99%) */}
                    {uploadStage === 'uploading' && (
                      <div className="space-y-2.5">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="w-7 h-7 rounded-lg bg-sky-500/10 flex items-center justify-center shrink-0">
                              <svg className="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                              </svg>
                            </div>
                            <div className="min-w-0">
                              <p className="text-xs font-bold text-sky-500 truncate">Mengunggah File PDF ({uploadProgress}%)</p>
                              <p className="text-[11px] text-[var(--text-muted)] truncate">
                                {uploadFile?.name} {uploadFile?.size ? `(${Math.round(uploadFile.size / 1024)} KB)` : ''}
                              </p>
                            </div>
                          </div>
                          <span className="text-sm font-black text-sky-500 tabular-nums shrink-0">{uploadProgress}%</span>
                        </div>

                        <div className="w-full bg-black/10 dark:bg-white/10 rounded-full h-2 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-sky-400 to-blue-500 transition-all duration-200 ease-out"
                            style={{ width: `${uploadProgress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Stage 2: Processing (100% Uploaded, 5-Second Countdown) */}
                    {uploadStage === 'processing' && (
                      <div className="space-y-3">
                        {/* Checkpoint 1: Upload Complete */}
                        <div className="flex items-center gap-2 text-xs font-bold text-emerald-500">
                          <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                          </svg>
                          <span>File PDF Selesai Terunggah (100%)</span>
                        </div>

                        {/* Checkpoint 2: 5-Second Countdown Status */}
                        <div className="flex items-center justify-between gap-3 pt-1 border-t border-[var(--border-color)]">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className="w-7 h-7 rounded-lg bg-amber-500/10 flex items-center justify-center shrink-0">
                              <svg className="w-4 h-4 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                              </svg>
                            </div>
                            <div className="min-w-0">
                              <p className="text-xs font-bold text-amber-500">Menyimpan &amp; Mengonfirmasi Dokumen...</p>
                              <p className="text-[11px] text-[var(--text-muted)] mt-0.5">
                                Selesai dalam {processingSeconds} detik...
                              </p>
                            </div>
                          </div>
                          <span className="text-sm font-black text-amber-500 tabular-nums shrink-0">{processingSeconds}s</span>
                        </div>

                        {/* Smooth 5-Second Progress Bar */}
                        <div className="w-full bg-black/10 dark:bg-white/10 rounded-full h-2 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-gradient-to-r from-amber-400 to-amber-500 transition-all duration-1000 linear"
                            style={{ width: `${((6 - processingSeconds) / 5) * 100}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* Stage 3: Done */}
                    {uploadStage === 'done' && (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2.5 text-xs font-bold text-emerald-500">
                          <div className="w-7 h-7 rounded-lg bg-emerald-500/10 flex items-center justify-center shrink-0">
                            <svg className="w-4 h-4 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                          <div>
                            <p className="font-bold">Dokumen Berhasil Disimpan!</p>
                            <p className="text-[11px] text-[var(--text-muted)] font-normal">Menutup modal &amp; memperbarui daftar...</p>
                          </div>
                        </div>
                        <div className="w-full bg-emerald-500 rounded-full h-1.5" />
                      </div>
                    )}

                  </div>
                </div>
              )}



              <div className="px-6 py-4 border-t border-[var(--border-color)] bg-black/5 dark:bg-white/5 flex justify-end gap-3">
                <button
                  type="button"
                  className="px-4 py-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors"
                  onClick={() => setShowModal(false)}
                  disabled={uploading}
                >
                  Batal
                </button>
                <button
                  type="submit"
                  className={`px-5 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-sm shadow-lg shadow-sky-500/25 transition-all relative overflow-hidden flex items-center justify-center gap-2 ${
                    uploading ? 'cursor-wait opacity-75' : 'hover:scale-[1.02] disabled:opacity-50'
                  }`}
                  disabled={uploading || !uploadTitle || !uploadFile}
                >
                  {uploading ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full shrink-0" />
                      <span>
                        {uploadStage === 'uploading' ? `${uploadProgress}%` : 'Memproses...'}
                      </span>
                    </>
                  ) : (
                    'Unggah Dokumen'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={!!deleteTarget}
        title="Hapus Dokumen"
        message={`Yakin ingin menghapus dokumen "${deleteTarget?.title}"?`}
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
        confirmText="Hapus"
      />
    </div>
  )
}
