// Bearer token for the logged-in (or, later, anonymous device) session. The
// backend always derives identity from this token — the client never sends a
// user id. Persisted so a reload keeps you signed in.

const KEY = 'nithara.token'

export function getToken(): string | null {
  return localStorage.getItem(KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(KEY, token)
  else localStorage.removeItem(KEY)
}

export function isAuthed(): boolean {
  return getToken() !== null
}
