// The offering catalogue: one master list, and each temple's departures from it.
//
// The two halves are on one screen because they are one decision. A price only
// means something relative to the master entry it overrides, and the commonest
// mistake — copying the master price into an override so a later repricing
// silently skips that temple — is only visible when both are in front of you.
//
// So an override's price and lead time are blank by default and blank means
// INHERIT. That is not the same as zero, and the input says so.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  clearOverride,
  createPooja,
  listOverrides,
  listPoojas,
  listTemples,
  patchPooja,
  rupees,
  setOverride,
  type Pooja,
} from '../../api/temples'
import { useAuth } from '../../lib/auth'
import { readDays, readPaise } from '../../lib/temple'
import { Badge, Field, Problem } from '../bits'

function MasterRow({ pooja, editable }: { pooja: Pooja; editable: boolean }) {
  const queryClient = useQueryClient()
  const [price, setPrice] = useState((pooja.amount_paise / 100).toString())
  const [lead, setLead] = useState(String(pooja.lead_days))

  const amount = readPaise(price)
  const days = readDays(lead)
  // A master offering must carry a figure; only an override may inherit one.
  const usable = amount.ok && amount.value !== null && days.ok && days.value !== null

  const save = useMutation({
    mutationFn: () =>
      patchPooja(pooja.key, {
        amount_paise: amount.value as number,
        lead_days: days.value as number,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['poojas'] }),
  })
  const toggle = useMutation({
    mutationFn: () => patchPooja(pooja.key, { active: !pooja.active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['poojas'] }),
  })

  const dirty =
    usable && (amount.value !== pooja.amount_paise || days.value !== pooja.lead_days)

  return (
    <tr>
      <td>
        <strong>{pooja.name}</strong>
        <span className="cell__ml" lang="ml">
          {pooja.name_ml}
        </span>
        <span className="cell__sub">{pooja.key}</span>
      </td>
      <td>
        <input
          className="input--num"
          inputMode="decimal"
          value={price}
          disabled={!editable}
          onChange={(e) => setPrice(e.target.value)}
        />
        {!amount.ok && <span className="field__error">not a price</span>}
      </td>
      <td>
        <input
          className="input--num"
          inputMode="numeric"
          value={lead}
          disabled={!editable}
          onChange={(e) => setLead(e.target.value)}
        />
        {!days.ok && <span className="field__error">whole days</span>}
      </td>
      <td>
        <Badge on={pooja.active} yes="Offered" no="Withdrawn" />
      </td>
      <td className="cell__acts">
        {editable && (
          <>
            <button
              className="btn"
              disabled={!dirty || save.isPending}
              onClick={() => save.mutate()}
            >
              Save
            </button>
            <button className="btn" disabled={toggle.isPending} onClick={() => toggle.mutate()}>
              {pooja.active ? 'Withdraw' : 'Offer'}
            </button>
          </>
        )}
        <Problem error={save.error ?? toggle.error} />
      </td>
    </tr>
  )
}

function NewMasterOffering() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({ key: '', name: '', name_ml: '', price: '', lead: '0' })
  const amount = readPaise(form.price)
  const days = readDays(form.lead)
  const create = useMutation({
    mutationFn: () =>
      createPooja({
        key: form.key.trim(),
        name: form.name.trim(),
        name_ml: form.name_ml.trim(),
        amount_paise: amount.value as number,
        lead_days: days.value as number,
        active: true,
        sort_order: 0,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['poojas'] })
      setForm({ key: '', name: '', name_ml: '', price: '', lead: '0' })
    },
  })
  const ready =
    form.key.trim() && form.name.trim() && amount.value !== null && days.value !== null

  return (
    <details className="card">
      <summary>Add a master offering</summary>
      <p className="field__hint">
        Adding one here makes it available at every temple. A temple that does not
        perform it withdraws it below.
      </p>
      <div className="grid3">
        <Field label="Key" hint="lowercase, hyphens">
          <input
            value={form.key}
            placeholder="pushpanjali"
            onChange={(e) => setForm({ ...form, key: e.target.value })}
          />
        </Field>
        <Field label="Name">
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
        <Field label="Name" ml>
          <input
            lang="ml"
            spellCheck={false}
            value={form.name_ml}
            onChange={(e) => setForm({ ...form, name_ml: e.target.value })}
          />
        </Field>
        <Field label="Price (₹)">
          <input
            inputMode="decimal"
            value={form.price}
            onChange={(e) => setForm({ ...form, price: e.target.value })}
          />
        </Field>
        <Field label="Lead days" hint="How far ahead it must be booked.">
          <input
            inputMode="numeric"
            value={form.lead}
            onChange={(e) => setForm({ ...form, lead: e.target.value })}
          />
        </Field>
      </div>
      <Problem error={create.error} />
      <button
        className="btn btn--primary btn--inline"
        disabled={!ready || create.isPending}
        onClick={() => create.mutate()}
      >
        Add offering
      </button>
    </details>
  )
}

function OverrideRow({ templeId, pooja }: { templeId: string; pooja: Pooja }) {
  const queryClient = useQueryClient()
  const { data: overrides } = useQuery({
    queryKey: ['overrides', templeId],
    queryFn: () => listOverrides(templeId),
  })
  const current = overrides?.find((o) => o.pooja_key === pooja.key)

  const [price, setPrice] = useState<string | null>(null)
  const [lead, setLead] = useState<string | null>(null)
  // null local state = "showing what the server holds"; a string = being edited.
  const priceText =
    price ?? (current?.amount_paise != null ? String(current.amount_paise / 100) : '')
  const leadText = lead ?? (current?.lead_days != null ? String(current.lead_days) : '')

  const done = async () => {
    await queryClient.invalidateQueries({ queryKey: ['overrides', templeId] })
    setPrice(null)
    setLead(null)
  }
  const amount = readPaise(priceText)
  const days = readDays(leadText)
  const write = useMutation({
    mutationFn: (active: boolean) =>
      setOverride(templeId, pooja.key, {
        amount_paise: amount.value,
        lead_days: days.value,
        active,
      }),
    onSuccess: done,
  })
  const drop = useMutation({
    mutationFn: () => clearOverride(templeId, pooja.key),
    onSuccess: done,
  })

  const offered = current?.active ?? true
  // Nonsense in a box would otherwise reach the server as null, which it reads
  // as "inherit the master price" — a silent repricing rather than an error.
  const usable = amount.ok && days.ok

  return (
    <tr className={offered ? undefined : 'row--off'}>
      <td>
        <strong>{pooja.name}</strong>
        <span className="cell__sub">
          master ₹{rupees(pooja.amount_paise)} · {pooja.lead_days}d
        </span>
      </td>
      <td>
        <input
          className="input--num"
          inputMode="decimal"
          placeholder="inherit"
          value={priceText}
          onChange={(e) => setPrice(e.target.value)}
        />
        {!amount.ok && <span className="field__error">not a price</span>}
      </td>
      <td>
        <input
          className="input--num"
          inputMode="numeric"
          placeholder="inherit"
          value={leadText}
          onChange={(e) => setLead(e.target.value)}
        />
        {!days.ok && <span className="field__error">whole days</span>}
      </td>
      <td>
        <Badge on={offered} yes="Performed here" no="Not performed" />
      </td>
      <td className="cell__acts">
        <button
          className="btn"
          disabled={!usable || write.isPending}
          onClick={() => write.mutate(offered)}
        >
          Save
        </button>
        <button
          className="btn"
          disabled={!usable || write.isPending}
          onClick={() => write.mutate(!offered)}
        >
          {offered ? 'Not performed' : 'Perform here'}
        </button>
        {current && (
          <button className="btn" disabled={drop.isPending} onClick={() => drop.mutate()}>
            Reset to master
          </button>
        )}
        <Problem error={write.error ?? drop.error} />
      </td>
    </tr>
  )
}

export function PoojaCatalogue() {
  const { me } = useAuth()
  const [templeId, setTempleId] = useState('')

  const poojas = useQuery({ queryKey: ['poojas'], queryFn: listPoojas })
  const temples = useQuery({ queryKey: ['temples'], queryFn: listTemples })

  const mine = useMemo(() => temples.data ?? [], [temples.data])
  const list = useMemo(() => poojas.data ?? [], [poojas.data])

  return (
    <section className="page">
      <h1 className="page__title">Pooja catalogue</h1>
      <p className="page__lede">
        The master offerings every temple starts from, and what each temple charges
        for them.
      </p>

      <Problem error={poojas.error ?? temples.error} />

      <h2 className="section__title">Master offerings</h2>
      {!me?.is_owner && (
        <p className="field__hint">
          The master catalogue is the owner's to change — it applies across the whole
          directory. Set your temple's own prices below.
        </p>
      )}
      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Offering</th>
              <th>Price (₹)</th>
              <th>Lead days</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.map((p) => (
              <MasterRow key={p.key} pooja={p} editable={!!me?.is_owner} />
            ))}
          </tbody>
        </table>
        {poojas.isLoading && <p className="empty">Loading…</p>}
        {!poojas.isLoading && !list.length && (
          <p className="empty">
            No master offerings yet. Until one exists no temple can be booked.
          </p>
        )}
      </div>
      {me?.is_owner && <NewMasterOffering />}

      <h2 className="section__title">One temple's prices</h2>
      <label className="toolbar__field toolbar__field--grow">
        <span>Temple</span>
        <select value={templeId} onChange={(e) => setTempleId(e.target.value)}>
          <option value="">Choose a temple…</option>
          {mine.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} — {t.district}
            </option>
          ))}
        </select>
      </label>

      {templeId && (
        <div className="tablewrap">
          <p className="field__hint">
            Leave a box empty to inherit the master value. Emptying a price later
            restores the inheritance, so a directory-wide repricing reaches this
            temple again.
          </p>
          <table className="table">
            <thead>
              <tr>
                <th>Offering</th>
                <th>Price here (₹)</th>
                <th>Lead days here</th>
                <th>Status</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {list.map((p) => (
                <OverrideRow key={p.key} templeId={templeId} pooja={p} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
