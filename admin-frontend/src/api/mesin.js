import client from './client'

/**
 * Diagnostik mesin dari layanan Python AI.
 *
 * Lewat proxy `/api/ai` — proxy itulah yang menyisipkan INTERNAL_API_TOKEN,
 * karena endpoint ini terautentikasi (berbeda dari `/api/ai/health` yang publik).
 */
export const mesinApi = {
  async ambil() {
    const { data } = await client.get('/api/ai/health/mesin')
    return data
  },
}

export default mesinApi
