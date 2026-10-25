import { useState, useEffect } from 'react'
import {
  getDirectories,
  createDirectory,
  updateDirectory,
  toggleDirectory,
  deleteDirectory,
} from '../../api/fastPaths'
import { addAppNotification } from '../../utils/notifications'

/** Workflow form DirectorySettings; JSX dan portal tetap dimiliki komponen. */
export function useDirectorySettings() {
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

  return {
    items,
    loading,
    search,
    setSearch,
    isModalOpen,
    editingItem,
    submitting,
    deleteConfirmId,
    setDeleteConfirmId,
    form,
    setForm,
    filteredItems,
    handleOpenModal,
    handleCloseModal,
    handleSubmit,
    handleToggle,
    handleDelete,
  }
}
