import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// One codebase → web (this dev/preview server + `vite build` to dist/) and,
// wrapped by Capacitor, Android/iOS. The service worker makes it installable.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Nithara — your temple, in your pocket',
        short_name: 'Nithara',
        description: 'Your Malayalam temple companion.',
        theme_color: '#FFFFFF',
        background_color: '#E9EDF2',
        display: 'standalone',
        start_url: '/',
        icons: [],
      },
    }),
  ],
  server: { port: 5173 },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
