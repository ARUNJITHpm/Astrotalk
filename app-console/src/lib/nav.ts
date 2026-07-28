// The sidebar information architecture, and the single source of truth for
// which roles may reach which section.
//
// Both the sidebar and the route guard read this table. That is the point:
// hiding a nav item is NOT access control, so the same declaration that decides
// what renders also decides what a typed-in URL reaches. Keeping them in two
// places is how a section ends up invisible but reachable.
//
// The real gate is the server's — every one of these paths is behind
// `require_operator(...)`, and a hand-crafted request gets a 403 no matter what
// this file says. This exists so a temple_admin sees a coherent tool instead of
// a wall of sections that error on click.
//
// Roles come from admin/models.py ROLES: owner, temple_admin, content_reviewer,
// support. An owner satisfies every role (admin_auth.require_operator), so
// `roles` here lists the NON-owner roles that also qualify.

import { matchPath } from 'react-router-dom'

export type Role = 'owner' | 'temple_admin' | 'content_reviewer' | 'support'

export interface NavItem {
  path: string
  label: string
  /** Non-owner roles allowed here. Empty = owner only. */
  roles: Role[]
  /** Rendered greyed with a "soon" marker; the route still resolves to a stub. */
  stub?: boolean
  /** One-line "what is this for", shown in the stub page. */
  blurb?: string
  /**
   * Routes that belong to this section but are not sidebar entries — a detail
   * page reached from its list, written as a react-router pattern
   * (`/temples/:templeId`). They inherit this item's roles.
   *
   * They are declared HERE rather than added straight to the router because
   * `Guard` decides what a path needs by looking the path up in this table. A
   * route the table does not know about would fall through the guard's
   * "not in the IA" branch and render for anyone signed in.
   */
  children?: string[]
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

export const NAV: NavGroup[] = [
  {
    title: 'Overview',
    items: [
      {
        path: '/',
        label: 'Dashboard',
        // Every operator gets a dashboard; its CONTENT narrows to their scope.
        roles: ['temple_admin', 'content_reviewer', 'support'],
      },
    ],
  },
  {
    title: 'Temples',
    items: [
      {
        path: '/temples',
        label: 'All temples',
        roles: ['temple_admin'],
        // The editor. `new` is spelled as a child of the same item so it is
        // guarded identically; the screen itself refuses a non-owner, because
        // adding a temple is a directory-wide decision.
        children: ['/temples/new', '/temples/:templeId'],
      },
      { path: '/temples/poojas', label: 'Pooja catalogue', roles: ['temple_admin'] },
      {
        path: '/temples/festivals',
        label: 'Festivals',
        roles: ['temple_admin'],
      },
      { path: '/temples/partners', label: 'Partners & QR', roles: [] },
    ],
  },
  {
    title: 'Bookings',
    items: [
      {
        path: '/bookings',
        label: 'Pooja bookings',
        roles: ['temple_admin'],
        children: ['/bookings/:bookingId'],
      },
      { path: '/bookings/worklist', label: 'Temple worklist', roles: ['temple_admin'] },
      { path: '/bookings/consults', label: 'Consults', roles: [] },
      { path: '/bookings/payments', label: 'Payments', roles: [] },
    ],
  },
  {
    title: 'People',
    items: [
      { path: '/people/users', label: 'Users', roles: [] },
      { path: '/people/astrologers', label: 'Astrologers', roles: [] },
      { path: '/people/operators', label: 'Operators', roles: [] },
      {
        path: '/people/engagement',
        label: 'Engagement',
        roles: ['support'],
        stub: true,
        blurb: 'Check-ins, streaks and milestones.',
      },
    ],
  },
  {
    title: 'Content',
    items: [
      { path: '/content/feed', label: 'App feed', roles: ['content_reviewer'] },
      {
        path: '/content/daily',
        label: 'Daily pack',
        roles: ['content_reviewer'],
        stub: true,
        blurb: 'The scheduled daily content pack. Two implementations exist and need deduping.',
      },
      {
        path: '/content/studio',
        label: 'Studio',
        roles: ['content_reviewer'],
        stub: true,
        blurb: 'On-demand reel scripts and episodes, posted by hand.',
      },
      {
        path: '/content/cards',
        label: 'Share cards',
        roles: ['content_reviewer'],
        stub: true,
        blurb: 'Rendered branded images and their /s/ landing pages.',
      },
    ],
  },
  {
    title: 'Astrology',
    items: [
      {
        path: '/astrology/panchangam',
        label: 'Panchangam',
        roles: ['support'],
        stub: true,
        blurb: 'Date explorer for the panchangam engine.',
      },
      {
        path: '/astrology/suggest',
        label: 'Temple suggest',
        roles: ['support'],
        stub: true,
        blurb: 'Tester for the concern → temple suggestion path.',
      },
    ],
  },
  {
    title: 'Channels',
    items: [
      {
        path: '/channels/whatsapp',
        label: 'WhatsApp sim',
        roles: [],
        stub: true,
        blurb: 'The existing /whatsapp simulator, carried over.',
      },
      {
        path: '/channels/notifications',
        label: 'Notifications',
        roles: [],
        stub: true,
        blurb: 'Nakshatram reminders and festival runs.',
      },
    ],
  },
  {
    title: 'System',
    items: [
      {
        path: '/system/integrations',
        label: 'Integrations',
        roles: [],
        stub: true,
        blurb: 'Health and live/mock status for every external service.',
      },
      {
        path: '/system/chat',
        label: 'Chat explorer',
        roles: ['support'],
        stub: true,
        blurb: 'Read-only chat history, for support.',
      },
      {
        path: '/system/tenants',
        label: 'Org tenants',
        roles: [],
        stub: true,
        blurb: 'White-label organisations.',
      },
      {
        path: '/system/settings',
        label: 'Settings',
        roles: [],
        stub: true,
        blurb: 'Service fee, admin token and role defaults.',
      },
    ],
  },
]

/** Whether `roles` may reach `item`. An owner may reach everything. */
export function canAccess(item: NavItem, roles: readonly string[]): boolean {
  if (roles.includes('owner')) return true
  return item.roles.some((r) => roles.includes(r))
}

/** Groups with at least one reachable item, each filtered to those items. */
export function visibleNav(roles: readonly string[]): NavGroup[] {
  return NAV.map((group) => ({
    ...group,
    items: group.items.filter((item) => canAccess(item, roles)),
  })).filter((group) => group.items.length > 0)
}

/** Every declared item, flattened — the sidebar's source. */
export function allNavItems(): NavItem[] {
  return NAV.flatMap((g) => g.items)
}

/**
 * Every routable path, sidebar entries and their detail pages alike, each
 * paired with the item whose permissions it answers to. The router builds from
 * this, so a route cannot exist without a guard.
 */
export function allRoutes(): { path: string; item: NavItem }[] {
  return allNavItems().flatMap((item) => [
    { path: item.path, item },
    ...(item.children ?? []).map((path) => ({ path, item })),
  ])
}

/**
 * The item a path maps to, or undefined if the path is not in the IA.
 *
 * Exact matches win over patterns. `/temples/festivals` is its own section AND
 * would match `/temples/:templeId`; resolving it to the editor would hand it
 * the wrong permissions — and, since the two differ, quietly the wrong ones.
 */
export function itemForPath(path: string): NavItem | undefined {
  const routes = allRoutes()
  return (
    routes.find((r) => r.path === path)?.item ??
    routes.find((r) => r.path.includes(':') && matchPath(r.path, path))?.item
  )
}

/**
 * Where to send an operator who has no business on the page they asked for.
 * Their first reachable item, so a temple_admin landing on /people/users is
 * redirected somewhere useful rather than to a dashboard they cannot see.
 */
export function firstReachablePath(roles: readonly string[]): string | undefined {
  return visibleNav(roles)[0]?.items[0]?.path
}
