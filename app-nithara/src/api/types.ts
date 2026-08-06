// TypeScript mirrors of the backend response shapes (field names match the API
// and the prototype 1:1, so components need no remapping). See
// NITHARA-UI-ENDPOINT-AUDIT.md for the source of truth.

export interface Temple {
  id: string
  en: string
  ml: string
  place: string
  mplace: string | null
  deity: string
  sig: string
  lat: number
  lng: number
  pooja: boolean
  open: boolean
  closes: string | null
  rating: string | null
  reviews: string | null
  distance_km: number | null
}

export interface PoojaCatalogueItem {
  key: string
  name: string
  name_ml: string
  amount: number
  lead_days: number
  locked: boolean
}

export interface TempleTimings {
  nirmalyam: string
  morning: string
  evening: string
}

export interface TempleDetail extends Temple {
  district: string
  story: string
  story_ml: string | null
  timings: TempleTimings
  poojas: PoojaCatalogueItem[]
}

export interface PoojaCatalogue {
  temple_id: string
  days_until: number | null
  poojas: PoojaCatalogueItem[]
  /** The booking fee added on top of the chosen offering. Served here because
   *  the app must show a total before an order exists, and the console can
   *  change this figure (PUT /bookings/settings) — a hardcoded 15 went stale
   *  the moment that screen shipped. */
  service_fee_paise: number
}

export interface CheckinResult {
  fresh: boolean
  temple_id: string
  temples_visited: number
}

export interface NakshatramDay {
  nakshatram_index: number
  nakshatram: string
  date: string
  days_until: number
}

export interface Panchangam {
  date: string
  nakshatram: string
  nalla_neram: string
  tithi: string
  mock: boolean
  source: string
}

export interface Today {
  date: string
  tithi: string
  nakshatram: string
  nalla_neram: string
  is_star_day: boolean
  note: string
}

export interface Booking {
  id: number
  ref: string
  temple_id: string
  pooja_key: string
  pooja_name: string
  amount_paise: number
  service_fee_paise: number
  total_paise: number
  member_id: number | null
  member_name: string
  member_nak: number | null
  when: string
  state: 'wait' | 'ok'
  order_id: string | null
  mock: boolean
  razorpay_key_id: string
  created_at: string
}

export interface Member {
  id: number
  name: string
  rel: string
  nak: number | null
  self: boolean
}

export interface Stats {
  temples_visited: number
  poojas: number
  streak: number
  badges: number
}

export interface Milestone {
  key: string
  current: number
  target: number
  got: boolean
}

export interface FeedItem {
  id: string
  cat: 'Festival' | 'Darshan' | 'AstroTalk'
  image: string
  glyph: string
  live: boolean
  title_en: string
  title_ml: string
  body_en: string
  body_ml: string
  who_en: string
  who_ml: string
  likes: number
  comments: number
  temple_id: string | null
}
