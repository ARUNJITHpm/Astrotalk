// The temples section's pure rules. Every one of these is a place where a
// plausible-looking implementation is wrong in a way no rendering test notices.

import { describe, expect, it } from 'vitest'

import type { Temple } from '../api/temples'
import {
  EMPTY_FILTER,
  clockToMinutes,
  diffTemple,
  districtsOf,
  filterTemples,
  hoursProblem,
  minutesToClock,
  parseCoords,
  readDays,
  readPaise,
} from '../lib/temple'

function temple(over: Partial<Temple> = {}): Temple {
  return {
    id: 'tsr-guruvayur',
    name: 'Guruvayur Temple',
    name_ml: 'ഗുരുവായൂർ',
    deity: 'krishna',
    district: 'Thrissur',
    town: 'Guruvayur',
    town_ml: 'ഗുരുവായൂർ',
    lat: 10.5946,
    lng: 76.0402,
    famous_for: 'Krishna darshan',
    vazhipadu: ['thulabharam'],
    reviewed: true,
    story: 'A story.',
    story_ml: null,
    hours: [[180, 780]],
    timings: { nirmalyam: '3:00 AM', morning: '7:00 AM', evening: '4:30 PM' },
    rating: null,
    reviews: null,
    active: true,
    image_key: null,
    sort_order: 0,
    updated_at: '2026-07-01T00:00:00Z',
    ...over,
  }
}

describe('filterTemples', () => {
  const rows = [
    temple(),
    temple({ id: 'ekm-chottanikkara', name: 'Chottanikkara', name_ml: 'ചോറ്റാനിക്കര', district: 'Ernakulam', town: 'Chottanikkara', deity: 'devi', reviewed: false }),
    temple({ id: 'tvm-attukal', name: 'Attukal', name_ml: 'ആറ്റുകാൽ', district: 'Thiruvananthapuram', town: 'Attukal', deity: 'devi', active: false }),
  ]

  it('returns everything when nothing is chosen', () => {
    expect(filterTemples(rows, EMPTY_FILTER)).toHaveLength(3)
  })

  it('keeps the order the server sent', () => {
    // sort_order then id is a curated sequence; re-sorting client-side would
    // quietly override an owner's arrangement of the directory.
    expect(filterTemples(rows, EMPTY_FILTER).map((t) => t.id)).toEqual(rows.map((t) => t.id))
  })

  it('searches the id, because that is what a booking ref carries', () => {
    const hit = filterTemples(rows, { ...EMPTY_FILTER, q: 'ekm-' })
    expect(hit.map((t) => t.name)).toEqual(['Chottanikkara'])
  })

  it('searches the Malayalam name', () => {
    const hit = filterTemples(rows, { ...EMPTY_FILTER, q: 'ആറ്റുകാൽ' })
    expect(hit.map((t) => t.id)).toEqual(['tvm-attukal'])
  })

  it('is case-insensitive on the English name', () => {
    expect(filterTemples(rows, { ...EMPTY_FILTER, q: 'GURUVAYUR' })).toHaveLength(1)
  })

  it('combines filters rather than replacing them', () => {
    const hit = filterTemples(rows, { ...EMPTY_FILTER, deity: 'devi', active: 'yes' })
    expect(hit.map((t) => t.id)).toEqual(['ekm-chottanikkara'])
  })

  it('separates unreviewed drafts from signed-off rows', () => {
    expect(filterTemples(rows, { ...EMPTY_FILTER, reviewed: 'no' })).toHaveLength(1)
    expect(filterTemples(rows, { ...EMPTY_FILTER, reviewed: 'yes' })).toHaveLength(2)
  })

  it('finds retired temples, which the app itself will not show', () => {
    const hit = filterTemples(rows, { ...EMPTY_FILTER, active: 'no' })
    expect(hit.map((t) => t.id)).toEqual(['tvm-attukal'])
  })

  it('offers each district once, sorted', () => {
    expect(districtsOf(rows)).toEqual(['Ernakulam', 'Thiruvananthapuram', 'Thrissur'])
  })
})

describe('diffTemple', () => {
  it('sends nothing when nothing changed', () => {
    const row = temple()
    expect(diffTemple(row, { name: row.name, hours: row.hours, timings: row.timings })).toEqual({})
  })

  it('sends only the field that moved', () => {
    expect(diffTemple(temple(), { name: 'New name', district: 'Thrissur' })).toEqual({
      name: 'New name',
    })
  })

  it('does not restate hours and timings that were only re-read', () => {
    // The one that matters. PATCH treats an explicit null as "clear this
    // column", and hours/timings arrive as fresh objects on every render, so a
    // by-reference comparison would resend them — and a form that resends a
    // field it did not change is one bug away from clearing it.
    const row = temple()
    const patch = diffTemple(row, {
      hours: JSON.parse(JSON.stringify(row.hours)),
      timings: { ...row.timings! },
    })
    expect(patch).toEqual({})
  })

  it('does send a genuinely edited window', () => {
    expect(diffTemple(temple(), { hours: [[180, 800]] })).toEqual({ hours: [[180, 800]] })
  })

  it('carries an explicit null through, so defaults can be restored', () => {
    expect(diffTemple(temple(), { hours: null })).toEqual({ hours: null })
  })

  it('ignores fields the operator never touched', () => {
    expect(diffTemple(temple(), {})).toEqual({})
  })

  it('never emits a field that has its own route', () => {
    // reviewed and active answer to different roles and different endpoints.
    // TypeScript already forbids them; this pins the runtime behaviour too, in
    // case a draft is ever assembled dynamically.
    const patch = diffTemple(temple({ reviewed: false }), {
      name: 'x',
      reviewed: true,
      active: false,
      id: 'other',
    } as never)
    expect(patch).toEqual({ name: 'x' })
  })
})

describe('darshan windows', () => {
  it('round-trips minutes and the clock', () => {
    expect(minutesToClock(555)).toBe('09:15')
    expect(clockToMinutes('09:15')).toBe(555)
    expect(minutesToClock(0)).toBe('00:00')
  })

  it('refuses text that is not a time', () => {
    expect(clockToMinutes('nine')).toBeNull()
    expect(clockToMinutes('25:00')).toBeNull()
    expect(clockToMinutes('09:75')).toBeNull()
  })

  it('catches a reversed window before the server does', () => {
    expect(hoursProblem([[600, 300]])).toMatch(/close after/)
    expect(hoursProblem([])).toMatch(/at least one/)
    expect(hoursProblem([[180, 780]])).toBeNull()
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

describe('parseCoords', () => {
  it('reads a plain pair', () => {
    expect(parseCoords('9.9312, 76.2673')).toEqual({ lat: 9.9312, lng: 76.2673 })
    expect(parseCoords('10.5946 76.0402')).toEqual({ lat: 10.5946, lng: 76.0402 })
  })

  it('reads the camera position out of a Maps URL', () => {
    expect(parseCoords('https://www.google.com/maps/@10.5946,76.0402,17z')).toEqual({
      lat: 10.5946,
      lng: 76.0402,
    })
  })

  it("prefers the place's own point over where the camera sits", () => {
    // A share link carries both. `@` is the viewport, `!3d!4d` is the pin, and
    // the pin is the temple.
    const url =
      'https://www.google.com/maps/place/Guruvayur/@10.6,76.1,15z/data=!3m1!4b1!4m5!3d10.5946!4d76.0402'
    expect(parseCoords(url)).toEqual({ lat: 10.5946, lng: 76.0402 })
  })

  it('reads a ?q= link', () => {
    expect(parseCoords('https://maps.google.com/?q=9.9312,76.2673')).toEqual({
      lat: 9.9312,
      lng: 76.2673,
    })
  })

  it('rejects a URL with no coordinates rather than scavenging its digits', () => {
    expect(parseCoords('https://maps.app.goo.gl/AbCdEf123')).toBeNull()
  })

  it('rejects impossible coordinates', () => {
    expect(parseCoords('91, 76')).toBeNull()
    expect(parseCoords('10, 181')).toBeNull()
  })

  it('rejects a lone number and empty input', () => {
    expect(parseCoords('76.2673')).toBeNull()
    expect(parseCoords('   ')).toBeNull()
  })
})
