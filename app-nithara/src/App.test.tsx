import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import { IconSprite } from './components/IconSprite'
import './i18n'

function renderApp() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <IconSprite />
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

test('renders the four-tab shell with English labels by default', () => {
  renderApp()
  expect(screen.getByText('Home')).toBeInTheDocument()
  expect(screen.getByText('Poojas')).toBeInTheDocument()
  expect(screen.getByText('Astro')).toBeInTheDocument() // nav_astro
  expect(screen.getByText('You')).toBeInTheDocument() // nav_profile
})
