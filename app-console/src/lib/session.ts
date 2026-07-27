// The console's credential, held in one place.
//
// Two kinds of token reach the same header set. An operator sign-in
// (POST /admin/operators/login) returns a session token that goes in
// `Authorization: Bearer`. The owner's own sign-in (POST /admin/login) returns
// the configured ADMIN_TOKEN, which the backend expects in `X-Admin-Token`.
// admin_auth.py accepts either, so the console stores which kind it holds and
// sends the matching header — guessing wrong reads as unauthenticated.
//
// sessionStorage, not localStorage: a console token is an operator credential
// on what may be a shared back-office machine, and it should not outlive the
// browser tab. The consumer app makes the opposite trade deliberately, because
// a devotee's phone is personal and a 47h session is the point there.

export type TokenKind = 'operator' | 'admin_token'

const TOKEN_KEY = 'nithara.console.token'
const KIND_KEY = 'nithara.console.token_kind'

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null // private mode / storage disabled — treat as signed out
  }
}

export function getTokenKind(): TokenKind {
  try {
    return sessionStorage.getItem(KIND_KEY) === 'admin_token'
      ? 'admin_token'
      : 'operator'
  } catch {
    return 'operator'
  }
}

export function setToken(token: string, kind: TokenKind): void {
  try {
    sessionStorage.setItem(TOKEN_KEY, token)
    sessionStorage.setItem(KIND_KEY, kind)
  } catch {
    /* nothing useful to do; the request layer will 401 and prompt a re-login */
  }
}

export function clearToken(): void {
  try {
    sessionStorage.removeItem(TOKEN_KEY)
    sessionStorage.removeItem(KIND_KEY)
  } catch {
    /* ignore */
  }
}

/** Headers carrying whichever credential we hold. Empty when signed out. */
export function authHeaders(): Record<string, string> {
  const token = getToken()
  if (!token) return {}
  return getTokenKind() === 'admin_token'
    ? { 'X-Admin-Token': token }
    : { Authorization: `Bearer ${token}` }
}
