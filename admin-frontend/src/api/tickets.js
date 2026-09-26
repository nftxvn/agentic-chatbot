import api from './client'

export const ticketsApi = {
  /**
   * Mengambil daftar tiket dengan filter & paginasi
   */
  list: async (params = {}) => {
    const res = await api.get('/tickets', { params })
    return res.data
  },

  /**
   * Mengambil statistik ringkasan tiket (open, in_progress, resolved, total)
   */
  getStats: async () => {
    const res = await api.get('/tickets/stats')
    return res.data
  },

  /**
   * Mengambil detail satu tiket beserta riwayat pesan
   */
  get: async (id) => {
    const res = await api.get(`/tickets/${id}`)
    return res.data
  },

  /**
   * Assign tiket ke admin saat ini
   */
  assign: async (id, adminId = null) => {
    const res = await api.post(`/tickets/${id}/assign`, { admin_id: adminId })
    return res.data
  },

  /**
   * Mengubah status tiket (open, in_progress, resolved, closed)
   */
  updateStatus: async (id, status) => {
    const res = await api.patch(`/tickets/${id}/status`, { status })
    return res.data
  },

  /**
   * Mengambil daftar pesan percakapan tiket
   */
  getMessages: async (id) => {
    const res = await api.get(`/tickets/${id}/messages`)
    return res.data
  },

  /**
   * Mengirim balasan petugas ke warga
   */
  reply: async (id, message) => {
    const res = await api.post(`/tickets/${id}/messages`, { message })
    return res.data
  },
}
