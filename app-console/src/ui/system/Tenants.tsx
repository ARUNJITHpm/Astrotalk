// White-label organisations — the astrologers and practices running on Nithara
// under their own name at /a/{handle}.
//
// Two levers, both commercial, both owner-only: which plan a tenant is on and
// what state their billing is in. Everything else about an org — branding,
// slots, customers — belongs to that org's own dashboard, and reaching into it
// from here would be doing their job for them without them knowing.
//
// Creating a tenant is not offered. It takes a handle, a theme and an existing
// owner account, and a half-filled org is a live public page at a URL somebody
// may already have been given.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { apiUrl } from '../../api/client'
import { listOrgs, setOrgPlan, type Org } from '../../api/system'
import { Problem } from '../bits'

const PLANS = ['starter', 'pro']
const BILLING = ['trial', 'active', 'past_due']

function OrgRow({ org }: { org: Org }) {
  const queryClient = useQueryClient()
  const [plan, setPlan] = useState(org.plan)
  const [billing, setBilling] = useState('')

  const save = useMutation({
    mutationFn: () =>
      setOrgPlan(org.handle, {
        plan,
        ...(billing ? { billing_status: billing } : {}),
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['orgs'] })
      setBilling('')
    },
  })

  // The endpoint takes plan and billing together and the list does not report
  // the current billing state, so "leave it alone" has to be a real option —
  // otherwise opening this row and pressing Save would set a billing status
  // nobody chose.
  const changed = plan !== org.plan || billing !== ''

  return (
    <tr className={org.active ? undefined : 'row--off'}>
      <td>
        <strong>{org.name}</strong>
        <span className="cell__sub">{org.handle}</span>
      </td>
      <td>
        {/* apiUrl, not a bare path: the org's page is served by the API, and
            in dev the console runs on a different origin. */}
        <a href={apiUrl(`/a/${org.handle}`)} target="_blank" rel="noreferrer">
          /a/{org.handle} ↗
        </a>
      </td>
      <td>
        <select value={plan} onChange={(e) => setPlan(e.target.value)}>
          {PLANS.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
      </td>
      <td>
        <select value={billing} onChange={(e) => setBilling(e.target.value)}>
          <option value="">leave as it is</option>
          {BILLING.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </td>
      <td>
        <span className={org.active ? 'badge badge--on' : 'badge badge--off'}>
          {org.active ? 'active' : 'suspended'}
        </span>
      </td>
      <td className="cell__acts">
        <button
          className="btn"
          disabled={!changed || save.isPending}
          onClick={() => save.mutate()}
        >
          Save
        </button>
        <Problem error={save.error} />
      </td>
    </tr>
  )
}

export function Tenants() {
  const { data, isLoading, error } = useQuery({ queryKey: ['orgs'], queryFn: listOrgs })
  const rows = data ?? []

  return (
    <section className="page">
      <h1 className="page__title">Org tenants</h1>
      <p className="page__lede">
        Practices running on Nithara under their own name, and what each is on.
      </p>

      <Problem error={error} />
      {isLoading && <p className="empty">Loading…</p>}
      {!isLoading && !rows.length && (
        <p className="empty">
          No tenants yet. An org is created with its handle, branding and owner
          account through <code>POST /orgs</code>.
        </p>
      )}

      {rows.length > 0 && (
        <div className="tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th>Org</th>
                <th>Their page</th>
                <th>Plan</th>
                <th>Billing</th>
                <th>State</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((org) => (
                <OrgRow key={org.id} org={org} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="field__hint">
        Moving a tenant between plans here is an ops lever, not a payment. It
        changes what they may use; it does not charge or refund anybody.
      </p>
    </section>
  )
}
