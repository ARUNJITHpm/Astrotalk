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

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers)
  headers.set('Accept', 'application/json')
  if (opts.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(`${BASE}${path}`, { ...opts, headers })
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

/** Build a query string from defined params only. */
export function qs(params: Record<string, string | number | undefined | null>): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  return parts.length ? `?${parts.join('&')}` : ''
}
