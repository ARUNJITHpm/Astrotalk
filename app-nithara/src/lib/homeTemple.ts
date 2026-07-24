import { useSyncExternalStore } from 'react'

// The chosen "home temple". NOTE: the backend's /me/home-temple + anonymous
// session aren't built yet (audit 🔨), so we persist client-side for now. When
// that lands, this becomes a thin cache over the server value.

const KEY = 'nithara.home_temple'
const listeners = new Set<() => void>()

export function getHomeTempleId(): string | null {
  return localStorage.getItem(KEY)
}

export function setHomeTempleId(id: string): void {
  localStorage.setItem(KEY, id)
  listeners.forEach((l) => l())
}

/** Forget the chosen temple (e.g. it 404s after a data change) → re-onboard. */
export function clearHomeTempleId(): void {
  localStorage.removeItem(KEY)
  listeners.forEach((l) => l())
}

function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

/** Reactive read of the chosen home temple id (re-renders on change). */
export function useHomeTempleId(): string | null {
  return useSyncExternalStore(subscribe, getHomeTempleId, () => null)
}
