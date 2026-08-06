// The service worker must not answer navigations that belong to other pages on
// this origin.
//
// The SW is registered at the root scope, so it sees EVERY navigation to
// localhost — including `/console`, which is a different React app, and
// `/a/{handle}/ui`, which is the white-label surface. Workbox's navigation
// fallback would happily answer all of them out of the precached index.html,
// and the failure is quiet: the consumer app boots, finds no matching route,
// and shows a devotee-facing "not found" to an operator who followed a bookmark.
// Nothing errors. The server is never asked.
//
// This is exactly how the /prototype bug got through once already, and a curl
// cannot see it — curl has no service worker.
//
// So the assertion is made against the BUILT artifact rather than the config.
// `navigateFallbackAllowlist` in vite.config.ts is an input to a code generator;
// what governs a real browser is the regex array Workbox emitted into dist/sw.js,
// and the two are only the same until vite-plugin-pwa changes how it compiles
// them. Reading the shipped file is the only check that cannot drift.

import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// Relative to the package root, which is where vitest runs. `import.meta.url`
// is not a file: URL under the jsdom environment.
const SW = resolve(process.cwd(), 'dist/sw.js')

/** The allowlist Workbox actually compiled into the worker. */
function allowlist(): RegExp[] {
  const source = readFileSync(SW, 'utf8')
  const match = source.match(/NavigationRoute\([^)]*\)\s*,\s*\{\s*allowlist:\s*\[([^\]]*)\]/)
  expect(match, 'no NavigationRoute allowlist found in the built sw.js').toBeTruthy()
  return (match as RegExpMatchArray)[1]
    .split(/,(?=\/)/)
    .map((literal) => literal.trim())
    .filter(Boolean)
    .map((literal) => {
      const end = literal.lastIndexOf('/')
      return new RegExp(literal.slice(1, end), literal.slice(end + 1))
    })
}

const claims = (list: RegExp[], path: string) => list.some((re) => re.test(path))

describe.skipIf(!existsSync(SW))('the service worker navigation fallback', () => {
  it('claims the app’s own routes', () => {
    const list = allowlist()
    for (const path of ['/', '/poojas', '/poojas/', '/astro', '/profile']) {
      expect(claims(list, path), `${path} should be handled by the SW`).toBe(true)
    }
  })

  it('does not claim the operator console', () => {
    // Including deep links. A denylist naming the flat pages the console used
    // to be would have caught /console and missed /console/bookings — and the
    // deep link is the one an operator actually bookmarks.
    const list = allowlist()
    for (const path of [
      '/console',
      '/console/',
      '/console/bookings',
      '/console/bookings/payments',
      '/console/channels/whatsapp',
    ]) {
      expect(claims(list, path), `${path} must reach the server`).toBe(false)
    }
  })

  it('does not claim the white-label surface or the prototype', () => {
    const list = allowlist()
    for (const path of ['/a/guruji/ui', '/a/guruji/dashboard', '/prototype', '/docs']) {
      expect(claims(list, path), `${path} must reach the server`).toBe(false)
    }
  })

  it('does not precache anything belonging to the console', () => {
    // A second, independent way in: even with the fallback allowlisted, a
    // precache entry under /console/ would be served from the cache and shadow
    // the console's own hashed bundles.
    const source = readFileSync(SW, 'utf8')
    expect(source).not.toMatch(/["'/]console\//)
  })
})
