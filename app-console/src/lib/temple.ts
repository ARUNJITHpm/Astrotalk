// Pure temple-domain logic: filtering the directory, working out what a save
// should actually send, and reading coordinates an operator pasted.
//
// It lives apart from the screens because every rule in here is one a test can
// pin without mounting React, and because two of them are easy to get subtly
// wrong in ways no rendering test would catch — see `diffTemple`.

import type { Temple, TemplePatch } from '../api/temples'

// ---- the directory list ----

export type Tri = 'any' | 'yes' | 'no'

export interface TempleFilter {
  q: string
  district: string
  deity: string
  reviewed: Tri
  active: Tri
}

export const EMPTY_FILTER: TempleFilter = {
  q: '',
  district: '',
  deity: '',
  reviewed: 'any',
  active: 'any',
}

function matchesTri(value: boolean, want: Tri): boolean {
  return want === 'any' || (want === 'yes') === value
}

/**
 * The rows a filter selects, in the order the server sent them (sort_order,
 * then id — a curated sequence the console must not silently re-shuffle).
 *
 * Search covers the id and the Malayalam name as well as the English one. The
 * id because it is what appears in a booking ref and a log line, so it is what
 * an operator arrives holding; the Malayalam name because half the directory is
 * better known by it. `toLowerCase` is a no-op on Malayalam script rather than
 * a corruption, so one pass handles both.
 */
export function filterTemples(temples: Temple[], f: TempleFilter): Temple[] {
  const q = f.q.trim().toLowerCase()
  return temples.filter((t) => {
    if (f.district && t.district !== f.district) return false
    if (f.deity && t.deity !== f.deity) return false
    if (!matchesTri(t.reviewed, f.reviewed)) return false
    if (!matchesTri(t.active, f.active)) return false
    if (!q) return true
    return [t.id, t.name, t.name_ml, t.town, t.town_ml ?? '', t.district].some((field) =>
      field.toLowerCase().includes(q),
    )
  })
}

/** Every district present, sorted — the filter's options come from the data. */
export function districtsOf(temples: Temple[]): string[] {
  return [...new Set(temples.map((t) => t.district).filter(Boolean))].sort()
}

// ---- saving ----

const PATCHABLE = [
  'name',
  'name_ml',
  'deity',
  'district',
  'town',
  'town_ml',
  'lat',
  'lng',
  'famous_for',
  'vazhipadu',
  'story',
  'story_ml',
  'hours',
  'timings',
  'rating',
  'reviews',
  'sort_order',
] as const satisfies readonly (keyof TemplePatch)[]

function sameValue(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a === null || b === null || a === undefined || b === undefined) return false
  if (typeof a === 'object' && typeof b === 'object') {
    // Shapes here are small and JSON-shaped (string[], number[][], a flat
    // record), so a structural compare is enough and needs no dependency.
    return JSON.stringify(a) === JSON.stringify(b)
  }
  return false
}

/**
 * Only what the operator actually changed.
 *
 * This is not an optimisation. `PATCH /temples/{id}` reads
 * `model_dump(exclude_unset=True)`, and an explicit `null` for `hours` or
 * `timings` CLEARS the column back to the module defaults. So a payload that
 * dutifully restates every field would wipe a temple's darshan windows every
 * time someone fixed a typo in its name. Sending nothing but the diff also
 * means two operators editing different fields of the same temple do not
 * overwrite each other.
 */
export function diffTemple(original: Temple, draft: TemplePatch): TemplePatch {
  const patch: Record<string, unknown> = {}
  for (const key of PATCHABLE) {
    if (!(key in draft)) continue
    if (!sameValue(draft[key], original[key])) patch[key] = draft[key]
  }
  return patch as TemplePatch
}

// ---- darshan windows ----

/** 555 → "09:15". Minutes past midnight is the stored unit. */
export function minutesToClock(minutes: number): string {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** "09:15" → 555, or null when it is not a time. */
export function clockToMinutes(clock: string): number | null {
  const match = /^(\d{1,2}):(\d{2})$/.exec(clock.trim())
  if (!match) return null
  const h = Number(match[1])
  const m = Number(match[2])
  if (h > 24 || m > 59 || h * 60 + m > 24 * 60) return null
  return h * 60 + m
}

/**
 * Why the server would refuse these windows, or null if it would not.
 *
 * Mirrors `_validate_hours` in temples/admin.py so an operator learns about a
 * reversed pair while looking at it, instead of after a round trip. The server
 * still checks — this is a courtesy, not the rule.
 */
export function hoursProblem(hours: number[][]): string | null {
  if (!hours.length) return 'Add at least one window, or switch back to the defaults.'
  for (const [open, close] of hours) {
    if (!(open < close)) return 'Each window must close after it opens.'
    if (open < 0 || close > 24 * 60) return 'Windows must fall inside a single day.'
  }
  return null
}

// ---- coordinates ----

export interface LatLng {
  lat: number
  lng: number
}

const COORD_PAIR = /(-?\d{1,3}(?:\.\d+)?)[,\s]+(-?\d{1,3}(?:\.\d+)?)/
const MAPS_AT = /@(-?\d{1,3}(?:\.\d+)?),(-?\d{1,3}(?:\.\d+)?)/
const MAPS_PLACE = /!3d(-?\d{1,3}(?:\.\d+)?)!4d(-?\d{1,3}(?:\.\d+)?)/

function valid(lat: number, lng: number): LatLng | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null
  return { lat, lng }
}

/**
 * Read a location out of whatever an operator pasted.
 *
 * Deliberately not a map widget. An operator locating a temple is already in
 * Google Maps — that is where the satellite view and the Malayalam place names
 * are — so the useful thing is to accept what that tab gives them: a share
 * link, a URL from the address bar, or the "9.9312, 76.2673" that right-click →
 * copy produces. An embedded map would mean a tile provider, a key and an
 * external request from a back-office tool, to reproduce a worse version of the
 * thing they already have open.
 *
 * Order matters: a Maps URL contains other numbers (zoom, ids), so the
 * URL-shaped patterns are tried before the bare pair.
 */
export function parseCoords(text: string): LatLng | null {
  const input = text.trim()
  if (!input) return null

  // `!3d..!4d..` is the place's own point; `@..` is only where the camera sits.
  // When a share link carries both, the place is the one the operator meant.
  for (const pattern of [MAPS_PLACE, MAPS_AT]) {
    const hit = pattern.exec(input)
    if (hit) {
      const found = valid(Number(hit[1]), Number(hit[2]))
      if (found) return found
    }
  }

  if (/^https?:/i.test(input)) {
    // A `?q=`/`?ll=` style link. Anything else in a URL is not a coordinate.
    const query = /[?&](?:q|ll|query|center|daddr)=([^&]+)/i.exec(input)
    if (!query) return null
    const pair = COORD_PAIR.exec(decodeURIComponent(query[1]))
    return pair ? valid(Number(pair[1]), Number(pair[2])) : null
  }

  const pair = COORD_PAIR.exec(input)
  return pair ? valid(Number(pair[1]), Number(pair[2])) : null
}
