// The CONTENT section's slice of the API (console plan Part 13).
//
// Two pipelines that look alike and are not. The **daily pack** is generated on
// a schedule, one piece per platform, and its pieces can be published by the
// product itself. The **studio** is generated on demand, in formats a human
// posts by hand to YouTube or Instagram, so it has no publish action at all —
// only "I posted it, here is the URL".
//
// Both are owner-or-content_reviewer on the server. They were "any operator"
// until Part 13; see tests/platform/test_carried_over_guards.py.

import { api, apiGet, apiPatch, apiPost, qs } from './client'

// ---- the daily pack ----

/** A daily-pack piece. `status` moves draft → approved → published. */
export interface ContentPost {
  id: number
  day: string
  platform: string
  kind: string
  body: string
  media_key: string | null
  media_url: string | null
  status: string
  external_id: string | null
  created_at: string
  published_at: string | null
}

export interface RunDailySummary {
  day: string
  /** Platforms a piece was drafted for on this run. */
  created: string[]
  /** Platforms that already had one — the run is idempotent. */
  skipped: string[]
}

export const listPosts = (day?: string): Promise<ContentPost[]> =>
  apiGet<ContentPost[]>(`/content/posts${qs({ day })}`)

export const runDaily = (day?: string): Promise<RunDailySummary> =>
  apiPost<RunDailySummary>(`/content/run-daily${qs({ day })}`)

/** Approve, optionally replacing the text the generator wrote. */
export const approvePost = (id: number, body?: string): Promise<ContentPost> =>
  apiPost<ContentPost>(`/content/posts/${id}/approve`, body === undefined ? {} : { body })

export const publishPost = (id: number): Promise<ContentPost> =>
  apiPost<ContentPost>(`/content/posts/${id}/publish`)

export const markPostPublished = (id: number, url: string): Promise<ContentPost> =>
  apiPost<ContentPost>(`/content/posts/${id}/mark-published`, { external_url: url })

// ---- the studio ----

export interface StudioDraft {
  id: number
  kind: string
  topic: string | null
  title: string
  body: string
  caption: string | null
  media_url: string | null
  status: string
  external_url: string | null
  created_at: string
  published_at: string | null
}

export const listStudio = (): Promise<StudioDraft[]> => apiGet<StudioDraft[]>('/content/studio')

export const generateStudio = (kind: string, topic: string): Promise<StudioDraft> =>
  apiPost<StudioDraft>('/content/generate', { kind, topic })

export const approveStudio = (id: number, body?: string): Promise<StudioDraft> =>
  apiPost<StudioDraft>(`/content/studio/${id}/approve`, body === undefined ? {} : { body })

export const markStudioPublished = (id: number, url: string): Promise<StudioDraft> =>
  apiPost<StudioDraft>(`/content/studio/${id}/mark-published`, { external_url: url })

export const deleteStudio = (id: number): Promise<void> =>
  api<void>(`/content/studio/${id}`, { method: 'DELETE' })

// ---- share cards ----

export interface ShareCard {
  slug: string
  kind: string
  title: string
  media_url: string
  share_url: string
  hits: number
}

/**
 * The public daily card for one nakshatram.
 *
 * `GET /content/cards/daily/{nakshatra}` is unauthenticated by design — the
 * whole point of a share card is that a stranger following a WhatsApp Status
 * can open it. It takes a name ("Ashwathi") or an index ("0").
 */
export const dailyCard = (nakshatra: string): Promise<ShareCard> =>
  apiGet<ShareCard>(`/content/cards/daily/${encodeURIComponent(nakshatra)}`)

// ---- the app feed ----

/** A notices card as the console reads it — drafts included. */
export interface FeedItem {
  id: string
  cat: string
  image: string
  glyph: string
  live: boolean
  title_en: string
  title_ml: string
  body_en: string
  body_ml: string
  who_en: string
  who_ml: string
  temple_id: string | null
  published: boolean
  sort_order: number
  updated_at: string
}

/** What a write may set. `likes`/`comments` are absent because they are not
 *  columns: the API serves 0 until real reactions exist, and the schema
 *  `forbid`s them so a typed-in count is an error rather than a silent no-op
 *  (GUARDRAILS §4 — never invent engagement counts). */
export interface FeedPatch {
  cat?: string
  image?: string
  glyph?: string
  live?: boolean
  title_en?: string
  title_ml?: string
  body_en?: string
  body_ml?: string
  who_en?: string
  who_ml?: string
  temple_id?: string | null
  sort_order?: number
}

/** Create takes the four the server insists on: an id, a category, a title and
 *  an attribution. Everything else has a default. */
export type FeedCreate = FeedPatch & {
  id: string
  cat: string
  title_en: string
  who_en: string
}

export const listFeed = (): Promise<FeedItem[]> => apiGet<FeedItem[]>('/content/feed/manage')

export const createFeedItem = (body: FeedCreate): Promise<FeedItem> =>
  apiPost<FeedItem>('/content/feed', body)

export const patchFeedItem = (id: string, body: FeedPatch): Promise<FeedItem> =>
  apiPatch<FeedItem>(`/content/feed/${encodeURIComponent(id)}`, body)

/** Publish or withdraw. There is no delete: pulling a wrong notice off the app
 *  should not destroy the text that then has to be corrected. */
export const setFeedPublished = (id: string, published: boolean): Promise<FeedItem> =>
  apiPost<FeedItem>(`/content/feed/${encodeURIComponent(id)}/published`, { published })
