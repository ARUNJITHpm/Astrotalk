import { useQuery } from '@tanstack/react-query'
import { apiGet } from '../api/client'
import type { Temple } from '../api/types'
import { toggleLang, useT } from '../i18n'
import { Icon } from '../components/Icon'

// Part 5 shell: the real Home (My Temple hero, promo rail, nearby, map) lands in
// Part 6. For now it proves the plumbing — brand row, language toggle, and a
// live health call to the backend's public /temples endpoint.
export default function Home() {
  const { lang } = useT()
  const health = useQuery({
    queryKey: ['temples', 'health'],
    queryFn: () => apiGet<Temple[]>('/temples?limit=200'),
    retry: false,
  })

  const status = health.isLoading
    ? 'Connecting…'
    : health.isError
      ? 'Backend offline'
      : `Backend OK — ${health.data?.length ?? 0} temples`

  return (
    <section className="screen" data-active id="s-home">
      <header className="hometop">
        <div className="brandrow">
          <span className="mark">
            <Icon name="i-lamp" />
          </span>
          <span className="wordmark">Nithara</span>
          <button className="iconbtn lang" onClick={toggleLang} aria-label="Language">
            <Icon name="i-globe" cls="ic sm" />
            <b>{lang === 'en' ? 'ML' : 'EN'}</b>
          </button>
        </div>
      </header>

      <p style={{ padding: 'var(--s5)', color: 'var(--muted)', fontSize: 13 }}>{status}</p>
    </section>
  )
}
