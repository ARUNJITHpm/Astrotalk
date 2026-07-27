// Thin typed fetch wrapper, shaped after app-nithara/src/api/client.ts but
// sending an operator credential instead of a devotee bearer token.
//
// One deliberate difference from the consumer app: there is NO silent re-auth
// on 401. The consumer app can transparently re-mint an anonymous session
// because it owns no credential worth protecting. A console 401 means the
// operator's session expired or was revoked, and the only correct response is
// to drop the token and make a human sign in again.

import { authHeaders, clearToken } from '../lib/session'

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: string,
  ) {
    super(`API ${status}`)
    this.name = 'ApiError'
  }

  /** The session is gone — sign in again. */
  get isUnauthenticated(): boolean {
    return this.status === 401
  }

  /** Signed in, but this role may not do that. A re-login will NOT help. */
  get isForbidden(): boolean {
    return this.status === 403
  }

  /** The server's `detail`, when it sent one, else the raw body. */
  get detail(): string {
    try {
      const parsed = JSON.parse(this.body)
      if (typeof parsed?.detail === 'string') return parsed.detail
      // FastAPI validation errors arrive as a list of objects.
      if (Array.isArray(parsed?.detail)) {
        return parsed.detail
          .map((e: { loc?: unknown[]; msg?: string }) =>
            [e.loc?.slice(1).join('.'), e.msg].filter(Boolean).join(': '),
          )
          .join('; ')
      }
    } catch {
      /* not JSON */
    }
    return this.body
  }
}

// Set by AuthProvider so an expired session clears app state, not just storage.
let onUnauthenticated: (() => void) | null = null
export function setUnauthenticatedHandler(fn: (() => void) | null) {
  onUnauthenticated = fn
}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers = new Headers(opts.headers)
  headers.set('Accept', 'application/json')
  if (opts.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  for (const [key, value] of Object.entries(authHeaders())) {
    headers.set(key, value)
  }

  const res = await fetch(`${BASE}${path}`, { ...opts, headers })

  if (res.status === 401) {
    // Drop the dead credential before surfacing the error, so no later request
    // retries with it and no stale "signed in" UI survives.
    clearToken()
    onUnauthenticated?.()
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

export const apiPatch = <T>(path: string, body?: unknown): Promise<T> =>
  api<T>(path, {
    method: 'PATCH',
    body: body === undefined ? undefined : JSON.stringify(body),
  })

export const apiDelete = <T>(path: string): Promise<T> =>
  api<T>(path, { method: 'DELETE' })

/** Build a query string from defined params only. */
export function qs(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  return parts.length ? `?${parts.join('&')}` : ''
}
