// The CHANNELS section's pure rules.

import { describe, expect, it } from 'vitest'

import { clockStamp, normalizePhone, phoneProblem, sendReality } from '../lib/channels'

describe('normalizePhone', () => {
  it('agrees with the server, digit for digit', () => {
    // This has to match identity/service.py `normalize_phone` exactly. The
    // phone IS the identity key across SQL, chat history and WhatsApp sessions,
    // so a console that normalised differently would open a SECOND conversation
    // for someone who already has one — and show an empty history for a devotee
    // who has been writing in for months.
    expect(normalizePhone('+91 98765 43210')).toBe('+919876543210')
    expect(normalizePhone('+91-98765-43210')).toBe('+919876543210')
    expect(normalizePhone(' +919876543210 ')).toBe('+919876543210')
  })

  it('keeps a leading plus and only a leading plus', () => {
    expect(normalizePhone('9876543210')).toBe('9876543210')
    expect(normalizePhone('00919876543210')).toBe('00919876543210')
  })

  it('drops everything that is not a digit', () => {
    expect(normalizePhone('(0484) 123 4567')).toBe('04841234567')
  })
})

describe('phoneProblem', () => {
  it('accepts a real mobile', () => {
    expect(phoneProblem('+91 98765 43210')).toBeNull()
  })

  it('asks for a number when there is none', () => {
    expect(phoneProblem('   ')).toMatch(/enter a number/i)
  })

  it('catches a short number before the server answers in character', () => {
    // The server replies to a too-short number with a friendly Malayalam
    // "❌ Invalid phone number" — as a CHAT REPLY. The mistake would arrive
    // looking like something the brain said.
    expect(phoneProblem('+91987')).toMatch(/too short/i)
  })
})

describe('clockStamp', () => {
  it('pads to a wall clock', () => {
    expect(clockStamp(new Date(2026, 6, 28, 9, 5))).toBe('09:05')
    expect(clockStamp(new Date(2026, 6, 28, 23, 59))).toBe('23:59')
  })
})

describe('sendReality', () => {
  it('does not let a mocked run be quoted as delivery', () => {
    // "12 sent" is exactly the sentence an operator would repeat to a temple,
    // and the run reports it whether or not WhatsApp is wired.
    const text = sendReality(12, false)
    expect(text).toMatch(/mocked/i)
    expect(text).toMatch(/no message was delivered/i)
  })

  it('says sent when it means sent', () => {
    expect(sendReality(12, true)).toBe('12 messages sent.')
    expect(sendReality(1, true)).toBe('1 message sent.')
  })

  it('marks it unconfirmed rather than guessing', () => {
    expect(sendReality(3, undefined)).toMatch(/unconfirmed/i)
  })
})
