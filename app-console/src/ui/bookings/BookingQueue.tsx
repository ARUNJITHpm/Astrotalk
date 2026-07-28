// The booking queue — the screen the product is actually run from.
//
// Before Part 7 an operator could see nothing here at all: the bookings module
// had two routes and both were hard-scoped to the caller, so answering "what
// are we performing tomorrow" meant opening the database.
//
// Two decisions worth knowing:
//
//   - The scope is the server's. A temple_admin's queue is filtered inside the
//     query, not here, so nothing this file does can widen it. The temple
//     picker below narrows further; it cannot reach past the grant.
//   - The CSV comes from the server too. An accountant reconciling a month must
//     not be reconciling against a figure this app rounded, so paise are
//     exported as stored and no client-side export exists to disagree with it.

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { bookingQueue, downloadBookingsCsv, type QueueQuery } from '../../api/bookings'
import { listTemples } from '../../api/temples'
import {
  BOOKING_STATES,
  INITIAL_QUEUE,
  applyFilter,
  goToPage,
  isFiltered,
  pageSummary,
  performLabel,
  queueQuery,
  stateLabel,
  today,
} from '../../lib/booking'
import { money } from '../../lib/money'
import { nakLabel } from '../../lib/nakshatrams'
import { Problem } from '../bits'
import { StateBadge } from './bits'

const PAGE = 50

export function BookingQueue() {
  const [state, setState] = useState(INITIAL_QUEUE)
  const [csvError, setCsvError] = useState<unknown>(null)
  const [exporting, setExporting] = useState(false)
  const query: QueueQuery = queueQuery(state, PAGE)

  const temples = useQuery({ queryKey: ['temples'], queryFn: listTemples })
  const page = useQuery({
    queryKey: ['queue', query],
    queryFn: () => bookingQueue(query),
    // Without this the table blanks on every keystroke in the ref box, which
    // reads as "no results" for as long as the request is in flight.
    placeholderData: keepPreviousData,
  })

  const set = (patch: Parameters<typeof applyFilter>[1]) =>
    setState((s) => applyFilter(s, patch))
  const rows = page.data?.items ?? []
  const total = page.data?.total ?? 0

  const exportCsv = async () => {
    setExporting(true)
    setCsvError(null)
    try {
      // The export takes the same filter, minus the paging: it is a settlement
      // document, not the page on screen.
      await downloadBookingsCsv({ ...query, limit: undefined, offset: undefined })
    } catch (err) {
      setCsvError(err)
    } finally {
      setExporting(false)
    }
  }

  return (
    <section className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">Pooja bookings</h1>
          <p className="page__lede">
            Every booking you may see, newest first. Amounts are the offering plus
            the service fee.
          </p>
        </div>
        <button className="btn btn--inline" disabled={exporting} onClick={() => void exportCsv()}>
          {exporting ? 'Preparing…' : 'Export CSV'}
        </button>
      </div>

      <Problem error={page.error ?? csvError} />

      <div className="toolbar">
        <label className="toolbar__field toolbar__field--grow">
          <span>Booking ref</span>
          <input
            value={state.filter.ref}
            placeholder="NT7K3Q2X"
            onChange={(e) => set({ ref: e.target.value })}
          />
        </label>
        <label className="toolbar__field">
          <span>Devotee mobile</span>
          <input
            value={state.filter.phone}
            placeholder="+91…"
            onChange={(e) => set({ phone: e.target.value })}
          />
        </label>
        <label className="toolbar__field">
          <span>Temple</span>
          <select
            value={state.filter.temple_id}
            onChange={(e) => set({ temple_id: e.target.value })}
          >
            <option value="">All mine</option>
            {(temples.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="toolbar__field">
          <span>State</span>
          <select value={state.filter.state} onChange={(e) => set({ state: e.target.value })}>
            <option value="">Any</option>
            {BOOKING_STATES.map((s) => (
              <option key={s} value={s}>
                {stateLabel(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="toolbar__field">
          <span>Perform from</span>
          <input
            type="date"
            value={state.filter.perform_from}
            onChange={(e) => set({ perform_from: e.target.value })}
          />
        </label>
        <label className="toolbar__field">
          <span>Perform to</span>
          <input
            type="date"
            value={state.filter.perform_to}
            onChange={(e) => set({ perform_to: e.target.value })}
          />
        </label>
        <label className="toolbar__field">
          <span>Booked from</span>
          <input
            type="date"
            value={state.filter.booked_from}
            onChange={(e) => set({ booked_from: e.target.value })}
          />
        </label>
        <label className="toolbar__field">
          <span>Booked to</span>
          <input
            type="date"
            value={state.filter.booked_to}
            onChange={(e) => set({ booked_to: e.target.value })}
          />
        </label>
      </div>

      <div className="row row--wrap quickfilters">
        <button className="btn" onClick={() => set({ state: 'ok' })}>
          Paid, not yet performed
        </button>
        <button
          className="btn"
          onClick={() => set({ perform_from: today(), perform_to: today() })}
        >
          To perform today
        </button>
        {isFiltered(state.filter) && (
          <button className="btn" onClick={() => setState(INITIAL_QUEUE)}>
            Clear filters
          </button>
        )}
      </div>

      <p className="count" role="status">
        {page.isLoading ? 'Loading…' : pageSummary(total, state.offset, rows.length)}
      </p>

      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Ref</th>
              <th>Offering</th>
              <th>For</th>
              <th>Perform on</th>
              <th>Amount</th>
              <th>State</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((b) => (
              <tr key={b.id}>
                <td>
                  <Link className="celllink" to={`/bookings/${b.id}`}>
                    {b.ref}
                  </Link>
                  <span className="cell__sub">{b.temple_id}</span>
                </td>
                <td>
                  {b.pooja_name}
                  {b.operator_note && <span className="cell__sub">note on file</span>}
                </td>
                <td>
                  {b.member_name || '—'}
                  <span className="cell__sub">{nakLabel(b.member_nak)}</span>
                </td>
                <td>{performLabel(b)}</td>
                <td className="num">{money(b.amount_paise + b.service_fee_paise)}</td>
                <td>
                  <StateBadge state={b.state} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!page.isLoading && !rows.length && (
          <p className="empty">
            {isFiltered(state.filter)
              ? 'No booking matches those filters.'
              : 'No bookings yet.'}
          </p>
        )}
      </div>

      <div className="pager">
        <button
          className="btn"
          disabled={state.offset === 0}
          onClick={() => setState((s) => goToPage(s, s.offset - PAGE))}
        >
          Previous
        </button>
        <button
          className="btn"
          disabled={state.offset + rows.length >= total}
          onClick={() => setState((s) => goToPage(s, s.offset + PAGE))}
        >
          Next
        </button>
      </div>
    </section>
  )
}
