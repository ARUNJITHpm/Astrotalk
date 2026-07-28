// The TEMPLES screens end to end: find a temple, open it, change one thing.
//
// The two the plan names — the list filters and the editor's save path — are
// here, plus the guard on the editor's URL, which is a route the sidebar never
// links to and therefore the one most likely to be left open.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import type { Temple } from '../api/temples'
import { AuthProvider, type Me } from '../lib/auth'

const OWNER: Me = { operator_id: null, roles: ['owner'], temple_ids: [], is_owner: true }
const CLERK: Me = {
  operator_id: 7,
  roles: ['temple_admin'],
  temple_ids: ['tsr-guruvayur'],
  is_owner: false,
}
const REVIEWER: Me = {
  operator_id: 9,
  roles: ['content_reviewer'],
  temple_ids: [],
  is_owner: false,
}

function temple(over: Partial<Temple> = {}): Temple {
  return {
    id: 'tsr-guruvayur',
    name: 'Guruvayur Temple',
    name_ml: 'ഗുരുവായൂർ',
    deity: 'krishna',
    district: 'Thrissur',
    town: 'Guruvayur',
    town_ml: 'ഗുരുവായൂർ',
    lat: 10.5946,
    lng: 76.0402,
    famous_for: 'Krishna darshan',
    vazhipadu: ['thulabharam'],
    reviewed: true,
    story: 'A story.',
    story_ml: null,
    hours: [[180, 780]],
    timings: { nirmalyam: '3:00 AM', morning: '7:00 AM', evening: '4:30 PM' },
    rating: null,
    reviews: null,
    active: true,
    image_key: null,
    sort_order: 0,
    updated_at: '2026-07-01T00:00:00Z',
    ...over,
  }
}

const ROWS = [
  temple(),
  temple({
    id: 'ekm-chottanikkara',
    name: 'Chottanikkara Temple',
    name_ml: 'ചോറ്റാനിക്കര',
    district: 'Ernakulam',
    town: 'Chottanikkara',
    deity: 'devi',
    reviewed: false,
  }),
]

interface Call {
  url: string
  method: string
  body: unknown
}

/** Every write the screen made, in order — what the assertions are about. */
let calls: Call[] = []

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as Response
}

function stubApi(me: Me, rows: Temple[] = ROWS) {
  return vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET'
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
    if (method !== 'GET') calls.push({ url: String(url), method, body })

    if (url.includes('/admin/operators/me')) return jsonResponse(me)
    if (url.includes('/temples/manage')) return jsonResponse(rows)
    if (url.includes('/temples/poojas')) return jsonResponse([])
    if (url.includes('/temples/partners')) return jsonResponse([])
    if (url.includes('/temples/festivals')) return jsonResponse([])
    if (url.includes('/review')) return jsonResponse({ ...rows[0], reviewed: false })
    if (url.startsWith('/temples/')) return jsonResponse({ ...rows[0], ...(body as object) })
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

function signedInAs(me: Me, rows?: Temple[]) {
  sessionStorage.setItem('nithara.console.token', 'the-admin-token')
  sessionStorage.setItem('nithara.console.token_kind', 'admin_token')
  vi.stubGlobal('fetch', stubApi(me, rows))
}

beforeEach(() => {
  sessionStorage.clear()
  calls = []
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the directory list', () => {
  it('shows the console rows, including the unreviewed ones', async () => {
    signedInAs(OWNER)
    renderAt('/temples')
    expect(await screen.findByText('Guruvayur Temple')).toBeVisible()
    expect(screen.getByText('Chottanikkara Temple')).toBeVisible()
    expect(await screen.findByText('2 of 2 temples')).toBeVisible()
  })

  it('narrows on a search', async () => {
    signedInAs(OWNER)
    renderAt('/temples')
    await screen.findByText('Guruvayur Temple')
    await userEvent.type(screen.getByLabelText('Search'), 'chott')
    await waitFor(() =>
      expect(screen.queryByText('Guruvayur Temple')).not.toBeInTheDocument(),
    )
    expect(screen.getByText('1 of 2 temples')).toBeVisible()
  })

  it('narrows on a district', async () => {
    signedInAs(OWNER)
    renderAt('/temples')
    await screen.findByText('Guruvayur Temple')
    await userEvent.selectOptions(screen.getByLabelText('District'), 'Ernakulam')
    expect(screen.queryByText('Guruvayur Temple')).not.toBeInTheDocument()
    expect(screen.getByText('Chottanikkara Temple')).toBeVisible()
  })

  it('finds the drafts that still need an astrologer', async () => {
    signedInAs(OWNER)
    renderAt('/temples')
    await screen.findByText('Guruvayur Temple')
    await userEvent.selectOptions(screen.getByLabelText('Reviewed'), 'no')
    expect(screen.getByText('1 of 2 temples')).toBeVisible()
    expect(screen.getByText('Chottanikkara Temple')).toBeVisible()
  })

  it('says so when a filter matches nothing, instead of looking broken', async () => {
    signedInAs(OWNER)
    renderAt('/temples')
    await screen.findByText('Guruvayur Temple')
    await userEvent.type(screen.getByLabelText('Search'), 'zzzz')
    expect(await screen.findByText('No temple matches those filters.')).toBeVisible()
  })

  it('offers "Add a temple" to an owner only', async () => {
    signedInAs(OWNER)
    renderAt('/temples')
    expect(await screen.findByRole('link', { name: 'Add a temple' })).toBeVisible()
  })

  it('does not offer it to a temple_admin, for whom it would 403', async () => {
    signedInAs(CLERK)
    renderAt('/temples')
    await screen.findByText('Guruvayur Temple')
    expect(screen.queryByRole('link', { name: 'Add a temple' })).not.toBeInTheDocument()
  })
})

describe('the editor', () => {
  it('sends only the field that changed', async () => {
    // The point of the whole diff. PATCH treats an explicit null as "clear
    // this column", so a save that restated the form would wipe the darshan
    // windows every time somebody fixed a name.
    signedInAs(OWNER)
    renderAt('/temples/tsr-guruvayur')
    const name = await screen.findByDisplayValue('Guruvayur Temple')
    await userEvent.clear(name)
    await userEvent.type(name, 'Guruvayoor Temple')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].method).toBe('PATCH')
    expect(calls[0].url).toBe('/temples/tsr-guruvayur')
    expect(calls[0].body).toEqual({ name: 'Guruvayoor Temple' })
  })

  it('will not "save" when nothing changed', async () => {
    // A Save that fires no request but reports success is how an operator comes
    // to believe an edit landed.
    signedInAs(OWNER)
    renderAt('/temples/tsr-guruvayur')
    await screen.findByDisplayValue('Guruvayur Temple')
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    expect(calls).toHaveLength(0)
  })

  it('will not save a temple with no coordinates', async () => {
    // Cleared number inputs become NaN, JSON.stringify turns NaN into null,
    // and a null latitude reaches the server's range check as a type error.
    signedInAs(OWNER)
    renderAt('/temples/tsr-guruvayur')
    const lat = await screen.findByDisplayValue('10.5946')
    await userEvent.clear(lat)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Latitude and longitude are required.',
    )
    expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled()
    expect(calls).toHaveLength(0)
  })

  it('does not shout at an untouched create form', async () => {
    signedInAs(OWNER)
    renderAt('/temples/new')
    expect(await screen.findByRole('heading', { name: 'Add a temple' })).toBeVisible()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Create temple' })).toBeDisabled()

    // …but says what is missing as soon as they start.
    await userEvent.type(screen.getByLabelText(/^Id/), 'Not A Slug')
    expect(await screen.findByRole('alert')).toHaveTextContent(/lowercase letters/)
  })

  it('takes coordinates off a pasted Maps link', async () => {
    signedInAs(OWNER)
    renderAt('/temples/tsr-guruvayur')
    const paste = await screen.findByLabelText(/Paste from Google Maps/)
    await userEvent.type(
      paste,
      'https://www.google.com/maps/place/X/@10.6,76.1,15z/data=!3d10.6001!4d76.1002',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Use it' }))
    expect(screen.getByDisplayValue('10.6001')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].body).toEqual({ lat: 10.6001, lng: 76.1002 })
  })

  it('rejects a paste with no coordinates in it', async () => {
    signedInAs(OWNER)
    renderAt('/temples/tsr-guruvayur')
    const paste = await screen.findByLabelText(/Paste from Google Maps/)
    await userEvent.type(paste, 'https://maps.app.goo.gl/AbCdEf')
    await userEvent.click(screen.getByRole('button', { name: 'Use it' }))
    expect(screen.getByText(/No coordinates in that/)).toBeVisible()
    expect(screen.getByDisplayValue('10.5946')).toBeVisible() // unchanged
  })

  it('puts the sign-off on its own route, not in Save', async () => {
    signedInAs(OWNER)
    renderAt('/temples/tsr-guruvayur')
    await userEvent.click(
      await screen.findByRole('button', { name: 'Withdraw the sign-off' }),
    )
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].url).toBe('/temples/tsr-guruvayur/review')
    expect(calls[0].body).toEqual({ reviewed: false })
  })

  it('will not let a temple_admin certify their own copy', async () => {
    // The role that writes a temple's story must not be the one that asserts
    // an astrologer checked it (GUARDRAILS §1). The server refuses too.
    signedInAs(CLERK, [temple({ reviewed: false })])
    renderAt('/temples/tsr-guruvayur')
    expect(await screen.findByRole('button', { name: 'Mark as reviewed' })).toBeDisabled()
    expect(
      screen.getByText(/Only an owner or a content reviewer may sign a temple off/),
    ).toBeVisible()
  })

  it('offers retiring to an owner only', async () => {
    signedInAs(CLERK, [temple({ reviewed: false })])
    renderAt('/temples/tsr-guruvayur')
    await screen.findByRole('button', { name: 'Mark as reviewed' })
    expect(
      screen.queryByRole('button', { name: 'Retire from the app' }),
    ).not.toBeInTheDocument()
  })

  it('says so plainly when the id is not one of theirs', async () => {
    signedInAs(CLERK, [ROWS[0]])
    renderAt('/temples/ekm-chottanikkara')
    expect(await screen.findByRole('heading', { name: 'No such temple' })).toBeVisible()
  })

  it('guards the detail URL with the section it belongs to', async () => {
    // /temples/:templeId is never linked from the sidebar, so nothing would
    // have caught it being left reachable. A content_reviewer cannot open
    // /temples, and must not get in through a temple's own address either.
    signedInAs(REVIEWER)
    renderAt('/temples/tsr-guruvayur')
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeVisible(),
    )
    expect(screen.queryByText('Guruvayur Temple')).not.toBeInTheDocument()
  })
})

describe('festivals', () => {
  it('will not offer an add form when no partner exists to hang one on', async () => {
    signedInAs(OWNER)
    renderAt('/temples/festivals')
    expect(await screen.findByRole('heading', { name: 'Festivals' })).toBeVisible()
    await userEvent.click(screen.getByText('Add a festival'))
    const panel = screen.getByText('Add a festival').closest('details') as HTMLElement
    expect(within(panel).getByText(/No live partner temples/)).toBeVisible()
    expect(within(panel).getByRole('button', { name: 'Add festival' })).toBeDisabled()
  })
})
