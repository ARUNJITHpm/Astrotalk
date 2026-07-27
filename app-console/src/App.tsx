// Routing skeleton for the whole console.
//
// Every section in the IA gets a route now, even the ones later Parts build, so
// the sidebar has nowhere dead to point and each stub is already behind the
// same guard its real screen will use. Routes are GENERATED from lib/nav.ts —
// a hand-written <Route> list is how a path ends up in the router but not the
// nav table (or worse, in the router without a guard).

import { Navigate, Route, Routes } from 'react-router-dom'

import { useAuth } from './lib/auth'
import { allNavItems } from './lib/nav'
import { Dashboard } from './ui/Dashboard'
import { Guard } from './ui/Guard'
import { Login } from './ui/Login'
import { Shell } from './ui/Shell'
import { Stub } from './ui/Stub'

/** Real screens, keyed by path. Anything absent renders a stub. */
const SCREENS: Record<string, React.ComponentType> = {
  '/': Dashboard,
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
        {allNavItems().map((item) => {
          const Screen = SCREENS[item.path] ?? Stub
          return (
            <Route
              key={item.path}
              path={item.path}
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
