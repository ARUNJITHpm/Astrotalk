// Routing skeleton for the whole console.
//
// Every section in the IA gets a route now, even the ones later Parts build, so
// the sidebar has nowhere dead to point and each stub is already behind the
// same guard its real screen will use. Routes are GENERATED from lib/nav.ts —
// a hand-written <Route> list is how a path ends up in the router but not the
// nav table (or worse, in the router without a guard).

import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './lib/auth'
import { allRoutes } from './lib/nav'
import { Dashboard } from './ui/Dashboard'
import { Guard } from './ui/Guard'
import { Login } from './ui/Login'
import { Shell } from './ui/Shell'
import { Stub } from './ui/Stub'
import { BookingDetail } from './ui/bookings/BookingDetail'
import { BookingQueue } from './ui/bookings/BookingQueue'
import { Consults } from './ui/bookings/Consults'
import { Payments } from './ui/bookings/Payments'
import { Worklist } from './ui/bookings/Worklist'
import { Astrologers } from './ui/people/Astrologers'
import { Engagement } from './ui/people/Engagement'
import { Operators } from './ui/people/Operators'
import { UserDetail } from './ui/people/UserDetail'
import { UserList } from './ui/people/UserList'
import { Festivals } from './ui/temples/Festivals'
import { Partners } from './ui/temples/Partners'
import { PoojaCatalogue } from './ui/temples/PoojaCatalogue'
import { TempleEditor } from './ui/temples/TempleEditor'
import { TempleList } from './ui/temples/TempleList'

/** Real screens, keyed by path. Anything absent renders a stub. */
const SCREENS: Record<string, React.ComponentType> = {
  '/': Dashboard,
  '/temples': TempleList,
  '/temples/new': TempleEditor,
  '/temples/:templeId': TempleEditor,
  '/temples/poojas': PoojaCatalogue,
  '/temples/festivals': Festivals,
  '/temples/partners': Partners,
  '/bookings': BookingQueue,
  '/bookings/:bookingId': BookingDetail,
  '/bookings/worklist': Worklist,
  '/bookings/consults': Consults,
  '/bookings/payments': Payments,
  '/people/users': UserList,
  '/people/users/:userId': UserDetail,
  '/people/astrologers': Astrologers,
  '/people/operators': Operators,
  '/people/engagement': Engagement,
}

function NotFound() {
  return (
    <section className="page">
      <h1 className="page__title">No such page</h1>
      <p className="page__lede">That address is not part of the console.</p>
    </section>
  )
}

export default function App() {
  const { me, loading } = useAuth()

  // Render nothing until the stored token has been checked. Showing the login
  // form first would flash it at an operator who is already signed in.
  if (loading) {
    return (
      <div className="boot" role="status" aria-live="polite">
        Loading…
      </div>
    )
  }

  if (!me) return <Login />

  return (
    <Routes>
      <Route element={<Shell />}>
        {allRoutes().map(({ path }) => {
          const Screen = SCREENS[path] ?? Stub
          return (
            <Route
              key={path}
              path={path}
              element={
                <Guard>
                  <Screen />
                </Guard>
              }
            />
          )
        })}
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}
