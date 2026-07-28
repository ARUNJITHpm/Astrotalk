// The festival calendar.
//
// Festivals matter more than their size suggests: subscribers to a temple's
// microsite get a WhatsApp message three days before each one, so a date typed
// as last year is a message that never goes and a date typed a month early is a
// message that goes to the wrong week. That is why the list shows days already
// past instead of tidying them away — a wrong date is only findable if it is
// still on screen.
//
// A festival hangs off a PARTNER, not a temple: the create route is
// POST /temples/partners/{slug}/festivals, because the microsite that renders
// it is the partner's. So the add form picks a partner, and a temple with no
// partnership cannot have one yet.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  createFestival,
  deleteFestival,
  listFestivals,
  listPartners,
  listTemples,
  patchFestival,
  type Festival,
} from '../../api/temples'
import { Field, Problem } from './bits'

function today(): string {
  const now = new Date()
  const month = `${now.getMonth() + 1}`.padStart(2, '0')
  const day = `${now.getDate()}`.padStart(2, '0')
  return `${now.getFullYear()}-${month}-${day}`
}

function FestivalRow({ festival, templeName }: { festival: Festival; templeName: string }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState({
    name: festival.name,
    name_ml: festival.name_ml,
    day: festival.day,
  })
  const [confirming, setConfirming] = useState(false)

  const done = () => queryClient.invalidateQueries({ queryKey: ['festivals'] })
  const save = useMutation({
    mutationFn: () => patchFestival(festival.id, draft),
    onSuccess: done,
  })
  const remove = useMutation({
    mutationFn: () => deleteFestival(festival.id),
    onSuccess: done,
  })

  const dirty =
    draft.name !== festival.name ||
    draft.name_ml !== festival.name_ml ||
    draft.day !== festival.day
  const past = festival.day < today()

  return (
    <tr className={past ? 'row--off' : undefined}>
      <td>
        <span className="cell__sub">{templeName}</span>
      </td>
      <td>
        <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
      </td>
      <td>
        <input
          lang="ml"
          spellCheck={false}
          className="input--ml"
          value={draft.name_ml}
          onChange={(e) => setDraft({ ...draft, name_ml: e.target.value })}
        />
      </td>
      <td>
        <input
          type="date"
          value={draft.day}
          onChange={(e) => setDraft({ ...draft, day: e.target.value })}
        />
        {past && <span className="cell__sub">past</span>}
      </td>
      <td className="cell__acts">
        <button className="btn" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          Save
        </button>
        {confirming ? (
          <>
            <button
              className="btn btn--danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Really delete
            </button>
            <button className="btn" onClick={() => setConfirming(false)}>
              Keep
            </button>
          </>
        ) : (
          <button className="btn" onClick={() => setConfirming(true)}>
            Delete
          </button>
        )}
        <Problem error={save.error ?? remove.error} />
      </td>
    </tr>
  )
}

export function Festivals() {
  const queryClient = useQueryClient()
  const festivals = useQuery({ queryKey: ['festivals'], queryFn: () => listFestivals() })
  const temples = useQuery({ queryKey: ['temples'], queryFn: listTemples })
  const partners = useQuery({ queryKey: ['partners'], queryFn: listPartners })

  const [form, setForm] = useState({ slug: '', name: '', name_ml: '', day: '' })

  const names = useMemo(() => {
    const map = new Map<string, string>()
    for (const t of temples.data ?? []) map.set(t.id, t.name)
    return map
  }, [temples.data])

  const add = useMutation({
    mutationFn: () =>
      createFestival(form.slug, {
        name: form.name.trim(),
        name_ml: form.name_ml.trim(),
        day: form.day,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['festivals'] })
      setForm({ ...form, name: '', name_ml: '', day: '' })
    },
  })

  const livePartners = (partners.data ?? []).filter((p) => p.active)
  const ready = form.slug && form.name.trim() && form.day
  const rows = festivals.data ?? []

  return (
    <section className="page">
      <h1 className="page__title">Festivals</h1>
      <p className="page__lede">
        Dated festivals for partner temples. Subscribers are messaged three days
        before each one, so the date is the part that has to be right.
      </p>

      <details className="card">
        <summary>Add a festival</summary>
        {!livePartners.length && (
          <p className="field__hint">
            No live partner temples. A festival belongs to a partner's microsite, so
            register one under Partners &amp; QR first.
          </p>
        )}
        <div className="grid2">
          <Field label="Partner temple">
            <select value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })}>
              <option value="">Choose…</option>
              {livePartners.map((p) => (
                <option key={p.id} value={p.slug}>
                  {names.get(p.temple_id) ?? p.temple_id} ({p.slug})
                </option>
              ))}
            </select>
          </Field>
          <Field label="Date">
            <input
              type="date"
              value={form.day}
              onChange={(e) => setForm({ ...form, day: e.target.value })}
            />
          </Field>
          <Field label="Name">
            <input
              value={form.name}
              placeholder="Painkuni Utsavam"
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field label="Name" ml>
            <input
              lang="ml"
              spellCheck={false}
              value={form.name_ml}
              placeholder="പൈങ്കുനി ഉത്സവം"
              onChange={(e) => setForm({ ...form, name_ml: e.target.value })}
            />
          </Field>
        </div>
        <p className="field__hint">
          The microsite shows the Malayalam name when there is one, so it is worth
          filling in even though it is optional.
        </p>
        <Problem error={add.error} />
        <button
          className="btn btn--primary btn--inline"
          disabled={!ready || add.isPending}
          onClick={() => add.mutate()}
        >
          Add festival
        </button>
      </details>

      <Problem error={festivals.error} />

      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Temple</th>
              <th>Name</th>
              <th>Malayalam</th>
              <th>Date</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((f) => (
              <FestivalRow
                key={f.id}
                festival={f}
                templeName={names.get(f.temple_id) ?? f.temple_id}
              />
            ))}
          </tbody>
        </table>
        {festivals.isLoading && <p className="empty">Loading…</p>}
        {!festivals.isLoading && !rows.length && (
          <p className="empty">No festivals on record.</p>
        )}
      </div>
    </section>
  )
}
