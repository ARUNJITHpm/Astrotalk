import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import { AuthProvider } from './lib/auth'
import './styles.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // A 401 clears the session and shows the login screen; a 403 is a settled
      // answer about this role. Retrying either just delays the truth.
      retry: (count, error) => {
        const status = (error as { status?: number })?.status
        if (status === 401 || status === 403) return false
        return count < 2
      },
    },
  },
})

// basename matches vite.config.ts `base`: FastAPI serves the console under
// /console/, so react-router must strip that prefix or every route 404s.
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename="/console">
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
