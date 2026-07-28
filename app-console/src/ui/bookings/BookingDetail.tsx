// One booking, joined across modules the way an operator needs to read it:
// who booked it, how to call them back, whether the money arrived, and what to
// perform.
//
// The transition buttons come from `nextStates`, a mirror of the server's
// OPERATOR_TRANSITIONS. Two absences there are deliberate and are explained on
// screen rather than left as three buttons that 409: nothing can be moved back
// to `ok` (that word means the payment reconciler saw a captured payment), and
// nothing can be moved back to `wait` (you cannot un-pay an order).
//
// `refunded` is bookkeeping. It records that a refund was issued in the
// Razorpay dashboard; nothing here moves money, and the screen says so, because
// a button labelled "Refund" that does not refund is the worst kind of lie a
// console can tell.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  bookingDetail,
  setBookingNote,
  setBookingStatus,
  setPerformOn,
} from '../../api/bookings'
import { nextStates, stateLabel, whenStamp } from '../../lib/booking'
import { money } from '../../lib/money'
import { nakLabel } from '../../lib/nakshatrams'
import { Problem } from '../bits'
import { StateBadge } from './bits'

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="deftrow">
      <span className="deftrow__label">{label}</span>
      <span className="deftrow__value">{children}</span>
    </div>
  )
}

export function BookingDetail() {
  const { bookingId } = useParams<{ bookingId: string }>()
  const id = Number(bookingId)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const { data: booking, isLoading, error } = useQuery({
    queryKey: ['booking', id],
    queryFn: () => bookingDetail(id),
    enabled: Number.isInteger(id),
  })

  const [note, setNote] = useState('')
  const [target, setTarget] = useState<string | null>(null)
  const [reason, setReason] = useState('')
  const [day, setDay] = useState('')

  useEffect(() => {
    setNote(booking?.operator_note ?? '')
    setDay(booking?.perform_on ?? '')
    setTarget(null)
    setReason('')
  }, [booking?.id, booking?.updated_at])

  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: ['booking', id] })
    // The queue is a different query and would otherwise show the old state
    // until it refetched on its own.
    await queryClient.invalidateQueries({ queryKey: ['queue'] })
  }

  const move = useMutation({
    mutationFn: (to: string) => setBookingStatus(id, to, reason.trim()),
    onSuccess: async () => {
      await done()
      setTarget(null)
      setReason('')
    },
  })
  const saveNote = useMutation({
    mutationFn: () => setBookingNote(id, note),
    onSuccess: done,
  })
  const schedule = useMutation({
    // '' is an operator clearing the box, which means "no date" — not "leave it".
    mutationFn: () => setPerformOn(id, day || null),
    onSuccess: async () => {
      await done()
      await queryClient.invalidateQueries({ queryKey: ['worklist'] })
    },
  })

  if (!Number.isInteger(id)) {
    return (
      <section className="page">
        <h1 className="page__title">Not a booking</h1>
        <p className="page__lede">
          <Link to="/bookings">Back to the queue</Link>.
        </p>
      </section>
    )
  }
  if (isLoading) return <p className="empty">Loading…</p>
  if (error || !booking) {
    return (
      <section className="page">
        <h1 className="page__title">No such booking</h1>
        <p className="page__lede">
          It may not be one of yours. <Link to="/bookings">Back to the queue</Link>.
        </p>
        <Problem error={error} />
      </section>
    )
  }

  const targets = nextStates(booking.state)

  return (
    <section className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">{booking.ref}</h1>
          <p className="page__lede">
            {booking.pooja_name} at {booking.temple_id} · <StateBadge state={booking.state} />
          </p>
        </div>
        <button className="btn btn--inline" onClick={() => navigate('/bookings')}>
          Back to the queue
        </button>
      </div>

      <Problem error={move.error ?? saveNote.error ?? schedule.error} />

      <div className="grid2">
        <section className="card">
          <h2 className="card__title">The offering</h2>
          <Row label="Offering">{booking.pooja_name}</Row>
          <Row label="For">{booking.member_name || '—'}</Row>
          <Row label="Star">{nakLabel(booking.member_nak)}</Row>
          <Row label="Told to expect">{booking.when_label || '—'}</Row>
          <Row label="Booked">{whenStamp(booking.created_at)}</Row>

          {/* The button sits outside the label: a <label> forwards its click to
              the first labelable control inside it, so wrapping both would make
              "Set date" ambiguous to a screen reader. */}
          <div className="row">
            <label className="field">
              <span>Perform on</span>
              <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
            </label>
            <button
              className="btn"
              disabled={day === (booking.perform_on ?? '') || schedule.isPending}
              onClick={() => schedule.mutate()}
            >
              {schedule.isPending ? 'Saving…' : 'Set date'}
            </button>
          </div>
          {!booking.perform_on && (
            <p className="field__hint">
              Undated, so this booking is on no worklist at any date. The app
              started recording a date later than it started taking bookings.
            </p>
          )}
          {/*
            The devotee's confirmation says "Told to expect"; this date is what
            the temple's sheet is built from. Setting one never rewrites the
            other, so the two can be compared rather than silently merged.
          */}
        </section>

        <section className="card">
          <h2 className="card__title">The devotee</h2>
          <Row label="Name">{booking.user_name || '—'}</Row>
          <Row label="Mobile">
            <a href={`tel:${booking.user_phone}`}>{booking.user_phone || '—'}</a>
          </Row>
          {/*
            Name and mobile only. A devotee's birth date, time and place are not
            needed to perform a pooja, and GUARDRAILS §4 keeps them out of
            screens that do not need them.
          */}
        </section>

        <section className="card">
          <h2 className="card__title">Money</h2>
          <Row label="Offering">{money(booking.amount_paise)}</Row>
          <Row label="Service fee">{money(booking.service_fee_paise)}</Row>
          <Row label="Total">
            <strong>{money(booking.total_paise)}</strong>
          </Row>
          <Row label="Payment">
            {booking.payment_status ? stateLabel(booking.payment_status) : 'No order'}
          </Row>
          <Row label="Razorpay order">
            <code>{booking.razorpay_order_id || '—'}</code>
          </Row>
        </section>

        <section className="card">
          <h2 className="card__title">Operator note</h2>
          <p className="field__hint">
            Whatever the temple needs to remember: a phone call, a substitution,
            why it was cancelled. The devotee never sees this.
          </p>
          <textarea rows={5} value={note} onChange={(e) => setNote(e.target.value)} />
          <button
            className="btn btn--primary btn--inline"
            disabled={note === booking.operator_note || saveNote.isPending}
            onClick={() => saveNote.mutate()}
          >
            {saveNote.isPending ? 'Saving…' : 'Save note'}
          </button>
        </section>
      </div>

      <section className="card">
        <h2 className="card__title">Move this booking on</h2>
        {!targets.length ? (
          <p className="field__hint">
            A refunded booking is the end of the line — there is nothing further to
            record.
          </p>
        ) : (
          <>
            <div className="row row--wrap">
              {targets.map((to) => (
                <button
                  key={to}
                  className={to === target ? 'btn btn--primary btn--inline' : 'btn'}
                  onClick={() => setTarget(to)}
                >
                  {stateLabel(to)}
                </button>
              ))}
            </div>
            {target && (
              <div className="confirmbox">
                {target === 'refunded' && (
                  <p className="banner banner--warn">
                    This records that a refund was issued in the Razorpay dashboard.
                    It does not move any money — issue the refund there first.
                  </p>
                )}
                <label className="field">
                  <span>Why (kept on the booking)</span>
                  <input
                    value={reason}
                    placeholder="optional"
                    onChange={(e) => setReason(e.target.value)}
                  />
                </label>
                <div className="row">
                  <button
                    className="btn btn--primary btn--inline"
                    disabled={move.isPending}
                    onClick={() => move.mutate(target)}
                  >
                    {move.isPending ? 'Recording…' : `Mark ${stateLabel(target).toLowerCase()}`}
                  </button>
                  <button className="btn" onClick={() => setTarget(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </>
        )}
        <p className="field__hint">
          Paid and awaiting-payment are not on offer: both are set by the payment
          reconciler, and a booking marked paid by hand would be
          indistinguishable from a mistaken click.
        </p>
      </section>
    </section>
  )
}
