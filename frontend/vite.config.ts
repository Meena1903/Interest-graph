import { defineConfig } from 'vite'
import react from '@vitejs/vite-plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true
  }
})
