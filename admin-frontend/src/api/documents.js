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

  async upload(title, pdfFile, categoryId, onUploadProgress) {
    const formData = new FormData()
    formData.append('title', title)
    formData.append('pdf_file', pdfFile)
    if (categoryId) {
      formData.append('category_id', categoryId)
    }
    const { data } = await client.post('/api/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
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

  /** Batalkan proses ekstraksi (set status failed). */
  async cancel(id) {
    const { data } = await client.post(`/api/documents/${id}/cancel`)
    return data
  },

  /** Minta jeda ekstraksi di batas halaman (tidak merusak progress). */
  async pause(id) {
    const { data } = await client.post(`/api/documents/${id}/extraction/pause`)
    return data
  },

  /** Mulai atau lanjutkan ekstraksi bertahap. */
  async resume(id, maksHalaman = null) {
    const payload = maksHalaman ? { maks_halaman: maksHalaman } : {}
    const { data } = await client.post(`/api/documents/${id}/extraction`, payload)
    return data
  },

  async startExtraction(id, maksHalaman = null) {
    return this.resume(id, maksHalaman)
  },

  /** Ambil status dan kemajuan ekstraksi bertahap. */
  async getExtractionStatus(id) {
    const { data } = await client.get(`/api/documents/${id}/extraction`)
    return data
  },

  /** Ambil daftar teks halaman untuk editor koreksi manual. */
  async getPages(id, perluDiperiksa = false) {
    const { data } = await client.get(`/api/documents/${id}/pages`, {
      params: { perlu_diperiksa: perluDiperiksa ? 1 : 0 },
    })
    return data
  },

  /** Simpan koreksi teks satu halaman. */
  async savePageCorrection(id, pageNumber, text) {
    const { data } = await client.put(`/api/documents/${id}/pages/${pageNumber}`, { text })
    return data
  },

  /** Ambil ukuran dan orientasi semua halaman. */
  async getPageSizes(id) {
    const { data } = await client.get(`/api/documents/${id}/pages/dimensions`)
    return data
  },

  /** URL citra JPEG satu halaman untuk perbandingan dengan teks OCR. */
  pageImageUrl(id, pageNumber, zoom = 2.0) {
    return `/api/documents/${id}/pages/${pageNumber}/image?zoom=${zoom}`
  },

  /** Ambil pratinjau potongan induk dan anak dengan opsi kustom. */
  async getChunksPreview(id, params = {}) {
    const { data } = await client.post(`/api/documents/${id}/chunks/preview`, params)
    return data
  },

  /** Finalisasi dokumen: simpan potongan vektor ke ChromaDB dengan opsi kustom. */
  async saveToCorpus(id, params = {}) {
    const { data } = await client.post(`/api/documents/${id}/embed`, params)
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
