// The Profile screen's two chart states, and the chat exchange.
//
// The plan (Part 8) asked for exactly these. The before-state is the one that
// was wrong for weeks — it offered "set your nakshatram" because an anonymous
// account had no way to create a chart, and a test pinning what it offers now
// is what stops that regressing quietly.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Profile from './Profile'

const CHART = {
  id: 1,
  user_id: 3,
  computed_at: '2026-08-06T06:00:00Z',
  natal_json: {
    rasi: 'ഇടവം',
    nakshatram: 'രോഹിണി',
    lagnam: 'ചിങ്ങം',
    birth_time_known: true,
    mock: false,
    planets: {
      sun: { rasi: 'മേടം', rasi_index: 0, house: 9 },
      moon: { rasi: 'ഇടവം', rasi_index: 1, house: 10 },
    },
    dasha: {
      mahadashas: [
        {
          lord: 'Rahu',
          lord_ml: 'രാഹു',
          start: '2005-01-01T00:00:00',
          end: '2099-01-01T00:00:00',
          years: 18,
        },
      ],
    },
  },
}

let chart: typeof CHART | null = null
let posts: { url: string; body: unknown }[] = []

function json(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response
}

beforeEach(() => {
  localStorage.clear()
  chart = null
  posts = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const path = String(url)
      const method = init.method ?? 'GET'
      if (method !== 'GET') {
        posts.push({ url: path, body: init.body ? JSON.parse(String(init.body)) : null })
        if (path.includes('/me/birth')) {
          chart = CHART
          return json(CHART)
        }
        if (path.includes('/chat/message')) {
          return json({ reply: 'ഇന്നത്തെ നക്ഷത്രം വിശാഖം.' })
        }
        return json({})
      }
      if (path.includes('/me/chart')) {
        return chart ? json(chart) : json({ detail: 'No chart yet' }, 404)
      }
      if (path.includes('/me/birth')) return json({ dob: null, birth_time: null, birth_place: '' })
      if (path.includes('/me/members')) return json([{ id: 1, name: 'Ananya', rel: 'rSelf', nak: 21, self: true }])
      if (path.includes('/me/stats')) return json({ temples_visited: 2, poojas: 1, streak: 3, badges: 1 })
      if (path.includes('/me/milestones')) return json([])
      return json([])
    }),
  )
})

afterEach(() => {
  // Unmount BEFORE the host is removed. React's portal cleanup needs the node
  // it rendered into to still exist, and a tree left mounted fights the next
  // test's render for the #phone element.
  cleanup()
  vi.restoreAllMocks()
  document.querySelectorAll('#phone').forEach((el) => el.remove())
})

function renderProfile() {
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
      <MemoryRouter>
        <Profile />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('before there is a chart', () => {
  it('offers to compute one, not merely to set a nakshatram', async () => {
    // The old CTA offered only "set your nakshatram", because an anonymous
    // account genuinely had no route to a chart. It has one now, and this is
    // what stops the placeholder creeping back.
    renderProfile()
    expect(await screen.findByRole('button', { name: /Compute my jathakam/i })).toBeVisible()
    expect(screen.queryByText(/rasi grid|Rahu/i)).toBeNull()
  })

  it('sends the birth details in a body and never a query string', async () => {
    // GUARDRAILS §4 — a date of birth in a URL is a date of birth in every
    // access log between the phone and the server.
    const user = userEvent.setup()
    renderProfile()
    await user.click(await screen.findByRole('button', { name: /Compute my jathakam/i }))

    // The sheet's submit and the card's CTA share a label by design — the same
    // action, offered twice. Scope to the dialog.
    const sheet = within(await screen.findByRole('dialog'))
    // fireEvent, not user.type, for both. A date input does not accept typed
    // characters in jsdom, and the birth-details query resolving mid-typing
    // re-renders the sheet and drops keystrokes from the text field.
    fireEvent.change(sheet.getByLabelText(/Date of birth/i), { target: { value: '1990-04-12' } })
    fireEvent.change(sheet.getByLabelText(/Place of birth/i), { target: { value: 'Thrissur' } })
    await user.click(sheet.getByRole('button', { name: /Compute my jathakam/i }))

    await waitFor(() => expect(posts.some((p) => p.url.includes('/me/birth'))).toBe(true))
    const call = posts.find((p) => p.url.includes('/me/birth'))!
    expect(call.url).not.toMatch(/1990/)
    expect(call.body).toMatchObject({ dob: '1990-04-12', birth_place: 'Thrissur' })
  })

  it('lets somebody who does not know their birth time proceed', async () => {
    // A required time makes people guess, and a guessed hour is a confidently
    // wrong lagna.
    const user = userEvent.setup()
    renderProfile()
    await user.click(await screen.findByRole('button', { name: /Compute my jathakam/i }))
    const sheet = within(await screen.findByRole('dialog'))
    fireEvent.change(sheet.getByLabelText(/Date of birth/i), { target: { value: '1990-04-12' } })
    fireEvent.change(sheet.getByLabelText(/Place of birth/i), { target: { value: 'Thrissur' } })

    const submit = sheet.getByRole('button', { name: /Compute my jathakam/i })
    expect(submit).toBeEnabled()
    await user.click(submit)
    await waitFor(() => expect(posts.some((p) => p.url.includes('/me/birth'))).toBe(true))
    expect((posts.find((p) => p.url.includes('/me/birth'))!.body as Record<string, unknown>).birth_time).toBeNull()
  })
})

describe('once there is a chart', () => {
  it('shows the janma nakshatram and the running dasha', async () => {
    chart = CHART
    renderProfile()
    await waitFor(() => expect(screen.getByText('രോഹിണി')).toBeVisible())
    expect(screen.getByText(/രാഹു|Rahu/)).toBeVisible()
  })

  it('shares the nakshatram and never the birth details', async () => {
    // The card lands on a public /s/ page. Date, time and place are what a
    // chart is recomputed from; putting them on a shareable image would hand
    // anyone who saw it the whole jathakam.
    chart = CHART
    const user = userEvent.setup()
    renderProfile()
    await user.click(await screen.findByRole('button', { name: /Share my nakshatram/i }))

    await waitFor(() => expect(posts.some((p) => p.url.includes('/content/cards'))).toBe(true))
    const body = posts.find((p) => p.url.includes('/content/cards'))!.body as { body: string }
    expect(body.body).toContain('രോഹിണി')
    expect(body.body).not.toMatch(/1990|04-12|Thrissur/)
  })
})
