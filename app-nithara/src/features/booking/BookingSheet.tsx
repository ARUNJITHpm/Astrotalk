import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { apiPost } from '../../api/client'
import { useMembers } from '../../api/hooks'
import { nakName } from '../../lib/nakshatrams'
import { useT } from '../../i18n'
import type { Booking } from '../../api/types'

const money = (n: number) => '₹' + n.toLocaleString('en-IN')
const FEE = 15 // ₹, matches the backend service fee

export interface BookTarget {
  templeId: string
  templeName: string
  poojaKey: string
  poojaName: string
  amount: number // rupees (display); the server prices the order
  when?: string
  /** Whose star day this booking is for — pre-selects the who-for chip so a
   *  "book for Amma's star" CTA doesn't silently record it under the account
   *  holder's name. */
  memberId?: number
}

export function BookingSheet({
  target,
  onClose,
  onAddMember,
}: {
  target: BookTarget | null
  onClose: () => void
  onAddMember: () => void
}) {
  const { t: T, lang } = useT()
  const qc = useQueryClient()
  const { data: members = [] } = useMembers()
  const [whoId, setWhoId] = useState<number | null>(null)
  const [done, setDone] = useState<{ ref: string; paid: boolean } | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const self = members.find((m) => m.self)
  // The CTA's member (e.g. whoever's star day this is) wins, then an explicit
  // pick, then the account holder.
  const who = members.find((m) => m.id === (whoId ?? target?.memberId)) ?? self ?? null
  const total = target ? target.amount + FEE : 0

  async function confirm() {
    if (!target || !who) return
    setBusy(true)
    setError(null)
    let booking: Booking
    try {
      booking = await apiPost<Booking>('/bookings', {
        temple_id: target.templeId,
        pooja_key: target.poojaKey,
        member_id: who.id,
        member_name: who.name,
        member_nak: who.nak,
        when: target.when ?? '',
      })
    } catch {
      setBusy(false)
      setError(T('bookFailed'))
      return
    }

    // The booking now EXISTS server-side, so from here we always show its
    // reference — never silently drop it (a retry would double-book).
    let paid = false
    try {
      // Dev/mock only: capture immediately so the booking confirms. On a live
      // build the order_id + razorpay_key_id drive Razorpay checkout (Part 9),
      // and the booking stays "pending" until the webhook captures it.
      if (booking.mock && booking.order_id) {
        await apiPost(`/commerce/orders/${booking.order_id}/mock-pay`)
        paid = true
      }
    } catch {
      paid = false
    }
    qc.invalidateQueries({ queryKey: ['bookings'] })
    qc.invalidateQueries({ queryKey: ['stats'] })
    qc.invalidateQueries({ queryKey: ['milestones'] })
    setDone({ ref: booking.ref, paid })
    setBusy(false)
  }

  function close() {
    setDone(null)
    setWhoId(null)
    setError(null)
    onClose()
  }

  return (
    <Sheet open={!!target} onClose={close}>
      {done ? (
        <>
          <div className="sheet-bar">
            <button className="iconbtn" onClick={close} aria-label={T('a11yClose')}>
              <Icon name="i-close" />
            </button>
            <h2>{done.paid ? T('confirmedT') : T('pending')}</h2>
          </div>
          <div className="sheet-scroll">
            <div className="done">
              <Icon name="i-lamp" cls="ic lamp" />
              {/* Only claim "all set" when payment actually completed; otherwise
                  say plainly that it is awaiting payment. */}
              <h2>{done.paid ? T('allSet') : T('pending')}</h2>
              <p>
                {target?.poojaName} · {who?.name}
              </p>
              {!done.paid && <p>{T('bookPendingNote')}</p>}
              <div className="ref">
                {T('refWord')} · {done.ref}
              </div>
            </div>
          </div>
          <div className="dcta">
            <button className="btn btn-pri btn-block" onClick={close}>
              {T('done')}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="sheet-bar">
            <button className="iconbtn" onClick={close} aria-label={T('a11yBack')}>
              <Icon name="i-back" />
            </button>
            <h2>{T('reviewBooking')}</h2>
          </div>
          <div className="sheet-scroll">
            <div className="whorow">
              <div className="lb">{T('whoFor')}</div>
              <div className="whochips">
                {members.map((m) => (
                  <button
                    key={m.id}
                    className="whochip"
                    aria-pressed={m.id === who?.id}
                    onClick={() => setWhoId(m.id)}
                  >
                    <span className="in">{(m.name || '?').charAt(0).toUpperCase()}</span>
                    <span className="wn">
                      {m.name || T('addYourName')}
                      <small>{m.nak != null ? nakName(m.nak, lang) : T('nakUnset')}</small>
                    </span>
                  </button>
                ))}
                <button className="whochip add" onClick={onAddMember}>
                  <Icon name="i-user" cls="ic sm" />
                  {T('addSomeone')}
                </button>
              </div>
            </div>
            <div className="rvcard" style={{ marginTop: 14 }}>
              <div className="rvrow">
                <span className="k">{T('rPooja')}</span>
                <span className="v">{target?.poojaName}</span>
              </div>
              <div className="rvrow">
                <span className="k">{T('rTemple')}</span>
                <span className="v">{target?.templeName}</span>
              </div>
              <div className="rvrow">
                <span className="k">{T('rDate')}</span>
                {/* Never invent a date on a payment screen — say it's to be
                    confirmed when no star day drove this booking. */}
                <span className="v">{target?.when || T('dateTbc')}</span>
              </div>
              <div className="rvrow">
                <span className="k">{T('rFee')}</span>
                <span className="v">{money(FEE)}</span>
              </div>
              <div className="rvrow total">
                <span className="k">{T('rTotal')}</span>
                <span className="v">{money(total)}</span>
              </div>
            </div>
            <div className="rvnote">
              <Icon name="i-shield" cls="ic sm" />
              <span>{T('rNote')}</span>
            </div>
          </div>
          <div className="dcta" style={{ flexDirection: 'column', gap: 8 }}>
            {error && (
              <p style={{ color: 'var(--kumkum)', fontSize: 13, textAlign: 'center', margin: 0 }} role="alert">
                {error}
              </p>
            )}
            <button className="btn btn-pri btn-block" disabled={busy || !who} onClick={confirm}>
              {T('payConfirm')} {money(total)}
            </button>
          </div>
        </>
      )}
    </Sheet>
  )
}
