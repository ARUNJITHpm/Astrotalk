// The directory: every temple this operator may touch, filterable.
//
// The list is deliberately the CONSOLE list (`/temples/manage`) rather than the
// public one, so retired temples and unreviewed drafts are both visible. An
// operator's job here is largely to find the rows the app is hiding.

import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { DEITIES, listTemples } from '../../api/temples'
import { useAuth } from '../../lib/auth'
import {
  EMPTY_FILTER,
  districtsOf,
  filterTemples,
  type TempleFilter,
  type Tri,
} from '../../lib/temple'
import { Badge, Problem } from '../bits'

function TriFilter({
  label,
  value,
  onChange,
  yes,
  no,
}: {
  label: string
  value: Tri
  onChange: (v: Tri) => void
  yes: string
  no: string
}) {
  return (
    <label className="toolbar__field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value as Tri)}>
        <option value="any">Any</option>
        <option value="yes">{yes}</option>
        <option value="no">{no}</option>
      </select>
    </label>
  )
}

export function TempleList() {
  const { me } = useAuth()
  const [filter, setFilter] = useState<TempleFilter>(EMPTY_FILTER)
  const { data, isLoading, error } = useQuery({
    queryKey: ['temples'],
    queryFn: listTemples,
  })

  const temples = useMemo(() => data ?? [], [data])
  const shown = useMemo(() => filterTemples(temples, filter), [temples, filter])
  const districts = useMemo(() => districtsOf(temples), [temples])
  const set = (patch: Partial<TempleFilter>) => setFilter((f) => ({ ...f, ...patch }))

  return (
    <section className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">All temples</h1>
          <p className="page__lede">
            The directory the app serves. Retired and unreviewed rows are shown
            here and nowhere else.
          </p>
        </div>
        {me?.is_owner && (
          <Link className="btn btn--primary btn--inline" to="/temples/new">
            Add a temple
          </Link>
        )}
      </div>

      <Problem error={error} />

      <div className="toolbar">
        <label className="toolbar__field toolbar__field--grow">
          <span>Search</span>
          <input
            type="search"
            value={filter.q}
            placeholder="name, Malayalam name, town or id"
            onChange={(e) => set({ q: e.target.value })}
          />
        </label>
        <label className="toolbar__field">
          <span>District</span>
          <select
            value={filter.district}
            onChange={(e) => set({ district: e.target.value })}
          >
            <option value="">All</option>
            {districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <label className="toolbar__field">
          <span>Deity</span>
          <select value={filter.deity} onChange={(e) => set({ deity: e.target.value })}>
            <option value="">All</option>
            {DEITIES.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
        </label>
        <TriFilter
          label="Reviewed"
          value={filter.reviewed}
          onChange={(reviewed) => set({ reviewed })}
          yes="Signed off"
          no="Not yet"
        />
        <TriFilter
          label="Listed"
          value={filter.active}
          onChange={(active) => set({ active })}
          yes="Listed"
          no="Retired"
        />
      </div>

      <p className="count" role="status">
        {isLoading
          ? 'Loading…'
          : `${shown.length} of ${temples.length} temple${temples.length === 1 ? '' : 's'}`}
      </p>

      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Temple</th>
              <th>District</th>
              <th>Deity</th>
              <th>Sign-off</th>
              <th>In the app</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((t) => (
              <tr key={t.id}>
                <td>
                  <Link className="celllink" to={`/temples/${encodeURIComponent(t.id)}`}>
                    {t.name}
                  </Link>
                  <span className="cell__ml" lang="ml">
                    {t.name_ml}
                  </span>
                  <span className="cell__sub">{t.town || t.id}</span>
                </td>
                <td>{t.district}</td>
                <td>{t.deity}</td>
                <td>
                  <Badge on={t.reviewed} yes="Reviewed" no="Draft" />
                </td>
                <td>
                  <Badge on={t.active} yes="Listed" no="Retired" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && !shown.length && (
          <p className="empty">
            {temples.length
              ? 'No temple matches those filters.'
              : 'No temples are assigned to you.'}
          </p>
        )}
      </div>
    </section>
  )
}
