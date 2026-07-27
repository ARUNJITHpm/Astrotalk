// Who is signed in, and what they may touch.
//
// The console never decides its own permissions. On sign-in it asks
// GET /admin/operators/me and renders from that answer, so the sidebar reflects
// what the SERVER already resolved rather than a client-side guess that could
// drift from admin_auth.py.

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { apiGet, apiPost, setUnauthenticatedHandler } from '../api/client'
import {
  clearToken,
  getToken,
  setToken,
  type TokenKind,
} from './session'

export interface Me {
  operator_id: number | null
  roles: string[]
  temple_ids: string[]
  is_owner: boolean
}

interface AuthState {
  me: Me | null
  /** True until the initial "do we already hold a valid token?" check settles. */
  loading: boolean
  signInAsOperator: (identifier: string, password: string) => Promise<void>
  signInAsOwner: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  const forget = useCallback(() => {
    clearToken()
    setMe(null)
  }, [])

  // A 401 from anywhere in the app drops the session, so an expired token
  // cannot leave a signed-in shell rendering around dead requests.
  useEffect(() => {
    setUnauthenticatedHandler(forget)
    return () => setUnauthenticatedHandler(null)
  }, [forget])

  // Resume a session that survived a page reload within the same tab.
  useEffect(() => {
    let cancelled = false
    async function resume() {
      if (!getToken()) {
        setLoading(false)
        return
      }
      try {
        const who = await apiGet<Me>('/admin/operators/me')
        if (!cancelled) setMe(who)
      } catch {
        if (!cancelled) forget() // expired or revoked; the client already cleared it
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void resume()
    return () => {
      cancelled = true
    }
  }, [forget])

  const adopt = useCallback(async (token: string, kind: TokenKind) => {
    setToken(token, kind)
    try {
      setMe(await apiGet<Me>('/admin/operators/me'))
    } catch (err) {
      // A token that cannot describe itself is not a usable session. Drop it
      // rather than leave the console half-signed-in with an empty sidebar.
      clearToken()
      setMe(null)
      throw err
    }
  }, [])

  const signInAsOperator = useCallback(
    async (identifier: string, password: string) => {
      const { token } = await apiPost<{ token: string }>('/admin/operators/login', {
        identifier,
        password,
      })
      await adopt(token, 'operator')
    },
    [adopt],
  )

  const signInAsOwner = useCallback(
    async (username: string, password: string) => {
      // Returns the configured ADMIN_TOKEN, which travels as X-Admin-Token.
      const { token } = await apiPost<{ token: string }>('/admin/login', {
        username,
        password,
      })
      await adopt(token, 'admin_token')
    },
    [adopt],
  )

  const signOut = useCallback(async () => {
    try {
      // Revoke server-side so the token dies with the click, not at expiry.
      // Harmless for an owner ADMIN_TOKEN: it is not a session row, and the
      // endpoint is a no-op for a token it does not recognise.
      await apiPost('/admin/operators/logout')
    } catch {
      /* signing out must always succeed locally */
    }
    forget()
  }, [forget])

  const value = useMemo(
    () => ({ me, loading, signInAsOperator, signInAsOwner, signOut }),
    [me, loading, signInAsOperator, signInAsOwner, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
