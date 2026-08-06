import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { apiGet, apiPost } from '../../api/client'
import { useMembers, useTemplePoojas } from '../../api/hooks'
import { nakName } from '../../lib/nakshatrams'
import { openCheckout } from '../../lib/razorpay'
import { useT } from '../../i18n'
import type { Booking } from '../../api/types'

const money = (n: number) => '₹' + n.toLocaleString('en-IN')
const rupees = (paise: number) => paise / 100

/** The fee to assume while the catalogue is still loading. Only ever shown for
 *  the moment before the real figure arrives, and never used to charge: the
 *  server prices the order from its own settings row. */
const FEE_FALLBACK_PAISE = 1500

/** How a booking attempt ended, from the server's point of view where we have
 *  one. `received` exists because "Razorpay says paid" and "our booking is
 *  confirmed" are two different facts. */
interface Outcome {
  ref: string
  status: 'paid' | 'received' | 'pending'
  /** What to say about how it ended, when "pending" alone is not enough — a
   *  declined card and a closed checkout window are both pending and want
   *  different words. Carried on the outcome because `error` below belongs to
   *  the review screen, which we have already left by the time this is known. */
  note?: string
}

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
  // The fee comes from the same catalogue the price came from, not from a
  // constant here. It was hardcoded to 15, which stopped being true the moment
  // the console could change it — and a total shown on a payment screen that
  // differs from the amount charged is not a rounding problem.
  const { data: catalogue } = useTemplePoojas(target?.templeId)
  const [whoId, setWhoId] = useState<number | null>(null)
  const [done, setDone] = useState<Outcome | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const self = members.find((m) => m.self)
  // The CTA's member (e.g. whoever's star day this is) wins, then an explicit
  // pick, then the account holder.
  const who = members.find((m) => m.id === (whoId ?? target?.memberId)) ?? self ?? null
  const feePaise = catalogue?.service_fee_paise ?? FEE_FALLBACK_PAISE
  const total = target ? target.amount + rupees(feePaise) : 0

  /**
   * Ask the server whether this booking is actually paid.
   *
   * Checkout's own callback says Razorpay took the money; our `state` flips to
   * `ok` only when the signed webhook lands. Those are different facts, usually
   * a second or two apart. So we re-read rather than assert — and if the
   * webhook has not arrived yet we say "received", not "confirmed".
   */
  async function serverSaysPaid(ref: string): Promise<boolean> {
    try {
      const rows = await apiGet<Booking[]>('/bookings')
      return rows.find((b) => b.ref === ref)?.state === 'ok'
    } catch {
      return false
    }
  }

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
    let status: Outcome['status'] = 'pending'
    let note: string | undefined
    try {
      if (booking.mock && booking.order_id) {
        // Dev/mock: capture immediately so the flow completes with no keys.
        // mock-pay 404s on a live deployment, so this cannot fire there.
        await apiPost(`/commerce/orders/${booking.order_id}/mock-pay`)
        status = 'paid'
      } else if (booking.order_id && booking.razorpay_key_id) {
        const outcome = await openCheckout({
          keyId: booking.razorpay_key_id,
          orderId: booking.order_id,
          // The server's figure, not ours — it created the order for exactly
          // this, so the two cannot drift.
          amountPaise: booking.total_paise,
          description: `${booking.pooja_name} · ${target.templeName}`,
          // Name only. The account holder's mobile is not fetched anywhere in
          // this app, and adding a request for it to save one keystroke on a
          // payment screen is not a trade worth making — Razorpay asks.
          prefill: { name: who.name || self?.name },
        })
        if (outcome.kind === 'paid') {
          status = (await serverSaysPaid(booking.ref)) ? 'paid' : 'received'
        } else if (outcome.kind === 'failed') {
          note = T('payFailed')
        } else if (outcome.kind === 'unavailable') {
          note = T('payUnavailable')
        }
        // 'dismissed' keeps the default note: they closed it on purpose, and
        // "awaiting payment" is exactly right.
      }
      // No order and not mocked: payments are not configured on this
      // deployment. The booking stands, unpaid, and says so.
    } catch {
      status = 'pending'
    }
    qc.invalidateQueries({ queryKey: ['bookings'] })
    qc.invalidateQueries({ queryKey: ['stats'] })
    qc.invalidateQueries({ queryKey: ['milestones'] })
    setDone({ ref: booking.ref, status, note })
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
            <h2>{done.status === 'paid' ? T('confirmedT') : T('pending')}</h2>
          </div>
          <div className="sheet-scroll">
            <div className="done">
              <Icon name="i-lamp" cls="ic lamp" />
              {/* Three endings, not two. "paid" is the server's word. "received"
                  means Razorpay took the money and the webhook has not reached
                  us yet — true and reassuring, without claiming a confirmation
                  we have not got. "pending" means no payment happened. */}
              <h2>{done.status === 'paid' ? T('allSet') : T('pending')}</h2>
              <p>
                {target?.poojaName} · {who?.name}
              </p>
              {done.status === 'received' && <p>{T('bookReceivedNote')}</p>}
              {done.status === 'pending' && <p>{done.note ?? T('bookPendingNote')}</p>}
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
                <span className="v">{money(rupees(feePaise))}</span>
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
