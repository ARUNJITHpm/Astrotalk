// The lead-time sentence on a pooja row.

import { describe, expect, it } from 'vitest'

import { leadLabel } from './poojaLock'

const pooja = (lead_days: number, locked = false) => ({ lead_days, locked })

describe('leadLabel', () => {
  it('says the window is closed before anything else', () => {
    // A locked row's lead time is no longer the useful fact — that the date
    // cannot be met is.
    expect(leadLabel(pooja(0, true)).key).toBe('windowClosed')
    expect(leadLabel(pooja(7, true)).key).toBe('windowClosed')
  })

  it('names same-day and one-day plainly', () => {
    expect(leadLabel(pooja(0)).key).toBe('sameDay')
    expect(leadLabel(pooja(1)).key).toBe('needs1')
  })

  it('carries the real number for anything longer', () => {
    // The bug this replaces: the label was picked as `0 → same day, 1 → one
    // day, anything else → "Needs 3 days"`. True of the seed catalogue, whose
    // lead times are only 0, 1 or 3 — and false the moment the console could
    // set the number. A five-day offering told people three.
    expect(leadLabel(pooja(2))).toEqual({ key: 'needsDays', count: 2 })
    expect(leadLabel(pooja(5))).toEqual({ key: 'needsDays', count: 5 })
    expect(leadLabel(pooja(14))).toEqual({ key: 'needsDays', count: 14 })
  })

  it('treats a nonsense negative lead as same-day rather than showing it', () => {
    expect(leadLabel(pooja(-1)).key).toBe('sameDay')
  })
})
