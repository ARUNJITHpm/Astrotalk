// Small pieces the section screens share.

import { ApiError } from '../api/client'

/**
 * Whatever went wrong, in the operator's terms.
 *
 * A 403 is called out separately because it is the one error a retry cannot
 * fix: the caller is signed in, and the server has decided this temple is not
 * theirs. Rendering it as a generic failure invites them to click Save again.
 */
export function Problem({ error }: { error: unknown }) {
  if (!error) return null
  if (error instanceof ApiError && error.isForbidden) {
    return (
      <p className="banner banner--warn" role="alert">
        You do not manage this temple. Ask the owner if that looks wrong.
      </p>
    )
  }
  const message =
    error instanceof ApiError
      ? error.detail
      : error instanceof Error
        ? error.message
        : String(error)
  return (
    <p className="banner banner--warn" role="alert">
      {message || 'That did not go through.'}
    </p>
  )
}

export function Badge({
  on,
  yes,
  no,
}: {
  on: boolean
  yes: string
  no: string
}) {
  return <span className={on ? 'badge badge--on' : 'badge'}>{on ? yes : no}</span>
}

/** A labelled control. `ml` switches on a Malayalam-capable font and turns off
 *  the spell checker, which flags every word of it otherwise. */
export function Field({
  label,
  hint,
  ml,
  children,
}: {
  label: string
  hint?: string
  ml?: boolean
  children: React.ReactNode
}) {
  return (
    <label className={ml ? 'field field--ml' : 'field'}>
      <span>
        {label}
        {ml && <em className="field__tag">മലയാളം</em>}
      </span>
      {children}
      {hint && <small className="field__hint">{hint}</small>}
    </label>
  )
}
