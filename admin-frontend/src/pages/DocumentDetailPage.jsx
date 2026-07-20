import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { documentsApi } from '../api/documents'
import styles from './DocumentDetailPage.module.css'

export default function DocumentDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  
  const [document, setDocument] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  
  const [replaceFile, setReplaceFile] = useState(null)
  const [replacing, setReplacing] = useState(false)
  
  const [chunks, setChunks] = useState([])
  const [showChunks, setShowChunks] = useState(false)
  
  const fetchTimeout = useRef(null)

  const fetchDocument = async () => {
    try {
      const res = await documentsApi.get(id)
      setDocument(res.data.document)
      
      if (res.data.document.status === 'processing' || res.data.document.status === 'pending') {
        fetchTimeout.current = setTimeout(fetchDocument, 5000)
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Gagal memuat detail dokumen.')
    } finally {
      setLoading(false)
    }
  }

  const fetchChunks = async () => {
    try {
      const res = await documentsApi.getChunks(id)
      setChunks(res.chunks || [])
    } catch (err) {
      console.error('Gagal memuat chunks', err)
    }
  }

  useEffect(() => {
    fetchDocument()
    return () => clearTimeout(fetchTimeout.current)
  }, [id])

  const handleReplace = async (e) => {
    e.preventDefault()
    if (!replaceFile) return
    if (!window.confirm('Yakin ingin mengganti file ini? Proses indexing akan diulang dari awal.')) return
    
    setReplacing(true)
    try {
      await documentsApi.replace(id, replaceFile)
      setReplaceFile(null)
      fetchDocument()
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal mengganti file.')
    } finally {
      setReplacing(false)
    }
  }

  const handleDelete = async () => {
    if (!window.confirm('PERINGATAN: Dokumen ini akan dihapus permanen. Lanjutkan?')) return
    try {
      await documentsApi.destroy(id)
      navigate('/dashboard')
    } catch (err) {
      alert(err.response?.data?.message || 'Gagal menghapus dokumen.')
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
      case 'uploaded': return 'var(--blue-400)'
      case 'processing': return 'var(--yellow-400)'
      case 'completed': return 'var(--green-400)'
      case 'failed': return 'var(--red-400)'
      case 'replaced': return 'var(--orange-400)'
      default: return 'var(--text-secondary)'
    }
  }

  if (loading) {
    return (
      <div className={styles.container}>
        <div className="skeleton" style={{ height: '40px', width: '30%', marginBottom: '32px' }}></div>
        <div className={styles.grid}>
          <div className="skeleton" style={{ height: '400px', borderRadius: '16px' }}></div>
          <div className="skeleton" style={{ height: '400px', borderRadius: '16px' }}></div>
        </div>
      </div>
    )
  }

  if (error || !document) {
    return (
      <div className={styles.container}>
        <div className={styles.alert}>{error || 'Dokumen tidak ditemukan'}</div>
        <Link to="/dashboard" className={styles.link}>&larr; Kembali ke Dashboard</Link>
      </div>
    )
  }

  return (
    <div className={`fade-in ${styles.container}`}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerTitle}>
          <Link to="/dashboard" className={styles.backBtn} title="Kembali">
            <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
          </Link>
          <div>
            <h1 className={styles.title}>{document.title}</h1>
            <p className={styles.subtitle}>ID Dokumen: {document.id}</p>
          </div>
        </div>
      </div>

      <div className={styles.grid}>
        {/* KOLOM KIRI */}
        <div className={styles.colLeft}>
          
          {/* Card Info */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Informasi Dokumen</h3>
            
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Status</span>
              <span className={styles.infoValue}>
                <span className={styles.badge} style={{ 
                  background: document.status === 'completed' ? 'var(--green-bg)' : 
                              document.status === 'processing' ? 'var(--yellow-bg)' : 
                              document.status === 'failed' ? 'var(--red-bg)' : 'rgba(255,255,255,0.1)',
                  color: document.status === 'completed' ? 'var(--green-400)' : 
                         document.status === 'processing' ? 'var(--yellow-400)' : 
                         document.status === 'failed' ? 'var(--red-400)' : 'var(--text-secondary)'
                }}>
                  {document.status === 'processing' && <svg className="spin" width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ marginRight: '4px' }}><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>}
                  {document.status_label}
                </span>
              </span>
            </div>
            
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>File Asli</span>
              <span className={styles.infoValue}>{document.original_filename}</span>
            </div>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Tipe PDF</span>
              <span className={styles.infoValue}>{document.pdf_type_label}</span>
            </div>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Halaman / Chunks</span>
              <span className={styles.infoValue}>{document.total_pages || '-'} / {document.total_chunks || '-'}</span>
            </div>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Diunggah Oleh</span>
              <span className={styles.infoValue}>{document.uploaded_by || '-'}</span>
            </div>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Waktu Unggah</span>
              <span className={styles.infoValue}>{formatDate(document.created_at)}</span>
            </div>
            <div className={styles.infoRow}>
              <span className={styles.infoLabel}>Selesai Diproses</span>
              <span className={styles.infoValue}>{formatDate(document.processed_at)}</span>
            </div>
            
            {document.error_message && (
              <div className={styles.errorBox}>
                <strong>Pesan Error:</strong><br/>
                {document.error_message}
              </div>
            )}
          </div>

          {/* Card Replace */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Ganti File PDF</h3>
            <p className={styles.cardDesc}>Mengganti file akan menghapus indexing lama dan memproses ulang dokumen dari awal.</p>
            <form onSubmit={handleReplace}>
              <input 
                type="file" 
                accept="application/pdf"
                onChange={(e) => setReplaceFile(e.target.files[0])}
                className={styles.fileInput}
                disabled={replacing || document.status === 'processing'}
              />
              <button 
                type="submit" 
                className={styles.btnSecondary}
                disabled={!replaceFile || replacing || document.status === 'processing'}
                style={{ width: '100%' }}
              >
                {replacing ? 'Mengunggah...' : 'Ganti & Proses Ulang'}
              </button>
            </form>
          </div>

          {/* Card Danger */}
          <div className={`${styles.card} ${styles.cardDanger}`}>
            <h3 className={styles.cardTitle} style={{ color: 'var(--red-400)' }}>Zona Berbahaya</h3>
            <p className={styles.cardDesc}>Menghapus dokumen bersifat permanen. AI tidak akan bisa lagi mencari jawaban dari dokumen ini.</p>
            <button onClick={handleDelete} className={styles.btnDangerOutlined} style={{ width: '100%' }}>
              Hapus Dokumen
            </button>
          </div>

        </div>

        {/* KOLOM KANAN */}
        <div className={styles.colRight}>
          
          {/* Card PDF */}
          <div className={styles.card} style={{ display: 'flex', flexDirection: 'column', height: '500px', padding: 0, overflow: 'hidden' }}>
            <div className={styles.cardHeaderWithAction}>
              <h3 className={styles.cardTitle} style={{ margin: 0 }}>Pratinjau PDF</h3>
              <a href={documentsApi.pdfUrl(id)} target="_blank" rel="noopener" className={styles.linkAction}>
                Buka di Tab Baru <svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
              </a>
            </div>
            <div className={styles.iframeWrapper}>
              <iframe 
                src={documentsApi.pdfUrl(id)} 
                className={styles.iframe} 
                title={document.title}
              />
            </div>
          </div>

          {/* Card Chunks / Vektor */}
          <div className={styles.card}>
            <div className={styles.cardHeaderWithAction}>
              <h3 className={styles.cardTitle} style={{ margin: 0 }}>Data Vektor ChromaDB</h3>
              <button 
                onClick={() => {
                  setShowChunks(!showChunks);
                  if (!showChunks && chunks.length === 0) fetchChunks();
                }}
                className={styles.btnSecondary}
                style={{ fontSize: '12px', padding: '4px 10px' }}
              >
                {showChunks ? 'Sembunyikan' : 'Tampilkan Teks OCR'}
              </button>
            </div>
            
            {showChunks && (
              <div style={{ marginTop: '16px', maxHeight: '450px', overflowY: 'auto' }}>
                {chunks.length === 0 ? <p className={styles.emptyText}>Memuat atau tidak ada data...</p> : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {chunks.map(c => (
                      <div key={c.id} style={{ background: 'var(--bg-main)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                          <span><strong>ID:</strong> {c.id}</span>
                          <span style={{ background: 'var(--brand-primary)', color: '#000', padding: '2px 8px', borderRadius: '12px', fontWeight: 'bold' }}>
                            Halaman {c.metadata.page_number}
                          </span>
                        </div>
                        <p style={{ fontSize: '14px', whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-primary)', lineHeight: '1.6' }}>
                          {c.text}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Card Logs */}
          <div className={styles.card}>
            <h3 className={styles.cardTitle}>Riwayat Pemrosesan</h3>
            
            <div className={styles.timeline}>
              {document.logs && document.logs.length > 0 ? (
                document.logs.map((log, index) => (
                  <div key={log.id} className={styles.timelineItem}>
                    <div className={styles.timelineIcon} style={{ background: getLogColor(log.action) }}>
                      <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--surface-900)' }}>
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    {index !== document.logs.length - 1 && <div className={styles.timelineLine}></div>}
                    <div className={styles.timelineContent}>
                      <div className={styles.timelineHeader}>
                        <span className={styles.timelineAction}>{log.action_label}</span>
                        <span className={styles.timelineDate}>{formatDate(log.created_at)}</span>
                      </div>
                      <p className={styles.timelineDetails}>{log.details}</p>
                    </div>
                  </div>
                ))
              ) : (
                <p className={styles.emptyText}>Belum ada riwayat.</p>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
