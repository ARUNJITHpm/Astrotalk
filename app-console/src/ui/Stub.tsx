// Placeholder for a section the IA declares but a later Part builds.
//
// It names what will live here rather than saying "coming soon" and nothing
// else, so the sidebar reads as a map of the finished tool instead of a set of
// dead ends. The route exists and is guarded exactly like a real page.

import { useLocation } from 'react-router-dom'

import { itemForPath } from '../lib/nav'

export function Stub() {
  const { pathname } = useLocation()
  const item = itemForPath(pathname)

  return (
    <section className="page">
      <h1 className="page__title">{item?.label ?? 'Not built yet'}</h1>
      <p className="page__lede">{item?.blurb ?? 'This section is not built yet.'}</p>
      <p className="stub__note">
        Not built yet. The route and its permissions are in place; the screen
        arrives in a later part of the console build.
      </p>
    </section>
  )
}
