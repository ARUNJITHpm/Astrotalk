// Who may sign in to this console, and what each of them may touch.
//
// This replaces scripts/grant_role.py for everyone after the first operator —
// that script exists to bootstrap the very first owner on a fresh deployment,
// and there is no way to run it from a browser.
//
// The invite token is shown on screen rather than emailed. There is no mail
// transport in this deployment yet, so the owner passes the link on themselves;
// saying so is better than a "check your inbox" that never arrives.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  ROLES,
  SCOPED_ROLES,
  grantRole,
  inviteOperator,
  listOperators,
  revokeRole,
  setOperatorActive,
  type OperatorRow,
} from '../../api/people'
import { listTemples } from '../../api/temples'
import { whenStamp } from '../../lib/booking'
import { grantProblem, operatorIdentifier, roleSummary } from '../../lib/people'
import { Badge, Field, Problem } from '../bits'

function roleLabel(role: string): string {
  return role.replace(/_/g, ' ')
}

function GrantPanel({ operator }: { operator: OperatorRow }) {
  const queryClient = useQueryClient()
  const [role, setRole] = useState('temple_admin')
  const [templeId, setTempleId] = useState('')

  const temples = useQuery({ queryKey: ['temples'], queryFn: listTemples })
  const done = () => queryClient.invalidateQueries({ queryKey: ['operators'] })

  const grant = useMutation({
    mutationFn: () => grantRole(operator.id, role, templeId || null),
    onSuccess: async () => {
      await done()
      setTempleId('')
    },
  })
  const revoke = useMutation({ mutationFn: revokeRole, onSuccess: done })

  const scoped = SCOPED_ROLES.includes(role)
  const problem = grantProblem(role, templeId || null, SCOPED_ROLES)

  return (
    <div>
      <div className="tablewrap">
        <table className="table">
          <tbody>
            {operator.roles.map((g) => (
              <tr key={g.id}>
                <td>
                  <strong>{roleLabel(g.role)}</strong>
                  {g.temple_id && <span className="cell__sub">{g.temple_id}</span>}
                </td>
                <td className="cell__acts">
                  <button
                    className="btn"
                    disabled={revoke.isPending}
                    onClick={() => revoke.mutate(g.id)}
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!operator.roles.length && (
          <p className="empty">
            No roles, so they can sign in and see nothing. Grant one below.
          </p>
        )}
      </div>

      <div className="grid3">
        <Field label="Role">
          <select
            value={role}
            onChange={(e) => {
              setRole(e.target.value)
              // A temple only means something on a scoped role, and leaving a
              // stale one selected is how an invalid grant gets submitted.
              if (!SCOPED_ROLES.includes(e.target.value)) setTempleId('')
            }}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </select>
        </Field>
        {scoped && (
          <Field label="Temple" hint="One grant per temple; add more for more.">
            <select value={templeId} onChange={(e) => setTempleId(e.target.value)}>
              <option value="">Choose…</option>
              {(temples.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} — {t.district}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
      {problem && <p className="field__error">{problem}</p>}
      <Problem error={grant.error ?? revoke.error} />
      <button
        className="btn btn--primary btn--inline"
        disabled={!!problem || grant.isPending}
        onClick={() => grant.mutate()}
      >
        {grant.isPending ? 'Granting…' : 'Grant'}
      </button>
    </div>
  )
}

function OperatorCard({ operator }: { operator: OperatorRow }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const account = useMutation({
    mutationFn: () => setOperatorActive(operator.id, !operator.active),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['operators'] }),
  })

  return (
    <article className="card">
      <div className="card__head">
        <div>
          <h3 className="card__title">{operator.name || operatorIdentifier(operator)}</h3>
          <p className="cell__sub">
            {operatorIdentifier(operator)} · {roleSummary(operator)}
            {operator.last_login_at
              ? ` · last in ${whenStamp(operator.last_login_at)}`
              : ' · never signed in'}
          </p>
        </div>
        <div className="row">
          {operator.pending && <span className="badge">Invite not redeemed</span>}
          <Badge on={operator.active} yes="Active" no="Disabled" />
        </div>
      </div>

      <div className="row row--wrap">
        <button className="btn" onClick={() => setOpen(!open)}>
          {open ? 'Done' : 'Roles'}
        </button>
        <button className="btn" disabled={account.isPending} onClick={() => account.mutate()}>
          {operator.active ? 'Disable this operator' : 'Enable them again'}
        </button>
      </div>

      <Problem error={account.error} />
      {open && <GrantPanel operator={operator} />}
    </article>
  )
}

function InvitePanel() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    email: '',
    phone: '',
    name: '',
    role: 'temple_admin',
    temple_id: '',
  })
  const [issued, setIssued] = useState<{ token: string; expires_at: string } | null>(null)
  const temples = useQuery({ queryKey: ['temples'], queryFn: listTemples })

  const invite = useMutation({
    mutationFn: () =>
      inviteOperator({
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        name: form.name.trim() || undefined,
        role: form.role,
        temple_id: form.temple_id || null,
      }),
    onSuccess: async (row) => {
      await queryClient.invalidateQueries({ queryKey: ['operators'] })
      setIssued({ token: row.invite_token, expires_at: row.expires_at })
      setForm({ ...form, email: '', phone: '', name: '' })
    },
  })

  const scoped = SCOPED_ROLES.includes(form.role)
  const problem =
    !form.email.trim() && !form.phone.trim()
      ? 'An email or a mobile is needed — it is how they sign in.'
      : grantProblem(form.role, form.temple_id || null, SCOPED_ROLES)

  return (
    <details className="card">
      <summary>Invite an operator</summary>
      <div className="grid3">
        <Field label="Email">
          <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </Field>
        <Field label="Mobile" hint="Either one will do; both is fine.">
          <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        </Field>
        <Field label="Name">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="Role">
          <select
            value={form.role}
            onChange={(e) =>
              setForm({
                ...form,
                role: e.target.value,
                temple_id: SCOPED_ROLES.includes(e.target.value) ? form.temple_id : '',
              })
            }
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </select>
        </Field>
        {scoped && (
          <Field label="Temple">
            <select
              value={form.temple_id}
              onChange={(e) => setForm({ ...form, temple_id: e.target.value })}
            >
              <option value="">Choose…</option>
              {(temples.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} — {t.district}
                </option>
              ))}
            </select>
          </Field>
        )}
      </div>
      {problem && <p className="field__error">{problem}</p>}
      <Problem error={invite.error} />
      <button
        className="btn btn--primary btn--inline"
        disabled={!!problem || invite.isPending}
        onClick={() => invite.mutate()}
      >
        {invite.isPending ? 'Inviting…' : 'Invite'}
      </button>

      {issued && (
        <div className="confirmbox">
          <p className="field__hint">
            There is no mail transport on this deployment, so send this to them
            yourself. It expires {whenStamp(issued.expires_at)} and can be
            redeemed once.
          </p>
          <pre className="snippet">{issued.token}</pre>
          <button
            className="btn"
            onClick={() => void navigator.clipboard?.writeText(issued.token)}
          >
            Copy the token
          </button>
        </div>
      )}
    </details>
  )
}

export function Operators() {
  const operators = useQuery({ queryKey: ['operators'], queryFn: listOperators })
  const rows = operators.data ?? []

  return (
    <section className="page">
      <h1 className="page__title">Operators</h1>
      <p className="page__lede">
        Who may sign in here, and what each of them may reach. An owner satisfies
        every role; a temple admin sees only the temples granted to them.
      </p>

      <Problem error={operators.error} />
      <InvitePanel />

      {operators.isLoading && <p className="empty">Loading…</p>}
      {!operators.isLoading && !rows.length && (
        <p className="empty">
          No operator accounts. You are signed in with the owner token.
        </p>
      )}
      {rows.map((o) => (
        <OperatorCard key={o.id} operator={o} />
      ))}
    </section>
  )
}
