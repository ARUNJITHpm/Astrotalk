// The auto-advancing promo rail from the prototype.
//
// It advances on a timer, and everything awkward about this component is a
// consequence of that: a carousel that keeps moving while somebody is reading,
// or reading it aloud, or dragging it, is worse than no carousel. So it stops
// on interaction, stops when the tab is hidden, and does not start at all if the
// reader has asked for reduced motion.

import { useEffect, useRef, useState } from 'react'

import { Icon } from '../../components/Icon'
import type { Promo } from '../../lib/promos'

const ADVANCE_MS = 6000

export function PromoRail({
  promos,
  onAct,
}: {
  promos: Promo[]
  onAct: (promo: Promo) => void
}) {
  const railRef = useRef<HTMLDivElement>(null)
  const [index, setIndex] = useState(0)
  // Set once a person touches the rail. Auto-advance never resumes: they are
  // driving now, and yanking the view away mid-read is the exact complaint
  // carousels earn.
  const [taken, setTaken] = useState(false)

  // Keep the dots honest while scrolling by hand.
  useEffect(() => {
    const rail = railRef.current
    if (!rail) return
    const onScroll = () => {
      const card = rail.firstElementChild as HTMLElement | null
      if (!card) return
      const step = card.offsetWidth + 10
      setIndex(Math.round(rail.scrollLeft / Math.max(step, 1)))
    }
    rail.addEventListener('scroll', onScroll, { passive: true })
    return () => rail.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (taken || promos.length < 2) return
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

    const tick = () => {
      // A hidden tab would otherwise pile up advances and jump several cards
      // the moment somebody comes back.
      if (document.hidden) return
      const rail = railRef.current
      const card = rail?.firstElementChild as HTMLElement | null
      if (!rail || !card) return
      setIndex((prev) => {
        const next = (prev + 1) % promos.length
        rail.scrollTo({ left: next * (card.offsetWidth + 10), behavior: 'smooth' })
        return next
      })
    }
    const timer = window.setInterval(tick, ADVANCE_MS)
    return () => window.clearInterval(timer)
  }, [taken, promos.length])

  if (!promos.length) return null

  return (
    <div className="promowrap">
      <div
        className="promorail"
        ref={railRef}
        onPointerDown={() => setTaken(true)}
        onKeyDown={() => setTaken(true)}
      >
        {promos.map((promo) => (
          <button
            key={promo.key}
            className={`promo ${promo.cls}`}
            onClick={() => onAct(promo)}
          >
            <span className="pglyph" aria-hidden="true">
              <Icon name={promo.glyph} />
            </span>
            <span className={promo.hot ? 'ptag hot' : 'ptag'}>{promo.tag}</span>
            {promo.count != null && (
              <span className="pcount">
                <b>{promo.count}</b>
              </span>
            )}
            <span className="pbody">
              <b>{promo.title}</b>
              <span>{promo.sub}</span>
            </span>
            <span className="pcta">{promo.cta}</span>
          </button>
        ))}
      </div>
      {promos.length > 1 && (
        <div className="promodots" aria-hidden="true">
          {promos.map((promo, i) => (
            <i key={promo.key} className={i === index ? 'on' : undefined} />
          ))}
        </div>
      )}
    </div>
  )
}
