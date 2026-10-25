import { useState, useEffect } from 'react'
import {
  getFastPaths,
  createFastPath,
  updateFastPath,
  toggleFastPath,
  deleteFastPath,
} from '../../api/fastPaths'
import { addAppNotification } from '../../utils/notifications'

/** Workflow form FastPathSettings; JSX dan portal tetap dimiliki komponen. */
export function useFastPathSettings() {
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


  return {
    items,
    loading,
    search,
    setSearch,
    selectedCategory,
    setSelectedCategory,
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
