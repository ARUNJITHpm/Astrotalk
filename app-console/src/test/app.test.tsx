// The shell end to end: sign in, see only your sections, and be turned away
// from a URL you typed by hand.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import { AuthProvider } from '../lib/auth'
import type { Me } from '../lib/auth'

const OWNER: Me = { operator_id: null, roles: ['owner'], temple_ids: [], is_owner: true }
const CLERK: Me = {
  operator_id: 7,
  roles: ['temple_admin'],
  temple_ids: ['tsr-guruvayur'],
  is_owner: false,
}

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as Response
}

/** Answer /operators/me with `me`; everything else with an empty count. */
function stubApi(me: Me | null) {
  return vi.fn(async (url: string) => {
    if (String(url).includes('/admin/operators/me')) {
      return me
        ? jsonResponse(me)
        : jsonResponse({ detail: 'Invalid or missing admin credentials' }, 401)
    }
    if (String(url).includes('/admin/operators/login')) {
      return jsonResponse({ token: 'sess-abc' })
    }
    if (String(url).includes('/admin/login')) {
      return jsonResponse({ token: 'the-admin-token' })
    }
    return jsonResponse({ total: 0, items: [] })
  })
}

function renderAt(path: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  sessionStorage.clear()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('signed out', () => {
  it('shows the login screen and no navigation', async () => {
    vi.stubGlobal('fetch', stubApi(null))
    renderAt('/')
    expect(await screen.findByRole('heading', { name: 'Nithara Console' })).toBeVisible()
    expect(screen.queryByText('Dashboard')).not.toBeInTheDocument()
  })

  it('prefills neither field', async () => {
    // console.html hardcoded a personal email and admin.html printed the
    // password on screen. Neither carries over, and this test is the guard.
    vi.stubGlobal('fetch', stubApi(null))
    renderAt('/')
    const identifier = await screen.findByLabelText('Email or mobile')
    expect(identifier).toHaveValue('')
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('does not reveal that a deployment is unconfigured', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse({ detail: 'Invalid credentials' }, 401),
    )
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/')
    await userEvent.type(await screen.findByLabelText('Email or mobile'), 'a@b.c')
    await userEvent.type(screen.getByLabelText('Password'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Those credentials were not accepted.',
    )
  })

  it('passes a missing ADMIN_TOKEN through as the deploy problem it is', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse({ detail: 'ADMIN_TOKEN is not configured on this deployment' }, 503),
      ),
    )
    renderAt('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Owner' }))
    await userEvent.type(screen.getByLabelText('Email'), 'owner@nithara.app')
    await userEvent.type(screen.getByLabelText('Password'), 'right')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('ADMIN_TOKEN')
  })
})

describe('signed in as owner', () => {
  beforeEach(() => {
    sessionStorage.setItem('nithara.console.token', 'the-admin-token')
    sessionStorage.setItem('nithara.console.token_kind', 'admin_token')
    vi.stubGlobal('fetch', stubApi(OWNER))
  })

  it('renders every section', async () => {
    renderAt('/')
    expect(await screen.findByRole('link', { name: /All temples/ })).toBeVisible()
    expect(screen.getByRole('link', { name: /Users/ })).toBeVisible()
    expect(screen.getByRole('link', { name: /Operators/ })).toBeVisible()
    expect(screen.getByRole('link', { name: /App feed/ })).toBeVisible()
  })

  it('labels the caller as owner', async () => {
    renderAt('/')
    expect(await screen.findByText('Owner')).toBeVisible()
  })

  it('shows owner-only dashboard figures', async () => {
    renderAt('/')
    expect(await screen.findByText('Registered users')).toBeVisible()
    expect(screen.getByText('Payments received')).toBeVisible()
  })
})

describe('signed in as a temple_admin', () => {
  beforeEach(() => {
    sessionStorage.setItem('nithara.console.token', 'sess-abc')
    sessionStorage.setItem('nithara.console.token_kind', 'operator')
    vi.stubGlobal('fetch', stubApi(CLERK))
  })

  it('sees their own sections only', async () => {
    renderAt('/')
    expect(await screen.findByRole('link', { name: /All temples/ })).toBeVisible()
    expect(screen.getByRole('link', { name: /Pooja bookings/ })).toBeVisible()
    expect(screen.queryByRole('link', { name: /^Users/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Operators/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /App feed/ })).not.toBeInTheDocument()
  })

  it('is redirected away from a URL they typed by hand', async () => {
    // Hiding the nav item is not access control — this is the half that is.
    renderAt('/people/users')
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeVisible(),
    )
    expect(screen.queryByText(/devotee register/i)).not.toBeInTheDocument()
  })

  it('does not see owner-only dashboard figures', async () => {
    renderAt('/')
    expect(await screen.findByText('To perform today')).toBeVisible()
    expect(screen.queryByText('Registered users')).not.toBeInTheDocument()
  })

  it('is told how many temples they hold', async () => {
    renderAt('/')
    expect(await screen.findByText(/1 temple/)).toBeVisible()
  })
})

describe('session lifetime', () => {
  it('drops a token the server no longer accepts', async () => {
    sessionStorage.setItem('nithara.console.token', 'stale')
    vi.stubGlobal('fetch', stubApi(null))
    renderAt('/')
    expect(await screen.findByRole('heading', { name: 'Nithara Console' })).toBeVisible()
    expect(sessionStorage.getItem('nithara.console.token')).toBeNull()
  })

  it('signs out locally even when the server call fails', async () => {
    sessionStorage.setItem('nithara.console.token', 'sess-abc')
    const fetchMock = vi.fn(async (url: string) => {
      if (String(url).includes('/logout')) throw new Error('network down')
      if (String(url).includes('/operators/me')) return jsonResponse(OWNER)
      return jsonResponse({ total: 0, items: [] })
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/')
    await userEvent.click(await screen.findByRole('button', { name: 'Sign out' }))
    await waitFor(() =>
      expect(sessionStorage.getItem('nithara.console.token')).toBeNull(),
    )
  })
})

describe('stub sections', () => {
  it('name what will live there instead of dead-ending', async () => {
    sessionStorage.setItem('nithara.console.token', 'the-admin-token')
    sessionStorage.setItem('nithara.console.token_kind', 'admin_token')
    vi.stubGlobal('fetch', stubApi(OWNER))
    renderAt('/system/integrations')
    expect(await screen.findByRole('heading', { name: 'Integrations' })).toBeVisible()
    expect(screen.getByText(/live\/mock status/i)).toBeVisible()
  })
})
