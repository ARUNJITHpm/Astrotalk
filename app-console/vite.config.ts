import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// The operator console. Deliberately NOT a PWA and not Capacitor-wrapped: it is
// a desktop tool for staff, so there is no service worker to shadow the pages
// this origin already serves, and no install prompt.
//
// `base: '/console-app/'` because the built assets are served from that path,
// not the root — the root belongs to app-nithara. Without it every asset URL in
// index.html would point at /assets/... and collide with the consumer app's.
export default defineConfig({
  plugins: [react()],
  base: '/console-app/',
  server: {
    port: 5174, // 5173 is app-nithara; both run at once during development
    proxy: {
      // Dev-only. In production the console is served by FastAPI on the same
      // origin, so the API base stays empty and no proxy is involved.
      '/admin': 'http://localhost:3000',
      '/temples': 'http://localhost:3000',
      '/astrologers': 'http://localhost:3000',
      '/bookings': 'http://localhost:3000',
      '/content': 'http://localhost:3000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
