// A date explorer for the panchangam engine.
//
// This is a tester, and its job is to answer one question honestly: is what the
// app told a devotee this morning correct? So the `mock` flag and the source
// are given the same weight as the figures themselves. A mocked panchangam
// returns plausible-looking Malayalam that is not derived from any ephemeris,
// and an operator comparing it against a printed calendar and finding it wrong
// needs to know that before they go looking for a bug in the almanac.

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { panchangam } from '../../api/astrology'
import { today } from '../../lib/content'
import { Field, Problem } from '../bits'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="deftrow">
      <span className="deftrow__label">{label}</span>
      <span className="deftrow__value" lang="ml">
        {value || '—'}
      </span>
    </div>
  )
}

export function Panchangam() {
  const [day, setDay] = useState(today())

  const { data, isLoading, error } = useQuery({
    queryKey: ['panchangam', day],
    queryFn: () => panchangam(day || undefined),
  })

  return (
    <section className="page">
      <h1 className="page__title">Panchangam</h1>
      <p className="page__lede">
        What the engine says about a day — the same call the app and every temple
        microsite make.
      </p>

      <div className="toolbar">
        <Field label="Day">
          <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
        </Field>
        <button className="btn btn--ghost" onClick={() => setDay(today())}>
          Today
        </button>
      </div>

      <Problem error={error} />
      {isLoading && <p className="empty">Loading…</p>}

      {data && (
        <>
          {data.mock && (
            <p className="banner banner--warn" role="status">
              The ephemeris is mocked on this installation. These figures are
              placeholders, not calculations — do not check them against an
              almanac and do not act on them.
            </p>
          )}
          <div className="card">
            <Row label="Date" value={data.date} />
            <Row label="Nakshatram" value={data.nakshatram} />
            <Row label="Nalla neram" value={data.nalla_neram} />
            <Row label="Tithi" value={data.tithi} />
            <Row label="Computed by" value={data.source} />
          </div>
          <p className="field__hint">
            Computed at local noon, Asia/Kolkata. Nalla neram here is the Abhijit
            muhurta — the windows that depend on a particular place's sunrise
            (rahu kalam and the rest) need a location and are not shown.
          </p>
        </>
      )}
    </section>
  )
}
