// Routing skeleton for the whole console.
//
// Routes are GENERATED from lib/nav.ts — a hand-written <Route> list is how a
// path ends up in the router but not the nav table, or worse, in the router
// without a guard.
//
// Every declared route now resolves to a real screen. The placeholder that
// stood in for the unbuilt sections through Parts 8-12 is gone, and a test
// pins the pairing: a sidebar entry with no screen behind it would otherwise
// render as "no such page" to whoever clicked it.

import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './lib/auth'
import { allRoutes } from './lib/nav'
import { Dashboard } from './ui/Dashboard'
import { Guard } from './ui/Guard'
import { Login } from './ui/Login'
import { Shell } from './ui/Shell'
import { BookingDetail } from './ui/bookings/BookingDetail'
import { BookingQueue } from './ui/bookings/BookingQueue'
import { Consults } from './ui/bookings/Consults'
import { Payments } from './ui/bookings/Payments'
import { Worklist } from './ui/bookings/Worklist'
import { Panchangam } from './ui/astrology/Panchangam'
import { TempleSuggest } from './ui/astrology/TempleSuggest'
import { Notifications } from './ui/channels/Notifications'
import { WhatsAppSim } from './ui/channels/WhatsAppSim'
import { AppFeed } from './ui/content/AppFeed'
import { DailyPack } from './ui/content/DailyPack'
import { ShareCards } from './ui/content/ShareCards'
import { Studio } from './ui/content/Studio'
import { Astrologers } from './ui/people/Astrologers'
import { Engagement } from './ui/people/Engagement'
import { Operators } from './ui/people/Operators'
import { UserDetail } from './ui/people/UserDetail'
import { UserList } from './ui/people/UserList'
import { ChatExplorer } from './ui/system/ChatExplorer'
import { Integrations } from './ui/system/Integrations'
import { Settings } from './ui/system/Settings'
import { Tenants } from './ui/system/Tenants'
import { Festivals } from './ui/temples/Festivals'
import { Partners } from './ui/temples/Partners'
import { PoojaCatalogue } from './ui/temples/PoojaCatalogue'
import { TempleEditor } from './ui/temples/TempleEditor'
import { TempleList } from './ui/temples/TempleList'

/** Every screen, keyed by the path in lib/nav.ts. Exported so a test can
 *  check the two lists agree. */
export const SCREENS: Record<string, React.ComponentType> = {
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
  '/content/feed': AppFeed,
  '/content/daily': DailyPack,
  '/content/studio': Studio,
  '/content/cards': ShareCards,
  '/astrology/panchangam': Panchangam,
  '/astrology/suggest': TempleSuggest,
  '/channels/whatsapp': WhatsAppSim,
  '/channels/notifications': Notifications,
  '/system/integrations': Integrations,
  '/system/chat': ChatExplorer,
  '/system/tenants': Tenants,
  '/system/settings': Settings,
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
          const Screen = SCREENS[path] ?? NotFound
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
