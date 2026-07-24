import { useT } from '../i18n'

// Part 5 shell — real Poojas tab (star countdown, catalogue, bookings) in Part 7.
export default function Poojas() {
  const { t } = useT()
  return (
    <section className="screen" data-active id="s-poojas">
      <header className="top">
        <div className="g">
          <div className="nm">{t('nav_poojas')}</div>
        </div>
      </header>
    </section>
  )
}
