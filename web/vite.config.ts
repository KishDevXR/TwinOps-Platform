import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api/v1/telemetry': 'http://127.0.0.1:8001',
      // per-asset sub-resources served by other services; must come before '/api/v1/assets'
      '^/api/v1/assets/[^/]+/telemetry': 'http://127.0.0.1:8001',
      '^/api/v1/assets/[^/]+/(twin|playback)': 'http://127.0.0.1:8003',
      '/api/v1/assets': 'http://127.0.0.1:8002',
      '/api/v1/tree': 'http://127.0.0.1:8002',
      '/api/v1/types': 'http://127.0.0.1:8002',
      '/api/v1/relations': 'http://127.0.0.1:8002',
      '/api/v1/tags': 'http://127.0.0.1:8002',
      '/api/v1/twins': 'http://127.0.0.1:8003',
      '/api/v1/sites': 'http://127.0.0.1:8003',
      '/api/v1/simulations': 'http://127.0.0.1:8003',
      '/api/v1/playback': 'http://127.0.0.1:8003',
      '/api/v1/alarms': 'http://127.0.0.1:8004',
      '/api/v1/work-orders': 'http://127.0.0.1:8005',
      '/api/v1/pm-plans': 'http://127.0.0.1:8005',
      '/api/v1/parts': 'http://127.0.0.1:8005',
      '/api/v1/maintenance': 'http://127.0.0.1:8005',
      '/api/v1/analytics': 'http://127.0.0.1:8006',
      '/api/v1/copilot': 'http://127.0.0.1:8007',
      '/api': 'http://127.0.0.1:8003',
      '/ws': {
        target: 'ws://127.0.0.1:8003',
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
  },
})
