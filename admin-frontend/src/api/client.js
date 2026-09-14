import axios from 'axios'

/**
 * Axios instance untuk berkomunikasi dengan Laravel API.
 *
 * Menggunakan Vite proxy, sehingga semua request ke /api
 * secara otomatis diteruskan ke http://localhost:8000
 * tanpa masalah CORS di development.
 */
const client = axios.create({
  baseURL: '/',
  withCredentials: true,          // kirim cookie session Sanctum
  headers: {
    'Content-Type': 'application/json',
    'Accept':       'application/json',
    'X-Requested-With': 'XMLHttpRequest', // diperlukan Sanctum SPA auth
  },
})

/**
 * Ambil CSRF cookie dari Sanctum sebelum request mutasi pertama.
 * Axios secara otomatis menyertakan X-XSRF-TOKEN dari cookie
 * ini pada setiap request selanjutnya.
 */
export async function initCsrf() {
  await client.get('/sanctum/csrf-cookie')
}

/**
 * Response interceptor — normalisasi error.
 */
client.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || ''
    const isAuthCheck = url.includes('/api/auth/user')
    const isAuthPage =
      window.location.pathname.startsWith('/login') ||
      window.location.pathname.startsWith('/forgot-password') ||
      window.location.pathname.startsWith('/reset-password')

    // Jika 401 pada request biasa (sesi habis saat sedang aktif), redirect ke login
    if (error.response?.status === 401 && !isAuthCheck && !isAuthPage) {
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
