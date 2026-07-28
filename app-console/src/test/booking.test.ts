// The queue's pure rules: what a filter change means, and what an operator may
// do to a booking.

import { describe, expect, it } from 'vitest'

import {
  BOOKING_STATES,
  EMPTY_QUEUE_FILTER,
  INITIAL_QUEUE,
  OPERATOR_TRANSITIONS,
  applyFilter,
  goToPage,
  isFiltered,
  nextStates,
  pageSummary,
  performLabel,
  queueQuery,
  stateLabel,
} from '../lib/booking'
import { money, readDays, readPaise } from '../lib/money'
import { NAKSHATRAMS, nakLabel } from '../lib/nakshatrams'

describe('the filter bar', () => {
  it('sends nothing when nothing is set', () => {
    expect(queueQuery(INITIAL_QUEUE, 50)).toEqual({ limit: 50, offset: 0 })
  })

  it('omits blanks rather than sending them empty', () => {
    // `?state=` is not the same request as no `state` at all, and the server
    // would have to decide which one an empty string meant.
    const state = applyFilter(INITIAL_QUEUE, { ref: 'NT123', temple_id: '' })
    expect(queueQuery(state, 50)).toEqual({ limit: 50, offset: 0, ref: 'NT123' })
  })

  it('trims what an operator pasted', () => {
    // A ref read off a phone screen arrives with a space on the end often
    // enough to matter, and the server matches it literally.
    const state = applyFilter(INITIAL_QUEUE, { ref: '  NT123 ' })
    expect(queueQuery(state, 50).ref).toBe('NT123')
  })

  it('returns to the first page whenever a filter changes', () => {
    // The one that actually bites. Narrowing a 400-row queue while sitting on
    // offset 300 leaves an operator staring at an empty table that is not
    // empty — the classic way a working filter looks broken.
    const deep = goToPage(INITIAL_QUEUE, 300)
    expect(deep.offset).toBe(300)
    expect(applyFilter(deep, { state: 'ok' }).offset).toBe(0)
  })

  it('keeps the filter when only the page changes', () => {
    const filtered = applyFilter(INITIAL_QUEUE, { state: 'ok' })
    expect(goToPage(filtered, 50).filter.state).toBe('ok')
  })

  it('never pages below zero', () => {
    expect(goToPage(INITIAL_QUEUE, -50).offset).toBe(0)
  })

  it('knows whether anything is narrowing the queue', () => {
    expect(isFiltered(EMPTY_QUEUE_FILTER)).toBe(false)
    expect(isFiltered({ ...EMPTY_QUEUE_FILTER, phone: ' ' })).toBe(false)
    expect(isFiltered({ ...EMPTY_QUEUE_FILTER, phone: '+91' })).toBe(true)
  })

  it('describes a page without guessing at an empty one', () => {
    expect(pageSummary(480, 50, 50)).toBe('51–100 of 480')
    expect(pageSummary(0, 0, 0)).toBe('No bookings match')
  })
})

describe('the state machine', () => {
  it('mirrors the server, including what it refuses', () => {
    // A copy of OPERATOR_TRANSITIONS in bookings/models.py. `ok` and `wait` are
    // absent from every target list: `ok` means the payment reconciler saw a
    // captured payment, and you cannot un-pay an order.
    for (const targets of Object.values(OPERATOR_TRANSITIONS)) {
      expect(targets).not.toContain('ok')
      expect(targets).not.toContain('wait')
    }
  })

  it('lets a paid booking be performed, cancelled or refunded', () => {
    expect(nextStates('ok').sort()).toEqual(['cancelled', 'completed', 'refunded'])
  })

  it('lets an unpaid booking only be cancelled', () => {
    expect(nextStates('wait')).toEqual(['cancelled'])
  })

  it('makes refunded the end of the line', () => {
    expect(nextStates('refunded')).toEqual([])
  })

  it('offers nothing for a state it does not know', () => {
    expect(nextStates('nonsense')).toEqual([])
  })

  it('never proposes a move to the state already held', () => {
    for (const state of BOOKING_STATES) {
      expect(nextStates(state)).not.toContain(state)
    }
  })

  it('labels every state it can reach in words an operator reads', () => {
    for (const state of BOOKING_STATES) {
      expect(stateLabel(state)).not.toBe(state)
    }
    expect(stateLabel('ok')).toBe('Paid')
  })
})

describe('display', () => {
  it('formats paise as rupees and drops a pointless decimal', () => {
    expect(money(6600)).toBe('₹66')
    expect(money(5150)).toBe('₹51.50')
    expect(money(0)).toBe('₹0')
  })

  it('calls out a booking that is on no sheet', () => {
    // `perform_on` is the machine date; `when_label` is free text the app wrote.
    // Only the first can put a booking on a worklist.
    expect(performLabel({ perform_on: '2026-08-01', when_label: '1 Aug' })).toBe('2026-08-01')
    expect(performLabel({ perform_on: null, when_label: '1 Aug' })).toBe('1 Aug (no date)')
    expect(performLabel({ perform_on: null, when_label: '' })).toBe('Not dated')
  })

  it('names a star in both scripts, and says so when there is none', () => {
    expect(NAKSHATRAMS).toHaveLength(27)
    expect(nakLabel(0)).toBe('Ashwathi · അശ്വതി')
    expect(nakLabel(21)).toBe('Thiruvonam · തിരുവോണം')
    expect(nakLabel(null)).toBe('No star')
    expect(nakLabel(27)).toBe('No star')
  })
})

describe('readPaise / readDays', () => {
  it('treats an empty box as inherit, not as zero', () => {
    // The distinction the whole override model rests on. Zero is a free
    // offering; blank means "whatever the master catalogue says", so that a
    // later repricing still reaches this temple.
    expect(readPaise('')).toEqual({ value: null, ok: true })
    expect(readPaise('0')).toEqual({ value: 0, ok: true })
  })

  it('converts rupees to paise, fractions included', () => {
    expect(readPaise('12.50')).toEqual({ value: 1250, ok: true })
    expect(readPaise('101')).toEqual({ value: 10100, ok: true })
  })

  it('refuses text that is not a number instead of sending null', () => {
    // Number('abc') is NaN, JSON.stringify(NaN) is null, and the server reads
    // that null as "inherit" — a silent repricing rather than a rejection.
    for (const bad of ['abc', '1,000', '-5', '1 2']) {
      expect(readPaise(bad).ok, bad).toBe(false)
    }
  })

  it('wants whole days', () => {
    expect(readDays('3')).toEqual({ value: 3, ok: true })
    expect(readDays('')).toEqual({ value: null, ok: true })
    expect(readDays('1.5').ok).toBe(false)
    expect(readDays('-1').ok).toBe(false)
  })
})
