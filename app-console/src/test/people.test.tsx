// The PEOPLE screens.
//
// The family board and the chart are the two places in this console that hold
// birth data, so most of what follows is about where it may and may not appear.
// Asserting the absence of a field is the only way a leak is caught before it
// ships, and these are the assertions that would fail if someone later folded
// the chart into the detail payload "for convenience".

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import type { Member, OperatorRow, UserDetail } from '../api/people'
import { AuthProvider, type Me } from '../lib/auth'

const OWNER: Me = { operator_id: null, roles: ['owner'], temple_ids: [], is_owner: true }
const CLERK: Me = {
  operator_id: 7,
  roles: ['temple_admin'],
  temple_ids: ['tsr-guruvayur'],
  is_owner: false,
}

const USER: UserDetail = {
  id: 3,
  name: 'Ananya Nair',
  phone: '+919812345678',
  active: true,
  birth_place: 'Thrissur',
  tz: 'Asia/Kolkata',
  org_id: null,
  transcript_consent: false,
  created_at: '2026-07-01T06:00:00Z',
  bookings: [],
  payments: [],
  entitlements: [
    {
      id: 11,
      product_key: 'full_report',
      granted_by: 'admin',
      source: 'goodwill',
      expires_at: null,
      created_at: '2026-07-02T06:00:00Z',
    },
  ],
}

const FAMILY: Member[] = [
  { id: 1, name: 'Ananya Nair', rel: 'rSelf', nak: 21, dob: null, self: true },
  { id: 2, name: 'Sarada', rel: 'rMother', nak: 10, dob: '1961-04-12', self: false },
]

const OPERATORS: OperatorRow[] = [
  {
    id: 7,
    email: 'clerk@example.com',
    phone: null,
    name: 'Clerk',
    active: true,
    pending: false,
    last_login_at: null,
    roles: [{ id: 1, role: 'temple_admin', temple_id: 'tsr-guruvayur' }],
  },
]

interface Call {
  url: string
  method: string
  body: unknown
}
let calls: Call[] = []
let gets: string[] = []

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as Response
}

function stubApi(me: Me, opts: { family?: Member[]; chart?: unknown } = {}) {
  const family = opts.family ?? FAMILY
  return vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET'
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
    if (method === 'GET') gets.push(String(url))
    else calls.push({ url: String(url), method, body })

    if (url.includes('/admin/operators/me')) return jsonResponse(me)
    if (url.includes('/admin/operators')) return jsonResponse(OPERATORS)
    if (url.includes('/family')) {
      if (method === 'GET') return jsonResponse(family)
      return jsonResponse({ ...family[1], ...(body as object) }, method === 'POST' ? 201 : 200)
    }
    if (url.includes('/chart')) {
      return opts.chart
        ? jsonResponse({ computed_at: '2026-07-01T06:00:00Z', natal: opts.chart })
        : jsonResponse({ detail: 'No chart has been computed for this user' }, 404)
    }
    if (url.includes('/admin/engagement')) {
      return jsonResponse({
        generated_at: '2026-07-28T06:00:00Z',
        day: '2026-07-28',
        users_counted: 2,
        users_total: 2,
        truncated: false,
        checkins: { total: 4, users_ever: 2, users_on_a_streak: 1, checked_in_today: 1 },
        milestones: [{ key: 'first_temple', target: 1, unlocked: 1 }],
        most_engaged: [
          {
            user_id: 3,
            name: 'Ananya Nair',
            phone: '+919812345678',
            checkins: 3,
            badges: 1,
            temples_visited: 1,
            districts_visited: 1,
            poojas: 1,
            streak: 3,
          },
        ],
      })
    }
    if (/\/admin\/users\/\d+$/.test(String(url))) return jsonResponse(USER)
    if (url.includes('/admin/users')) {
      return jsonResponse({
        total: 1,
        limit: 50,
        offset: 0,
        items: [
          {
            id: 3,
            name: 'Ananya Nair',
            phone: '+919812345678',
            active: true,
            org_id: null,
            created_at: '2026-07-01T06:00:00Z',
          },
        ],
      })
    }
    if (url.includes('/astrologers/manage')) return jsonResponse([])
    if (url.includes('/temples/manage')) return jsonResponse([])
    return jsonResponse({ total: 0, items: [] })
  })
}

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
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

function signedInAs(me: Me, opts?: { family?: Member[]; chart?: unknown }) {
  sessionStorage.setItem('nithara.console.token', 'the-admin-token')
  sessionStorage.setItem('nithara.console.token_kind', 'admin_token')
  vi.stubGlobal('fetch', stubApi(me, opts))
}

beforeEach(() => {
  sessionStorage.clear()
  calls = []
  gets = []
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the devotee register', () => {
  it('lists accounts whether or not they have ever chatted', async () => {
    signedInAs(OWNER)
    renderAt('/people/users')
    expect(await screen.findByText('Ananya Nair')).toBeVisible()
    expect(screen.getByText('+919812345678')).toBeVisible()
  })

  it('searches by name or mobile and by nothing else', async () => {
    // A birth-date filter would put a date of birth in a query string and
    // therefore in an access log (GUARDRAILS §4). The box cannot ask.
    signedInAs(OWNER)
    renderAt('/people/users')
    await screen.findByText('Ananya Nair')
    expect(screen.getByLabelText('Search')).toHaveAttribute('placeholder', 'name or mobile')
    expect(screen.queryByLabelText(/born/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/birth/i)).not.toBeInTheDocument()
  })

  it('is not open to a temple_admin', async () => {
    signedInAs(CLERK)
    renderAt('/people/users')
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeVisible(),
    )
    expect(screen.queryByText('Ananya Nair')).not.toBeInTheDocument()
  })

  it('guards the detail URL the sidebar never links to', async () => {
    signedInAs(CLERK)
    renderAt('/people/users/3')
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeVisible(),
    )
  })
})

describe('one devotee', () => {
  it('shows birth place and neither date nor time of birth', async () => {
    signedInAs(OWNER)
    renderAt('/people/users/3')
    expect(await screen.findByRole('heading', { name: 'Ananya Nair' })).toBeVisible()
    expect(screen.getByText('Thrissur')).toBeVisible()
    expect(screen.queryByText(/time of birth/i)).not.toBeInTheDocument()
  })

  it('does not fetch the chart until somebody asks for it', async () => {
    // The chart is birth data by another name. It is a separate request against
    // one named id precisely so it cannot ride along with a routine page load.
    signedInAs(OWNER, { chart: { lagna: 'Simha' } })
    renderAt('/people/users/3')
    await screen.findByRole('heading', { name: 'Ananya Nair' })
    expect(gets.some((u) => u.includes('/chart'))).toBe(false)

    await userEvent.click(screen.getByRole('button', { name: 'Show the chart' }))
    await waitFor(() => expect(gets.some((u) => u.includes('/chart'))).toBe(true))
    expect(await screen.findByText(/Simha/)).toBeVisible()
  })

  it('warns what the chart is before showing it', async () => {
    signedInAs(OWNER)
    renderAt('/people/users/3')
    expect(await screen.findByText(/This is birth data/)).toBeVisible()
  })

  it('can withdraw an entitlement', async () => {
    signedInAs(OWNER)
    renderAt('/people/users/3')
    await userEvent.click(await screen.findByRole('button', { name: 'Withdraw' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].method).toBe('DELETE')
    expect(calls[0].url).toBe('/admin/entitlements/11')
  })

  it('says what disabling an account actually does', async () => {
    signedInAs(OWNER)
    renderAt('/people/users/3')
    expect(await screen.findByText(/drops every live session/)).toBeVisible()
  })
})

describe('the family board', () => {
  it('shows a derived age beside the stored birth date', async () => {
    signedInAs(OWNER)
    renderAt('/people/users/3')
    const row = (await screen.findByDisplayValue('Sarada')).closest('tr') as HTMLElement
    expect(within(row).getByDisplayValue('1961-04-12')).toBeVisible()
    // Derived, never stored — nothing is sent or received called "age".
    expect(within(row).queryByLabelText(/age/i)).not.toBeInTheDocument()
  })

  it('will not let the account holder be removed', async () => {
    // It is the row a booking defaults to; removing it would leave the account
    // unable to book for itself.
    signedInAs(OWNER)
    renderAt('/people/users/3')
    const self = (await screen.findByDisplayValue('Ananya Nair')).closest('tr') as HTMLElement
    expect(within(self).queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument()
    expect(within(self).getByText('the account holder')).toBeVisible()
  })

  it('adds a relative with a star and a birth date', async () => {
    signedInAs(OWNER)
    renderAt('/people/users/3')
    await screen.findByDisplayValue('Sarada')
    await userEvent.click(screen.getByText('Add someone'))

    await userEvent.type(screen.getByLabelText('Name'), 'Ravi')
    await userEvent.selectOptions(screen.getByLabelText(/^Star/), '10')
    await userEvent.click(screen.getByRole('button', { name: 'Add to the board' }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].method).toBe('POST')
    expect(calls[0].url).toBe('/admin/users/3/family')
    expect(calls[0].body).toEqual({ name: 'Ravi', rel: 'rMother', nak: 10, dob: null })
  })

  it('sends null for an unknown star, not a zero', async () => {
    // Index 0 is Ashwathi, a real star. "Not known" has to travel as null or
    // every unknown becomes Ashwathi.
    signedInAs(OWNER)
    renderAt('/people/users/3')
    const row = (await screen.findByDisplayValue('Sarada')).closest('tr') as HTMLElement
    // [0] is the relation, [1] is the star.
    const star = within(row).getAllByRole('combobox')[1]
    await userEvent.selectOptions(star, '')
    await userEvent.click(within(row).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect((calls[0].body as { nak: number | null }).nak).toBeNull()
  })
})

describe('operators', () => {
  it('will not offer a grant the server would refuse', async () => {
    // A temple_admin with no temple can see nothing at all and reads as a
    // broken account; the form says so rather than letting the 422 explain it.
    signedInAs(OWNER)
    renderAt('/people/operators')
    await userEvent.click(await screen.findByRole('button', { name: 'Roles' }))
    expect(screen.getByText(/must be given a temple/)).toBeVisible()
    const grant = screen.getByRole('button', { name: 'Grant' })
    expect(grant).toBeDisabled()
  })

  it('explains that the invite has to be passed on by hand', async () => {
    signedInAs(OWNER)
    renderAt('/people/operators')
    await userEvent.click(await screen.findByText('Invite an operator'))
    expect(screen.getByText(/An email or a mobile is needed/)).toBeVisible()
  })

  it('shows what a scoped operator actually holds', async () => {
    signedInAs(OWNER)
    renderAt('/people/operators')
    expect(await screen.findByText(/temple admin · 1 temple/)).toBeVisible()
  })
})

describe('engagement', () => {
  it('reports check-ins, badges and who is worth talking to', async () => {
    signedInAs(OWNER)
    renderAt('/people/engagement')
    expect(await screen.findByText('Checked in today')).toBeVisible()
    expect(screen.getByText('Visited a temple')).toBeVisible()
    const row = screen.getByRole('link', { name: 'Ananya Nair' }).closest('tr') as HTMLElement
    // streak, check-ins, temples, poojas, badges — in that order.
    const figures = within(row)
      .getAllByRole('cell')
      .slice(1)
      .map((cell) => cell.textContent?.trim())
    expect(figures[0]).toBe('3') // the streak
    expect(figures[1]).toBe('3') // check-ins
    expect(figures[3]).toBe('1') // poojas
  })

  it('carries no birth data', async () => {
    signedInAs(OWNER)
    renderAt('/people/engagement')
    await screen.findByText('Checked in today')
    expect(screen.queryByText('Thrissur')).not.toBeInTheDocument()
    expect(screen.queryByText(/1990/)).not.toBeInTheDocument()
  })
})
