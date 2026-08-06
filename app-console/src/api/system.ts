// The SYSTEM section's slice of the API (console plan Part 13).
//
// Four unrelated surfaces that share one property: they answer questions about
// the installation rather than about a temple or a devotee.

import { apiGet, apiPost, apiPut } from './client'

// ---- integrations ----

/**
 * `system` out of GET /admin/overview.
 *
 * Every value here is a boolean or a name — the endpoint reports whether a
 * credential is present, never what it is. `integrations[x] === false` means
 * that service is mocked, which is the single most useful fact in the console:
 * it is the difference between "the reminder was sent" and "the reminder was
 * written to a log file".
 */
export interface SystemStatus {
  app_env: string
  chat_provider: string
  session_ttl_hours: number
  chat_rate_limit_per_hour: number
  integrations: Record<string, boolean>
  api_keys_present: Record<string, boolean>
}

export interface Overview {
  generated_at: string
  system: SystemStatus
  users: Record<string, unknown>
  chat: Record<string, unknown>
  llm: Record<string, unknown>
}

export const overview = (): Promise<Overview> => apiGet<Overview>('/admin/overview')

/** Just the live/mock flags. Any operator may ask. */
export interface IntegrationFlags {
  app_env: string
  integrations: Record<string, boolean>
}

/**
 * The flags without the analytics.
 *
 * The daily pack and the notification runs both need to know whether a button
 * really reaches anybody, and the daily pack is a content_reviewer's screen.
 * Fetching `/admin/overview` for that one boolean would also hand them the
 * devotee count, the chat volume and the token spend.
 */
export const integrationFlags = (): Promise<IntegrationFlags> =>
  apiGet<IntegrationFlags>('/admin/integrations')

// ---- the chat explorer ----

export interface ChatUser {
  phone: string
  name: string
  turns: number
  last_active: string | null
}

/** One stored turn. `messages` is the request the model saw, `reply` its answer. */
export interface ChatTurn {
  user_id: string
  conversation_id: string | null
  messages: { role: string; content: string }[]
  reply: string
  created_at: string
  llm_provider: string | null
  llm_model: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  price_inr: number | null
  price_usd: number | null
}

export const chatUsers = (): Promise<ChatUser[]> => apiGet<ChatUser[]>('/admin/users-chats')

/**
 * One devotee's transcript, newest turn first.
 *
 * The mobile is a path segment because that is how the route has always been
 * shaped and it is the user's identity key across the product. It is not birth
 * data — GUARDRAILS §4 is about dob, birth time, place, coordinates and derived
 * charts, none of which appear here — but it still needs encoding, since a
 * number stored as `+91…` becomes a space without it.
 */
export const chatHistory = (phone: string): Promise<ChatTurn[]> =>
  apiGet<ChatTurn[]>(`/admin/user-chat/${encodeURIComponent(phone)}`)

// ---- org tenants ----

export interface Org {
  id: number
  handle: string
  name: string
  plan: string
  active: boolean
  owner_user_id: number | null
  created_at: string
}

export const listOrgs = (): Promise<Org[]> => apiGet<Org[]>('/orgs')

export const setOrgPlan = (
  handle: string,
  body: { plan?: string; billing_status?: string },
): Promise<Record<string, unknown>> =>
  apiPost<Record<string, unknown>>(`/orgs/${encodeURIComponent(handle)}/plan`, body)

// ---- settings ----

export interface BookingSettings {
  service_fee_paise: number
}

export const bookingSettings = (): Promise<BookingSettings> =>
  apiGet<BookingSettings>('/bookings/settings')

export const setBookingSettings = (paise: number): Promise<BookingSettings> =>
  apiPut<BookingSettings>('/bookings/settings', { service_fee_paise: paise })
