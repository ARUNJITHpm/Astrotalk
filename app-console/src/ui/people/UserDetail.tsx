// One devotee, as support needs to read them.
//
// The chart is behind a click, not on the page. It is birth data by another
// name (GUARDRAILS §4), and an operator answering "when is my pooja" has no
// business seeing it — so opening it is a deliberate act, and the screen says
// what it is before showing it. The API is shaped the same way: a separate
// request against one named user id, never part of the detail payload and never
// in any list.
//
// Note what the header does NOT show: date and time of birth. Birth place is
// here because a "my chart looks wrong" report is usually a wrong place.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { revokeEntitlement, setUserActive, userChart, userDetail } from '../../api/people'
import { stateLabel, whenStamp } from '../../lib/booking'
import { money } from '../../lib/money'
import { nakLabel } from '../../lib/nakshatrams'
import { Badge, Problem } from '../bits'
import { StateBadge } from '../bookings/bits'
import { FamilyBoard } from './FamilyBoard'

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="deftrow">
      <span className="deftrow__label">{label}</span>
      <span className="deftrow__value">{children}</span>
    </div>
  )
}

function ChartPanel({ userId }: { userId: number }) {
  const [open, setOpen] = useState(false)
  const chart = useQuery({
    queryKey: ['chart', userId],
    queryFn: () => userChart(userId),
    enabled: open,
    retry: false,
  })

  return (
    <section className="card">
      <h2 className="card__title">Natal chart</h2>
      <p className="field__hint">
        This is birth data. Open it only when a question genuinely needs it — a
        booking, a payment or a refund does not.
      </p>
      {!open ? (
        <button className="btn" onClick={() => setOpen(true)}>
          Show the chart
        </button>
      ) : (
        <>
          <button className="btn" onClick={() => setOpen(false)}>
            Hide it again
          </button>
          {chart.isLoading && <p className="field__hint">Loading…</p>}
          <Problem error={chart.error} />
          {chart.data && (
            <>
              <p className="field__hint">
                Computed {whenStamp(chart.data.computed_at)}.
              </p>
              <pre className="snippet">{JSON.stringify(chart.data.natal, null, 2)}</pre>
            </>
          )}
        </>
      )}
    </section>
  )
}

export function UserDetail() {
  const { userId } = useParams<{ userId: string }>()
  const id = Number(userId)
  const queryClient = useQueryClient()

  const { data: user, isLoading, error } = useQuery({
    queryKey: ['user', id],
    queryFn: () => userDetail(id),
    enabled: Number.isInteger(id),
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['user', id] })
  const account = useMutation({
    mutationFn: (active: boolean) => setUserActive(id, active),
    onSuccess: async () => {
      await refresh()
      await queryClient.invalidateQueries({ queryKey: ['users'] })
    },
  })
  const revoke = useMutation({
    mutationFn: (entitlementId: number) => revokeEntitlement(entitlementId),
    onSuccess: refresh,
  })

  if (!Number.isInteger(id) || error || (!isLoading && !user)) {
    return (
      <section className="page">
        <h1 className="page__title">No such user</h1>
        <p className="page__lede">
          <Link to="/people/users">Back to the register</Link>.
        </p>
        <Problem error={error} />
      </section>
    )
  }
  if (isLoading || !user) return <p className="empty">Loading…</p>

  return (
    <section className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">{user.name || '(no name)'}</h1>
          <p className="page__lede">
            {user.phone} · <Badge on={user.active} yes="Enabled" no="Disabled" />
          </p>
        </div>
        <Link className="btn btn--inline" to="/people/users">
          Back to the register
        </Link>
      </div>

      <Problem error={account.error ?? revoke.error} />

      <div className="grid2">
        <section className="card">
          <h2 className="card__title">Account</h2>
          <Row label="Mobile">
            <a href={`tel:${user.phone}`}>{user.phone}</a>
          </Row>
          <Row label="Born in">{user.birth_place || '—'}</Row>
          <Row label="Timezone">{user.tz}</Row>
          <Row label="Joined">{whenStamp(user.created_at)}</Row>
          <Row label="Transcript consent">
            {user.transcript_consent ? 'Given' : 'Not given'}
          </Row>
          {user.org_id !== null && <Row label="Organisation">#{user.org_id}</Row>}
          <div className="row">
            <button
              className="btn"
              disabled={account.isPending}
              onClick={() => account.mutate(!user.active)}
            >
              {user.active ? 'Disable this account' : 'Enable it again'}
            </button>
          </div>
          <p className="field__hint">
            Disabling drops every live session as well as blocking the next
            sign-in — otherwise the account keeps working until the session
            expires, which is not what anyone means by disabled.
          </p>
        </section>

        <section className="card">
          <h2 className="card__title">Entitlements</h2>
          {!user.entitlements.length ? (
            <p className="field__hint">Nothing unlocked by hand or by purchase.</p>
          ) : (
            <div className="tablewrap">
              <table className="table">
                <tbody>
                  {user.entitlements.map((e) => (
                    <tr key={e.id}>
                      <td>
                        <strong>{e.product_key}</strong>
                        <span className="cell__sub">
                          {e.granted_by === 'admin' ? 'granted by an operator' : e.granted_by}
                          {e.source ? ` · ${e.source}` : ''}
                        </span>
                      </td>
                      <td>
                        {e.expires_at ? `until ${whenStamp(e.expires_at)}` : 'no expiry'}
                      </td>
                      <td className="cell__acts">
                        <button
                          className="btn"
                          disabled={revoke.isPending}
                          onClick={() => revoke.mutate(e.id)}
                        >
                          Withdraw
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="field__hint">
            Withdrawing removes the row outright. A disabled entitlement would
            still read as held, so there is no soft version of this.
          </p>
        </section>
      </div>

      <FamilyBoard userId={id} />

      <section className="card">
        <h2 className="card__title">Bookings</h2>
        {!user.bookings.length ? (
          <p className="field__hint">No poojas booked.</p>
        ) : (
          <div className="tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Ref</th>
                  <th>Offering</th>
                  <th>For</th>
                  <th>Amount</th>
                  <th>State</th>
                </tr>
              </thead>
              <tbody>
                {user.bookings.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <Link className="celllink" to={`/bookings/${b.id}`}>
                        {b.ref}
                      </Link>
                      <span className="cell__sub">{b.temple_id}</span>
                    </td>
                    <td>{b.pooja_name}</td>
                    <td>
                      {b.member_name || '—'}
                      <span className="cell__sub">{nakLabel(b.member_nak)}</span>
                    </td>
                    <td className="num">{money(b.total_paise)}</td>
                    <td>
                      <StateBadge state={b.state} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="card__title">Payments</h2>
        {!user.payments.length ? (
          <p className="field__hint">No orders.</p>
        ) : (
          <div className="tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Product</th>
                  <th>Amount</th>
                  <th>Status</th>
                  <th>Paid</th>
                </tr>
              </thead>
              <tbody>
                {user.payments.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <code>{p.razorpay_order_id || `#${p.id}`}</code>
                    </td>
                    <td>{p.product}</td>
                    <td className="num">{money(p.amount_paise)}</td>
                    <td>{stateLabel(p.status)}</td>
                    <td>{whenStamp(p.paid_at) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <ChartPanel userId={id} />
    </section>
  )
}
