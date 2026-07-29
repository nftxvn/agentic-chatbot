import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { documentsApi } from '../api/documents'
import { categoriesApi } from '../api/categories'
import styles from './DashboardPage.module.css'
import ConfirmModal from '../components/ConfirmModal'

export default function DashboardPage() {
  const [data, setData] = useState({ documents: [], stats: {}, meta: {} })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  
  // Modal Upload state
  const [showModal, setShowModal] = useState(false)
  const [uploadTitle, setUploadTitle] = useState('')
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadCategoryId, setUploadCategoryId] = useState('')
  const [uploading, setUploading] = useState(false)
  
  // Delete Confirmation state
  const [deleteTarget, setDeleteTarget] = useState(null)

  // Categories
  const [categories, setCategories] = useState([])

  const fetchTimeout = useRef(null)
  const statsGridRef = useRef(null)
  const modalRef = useRef(null)
  const headerRef = useRef(null)

  const fetchData = async (page = 1) => {
    try {
      const res = await documentsApi.list(page)
      setData(res.data)
      
      // Polling if there's any document processing
      if (res.data.has_processing) {
        fetchTimeout.current = setTimeout(() => fetchData(page), 10000) // Poll every 10s
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Gagal memuat data dokumen.')
    } finally {
      setLoading(false)
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
    if (headerRef.current && window.gsap) {
      window.gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -20 },
        { opacity: 1, x: 0, duration: 0.6, stagger: 0.1, ease: 'power2.out', clearProps: 'all' }
      )
    }
    
    if (!loading && statsGridRef.current && window.gsap) {
      const cards = statsGridRef.current.children
      
      window.gsap.fromTo(
        cards,
        { opacity: 0, y: -20 },
        { opacity: 1, y: 0, duration: 0.6, stagger: 0.05, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading])

  useEffect(() => {
    if (showModal && modalRef.current && window.gsap) {
      window.gsap.fromTo(
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
      setShowModal(false)
      setUploadTitle('')
      setUploadFile(null)
      fetchData() // Refresh data immediately
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal mengunggah dokumen.')
    } finally {
      setUploading(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    
    try {
      await documentsApi.destroy(deleteTarget.id)
      fetchData(data.meta?.current_page || 1)
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal menghapus dokumen.')
    } finally {
      setDeleteTarget(null)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return '-'
    // Hapus 'Z' atau offset agar browser menterjemahkannya langsung sebagai waktu lokal
    const localStr = dateString.replace('Z', '').replace('+00:00', '')
    return new Date(localStr).toLocaleDateString('id-ID', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    })
  }

  const getBadgeClass = (status) => {
    switch (status) {
      case 'completed': return styles.badgeSuccess
      case 'processing': return styles.badgeWarning
      case 'failed': return styles.badgeDanger
      default: return styles.badgeSecondary
    }
  }

  return (
    <>
      <div className={styles.container}>
      <div className={styles.header}>
        <div ref={headerRef}>
          <h1 className={styles.title}>MANAJEMEN DOKUMEN</h1>
          <p className={styles.subtitle}>Kelola dokumen dasar pengetahuan untuk AI Assistant</p>
        </div>
        <button className={styles.primaryBtn} onClick={() => setShowModal(true)}>
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
          Unggah Dokumen
        </button>
      </div>

      {error && <div className={styles.alert}>{error}</div>}

      <div className={styles.statsGrid} ref={statsGridRef}>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.statIconTotal}`}>
            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
          </div>
          <div>
            <p className={styles.statLabel}>Total Dokumen</p>
            <h3 className={styles.statValue}>
              {loading ? <div className="skeleton" style={{ height: '28px', width: '60px', marginTop: '4px', borderRadius: '4px' }}></div> : (data.stats?.total || 0)}
            </h3>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.statIconSuccess}`}>
            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          </div>
          <div>
            <p className={styles.statLabel}>Selesai</p>
            <h3 className={styles.statValue}>
              {loading ? <div className="skeleton" style={{ height: '28px', width: '60px', marginTop: '4px', borderRadius: '4px' }}></div> : (data.stats?.completed || 0)}
            </h3>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.statIconProcessing}`}>
            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          </div>
          <div>
            <p className={styles.statLabel}>Memproses</p>
            <h3 className={styles.statValue}>
              {loading ? <div className="skeleton" style={{ height: '28px', width: '60px', marginTop: '4px', borderRadius: '4px' }}></div> : (data.stats?.processing || 0)}
            </h3>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.statIconFailed}`}>
            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
          </div>
          <div>
            <p className={styles.statLabel}>Gagal</p>
            <h3 className={styles.statValue}>
              {loading ? <div className="skeleton" style={{ height: '28px', width: '60px', marginTop: '4px', borderRadius: '4px' }}></div> : (data.stats?.failed || 0)}
            </h3>
          </div>
        </div>
      </div>

      <div className={styles.tableCard}>
        <div className={styles.tableResponsive}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Nama Dokumen</th>
                <th>File Asli</th>
                <th>Status</th>
                <th>Kategori</th>
                <th>Chunks</th>
                <th>Diunggah</th>
                <th align="right">Aksi</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td><div className="skeleton" style={{ height: '20px', width: '80%' }}></div></td>
                    <td><div className="skeleton" style={{ height: '20px', width: '60%' }}></div></td>
                    <td><div className="skeleton" style={{ height: '24px', width: '80px', borderRadius: '12px' }}></div></td>
                    <td><div className="skeleton" style={{ height: '20px', width: '60px' }}></div></td>
                    <td><div className="skeleton" style={{ height: '20px', width: '40px' }}></div></td>
                    <td><div className="skeleton" style={{ height: '20px', width: '100px' }}></div></td>
                    <td><div className="skeleton" style={{ height: '32px', width: '100%', borderRadius: '6px' }}></div></td>
                  </tr>
                ))
              ) : data.documents.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', padding: '40px' }}>
                    <p style={{ color: 'var(--text-muted)' }}>Belum ada dokumen yang diunggah.</p>
                  </td>
                </tr>
              ) : (
                data.documents.map(doc => (
                  <tr key={doc.id}>
                    <td className={styles.fw500}>{doc.title}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{doc.original_filename}</td>
                    <td>
                      <span className={`${styles.badge} ${getBadgeClass(doc.status)}`}>
                        {doc.status === 'processing' && <svg className="spin" width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ marginRight: '4px' }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>}
                        {doc.status_label}
                      </span>
                    </td>
                    <td>
                      <span className={styles.badge} style={{ backgroundColor: 'var(--bg-secondary)', color: 'var(--text-primary)' }}>
                        {doc.category_name}
                      </span>
                    </td>
                    <td>{doc.total_chunks || '-'}</td>
                    <td style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                      {formatDate(doc.created_at)}
                    </td>
                    <td align="right">
                      <div className={styles.actionGroup}>
                        <Link to={`/documents/${doc.id}`} className={styles.btnSm}>Lihat</Link>
                        <button onClick={() => setDeleteTarget(doc)} className={`${styles.btnSm} ${styles.btnDanger}`}>Hapus</button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {!loading && data.meta?.last_page > 1 && (
          <div className={styles.pagination}>
            <button 
              disabled={data.meta.current_page === 1}
              onClick={() => fetchData(data.meta.current_page - 1)}
              className={styles.pageBtn}
            >
              &larr; Prev
            </button>
            <span className={styles.pageInfo}>
              Hal {data.meta.current_page} dari {data.meta.last_page}
            </span>
            <button 
              disabled={data.meta.current_page === data.meta.last_page}
              onClick={() => fetchData(data.meta.current_page + 1)}
              className={styles.pageBtn}
            >
              Next &rarr;
            </button>
          </div>
        )}
      </div>
    </div>

      {/* Upload Modal */}
      {showModal && (
        <div className={styles.modalOverlay} onClick={(e) => { if (e.target === e.currentTarget) setShowModal(false) }}>
          <div className={styles.modal} ref={modalRef}>
            <div className={styles.modalHeader}>
              <h3 className={styles.modalTitle}>Unggah Dokumen Baru</h3>
              <button className={styles.closeBtn} onClick={() => setShowModal(false)}>
                <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            <form onSubmit={handleUploadSubmit}>
              <div className={styles.modalBody}>
                <div className={styles.formGroup}>
                  <label>Judul Dokumen</label>
                  <input 
                    type="text" 
                    value={uploadTitle}
                    onChange={e => setUploadTitle(e.target.value)}
                    placeholder="Contoh: SK Pelayanan Publik 2024"
                    required
                    disabled={uploading}
                  />
                </div>
                <div className={styles.formGroup}>
                  <label>Kategori Dokumen / AI Prompt</label>
                  <select
                    value={uploadCategoryId}
                    onChange={e => setUploadCategoryId(e.target.value)}
                    required
                    disabled={uploading}
                    className={styles.select}
                  >
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
                <div className={styles.formGroup}>
                  <label>File PDF</label>
                  <input 
                    type="file" 
                    accept="application/pdf"
                    onChange={e => setUploadFile(e.target.files[0])}
                    required
                    disabled={uploading}
                  />
                  <p className={styles.helpText}>Maksimal ukuran file: 50MB</p>
                </div>
              </div>
              <div className={styles.modalFooter}>
                <button type="button" className={styles.btnSecondary} onClick={() => setShowModal(false)} disabled={uploading}>Batal</button>
                <button type="submit" className={styles.primaryBtn} disabled={uploading || !uploadTitle || !uploadFile}>
                  {uploading ? 'Mengunggah...' : 'Unggah & Proses'}
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
    </>
  )
}
