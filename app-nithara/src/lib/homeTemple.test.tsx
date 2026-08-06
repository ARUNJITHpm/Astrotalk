// The home temple: cached locally, owned by the account.
//
// The cache is the interesting part. It exists so a returning devotee sees
// their own temple on the first paint instead of watching onboarding flash
// past — but it must never outrank the server, or a choice made on one phone
// would be silently overridden by a stale copy on another.

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { clearHomeTempleCache, setHomeTempleId, useHomeTempleId } from './homeTemple'

const KEY = 'nithara.home_temple'

function json(body: unknown) {
  return { ok: true, status: 200, json: async () => body, text: async () => JSON.stringify(body) } as Response
}

let served: string | null = null
let puts: unknown[] = []
let resolveGet: (() => void) | null = null

beforeEach(() => {
  localStorage.clear()
  served = null
  puts = []
  resolveGet = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (_url: string, init: RequestInit = {}) => {
      if ((init.method ?? 'GET') === 'PUT') {
        puts.push(JSON.parse(String(init.body)))
        return json({ temple_id: served })
      }
      // Optionally hold the GET open so the placeholder can be observed.
      if (resolveGet) await new Promise<void>((r) => (resolveGet = r))
      return json({ temple_id: served })
    }),
  )
})

afterEach(() => {
  vi.restoreAllMocks()
})

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>
}

describe('the first paint', () => {
  it('shows the cached temple before the server answers', async () => {
    // Without this a returning devotee sees the onboarding prompt for a beat,
    // every single launch.
    localStorage.setItem(KEY, 'tsr-guruvayur')
    resolveGet = () => {} // hold the request open
    const { result } = renderHook(() => useHomeTempleId(), { wrapper })
    expect(result.current).toBe('tsr-guruvayur')
  })

  it('sends a genuinely new devotee to onboarding', async () => {
    const { result } = renderHook(() => useHomeTempleId(), { wrapper })
    await waitFor(() => expect(result.current).toBeNull())
  })
})

describe('the server is the source of truth', () => {
  it('overrides a stale cache', async () => {
    // Chosen on another phone. The local copy must not win.
    localStorage.setItem(KEY, 'tsr-guruvayur')
    served = 'tvm-attukal-devi'
    const { result } = renderHook(() => useHomeTempleId(), { wrapper })
    await waitFor(() => expect(result.current).toBe('tvm-attukal-devi'))
    await waitFor(() => expect(localStorage.getItem(KEY)).toBe('tvm-attukal-devi'))
  })

  it('clears the cache when the account has no temple', async () => {
    localStorage.setItem(KEY, 'tsr-guruvayur')
    served = null
    const { result } = renderHook(() => useHomeTempleId(), { wrapper })
    await waitFor(() => expect(result.current).toBeNull())
    await waitFor(() => expect(localStorage.getItem(KEY)).toBeNull())
  })
})

describe('choosing one', () => {
  it('caches immediately and writes through to the account', async () => {
    const client = new QueryClient()
    await setHomeTempleId('tsr-guruvayur', client)
    expect(localStorage.getItem(KEY)).toBe('tsr-guruvayur')
    expect(puts).toEqual([{ temple_id: 'tsr-guruvayur' }])
  })
})

describe('a temple that stops resolving', () => {
  it('drops the local copy only', () => {
    // The account keeps its id on purpose: a temple pulled from the directory
    // this morning may be back this afternoon, and erasing somebody's choice
    // over our own data problem is worse than asking them once.
    localStorage.setItem(KEY, 'retired-temple')
    clearHomeTempleCache()
    expect(localStorage.getItem(KEY)).toBeNull()
    expect(puts).toEqual([])
  })
})

// NOT tested here: localStorage throwing. The try/catch in homeTemple.ts is
// cheap insurance and stays, but it is not a resilience this app actually has —
// lib/session.ts keeps the bearer token in localStorage with no guard at all,
// so a browser that refuses storage fails to authenticate before any of this
// runs. Asserting otherwise would document a promise we do not keep.
