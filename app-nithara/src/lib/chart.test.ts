// Reading a natal chart.
//
// A wrong rasi grid renders perfectly — twelve filled cells, nothing to catch
// the eye — and is wrong in the one way a reader would notice immediately.
// These are the assertions that make that visible before a devotee does.

import { describe, expect, it } from 'vitest'

import {
  RASIS,
  SOUTH_INDIAN_ORDER,
  currentDasha,
  planetShort,
  rasiCells,
  rasiIndexOf,
  yearOf,
  type NatalChart,
} from './chart'

const CHART: NatalChart = {
  rasi: 'ഇടവം',
  nakshatram: 'രോഹിണി',
  lagnam: 'ചിങ്ങം',
  birth_time_known: true,
  planets: {
    sun: { rasi: 'മേടം', rasi_index: 0, house: 9 },
    moon: { rasi: 'ഇടവം', rasi_index: 1, house: 10 },
    saturn: { rasi: 'ഇടവം', rasi_index: 1, house: 10, retrograde: true },
    ketu: { rasi: 'മീനം', rasi_index: 11, house: 8 },
  },
  dasha: {
    mahadashas: [
      { lord: 'Moon', lord_ml: 'ചന്ദ്രൻ', start: '1988-01-01T00:00:00', end: '1998-01-01T00:00:00', years: 10 },
      { lord: 'Mars', lord_ml: 'ചൊവ്വ', start: '1998-01-01T00:00:00', end: '2005-01-01T00:00:00', years: 7 },
      { lord: 'Rahu', lord_ml: 'രാഹു', start: '2005-01-01T00:00:00', end: '2023-01-01T00:00:00', years: 18 },
    ],
  },
}

describe('the South Indian layout', () => {
  it('places the signs where a reader expects them', () => {
    // Signs are FIXED in this style — unlike the North Indian chart, where the
    // houses are fixed and the signs move. Meena top-left, then clockwise.
    expect([...SOUTH_INDIAN_ORDER]).toEqual([11, 0, 1, 2, 10, 3, 9, 4, 8, 7, 6, 5])
  })

  it('covers all twelve signs exactly once', () => {
    expect(new Set(SOUTH_INDIAN_ORDER).size).toBe(12)
  })

  it('emits cells in that DOM order, so grid auto-placement draws the chart', () => {
    // The centre cell is explicitly placed at rows 2-3 / cols 2-3 and the rest
    // flow around it. Any other order produces a wrong chart that looks fine.
    const cells = rasiCells(CHART)
    expect(cells.map((c) => c.index)).toEqual([...SOUTH_INDIAN_ORDER])
  })
})

describe('placing the planets', () => {
  it('groups them by sign', () => {
    const cells = rasiCells(CHART)
    const idavam = cells.find((c) => c.index === 1)!
    expect(idavam.planets).toEqual(['Mo', 'Sa℞'])
    expect(cells.find((c) => c.index === 0)!.planets).toEqual(['Su'])
    expect(cells.find((c) => c.index === 11)!.planets).toEqual(['Ke'])
  })

  it('marks retrograde', () => {
    const cells = rasiCells(CHART)
    expect(cells.find((c) => c.index === 1)!.planets).toContain('Sa℞')
  })

  it('marks the lagna', () => {
    const cells = rasiCells(CHART)
    expect(cells.filter((c) => c.isLagna).map((c) => c.index)).toEqual([4]) // ചിങ്ങം
  })

  it('reads a chart from the mock engine, which sends no rasi_index', () => {
    // The mock ephemeris emits the sign NAME only. A grid that works under the
    // real engine and silently empties under the mock is a defect nobody sees
    // until the keys are missing on a demo machine.
    const mocked: NatalChart = {
      lagnam: 'മേടം',
      planets: { sun: { rasi: 'തുലാം' }, moon: { rasi: 'ധനു' } },
    }
    const cells = rasiCells(mocked)
    expect(cells.find((c) => c.index === 6)!.planets).toEqual(['Su'])
    expect(cells.find((c) => c.index === 8)!.planets).toEqual(['Mo'])
  })

  it('keeps a stable order so the grid does not reshuffle between renders', () => {
    const a = rasiCells(CHART).find((c) => c.index === 1)!.planets
    const b = rasiCells(CHART).find((c) => c.index === 1)!.planets
    expect(a).toEqual(b)
  })

  it('drops a planet whose sign it cannot place rather than guessing', () => {
    const odd: NatalChart = { planets: { sun: { rasi: 'not-a-sign' } } }
    expect(rasiCells(odd).every((c) => c.planets.length === 0)).toBe(true)
  })

  it('renders an empty grid for a chart with no planets', () => {
    expect(rasiCells(null)).toHaveLength(12)
    expect(rasiCells(undefined).every((c) => c.planets.length === 0)).toBe(true)
  })

  it('agrees with the engine about the sign names', () => {
    // astrology_engine/swiss_ephemeris.py RASIS. A drift here silently
    // mis-places every planet.
    expect(RASIS[0]).toBe('മേടം')
    expect(RASIS[11]).toBe('മീനം')
    expect(RASIS).toHaveLength(12)
  })
})

describe('rasiIndexOf', () => {
  it('prefers the index the engine gave', () => {
    expect(rasiIndexOf({ rasi: 'മേടം', rasi_index: 5 })).toBe(5)
  })

  it('rejects an out-of-range index rather than trusting it', () => {
    expect(rasiIndexOf({ rasi_index: 99 })).toBeNull()
    expect(rasiIndexOf({ rasi_index: -1 })).toBeNull()
  })

  it('returns null when there is nothing to go on', () => {
    expect(rasiIndexOf({})).toBeNull()
  })
})

describe('the running mahadasha', () => {
  it('finds the period covering today and how far through it is', () => {
    const now = new Date('2014-01-01T00:00:00')
    const dasha = currentDasha(CHART, now)!
    expect(dasha.lord).toBe('Rahu')
    expect(dasha.lordMl).toBe('രാഹു')
    // 2005 → 2023, so 2014 is roughly half way.
    expect(dasha.progress).toBeGreaterThan(0.4)
    expect(dasha.progress).toBeLessThan(0.6)
  })

  it('returns null rather than drawing a bar at zero when the timeline ends', () => {
    // A bar at 0% is a claim about somebody's life period. An absent bar is
    // only an absent bar.
    expect(currentDasha(CHART, new Date('2099-01-01'))).toBeNull()
  })

  it('returns null for a chart with no dasha at all', () => {
    expect(currentDasha({ planets: {} })).toBeNull()
    expect(currentDasha(null)).toBeNull()
  })

  it('skips a period with unparseable dates instead of throwing', () => {
    const broken: NatalChart = {
      dasha: {
        mahadashas: [
          { lord: 'X', lord_ml: 'എക്സ്', start: 'nonsense', end: 'nonsense', years: 1 },
          { lord: 'Moon', lord_ml: 'ചന്ദ്രൻ', start: '2020-01-01', end: '2030-01-01', years: 10 },
        ],
      },
    }
    expect(currentDasha(broken, new Date('2025-01-01'))!.lord).toBe('Moon')
  })
})

describe('small things', () => {
  it('shortens planet names to fit a 9px cell', () => {
    expect(planetShort('jupiter')).toBe('Ju')
    expect(planetShort('Rahu')).toBe('Ra')
    expect(planetShort('unknown')).toBe('un')
  })

  it('shows only the year on the dasha bar', () => {
    // Enough to orient the bar, and it keeps a full date off a screen that may
    // be read over a shoulder.
    expect(yearOf('2005-06-15T00:00:00')).toBe('2005')
  })
})
