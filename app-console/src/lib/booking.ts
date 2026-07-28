// Pure rules for the bookings queue: what an operator may do to a booking, and
// what the filter bar means. Both are tested apart from the screens.

import type { QueueQuery } from '../api/bookings'

// ---- the state machine ----

/**
 * A mirror of `OPERATOR_TRANSITIONS` in app/modules/bookings/models.py.
 *
 * `ok` is absent from every target list on purpose: it means "the payment
 * reconciler saw a captured payment", so letting the console assert it by hand
 * would make a paid booking indistinguishable from a mistaken click. `wait` is
 * likewise never a target — you cannot un-pay an order.
 *
 * The server refuses anything this table would allow by mistake (409). What
 * this buys is a screen that offers three buttons instead of eight, six of
 * which would fail.
 */
export const OPERATOR_TRANSITIONS: Record<string, string[]> = {
  wait: ['cancelled'],
  ok: ['completed', 'cancelled', 'refunded'],
  completed: ['refunded'],
  cancelled: ['refunded'],
  refunded: [],
}

export const BOOKING_STATES = ['wait', 'ok', 'completed', 'cancelled', 'refunded']

/**
 * What each state means to someone who does not read the schema.
 *
 * Covers consults as well as poojas — the two machines are separate but one
 * badge renders both, and `ok` is the one word that would mislead: to an
 * operator it means paid and not yet performed, i.e. somebody's job today.
 */
export const STATE_LABELS: Record<string, string> = {
  // pooja bookings
  wait: 'Awaiting payment',
  ok: 'Paid',
  completed: 'Performed',
  cancelled: 'Cancelled',
  refunded: 'Refunded',
  // consults
  confirmed: 'Confirmed',
  no_show: 'No show',
  // commerce payments — `created` means an order exists and was never
  // captured, which reads as "done" to anyone who has not seen the schema.
  created: 'Not paid',
  paid: 'Paid',
  failed: 'Failed',
}

/** States that are somebody's job today, versus ones that are over with. */
export const LIVE_STATES = new Set(['ok', 'paid', 'confirmed'])
export const CLOSED_STATES = new Set(['cancelled', 'refunded', 'no_show', 'failed'])

export function nextStates(state: string): string[] {
  return OPERATOR_TRANSITIONS[state] ?? []
}

export const stateLabel = (state: string): string => STATE_LABELS[state] ?? state

/** Consults answer to a different machine and never return to `confirmed`. */
export const CONSULT_TARGETS = ['completed', 'cancelled', 'no_show']

// ---- the filter bar ----

export interface QueueFilter {
  temple_id: string
  state: string
  pooja_key: string
  ref: string
  phone: string
  booked_from: string
  booked_to: string
  perform_from: string
  perform_to: string
}

export const EMPTY_QUEUE_FILTER: QueueFilter = {
  temple_id: '',
  state: '',
  pooja_key: '',
  ref: '',
  phone: '',
  booked_from: '',
  booked_to: '',
  perform_from: '',
  perform_to: '',
}

export interface QueueState {
  filter: QueueFilter
  offset: number
}

export const INITIAL_QUEUE: QueueState = { filter: EMPTY_QUEUE_FILTER, offset: 0 }

/**
 * Change a filter, and go back to page one.
 *
 * The reset is the point. Narrowing a 400-row queue while sitting on offset 300
 * leaves an operator staring at an empty table that is not empty — the
 * classic way a filter looks broken when it worked perfectly.
 */
export function applyFilter(state: QueueState, patch: Partial<QueueFilter>): QueueState {
  return { filter: { ...state.filter, ...patch }, offset: 0 }
}

export function goToPage(state: QueueState, offset: number): QueueState {
  return { ...state, offset: Math.max(0, offset) }
}

/** The filter as query params, blanks omitted so they are not sent as empty. */
export function queueQuery(state: QueueState, limit: number): QueueQuery {
  const query: QueueQuery = { limit, offset: state.offset }
  for (const [key, value] of Object.entries(state.filter)) {
    if (value.trim()) (query as Record<string, unknown>)[key] = value.trim()
  }
  return query
}

/** Whether anything is narrowing the queue — drives the "clear" affordance. */
export function isFiltered(filter: QueueFilter): boolean {
  return Object.values(filter).some((v) => v.trim() !== '')
}

/** "showing 26–50 of 480", or an honest nothing. */
export function pageSummary(total: number, offset: number, shown: number): string {
  if (!total) return 'No bookings match'
  return `${offset + 1}–${offset + shown} of ${total}`
}

// ---- display ----

/** Paise → "₹1,234.50", trailing ".00" dropped. Display only. */
export function money(paise: number): string {
  const rupees = paise / 100
  return `₹${rupees.toLocaleString('en-IN', {
    minimumFractionDigits: Number.isInteger(rupees) ? 0 : 2,
    maximumFractionDigits: 2,
  })}`
}

/**
 * When the pooja is to be performed.
 *
 * `perform_on` is the machine-readable date and `when_label` is free display
 * text the app wrote; only the first can be sorted or filtered on, so a booking
 * without one is called out rather than quietly shown as if it were scheduled.
 * Those are the bookings that appear on no worklist at all.
 */
export function performLabel(row: {
  perform_on: string | null
  when_label: string
}): string {
  if (row.perform_on) return row.perform_on
  return row.when_label ? `${row.when_label} (no date)` : 'Not dated'
}

/** An ISO timestamp as a local, readable one. Blank stays blank. */
export function whenStamp(iso: string | null | undefined): string {
  if (!iso) return ''
  const at = new Date(iso)
  if (Number.isNaN(at.getTime())) return ''
  return at.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Today, in the operator's own timezone — the day they mean by "today". */
export function today(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}
