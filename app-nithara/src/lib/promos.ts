// The home screen's promo rail, composed from data the app already has.
//
// NITHARA-BUILD-PLAN Part 4 settled that this is NOT a backend endpoint: the
// rail is presentation logic over panchangam, members and the star calendar,
// exactly as the prototype's PROMOS() built it client-side. Baking banner
// ordering into an API would put UI decisions on the server for no gain.
//
// Three of the prototype's six cards are deliberately NOT ported, and that is
// the substance of this file rather than an omission:
//
//   * "Pradosham today" was shown unconditionally. Pradosham is the evening of
//     trayodashi — a fact about a specific day, not a decoration — so telling
//     somebody it is pradosham when it is not is a false statement about an
//     observance they may act on. It now appears only when the panchangam says
//     the tithi IS trayodashi.
//   * The astrologer card named a practitioner and quoted "₹45 a minute". The
//     directory is seeded dummy data and the Astro screen already refuses to
//     render it, because presenting invented practitioners is fabricated social
//     proof (GUARDRAILS §1). A promo doing it on the home screen would be worse.
//   * The festival card hardcoded "Ilanjithara Melam · Vadakkunnathan, 5 PM".
//     That is a claim about a live event on a real date. It now comes from a
//     published Festival card in the feed, or it does not appear.

import type { FeedItem, Member, NakshatramDay, Panchangam } from '../api/types'

export interface Promo {
  key: string
  /** Palette class from globals.css (.p-star, .p-kin, .p-night, …). */
  cls: string
  glyph: string
  tag: string
  /** Highlighted tag — the prototype's `hot`. */
  hot?: boolean
  /** Days remaining, shown as a big countdown. */
  count?: number
  title: string
  sub: string
  cta: string
  action: PromoAction
}

export type PromoAction =
  | { kind: 'poojas' }
  | { kind: 'chat' }
  | { kind: 'temple'; templeId: string }

/** How near a star day has to be before it leads the rail. */
const STAR_WINDOW_DAYS = 12

export interface PromoInput {
  panchangam?: Panchangam
  members: Member[]
  /** Upcoming star days, one per member nakshatram (from /astrology/nakshatram/next). */
  starDays: NakshatramDay[]
  feed: FeedItem[]
  t: (key: string) => string
  lang: 'en' | 'ml'
  nakName: (index: number) => string
}

/**
 * Pradosham is the evening of trayodashi — the thirteenth tithi.
 *
 * A named lookup, not an interpretation: the mapping is definitional, and the
 * alternative was the prototype's version, which asserted it every day.
 */
const isPradosham = (panchangam?: Panchangam): boolean =>
  !!panchangam && !panchangam.mock && panchangam.tithi.includes('ത്രയോദശി')

/**
 * The rail, in order. Highest intent first: a star day inside the booking
 * window is the most useful thing the home screen can say, and a card nobody
 * can act on today should not outrank it.
 */
export function buildPromos(input: PromoInput): Promo[] {
  const { panchangam, members, starDays, feed, t, lang, nakName } = input
  const promos: Promo[] = []

  // Star days, nearest first. One card per member whose star is close.
  //
  // `days_until` comes from the server, which computed it against the same
  // calendar the star day itself came from. Recomputing it here from an ISO
  // date would introduce a timezone the backend does not have — and be off by
  // one for anybody awake near midnight.
  const byNak = new Map(starDays.map((d) => [d.nakshatram_index, d]))
  const upcoming = members
    .filter((m) => m.nak != null)
    .map((m) => ({ member: m, day: byNak.get(m.nak as number) }))
    .filter((x) => !!x.day)
    .map((x) => ({ member: x.member, days: x.day!.days_until }))
    .filter((x) => x.days >= 0 && x.days <= STAR_WINDOW_DAYS)
    .sort((a, b) => a.days - b.days)

  for (const { member, days } of upcoming) {
    const star = nakName(member.nak as number)
    promos.push({
      key: `star-${member.id}`,
      cls: member.self ? 'p-star' : 'p-kin',
      glyph: 'i-star',
      tag: member.self ? t('starKicker') : t('kinStarTag'),
      hot: member.self,
      count: days,
      title: member.self ? `${star} · ${t('yourStar')}` : `${member.name} · ${t(member.rel)}`,
      sub: member.self ? t('bookForStar') : `${star} · ${t('bookForStar')}`,
      cta: t('bookPooja'),
      action: { kind: 'poojas' },
    })
  }

  // Only when the day really is trayodashi — see isPradosham.
  if (isPradosham(panchangam)) {
    promos.push({
      key: 'pradosham',
      cls: 'p-night',
      glyph: 'i-moon',
      tag: t('tagToday'),
      title: t('promoPradT'),
      sub: t('promoPradS'),
      cta: t('promoPradC'),
      action: { kind: 'chat' },
    })
  }

  // Always true, and it promises nothing we do not deliver.
  promos.push({
    key: 'nithara',
    cls: 'p-orange',
    glyph: 'i-sparkle',
    tag: t('tagFree'),
    hot: true,
    title: t('promoNitT'),
    sub: t('promoNitS'),
    cta: t('promoNitC'),
    action: { kind: 'chat' },
  })

  // A real festival notice, or none at all — and only one that has a temple to
  // open. The card's CTA is "View"; a notice with no temple_id has nothing to
  // show, and a button that does nothing is worse than an absent card.
  const festival = feed.find((f) => f.cat === 'Festival' && f.live && f.temple_id)
  if (festival) {
    promos.push({
      key: `feed-${festival.id}`,
      cls: 'p-fest',
      glyph: 'i-parasol',
      tag: t('tagLive'),
      title: lang === 'ml' ? festival.title_ml || festival.title_en : festival.title_en,
      sub: lang === 'ml' ? festival.who_ml || festival.who_en : festival.who_en,
      cta: t('promoFestC'),
      action: { kind: 'temple', templeId: festival.temple_id as string },
    })
  }

  return promos
}
