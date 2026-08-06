// What the home screen is willing to claim.
//
// Most of these pin a card NOT appearing. The prototype's rail asserted
// pradosham every day, named an invented astrologer with a made-up rate, and
// hardcoded a festival at a specific temple at a specific hour. All three look
// fine on screen and are statements about the world.

import { describe, expect, it } from 'vitest'

import { buildPromos, type PromoInput } from './promos'
import type { FeedItem, Member, NakshatramDay, Panchangam } from '../api/types'

const t = (key: string) => key
const nakName = (i: number) => `star-${i}`

function member(over: Partial<Member> = {}): Member {
  return { id: 1, name: 'Ananya', rel: 'rSelf', nak: 21, self: true, ...over }
}

function starDay(nak: number, days: number): NakshatramDay {
  return {
    nakshatram_index: nak,
    nakshatram: `star-${nak}`,
    date: '2026-08-12',
    days_until: days,
  }
}

function panchangam(over: Partial<Panchangam> = {}): Panchangam {
  return {
    date: '2026-08-06',
    nakshatram: 'വിശാഖം',
    nalla_neram: '06:30–07:30',
    tithi: 'ദ്വിതീയ',
    mock: false,
    source: 'swiss-ephemeris',
    ...over,
  }
}

function feedItem(over: Partial<FeedItem> = {}): FeedItem {
  return {
    id: 'pooram',
    cat: 'Festival',
    image: 'i-fest',
    glyph: 'i-parasol',
    live: true,
    title_en: 'Ilanjithara Melam',
    title_ml: 'ഇലഞ്ഞിത്തറ മേളം',
    body_en: '',
    body_ml: '',
    who_en: 'Vadakkunnathan',
    who_ml: 'വടക്കുന്നാഥൻ',
    likes: 0,
    comments: 0,
    temple_id: 'tsr-vadakkunnathan',
    ...over,
  }
}

const base: PromoInput = {
  panchangam: panchangam(),
  members: [],
  starDays: [],
  feed: [],
  t,
  lang: 'en',
  nakName,
}

const keys = (input: Partial<PromoInput> = {}) =>
  buildPromos({ ...base, ...input }).map((p) => p.key)

describe('what is never claimed', () => {
  it('does not say it is pradosham on a day that is not', () => {
    // The prototype showed this card unconditionally. Pradosham is the evening
    // of trayodashi — a fact somebody may act on, not a decoration.
    expect(keys()).not.toContain('pradosham')
  })

  it('says it on a day that is', () => {
    expect(keys({ panchangam: panchangam({ tithi: 'ത്രയോദശി' }) })).toContain('pradosham')
  })

  it('stays quiet when the ephemeris is mocked', () => {
    // A mocked panchangam produces a plausible tithi from a seed. It must not
    // become a claim about a real observance.
    const mocked = panchangam({ tithi: 'ത്രയോദശി', mock: true })
    expect(keys({ panchangam: mocked })).not.toContain('pradosham')
  })

  it('never advertises an astrologer', () => {
    // The directory is seeded dummy data and the Astro screen already refuses
    // to render it — inventing practitioners is fabricated social proof.
    const built = buildPromos(base)
    expect(built.some((p) => /astro|consult/i.test(p.key))).toBe(false)
  })

  it('shows no festival unless a real one is published', () => {
    expect(keys()).not.toContain('feed-pooram')
    expect(keys({ feed: [feedItem()] })).toContain('feed-pooram')
  })

  it('ignores a festival notice that is not live', () => {
    expect(keys({ feed: [feedItem({ live: false })] })).not.toContain('feed-pooram')
  })

  it('ignores a festival with no temple to open', () => {
    // The card's CTA is "View". A button that does nothing is worse than an
    // absent card.
    expect(keys({ feed: [feedItem({ temple_id: null })] })).not.toContain('feed-pooram')
  })
})

describe('star days lead the rail', () => {
  it('puts a near star day first, ahead of everything else', () => {
    const built = buildPromos({
      ...base,
      members: [member()],
      starDays: [starDay(21, 3)],
      feed: [feedItem()],
      panchangam: panchangam({ tithi: 'ത്രയോദശി' }),
    })
    expect(built[0].key).toBe('star-1')
    expect(built[0].count).toBe(3)
  })

  it('marks the account holder’s own star differently from a relative’s', () => {
    const mine = buildPromos({ ...base, members: [member()], starDays: [starDay(21, 2)] })
    expect(mine[0].cls).toBe('p-star')

    const theirs = buildPromos({
      ...base,
      members: [member({ id: 2, name: 'Amma', rel: 'rMother', self: false, nak: 10 })],
      starDays: [starDay(10, 2)],
    })
    expect(theirs[0].cls).toBe('p-kin')
    expect(theirs[0].title).toContain('Amma')
  })

  it('orders several relatives by how soon their star falls', () => {
    const built = buildPromos({
      ...base,
      members: [
        member({ id: 1, nak: 1, self: false, name: 'A', rel: 'rFather' }),
        member({ id: 2, nak: 2, self: false, name: 'B', rel: 'rMother' }),
      ],
      starDays: [starDay(1, 9), starDay(2, 2)],
    })
    expect(built.slice(0, 2).map((p) => p.title)).toEqual(['B · rMother', 'A · rFather'])
  })

  it('drops a star day too far out to act on', () => {
    expect(keys({ members: [member()], starDays: [starDay(21, 40)] })).not.toContain('star-1')
  })

  it('keeps today’s star day', () => {
    expect(keys({ members: [member()], starDays: [starDay(21, 0)] })).toContain('star-1')
  })

  it('skips a member with no nakshatram set rather than guessing one', () => {
    expect(keys({ members: [member({ nak: null })], starDays: [] })).not.toContain('star-1')
  })
})

describe('the rail always has something', () => {
  it('falls back to the one card that is always true', () => {
    // No members, no festival, an ordinary tithi. "Ask Nithara" promises
    // nothing the app does not deliver.
    expect(keys()).toEqual(['nithara'])
  })

  it('survives having no panchangam at all', () => {
    expect(keys({ panchangam: undefined })).toEqual(['nithara'])
  })
})
