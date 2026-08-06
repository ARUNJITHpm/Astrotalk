// The CONTENT section's pure rules.
//
// The point of pulling these out is the same as in lib/booking.ts: a rendering
// test proves a button appeared, not that it was the right button. The rules
// about which action a piece can take are the ones that go wrong quietly.

/** Publishing surfaces, mirroring content/models.py PLATFORMS. */
export const PLATFORMS: Record<string, string> = {
  wa_channel: 'WhatsApp channel',
  fb_post: 'Facebook',
  ig_reel: 'Instagram reel',
  yt_short: 'YouTube short',
}

/** What a daily piece is about (content/models.py KINDS). */
export const POST_KINDS: Record<string, string> = {
  panchangam: 'Panchangam',
  nakshatra: 'Nakshatram',
  festival: 'Festival',
  tip: 'Tip',
}

/** Studio formats, mirroring content/models.py STUDIO_KINDS. */
export const STUDIO_KINDS: { key: string; label: string; hint: string }[] = [
  { key: 'reel_script', label: 'Reel / Short script', hint: '45–60s spoken Malayalam, with a caption' },
  { key: 'weekly_astro_news', label: 'Weekly astro news', hint: 'ഈ ആഴ്ചയിലെ ജ്യോതിഷ വിശേഷങ്ങൾ' },
  { key: 'festival_special', label: 'Festival special', hint: 'name the festival in the topic box' },
  { key: 'nakshatra_episode', label: 'Nakshatram episode', hint: 'one of the 27 evergreen scripts' },
  { key: 'myth_buster', label: 'Myth-buster', hint: 'a gentle, no-fear correction' },
]

export const platformLabel = (key: string): string => PLATFORMS[key] ?? key
export const postKindLabel = (key: string): string => POST_KINDS[key] ?? key
export const studioKindLabel = (key: string): string =>
  STUDIO_KINDS.find((k) => k.key === key)?.label ?? key

/**
 * What an operator may do to a daily-pack piece in `status`.
 *
 * Mirrors content/service.py's transitions rather than guessing from the status
 * name. Offering a button the server will 409 is worse than hiding it: it
 * teaches an operator that a real conflict is a glitch to click through.
 *
 *   - **`draft` cannot be published.** Human approval is the safety net for
 *     public copy, and publish enforces it.
 *   - **`failed` can be approved again**, which is the retry path back to
 *     publish. Approve refused a failed piece until Part 13 and nothing else
 *     accepted it either, so a timed-out publish stranded it for good.
 *   - **`markPublished` is not offered on a failed piece**, because the server
 *     will not take it — approve first, then record the link.
 */
export interface PostActions {
  approve: boolean
  publish: boolean
  markPublished: boolean
}

export function postActions(status: string): PostActions {
  return {
    approve: status === 'draft' || status === 'approved' || status === 'failed',
    publish: status === 'approved',
    markPublished: status === 'draft' || status === 'approved',
  }
}

/**
 * Platforms the product can actually post to by itself.
 *
 * Only the WhatsApp channel has a wired publisher. `fb_post`, `ig_reel` and
 * `yt_short` go through adapters that log the body and return an external id
 * ending in `:mock` — and the post is then recorded as **published**, with a
 * timestamp, in a list an operator reads to decide what still needs doing.
 *
 * That is the trap this set exists to close. Pressing Publish on a Facebook
 * piece looks like it worked and nothing reached Facebook, so the console has
 * to say which button does what before it is pressed.
 */
export const AUTO_PUBLISH: ReadonlySet<string> = new Set(['wa_channel'])

/**
 * What Publish will really do for `platform`, or null when it does what it says.
 *
 * `whatsappLive` comes from the integrations snapshot (`mock_whatsapp` inverted).
 * Undefined means we could not ask — in which case we say so rather than
 * guessing, because both possible guesses are a claim about whether a message
 * reached a real phone.
 */
export function publishNote(platform: string, whatsappLive: boolean | undefined): string | null {
  if (!AUTO_PUBLISH.has(platform)) {
    return `Nithara cannot post to ${platformLabel(platform)} yet. Publishing here only records it — post it by hand and use "Mark posted" so the link is kept.`
  }
  if (whatsappLive === undefined) return 'WhatsApp status unknown — this may only be logged.'
  if (!whatsappLive) return 'WhatsApp is mocked, so this will be written to the log, not sent.'
  return null
}

/**
 * The same question for a studio draft, and a different answer.
 *
 * There is no `publish`: studio formats go to YouTube and Instagram, which the
 * product does not post to. Auto-publishing them is not "not built yet", it is
 * deliberately absent, so the screen must not imply the button is coming.
 */
export interface DraftActions {
  approve: boolean
  markPublished: boolean
  delete: boolean
}

export function draftActions(status: string): DraftActions {
  return {
    // Re-approving an approved draft is how an edit is saved, so it stays on.
    approve: status !== 'published',
    markPublished: status !== 'published',
    // A published draft is a record of something that exists in the world.
    // Deleting it would leave the post up with nothing here explaining it.
    delete: status !== 'published',
  }
}

/**
 * Whether `url` is something we are willing to record as "where I posted it".
 *
 * Deliberately strict about the scheme and nothing else. The value is stored
 * and later rendered as a link, and a `javascript:` string in an href is the
 * one input here that does more than look wrong. Beyond that it does not try to
 * guess whether a YouTube URL is really a YouTube URL — an operator pasting a
 * shortlink is doing something normal.
 */
export function urlProblem(raw: string): string | null {
  const text = raw.trim()
  if (!text) return 'Paste the public URL of the post you made.'
  let parsed: URL
  try {
    parsed = new URL(text)
  } catch {
    return 'That is not a URL. Include the https:// part.'
  }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    return 'Only http(s) links can be recorded.'
  }
  return null
}

/** Today as the API's `YYYY-MM-DD`, in the operator's own timezone. */
export function today(now: Date = new Date()): string {
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

/**
 * A plain-English reading of a run summary.
 *
 * The raw shape (`created: [], skipped: ['fb_post', …]`) reads like a failure
 * and is the opposite: the run is idempotent, and an empty `created` means
 * every platform already had its piece. An operator pressing the button twice
 * should be told that, not left wondering what broke.
 */
export function runSummary(summary: { created: string[]; skipped: string[] }): string {
  const made = summary.created.map(platformLabel)
  const had = summary.skipped.map(platformLabel)
  if (!made.length && !had.length) return 'Nothing to draft for that day.'
  if (!made.length) return `Already drafted for ${had.join(', ')}. Nothing new was created.`
  const tail = had.length ? ` ${had.join(', ')} already had one.` : ''
  return `Drafted for ${made.join(', ')}.${tail}`
}

// ---- the app feed ----

/** Categories the feed understands (content/feed.py CATEGORIES). */
export const FEED_CATEGORIES = ['Festival', 'Darshan', 'AstroTalk'] as const

/** Artwork keys the app has assets for, paired with their usual glyph. */
export const FEED_ART: { image: string; glyph: string; label: string }[] = [
  { image: 'i-fest', glyph: 'i-parasol', label: 'Festival' },
  { image: 'i-dars', glyph: 'i-lamp', label: 'Darshan' },
  { image: 'i-astr', glyph: 'i-sparkle', label: 'Astro talk' },
]

/** Mirror of feed_admin.py `_ID_RE`. */
const FEED_ID_RE = /^[a-z0-9][a-z0-9-]{1,60}$/

/**
 * Why a new card cannot be created yet, or null.
 *
 * Mirrors `feed_admin._validate` in both directions, and the attribution rule
 * is the one that earns its keep. A card with no `who_en` reads as an anonymous
 * authority making claims about a temple, which is exactly what GUARDRAILS §1
 * exists to stop — so the console refuses it here rather than letting an
 * operator write a whole notice and lose it to a 422.
 */
export function feedProblem(draft: {
  id?: string
  cat?: string
  title_en?: string
  who_en?: string
}): string | null {
  if (!FEED_ID_RE.test(draft.id ?? '')) {
    return 'The id must be lowercase letters, digits and hyphens — it becomes part of a URL.'
  }
  if (!FEED_CATEGORIES.includes((draft.cat ?? '') as (typeof FEED_CATEGORIES)[number])) {
    return `Pick a category: ${FEED_CATEGORIES.join(', ')}.`
  }
  if (!(draft.title_en ?? '').trim()) return 'A card needs a title.'
  if (!(draft.who_en ?? '').trim()) {
    return 'Say whose words these are. A notice from a temple carries that temple; anything in our own voice says Nithara.'
  }
  return null
}
