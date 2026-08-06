// What a pooja row says about when it can be booked.
//
// The lock itself is the server's: /temples/{id}/poojas resolves `locked`
// against the star day being booked for, so the client never recomputes it —
// two implementations of a lead time is how a booking gets accepted on screen
// and refused on submit.
//
// What IS decided here is the sentence, and it had a latent bug. The label was
// picked inline as `0 → same day, 1 → one day, anything else → "Needs 3 days"`.
// That was true of the seed catalogue, whose lead times are only ever 0, 1 or
// 3 — and stopped being true the moment the console could set the number
// (console plan Part 13). A five-day offering told people three.

export interface LeadTimed {
  locked: boolean
  lead_days: number
}

export interface LeadLabel {
  key: string
  /** Passed to i18n interpolation when the sentence carries a number. */
  count?: number
}

export function leadLabel(pooja: LeadTimed): LeadLabel {
  if (pooja.locked) return { key: 'windowClosed' }
  if (pooja.lead_days <= 0) return { key: 'sameDay' }
  if (pooja.lead_days === 1) return { key: 'needs1' }
  return { key: 'needsDays', count: pooja.lead_days }
}
