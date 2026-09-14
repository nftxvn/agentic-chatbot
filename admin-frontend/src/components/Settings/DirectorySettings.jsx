import { useState, useEffect } from 'react'
import ReactDOM from 'react-dom'
import {
  getDirectories,
  createDirectory,
  updateDirectory,
  toggleDirectory,
  deleteDirectory,
} from '../../api/fastPaths'
import { addAppNotification } from '../../utils/notifications'
import { InfoTooltip } from '../UI/InfoTooltip'

export function DirectorySettings() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [editingItem, setEditingItem] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [deleteConfirmId, setDeleteConfirmId] = useState(null)

  const [form, setForm] = useState({
    nama_bidang: '',
    keywords: '',
    lokasi: 'Gedung C Lantai 3 Balai Kota Banda Aceh',
    email: '',
    layanan_utama: '',
    daftar_tugas: '',
    jam_operasional: 'Senin - Jumat (08:00 - 16:45 WIB)',
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
      const res = await getDirectories()
      if (res?.data) {
        setItems(res.data)
      }
    } catch (err) {
      console.error('Gagal memuat direktori:', err)
      addAppNotification({
        title: 'Direktori Error',
        message: 'Gagal memuat data direktori unit kerja dari basis data.',
        type: 'system',
      })
    } finally {
      setLoading(false)
    }
  }

  function handleOpenModal(item = null) {
    if (item) {
      setEditingItem(item)
      const tasksStr = Array.isArray(item.daftar_tugas)
        ? item.daftar_tugas.join('\n')
        : item.daftar_tugas || ''

      setForm({
        nama_bidang: item.nama_bidang || '',
        keywords: item.keywords || '',
        lokasi: item.lokasi || 'Gedung C Lantai 3 Balai Kota Banda Aceh',
        email: item.email || '',
        layanan_utama: item.layanan_utama || '',
        daftar_tugas: tasksStr,
        jam_operasional: item.jam_operasional || 'Senin - Jumat (08:00 - 16:45 WIB)',
        is_active: Boolean(item.is_active),
        sort_order: item.sort_order || 0,
      })
    } else {
      setEditingItem(null)
      setForm({
        nama_bidang: '',
        keywords: '',
        lokasi: 'Gedung C Lantai 3 Balai Kota Banda Aceh',
        email: '',
        layanan_utama: '',
        daftar_tugas: '',
        jam_operasional: 'Senin - Jumat (08:00 - 16:45 WIB)',
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
    if (!form.nama_bidang.trim() || !form.keywords.trim() || !form.email.trim()) {
      addAppNotification({
        title: 'Validasi Gagal',
        message: 'Mohon lengkapi nama bidang, kata kunci, dan email.',
        type: 'system',
      })
      return
    }

    try {
      setSubmitting(true)
      if (editingItem) {
        await updateDirectory(editingItem.id, form)
        addAppNotification({
          title: 'Direktori Diperbarui',
          message: `Data "${form.nama_bidang}" berhasil disimpan.`,
          type: 'system',
        })
      } else {
        await createDirectory(form)
        addAppNotification({
          title: 'Direktori Ditambahkan',
          message: `Bidang "${form.nama_bidang}" berhasil ditambahkan.`,
          type: 'system',
        })
      }
      handleCloseModal()
      fetchItems()
    } catch (err) {
      console.error('Gagal menyimpan direktori:', err)
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
      await toggleDirectory(id)
      setItems((prev) =>
        prev.map((it) => (it.id === id ? { ...it, is_active: !it.is_active } : it))
      )
      addAppNotification({
        title: 'Status Diperbarui',
        message: 'Status direktori bidang berhasil diubah.',
        type: 'system',
      })
    } catch (err) {
      console.error('Gagal mengubah status:', err)
    }
  }

  async function handleDelete(id) {
    try {
      await deleteDirectory(id)
      setItems((prev) => prev.filter((it) => it.id !== id))
      setDeleteConfirmId(null)
      addAppNotification({
        title: 'Direktori Dihapus',
        message: 'Data direktori bidang berhasil dihapus.',
        type: 'system',
      })
    } catch (err) {
      console.error('Gagal menghapus:', err)
    }
  }

  const filteredItems = items.filter((it) => {
    const q = search.toLowerCase()
    return (
      !q ||
      it.nama_bidang.toLowerCase().includes(q) ||
      it.keywords.toLowerCase().includes(q) ||
      it.layanan_utama.toLowerCase().includes(q) ||
      it.email.toLowerCase().includes(q)
    )
  })

  return (
    <div className="space-y-4">
      {/* Header Info & Actions */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[var(--bg-input)] p-3.5 rounded-lg border border-[var(--border-color)]">
        <div>
          <h3 className="text-xs font-bold text-[var(--text-primary)] flex items-center">
            <span>Direktori Unit Kerja, Bidang & Kontak Layanan</span>
            <InfoTooltip content="Basis data direktori bidang dan kontak unit kerja yang digunakan bot untuk memberikan arahan rujukan dinas secara akurat." />
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
          Tambah Unit / Bidang
        </button>
      </div>

      {/* Search Input */}
      <div className="relative">
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Cari nama bidang, email, kata kunci..."
          className="w-full pl-7 pr-3 py-1.5 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-[var(--brand-primary)]"
        />
        <svg className="w-3.5 h-3.5 absolute left-2 top-2.5 text-[var(--text-muted)]" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
        </svg>
      </div>

      {/* Directory Cards */}
      {loading ? (
        <div className="p-8 text-center text-xs text-[var(--text-muted)]">
          Memuat direktori bidang dari basis data...
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="p-8 text-center border border-dashed border-[var(--border-color)] rounded-xl text-xs text-[var(--text-muted)] space-y-2">
          <p>Belum ada data unit kerja yang sesuai.</p>
          <button
            type="button"
            onClick={() => handleOpenModal()}
            className="text-[var(--brand-primary)] hover:underline font-medium"
          >
            + Tambahkan unit kerja baru
          </button>
        </div>
      ) : (
        <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
          {filteredItems.map((item) => {
            const taskList = Array.isArray(item.daftar_tugas)
              ? item.daftar_tugas
              : typeof item.daftar_tugas === 'string'
              ? item.daftar_tugas.split('\n').filter(Boolean)
              : []

            return (
              <div
                key={item.id}
                className={`p-4 rounded-xl border transition-all ${
                  item.is_active
                    ? 'bg-[var(--bg-card)] border-[var(--border-color)] shadow-xs hover:border-[var(--brand-primary)]'
                    : 'bg-[var(--bg-input)] border-[var(--border-color)] opacity-60'
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-2 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h4 className="text-xs font-bold text-[var(--text-primary)]">
                        {item.nama_bidang}
                      </h4>
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-[var(--bg-input)] text-[var(--brand-primary)] border border-[var(--border-color)]">
                        {item.layanan_utama}
                      </span>
                      {!item.is_active && (
                        <span className="text-[10px] font-semibold text-[var(--red-color)] bg-[var(--bg-input)] border border-[var(--border-color)] px-1.5 py-0.5 rounded">
                          Nonaktif
                        </span>
                      )}
                    </div>

                    {/* Meta info tags */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-xs text-[var(--text-secondary)]">
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="text-[10px] font-semibold text-[var(--text-muted)]">Lokasi:</span>
                        <span className="truncate">{item.lokasi}</span>
                      </div>
                      <div className="flex items-center gap-1.5 truncate">
                        <span className="text-[10px] font-semibold text-[var(--text-muted)]">Email:</span>
                        <span className="font-mono text-[11px] text-[var(--brand-primary)] truncate">{item.email}</span>
                      </div>
                    </div>

                    {/* Keywords tags */}
                    <div className="flex items-center gap-1 text-xs flex-wrap">
                      <span className="text-[10px] text-[var(--text-muted)]">Pemicu:</span>
                      {item.keywords.split(',').slice(0, 5).map((kw, i) => (
                        <span
                          key={i}
                          className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[var(--bg-input)] text-[var(--text-muted)] border border-[var(--border-color)]"
                        >
                          {kw.trim()}
                        </span>
                      ))}
                    </div>

                    {/* Task list preview */}
                    {taskList.length > 0 && (
                      <div className="bg-[var(--bg-input)] p-2.5 rounded-lg border border-[var(--border-color)] space-y-1">
                        <span className="text-[10px] font-bold text-[var(--text-muted)] uppercase tracking-wider block">
                          Lingkup Tugas & Layanan:
                        </span>
                        <ul className="text-xs text-[var(--text-secondary)] space-y-0.5 list-disc list-inside">
                          {taskList.slice(0, 3).map((t, idx) => (
                            <li key={idx} className="truncate">{t}</li>
                          ))}
                          {taskList.length > 3 && (
                            <li className="text-[10px] text-[var(--text-muted)] list-none font-medium">
                              +{taskList.length - 3} tugas lainnya
                            </li>
                          )}
                        </ul>
                      </div>
                    )}
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

      {/* MODAL FORM: TAMBAH / EDIT DIREKTORI (PORTAL KE DOCUMENT.BODY) */}
      {isModalOpen &&
        ReactDOM.createPortal(
          <div className="fixed inset-0 z-[99999] flex items-center justify-center p-4 sm:p-6 bg-black/75 backdrop-blur-sm animate-fade-in">
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl w-full max-w-lg shadow-2xl animate-scale-up flex flex-col max-h-[90vh]">
              {/* Modal Header */}
              <div className="px-5 py-4 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-card)] rounded-t-2xl shrink-0">
                <h3 className="text-sm font-bold text-[var(--text-primary)]">
                  {editingItem ? 'Edit Unit / Bidang' : 'Tambah Unit Kerja / Bidang Baru'}
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
                {/* Nama Bidang */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text-primary)]">
                    Nama Unit / Bidang <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.nama_bidang}
                    onChange={(e) => setForm({ ...form, nama_bidang: e.target.value })}
                    placeholder="Contoh: Bidang Tata Kelola E-Government"
                    required
                    className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                  />
                </div>

                {/* Kata Kunci */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text-primary)]">
                    Kata Kunci Pemicu (Pisahkan koma) <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={form.keywords}
                    onChange={(e) => setForm({ ...form, keywords: e.target.value })}
                    placeholder="Contoh: egov, domain, hosting, vps, server, spbe"
                    required
                    className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                  />
                </div>

                {/* Layanan Utama & Email */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-primary)]">
                      Layanan Unggulan / Utama <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={form.layanan_utama}
                      onChange={(e) => setForm({ ...form, layanan_utama: e.target.value })}
                      placeholder="Contoh: Helpdesk SPBE & Domain"
                      required
                      className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-primary)]">
                      Email Resmi <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="email"
                      value={form.email}
                      onChange={(e) => setForm({ ...form, email: e.target.value })}
                      placeholder="egov@bandaacehkota.go.id"
                      required
                      className="w-full px-3 py-2 text-xs font-mono rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                    />
                  </div>
                </div>

                {/* Lokasi & Jam Operasional */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-primary)]">
                      Lokasi Kantor / Ruangan
                    </label>
                    <input
                      type="text"
                      value={form.lokasi}
                      onChange={(e) => setForm({ ...form, lokasi: e.target.value })}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-[var(--text-primary)]">
                      Jam Operasional
                    </label>
                    <input
                      type="text"
                      value={form.jam_operasional}
                      onChange={(e) => setForm({ ...form, jam_operasional: e.target.value })}
                      className="w-full px-3 py-2 text-xs rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500"
                    />
                  </div>
                </div>

                {/* Daftar Tugas */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-[var(--text-primary)]">
                    Daftar Tugas & Pelayanan (Satu baris per poin tugas)
                  </label>
                  <textarea
                    value={form.daftar_tugas}
                    onChange={(e) => setForm({ ...form, daftar_tugas: e.target.value })}
                    rows={4}
                    placeholder="Pengelolaan domain dan hosting&#10;Pengembangan aplikasi SPBE&#10;Jaringan intra pemerintah"
                    className="w-full p-2.5 text-xs font-mono leading-relaxed rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] text-[var(--text-primary)] focus:outline-none focus:border-sky-500 resize-y"
                  />
                </div>

                {/* Status Aktif */}
                <div className="flex items-center gap-2 pt-1">
                  <input
                    type="checkbox"
                    id="dir_active_check"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    className="rounded border-[var(--border-color)] text-sky-600 focus:ring-sky-500 cursor-pointer"
                  />
                  <label htmlFor="dir_active_check" className="text-xs font-medium text-[var(--text-primary)] cursor-pointer">
                    Aktifkan unit kerja ini di sistem direktori bot
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
