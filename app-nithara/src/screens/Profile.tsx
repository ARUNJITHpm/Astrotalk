import { useT } from '../i18n'

// Part 5 shell — real Profile tab (chart, bookings, milestones, family) in Part 8.
export default function Profile() {
  const { t } = useT()
  return (
    <section className="screen" data-active id="s-profile">
      <header className="top">
        <div className="g">
          <div className="nm">{t('nav_profile')}</div>
        </div>
      </header>
    </section>
  )
}
