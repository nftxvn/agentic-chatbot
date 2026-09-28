import api from './client'

export const ticketsApi = {
  /**
   * Mengambil daftar tiket dengan filter & paginasi
   */
  list: async (params = {}) => {
    const res = await api.get('/api/tickets', { params })
    return res.data
  },

  /**
   * Mengambil statistik ringkasan tiket (open, in_progress, resolved, total)
   */
  getStats: async () => {
    const res = await api.get('/api/tickets/stats')
    return res.data
  },

  /**
   * Mengambil detail satu tiket beserta riwayat pesan
   */
  get: async (id) => {
    const res = await api.get(`/api/tickets/${id}`)
    return res.data
  },

  /**
   * Assign tiket ke admin saat ini
   */
  assign: async (id, adminId = null) => {
    const res = await api.post(`/api/tickets/${id}/assign`, { admin_id: adminId })
    return res.data
  },

  /**
   * Mengubah status tiket (open, in_progress, resolved, closed)
   */
  updateStatus: async (id, status) => {
    const res = await api.patch(`/api/tickets/${id}/status`, { status })
    return res.data
  },

  /**
   * Mengambil daftar pesan percakapan tiket
   */
  getMessages: async (id) => {
    const res = await api.get(`/api/tickets/${id}/messages`)
    return res.data
  },

  /**
   * Mengirim balasan petugas ke warga (dengan opsional lampiran file/gambar)
   */
  reply: async (id, message, file = null) => {
    if (file) {
      const formData = new FormData()
      formData.append('message', message || '')
      formData.append('file', file)
      const res = await api.post(`/api/tickets/${id}/messages`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })
      return res.data
    }

    const res = await api.post(`/api/tickets/${id}/messages`, { message })
    return res.data
  },
}

