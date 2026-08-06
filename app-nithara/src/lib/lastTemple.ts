import type { TempleDetail } from '../api/types'

// The last temple opened, kept across launches.
//
// This is the offline case that actually happens: standing outside your own
// temple with no signal, wanting the timings. The service worker precaches the
// shell so the app opens — but react-query's cache is in memory, so a cold
// start had nothing to show and every screen sat on a failed request.
//
// One entry, not a store. The home temple is the one people open again and
// again, and keeping a growing cache of every temple ever tapped would trade a
// real benefit for a slow leak in localStorage.
//
// It is a CACHE, never a source of truth: it seeds the first render and the
// network answer replaces it. Timings and pooja prices change, and a stale copy
// shown as current is worse than a spinner.

const KEY = 'nithara.last_temple'

export function rememberTemple(detail: TempleDetail): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(detail))
  } catch {
    // Storage full or disabled. The app works without this.
  }
}

/** The cached detail for `id`, or null if a different temple is cached. */
export function recallTemple(id: string | null | undefined): TempleDetail | null {
  if (!id) return null
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as TempleDetail
    return parsed?.id === id ? parsed : null
  } catch {
    // Corrupt or half-written JSON — treat it as absent rather than crashing
    // the screen it was meant to help.
    return null
  }
}
