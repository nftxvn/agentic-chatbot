import client from './client'

export const chatLogsApi = {
  async list(params = {}) {
    const { data } = await client.get('/api/chat-logs', { params })
    return data
  },

  async analytics() {
    const { data } = await client.get('/api/chat-logs/analytics')
    return data
  },

  async delete(id) {
    const { data } = await client.delete(`/api/chat-logs/${id}`)
    return data
  },

  async purge() {
    const { data } = await client.delete('/api/chat-logs/purge')
    return data
  },
}
