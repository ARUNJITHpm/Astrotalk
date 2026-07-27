// Which header the console sends, and where the credential lives.

import { beforeEach, describe, expect, it } from 'vitest'

import { authHeaders, clearToken, getTokenKind, setToken } from '../lib/session'

beforeEach(() => {
  sessionStorage.clear()
})

describe('credential storage', () => {
  it('sends an operator session as a bearer token', () => {
    setToken('sess-abc', 'operator')
    expect(authHeaders()).toEqual({ Authorization: 'Bearer sess-abc' })
  })

  it('sends the owner ADMIN_TOKEN as X-Admin-Token', () => {
    // admin_auth.py accepts either, but only in its own header. Sending the
    // admin token as a bearer reads as an unknown session — a silent 401.
    setToken('the-admin-token', 'admin_token')
    expect(authHeaders()).toEqual({ 'X-Admin-Token': 'the-admin-token' })
  })

  it('sends nothing at all when signed out', () => {
    expect(authHeaders()).toEqual({})
  })

  it('forgets both the token and its kind on sign-out', () => {
    setToken('the-admin-token', 'admin_token')
    clearToken()
    expect(authHeaders()).toEqual({})
    // Kind falls back to the safer default rather than remembering "owner".
    expect(getTokenKind()).toBe('operator')
  })

  it('keeps the credential out of localStorage', () => {
    // A back-office machine may be shared. The token should die with the tab;
    // the consumer app makes the opposite trade on purpose.
    setToken('sess-abc', 'operator')
    expect(localStorage.getItem('nithara.console.token')).toBeNull()
    expect(sessionStorage.getItem('nithara.console.token')).toBe('sess-abc')
  })
})
