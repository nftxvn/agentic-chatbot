import { useState, useEffect } from 'react'
import ReactDOM from 'react-dom'
import {
  getFastPaths,
  createFastPath,
  updateFastPath,
  toggleFastPath,
  deleteFastPath,
} from '../../api/fastPaths'
import { addAppNotification } from '../../utils/notifications'
import { InfoTooltip } from '../UI/InfoTooltip'

export function FastPathSettings() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)

  const [form, setForm] = useState({
    category: 'general',
    title: '',
    keywords: '',
    response_text: '',
    is_active: true,
    sort_order: 0,
  })

  useEffect(() => {
    fetchItems()
  }, [])

  // Lock body scroll when modal is open to prevent bleeding and background scrolling
  useEffect(() => {
    if (isModalOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = 'unset'
    }
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [isModalOpen])

  async function fetchItems() {
    try {
      setLoading(true)
      const res = await getFastPaths()
      if (res?.data) {
        setItems(res.data)
      }
    } catch (err) {
      console.error('Gagal memuat Fast-Paths:', err)
      addAppNotification({
        title: 'Fast-Path Error',
        message: 'Gagal memuat data Fast-Path dari basis data.',
        type: 'system',
      })
    } finally {
      setLoading(false)
    }
  }

  function handleOpenModal(item = null) {
    if (item) {
      setEditingItem(item)
      setForm({
        category: item.category || 'general',
        title: item.title || '',
        keywords: item.keywords || '',
        response_text: item.response_text || '',
        is_active: Boolean(item.is_active),
        sort_order: item.sort_order || 0,
      })
    } else {
      setEditingItem(null)
      setForm({
        category: selectedCategory !== 'all' ? selectedCategory : 'general',
        title: '',
        keywords: '',
        response_text: '',
        is_active: true,
        sort_order: items.length + 1,
      })
    }
    setIsModalOpen(true)
  }

  function handleCloseModal() {
    setIsModalOpen(false)
    setEditingItem(null)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.title.trim() || !form.keywords.trim() || !form.response_text.trim()) {
      addAppNotification({
        title: 'Validasi Gagal',
        message: 'Mohon lengkapi judul, kata kunci, dan teks respons.',
        type: 'system',
      })
      return
    }

    try {
      setSubmitting(true)
      if (editingItem) {
        await updateFastPath(editingItem.id, form)
        addAppNotification({
          title: 'Fast-Path Diperbarui',
          message: `Aturan "${form.title}" berhasil disimpan.`,
          type: 'system',
        })
      } else {
        await createFastPath(form)
        addAppNotification({
          title: 'Fast-Path Ditambahkan',
          message: `Aturan "${form.title}" berhasil ditambahkan.`,
          type: 'system',
        })
      }
      handleCloseModal()
      fetchItems()
    } catch (err) {
      console.error('Gagal menyimpan Fast-Path:', err)
      addAppNotification({
        title: 'Penyimpanan Gagal',
        message: err.response?.data?.message || 'Terjadi kesalahan saat menyimpan data.',
        type: 'system',
      })
    } finally {
      setSubmitting(false)
    }
  }

  async function handleToggle(id) {
    try {
      await toggleFastPath(id)
      setItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, is_active: !it.is_active } : it))
      )
      addAppNotification({
        title: 'Status Diperbarui',
        message: `Status Fast-Path berhasil diubah.`,
        type: 'system',
      })
    } catch (err) {
      console.error('Gagal mengubah status:', err)
    }
  }

  async function handleDelete(id) {
    try {
      await deleteFastPath(id)
      setItems((prev) => prev.filter((it) => it.id !== id))
      setDeleteConfirmId(null)
      addAppNotification({
        title: 'Fast-Path Dihapus',
        message: 'Aturan Fast-Path berhasil dihapus.',
        type: 'system',
      })
    } catch (err) {
      console.error('Gagal menghapus:', err)
    }
  }

  const filteredItems = items.filter((it) => {
    const matchCat = selectedCategory === 'all' || it.category === selectedCategory
    const q = search.toLowerCase()
    const matchSearch =
      !q ||
      it.title.toLowerCase().includes(q) ||
      it.keywords.toLowerCase().includes(q) ||
      it.response_text.toLowerCase().includes(q)
    return matchCat && matchSearch
  })

  const categoryLabels = {
    general: { label: 'General / Profil', badge: 'bg-[var(--bg-input)] text-[var(--action-green)] border-[var(--border-color)]' },
    layanan: { label: 'Layanan & Helpdesk', badge: 'bg-[var(--bg-input)] text-[var(--brand-primary)] border-[var(--border-color)]' },
    sop: { label: 'SOP & Prosedur', badge: 'bg-[var(--bg-input)] text-[var(--yellow-color)] border-[var(--border-color)]' },
    faq: { label: 'FAQ Tambahan', badge: 'bg-[var(--bg-input)] text-[var(--text-secondary)] border-[var(--border-color)]' },
  }

  return (
    <div className="space-y-4">
      {/* Header Info & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[var(--bg-input)] p-3.5 rounded-lg border border-[var(--border-color)]">
        <div>
          <h3 className="text-xs font-bold text-[var(--text-primary)] flex items-center">
            <span>Manajemen Fast-Path & FAQ Dinamis</span>
            <InfoTooltip content="Aturan pencocokan kata kunci untuk memberikan respons instan (< 0.05 detik) pada pertanyaan berulang tanpa membebani model LLM." />
          </h3>
        </div>
        <button
          type="button"
          onClick={() => handleOpenModal()}
          className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-[var(--brand-primary)] hover:bg-[var(--brand-hover)] text-white transition-all shadow-xs flex items-center gap-1.5 self-start sm:self-auto cursor-pointer"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Tambah Fast-Path
        </button>
      </div>

      {/* Filter & Search Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
        <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0 scrollbar-none">
          {[
            { id: 'all', label: 'Semua Kategori' },
            { id: 'general', label: 'General' },
            { id: 'layanan', label: 'Layanan' },
            { id: 'sop', label: 'SOP' },
            { id: 'faq', label: 'FAQ' },
          ].map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelectedCategory(cat.id)}
              className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all cursor-pointer whitespace-nowrap ${
                selectedCategory === cat.id
                  ? 'bg-[var(--brand-primary)] text-white font-semibold'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] bg-[var(--bg-input)]'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <div className="relative min-w-[200px]">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cari judul, kata kunci..."
            className="w-full pl-7 pr-3 py-1 text-xs rounded-md border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--brand-primary)]"
          />
          <svg className="w-3.5 h-3.5 absolute left-2 top-2 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
          </svg>
        </div>
      </div>

      {/* Items List */}
      {loading ? (
        <div className="p-8 text-center text-xs text-[var(--text-muted)]">
          Memuat data Fast-Path dari basis data...
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="p-8 text-center border border-dashed border-[var(--border-color)] rounded-xl text-xs text-[var(--text-muted)] space-y-2">
          <p>Belum ada aturan Fast-Path yang cocok dengan filter pencarian.</p>
          <button
            type="button"
            onClick={() => handleOpenModal()}
            className="text-[var(--brand-primary)] hover:underline font-medium"
          >
            + Buat aturan Fast-Path baru
          </button>
        </div>
      ) : (
        <div className="space-y-2.5 max-h-[520px] overflow-y-auto pr-1">
          {filteredItems.map((item) => {
            const catMeta = categoryLabels[item.category] || categoryLabels.general
            return (
              <div
                key={item.id}
                className={`p-3.5 rounded-lg border transition-all ${
                  item.is_active
                    ? 'bg-[var(--bg-card)] border-[var(--border-color)] shadow-xs hover:border-[var(--brand-primary)]'
                    : 'bg-[var(--bg-input)] border-[var(--border-color)] opacity-60'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[10px] uppercase font-bold px-1.5 py-0.5 rounded border ${catMeta.badge}`}>
                        {catMeta.label}
                      </span>
                      <h4 className="text-xs font-bold text-[var(--text-primary)] truncate">
                        {item.title}
                      </h4>
                      {!item.is_active && (
                        <span className="text-[10px] font-semibold text-[var(--red-color)] bg-[var(--bg-input)] border border-[var(--border-color)] px-1.5 py-0.5 rounded">
                          Nonaktif
                        </span>
                      )}
                    </div>

                    {/* Keywords preview */}
                    <div className="flex items-center gap-1.5 text-xs text-[var(--text-muted)] flex-wrap">
                      <span className="text-[10px] font-mono text-[var(--text-muted)]">Pemicu:</span>
                      {item.keywords.split(',').slice(0, 4).map((kw, i) => (
                        <span
                          key={i}
                          className="text-[11px] font-mono px-1.5 py-0.2 rounded bg-[var(--bg-input)] text-[var(--text-secondary)] border border-[var(--border-color)]"
                        >
                          {kw.trim()}
                        </span>
                      ))}
                      {item.keywords.split(',').length > 4 && (
                        <span className="text-[10px] text-[var(--text-muted)]">
                          +{item.keywords.split(',').length - 4} lainnya
                        </span>
                      )}
                    </div>

                    {/* Response snippet */}
                    <p className="text-xs text-[var(--text-secondary)] line-clamp-2 bg-[var(--bg-input)] p-2 rounded border border-[var(--border-color)] font-mono text-[11px]">
                      {item.response_text}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0 pt-0.5">
                    <button
                      type="button"
                      onClick={() => handleToggle(item.id)}
                      className={`p-1.5 rounded-md text-xs font-medium transition-colors cursor-pointer ${
                        item.is_active
                          ? 'text-[var(--action-green)] hover:bg-[var(--bg-input)]'
                          : 'text-[var(--text-muted)] hover:bg-[var(--bg-input)]'
                      }`}
                      title={item.is_active ? 'Nonaktifkan' : 'Aktifkan'}
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5.636 18.364a9 9 0 010-12.728m12.728 0a9 9 0 010 12.728m-9.9-2.829a5 5 0 010-7.07m7.072 0a5 5 0 010 7.07M12 9v4" />
                      </svg>
                    </button>

                    <button
                      type="button"
                      onClick={() => handleOpenModal(item)}
                      className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--brand-primary)] hover:bg-[var(--bg-input)] transition-colors cursor-pointer"
                      title="Edit"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                      </svg>
                    </button>

                    {deleteConfirmId === item.id ? (
                      <div className="flex items-center gap-1 bg-[var(--bg-input)] p-0.5 rounded-md border border-[var(--border-color)]">
                        <button
                          type="button"
                          onClick={() => handleDelete(item.id)}
                          className="px-1.5 py-0.5 text-[10px] font-bold text-[var(--red-color)] hover:bg-[var(--bg-card)] rounded cursor-pointer"
                        >
                          Hapus?
                        </button>
                        <button
                          type="button"
                          onClick={() => setDeleteConfirmId(null)}
                          className="px-1 py-0.5 text-[10px] text-[var(--text-muted)] hover:bg-[var(--bg-card)] rounded cursor-pointer"
                        >
                          Batal
                        </button>
                      </div>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setDeleteConfirmId(item.id)}
                        className="p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--red-color)] hover:bg-[var(--bg-input)] transition-colors cursor-pointer"
                        title="Hapus"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* MODAL FORM: TAMBAH / EDIT FAST-PATH (PORTAL KE DOCUMENT.BODY) */}
      {isModalOpen &&
        ReactDOM.createPortal(
          <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 sm:p-6 bg-black/75 backdrop-blur-sm animate-fade-in">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl w-full max-w-lg shadow-2xl animate-scale-up flex flex-col max-h-[90vh]">
              {/* Modal Header */}
              <div className="px-5 py-4 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-card)] rounded-t-2xl shrink-0">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  {editingItem ? 'Edit Aturan Fast-Path' : 'Tambah Aturan Fast-Path Baru'}
                </h3>
                <button
                  type="button"
                  onClick={handleCloseModal}
                  className="text-[var(--text-muted)] hover:text-[var(--text-primary)] p-1.5 rounded-lg hover:bg-[var(--bg-input)] transition-colors cursor-pointer"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Modal Form */}
              <form onSubmit={handleSubmit} className="p-5 space-y-4 overflow-y-auto flex-1 bg-[var(--bg-card)]">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {/* Kategori */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-primary)]">
                      Kategori Pengetahuan
                    </label>
                    <select
                      value={form.category}
                      onChange={(e) => setForm({ ...form, category: e.target.value })}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                    >
                      <option value="general">General / Profil Instansi</option>
                      <option value="layanan">Layanan & Helpdesk</option>
                      <option value="sop">SOP & Prosedur</option>
                      <option value="faq">FAQ Tambahan</option>
                    </select>
                  </div>

                  {/* Urutan */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-primary)]">
                      Prioritas Urutan
                    </label>
                    <input
                      type="number"
                      value={form.sort_order}
                      onChange={(e) => setForm({ ...form, sort_order: parseInt(e.target.value) || 0 })}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                    />
                  </div>
                </div>

                {/* Judul */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text-primary)]">
                    Judul / Topik Aturan <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.title}
                    onChange={(e) => setForm({ ...form, title: e.target.value })}
                    placeholder="Contoh: Profil Kepala Dinas, Alamat Kantor, Magang Mahasiswa"
                    required
                    className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                  />
                </div>

                {/* Kata Kunci */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text-primary)]">
                    Kata Kunci Pemicu (Pisahkan dengan koma) <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.keywords}
                    onChange={(e) => setForm({ ...form, keywords: e.target.value })}
                    placeholder="Contoh: kepala dinas, siapa kadis, pimpinan kominfo"
                    required
                    className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                  />
                  <p className="text-[10px] text-[var(--text-muted)]">
                    Jika pengguna mengetikkan salah satu kata di atas, bot akan langsung mengirim respons di bawah.
                  </p>
                </div>

                {/* Teks Respons */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text-primary)]">
                    Teks Jawaban / Format Markdown <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    value={form.response_text}
                    onChange={(e) => setForm({ ...form, response_text: e.target.value })}
                    rows={5}
                    placeholder="Tuliskan teks jawaban resmi di sini (mendukung format Markdown tebal, miring, list poin)..."
                    required
                    className="w-full p-2.5 text-xs font-mono leading-relaxed rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 resize-y"
                  />
                </div>

                {/* Status Aktif */}
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="is_active_check"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    className="rounded border-[var(--border-color)] text-sky-600 focus:ring-sky-500 cursor-pointer"
                  />
                  <label htmlFor="is_active_check" className="text-xs font-medium text-[var(--text-primary)] cursor-pointer">
                    Aktifkan aturan Fast-Path ini sekarang
                  </label>
                </div>

                {/* Modal Buttons */}
                <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-[var(--border-color)] bg-[var(--bg-card)] rounded-b-2xl">
                  <button
                    type="button"
                    onClick={handleCloseModal}
                    className="px-4 py-2 text-xs font-medium rounded-xl border border-[var(--border-color)] text-[var(--text-secondary)] hover:bg-[var(--bg-input)] transition-colors cursor-pointer"
                  >
                    Batal
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-4 py-2 text-xs font-semibold rounded-xl bg-sky-600 hover:bg-sky-500 text-white transition-all shadow-xs disabled:opacity-50 cursor-pointer"
                  >
                    {submitting ? 'Menyimpan...' : editingItem ? 'Simpan Perubahan' : 'Tambahkan'}
                  </button>
                </div>
              </form>
            </div>
          </div>,
          document.body
        )}
    </div>
  )
}
