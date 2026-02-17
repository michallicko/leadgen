import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': `http://localhost:${process.env.VITE_API_PORT ?? '5001'}`,
      '/webhook': process.env.VITE_WEBHOOK_URL || 'https://n8n.visionvolve.com',
    },
  },
})
