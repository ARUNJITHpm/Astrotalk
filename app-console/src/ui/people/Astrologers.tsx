// The practitioner directory: onboarding, pricing, weekly hours, visibility.
//
// Every one of the 28 seeded entries is a generated placeholder — this is how
// the first real practitioner gets in, and how the placeholders leave. They
// leave by being hidden, not deleted: `astro_bookings` references the id as a
// plain string with no foreign key, so a DELETE would orphan every consult ever
// booked with them.
//
// Availability is replaced wholesale rather than merged, matching the PUT
// behind it — "these are my hours" is how a person states it, and a partial
// update makes removing a window awkward. Narrowing the schedule never cancels
// an existing consult: those hold an absolute instant, not a reference to a
// window. It only stops new bookings.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import {
  createAstrologer,
  listAstrologers,
  patchAstrologer,
  replaceAvailability,
  setAstrologerActive,
  type Astrologer,
  type AvailabilityWindow,
} from '../../api/people'
import { money } from '../../lib/money'
import { WEEKDAYS, availabilityProblem } from '../../lib/people'
import { readPaise } from '../../lib/money'
import { Badge, Field, Problem } from '../bits'

const ID_RE = /^[a-z0-9][a-z0-9-]{1,60}$/
const NEW_WINDOW: AvailabilityWindow = {
  weekday: 0,
  start: '09:00',
  end: '12:00',
  duration_min: 30,
}

function csv(values: string[]): string {
  return values.join(', ')
}
function fromCsv(text: string): string[] {
  return text
    .split(',')
    .map((v) => v.trim())
    .filter(Boolean)
}

function Schedule({ astrologer }: { astrologer: Astrologer }) {
  const queryClient = useQueryClient()
  const [windows, setWindows] = useState<AvailabilityWindow[]>(astrologer.availability)

  useEffect(() => {
    setWindows(astrologer.availability)
  }, [astrologer.id, astrologer.updated_at])

  const save = useMutation({
    mutationFn: () => replaceAvailability(astrologer.id, windows),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['astrologers'] }),
  })

  const problem = availabilityProblem(windows)
  const set = (index: number, patch: Partial<AvailabilityWindow>) =>
    setWindows(windows.map((w, i) => (i === index ? { ...w, ...patch } : w)))

  return (
    <div>
      <p className="field__hint">
        Weekly hours in IST. Slots are cut from each window at the consult
        length, so a 09:00–12:00 window at 30 minutes offers six.
      </p>
      {windows.map((w, i) => (
        <div className="row row--window" key={i}>
          <select
            value={w.weekday}
            onChange={(e) => set(i, { weekday: Number(e.target.value) })}
          >
            {WEEKDAYS.map((day, index) => (
              <option key={day} value={index}>
                {day}
              </option>
            ))}
          </select>
          <input type="time" value={w.start} onChange={(e) => set(i, { start: e.target.value })} />
          <span className="row__dash">to</span>
          <input type="time" value={w.end} onChange={(e) => set(i, { end: e.target.value })} />
          <input
            className="input--num"
            inputMode="numeric"
            value={w.duration_min}
            onChange={(e) => set(i, { duration_min: Number(e.target.value) || 0 })}
          />
          <span className="row__dash">min</span>
          <button className="btn" onClick={() => setWindows(windows.filter((_, j) => j !== i))}>
            Remove
          </button>
        </div>
      ))}
      <div className="row">
        <button className="btn" onClick={() => setWindows([...windows, { ...NEW_WINDOW }])}>
          Add a window
        </button>
        <button
          className="btn btn--primary btn--inline"
          disabled={!!problem || save.isPending}
          onClick={() => save.mutate()}
        >
          {save.isPending ? 'Saving…' : 'Replace the schedule'}
        </button>
      </div>
      {problem && <p className="field__error">{problem}</p>}
      {!windows.length && (
        <p className="field__hint">
          No windows means no bookable slots at all — which reads as "nobody wants
          this astrologer" rather than "we never set their hours".
        </p>
      )}
      <Problem error={save.error} />
    </div>
  )
}

function AstrologerCard({ astrologer }: { astrologer: Astrologer }) {
  const queryClient = useQueryClient()
  const [panel, setPanel] = useState<'' | 'edit' | 'hours'>('')
  const [form, setForm] = useState({
    name: astrologer.name,
    name_ml: astrologer.name_ml,
    district: astrologer.district,
    town: astrologer.town,
    specialties: csv(astrologer.specialties),
    languages: csv(astrologer.languages),
    experience_years: String(astrologer.experience_years),
    bio_ml: astrologer.bio_ml,
    price: String(astrologer.price_paise_per_min / 100),
  })

  const done = () => queryClient.invalidateQueries({ queryKey: ['astrologers'] })
  const price = readPaise(form.price)
  const save = useMutation({
    mutationFn: () =>
      patchAstrologer(astrologer.id, {
        name: form.name.trim(),
        name_ml: form.name_ml.trim(),
        district: form.district.trim(),
        town: form.town.trim(),
        specialties: fromCsv(form.specialties),
        languages: fromCsv(form.languages),
        experience_years: Number(form.experience_years) || 0,
        bio_ml: form.bio_ml,
        price_paise_per_min: price.value ?? 0,
      }),
    onSuccess: async () => {
      await done()
      setPanel('')
    },
  })
  const visibility = useMutation({
    mutationFn: () => setAstrologerActive(astrologer.id, !astrologer.active),
    onSuccess: done,
  })

  const toggle = (which: typeof panel) => setPanel((p) => (p === which ? '' : which))

  return (
    <article className="card">
      <div className="card__head">
        <div>
          <h3 className="card__title">
            {astrologer.name}
            {astrologer.name_ml && (
              <span className="cell__ml" lang="ml">
                {astrologer.name_ml}
              </span>
            )}
          </h3>
          <p className="cell__sub">
            {astrologer.district} · {astrologer.experience_years} yrs ·{' '}
            {money(astrologer.price_paise_per_min)}/min ·{' '}
            {astrologer.availability.length} window
            {astrologer.availability.length === 1 ? '' : 's'}
          </p>
        </div>
        <Badge on={astrologer.active} yes="Listed" no="Hidden" />
      </div>

      <div className="row row--wrap">
        <button className="btn" onClick={() => toggle('edit')}>
          Edit
        </button>
        <button className="btn" onClick={() => toggle('hours')}>
          Weekly hours
        </button>
        <button className="btn" disabled={visibility.isPending} onClick={() => visibility.mutate()}>
          {astrologer.active ? 'Hide from the app' : 'List in the app'}
        </button>
      </div>

      <Problem error={visibility.error} />

      {panel === 'hours' && <Schedule astrologer={astrologer} />}

      {panel === 'edit' && (
        <>
          <div className="grid3">
            <Field label="Name">
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </Field>
            <Field label="Name" ml>
              <input
                lang="ml"
                spellCheck={false}
                value={form.name_ml}
                onChange={(e) => setForm({ ...form, name_ml: e.target.value })}
              />
            </Field>
            <Field label="District">
              <input
                value={form.district}
                onChange={(e) => setForm({ ...form, district: e.target.value })}
              />
            </Field>
            <Field label="Town">
              <input value={form.town} onChange={(e) => setForm({ ...form, town: e.target.value })} />
            </Field>
            <Field label="Years of practice">
              <input
                inputMode="numeric"
                value={form.experience_years}
                onChange={(e) => setForm({ ...form, experience_years: e.target.value })}
              />
            </Field>
            <Field label="Price per minute (₹)">
              <input
                inputMode="decimal"
                value={form.price}
                onChange={(e) => setForm({ ...form, price: e.target.value })}
              />
              {!price.ok && <span className="field__error">not a price</span>}
            </Field>
            <Field label="Specialties" hint="Comma separated.">
              <input
                value={form.specialties}
                onChange={(e) => setForm({ ...form, specialties: e.target.value })}
              />
            </Field>
            <Field label="Languages" hint="Comma separated.">
              <input
                value={form.languages}
                onChange={(e) => setForm({ ...form, languages: e.target.value })}
              />
            </Field>
          </div>
          <Field label="Bio" ml hint="What the app shows on their card.">
            <textarea
              rows={4}
              lang="ml"
              spellCheck={false}
              value={form.bio_ml}
              onChange={(e) => setForm({ ...form, bio_ml: e.target.value })}
            />
          </Field>
          {/*
            `rating` is editable in the API and is not offered here. It is a
            number a devotee would read as other devotees' opinion, and there is
            no review data behind it yet (GUARDRAILS §1).
          */}
          <Problem error={save.error} />
          <button
            className="btn btn--primary btn--inline"
            disabled={!price.ok || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? 'Saving…' : 'Save'}
          </button>
        </>
      )}
    </article>
  )
}

function Onboard() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    id: '',
    name: '',
    district: '',
    town: '',
    lat: '',
    lng: '',
    price: '',
  })

  const create = useMutation({
    mutationFn: () =>
      createAstrologer({
        id: form.id.trim(),
        name: form.name.trim(),
        district: form.district.trim(),
        town: form.town.trim(),
        lat: Number(form.lat),
        lng: Number(form.lng),
        price_paise_per_min: readPaise(form.price).value ?? 0,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['astrologers'] })
      setForm({ id: '', name: '', district: '', town: '', lat: '', lng: '', price: '' })
    },
  })

  const ready =
    ID_RE.test(form.id.trim()) &&
    form.name.trim() &&
    form.district.trim() &&
    Number.isFinite(Number(form.lat)) &&
    form.lat.trim() !== '' &&
    Number.isFinite(Number(form.lng)) &&
    form.lng.trim() !== ''

  return (
    <details className="card">
      <summary>Onboard a practitioner</summary>
      <p className="field__hint">
        A new entry is listed in the app straight away, but with no weekly hours
        nobody can book it — so set those next. Hours, bio and pricing are edited
        on the card below.
      </p>
      <div className="grid3">
        <Field label="Id" hint="Permanent. lowercase, hyphens.">
          <input
            value={form.id}
            placeholder="tsr-ramesh-panicker"
            onChange={(e) => setForm({ ...form, id: e.target.value })}
          />
        </Field>
        <Field label="Name">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </Field>
        <Field label="District">
          <input
            value={form.district}
            onChange={(e) => setForm({ ...form, district: e.target.value })}
          />
        </Field>
        <Field label="Town">
          <input value={form.town} onChange={(e) => setForm({ ...form, town: e.target.value })} />
        </Field>
        <Field label="Latitude">
          <input value={form.lat} onChange={(e) => setForm({ ...form, lat: e.target.value })} />
        </Field>
        <Field label="Longitude">
          <input value={form.lng} onChange={(e) => setForm({ ...form, lng: e.target.value })} />
        </Field>
        <Field label="Price per minute (₹)">
          <input
            inputMode="decimal"
            value={form.price}
            onChange={(e) => setForm({ ...form, price: e.target.value })}
          />
        </Field>
      </div>
      <Problem error={create.error} />
      <button
        className="btn btn--primary btn--inline"
        disabled={!ready || create.isPending}
        onClick={() => create.mutate()}
      >
        {create.isPending ? 'Adding…' : 'Onboard'}
      </button>
    </details>
  )
}

export function Astrologers() {
  const [q, setQ] = useState('')
  const [listed, setListed] = useState('')
  const astrologers = useQuery({ queryKey: ['astrologers'], queryFn: listAstrologers })

  const rows = (astrologers.data ?? []).filter((a) => {
    if (listed && (listed === 'yes') !== a.active) return false
    const term = q.trim().toLowerCase()
    if (!term) return true
    return [a.id, a.name, a.name_ml, a.district, a.town].some((f) =>
      f.toLowerCase().includes(term),
    )
  })

  return (
    <section className="page">
      <h1 className="page__title">Astrologers</h1>
      <p className="page__lede">
        The consultation directory. Every seeded entry is a placeholder — hide
        them as real practitioners arrive.
      </p>

      <Problem error={astrologers.error} />

      <div className="toolbar">
        <label className="toolbar__field toolbar__field--grow">
          <span>Search</span>
          <input
            type="search"
            value={q}
            placeholder="name, district or id"
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <label className="toolbar__field">
          <span>In the app</span>
          <select value={listed} onChange={(e) => setListed(e.target.value)}>
            <option value="">Any</option>
            <option value="yes">Listed</option>
            <option value="no">Hidden</option>
          </select>
        </label>
      </div>

      <p className="count" role="status">
        {astrologers.isLoading
          ? 'Loading…'
          : `${rows.length} of ${(astrologers.data ?? []).length}`}
      </p>

      <Onboard />

      {rows.map((a) => (
        <AstrologerCard key={a.id} astrologer={a} />
      ))}
      {!astrologers.isLoading && !rows.length && (
        <p className="empty">Nobody matches those filters.</p>
      )}
    </section>
  )
}
