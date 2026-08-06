// The CHANNELS section's slice of the API (console plan Part 13).
//
// Two surfaces that both end at a real person's phone, which is why both are
// owner-only on the server.

import { apiPost, qs } from './client'

// ---- the WhatsApp simulator ----

export interface SimulateReply {
  reply: string
}

/**
 * Route one message through the SAME brain the real WhatsApp webhook uses —
 * onboarding FSM, registration, chat — as if it came from `phone`.
 *
 * The phone goes in the **body**, never the path. Conversation state is kept
 * server-side per number, so there is nothing to accumulate here: the reply
 * that comes back is the reply that number would really have received.
 */
export const simulate = (phone: string, text: string): Promise<SimulateReply> =>
  apiPost<SimulateReply>('/whatsapp/simulate', { phone, text })

// ---- notification runs ----

export interface FestivalRunSummary {
  target_day: string
  festivals: number
  sent: number
  skipped: number
}

export interface NakshatramRunSummary {
  target_lead_days: number
  reminders_sent: number
}

/**
 * Send the T-3-day festival update to subscribers.
 *
 * Idempotent — the notification log holds a unique row per (festival, phone),
 * so a second press never double-sends. That is the property that makes a
 * manual "run now" button safe to offer at all.
 */
export const runFestivals = (today?: string): Promise<FestivalRunSummary> =>
  apiPost<FestivalRunSummary>(`/notifications/run-festivals${qs({ today })}`)

/** Push star-day reminders to registered devices, same T-3 window. */
export const runNakshatramReminders = (today?: string): Promise<NakshatramRunSummary> =>
  apiPost<NakshatramRunSummary>(`/notifications/run-nakshatram-reminders${qs({ today })}`)
