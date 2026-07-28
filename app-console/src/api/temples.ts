// The TEMPLES section's slice of the API (console plan Part 10).
//
// Types mirror app/modules/temples/schemas.py. Where the backend draws a line
// this file draws the same one rather than smoothing it over:
//
//   - `reviewed` and `active` are absent from TemplePatch. They have their own
//     routes because they answer to different roles — `reviewed` asserts an
//     astrologer checked the devotional copy (GUARDRAILS §1), so the role that
//     WRITES a temple's story must not be the one that certifies it.
//   - Money is paise everywhere here. The app's read contract quotes whole
//     rupees, which is a lossy rendering; the console is where the
//     authoritative figure is set, so it must not round-trip through it.
//   - `null` on an override means INHERIT the master value, and it is not the
//     same as 0. Changing a lead time must not silently freeze today's price.

import { authHeaders } from '../lib/session'
import { ApiError, api, apiDelete, apiGet, apiPatch, apiPost, apiUrl, qs } from './client'

/** A directory row as the console edits it — every stored column. */
export interface Temple {
  id: string
  name: string
  name_ml: string
  deity: string
  district: string
  town: string
  town_ml: string | null
  lat: number
  lng: number
  famous_for: string
  vazhipadu: string[]
  reviewed: boolean
  story: string | null
  story_ml: string | null
  hours: number[][] | null
  timings: Record<string, string> | null
  rating: string | null
  reviews: string | null
  active: boolean
  image_key: string | null
  sort_order: number
  updated_at: string
}

/** The editable subset. Deliberately not `Partial<Temple>`: the four fields it
 *  omits (id, reviewed, active, image_key) each have their own route, and the
 *  server rejects unknown keys outright (`extra="forbid"`). */
export type TemplePatch = Partial<
  Pick<
    Temple,
    | 'name'
    | 'name_ml'
    | 'deity'
    | 'district'
    | 'town'
    | 'town_ml'
    | 'lat'
    | 'lng'
    | 'famous_for'
    | 'vazhipadu'
    | 'story'
    | 'story_ml'
    | 'hours'
    | 'timings'
    | 'rating'
    | 'reviews'
    | 'sort_order'
  >
>

export type TempleCreate = TemplePatch & {
  id: string
  name: string
  deity: string
  district: string
  lat: number
  lng: number
}

export interface Pooja {
  key: string
  name: string
  name_ml: string
  description: string | null
  amount_paise: number
  lead_days: number
  active: boolean
  sort_order: number
}

export interface TempleOverride {
  temple_id: string
  pooja_key: string
  /** null = inherit the master price. */
  amount_paise: number | null
  /** null = inherit the master lead time. */
  lead_days: number | null
  /** false = this temple does not offer it, which differs from having no override. */
  active: boolean
}

export interface Partner {
  id: number
  temple_id: string
  slug: string
  contact_name: string
  tier: string
  active: boolean
  created_at: string
}

export interface Festival {
  id: number
  temple_id: string
  name: string
  name_ml: string
  day: string
}

// Keys of app/modules/temples/remedy_map.py DEITIES. The server rejects
// anything else, so the editor offers a select rather than a free-text box that
// fails on save.
export const DEITIES = [
  'devi',
  'dhanwantari',
  'ganapathi',
  'hanuman',
  'krishna',
  'naga',
  'saraswati',
  'sastha',
  'shiva',
  'subrahmanya',
  'surya',
  'vishnu',
] as const

export const TIMING_KEYS = ['nirmalyam', 'morning', 'evening'] as const

export const PARTNER_TIERS = ['free', 'partner'] as const

// ---- temples ----

export const listTemples = () => apiGet<Temple[]>('/temples/manage')

export const createTemple = (body: TempleCreate) => apiPost<Temple>('/temples', body)

export const patchTemple = (id: string, body: TemplePatch) =>
  apiPatch<Temple>(`/temples/${encodeURIComponent(id)}`, body)

export const setTempleActive = (id: string, active: boolean) =>
  apiPost<Temple>(`/temples/${encodeURIComponent(id)}/active`, { active })

export const setTempleReviewed = (id: string, reviewed: boolean) =>
  apiPatch<Temple>(`/temples/${encodeURIComponent(id)}/review`, { reviewed })

/**
 * Upload the temple photo.
 *
 * The body is the file itself, not multipart — the route was written that way
 * so the backend need not depend on python-multipart for one endpoint. So this
 * is the one call that cannot go through apiPost: JSON.stringify would turn the
 * bytes into "{}".
 */
export const uploadTempleImage = (id: string, file: File) =>
  api<{ temple_id: string; image_key: string; url: string }>(
    `/temples/${encodeURIComponent(id)}/image`,
    { method: 'POST', body: file, headers: { 'Content-Type': file.type } },
  )

// ---- offerings ----

export const listPoojas = () => apiGet<Pooja[]>('/temples/poojas')

export const createPooja = (body: Omit<Pooja, 'description'> & { description?: string }) =>
  apiPost<Pooja>('/temples/poojas', body)

export const patchPooja = (key: string, body: Partial<Omit<Pooja, 'key'>>) =>
  apiPatch<Pooja>(`/temples/poojas/${encodeURIComponent(key)}`, body)

export const listOverrides = (templeId: string) =>
  apiGet<TempleOverride[]>(`/temples/${encodeURIComponent(templeId)}/overrides`)

export const setOverride = (
  templeId: string,
  poojaKey: string,
  body: { amount_paise: number | null; lead_days: number | null; active: boolean },
) =>
  api<TempleOverride>(
    `/temples/${encodeURIComponent(templeId)}/poojas/${encodeURIComponent(poojaKey)}`,
    { method: 'PUT', body: JSON.stringify(body) },
  )

export const clearOverride = (templeId: string, poojaKey: string) =>
  apiDelete<void>(
    `/temples/${encodeURIComponent(templeId)}/poojas/${encodeURIComponent(poojaKey)}`,
  )

// ---- partners, festivals ----

export const listPartners = () => apiGet<Partner[]>('/temples/partners')

export const createPartner = (body: {
  temple_id: string
  slug: string
  contact_name?: string
  contact_phone?: string
  tier?: string
}) => apiPost<Partner>('/temples/partners', body)

export const patchPartner = (
  slug: string,
  body: Partial<{ contact_name: string; contact_phone: string; tier: string; active: boolean }>,
) => apiPatch<Partner>(`/temples/partners/${encodeURIComponent(slug)}`, body)

/**
 * The printable QR poster, as a blob URL.
 *
 * It cannot be an `<img src>`: the route is operator-gated and an image request
 * carries no credential. So it is fetched like any other call and handed to the
 * browser as an object URL — which the caller must revoke, or every peek at a
 * QR leaks a few KB for the life of the tab.
 */
export async function partnerQrUrl(slug: string): Promise<string> {
  const res = await fetch(apiUrl(`/temples/partners/${encodeURIComponent(slug)}/qr.png`), {
    headers: authHeaders(),
  })
  if (!res.ok) throw new ApiError(res.status, await res.text().catch(() => ''))
  return URL.createObjectURL(await res.blob())
}

/** Where a stored image key is served from. Storage's own default mapping. */
export const mediaUrl = (key: string): string => apiUrl(`/media/${key}`)

export const listFestivals = (templeId?: string) =>
  apiGet<Festival[]>(`/temples/festivals${qs({ temple_id: templeId })}`)

export const createFestival = (
  slug: string,
  body: { name: string; name_ml?: string; day: string },
) => apiPost<Festival>(`/temples/partners/${encodeURIComponent(slug)}/festivals`, body)

export const patchFestival = (
  id: number,
  body: Partial<{ name: string; name_ml: string; day: string }>,
) => apiPatch<Festival>(`/temples/festivals/${id}`, body)

export const deleteFestival = (id: number) => apiDelete<void>(`/temples/festivals/${id}`)

/** Rupees for display. Paise are the stored unit; this never feeds a payload. */
export const rupees = (paise: number): string =>
  (paise / 100).toLocaleString('en-IN', { maximumFractionDigits: 2 })
