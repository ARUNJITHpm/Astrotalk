// The landing screen: what needs attention today.
//
// Deliberately built from the SCOPED endpoints rather than a new aggregate.
// /bookings/queue already narrows to the caller's temples, so a temple_admin's
// dashboard shows their work without this file knowing anything about scoping.
// Adding a dashboard-only aggregate would mean re-implementing that rule in a
// second place, which is how the two drift apart.
//
// Owner-only figures (users, payments) are fetched only when the caller is an
// owner. Asking and swallowing a 403 would work, but it puts a forbidden
// request in the server log on every page load for every temple_admin.

import { useQueries } from '@tanstack/react-query'

import { apiGet, qs } from '../api/client'
import { useAuth } from '../lib/auth'

interface QueueResponse {
  total: number
  items: { ref: string; temple_id: string; pooja_name: string; state: string }[]
}
interface CountResponse {
  total: number
}

function today(): string {
  // The operator's local day. The API compares against stored dates, so a
  // timezone-shifted ISO string would silently ask for the wrong day.
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function Tile({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string | number
  hint?: string
  tone?: 'warn'
}) {
  return (
    <div className={tone === 'warn' ? 'tile tile--warn' : 'tile'}>
      <p className="tile__label">{label}</p>
      <p className="tile__value">{value}</p>
      {hint && <p className="tile__hint">{hint}</p>}
    </div>
  )
}

export function Dashboard() {
  const { me } = useAuth()
  const isOwner = me?.is_owner ?? false
  const day = today()

  const results = useQueries({
    queries: [
      {
        queryKey: ['dash', 'perform-today', day],
        queryFn: () =>
          apiGet<QueueResponse>(
            `/bookings/queue${qs({ perform_from: day, perform_to: day, limit: 1 })}`,
          ),
      },
      {
        queryKey: ['dash', 'booked-today', day],
        queryFn: () =>
          apiGet<QueueResponse>(
            `/bookings/queue${qs({ booked_from: day, booked_to: day, limit: 1 })}`,
          ),
      },
      {
        // Bookings paid for but not yet acknowledged — the actual to-do list.
        queryKey: ['dash', 'waiting'],
        queryFn: () =>
          apiGet<QueueResponse>(`/bookings/queue${qs({ state: 'ok', limit: 1 })}`),
      },
      {
        queryKey: ['dash', 'payments'],
        queryFn: () =>
          apiGet<CountResponse>(`/admin/payments${qs({ status: 'paid', limit: 1 })}`),
        enabled: isOwner,
      },
      {
        queryKey: ['dash', 'users'],
        queryFn: () => apiGet<CountResponse>(`/admin/users${qs({ limit: 1 })}`),
        enabled: isOwner,
      },
    ],
  })

  const [performToday, bookedToday, waiting, payments, users] = results
  const loading = results.some((r) => r.isLoading && r.fetchStatus !== 'idle')
  const failed = results.find((r) => r.isError)

  return (
    <section className="page">
      <h1 className="page__title">Dashboard</h1>
      <p className="page__lede">
        {isOwner
          ? 'Everything across Nithara.'
          : 'Scoped to the temples you manage.'}
      </p>

      {failed && (
        <p className="banner banner--warn" role="alert">
          Some figures could not be loaded. They are left blank rather than shown
          as zero.
        </p>
      )}

      <div className="tiles">
        <Tile
          label="To perform today"
          value={loading ? '…' : (performToday.data?.total ?? '—')}
          hint="poojas with today's perform date"
        />
        <Tile
          label="Booked today"
          value={loading ? '…' : (bookedToday.data?.total ?? '—')}
          hint="new bookings placed today"
        />
        <Tile
          label="Awaiting action"
          value={loading ? '…' : (waiting.data?.total ?? '—')}
          hint="paid, not yet acknowledged"
          tone={waiting.data?.total ? 'warn' : undefined}
        />
        {isOwner && (
          <>
            <Tile
              label="Payments received"
              value={loading ? '…' : (payments.data?.total ?? '—')}
              hint="lifetime, status paid"
            />
            <Tile
              label="Registered users"
              value={loading ? '…' : (users.data?.total ?? '—')}
            />
          </>
        )}
      </div>

      {/*
        A blank figure is honest; a zero is a claim. When a request fails the
        tile shows an em dash, because "0 bookings today" and "we could not ask"
        are different facts and only one of them is safe to act on.
      */}
    </section>
  )
}
