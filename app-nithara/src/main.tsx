import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import 'leaflet/dist/leaflet.css'
import './styles/globals.css'
import './i18n'
import App from './App'
import { IconSprite } from './components/IconSprite'
import { ensureSession, refreshSession } from './lib/auth'
import { setReauthHandler } from './api/client'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } },
})

function mount() {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <IconSprite />
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>,
  )
}

// A 401 mid-session (the 47h token expired) transparently re-mints and retries.
setReauthHandler(refreshSession)

// Mint the anon session before mounting so authed queries have a token — but
// never let startup hang on it: a stalled network (captive portal, offline)
// would otherwise leave the user staring at a blank page. Race a short timeout;
// public screens work without a token, and the 401 retry covers the rest.
const withTimeout = (p: Promise<unknown>, ms: number) =>
  Promise.race([p, new Promise((resolve) => setTimeout(resolve, ms))])

withTimeout(ensureSession().catch(() => undefined), 3000).finally(mount)
