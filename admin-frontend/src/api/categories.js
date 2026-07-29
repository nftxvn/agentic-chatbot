import client from './client'

export const categoriesApi = {
  async list() {
    const { data } = await client.get('/api/categories')
    return data
  },
  async create(payload) {
    const { data } = await client.post('/api/categories', payload)
    return data
  },
  async update(id, payload) {
    const { data } = await client.put(`/api/categories/${id}`, payload)
    return data
  },
  async destroy(id) {
    const { data } = await client.delete(`/api/categories/${id}`)
    return data
  },
  async ollamaTags() {
    const { data } = await client.get('/api/ai/docs/ollama/tags')
    return data
  },
  async testPrompt(payload) {
    const { data } = await client.post('/api/ai/docs/test-prompt', payload)
    return data
  }
}
