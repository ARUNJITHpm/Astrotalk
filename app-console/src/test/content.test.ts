// The CONTENT section's pure rules.
//
// Most of these pin a *refusal*. The screens are mostly buttons, and a button
// that appears when the server will reject it is not a cosmetic problem: it
// teaches an operator that a 409 is a glitch worth clicking through, and the
// next real conflict gets the same treatment.

import { describe, expect, it } from 'vitest'

import {
  AUTO_PUBLISH,
  FEED_CATEGORIES,
  draftActions,
  feedProblem,
  postActions,
  publishNote,
  runSummary,
  today,
  urlProblem,
} from '../lib/content'

describe('postActions', () => {
  it('lets a draft be approved but never published', () => {
    // Human approval is the safety net for public copy and publish enforces it,
    // so offering the button on a draft is offering a guaranteed 409.
    expect(postActions('draft')).toEqual({
      approve: true,
      publish: false,
      markPublished: true,
    })
  })

  it('lets an approved piece publish, and be re-approved after an edit', () => {
    expect(postActions('approved')).toEqual({
      approve: true,
      publish: true,
      markPublished: true,
    })
  })

  it('offers a failed piece the way back', () => {
    // The one that matters. A publish that timed out left the piece `failed`,
    // and every route out was shut: approve refused it, publish only takes
    // `approved`, mark-published only takes approved/draft, and the daily run
    // skips any platform that already has a row. One network blip stranded it
    // permanently. Approve now accepts `failed` — server side too.
    const can = postActions('failed')
    expect(can.approve).toBe(true)
    expect(can.publish).toBe(false)
    // Still not offered: the server refuses mark-published on a failed row.
    // Approve first, then record the link.
    expect(can.markPublished).toBe(false)
  })

  it('offers nothing on a published piece', () => {
    expect(postActions('published')).toEqual({
      approve: false,
      publish: false,
      markPublished: false,
    })
  })
})

describe('publishNote', () => {
  it('says plainly that Facebook is not wired', () => {
    // The trap: the adapter logs the body, returns `fb_post:mock`, and the row
    // is then recorded as PUBLISHED with a timestamp. It looks like it worked.
    const note = publishNote('fb_post', true)
    expect(note).toMatch(/cannot post to Facebook/i)
    expect(note).toMatch(/by hand/i)
  })

  it('is silent only when the button does exactly what it says', () => {
    expect(publishNote('wa_channel', true)).toBeNull()
  })

  it('warns when WhatsApp itself is mocked', () => {
    expect(publishNote('wa_channel', false)).toMatch(/log, not sent/i)
  })

  it('says so rather than guessing when it could not check', () => {
    // Both guesses are a claim about whether a message reached a real phone.
    expect(publishNote('wa_channel', undefined)).toMatch(/unknown/i)
  })

  it('knows the WhatsApp channel is the only wired publisher', () => {
    expect([...AUTO_PUBLISH]).toEqual(['wa_channel'])
  })
})

describe('draftActions', () => {
  it('never offers publish, because the studio has nowhere to publish to', () => {
    // YouTube and Instagram are not wired and are not going to be by this
    // screen. The absence has to be deliberate or it reads as "not built yet".
    expect('publish' in draftActions('draft')).toBe(false)
  })

  it('keeps approve available on an approved draft, since that is how an edit saves', () => {
    expect(draftActions('approved').approve).toBe(true)
  })

  it('will not delete something already posted in the world', () => {
    // The post stays up; deleting the row just removes the only record of it.
    expect(draftActions('published')).toEqual({
      approve: false,
      markPublished: false,
      delete: false,
    })
  })
})

describe('urlProblem', () => {
  it('accepts an ordinary link', () => {
    expect(urlProblem('https://youtube.com/watch?v=abc')).toBeNull()
    expect(urlProblem('  http://fb.com/x  ')).toBeNull()
  })

  it('asks for one when the box is empty', () => {
    expect(urlProblem('   ')).toMatch(/paste/i)
  })

  it('rejects text that is not a URL', () => {
    expect(urlProblem('posted it on insta')).toMatch(/not a URL/i)
  })

  it('rejects a javascript: scheme', () => {
    // This value is stored and later rendered as an href. It is the one input
    // here that does more than look wrong.
    expect(urlProblem('javascript:alert(1)')).toMatch(/http/i)
  })
})

describe('runSummary', () => {
  it('reads a first run as work done', () => {
    const text = runSummary({ created: ['wa_channel', 'fb_post'], skipped: [] })
    expect(text).toMatch(/WhatsApp channel/)
    expect(text).toMatch(/Facebook/)
  })

  it('explains an empty run instead of looking like a failure', () => {
    // `created: []` is what a second press produces, and the raw shape reads
    // like nothing worked when in fact everything was already there.
    const text = runSummary({ created: [], skipped: ['wa_channel'] })
    expect(text).toMatch(/already/i)
    expect(text).toMatch(/nothing new/i)
  })

  it('names both halves of a partial run', () => {
    const text = runSummary({ created: ['yt_short'], skipped: ['wa_channel'] })
    expect(text).toMatch(/YouTube short/)
    expect(text).toMatch(/WhatsApp channel already had one/)
  })
})

describe('today', () => {
  it('uses the operator’s own calendar day, not UTC', () => {
    // A late-evening IST date is already tomorrow in UTC. Sending the UTC day
    // would ask the server about the wrong day's pack.
    const lateEvening = new Date(2026, 6, 28, 23, 30)
    expect(today(lateEvening)).toBe('2026-07-28')
  })

  it('pads a single-digit month and day', () => {
    expect(today(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})

describe('feedProblem', () => {
  const ok = { id: 'pooram-2026', cat: 'Festival', title_en: 'Pooram', who_en: 'Devaswom' }

  it('passes a complete card', () => {
    expect(feedProblem(ok)).toBeNull()
  })

  it('insists on attribution', () => {
    // GUARDRAILS §1. A card with no `who_en` reads as an anonymous authority
    // making claims about somebody's temple.
    expect(feedProblem({ ...ok, who_en: '  ' })).toMatch(/whose words/i)
  })

  it('rejects an id that would not survive a URL', () => {
    expect(feedProblem({ ...ok, id: 'Pooram 2026' })).toMatch(/lowercase/i)
    expect(feedProblem({ ...ok, id: '-leading' })).toMatch(/lowercase/i)
    expect(feedProblem({ ...ok, id: '' })).toMatch(/lowercase/i)
  })

  it('rejects a category the server does not know', () => {
    expect(feedProblem({ ...ok, cat: 'Notice' })).toMatch(/Festival, Darshan, AstroTalk/)
  })

  it('mirrors the categories the backend enforces', () => {
    // content/feed.py CATEGORIES. A drift here is a 422 an operator meets only
    // after typing the whole notice.
    expect([...FEED_CATEGORIES]).toEqual(['Festival', 'Darshan', 'AstroTalk'])
  })
})
