// The PEOPLE section's pure rules: derived age, role grants, weekly hours.

import { describe, expect, it } from 'vitest'

import { SCOPED_ROLES, type AvailabilityWindow, type OperatorRow } from '../api/people'
import {
  ageFrom,
  ageLabel,
  availabilityProblem,
  byWeekday,
  grantProblem,
  operatorIdentifier,
  roleSummary,
} from '../lib/people'

const TODAY = new Date('2026-07-28T12:00:00')

function operator(over: Partial<OperatorRow> = {}): OperatorRow {
  return {
    id: 7,
    email: 'clerk@example.com',
    phone: null,
    name: 'Clerk',
    active: true,
    pending: false,
    last_login_at: null,
    roles: [],
    ...over,
  }
}

function window(over: Partial<AvailabilityWindow> = {}): AvailabilityWindow {
  return { weekday: 0, start: '09:00', end: '12:00', duration_min: 30, ...over }
}

describe('ageFrom', () => {
  it('counts whole years', () => {
    expect(ageFrom('1961-04-12', TODAY)).toBe(65)
  })

  it('does not credit a birthday that has not come round yet', () => {
    // The commonest off-by-one in this kind of function, and it is off by a
    // whole year on roughly half the register.
    expect(ageFrom('1961-12-31', TODAY)).toBe(64)
    expect(ageFrom('1961-07-29', TODAY)).toBe(64)
    expect(ageFrom('1961-07-28', TODAY)).toBe(65) // the birthday itself counts
  })

  it('handles a leap day', () => {
    expect(ageFrom('2000-02-29', TODAY)).toBe(26)
  })

  it('returns null for no date, rather than zero', () => {
    // "We do not know" and "born this year" are different facts, and a newborn
    // on a family board is real.
    expect(ageFrom(null, TODAY)).toBeNull()
    expect(ageFrom('', TODAY)).toBeNull()
    expect(ageFrom('not a date', TODAY)).toBeNull()
    expect(ageFrom('2026-07-01', TODAY)).toBe(0)
  })

  it('refuses a date in the future rather than reporting a negative age', () => {
    expect(ageFrom('2030-01-01', TODAY)).toBeNull()
  })

  it('shows an em dash when there is no date on file', () => {
    expect(ageLabel(null, TODAY)).toBe('—')
    expect(ageLabel('1990-01-01', TODAY)).toBe('36')
  })
})

describe('grantProblem', () => {
  it('mirrors the server in both directions', () => {
    // admin/operators.py `_validate_grant`. Both halves matter: an unscoped
    // temple_admin sees nothing and looks like a broken account, and a temple
    // on any other role is a scope nothing reads — stored, ignored, and
    // misleading to whoever audits the grants later.
    expect(grantProblem('temple_admin', null, SCOPED_ROLES)).toMatch(/must be given a temple/)
    expect(grantProblem('owner', 'tsr-guruvayur', SCOPED_ROLES)).toMatch(/Only a temple admin/)
  })

  it('accepts the two valid shapes', () => {
    expect(grantProblem('temple_admin', 'tsr-guruvayur', SCOPED_ROLES)).toBeNull()
    expect(grantProblem('content_reviewer', null, SCOPED_ROLES)).toBeNull()
    expect(grantProblem('owner', null, SCOPED_ROLES)).toBeNull()
  })

  it('asks for a role at all', () => {
    expect(grantProblem('', null, SCOPED_ROLES)).toMatch(/Choose a role/)
  })
})

describe('operator summaries', () => {
  it('says plainly when somebody can sign in and see nothing', () => {
    expect(roleSummary(operator())).toBe('No roles yet')
  })

  it('counts the temples a scoped operator holds', () => {
    const scoped = operator({
      roles: [
        { id: 1, role: 'temple_admin', temple_id: 'a' },
        { id: 2, role: 'temple_admin', temple_id: 'b' },
      ],
    })
    expect(roleSummary(scoped)).toBe('temple admin · 2 temples')
  })

  it('does not repeat a role name once per grant', () => {
    const scoped = operator({
      roles: [
        { id: 1, role: 'temple_admin', temple_id: 'a' },
        { id: 2, role: 'temple_admin', temple_id: 'b' },
      ],
    })
    expect(roleSummary(scoped).startsWith('temple admin ·')).toBe(true)
  })

  it('falls back through email, mobile, then id', () => {
    expect(operatorIdentifier(operator())).toBe('clerk@example.com')
    expect(operatorIdentifier(operator({ email: null, phone: '+919000000001' }))).toBe(
      '+919000000001',
    )
    expect(operatorIdentifier(operator({ email: null, phone: null }))).toBe('#7')
  })
})

describe('availabilityProblem', () => {
  it('accepts a sane week', () => {
    expect(availabilityProblem([window(), window({ weekday: 2 })])).toBeNull()
    expect(availabilityProblem([])).toBeNull()
  })

  it('refuses a window that ends before it starts', () => {
    expect(availabilityProblem([window({ start: '12:00', end: '09:00' })])).toMatch(
      /end after it starts/,
    )
  })

  it('refuses a consult longer than the window holding it', () => {
    // Silently produces no bookable slots, which is indistinguishable from
    // "nobody wants this astrologer" until somebody reads the JSON.
    expect(availabilityProblem([window({ duration_min: 240 })])).toMatch(/no slot fits/)
  })

  it('refuses a zero-length consult', () => {
    expect(availabilityProblem([window({ duration_min: 0 })])).toMatch(/at least a minute/)
  })

  it('catches two windows overlapping on the same day', () => {
    // astro_bookings is unique on (astrologer_id, starts_at), so the same
    // instant offered twice fails at the database rather than in the UI.
    const clash = [window({ start: '09:00', end: '12:00' }), window({ start: '11:00', end: '13:00' })]
    expect(availabilityProblem(clash)).toMatch(/Mon windows overlap/)
  })

  it('allows the same hours on different days', () => {
    expect(
      availabilityProblem([window({ weekday: 0 }), window({ weekday: 1 })]),
    ).toBeNull()
  })

  it('allows windows that touch but do not overlap', () => {
    const back_to_back = [
      window({ start: '09:00', end: '12:00' }),
      window({ start: '12:00', end: '15:00' }),
    ]
    expect(availabilityProblem(back_to_back)).toBeNull()
  })

  it('refuses a time that is not a time', () => {
    expect(availabilityProblem([window({ start: 'morning' })])).toMatch(/HH:MM/)
  })
})

describe('byWeekday', () => {
  it('groups Monday first and drops empty days', () => {
    const grouped = byWeekday([
      window({ weekday: 3, start: '10:00' }),
      window({ weekday: 0, start: '14:00' }),
      window({ weekday: 0, start: '09:00' }),
    ])
    expect(grouped.map((g) => g.weekday)).toEqual([0, 3])
    expect(grouped[0].windows.map((w) => w.start)).toEqual(['09:00', '14:00'])
  })
})
