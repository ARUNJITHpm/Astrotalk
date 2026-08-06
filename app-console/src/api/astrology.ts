// The ASTROLOGY section's slice of the API (console plan Part 13).
//
// Both of these are read-only testers for engines the product already runs.
// They exist so an operator can answer "is the panchangam right today" or "why
// did the chat suggest that temple" without opening a Python shell.
//
// Neither takes birth data, and that is not an accident of the current design —
// `/temples/suggest` accepts already-derived keys (`dosha=sade_sati`) precisely
// so a suggestion can be requested without a chart (GUARDRAILS §4). A tester
// that grew a date-of-birth box would put birth data in a query string.

import { apiGet, qs } from './client'

export interface Panchangam {
  date: string
  nakshatram: string
  nalla_neram: string
  tithi: string
  /** True when the ephemeris is mocked — the figures are placeholders. */
  mock: boolean
  source: string
}

export const panchangam = (day?: string): Promise<Panchangam> =>
  apiGet<Panchangam>(`/astrology/panchangam${qs({ day })}`)

/** Life concerns the suggester understands (temples/router.py `suggest`). */
export const CONCERNS = [
  'career',
  'marriage',
  'children',
  'education',
  'health',
  'wealth',
  'ancestors',
  'obstacles',
  'peace',
] as const

export interface TempleSuggestion {
  id: string
  name: string
  name_ml: string
  deity: string
  deity_ml: string
  district: string
  town: string
  famous_for: string
  vazhipadu: string[]
  days: string
  mantra: string
  /** Why this temple matched — the tester's whole reason for existing. */
  reason: string
  /** Only present when the caller supplied a location, which we do not. */
  distance_km: number | null
}

export const suggestTemples = (params: {
  concern?: string
  district?: string
  k?: number
}): Promise<TempleSuggestion[]> =>
  apiGet<TempleSuggestion[]>(`/temples/suggest${qs({ ...params })}`)
