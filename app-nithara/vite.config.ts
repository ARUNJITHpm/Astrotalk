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
      workbox: {
        // The SW is registered at the root scope, and Workbox's navigation
        // fallback would otherwise answer EVERY in-scope navigation out of the
        // precached index.html — silently shadowing the server-rendered pages
        // this same origin serves (/prototype, /admin, /console, /whatsapp,
        // /a/{handle}/*, /docs). An allowlist, not a denylist: only the routes
        // react-router actually knows (see App.tsx) get the shell, so any page
        // added to app/main.py later keeps working without touching this file.
        navigateFallbackAllowlist: [
          /^\/$/,
          /^\/poojas\/?$/,
          /^\/astro\/?$/,
          /^\/profile\/?$/,
        ],
      },
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
