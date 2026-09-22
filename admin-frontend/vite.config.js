import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  const aiUrl = env.VITE_AI_URL || process.env.VITE_AI_URL || 'http://localhost:8080'
  const laravelUrl = env.VITE_LARAVEL_URL || process.env.VITE_LARAVEL_URL || 'http://localhost:8000'
  const token =
    env.INTERNAL_API_TOKEN ||
    env.AI_SERVICE_TOKEN ||
    process.env.INTERNAL_API_TOKEN ||
    process.env.AI_SERVICE_TOKEN ||
    'dev-internal-token-secret-1234567890'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: '0.0.0.0',
      port: 5173,
      allowedHosts: true,
      watch: {
        usePolling: true,
      },
      proxy: {
        // Proxy AI requests ke Python AI microservice (port 8080 / container python-ai)
        '/api/ai': {
          target: aiUrl,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api\/ai/, '/api'),
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
        // Proxy API requests ke Laravel backend (port 8000 / container laravel-backend)
        '/api': {
          target: laravelUrl,
          changeOrigin: true,
        },
        // Proxy Sanctum CSRF cookie endpoint
        '/sanctum': {
          target: laravelUrl,
          changeOrigin: true,
        },
      },
    },
  }
})
