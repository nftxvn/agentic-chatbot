import client, { initCsrf } from './client'

export const authApi = {
  /**
   * Ambil CSRF cookie lalu login.
   */
  async login(email, password, remember = false) {
    await initCsrf()
    const { data } = await client.post('/api/auth/login', { email, password, remember })
    return data
  },

  async logout() {
    const { data } = await client.post('/api/auth/logout')
    return data
  },

  async getUser() {
    const { data } = await client.get('/api/auth/user')
    return data
  },

  async forgotPassword(email) {
    await initCsrf()
    const { data } = await client.post('/api/auth/forgot-password', { email })
    return data
  },

  async resetPassword(token, email, password, password_confirmation) {
    await initCsrf()
    const { data } = await client.post('/api/auth/reset-password', {
      token, email, password, password_confirmation,
    })
    return data
  },
}
