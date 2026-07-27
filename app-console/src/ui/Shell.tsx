// The signed-in frame: role-aware sidebar on the left, routed page on the right.

import { NavLink, Outlet } from 'react-router-dom'

import { useAuth } from '../lib/auth'
import { visibleNav } from '../lib/nav'

function roleLabel(me: { is_owner: boolean; roles: string[]; temple_ids: string[] }) {
  if (me.is_owner) return 'Owner'
  const named = me.roles.map((r) => r.replace(/_/g, ' ')).join(', ') || 'No role'
  // A scoped operator should always be able to see WHICH temples they hold,
  // because it is the difference between "this list is empty" and "this list is
  // not mine to see".
  return me.temple_ids.length
    ? `${named} · ${me.temple_ids.length} temple${me.temple_ids.length > 1 ? 's' : ''}`
    : named
}

export function Shell() {
  const { me, signOut } = useAuth()
  if (!me) return null

  const groups = visibleNav(me.roles)

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="sidebar__brand">
          <span className="sidebar__mark">◈</span>
          <span>Nithara Console</span>
        </div>

        <nav className="sidebar__nav">
          {groups.map((group) => (
            <div className="navgroup" key={group.title}>
              <p className="navgroup__title">{group.title}</p>
              {group.items.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === '/'}
                  className={({ isActive }) =>
                    [
                      'navitem',
                      isActive ? 'navitem--on' : '',
                      item.stub ? 'navitem--stub' : '',
                    ]
                      .filter(Boolean)
                      .join(' ')
                  }
                >
                  {item.label}
                  {item.stub && <span className="navitem__soon">soon</span>}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar__foot">
          <p className="sidebar__who">{roleLabel(me)}</p>
          <button className="btn btn--ghost" onClick={() => void signOut()}>
            Sign out
          </button>
        </div>
      </aside>

      <main className="content">
        <Outlet />
      </main>
    </div>
  )
}
