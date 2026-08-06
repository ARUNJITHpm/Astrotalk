import { useSyncExternalStore } from 'react'

// Whether the device thinks it has a network.
//
// The app is a PWA whose service worker precaches the shell, so it OPENS
// offline — and then every screen sits on a failed query with no explanation,
// looking broken rather than disconnected. That gap is what this closes.
//
// `navigator.onLine` is a weak signal and worth being honest about: it means
// "there is a network interface", not "the internet is reachable". A phone on
// hotel wifi behind a login page reports true. So it is used only to explain a
// state the person is already in — never to block an action or to decide
// whether a request is worth making. False is trustworthy; true is a hint.

const subscribe = (cb: () => void): (() => void) => {
  window.addEventListener('online', cb)
  window.addEventListener('offline', cb)
  return () => {
    window.removeEventListener('online', cb)
    window.removeEventListener('offline', cb)
  }
}

const snapshot = (): boolean => {
  // Some engines have no navigator.onLine at all; assume connected rather than
  // showing a permanent offline banner to someone who is fine.
  const value = typeof navigator !== 'undefined' ? navigator.onLine : undefined
  return value === undefined ? true : value
}

/** Reactive online/offline state. Re-renders on the browser's own events. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribe, snapshot, () => true)
}
