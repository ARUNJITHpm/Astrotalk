// The concern → temple suggestion path, as the chat orchestrator sees it.
//
// A devotee says "things are stuck at work" and the chat replies with a temple
// and a reason. When that reply is wrong — the wrong deity, a temple three
// districts away, a reason that does not follow — this is where an operator
// finds out whether the suggester or the narration was at fault.
//
// No birth data is accepted here, and that is not a simplification: the
// endpoint takes already-derived keys precisely so a suggestion can be asked
// for without a chart (GUARDRAILS §4). A date-of-birth box on this screen would
// put a birth date in a query string, which is the one thing the design of that
// endpoint was arranged to prevent.

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { CONCERNS, suggestTemples } from '../../api/astrology'
import { Field, Problem } from '../bits'

export function TempleSuggest() {
  const [concern, setConcern] = useState<string>(CONCERNS[0])
  const [district, setDistrict] = useState('')
  const [k, setK] = useState('2')

  const { data, isLoading, error } = useQuery({
    queryKey: ['suggest', concern, district, k],
    queryFn: () =>
      suggestTemples({
        concern,
        district: district.trim() || undefined,
        k: Number(k),
      }),
  })

  const rows = data ?? []

  return (
    <section className="page">
      <h1 className="page__title">Temple suggest</h1>
      <p className="page__lede">
        What the chat would offer for a life concern, and why it chose it.
      </p>

      <div className="toolbar">
        <Field label="Concern">
          <select value={concern} onChange={(e) => setConcern(e.target.value)}>
            {CONCERNS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="District" hint="optional — narrows to one district">
          <input
            value={district}
            placeholder="e.g. Thrissur"
            onChange={(e) => setDistrict(e.target.value)}
          />
        </Field>
        <Field label="How many">
          <select value={k} onChange={(e) => setK(e.target.value)}>
            {[1, 2, 3, 4, 5].map((n) => (
              <option key={n} value={String(n)}>
                {n}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <Problem error={error} />
      {isLoading && <p className="empty">Loading…</p>}
      {!isLoading && !rows.length && (
        <p className="empty">
          Nothing matched. If a district is set, the suggester had no temple for
          that concern there — it does not silently widen the search.
        </p>
      )}

      {rows.map((t) => (
        <article className="card" key={t.id}>
          <div className="card__head">
            <h3 className="card__title">{t.name}</h3>
            <span className="cell__ml" lang="ml">
              {t.name_ml}
            </span>
            <span className="badge">{t.deity_ml || t.deity}</span>
          </div>
          <p className="cell__sub">
            {[t.town, t.district].filter(Boolean).join(', ')} · {t.id}
          </p>
          <div className="deftrow">
            <span className="deftrow__label">Why</span>
            <span className="deftrow__value">{t.reason}</span>
          </div>
          {t.vazhipadu.length > 0 && (
            <div className="deftrow">
              <span className="deftrow__label">Vazhipadu</span>
              <span className="deftrow__value">{t.vazhipadu.join(', ')}</span>
            </div>
          )}
          {t.days && (
            <div className="deftrow">
              <span className="deftrow__label">Days</span>
              <span className="deftrow__value" lang="ml">
                {t.days}
              </span>
            </div>
          )}
        </article>
      ))}
    </section>
  )
}
