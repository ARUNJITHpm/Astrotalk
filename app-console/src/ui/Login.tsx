// The sign-in screen.
//
// NOTHING is prefilled. The pages this replaces both leaked a credential into
// the markup — console.html:117 hardcoded a personal email into the field, and
// admin.html:363 printed the password on screen. Neither carries over, and this
// file should never grow a `defaultValue` on either input.

import { useState, type FormEvent } from 'react'

import { ApiError } from '../api/client'
import { useAuth } from '../lib/auth'

type Mode = 'operator' | 'owner'

export function Login() {
  const { signInAsOperator, signInAsOwner } = useAuth()
  const [mode, setMode] = useState<Mode>('operator')
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'owner') {
        await signInAsOwner(identifier, password)
      } else {
        await signInAsOperator(identifier, password)
      }
    } catch (err) {
      // 503 is the one message worth passing through verbatim: it means the
      // deployment has no ADMIN_TOKEN configured, which is a deploy problem the
      // owner can act on, not a wrong password they should retry.
      if (err instanceof ApiError && err.status === 503) {
        setError(err.detail || 'This deployment is missing its ADMIN_TOKEN.')
      } else if (err instanceof ApiError && err.isUnauthenticated) {
        setError('Those credentials were not accepted.')
      } else {
        setError('Could not reach the server. Try again.')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="login">
      <form className="login__card" onSubmit={submit}>
        <h1 className="login__title">Nithara Console</h1>
        <p className="login__sub">Staff access only.</p>

        <div className="login__modes" role="group" aria-label="Sign-in type">
          <button
            type="button"
            className={mode === 'operator' ? 'chip chip--on' : 'chip'}
            onClick={() => setMode('operator')}
            aria-pressed={mode === 'operator'}
          >
            Operator
          </button>
          <button
            type="button"
            className={mode === 'owner' ? 'chip chip--on' : 'chip'}
            onClick={() => setMode('owner')}
            aria-pressed={mode === 'owner'}
          >
            Owner
          </button>
        </div>

        <label className="field">
          <span>{mode === 'owner' ? 'Email' : 'Email or mobile'}</span>
          <input
            name="identifier"
            type="text"
            autoComplete="username"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            required
            autoFocus
          />
        </label>

        <label className="field">
          <span>Password</span>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        {error && (
          <p className="login__error" role="alert">
            {error}
          </p>
        )}

        <button className="btn btn--primary" type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </main>
  )
}
