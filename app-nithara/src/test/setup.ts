import '@testing-library/jest-dom'
import { vi } from 'vitest'

// No real backend in unit tests: stub fetch with an empty-OK JSON response so
// components that fire a query render their loaded state without a network call.
globalThis.fetch = vi.fn(
  async () =>
    new Response('[]', { status: 200, headers: { 'Content-Type': 'application/json' } }),
) as unknown as typeof fetch

// jsdom implements no scrolling API at all, so any component that keeps a
// thread pinned to the bottom (the chat sheet) throws on its first render in a
// test. A no-op is the right stand-in: there is nothing to scroll.
Element.prototype.scrollTo = Element.prototype.scrollTo ?? (() => {})
Element.prototype.scrollIntoView = Element.prototype.scrollIntoView ?? (() => {})
