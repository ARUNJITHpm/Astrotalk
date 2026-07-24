import '@testing-library/jest-dom'
import { vi } from 'vitest'

// No real backend in unit tests: stub fetch with an empty-OK JSON response so
// components that fire a query render their loaded state without a network call.
globalThis.fetch = vi.fn(
  async () =>
    new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }),
) as unknown as typeof fetch
