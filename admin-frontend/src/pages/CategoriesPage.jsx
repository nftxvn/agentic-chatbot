import { useState, useEffect, useRef, useLayoutEffect } from 'react'
import { categoriesApi } from '../api/categories'
import ConfirmModal from '../components/ConfirmModal'
import { Badge } from '@/components/ui/badge'

export default function CategoriesPage() {
  const [categories, setCategories] = useState([])
  const [loading, setLoading] = useState(true)
  const [showModal, setShowModal] = useState(false)
  const [editingCategory, setEditingCategory] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

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

  const [ollamaModels, setOllamaModels] = useState([])
  const [testImageBase64, setTestImageBase64] = useState('')
  const [testResult, setTestResult] = useState('')
  const [isTesting, setIsTesting] = useState(false)

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
        name: '', description: '', ui_layout: 'general',
        vision_prompt: '', llm_prompt: '', prompt_variables: '',
        vision_model: '', llm_model: '', temperature: 0.0,
        chunk_size: 1000, chunk_overlap: 200,
      })
    }
    setTestImageBase64('')
    setTestResult('')
    setShowModal(true)
  }

  const handleTestPrompt = async () => {
    if (!testImageBase64) {
      alert('Silakan unggah gambar terlebih dahulu untuk ditest.')
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
    reader.onload = () => setTestImageBase64(reader.result)
    reader.readAsDataURL(file)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      const payload = { ...formData }
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
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-sm">
        <div ref={headerRef}>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-purple-500" />
            <h1 className="text-2xl font-black text-[var(--text-primary)] tracking-tight">KATEGORI DOKUMEN AI</h1>
          </div>
          <p className="text-sm text-[var(--text-secondary)] mt-1">
            Konfigurasi instruksi LLM, Vision model, serta template antarmuka per jenis dokumen.
          </p>
        </div>
        <button
          className="px-5 py-3 rounded-xl bg-gradient-to-r from-sky-500 via-blue-600 to-blue-700 hover:from-sky-400 hover:to-blue-500 text-white font-bold text-sm flex items-center justify-center gap-2 shadow-lg shadow-sky-500/25 transition-all duration-200 hover:scale-[1.02] shrink-0"
          onClick={() => handleOpenModal()}
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Tambah Kategori Baru
        </button>
      </div>

      {/* Grid of Categories */}
      <div>
        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl space-y-4">
                <div className="skeleton h-6 w-1/2" />
                <div className="skeleton h-4 w-full" />
                <div className="skeleton h-4 w-3/4" />
                <div className="flex gap-3 pt-4">
                  <div className="skeleton h-10 flex-1" />
                  <div className="skeleton h-10 flex-1" />
                </div>
              </div>
            ))}
          </div>
        ) : categories.length === 0 ? (
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl p-12 text-center text-[var(--text-secondary)]">
            <div className="w-16 h-16 rounded-2xl bg-sky-500/10 text-sky-500 flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-1">Belum Ada Kategori</h3>
            <p className="text-sm">Tambahkan kategori pertama Anda untuk mulai mengatur prompt AI.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6" ref={gridRef}>
            {categories.map((cat) => (
              <div
                key={cat.id}
                className="bg-[var(--bg-card)] border border-[var(--border-color)] p-6 rounded-2xl flex flex-col justify-between hover:shadow-xl hover:-translate-y-1 transition-all duration-300"
              >
                <div>
                  <div className="flex justify-between items-start mb-3">
                    <h3 className="text-xl font-bold text-[var(--text-primary)]">{cat.name}</h3>
                    <Badge variant="default" className="uppercase tracking-wider">
                      {cat.ui_layout}
                    </Badge>
                  </div>
                  <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-6">
                    {cat.description || 'Tidak ada deskripsi.'}
                  </p>
                </div>

                <div className="flex gap-3 pt-4 border-t border-[var(--border-color)]">
                  <button
                    className="flex-1 py-2.5 px-4 rounded-xl text-xs font-bold bg-[var(--bg-input)] hover:bg-[var(--border-color)] text-[var(--text-primary)] border border-[var(--border-color)] transition-colors flex items-center justify-center gap-1.5"
                    onClick={() => handleOpenModal(cat)}
                  >
                    <svg className="w-4 h-4 text-sky-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                    </svg>
                    Edit Config
                  </button>
                  <button
                    className="py-2.5 px-4 rounded-xl text-xs font-bold bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white border border-red-500/20 transition-all flex items-center justify-center gap-1.5"
                    onClick={() => setDeleteTarget(cat.id)}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Hapus
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal Edit / Create */}
      {showModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[100] p-4">
          <form
            className="bg-[var(--bg-card)] border border-[var(--border-color)] w-full max-w-3xl max-h-[90vh] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
            onSubmit={handleSubmit}
            ref={modalRef}
          >
            {/* Modal Header */}
            <div className="px-6 py-5 border-b border-[var(--border-color)] flex justify-between items-center bg-black/5 dark:bg-white/5">
              <h2 className="text-lg font-bold text-[var(--text-primary)]">
                {editingCategory ? 'Edit Kategori AI' : 'Kategori AI Baru'}
              </h2>
              <button
                type="button"
                className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1 rounded-lg transition-colors"
                onClick={() => setShowModal(false)}
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Nama Kategori</label>
                  <input
                    type="text"
                    className="w-full"
                    value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    required
                    placeholder="Contoh: SOP Flowchart"
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">UI Layout</label>
                  <select
                    className="w-full"
                    value={formData.ui_layout}
                    onChange={e => setFormData({ ...formData, ui_layout: e.target.value })}
                  >
                    <option value="general">General (Markdown Biasa)</option>
                    <option value="flowchart">SOP Flowchart (Drag & Drop)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Deskripsi Singkat</label>
                <input
                  type="text"
                  className="w-full"
                  value={formData.description}
                  onChange={e => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Contoh: Untuk dokumen standar operasional prosedur"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Vision Prompt (Model OCR / Vision)</label>
                <textarea
                  className="w-full min-h-[90px]"
                  value={formData.vision_prompt}
                  onChange={e => setFormData({ ...formData, vision_prompt: e.target.value })}
                  placeholder="Instruksi untuk model vision (Qwen2.5-VL)"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">LLM Prompt (Teks Extractor / Corrector)</label>
                <textarea
                  className="w-full min-h-[90px]"
                  value={formData.llm_prompt}
                  onChange={e => setFormData({ ...formData, llm_prompt: e.target.value })}
                  placeholder="Gunakan {TEXT} untuk tempat teks hasil ekstraksi disisipkan."
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Variabel JSON (Opsional)</label>
                <textarea
                  className="w-full min-h-[70px] font-mono text-xs"
                  value={formData.prompt_variables}
                  onChange={e => setFormData({ ...formData, prompt_variables: e.target.value })}
                  placeholder={`{\n  "job_titles": ["PA/KPA", "PPK"]\n}`}
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Vision Model</label>
                  <select className="w-full" value={formData.vision_model} onChange={e => setFormData({ ...formData, vision_model: e.target.value })}>
                    <option value="">-- Default Global --</option>
                    {ollamaModels.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">LLM Model</label>
                  <select className="w-full" value={formData.llm_model} onChange={e => setFormData({ ...formData, llm_model: e.target.value })}>
                    <option value="">-- Default Global --</option>
                    {ollamaModels.map(m => <option key={m} value={m}>{m}</option>)}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2">
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Temperature ({formData.temperature})</label>
                  <input
                    type="range"
                    min="0" max="2" step="0.1"
                    className="w-full accent-sky-600"
                    value={formData.temperature}
                    onChange={e => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Chunk Size</label>
                  <input
                    type="number"
                    className="w-full"
                    value={formData.chunk_size}
                    onChange={e => setFormData({ ...formData, chunk_size: parseInt(e.target.value, 10) })}
                  />
                </div>
                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-[var(--text-muted)] mb-2">Chunk Overlap</label>
                  <input
                    type="number"
                    className="w-full"
                    value={formData.chunk_overlap}
                    onChange={e => setFormData({ ...formData, chunk_overlap: parseInt(e.target.value, 10) })}
                  />
                </div>
              </div>

              {/* Test Prompt Section */}
              <div className="bg-[var(--bg-input)] p-5 rounded-xl border border-[var(--border-color)] space-y-3">
                <h4 className="text-sm font-bold text-sky-500 flex items-center gap-2">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Live Preview / Test Prompt
                </h4>
                <div className="flex flex-col md:flex-row gap-3 items-center">
                  <input
                    type="file"
                    accept="image/*"
                    onChange={handleImageUpload}
                    className="w-full text-xs text-[var(--text-secondary)] file:mr-4 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-sky-500/10 file:text-sky-500"
                  />
                  <button
                    type="button"
                    onClick={handleTestPrompt}
                    disabled={isTesting || !testImageBase64}
                    className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shrink-0 disabled:opacity-50"
                  >
                    {isTesting ? 'Testing...' : 'Test Sekarang'}
                  </button>
                </div>
                {testResult && (
                  <div className="mt-3 p-3 bg-[var(--bg-card)] rounded-lg max-h-40 overflow-y-auto text-xs font-mono text-[var(--text-primary)] border border-[var(--border-color)]">
                    {testResult}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-[var(--border-color)] bg-black/5 dark:bg-white/5 flex justify-end gap-3">
              <button
                type="button"
                className="px-4 py-2.5 rounded-xl border border-[var(--border-color)] bg-[var(--bg-input)] text-sm font-semibold text-[var(--text-primary)] hover:bg-[var(--border-color)] transition-colors"
                onClick={() => setShowModal(false)}
              >
                Batal
              </button>
              <button
                type="submit"
                className="px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-sm shadow-md transition-all"
              >
                Simpan Kategori
              </button>
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
