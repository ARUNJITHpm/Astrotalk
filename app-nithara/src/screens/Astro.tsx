import { useT } from '../i18n'

// Part 5 shell — real Astro tab (Nithara chat, tools, astrologers) in Part 8.
export default function Astro() {
  const { t } = useT()
  return (
    <section className="screen" data-active id="s-astro">
      <header className="top">
        <div className="g">
          <div className="nm">{t('nav_astro')}</div>
        </div>
      </header>
    </section>
  )
}
