// The PEOPLE section's slice of the API (console plan Part 12).
//
// Everything here is owner-only on the server. A temple_admin runs a temple;
// the devotee register, the practitioner directory and the list of who may sign
// in are not theirs to read.
//
// GUARDRAILS §4 shapes the user half and it shows in the types. `UserRow` — the
// search result — carries no birth data at all. `UserDetail` adds birth *place*
// and nothing more. A family member's date of birth and the natal chart each
// need their own request against one named user id, which is what keeps them
// out of every list, log line and query string.

import { apiDelete, apiGet, apiPatch, apiPost, apiPut, qs } from './client'

// ---- users ----

/** A search result. Deliberately narrow — this shape reaches a list. */
export interface UserRow {
  id: number
  name: string
  phone: string
  active: boolean
  org_id: number | null
  created_at: string
}

export interface UserPage {
  total: number
  limit: number
  offset: number
  items: UserRow[]
}

export interface Entitlement {
  id: number
  product_key: string
  granted_by: string
  source: string
  expires_at: string | null
  created_at: string
}

export interface UserPayment {
  id: number
  product: string
  amount_paise: number
  status: string
  razorpay_order_id: string | null
  created_at: string
  paid_at: string | null
}

export interface UserBooking {
  id: number
  ref: string
  temple_id: string
  pooja_name: string
  amount_paise: number
  service_fee_paise: number
  total_paise: number
  member_name: string
  member_nak: number | null
  when: string
  perform_on: string | null
  state: string
  created_at: string
}

export interface UserDetail {
  id: number
  name: string
  phone: string
  active: boolean
  /** Birth PLACE only. Date and time of birth are not on this shape. */
  birth_place: string
  tz: string
  org_id: number | null
  transcript_consent: boolean
  created_at: string
  bookings: UserBooking[]
  payments: UserPayment[]
  entitlements: Entitlement[]
}

/** A family-board row. `self` is the account holder's own, and cannot be removed. */
export interface Member {
  id: number
  name: string
  rel: string
  nak: number | null
  /** A birth DATE. There is no age field: an age is right for one year. */
  dob: string | null
  self: boolean
}

export interface Chart {
  computed_at: string
  natal: Record<string, unknown>
}

export const listUsers = (query: { q?: string; active?: boolean; limit?: number; offset?: number }) =>
  apiGet<UserPage>(`/admin/users${qs({ ...query })}`)

export const userDetail = (id: number) => apiGet<UserDetail>(`/admin/users/${id}`)

export const setUserActive = (id: number, active: boolean) =>
  apiPost<{ id: number; active: boolean }>(`/admin/users/${id}/active`, { active })

export const revokeEntitlement = (id: number) =>
  apiDelete<void>(`/admin/entitlements/${id}`)

// ---- one user's family board ----

export const listFamily = (userId: number) =>
  apiGet<Member[]>(`/admin/users/${userId}/family`)

export const addFamilyMember = (
  userId: number,
  body: { name: string; rel: string; nak: number | null; dob: string | null },
) => apiPost<Member>(`/admin/users/${userId}/family`, body)

/** Only the keys sent are changed, and `null` is a real value — "we asked and
 *  they do not know" is different from "leave it alone". */
export const patchFamilyMember = (
  userId: number,
  memberId: number,
  body: Partial<{ name: string; rel: string; nak: number | null; dob: string | null }>,
) => apiPatch<Member>(`/admin/users/${userId}/family/${memberId}`, body)

export const removeFamilyMember = (userId: number, memberId: number) =>
  apiDelete<void>(`/admin/users/${userId}/family/${memberId}`)

export const userChart = (userId: number) => apiGet<Chart>(`/admin/users/${userId}/chart`)

// The relation keys the app writes. The console shows English labels because
// operators work in English; the stored value stays the app's key so a devotee
// sees the same person under the same relation in their own language.
export const RELATIONS: [string, string][] = [
  ['rSelf', 'Self'],
  ['rMother', 'Mother'],
  ['rFather', 'Father'],
  ['rSpouse', 'Spouse'],
  ['rSon', 'Son'],
  ['rDaughter', 'Daughter'],
  ['rBrother', 'Brother'],
  ['rSister', 'Sister'],
  ['rOther', 'Other'],
]

export const relationLabel = (key: string): string =>
  RELATIONS.find(([k]) => k === key)?.[1] ?? key

// ---- astrologers ----

export interface AvailabilityWindow {
  /** 0 = Monday … 6 = Sunday, matching Python's date.weekday(). */
  weekday: number
  /** IST wall-clock "HH:MM". */
  start: string
  end: string
  duration_min: number
}

export interface Astrologer {
  id: string
  name: string
  name_ml: string
  district: string
  town: string
  lat: number
  lng: number
  specialties: string[]
  experience_years: number
  languages: string[]
  rating: number
  bio_ml: string
  availability: AvailabilityWindow[]
  active: boolean
  price_paise_per_min: number
  photo_key: string | null
  sort_order: number
  updated_at: string
}

export type AstrologerPatch = Partial<
  Pick<
    Astrologer,
    | 'name'
    | 'name_ml'
    | 'district'
    | 'town'
    | 'lat'
    | 'lng'
    | 'specialties'
    | 'experience_years'
    | 'languages'
    | 'rating'
    | 'bio_ml'
    | 'price_paise_per_min'
    | 'sort_order'
  >
>

export const listAstrologers = () => apiGet<Astrologer[]>('/astrologers/manage')

export const createAstrologer = (body: AstrologerPatch & { id: string; name: string; district: string; lat: number; lng: number }) =>
  apiPost<Astrologer>('/astrologers', body)

export const patchAstrologer = (id: string, body: AstrologerPatch) =>
  apiPatch<Astrologer>(`/astrologers/${encodeURIComponent(id)}`, body)

export const setAstrologerActive = (id: string, active: boolean) =>
  apiPost<Astrologer>(`/astrologers/${encodeURIComponent(id)}/active`, { active })

/** A full replacement of the weekly schedule, not a merge — the route is a PUT
 *  because "these are my hours" is how a person states it. Already-booked
 *  consults hold an absolute instant and are never cancelled by narrowing. */
export const replaceAvailability = (id: string, windows: AvailabilityWindow[]) =>
  apiPut<Astrologer>(`/astrologers/${encodeURIComponent(id)}/availability`, { windows })

// ---- operators ----

export interface RoleGrant {
  id: number
  role: string
  temple_id: string | null
}

export interface OperatorRow {
  id: number
  email: string | null
  phone: string | null
  name: string
  active: boolean
  /** Invited but has never set a password, so cannot sign in yet. */
  pending: boolean
  last_login_at: string | null
  roles: RoleGrant[]
}

export const ROLES = ['owner', 'temple_admin', 'content_reviewer', 'support'] as const
/** Only these are scoped to a temple; granting a temple to any other is meaningless. */
export const SCOPED_ROLES = ['temple_admin']

export const listOperators = () => apiGet<OperatorRow[]>('/admin/operators')

export const inviteOperator = (body: {
  email?: string
  phone?: string
  name?: string
  role: string
  temple_id?: string | null
}) =>
  apiPost<{ invite_token: string; expires_at: string; role: string }>(
    '/admin/operators/invite',
    body,
  )

export const grantRole = (operatorId: number, role: string, templeId: string | null) =>
  apiPost<RoleGrant>(`/admin/operators/${operatorId}/roles`, {
    role,
    temple_id: templeId,
  })

export const revokeRole = (roleId: number) =>
  apiDelete<void>(`/admin/operators/roles/${roleId}`)

export const setOperatorActive = (operatorId: number, active: boolean) =>
  apiPost<{ id: number; active: boolean }>(`/admin/operators/${operatorId}/active`, {
    active,
  })

// ---- engagement ----

export interface EngagedUser {
  user_id: number
  name: string
  phone: string
  checkins: number
  badges: number
  temples_visited: number
  districts_visited: number
  poojas: number
  streak: number
}

export interface Engagement {
  generated_at: string
  day: string
  users_counted: number
  users_total: number
  /** True when the register is larger than the aggregate counted. */
  truncated: boolean
  checkins: {
    total: number
    users_ever: number
    users_on_a_streak: number
    checked_in_today: number
  }
  milestones: { key: string; target: number; unlocked: number }[]
  most_engaged: EngagedUser[]
}

export const engagement = (limit = 25) =>
  apiGet<Engagement>(`/admin/engagement${qs({ limit })}`)
