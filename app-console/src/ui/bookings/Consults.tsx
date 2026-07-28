// Astrologer consults: one practitioner's diary, and how each one went.
//
// A different module and a different state machine from pooja bookings.
// Nothing may return to `confirmed`: `astro_bookings` has a unique constraint
// on (astrologer_id, starts_at), and a cancelled row keeps holding that slot,
// so reviving one would re-seat a consult somebody else may have booked since.
// Only the user-facing booking path revives a slot, and it checks first.
//
// Owner-only, unlike the pooja queue — consults are not scoped to a temple, so
// there is no grant that could narrow them.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { astrologerDiary, listAstrologers, setConsultStatus } from '../../api/bookings'
import { CONSULT_TARGETS, stateLabel, whenStamp } from '../../lib/booking'
import { money } from '../../lib/money'
import { Problem } from '../bits'
import { StateBadge } from './bits'

export function Consults() {
  const queryClient = useQueryClient()
  const [astrologerId, setAstrologerId] = useState('')
  const [includeCancelled, setIncludeCancelled] = useState(true)

  const astrologers = useQuery({ queryKey: ['astrologers'], queryFn: listAstrologers })
  const diary = useQuery({
    queryKey: ['diary', astrologerId, includeCancelled],
    queryFn: () => astrologerDiary(astrologerId, includeCancelled),
    enabled: !!astrologerId,
  })

  const move = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      setConsultStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['diary'] }),
  })

  const chosen = (astrologers.data ?? []).find((a) => a.id === astrologerId)
  const rows = diary.data ?? []

  return (
    <section className="page">
      <h1 className="page__title">Consults</h1>
      <p className="page__lede">
        An astrologer's diary, and the record of how each consult went. Nothing here
        can be moved back to confirmed.
      </p>

      <Problem error={astrologers.error ?? diary.error ?? move.error} />

      <div className="toolbar">
        <label className="toolbar__field toolbar__field--grow">
          <span>Astrologer</span>
          <select value={astrologerId} onChange={(e) => setAstrologerId(e.target.value)}>
            <option value="">Choose an astrologer…</option>
            {(astrologers.data ?? []).map((a) => (
              <option key={a.id} value={a.id}>
                {a.name} — {a.district}
                {a.active ? '' : ' (inactive)'}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={includeCancelled}
            onChange={(e) => setIncludeCancelled(e.target.checked)}
          />
          <span>Show cancelled</span>
        </label>
      </div>

      {chosen && (
        <p className="count">
          {diary.isLoading
            ? 'Loading…'
            : `${rows.length} consult${rows.length === 1 ? '' : 's'} · ${money(
                chosen.price_paise_per_min,
              )} per minute`}
        </p>
      )}

      {!astrologerId ? (
        <p className="empty">Pick an astrologer to see their diary.</p>
      ) : (
        <div className="tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Length</th>
                <th>Devotee</th>
                <th>Status</th>
                <th>Record how it went</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr key={c.id}>
                  <td>{whenStamp(c.starts_at)}</td>
                  <td>{c.duration_min} min</td>
                  <td>
                    <a href={`tel:${c.user_phone}`}>{c.user_phone}</a>
                  </td>
                  <td>
                    <StateBadge state={c.status} />
                  </td>
                  <td className="cell__acts">
                    {CONSULT_TARGETS.filter((s) => s !== c.status).map((s) => (
                      <button
                        key={s}
                        className="btn"
                        disabled={move.isPending}
                        onClick={() => move.mutate({ id: c.id, status: s })}
                      >
                        {stateLabel(s)}
                      </button>
                    ))}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!diary.isLoading && !rows.length && (
            <p className="empty">Nothing booked with this astrologer.</p>
          )}
        </div>
      )}
    </section>
  )
}
