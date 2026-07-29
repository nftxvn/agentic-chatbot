import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { categoriesApi } from '../api/categories'
import styles from './CategoriesPage.module.css'
import ConfirmModal from '../components/ConfirmModal'

export default function CategoriesPage() {
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingCategory, setEditingCategory] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  // Advanced AI fields
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    ui_layout: 'general',
    vision_prompt: '',
    llm_prompt: '',
    prompt_variables: '',
    vision_model: '',
    llm_model: '',
    temperature: 0.0,
    chunk_size: 1000,
    chunk_overlap: 200,
  })

  // Ollama & Testing states
  const [ollamaModels, setOllamaModels] = useState([])
  const [testImageBase64, setTestImageBase64] = useState('')
  const [testResult, setTestResult] = useState('')
  const [isTesting, setIsTesting] = useState(false)

  // Refs for animation
  const gridRef = useRef(null)
  const modalRef = useRef(null)
  const headerRef = useRef(null)

  useEffect(() => {
    fetchCategories()
    fetchOllamaModels()
  }, [])

  useLayoutEffect(() => {
    if (headerRef.current && window.gsap) {
      window.gsap.fromTo(
        headerRef.current.children,
        { opacity: 0, x: -20 },
        { opacity: 1, x: 0, duration: 0.6, stagger: 0.1, ease: 'power2.out', clearProps: 'all' }
      )
    }

    if (!loading && categories.length > 0 && gridRef.current && window.gsap) {
      const elements = gridRef.current.children
      window.gsap.fromTo(
        elements,
        { opacity: 0, y: -20 },
        { opacity: 1, y: 0, duration: 0.6, stagger: 0.15, ease: 'power2.out', clearProps: 'all' }
      )
    }
  }, [loading, categories.length])

  useEffect(() => {
    if (showModal && modalRef.current && window.gsap) {
      window.gsap.fromTo(
        modalRef.current,
        { opacity: 0, scale: 0.95, y: 20 },
        { opacity: 1, scale: 1, y: 0, duration: 0.3, ease: 'power2.inOut' }
      )
    }
  }, [showModal])

  const fetchOllamaModels = async () => {
    try {
      const res = await categoriesApi.ollamaTags()
      if (res && res.models) {
        setOllamaModels(res.models.map(m => m.name))
      }
    } catch (err) {
      console.error('Failed to load Ollama tags', err)
    }
  }

  const fetchCategories = async () => {
    try {
      setLoading(true)
      const res = await categoriesApi.list()
      setCategories(res.data)
    } catch (err) {
      console.error('Failed to load categories', err)
    } finally {
      setLoading(false)
    }
  }

  const handleOpenModal = (category = null) => {
    if (category) {
      setEditingCategory(category)
      setFormData({
        name: category.name || '',
        description: category.description || '',
        ui_layout: category.ui_layout || 'general',
        vision_prompt: category.vision_prompt || '',
        llm_prompt: category.llm_prompt || '',
        prompt_variables: category.prompt_variables ? JSON.stringify(category.prompt_variables, null, 2) : '',
        vision_model: category.vision_model || '',
        llm_model: category.llm_model || '',
        temperature: category.temperature ?? 0.0,
        chunk_size: category.chunk_size ?? 1000,
        chunk_overlap: category.chunk_overlap ?? 200,
      })
    } else {
      setEditingCategory(null)
      setFormData({
        name: '',
        description: '',
        ui_layout: 'general',
        vision_prompt: '',
        llm_prompt: '',
        prompt_variables: '',
        vision_model: '',
        llm_model: '',
        temperature: 0.0,
        chunk_size: 1000,
        chunk_overlap: 200,
      })
    }
    setTestImageBase64('')
    setTestResult('')
    setShowModal(true)
  }

  const handleTestPrompt = async () => {
    if (!testImageBase64) {
      alert("Silakan unggah gambar terlebih dahulu untuk ditest.")
      return
    }
    setIsTesting(true)
    setTestResult('')
    try {
      const payload = {
        image_base64: testImageBase64.split(',')[1] || testImageBase64,
        category: {
          ...formData,
          prompt_variables: formData.prompt_variables ? JSON.parse(formData.prompt_variables) : null
        }
      }
      const res = await categoriesApi.testPrompt(payload)
      if (res.success) {
        setTestResult(res.result)
      } else {
        setTestResult('Error: ' + res.error)
      }
    } catch (err) {
      console.error(err)
      setTestResult('Terjadi kesalahan saat memanggil test API.')
    } finally {
      setIsTesting(false)
    }
  }

  const handleImageUpload = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      setTestImageBase64(reader.result)
    }
    reader.readAsDataURL(file)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const payload = { ...formData }
      // Validasi JSON
      if (payload.prompt_variables) {
        JSON.parse(payload.prompt_variables)
      } else {
        payload.prompt_variables = null
      }

      if (editingCategory) {
        await categoriesApi.update(editingCategory.id, payload)
      } else {
        await categoriesApi.create(payload)
      }
      setShowModal(false)
      fetchCategories()
    } catch (err) {
      console.error('Save failed', err)
      alert('Gagal menyimpan kategori. Pastikan JSON valid jika diisi.')
    }
  }

  const confirmDelete = async () => {
    if (!deleteTarget) return
    try {
      await categoriesApi.destroy(deleteTarget)
      fetchCategories()
    } catch (err) {
      console.error('Delete failed', err)
      alert('Gagal menghapus kategori.')
    } finally {
      setDeleteTarget(null)
    }
  }


  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <div ref={headerRef}>
          <h1 className={styles.title}>KATEGORI DOKUMEN AI</h1>
          <p className={styles.subtitle}>Kelola prompt AI dan template antarmuka untuk berbagai jenis dokumen.</p>
        </div>
        <button className={styles.primaryBtn} onClick={() => handleOpenModal()}>
          <svg width="20" height="20" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Kategori Baru
        </button>
      </header>

      {loading ? (
        <div className={styles.grid}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className={styles.card} style={{ minHeight: '180px' }}>
              <div className="skeleton" style={{ height: '24px', width: '60%', marginBottom: '16px' }}></div>
              <div className="skeleton" style={{ height: '16px', width: '100%', marginBottom: '8px' }}></div>
              <div className="skeleton" style={{ height: '16px', width: '80%', marginBottom: '24px' }}></div>
              <div style={{ display: 'flex', gap: '12px', marginTop: 'auto' }}>
                <div className="skeleton" style={{ height: '36px', flex: 1 }}></div>
                <div className="skeleton" style={{ height: '36px', flex: 1 }}></div>
              </div>
            </div>
          ))}
        </div>
      ) : categories.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '64px 20px', color: 'var(--text-secondary)' }}>
          <svg width="64" height="64" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ opacity: 0.5, marginBottom: '16px' }}>
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
          </svg>
          <h3 style={{ fontSize: '18px', color: 'var(--text-primary)', marginBottom: '8px' }}>Belum Ada Kategori</h3>
          <p>Tambahkan kategori pertama Anda untuk mulai mengatur prompt AI.</p>
        </div>
      ) : (
        <div className={styles.grid} ref={gridRef}>
          {categories.map(cat => (
            <div key={cat.id} className={styles.card}>
              <div className={styles.cardHeader}>
                <h3 className={styles.cardTitle}>{cat.name}</h3>
                <span className={styles.badge}>{cat.ui_layout}</span>
              </div>
              <p className={styles.cardDesc}>{cat.description || 'Tidak ada deskripsi.'}</p>
              
              <div className={styles.actions}>
                <button className={styles.actionBtn} onClick={() => handleOpenModal(cat)}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ verticalAlign: 'middle', marginRight: '6px', marginBottom: '2px' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                  </svg>
                  Edit
                </button>
                <button className={styles.actionBtn + ' ' + styles.delete} onClick={() => setDeleteTarget(cat.id)}>
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ verticalAlign: 'middle', marginRight: '6px', marginBottom: '2px' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                  Hapus
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className={styles.modalOverlay}>
          <form className={styles.modal} onSubmit={handleSubmit} ref={modalRef}>
            <div className={styles.modalHeader}>
              <h2>{editingCategory ? 'Edit Kategori' : 'Kategori AI Baru'}</h2>
              <button type="button" className={styles.closeBtn} onClick={() => setShowModal(false)}>✕</button>
            </div>
            
            <div className={styles.modalBody}>
              <div className={styles.formGroup}>
                <label>Nama Kategori</label>
                <input 
                  type="text" 
                  className={styles.input} 
                  value={formData.name}
                  onChange={e => setFormData({...formData, name: e.target.value})}
                  required
                  placeholder="Contoh: SOP Flowchart"
                />
              </div>

              <div className={styles.formGroup}>
                <label>Deskripsi Singkat</label>
                <input 
                  type="text" 
                  className={styles.input} 
                  value={formData.description}
                  onChange={e => setFormData({...formData, description: e.target.value})}
                  placeholder="Contoh: Untuk dokumen standar operasional prosedur"
                />
              </div>

              <div className={styles.formGroup}>
                <label>UI Layout (Tampilan Web)</label>
                <select 
                  className={styles.select}
                  value={formData.ui_layout}
                  onChange={e => setFormData({...formData, ui_layout: e.target.value})}
                >
                  <option value="general">General (Markdown Biasa)</option>
                  <option value="flowchart">SOP Flowchart (Drag & Drop)</option>
                </select>
              </div>

              <div className={styles.formGroup}>
                <label>Vision Prompt (Instruksi Baca Gambar)</label>
                <textarea 
                  className={styles.textarea} 
                  value={formData.vision_prompt}
                  onChange={e => setFormData({...formData, vision_prompt: e.target.value})}
                  placeholder="Instruksi untuk model mata (Qwen2.5-VL)"
                />
              </div>

              <div className={styles.formGroup}>
                <label>LLM Prompt (Instruksi Logika/Koreksi Teks)</label>
                <textarea 
                  className={styles.textarea} 
                  value={formData.llm_prompt}
                  onChange={e => setFormData({...formData, llm_prompt: e.target.value})}
                  placeholder="Gunakan {TEXT} untuk tempat teks hasil ekstraksi disisipkan."
                />
              </div>

              <div className={styles.formGroup}>
                <label>Variabel Tambahan (Format JSON)</label>
                <textarea 
                  className={`${styles.textarea} ${styles.code}`} 
                  value={formData.prompt_variables}
                  onChange={e => setFormData({...formData, prompt_variables: e.target.value})}
                  placeholder={`{\n  "job_titles": ["PA/KPA", "PPK"]\n}`}
                />
                <small style={{color: 'var(--text-secondary)', marginTop: '4px'}}>
                  Digunakan untuk menyuntikkan data seperti daftar jabatan ke dalam LLM Prompt.
                </small>
              </div>

              <div className={styles.formGroup} style={{display: 'flex', gap: '16px'}}>
                <div style={{flex: 1}}>
                  <label>Vision Model</label>
                  <select 
                    className={styles.select}
                    value={formData.vision_model}
                    onChange={e => setFormData({...formData, vision_model: e.target.value})}
                  >
                    <option value="">-- Default Global --</option>
                    {ollamaModels.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
                <div style={{flex: 1}}>
                  <label>LLM Model</label>
                  <select 
                    className={styles.select}
                    value={formData.llm_model}
                    onChange={e => setFormData({...formData, llm_model: e.target.value})}
                  >
                    <option value="">-- Default Global --</option>
                    {ollamaModels.map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className={styles.formGroup} style={{display: 'flex', gap: '16px', alignItems: 'center'}}>
                <div style={{flex: 1}}>
                  <label>Temperature (Kreativitas AI): {formData.temperature}</label>
                  <input 
                    type="range" 
                    min="0" max="2" step="0.1" 
                    style={{width: '100%', cursor: 'pointer', accentColor: 'var(--brand-primary)'}}
                    value={formData.temperature}
                    onChange={e => setFormData({...formData, temperature: parseFloat(e.target.value)})}
                  />
                </div>
                <div style={{flex: 1}}>
                  <label>Chunk Size (Karakter)</label>
                  <input 
                    type="number" 
                    className={styles.input} 
                    value={formData.chunk_size}
                    onChange={e => setFormData({...formData, chunk_size: parseInt(e.target.value, 10)})}
                  />
                </div>
                <div style={{flex: 1}}>
                  <label>Chunk Overlap (Karakter)</label>
                  <input 
                    type="number" 
                    className={styles.input} 
                    value={formData.chunk_overlap}
                    onChange={e => setFormData({...formData, chunk_overlap: parseInt(e.target.value, 10)})}
                  />
                </div>
              </div>

              <div className={styles.testSection} style={{background: 'var(--bg-card)', padding: '16px', borderRadius: '0', border: '1px solid var(--border-color)', marginTop: '16px'}}>
                <h4 style={{margin: '0 0 12px 0', fontSize: '15px', color: 'var(--brand-primary)'}}>
                  <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{verticalAlign: 'middle', marginRight: '6px', marginBottom: '2px'}}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" />
                  </svg>
                  Live Preview / Test Prompt
                </h4>
                <div style={{display: 'flex', gap: '12px', alignItems: 'center'}}>
                  <input type="file" accept="image/*" onChange={handleImageUpload} className={styles.input} style={{flex: 1}} />
                  <button type="button" onClick={handleTestPrompt} disabled={isTesting || !testImageBase64} className={styles.primaryBtn} style={{padding: '8px 16px'}}>
                    {isTesting ? 'Sedang Memproses...' : 'Test Sekarang'}
                  </button>
                </div>
                {testResult && (
                  <div style={{marginTop: '16px', padding: '12px', background: 'var(--bg-input)', borderRadius: '0', maxHeight: '200px', overflowY: 'auto', fontSize: '13px', whiteSpace: 'pre-wrap', border: '1px solid var(--border-color)'}}>
                    {testResult}
                  </div>
                )}
              </div>
            </div>

            <div className={styles.modalFooter}>
              <button type="button" className={styles.secondaryBtn} onClick={() => setShowModal(false)}>Batal</button>
              <button type="submit" className={styles.primaryBtn}>Simpan Kategori</button>
            </div>
          </form>
        </div>
      )}
      
      <ConfirmModal 
        isOpen={!!deleteTarget}
        title="Hapus Kategori"
        message="Yakin ingin menghapus kategori ini? Data yang terkait mungkin akan ikut terpengaruh."
        onConfirm={confirmDelete}
        onCancel={() => setDeleteTarget(null)}
        confirmText="Hapus"
      />
    </div>
  )
}
