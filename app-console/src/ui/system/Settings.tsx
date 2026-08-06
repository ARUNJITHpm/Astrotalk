// The handful of things about this installation an operator can change, and the
// ones they cannot.
//
// There is exactly one editable setting today — the service fee — and saying so
// is more useful than a page of controls that do nothing. The rest of this
// screen is the answer to "who can do what", generated from the same nav table
// the sidebar and the route guard read, so it cannot describe permissions the
// tool does not actually enforce.
//
// The shared admin token is deliberately absent. It grants full owner to
// anyone holding it, and a console that displays a break-glass credential turns
// every screen-share into a handover of it.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { bookingSettings, setBookingSettings } from '../../api/system'
import { useAuth } from '../../lib/auth'
import { readPaise, money } from '../../lib/money'
import { NAV, canAccess, type Role } from '../../lib/nav'
import { Field, Problem } from '../bits'

const ROLES: Role[] = ['owner', 'temple_admin', 'content_reviewer', 'support']

function ServiceFee({ editable }: { editable: boolean }) {
  const queryClient = useQueryClient()
  const [text, setText] = useState<string | null>(null)

  const current = useQuery({ queryKey: ['booking-settings'], queryFn: bookingSettings })
  const shown =
    text ?? (current.data ? String(current.data.service_fee_paise / 100) : '')

  const entry = readPaise(shown)
  const save = useMutation({
    mutationFn: () => setBookingSettings(entry.value as number),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['booking-settings'] })
      setText(null)
    },
  })

  // Blank is not a fee. `readPaise` reports an empty box as "inherit", which is
  // the right answer for a per-temple override and a meaningless one here —
  // there is nothing above this row to inherit from, and null would go straight
  // at a NOT NULL column.
  const usable = entry.ok && entry.value !== null
  const changed = usable && entry.value !== current.data?.service_fee_paise

  return (
    <article className="card">
      <div className="card__head">
        <h3 className="card__title">Service fee</h3>
      </div>
      <p>
        Added to every pooja booking, on top of whatever the temple charges for
        the offering itself. The devotee sees both lines.
      </p>

      <Problem error={current.error} />

      <div className="row">
        <Field label="Fee (₹)">
          <input
            className="input--num"
            inputMode="decimal"
            value={shown}
            disabled={!editable || current.isLoading}
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        {editable && (
          <button
            className="btn btn--primary"
            disabled={!changed || save.isPending}
            onClick={() => save.mutate()}
          >
            Save
          </button>
        )}
        {!entry.ok && <span className="field__error">not an amount</span>}
        {entry.ok && entry.value === null && shown !== '' && (
          <span className="field__error">the fee must be a figure</span>
        )}
      </div>

      {current.data && (
        <p className="field__hint">
          Currently {money(current.data.service_fee_paise)} per booking. Changing
          it applies to new bookings; ones already placed keep the fee they were
          quoted.
        </p>
      )}
      {!editable && (
        <p className="field__hint">
          The fee applies across every temple, so only the owner may change it.
        </p>
      )}
      <Problem error={save.error} />
    </article>
  )
}

export function Settings() {
  const { me } = useAuth()
  const isOwner = me?.is_owner ?? false

  return (
    <section className="page">
      <h1 className="page__title">Settings</h1>
      <p className="page__lede">What can be changed from here, and by whom.</p>

      <ServiceFee editable={isOwner} />

      <h2 className="section__title">What each role reaches</h2>
      <p className="field__hint">
        Generated from the console's own access table — the same declaration the
        sidebar and the route guard read, so this cannot claim a permission the
        tool does not enforce. The server checks independently: a typed-in URL
        gets a 403 whatever this says.
      </p>
      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Section</th>
              {ROLES.map((r) => (
                <th key={r}>{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {NAV.map((group) => (
              <tr key={group.title}>
                <td>
                  <strong>{group.title}</strong>
                  <span className="cell__sub">
                    {group.items.map((i) => i.label).join(', ')}
                  </span>
                </td>
                {ROLES.map((role) => {
                  const reachable = group.items.filter((i) => canAccess(i, [role]))
                  return (
                    <td key={role} className="num">
                      {reachable.length === group.items.length
                        ? 'all'
                        : reachable.length
                          ? `${reachable.length} of ${group.items.length}`
                          : '—'}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2 className="section__title">Sign-in</h2>
      <article className="card">
        <p>
          Operators sign in with their own email or mobile and a password they
          set when they accepted an invitation. Grant and revoke roles under{' '}
          <strong>People → Operators</strong>.
        </p>
        <p>
          A shared <code>X-Admin-Token</code> also exists for scripts and the
          scheduler. It grants full owner to whoever holds it, so it is not shown
          here and cannot be set from a browser — it is configured on the server
          and changing it takes a redeploy.
        </p>
      </article>
    </section>
  )
}
