import client from './client'

export const documentsApi = {
  async list(page = 1) {
    const { data } = await client.get('/api/documents', { params: { page } })
    return data
  },

  async get(id) {
    const { data } = await client.get(`/api/documents/${id}`)
    return data
  },

  async getChunks(id) {
    const { data } = await client.get(`/api/documents/${id}/chunks`)
    return data
  },

  async upload(title, pdfFile) {
    const formData = new FormData()
    formData.append('title', title)
    formData.append('pdf_file', pdfFile)
    const { data } = await client.post('/api/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async replace(id, pdfFile) {
    const formData = new FormData()
    formData.append('pdf_file', pdfFile)
    const { data } = await client.post(`/api/documents/${id}/replace`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return data
  },

  async destroy(id) {
    const { data } = await client.delete(`/api/documents/${id}`)
    return data
  },

  /** URL PDF untuk dipakai sebagai src iframe — sudah auth via cookie. */
  pdfUrl(id) {
    return `/api/documents/${id}/pdf`
  },
}
