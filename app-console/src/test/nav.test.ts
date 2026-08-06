// The role rules behind the sidebar.
//
// These matter more than they look. The console renders a nav item and guards a
// route from the SAME table, so a mistake here is not "a wrong menu" — it is a
// section that a scoped operator can walk into. The server still refuses (every
// path is behind require_operator), but the console would be lying to them.

import { describe, expect, it } from 'vitest'

import { SCREENS } from '../App'
import {
  NAV,
  allNavItems,
  allRoutes,
  canAccess,
  firstReachablePath,
  itemForPath,
  visibleNav,
} from '../lib/nav'

const OWNER = ['owner']
const TEMPLE_ADMIN = ['temple_admin']
const REVIEWER = ['content_reviewer']
const SUPPORT = ['support']

describe('role visibility', () => {
  it('shows an owner everything', () => {
    const visible = visibleNav(OWNER).flatMap((g) => g.items)
    expect(visible).toHaveLength(allNavItems().length)
  })

  it('gives a temple_admin only their temples and bookings', () => {
    const groups = visibleNav(TEMPLE_ADMIN).map((g) => g.title)
    expect(groups).toEqual(['Overview', 'Temples', 'Bookings'])
  })

  it('keeps the devotee register away from a temple_admin', () => {
    // A temple clerk runs a temple. The register of every Nithara user, the
    // payment ledger and the operator list are not theirs to read.
    for (const path of [
      '/people/users',
      '/people/operators',
      '/bookings/payments',
      '/system/settings',
    ]) {
      expect(canAccess(itemForPath(path)!, TEMPLE_ADMIN)).toBe(false)
    }
  })

  it('gives a content_reviewer the feed but no temple editing', () => {
    expect(canAccess(itemForPath('/content/feed')!, REVIEWER)).toBe(true)
    expect(canAccess(itemForPath('/temples')!, REVIEWER)).toBe(false)
    expect(canAccess(itemForPath('/bookings')!, REVIEWER)).toBe(false)
  })

  it('lets support read but not administer', () => {
    expect(canAccess(itemForPath('/system/chat')!, SUPPORT)).toBe(true)
    expect(canAccess(itemForPath('/people/operators')!, SUPPORT)).toBe(false)
    expect(canAccess(itemForPath('/temples')!, SUPPORT)).toBe(false)
  })

  it('keeps the whole PEOPLE group owner-only', () => {
    // Engagement was pencilled in for `support` while it was a stub. Built, it
    // names individual devotees and their mobile numbers, and the route behind
    // it is owner-gated — so showing it to support would be the sidebar
    // promising a page the server refuses.
    for (const item of NAV.find((g) => g.title === 'People')!.items) {
      expect(canAccess(item, SUPPORT), item.path).toBe(false)
      expect(canAccess(item, TEMPLE_ADMIN), item.path).toBe(false)
      expect(canAccess(item, OWNER), item.path).toBe(true)
    }
  })

  it('shows every role a dashboard', () => {
    for (const roles of [OWNER, TEMPLE_ADMIN, REVIEWER, SUPPORT]) {
      expect(canAccess(itemForPath('/')!, roles)).toBe(true)
    }
  })

  it('shows nothing at all to an operator with no roles', () => {
    expect(visibleNav([])).toEqual([])
    expect(firstReachablePath([])).toBeUndefined()
  })

  it('hides a group entirely when none of its items are reachable', () => {
    // Not just empty — absent, so the sidebar has no orphan heading.
    expect(visibleNav(REVIEWER).map((g) => g.title)).not.toContain('Temples')
  })
})

describe('owner override', () => {
  it('satisfies every role, matching admin_auth.require_operator', () => {
    // The server treats an owner as holding every role. If this file disagreed,
    // the console would hide sections the owner is entitled to.
    for (const item of allNavItems()) {
      expect(canAccess(item, OWNER)).toBe(true)
    }
  })

  it('is not implied by holding all four named roles', () => {
    // Sanity check that `owner` is a real check, not emergent from the others.
    const everythingButOwner = ['temple_admin', 'content_reviewer', 'support']
    const ownerOnly = allNavItems().filter((i) => i.roles.length === 0)
    expect(ownerOnly.length).toBeGreaterThan(0)
    for (const item of ownerOnly) {
      expect(canAccess(item, everythingButOwner)).toBe(false)
    }
  })
})

describe('redirect target', () => {
  it('sends a temple_admin to their own first section', () => {
    expect(firstReachablePath(TEMPLE_ADMIN)).toBe('/')
  })

  it('never points anyone at a section they cannot reach', () => {
    for (const roles of [OWNER, TEMPLE_ADMIN, REVIEWER, SUPPORT]) {
      const target = firstReachablePath(roles)
      expect(target).toBeDefined()
      expect(canAccess(itemForPath(target!)!, roles)).toBe(true)
    }
  })
})

describe('the table itself', () => {
  it('has no duplicate paths', () => {
    const paths = allNavItems().map((i) => i.path)
    expect(new Set(paths).size).toBe(paths.length)
  })

  it('has a screen behind every route it declares', () => {
    // The placeholder that stood in for unbuilt sections is gone as of Part 13,
    // so a nav entry with no screen no longer degrades gracefully — it renders
    // "no such page" to whoever clicked it in the sidebar.
    for (const { path } of allRoutes()) {
      expect(SCREENS[path], `${path} has no screen`).toBeTruthy()
    }
  })

  it('declares a route for every screen', () => {
    // The other direction. A screen the table does not know about is a screen
    // with no guard: Guard resolves permissions by looking the path up here.
    const declared = new Set(allRoutes().map((r) => r.path))
    for (const path of Object.keys(SCREENS)) {
      expect(declared.has(path), `${path} is routed but not in the IA`).toBe(true)
    }
  })

  it('declares only roles the backend knows', () => {
    // admin/models.py ROLES. A typo here would silently deny everyone.
    const known = new Set(['owner', 'temple_admin', 'content_reviewer', 'support'])
    for (const item of allNavItems()) {
      for (const role of item.roles) expect(known.has(role)).toBe(true)
    }
  })

  it('routes every declared item, so no nav entry 404s', () => {
    for (const group of NAV) {
      for (const item of group.items) {
        expect(itemForPath(item.path)).toBe(item)
      }
    }
  })
})

describe('detail routes', () => {
  it('gives a detail page its section’s permissions', () => {
    // /temples/:templeId is never in the sidebar, so nothing else would notice
    // it being reachable by a role that cannot open the list it belongs to.
    expect(itemForPath('/temples/tsr-guruvayur')).toBe(itemForPath('/temples'))
    expect(canAccess(itemForPath('/temples/tsr-guruvayur')!, TEMPLE_ADMIN)).toBe(true)
    expect(canAccess(itemForPath('/temples/tsr-guruvayur')!, REVIEWER)).toBe(false)
  })

  it('does not let the pattern swallow a sibling section', () => {
    // `/temples/festivals` and `/temples/poojas` both match `/temples/:templeId`.
    // Resolving them to the editor would hand them the editor's roles, which is
    // not the same set — and would render the wrong screen besides.
    for (const path of ['/temples/festivals', '/temples/poojas', '/temples/partners']) {
      expect(itemForPath(path)?.path).toBe(path)
    }
  })

  it('leaves an unknown path unresolved rather than guessing', () => {
    expect(itemForPath('/nonsense')).toBeUndefined()
    expect(itemForPath('/temples/a/b')).toBeUndefined()
  })

  it('routes every child, and every route is guarded by a real item', () => {
    const routes = allRoutes()
    expect(routes.length).toBeGreaterThan(allNavItems().length)
    for (const { path, item } of routes) {
      expect(allNavItems()).toContain(item)
      expect(new Set(routes.map((r) => r.path)).has(path)).toBe(true)
    }
    expect(new Set(routes.map((r) => r.path)).size).toBe(routes.length)
  })
})
