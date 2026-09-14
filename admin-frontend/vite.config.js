import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
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
        target: process.env.VITE_AI_URL || 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/ai/, '/api'),
        headers: {
          Authorization: `Bearer ${process.env.INTERNAL_API_TOKEN || process.env.AI_SERVICE_TOKEN || 'dev-internal-token-secret-1234567890'}`,
        },
      },
      // Proxy API requests ke Laravel backend (port 8000 / container laravel-backend)
      '/api': {
        target: process.env.VITE_LARAVEL_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
      // Proxy Sanctum CSRF cookie endpoint
      '/sanctum': {
        target: process.env.VITE_LARAVEL_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
