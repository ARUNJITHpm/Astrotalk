// The payment ledger, and the one write that goes with it: a manual grant.
//
// `granted_by` is not a field on the form. The server always records `"admin"`,
// and the console cannot claim a grant came from a purchase or a referral —
// that distinction is the entire point of the column, and a form that could
// forge it would make the audit trail worthless.
//
// Revoking a grant is not here. It needs an entitlement id, which is only
// visible on a devotee's own record; putting a "revoke by id" box on this
// screen would be an invitation to withdraw the wrong person's access.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { grantEntitlement, listPayments, type PaymentQuery } from '../../api/bookings'
import { money, whenStamp } from '../../lib/booking'
import { Field, Problem } from '../bits'
import { StateBadge } from './bits'

const PAGE = 50
const PAYMENT_STATES = ['created', 'paid', 'failed']

function GrantForm() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ user_id: '', product_key: '', reason: '', expires: '' })
  const [granted, setGranted] = useState<string | null>(null)

  const grant = useMutation({
    mutationFn: () =>
      grantEntitlement({
        user_id: Number(form.user_id),
        product_key: form.product_key.trim(),
        reason: form.reason.trim() || undefined,
        expires_at: form.expires ? new Date(form.expires).toISOString() : null,
      }),
    onSuccess: async (row) => {
      await queryClient.invalidateQueries({ queryKey: ['payments'] })
      setGranted(`${row.product_key} granted to user ${row.user_id}`)
      setForm({ user_id: '', product_key: '', reason: '', expires: '' })
    },
  })

  const userId = Number(form.user_id)
  const ready = Number.isInteger(userId) && userId > 0 && form.product_key.trim()

  return (
    <details className="card">
      <summary>Grant an entitlement by hand</summary>
      <p className="field__hint">
        For a goodwill unlock or a comped report — anything a payment did not pay
        for. It is always recorded as an operator grant, never as a purchase.
      </p>
      <div className="grid3">
        <Field label="User id" hint="From the devotee's record under People → Users.">
          <input
            inputMode="numeric"
            value={form.user_id}
            onChange={(e) => setForm({ ...form, user_id: e.target.value })}
          />
        </Field>
        <Field label="Product key">
          <input
            value={form.product_key}
            placeholder="full_report"
            onChange={(e) => setForm({ ...form, product_key: e.target.value })}
          />
        </Field>
        <Field label="Expires" hint="Leave empty for no expiry.">
          <input
            type="date"
            value={form.expires}
            onChange={(e) => setForm({ ...form, expires: e.target.value })}
          />
        </Field>
      </div>
      <Field label="Why" hint="Kept on the grant. Write what you would want to read in a year.">
        <input
          value={form.reason}
          onChange={(e) => setForm({ ...form, reason: e.target.value })}
        />
      </Field>
      <Problem error={grant.error} />
      {granted && (
        <p className="banner banner--ok" role="status">
          {granted}
        </p>
      )}
      <button
        className="btn btn--primary btn--inline"
        disabled={!ready || grant.isPending}
        onClick={() => grant.mutate()}
      >
        {grant.isPending ? 'Granting…' : 'Grant'}
      </button>
    </details>
  )
}

export function Payments() {
  const [status, setStatus] = useState('')
  const [product, setProduct] = useState('')
  const [offset, setOffset] = useState(0)

  const query: PaymentQuery = {
    status: status || undefined,
    product: product.trim() || undefined,
    limit: PAGE,
    offset,
  }
  const page = useQuery({ queryKey: ['payments', query], queryFn: () => listPayments(query) })

  const rows = page.data?.items ?? []
  const total = page.data?.total ?? 0
  // Every filter change returns to page one; narrowing while on page 7 leaves
  // an operator staring at an empty table that is not empty.
  const narrow = (fn: () => void) => {
    fn()
    setOffset(0)
  }

  return (
    <section className="page">
      <h1 className="page__title">Payments</h1>
      <p className="page__lede">
        The commerce ledger: every order, whether it was captured, and what it was
        for.
      </p>

      <Problem error={page.error} />

      <div className="toolbar">
        <label className="toolbar__field">
          <span>Status</span>
          <select value={status} onChange={(e) => narrow(() => setStatus(e.target.value))}>
            <option value="">Any</option>
            {PAYMENT_STATES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className="toolbar__field toolbar__field--grow">
          <span>Product</span>
          <input
            value={product}
            placeholder="pooja, full_report…"
            onChange={(e) => narrow(() => setProduct(e.target.value))}
          />
        </label>
      </div>

      <p className="count" role="status">
        {page.isLoading
          ? 'Loading…'
          : total
            ? `${offset + 1}–${offset + rows.length} of ${total}`
            : 'No payments match'}
      </p>

      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Order</th>
              <th>Product</th>
              <th>User</th>
              <th>Amount</th>
              <th>Status</th>
              <th>Paid</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => (
              <tr key={p.id}>
                <td>
                  <code>{p.razorpay_order_id || `#${p.id}`}</code>
                  {p.razorpay_payment_id && (
                    <span className="cell__sub">{p.razorpay_payment_id}</span>
                  )}
                </td>
                <td>{p.product}</td>
                <td>{p.user_id}</td>
                <td className="num">{money(p.amount_paise)}</td>
                <td>
                  <StateBadge state={p.status} />
                </td>
                <td>{whenStamp(p.paid_at) || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!page.isLoading && !rows.length && <p className="empty">Nothing to show.</p>}
      </div>

      <div className="pager">
        <button className="btn" disabled={offset === 0} onClick={() => setOffset(offset - PAGE)}>
          Previous
        </button>
        <button
          className="btn"
          disabled={offset + rows.length >= total}
          onClick={() => setOffset(offset + PAGE)}
        >
          Next
        </button>
      </div>

      <GrantForm />
    </section>
  )
}
