import { useLocation, useNavigate } from 'react-router-dom'
import { Icon } from './Icon'
import { useT } from '../i18n'

// The floating bottom tab bar. Buttons (not links) so the prototype's
// `.nav button` styling applies verbatim; navigation is programmatic.
const TABS: Array<{ to: string; s: string; key: string; icon: string }> = [
  { to: '/', s: 'home', key: 'nav_home', icon: 'i-home' },
  { to: '/poojas', s: 'poojas', key: 'nav_poojas', icon: 'i-lamp' },
  { to: '/astro', s: 'astro', key: 'nav_astro', icon: 'i-sparkle' },
  { to: '/profile', s: 'profile', key: 'nav_profile', icon: 'i-user' },
]

export function TabBar() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const { t } = useT()
  return (
    <nav className="nav" id="nav" aria-label="Main">
      {TABS.map(({ to, s, key, icon }) => {
        const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
        return (
          <button
            key={to}
            data-s={s}
            aria-current={active ? 'page' : undefined}
            onClick={() => navigate(to)}
          >
            <Icon name={icon} />
            <span>{t(key)}</span>
          </button>
        )
      })}
    </nav>
  )
}
