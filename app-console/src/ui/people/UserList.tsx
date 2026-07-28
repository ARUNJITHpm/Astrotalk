// The devotee register.
//
// Search matches name and mobile, and nothing else. Searching by birth detail
// is not offered anywhere in the console: it would put a date of birth in a
// query string and therefore in an access log (GUARDRAILS §4), and no operator
// task needs it. That is a server rule too — this screen simply cannot ask.

import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { listUsers } from '../../api/people'
import { whenStamp } from '../../lib/booking'
import { Badge, Problem } from '../bits'

const PAGE = 50

export function UserList() {
  const [q, setQ] = useState('')
  const [active, setActive] = useState('')
  const [offset, setOffset] = useState(0)

  const query = {
    q: q.trim() || undefined,
    active: active === '' ? undefined : active === 'yes',
    limit: PAGE,
    offset,
  }
  const page = useQuery({
    queryKey: ['users', query],
    queryFn: () => listUsers(query),
    placeholderData: keepPreviousData,
  })

  // Narrowing while on page 7 leaves an operator staring at an empty table
  // that is not empty.
  const narrow = (fn: () => void) => {
    fn()
    setOffset(0)
  }

  const rows = page.data?.items ?? []
  const total = page.data?.total ?? 0

  return (
    <section className="page">
      <h1 className="page__title">Users</h1>
      <p className="page__lede">
        Everyone with an account, whether or not they have ever chatted or booked.
      </p>

      <Problem error={page.error} />

      <div className="toolbar">
        <label className="toolbar__field toolbar__field--grow">
          <span>Search</span>
          <input
            type="search"
            value={q}
            placeholder="name or mobile"
            onChange={(e) => narrow(() => setQ(e.target.value))}
          />
        </label>
        <label className="toolbar__field">
          <span>Account</span>
          <select value={active} onChange={(e) => narrow(() => setActive(e.target.value))}>
            <option value="">Any</option>
            <option value="yes">Enabled</option>
            <option value="no">Disabled</option>
          </select>
        </label>
      </div>

      <p className="count" role="status">
        {page.isLoading
          ? 'Loading…'
          : total
            ? `${offset + 1}–${offset + rows.length} of ${total}`
            : 'Nobody matches that'}
      </p>

      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Mobile</th>
              <th>Joined</th>
              <th>Account</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link className="celllink" to={`/people/users/${u.id}`}>
                    {u.name || '(no name)'}
                  </Link>
                  <span className="cell__sub">#{u.id}</span>
                </td>
                <td>{u.phone}</td>
                <td>{whenStamp(u.created_at)}</td>
                <td>
                  <Badge on={u.active} yes="Enabled" no="Disabled" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!page.isLoading && !rows.length && (
          <p className="empty">
            {q ? 'No account matches that name or mobile.' : 'No users yet.'}
          </p>
        )}
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
    </section>
  )
}
