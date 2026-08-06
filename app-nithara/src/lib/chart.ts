// Reading a natal chart, without asking the backend to reshape it.
//
// NITHARA-BUILD-PLAN Part 3C settled this: the chart JSON already embeds every
// planet's rasi and whole-sign house plus a dasha timeline, so the rasi grid and
// the dasha bar are derived here rather than served. Nothing in this file
// interprets anything — it places facts on a grid. What a placement *means* is
// the knowledge corpus and the persona's job, never the frontend's.

/** The twelve rasis in engine order (astrology_engine/swiss_ephemeris.py RASIS),
 *  index 0 = മേടം. Kept in the same order so an index round-trips unchanged. */
export const RASIS = [
  'മേടം', 'ഇടവം', 'മിഥുനം', 'കർക്കടകം', 'ചിങ്ങം', 'കന്നി',
  'തുലാം', 'വൃശ്ചികം', 'ധനു', 'മകരം', 'കുംഭം', 'മീനം',
] as const

export const RASIS_EN = [
  'Mesha', 'Vrishabha', 'Mithuna', 'Karka', 'Simha', 'Kanya',
  'Thula', 'Vrischika', 'Dhanu', 'Makara', 'Kumbha', 'Meena',
] as const

/**
 * The South Indian chart's fixed layout, as DOM order for a 4x4 grid whose
 * centre cell is explicitly placed at rows 2-3 / columns 2-3.
 *
 *     Meena  Mesha   Vrishabha Mithuna
 *     Kumbha ┌─────────────┐   Karka
 *     Makara └─────────────┘   Simha
 *     Dhanu  Vrischika Thula   Kanya
 *
 * Signs sit in fixed positions in this style — unlike the North Indian chart,
 * where the houses are fixed and the signs move. Auto-placement flows around the
 * centre, so this order produces exactly that picture and any other order
 * produces a chart that is wrong in a way only a reader would catch.
 */
export const SOUTH_INDIAN_ORDER = [11, 0, 1, 2, 10, 3, 9, 4, 8, 7, 6, 5] as const

export interface Planet {
  rasi?: string
  rasi_index?: number
  house?: number
  retrograde?: boolean
  degree?: number
  nakshatra?: string
}

export interface NatalChart {
  rasi?: string
  nakshatram?: string
  lagnam?: string
  planets?: Record<string, Planet>
  dasha?: DashaBlock
  mock?: boolean
  birth_time_known?: boolean
}

export interface DashaPeriod {
  lord: string
  lord_ml: string
  start: string
  end: string
  years: number
}

export interface DashaBlock {
  mahadashas?: DashaPeriod[]
  starting_lord?: string
}

/** Short labels for the grid — the full names do not fit a 9px cell. */
const PLANET_SHORT: Record<string, string> = {
  sun: 'Su', moon: 'Mo', mercury: 'Me', venus: 'Ve', mars: 'Ma',
  jupiter: 'Ju', saturn: 'Sa', rahu: 'Ra', ketu: 'Ke',
  ascendant: 'Asc', lagna: 'Asc',
}

export const planetShort = (name: string): string =>
  PLANET_SHORT[name.toLowerCase()] ?? name.slice(0, 2)

/**
 * Which rasi a planet sits in.
 *
 * `rasi_index` when the engine gave one, otherwise the name looked up in RASIS.
 * Both paths exist because the mock ephemeris emits only the name — and a chart
 * that renders under a real engine and silently empties under the mock is a
 * defect nobody sees until the keys are missing on a demo machine.
 */
export function rasiIndexOf(planet: Planet): number | null {
  if (typeof planet.rasi_index === 'number' && planet.rasi_index >= 0 && planet.rasi_index < 12) {
    return planet.rasi_index
  }
  const byName = planet.rasi ? RASIS.indexOf(planet.rasi as (typeof RASIS)[number]) : -1
  return byName >= 0 ? byName : null
}

export interface RasiCell {
  index: number
  ml: string
  en: string
  /** Short labels, in a stable order so the grid does not reshuffle on re-render. */
  planets: string[]
  isLagna: boolean
}

/** The twelve cells, in the DOM order the South Indian grid needs. */
export function rasiCells(chart: NatalChart | null | undefined): RasiCell[] {
  const byRasi = new Map<number, string[]>()
  for (const [name, planet] of Object.entries(chart?.planets ?? {})) {
    const index = rasiIndexOf(planet)
    if (index == null) continue
    const label = planetShort(name) + (planet.retrograde ? '℞' : '')
    byRasi.set(index, [...(byRasi.get(index) ?? []), label])
  }
  const lagnaIndex = chart?.lagnam
    ? RASIS.indexOf(chart.lagnam as (typeof RASIS)[number])
    : -1

  return SOUTH_INDIAN_ORDER.map((index) => ({
    index,
    ml: RASIS[index],
    en: RASIS_EN[index],
    // Sorted so two renders of the same chart never disagree about order.
    planets: (byRasi.get(index) ?? []).sort(),
    isLagna: index === lagnaIndex,
  }))
}

export interface DashaNow {
  lord: string
  lordMl: string
  start: Date
  end: Date
  /** 0–1 through the current mahadasha. */
  progress: number
}

/**
 * The mahadasha running at `now`, and how far through it is.
 *
 * Returns null rather than guessing when the timeline does not cover `now` —
 * which happens for a chart computed before this code existed, or one whose
 * 120-year cycle has run out. A bar drawn at 0% would be a claim about
 * somebody's life period; an absent bar is only an absent bar.
 */
export function currentDasha(
  chart: NatalChart | null | undefined,
  now: Date = new Date(),
): DashaNow | null {
  const periods = chart?.dasha?.mahadashas
  if (!periods?.length) return null
  const t = now.getTime()
  for (const period of periods) {
    const start = new Date(period.start)
    const end = new Date(period.end)
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) continue
    if (t >= start.getTime() && t < end.getTime()) {
      const span = end.getTime() - start.getTime()
      return {
        lord: period.lord,
        lordMl: period.lord_ml,
        start,
        end,
        progress: span > 0 ? (t - start.getTime()) / span : 0,
      }
    }
  }
  return null
}

/** "1990" — the year alone. Enough to orient a dasha bar, and it keeps a full
 *  date of birth off a screen that may be shared or shoulder-read. */
export const yearOf = (iso: string | Date): string =>
  String((iso instanceof Date ? iso : new Date(iso)).getFullYear())
