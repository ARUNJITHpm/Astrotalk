// Shared pieces for the BOOKINGS screens.

import { CLOSED_STATES, LIVE_STATES, stateLabel } from '../../lib/booking'

/**
 * A booking, consult or payment state, coloured by what it means for the temple.
 *
 * One badge for three state machines, which is why the tone comes from a set
 * rather than a chain of comparisons: `ok` and `paid` are the same fact in two
 * modules, and both mean somebody has work to do today.
 */
export function StateBadge({ state }: { state: string }) {
  const tone = LIVE_STATES.has(state)
    ? ' badge--on'
    : CLOSED_STATES.has(state)
      ? ' badge--off'
      : ''
  return <span className={`badge${tone}`}>{stateLabel(state)}</span>
}
