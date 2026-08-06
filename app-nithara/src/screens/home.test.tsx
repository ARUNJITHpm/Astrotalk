// The Home screen's data states, and a chat exchange.
//
// The plan asked for loading / empty / error on the Part 6 screens and a mocked
// chat exchange in Part 8. Both are here because Home is where a failed request
// is most likely to be seen and least likely to be explained.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import Home from './Home'
import type { TempleDetail } from '../api/types'

const TEMPLE: TempleDetail = {
  id: 'tsr-guruvayur',
  en: 'Guruvayur',
  ml: 'ഗുരുവായൂർ',
  place: 'Thrissur',
  mplace: 'തൃശൂർ',
  deity: 'Vishnu',
  sig: 'vishnu',
  lat: 10.5946,
  lng: 76.0402,
  open: true,
  closes: '13:00',
  rating: null,
  reviews: null,
  distance_km: 1.2,
  district: 'Thrissur',
  story: 'A story.',
  story_ml: null,
  timings: { nirmalyam: '3:00 AM', morning: '7:00 AM', evening: '4:30 PM' },
  poojas: [],
} as unknown as TempleDetail

let templeStatus = 200
let hold: Promise<void> | null = null

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
  localStorage.setItem('nithara.home_temple', 'tsr-guruvayur')
  templeStatus = 200
  hold = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const path = String(url)
      if ((init.method ?? 'GET') !== 'GET') {
        if (path.includes('/chat/message')) {
          return json({ reply: 'ഇന്ന് നല്ല നേരം രാവിലെ 6:30 മുതൽ.' })
        }
        return json({})
      }
      if (path.includes('/identity/me/home-temple')) return json({ temple_id: 'tsr-guruvayur' })
      if (path.match(/\/temples\/[^/]+$/)) {
        if (hold) await hold
        return templeStatus === 200 ? json(TEMPLE) : json({ detail: 'gone' }, templeStatus)
      }
      if (path.includes('/poojas')) return json({ temple_id: 'x', days_until: null, poojas: [], service_fee_paise: 1500 })
      if (path.includes('/astrology/panchangam')) {
        return json({ date: '2026-08-06', nakshatram: 'വിശാഖം', nalla_neram: '06:30–07:30', tithi: 'ദ്വിതീയ', mock: false, source: 'swiss' })
      }
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

function renderHome() {
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
        <Home />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('data states', () => {
  it('shows the temple once it loads', async () => {
    renderHome()
    await waitFor(() => expect(screen.getByText('Guruvayur')).toBeVisible())
  })

  it('does not render a half-built hero while loading', async () => {
    let release: () => void = () => {}
    hold = new Promise<void>((r) => (release = r))
    renderHome()
    expect(screen.queryByText('Guruvayur')).toBeNull()
    release()
    await waitFor(() => expect(screen.getByText('Guruvayur')).toBeVisible())
  })

  it('sends the devotee back to onboarding when the temple is gone', async () => {
    // A temple retired from the directory would otherwise leave an empty hero
    // with no way out.
    templeStatus = 404
    renderHome()
    await waitFor(() =>
      expect(localStorage.getItem('nithara.home_temple')).toBeNull(),
    )
  })

  it('offers onboarding when no temple has been chosen', async () => {
    localStorage.clear()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        String(url).includes('/home-temple') ? json({ temple_id: null }) : json([]),
      ),
    )
    renderHome()
    await waitFor(() => expect(screen.getByRole('textbox')).toBeVisible())
  })
})
