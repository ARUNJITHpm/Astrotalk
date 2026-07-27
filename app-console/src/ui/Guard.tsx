// Route-level access control.
//
// The sidebar already hides what a role cannot use, but hiding is not access
// control — a bookmark, a typed URL or a back button all skip the sidebar
// entirely. This guard reads the SAME table (lib/nav.ts) so the two can never
// disagree.
//
// This is defence in depth, not the defence. Every one of these pages talks to
// an endpoint behind `require_operator(...)`, and the server refuses regardless
// of what the client rendered. What this buys is an honest message instead of a
// page that mounts, fires a request and collapses into an error toast.

import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../lib/auth'
import { canAccess, firstReachablePath, itemForPath } from '../lib/nav'

export function Guard({ children }: { children: React.ReactNode }) {
  const { me } = useAuth()
  const location = useLocation()
  if (!me) return null

  const item = itemForPath(location.pathname)
  // Not in the IA at all — let the router's own 404 handle it.
  if (!item) return <>{children}</>

  if (!canAccess(item, me.roles)) {
    const fallback = firstReachablePath(me.roles)
    // Redirect rather than render a bare 403 when there is somewhere to go, so
    // a temple_admin who clicks a stale link lands on their own work.
    if (fallback && fallback !== location.pathname) {
      return <Navigate to={fallback} replace />
    }
    return (
      <section className="page">
        <h1 className="page__title">Not available to your role</h1>
        <p className="page__lede">
          Your account does not have access to this section. If that looks wrong,
          ask the owner to review your roles.
        </p>
      </section>
    )
  }

  return <>{children}</>
}
