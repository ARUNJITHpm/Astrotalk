// The booking flow's payment path.
//
// These are the app's first screen tests, and they are here rather than
// somewhere prettier because this is the screen where being wrong costs a
// devotee money or a pooja. Almost every assertion is about the app NOT
// claiming something it does not know.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BookingSheet, type BookTarget } from './BookingSheet'
import type { Booking, Member, PoojaCatalogue } from '../../api/types'

const TARGET: BookTarget = {
  templeId: 'tsr-guruvayur',
  templeName: 'Guruvayur',
  poojaKey: 'pushpanjali',
  poojaName: 'Pushpanjali',
  amount: 100,
  when: '12 Aug',
}

const MEMBERS: Member[] = [
  { id: 1, name: 'Ananya', rel: 'rSelf', nak: 21, self: true },
]

const FAMILY: Member[] = [
  ...MEMBERS,
  { id: 2, name: 'Amma', rel: 'rMother', nak: 10, self: false },
]

function catalogue(feePaise: number): PoojaCatalogue {
  return {
    temple_id: 'tsr-guruvayur',
    days_until: 6,
    poojas: [],
    service_fee_paise: feePaise,
  }
}

function booking(over: Partial<Booking> = {}): Booking {
  return {
    id: 1,
    ref: 'NT123456',
    temple_id: 'tsr-guruvayur',
    pooja_key: 'pushpanjali',
    pooja_name: 'Pushpanjali',
    amount_paise: 10000,
    service_fee_paise: 1500,
    total_paise: 11500,
    member_id: 1,
    member_name: 'Ananya',
    member_nak: 21,
    when: '12 Aug',
    state: 'wait',
    order_id: 'order_live_1',
    mock: false,
    razorpay_key_id: 'rzp_test_key',
    created_at: '2026-08-06T06:00:00Z',
    ...over,
  }
}

let posts: { url: string; body: unknown }[] = []
let created: Booking = booking()
let listed: Booking[] = []
let feePaise = 1500
let members: Member[] = MEMBERS

function json(body: unknown) {
  return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) } as Response
}

beforeEach(() => {
  posts = []
  created = booking()
  listed = []
  feePaise = 1500
  members = MEMBERS
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const path = String(url)
      if ((init.method ?? 'GET') !== 'GET') {
        posts.push({ url: path, body: init.body ? JSON.parse(String(init.body)) : null })
        if (path.includes('/bookings')) return json(created)
        return json({ status: 'paid' })
      }
      if (path.includes('/poojas')) return json(catalogue(feePaise))
      if (path.includes('/members')) return json(members)
      if (path.includes('/bookings')) return json(listed)
      return json([])
    }),
  )
})

afterEach(() => {
  cleanup()
  // Restore unconditionally: a test that fails before its own cleanup would
  // otherwise leak fake timers into every test after it.
  vi.useRealTimers()
  vi.restoreAllMocks()
  delete window.Razorpay
  document.querySelectorAll('#phone').forEach((el) => el.remove())
})

function renderSheet(opts: { members?: Member[]; target?: BookTarget } = {}) {
  if (opts.members) members = opts.members
  // Sheet portals into #phone (the fixed device frame) and renders nothing
  // without it, so the harness has to supply the host the real app provides.
  // Clear any host a previous test left behind: Sheet portals into the FIRST
  // #phone it finds, and a stale one means the sheet renders into a detached
  // node and every query comes back empty.
  document.querySelectorAll('#phone').forEach((el) => el.remove())
  const host = document.createElement('div')
  host.id = 'phone'
  document.body.appendChild(host)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <BookingSheet target={opts.target ?? TARGET} onClose={() => {}} onAddMember={() => {}} />
    </QueryClientProvider>,
  )
}

/** Stand in for Razorpay's checkout.js with a scripted outcome. */
function stubRazorpay(behaviour: 'paid' | 'dismissed' | 'failed') {
  window.Razorpay = class {
    private opts: { handler: (r: unknown) => void; modal?: { ondismiss?: () => void } }
    private failHandler: ((p: unknown) => void) | null = null
    static lastOptions: Record<string, unknown> | null = null
    constructor(opts: Record<string, unknown>) {
      ;(window.Razorpay as unknown as { lastOptions: unknown }).lastOptions = opts
      this.opts = opts as never
    }
    on(event: string, handler: (p: unknown) => void) {
      if (event === 'payment.failed') this.failHandler = handler
    }
    open() {
      if (behaviour === 'paid') this.opts.handler({ razorpay_payment_id: 'pay_1' })
      else if (behaviour === 'dismissed') this.opts.modal?.ondismiss?.()
      else this.failHandler?.({ error: { description: 'Card declined' } })
    }
  } as never
}

describe('the total shown before paying', () => {
  it('uses the fee the server charges, not a constant', async () => {
    // The fee was hardcoded to ₹15 here while the console can change it. A
    // total on a payment screen that differs from the amount charged is a false
    // statement, not a rounding problem.
    feePaise = 2500
    renderSheet()
    await waitFor(() => expect(screen.getByText('₹25')).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /₹125/ })).toBeInTheDocument()
  })
})

describe('paying by card', () => {
  it('sends the server’s amount to Razorpay, never its own arithmetic', async () => {
    stubRazorpay('paid')
    listed = [booking({ state: 'ok' })]
    const user = userEvent.setup()
    renderSheet()
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(screen.getByText('All set')).toBeInTheDocument())
    const opts = (window.Razorpay as unknown as { lastOptions: Record<string, unknown> }).lastOptions
    expect(opts.amount).toBe(11500) // booking.total_paise
    expect(opts.order_id).toBe('order_live_1')
    expect(opts.key).toBe('rzp_test_key')
  })

  it('says "received", not "confirmed", until the server agrees', async () => {
    // Razorpay's callback means the money moved. Our booking flips to `ok` only
    // when the signed webhook lands. Claiming confirmation on the strength of a
    // browser callback tells a devotee their pooja is booked when it may not be.
    stubRazorpay('paid')
    listed = [booking({ state: 'wait' })]
    const user = userEvent.setup()
    renderSheet()
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(screen.getByText(/Payment received/i)).toBeInTheDocument())
    expect(screen.queryByText('All set')).toBeNull()
  })

  it('keeps the reference when checkout is dismissed', async () => {
    // The booking already exists server-side. Losing its reference would leave
    // the devotee with no way to ask about it.
    stubRazorpay('dismissed')
    const user = userEvent.setup()
    renderSheet()
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(screen.getByText(/NT123456/)).toBeInTheDocument())
    expect(screen.queryByText('All set')).toBeNull()
  })

  it('explains a declined card and says the booking is kept', async () => {
    stubRazorpay('failed')
    const user = userEvent.setup()
    renderSheet()
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(screen.getByText(/didn’t go through/i)).toBeInTheDocument())
    expect(screen.getByText(/NT123456/)).toBeInTheDocument()
  })

  // The unanswered-script case is a timing property of the loader, tested
  // directly in src/lib/razorpay.test.ts — driving it through React means
  // fighting fake timers against react-query to prove something about a
  // setTimeout.
})

describe('mock mode', () => {
  it('captures immediately so the flow works with no keys', async () => {
    created = booking({ mock: true, order_id: 'order_mock_1', razorpay_key_id: '' })
    const user = userEvent.setup()
    renderSheet()
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(screen.getByText('All set')).toBeInTheDocument())
    expect(posts.some((p) => p.url.includes('/mock-pay'))).toBe(true)
  })

  it('never calls mock-pay on a live booking', async () => {
    // mock-pay 404s on a live deployment, but the client must not be relying on
    // that: reaching for it at all would mean the branch is wrong.
    stubRazorpay('paid')
    listed = [booking({ state: 'ok' })]
    const user = userEvent.setup()
    renderSheet()
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(screen.getByText('All set')).toBeInTheDocument())
    expect(posts.some((p) => p.url.includes('/mock-pay'))).toBe(false)
  })
})

describe('who the booking is for', () => {
  it('records the member chosen, not the account holder', async () => {
    // Booking "for Amma's star" under the account holder's name is the mistake
    // this screen exists to prevent — the temple reads the member name off the
    // worklist and calls it out.
    const user = userEvent.setup()
    renderSheet({ members: FAMILY })
    await screen.findByRole('button', { name: /₹115/ })

    await user.click(screen.getByRole('button', { name: /Amma/ }))
    await user.click(screen.getByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(posts.some((p) => p.url.endsWith('/bookings'))).toBe(true))
    const body = posts.find((p) => p.url.endsWith('/bookings'))!.body as Record<string, unknown>
    expect(body.member_id).toBe(2)
    expect(body.member_name).toBe('Amma')
    expect(body.member_nak).toBe(10)
  })

  it('defaults to the member the CTA named', async () => {
    // A "book for Amma's star" button must not silently land on the account
    // holder just because nobody tapped a chip.
    const user = userEvent.setup()
    renderSheet({ members: FAMILY, target: { ...TARGET, memberId: 2 } })
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(posts.some((p) => p.url.endsWith('/bookings'))).toBe(true))
    const body = posts.find((p) => p.url.endsWith('/bookings'))!.body as Record<string, unknown>
    expect(body.member_id).toBe(2)
  })

  it('falls back to the account holder when the CTA named nobody', async () => {
    const user = userEvent.setup()
    renderSheet({ members: FAMILY })
    await user.click(await screen.findByRole('button', { name: /₹115/ }))

    await waitFor(() => expect(posts.some((p) => p.url.endsWith('/bookings'))).toBe(true))
    const body = posts.find((p) => p.url.endsWith('/bookings'))!.body as Record<string, unknown>
    expect(body.member_id).toBe(1)
  })
})
