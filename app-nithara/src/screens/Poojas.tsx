import { useState } from 'react'
import { Icon } from '../components/Icon'
import { toast } from '../components/Toast'
import { useT } from '../i18n'
import { useHomeTempleId } from '../lib/homeTemple'
import { nakName } from '../lib/nakshatrams'
import {
  useBookings,
  useMembers,
  useNakshatramNext,
  useTemple,
  useTemplePoojas,
} from '../api/hooks'
import { BookingSheet, type BookTarget } from '../features/booking/BookingSheet'
import { leadLabel } from '../lib/poojaLock'
import { MemberSheet } from '../features/member/MemberSheet'
import type { Member } from '../api/types'

const money = (n: number) => '₹' + n.toLocaleString('en-IN')

export default function Poojas() {
  const { t: T, lang } = useT()
  const homeId = useHomeTempleId()
  const temple = useTemple(homeId).data
  const { data: members = [], isLoading: membersLoading } = useMembers()
  const bookingsQuery = useBookings()
  const bookings = bookingsQuery.data ?? []

  const naks = [...new Set(members.map((m) => m.nak).filter((n): n is number => n != null))]
  const starDays = useNakshatramNext(naks).data ?? []
  const soonest = starDays[0]
  const starOwner: Member | undefined = soonest
    ? members.find((m) => m.nak === soonest.nakshatram_index)
    : undefined

  const [target, setTarget] = useState<BookTarget | null>(null)
  const [editing, setEditing] = useState<Member | 'new' | null>(null)

  const templeName = temple ? (lang === 'ml' ? temple.ml : temple.en) : ''
  const catalogue = useTemplePoojas(homeId, soonest?.nakshatram_index).data
  const poojas = catalogue?.poojas ?? []

  function book(poojaKey: string, poojaName: string, amount: number, when?: string, memberId?: number) {
    if (!homeId) return
    setTarget({ templeId: homeId, templeName, poojaKey, poojaName, amount, when, memberId })
  }

  /** The star-day CTA books the temple's FIRST catalogue offering at the price
   *  the server quoted — never a hardcoded key/amount, which would 404 (or
   *  misprice) at any temple with its own catalogue. */
  function bookForStar() {
    const first = poojas.find((p) => !p.locked) ?? poojas[0]
    if (!first || !soonest) return
    book(
      first.key,
      lang === 'ml' ? first.name_ml : first.name,
      first.amount,
      fmtDate(soonest.date),
      starOwner?.id,
    )
  }

  const fmtDate = (iso: string) =>
    new Date(iso).toLocaleDateString(lang === 'ml' ? 'ml-IN' : 'en-IN', { weekday: 'short', day: 'numeric', month: 'short' })

  return (
    <section className="screen" data-active id="s-poojas">
      <header className="top">
        <div className="g">
          <div className="nm">{T('nav_poojas')}</div>
        </div>
      </header>

      {!homeId ? (
        <p style={{ padding: 'var(--s5)', color: 'var(--muted)' }}>{T('obP')}</p>
      ) : (
        <>
          {/* Star countdown */}
          {soonest ? (
            <div className="starcard">
              <svg className="sg" aria-hidden="true">
                <use href="#i-star" />
              </svg>
              <div className="kk">
                <Icon name="i-star" />
                {starOwner?.name || T('starKicker')}
              </div>
              {/* The API returns the Malayalam name; render it in the reader's
                  language via the shared index→name table. */}
              <h2>{nakName(soonest.nakshatram_index, lang) || soonest.nakshatram}</h2>
              <div className="when">{fmtDate(soonest.date)}</div>
              <div className="cd">
                <div className="box">
                  <b>{soonest.days_until}</b>
                  <span>{T('cdDays')}</span>
                </div>
                <div className="box">
                  <b>{fmtDate(soonest.date)}</b>
                  <span>{T('cdDate')}</span>
                </div>
              </div>
              <button className="btn btn-pri btn-block" onClick={bookForStar} disabled={!poojas.length}>
                <Icon name="i-lamp" cls="ic sm" />
                {T('bookForStar')}
              </button>
            </div>
          ) : (
            <button
              className="setup"
              style={{ margin: 'var(--s5)' }}
              /* Wait for members to load — otherwise this opens "Add someone"
                 (relation = Mother) instead of editing the user's own row. */
              disabled={membersLoading}
              onClick={() => setEditing(members.find((m) => m.self) ?? 'new')}
            >
              <div className="si">
                <Icon name="i-sparkle" />
              </div>
              <div className="st">
                <b>{T('nakNotSet')}</b>
                <span>{T('chartNotSetS')}</span>
              </div>
            </button>
          )}

          {/* Catalogue with lead-time locks */}
          <div className="sec">
            <h2>
              {T('bookAt')} {templeName}
            </h2>
          </div>
          {poojas.map((p) => (
            <div className={`pjrow ${p.locked ? 'locked' : ''}`} key={p.key} style={{ margin: '0 var(--s5) 10px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <span className="pi">
                <Icon name="i-lamp" />
              </span>
              <span className="pm" style={{ flex: 1 }}>
                <b>{lang === 'ml' ? p.name_ml : p.name}</b>
                <span className={p.locked ? 'warn' : ''}>
                  {(() => {
                    const label = leadLabel(p)
                    return label.count != null ? T(label.key, { count: label.count }) : T(label.key)
                  })()}
                </span>
              </span>
              <span className="rt" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <b>{money(p.amount)}</b>
                {!p.locked && (
                  <button
                    className="btn btn-pri"
                    onClick={() =>
                      book(
                        p.key,
                        lang === 'ml' ? p.name_ml : p.name,
                        p.amount,
                        soonest ? fmtDate(soonest.date) : undefined,
                        starOwner?.id,
                      )
                    }
                  >
                    {T('book')}
                  </button>
                )}
              </span>
            </div>
          ))}

          {/* Your bookings */}
          <div className="sec">
            <h2>
              {T('yourBookings')}
              <span className="ml">{T('upcoming')}</span>
            </h2>
          </div>
          {bookings.length ? (
            bookings.map((b) => (
              <div className="bkrow" key={b.id} style={{ margin: '0 var(--s5) 9px' }}>
                <span className="bi">
                  <Icon name="i-lamp" />
                </span>
                <span className="bm">
                  <b>
                    {b.pooja_name}
                    {b.member_name ? ` · ${b.member_name}` : ''}
                  </b>
                  <span>{b.when || fmtDate(b.created_at)}</span>
                </span>
                <span className={`pill ${b.state === 'ok' ? 'pill-open' : 'pill-def'}`}>
                  <Icon name={b.state === 'ok' ? 'i-check' : 'i-clock'} />
                  {T(b.state === 'ok' ? 'confirmed' : 'pending')}
                </span>
              </div>
            ))
          ) : (
            <div className="emptyline" style={{ padding: '0 var(--s5)', color: 'var(--muted)' }}>
              {/* A failed load must not masquerade as "nothing booked yet". */}
              {bookingsQuery.isError ? T('loadFailed') : T('noPast')}
            </div>
          )}
        </>
      )}

      <BookingSheet target={target} onClose={() => setTarget(null)} onAddMember={() => setEditing('new')} />
      <MemberSheet editing={editing} onClose={() => setEditing(null)} />
    </section>
  )
}
