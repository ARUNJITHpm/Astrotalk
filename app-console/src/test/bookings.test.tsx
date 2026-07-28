// The BOOKINGS screens: work the queue, open a booking, move it on.
//
// The two the plan names are the filter state and a status transition. Both are
// here against the real components, on top of the pure tests in booking.test.ts.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from '../App'
import type { BookingDetail, BookingRow } from '../api/bookings'
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

function row(over: Partial<BookingRow> = {}): BookingRow {
  return {
    id: 41,
    ref: 'NT7K3Q2X',
    temple_id: 'tsr-guruvayur',
    pooja_key: 'archana',
    pooja_name: 'Archana',
    amount_paise: 5100,
    service_fee_paise: 1500,
    member_name: 'Devotee',
    member_nak: 21,
    when_label: '28 Jul, 6:00 AM',
    perform_on: '2026-08-01',
    state: 'ok',
    operator_note: '',
    created_at: '2026-07-20T06:00:00Z',
    updated_at: null,
    ...over,
  }
}

function detail(over: Partial<BookingDetail> = {}): BookingDetail {
  return {
    ...row(),
    user_id: 3,
    user_name: 'Anand',
    user_phone: '+919000000001',
    razorpay_order_id: 'order_abc',
    payment_status: 'paid',
    total_paise: 6600,
    ...over,
  }
}

interface Call {
  url: string
  method: string
  body: unknown
}
let calls: Call[] = []
/** Every GET the screen made — what the filter assertions read. */
let gets: string[] = []

function jsonResponse(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
    json: async () => body,
  } as Response
}

function stubApi(
  me: Me,
  opts: { rows?: BookingRow[]; one?: BookingDetail; total?: number } = {},
) {
  const rows = opts.rows ?? [row()]
  const total = opts.total ?? rows.length
  return vi.fn(async (url: string, init: RequestInit = {}) => {
    const method = init.method ?? 'GET'
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
    if (method === 'GET') gets.push(String(url))
    else calls.push({ url: String(url), method, body })

    if (url.includes('/admin/operators/me')) return jsonResponse(me)
    if (url.includes('/temples/manage')) return jsonResponse([])
    if (url.includes('/astrologers/manage')) return jsonResponse([])
    if (url.includes('/admin/payments')) {
      return jsonResponse({ total: 0, limit: 50, offset: 0, items: [] })
    }
    if (url.includes('/bookings/queue/worklist')) {
      return jsonResponse({ temple_id: null, day: null, total: 0, undated: 2, groups: [] })
    }
    if (url.includes('/bookings/queue?') || url.endsWith('/bookings/queue')) {
      return jsonResponse({ total, limit: 50, offset: 0, items: rows })
    }
    if (url.includes('/status') || url.includes('/note') || url.includes('/perform-on')) {
      return jsonResponse({ ...(opts.one ?? detail()), ...(body as object) })
    }
    if (url.includes('/bookings/queue/')) return jsonResponse(opts.one ?? detail())
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

function signedInAs(
  me: Me,
  opts?: { rows?: BookingRow[]; one?: BookingDetail; total?: number },
) {
  sessionStorage.setItem('nithara.console.token', 'the-admin-token')
  sessionStorage.setItem('nithara.console.token_kind', 'admin_token')
  vi.stubGlobal('fetch', stubApi(me, opts))
}

/** The most recent queue request, so filter assertions read what was sent. */
const lastQueueUrl = () => [...gets].reverse().find((u) => u.includes('/bookings/queue?')) ?? ''

beforeEach(() => {
  sessionStorage.clear()
  calls = []
  gets = []
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the queue', () => {
  it('shows a booking the way an operator reads it', async () => {
    signedInAs(OWNER)
    renderAt('/bookings')
    const ref = await screen.findByText('NT7K3Q2X')
    const line = ref.closest('tr') as HTMLElement
    expect(within(line).getByText('Thiruvonam · തിരുവോണം')).toBeVisible()
    expect(within(line).getByText('₹66')).toBeVisible() // offering + service fee
    expect(within(line).getByText('Paid')).toBeVisible() // not the raw "ok"
  })

  it('sends a filter to the server rather than filtering in the browser', async () => {
    // The queue is paged and scoped server-side; a client-side filter would
    // only ever narrow the page in front of you.
    signedInAs(OWNER)
    renderAt('/bookings')
    await screen.findByText('NT7K3Q2X')
    await userEvent.selectOptions(screen.getByLabelText('State'), 'ok')
    await waitFor(() => expect(lastQueueUrl()).toContain('state=ok'))
  })

  it('does not send a filter it was never given', async () => {
    signedInAs(OWNER)
    renderAt('/bookings')
    await waitFor(() => expect(lastQueueUrl()).toBeTruthy())
    expect(lastQueueUrl()).not.toContain('state=')
    expect(lastQueueUrl()).not.toContain('ref=')
  })

  it('goes back to the first page when a filter changes', async () => {
    signedInAs(OWNER, {
      rows: Array.from({ length: 50 }, (_, i) => row({ id: i, ref: `NT${i}` })),
      total: 400,
    })
    renderAt('/bookings')
    await screen.findByText('NT0')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(lastQueueUrl()).toContain('offset=50'))

    await userEvent.selectOptions(screen.getByLabelText('State'), 'ok')
    await waitFor(() => expect(lastQueueUrl()).toContain('offset=0'))
  })

  it('offers "to perform today" as one click', async () => {
    signedInAs(OWNER)
    renderAt('/bookings')
    await screen.findByText('NT7K3Q2X')
    await userEvent.click(screen.getByRole('button', { name: 'To perform today' }))
    await waitFor(() => expect(lastQueueUrl()).toContain('perform_from='))
    expect(lastQueueUrl()).toContain('perform_to=')
  })

  it('keeps a temple_admin out of nothing they hold, and everyone else out', async () => {
    signedInAs(REVIEWER)
    renderAt('/bookings')
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeVisible(),
    )
    expect(screen.queryByText('NT7K3Q2X')).not.toBeInTheDocument()
  })
})

describe('a status transition', () => {
  it('offers only the moves the server would accept', async () => {
    signedInAs(OWNER)
    renderAt('/bookings/41')
    const panel = (await screen.findByText('Move this booking on')).closest(
      'section',
    ) as HTMLElement
    // A paid booking: performed, cancelled or refunded — never back to paid or
    // awaiting payment, both of which belong to the payment reconciler.
    expect(within(panel).getByRole('button', { name: 'Performed' })).toBeVisible()
    expect(within(panel).getByRole('button', { name: 'Cancelled' })).toBeVisible()
    expect(within(panel).getByRole('button', { name: 'Refunded' })).toBeVisible()
    expect(within(panel).queryByRole('button', { name: 'Paid' })).not.toBeInTheDocument()
    expect(
      within(panel).queryByRole('button', { name: 'Awaiting payment' }),
    ).not.toBeInTheDocument()
  })

  it('confirms before it records, and sends the reason with it', async () => {
    signedInAs(OWNER)
    renderAt('/bookings/41')
    await userEvent.click(await screen.findByRole('button', { name: 'Cancelled' }))
    expect(calls).toHaveLength(0) // picking a target writes nothing

    await userEvent.type(screen.getByLabelText(/Why/), 'devotee called to cancel')
    await userEvent.click(screen.getByRole('button', { name: 'Mark cancelled' }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].method).toBe('PATCH')
    expect(calls[0].url).toBe('/bookings/queue/41/status')
    expect(calls[0].body).toEqual({ status: 'cancelled', note: 'devotee called to cancel' })
  })

  it('warns that a refund here moves no money', async () => {
    // The button says "Refunded" and records bookkeeping only — wiring a real
    // Razorpay refund is gated on human approval (AGENTS.md).
    signedInAs(OWNER)
    renderAt('/bookings/41')
    await userEvent.click(await screen.findByRole('button', { name: 'Refunded' }))
    expect(screen.getByText(/does not move any money/i)).toBeVisible()
  })

  it('offers nothing once a booking is refunded', async () => {
    signedInAs(OWNER, { one: detail({ state: 'refunded' }) })
    renderAt('/bookings/41')
    expect(await screen.findByText(/end of the line/)).toBeVisible()
  })

  it('shows the devotee a temple can call, and no birth data', async () => {
    // GUARDRAILS §4: performing a pooja needs a name and a number, not a
    // birth date, time or place.
    signedInAs(OWNER)
    renderAt('/bookings/41')
    expect(await screen.findByText('+919000000001')).toBeVisible()
    expect(screen.queryByText(/birth/i)).not.toBeInTheDocument()
  })
})

describe('dating a booking', () => {
  it('sends null when the date is cleared, not an empty string', async () => {
    signedInAs(OWNER)
    renderAt('/bookings/41')
    const date = await screen.findByLabelText('Perform on')
    await userEvent.clear(date)
    await userEvent.click(screen.getByRole('button', { name: 'Set date' }))
    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0].url).toBe('/bookings/queue/41/perform-on')
    expect(calls[0].body).toEqual({ perform_on: null })
  })

  it('says why an undated booking is invisible to the worklist', async () => {
    signedInAs(OWNER, { one: detail({ perform_on: null }) })
    renderAt('/bookings/41')
    expect(await screen.findByText(/on no worklist at any date/)).toBeVisible()
  })
})

describe('the worklist', () => {
  it('does not let undated bookings disappear quietly', async () => {
    signedInAs(OWNER)
    renderAt('/bookings/worklist')
    expect(await screen.findByText(/2 bookings carry no perform date/)).toBeVisible()
  })
})
