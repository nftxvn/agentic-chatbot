import client from './client'

export const apiKeysApi = {
  async list() {
    const { data } = await client.get('/api/api-keys')
    return data
  },

  async create(name) {
    const { data } = await client.post('/api/api-keys', { name })
    return data
  },

  async toggle(id) {
    const { data } = await client.patch(`/api/api-keys/${id}/toggle`)
    return data
  },

  async delete(id) {
    const { data } = await client.delete(`/api/api-keys/${id}`)
    return data
  },
}
