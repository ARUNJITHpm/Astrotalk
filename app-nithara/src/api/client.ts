// Thin typed fetch wrapper. Base URL from VITE_API_BASE (empty = same origin).
// Attaches the bearer token when present; identity is always derived from it
// server-side. React Query hooks wrap these for caching/loading state.

import { getToken } from '../lib/session'

// Empty base = same origin (web/prod behind the same host). NOTE (Part 9): the
// Capacitor native build runs from capacitor://localhost, so VITE_API_BASE MUST
// be injected at build time there (and the backend must allow that origin via
// CORS) — an empty base would point API calls at the app bundle.
const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`API ${status}`)
    this.name = 'ApiError'
  }
}

// Set by lib/auth to avoid an import cycle (auth uses apiPost). Lets a 401 —
// i.e. the 47h session expired — transparently re-mint and retry once, instead
// of leaving the app permanently signed out until localStorage is cleared.
let reauth: (() => Promise<void>) | null = null
export function setReauthHandler(fn: () => Promise<void>) {
  reauth = fn
}

async function send(path: string, opts: RequestInit): Promise<Response> {
  const headers = new Headers(opts.headers)
  headers.set('Accept', 'application/json')
  if (opts.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(`${BASE}${path}`, { ...opts, headers })
}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  let res = await send(path, opts)

  // Expired/unknown session → re-mint once and replay the request.
  if (res.status === 401 && reauth && path !== '/identity/anon') {
    try {
      await reauth()
      res = await send(path, opts)
    } catch {
      /* fall through to the error below */
    }
  }

  if (!res.ok) {
    throw new ApiError(res.status, await res.text().catch(() => ''))
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const apiGet = <T>(path: string): Promise<T> => api<T>(path)

export const apiPost = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const apiPut = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, {
    method: 'PUT',
    body: body === undefined ? undefined : JSON.stringify(body),
  })

/** Build a query string from defined params only. */
export function qs(params: Record<string, string | number | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  return parts.length ? `?${parts.join('&')}` : ''
}
