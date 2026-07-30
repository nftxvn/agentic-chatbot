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
      setData(res.data)
      if (res.data.has_processing) {
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
    try {
      await documentsApi.upload(uploadTitle, uploadFile, uploadCategoryId)
      addAppNotification({
        title: 'Dokumen Baru',
        message: `Anda baru saja mengunggah dokumen "${uploadTitle}"`,
        type: 'info',
      })
      setShowModal(false)
      setUploadTitle('')
      setUploadFile(null)
      fetchData()
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal mengunggah dokumen.')
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
      case 'failed':     return 'bg-red-500/10 text-red-500 border border-red-500/20'
      default:           return 'bg-[var(--bg-input)] text-[var(--text-muted)] border border-[var(--border-color)]'
    }
  }

  return (
    <div className="p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto space-y-6 sm:space-y-8">
      {/* Top Banner & Action */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm">
        <div ref={headerRef}>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-black text-[var(--text-primary)] tracking-tight">MANAJEMEN DOKUMEN RAG</h1>
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Kelola basis pengetahuan (knowledge base) dokumen PDF untuk AI Assistant.
          </p>
        </div>
        <button
          className="px-5 py-3 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-300 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-sky-500/25 transition-all duration-200 hover:scale-[1.02] shrink-0"
          onClick={() => setShowModal(true)}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Unggah Dokumen Baru
        </button>
      </div>

      {error && (
        <div className="bg-red-500/10 text-red-500 p-4 rounded-2xl border border-red-500/20 text-sm font-medium">
          {error}
        </div>
      )}

      {/* Stats Cards */}
      <div
        className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 sm:gap-5"
        ref={statsGridRef}
      >
        {[
          {
            icon: <svg className="w-6 h-6 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>,
            bg: 'bg-sky-500/10 border-sky-500/20',
            label: 'Total Dokumen',
            value: data.stats?.total || 0,
          },
          {
            icon: <svg className="w-6 h-6 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>,
            bg: 'bg-emerald-500/10 border-emerald-500/20',
            label: 'Selesai Ter-index',
            value: data.stats?.completed || 0,
          },
          {
            icon: <svg className="w-6 h-6 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>,
            bg: 'bg-amber-500/10 border-amber-500/20',
            label: 'Dalam Pemrosesan',
            value: data.stats?.processing || 0,
          },
          {
            icon: <svg className="w-6 h-6 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>,
            bg: 'bg-red-500/10 border-red-500/20',
            label: 'Gagal Ter-index',
            value: data.stats?.failed || 0,
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl flex items-center gap-4 transition-all duration-200 hover:shadow-lg hover:-translate-y-1"
          >
            <div className={`w-12 h-12 rounded-2xl border ${stat.bg} flex items-center justify-center shrink-0`}>
              {stat.icon}
            </div>
            <div>
              <p className="text-xs text-[var(--text-muted)] font-semibold uppercase tracking-wider">{stat.label}</p>
              <h3 className="text-2xl font-black text-[var(--text-primary)] mt-1">
                {loading ? <div className="skeleton h-7 w-16" /> : stat.value}
              </h3>
            </div>
          </div>
        ))}
      </div>

      {/* Table Section */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl overflow-hidden shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-black/5 dark:bg-white/5 border-b border-[var(--border-color)]">
                {['Judul Dokumen', 'File Asli', 'Status', 'Kategori AI', 'Chunks', 'Waktu Unggah', 'Aksi'].map((h, i) => (
                  <th
                    key={h}
                    className={`px-6 py-4 text-xs font-bold text-[var(--text-muted)] uppercase tracking-wider ${i === 6 ? 'text-right' : ''}`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)] text-sm">
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td className="px-6 py-4"><div className="skeleton h-5 w-4/5" /></td>
                    <td className="px-6 py-4"><div className="skeleton h-5 w-3/5" /></td>
                    <td className="px-6 py-4"><div className="skeleton h-6 w-20 rounded-full" /></td>
                    <td className="px-6 py-4"><div className="skeleton h-5 w-16" /></td>
                    <td className="px-6 py-4"><div className="skeleton h-5 w-10" /></td>
                    <td className="px-6 py-4"><div className="skeleton h-5 w-24" /></td>
                    <td className="px-6 py-4 text-right"><div className="skeleton h-8 w-24 ml-auto" /></td>
                  </tr>
                ))
              ) : data.documents.length === 0 ? (
                <tr>
                  <td colSpan="7" className="text-center py-12 text-[var(--text-muted)] font-medium">
                    Belum ada dokumen yang diunggah. Klik tombol diatas untuk mengunggah dokumen baru.
                  </td>
                </tr>
              ) : (
                data.documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                    <td className="px-6 py-4 font-bold text-[var(--text-primary)]">{doc.title}</td>
                    <td className="px-6 py-4 text-[var(--text-secondary)] font-mono text-xs">{doc.original_filename}</td>
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${getBadgeClass(doc.status)}`}>
                        {doc.status === 'processing' && (
                          <svg className="spin w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                        )}
                        {doc.status_label}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <span className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-[var(--bg-input)] text-[var(--text-secondary)] border border-[var(--border-color)]">
                        {doc.category_name}
                      </span>
                    </td>
                    <td className="px-6 py-4 font-semibold text-[var(--text-primary)]">{doc.total_chunks || '-'}</td>
                    <td className="px-6 py-4 text-xs text-[var(--text-muted)] font-medium">{formatDate(doc.created_at)}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex gap-2 justify-end">
                        <Link
                          to={`/documents/${doc.id}`}
                          className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-sky-500/10 text-sky-500 hover:bg-sky-500 hover:text-white transition-all duration-200"
                        >
                          Detail
                        </Link>
                        <button
                          onClick={() => setDeleteTarget(doc)}
                          className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white transition-all duration-200"
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
          <div className="flex justify-between items-center px-6 py-4 border-t border-[var(--border-color)] bg-black/5 dark:bg-white/5">
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
          onClick={(e) => { if (e.target === e.currentTarget) setShowModal(false) }}
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
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors"
                onClick={() => setShowModal(false)}
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
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-sky-500 via-sky-500 to-sky-100 text-white dark:from-sky-500 dark:via-blue-600 dark:to-blue-700 dark:text-white font-bold text-sm shadow-lg shadow-sky-500/25 transition-all disabled:opacity-50"
                  disabled={uploading || !uploadTitle || !uploadFile}
                >
                  {uploading ? 'Mengunggah & Memproses...' : 'Unggah Dokumen'}
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
