// Check-ins, streaks and milestones across the register.
//
// Every engagement figure the product had was per-caller — a devotee could see
// their own streak, and nobody could see whether the feature worked at all.
//
// Nothing on this page is invented. A user with no check-ins is counted as a
// zero rather than dropped, because dropping them would make these totals
// disagree with the register with no way to tell why. When the aggregate has
// counted fewer people than exist, the page says so instead of implying it is
// showing everybody.

import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { engagement } from '../../api/people'
import { whenStamp } from '../../lib/booking'
import { Problem } from '../bits'

// The badge keys the app defines (identity/service.py `_milestone_list`).
const BADGE_LABELS: Record<string, string> = {
  first_temple: 'Visited a temple',
  ten_temples: 'Visited ten temples',
  first_pooja: 'Booked a pooja',
  week_streak: 'Seven-day streak',
  five_districts: 'Five districts',
}

function Tile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="tile">
      <p className="tile__label">{label}</p>
      <p className="tile__value">{value}</p>
      {hint && <p className="tile__hint">{hint}</p>}
    </div>
  )
}

export function Engagement() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['engagement'],
    queryFn: () => engagement(25),
  })

  return (
    <section className="page">
      <h1 className="page__title">Engagement</h1>
      <p className="page__lede">
        Who is coming back, and which milestones people are actually reaching.
      </p>

      <Problem error={error} />

      {isLoading && <p className="empty">Loading…</p>}

      {data && (
        <>
          {data.truncated && (
            <p className="banner banner--warn" role="status">
              These figures cover the first {data.users_counted} of{' '}
              {data.users_total} accounts, not the whole register.
            </p>
          )}

          <div className="tiles">
            <Tile
              label="Checked in today"
              value={data.checkins.checked_in_today}
              hint={`of ${data.users_counted} accounts`}
            />
            <Tile
              label="On a live streak"
              value={data.checkins.users_on_a_streak}
              hint="checked in today or yesterday"
            />
            <Tile
              label="Have ever checked in"
              value={data.checkins.users_ever}
              hint={`${data.checkins.total} check-ins in total`}
            />
          </div>

          <h2 className="section__title">Milestones</h2>
          <div className="tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Badge</th>
                  <th>Target</th>
                  <th>Unlocked by</th>
                </tr>
              </thead>
              <tbody>
                {data.milestones.map((m) => (
                  <tr key={m.key}>
                    <td>{BADGE_LABELS[m.key] ?? m.key}</td>
                    <td className="num">{m.target}</td>
                    <td className="num">{m.unlocked}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.milestones.length && (
              <p className="empty">No milestone data yet.</p>
            )}
          </div>

          <h2 className="section__title">Most engaged</h2>
          <p className="field__hint">
            Longest live streak first. These are the people worth talking to.
          </p>
          <div className="tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>Streak</th>
                  <th>Check-ins</th>
                  <th>Temples</th>
                  <th>Poojas</th>
                  <th>Badges</th>
                </tr>
              </thead>
              <tbody>
                {data.most_engaged.map((u) => (
                  <tr key={u.user_id}>
                    <td>
                      <Link className="celllink" to={`/people/users/${u.user_id}`}>
                        {u.name || '(no name)'}
                      </Link>
                      <span className="cell__sub">{u.phone}</span>
                    </td>
                    <td className="num">{u.streak}</td>
                    <td className="num">{u.checkins}</td>
                    <td className="num">
                      {u.temples_visited}
                      <span className="cell__sub">{u.districts_visited} districts</span>
                    </td>
                    <td className="num">{u.poojas}</td>
                    <td className="num">{u.badges}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.most_engaged.length && (
              <p className="empty">Nobody has an account yet.</p>
            )}
          </div>

          <p className="field__hint">
            Counted {whenStamp(data.generated_at)}, against {data.day} as today.
          </p>
        </>
      )}
    </section>
  )
}
