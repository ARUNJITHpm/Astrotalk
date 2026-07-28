// "What do we perform tomorrow", grouped by star day.
//
// This is a sheet somebody prints and carries into the temple, so it is built
// to be read on paper: one heading per nakshatram, both scripts, and no
// controls in the printed output. The print CSS lives in styles.css.
//
// `undated` is the number the screen exists to surface. `perform_on` is
// optional on a booking — the app made it so for backwards compatibility — and
// a booking without one appears on NO sheet at any date. Left as a silent
// omission that is a pooja nobody performs, so it is counted and linked.

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { worklist } from '../../api/bookings'
import { listTemples } from '../../api/temples'
import { stateLabel, today } from '../../lib/booking'
import { nakLabel } from '../../lib/nakshatrams'
import { Problem } from '../bits'

function tomorrow(): string {
  const day = new Date()
  day.setDate(day.getDate() + 1)
  const month = `${day.getMonth() + 1}`.padStart(2, '0')
  return `${day.getFullYear()}-${month}-${String(day.getDate()).padStart(2, '0')}`
}

export function Worklist() {
  const [templeId, setTempleId] = useState('')
  const [day, setDay] = useState(today())

  const temples = useQuery({ queryKey: ['temples'], queryFn: listTemples })
  const sheet = useQuery({
    queryKey: ['worklist', templeId, day],
    queryFn: () => worklist(templeId || undefined, day || undefined),
  })

  const templeName =
    (temples.data ?? []).find((t) => t.id === templeId)?.name ?? 'All my temples'
  const groups = sheet.data?.groups ?? []

  return (
    <section className="page">
      <div className="page__head noprint">
        <div>
          <h1 className="page__title">Temple worklist</h1>
          <p className="page__lede">
            What to perform on a day, grouped by star. Print it and take it in.
          </p>
        </div>
        <button className="btn btn--inline" onClick={() => window.print()}>
          Print
        </button>
      </div>

      <Problem error={sheet.error} />

      <div className="toolbar noprint">
        <label className="toolbar__field toolbar__field--grow">
          <span>Temple</span>
          <select value={templeId} onChange={(e) => setTempleId(e.target.value)}>
            <option value="">All my temples</option>
            {(temples.data ?? []).map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        <label className="toolbar__field">
          <span>Day</span>
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <div className="toolbar__field">
          <span>&nbsp;</span>
          <div className="row">
            <button className="btn" onClick={() => setDay(today())}>
              Today
            </button>
            <button className="btn" onClick={() => setDay(tomorrow())}>
              Tomorrow
            </button>
          </div>
        </div>
      </div>

      <div className="sheet">
        <h2 className="sheet__title">
          {templeName} · {day || 'every dated booking'}
        </h2>
        <p className="count">
          {sheet.isLoading ? 'Loading…' : `${sheet.data?.total ?? 0} to perform`}
        </p>

        {!sheet.isLoading && !groups.length && (
          <p className="empty">Nothing is booked for that day.</p>
        )}

        {groups.map((group) => (
          <div className="starblock" key={group.nak ?? 'none'}>
            <h3 className="starblock__title">
              {nakLabel(group.nak)}
              <span className="starblock__count">{group.items.length}</span>
            </h3>
            <table className="table">
              <thead>
                <tr>
                  <th>Ref</th>
                  <th>Offering</th>
                  <th>For</th>
                  <th>State</th>
                  <th>Note</th>
                </tr>
              </thead>
              <tbody>
                {group.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link className="celllink" to={`/bookings/${item.id}`}>
                        {item.ref}
                      </Link>
                    </td>
                    <td>{item.pooja_name}</td>
                    <td>{item.member_name || '—'}</td>
                    <td>{stateLabel(item.state)}</td>
                    <td>{item.operator_note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>

      {!!sheet.data?.undated && (
        <p className="banner banner--warn noprint" role="status">
          {sheet.data.undated} booking{sheet.data.undated === 1 ? '' : 's'} carry no
          perform date, so {sheet.data.undated === 1 ? 'it appears' : 'they appear'} on
          no sheet at all. Find {sheet.data.undated === 1 ? 'it' : 'them'} in the{' '}
          <Link to="/bookings">queue</Link> and give{' '}
          {sheet.data.undated === 1 ? 'it a date' : 'them dates'}.
        </p>
      )}
    </section>
  )
}
