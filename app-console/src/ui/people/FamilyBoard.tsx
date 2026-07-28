// One user's family board, editable.
//
// This is the half that only existed inside the devotee's own app. An operator
// taking a booking over the phone is told "book it for my mother, her star is
// Pooram, she's about sixty" — and had nowhere to put any of it.
//
// Two things the form insists on:
//
//   - **A birth DATE, not an age.** An age is right for one year and silently
//     wrong after it, and this is the field a star-day reminder is computed
//     from. The age beside it is derived and never stored.
//   - **Leaving it empty is a real answer.** Inventing a birthday to record
//     "about sixty" corrupts the one field that matters. Blank means unknown,
//     and clearing a value later sends an explicit null.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  RELATIONS,
  addFamilyMember,
  listFamily,
  patchFamilyMember,
  removeFamilyMember,
  type Member,
} from '../../api/people'
import { NAKSHATRAMS, nakLabel } from '../../lib/nakshatrams'
import { ageLabel } from '../../lib/people'
import { Field, Problem } from '../bits'

function NakPicker({
  value,
  onChange,
}: {
  value: number | null
  onChange: (v: number | null) => void
}) {
  return (
    <select
      value={value === null ? '' : String(value)}
      onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
    >
      <option value="">Not known</option>
      {NAKSHATRAMS.map(([en, ml], index) => (
        <option key={en} value={index}>
          {en} · {ml}
        </option>
      ))}
    </select>
  )
}

function MemberRow({ userId, member }: { userId: number; member: Member }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState({
    name: member.name,
    rel: member.rel,
    nak: member.nak,
    dob: member.dob,
  })
  const [confirming, setConfirming] = useState(false)

  const done = () => queryClient.invalidateQueries({ queryKey: ['family', userId] })
  const save = useMutation({
    mutationFn: () => patchFamilyMember(userId, member.id, draft),
    onSuccess: done,
  })
  const remove = useMutation({
    mutationFn: () => removeFamilyMember(userId, member.id),
    onSuccess: done,
  })

  const dirty =
    draft.name !== member.name ||
    draft.rel !== member.rel ||
    draft.nak !== member.nak ||
    (draft.dob || null) !== member.dob

  return (
    <tr>
      <td>
        <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
      </td>
      <td>
        <select
          value={draft.rel}
          // The account holder's own row is always rSelf; the server ignores an
          // attempt to change it, so the control says so rather than appearing
          // to work.
          disabled={member.self}
          onChange={(e) => setDraft({ ...draft, rel: e.target.value })}
        >
          {RELATIONS.map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>
      </td>
      <td>
        <NakPicker value={draft.nak} onChange={(nak) => setDraft({ ...draft, nak })} />
      </td>
      <td>
        <input
          type="date"
          value={draft.dob ?? ''}
          onChange={(e) => setDraft({ ...draft, dob: e.target.value || null })}
        />
      </td>
      <td className="num">{ageLabel(draft.dob)}</td>
      <td className="cell__acts">
        <button className="btn" disabled={!dirty || save.isPending} onClick={() => save.mutate()}>
          Save
        </button>
        {member.self ? (
          <span className="cell__sub">the account holder</span>
        ) : confirming ? (
          <>
            <button
              className="btn btn--danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Really remove
            </button>
            <button className="btn" onClick={() => setConfirming(false)}>
              Keep
            </button>
          </>
        ) : (
          <button className="btn" onClick={() => setConfirming(true)}>
            Remove
          </button>
        )}
        <Problem error={save.error ?? remove.error} />
      </td>
    </tr>
  )
}

const BLANK = { name: '', rel: 'rMother', nak: null as number | null, dob: '' }

export function FamilyBoard({ userId }: { userId: number }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(BLANK)

  const family = useQuery({
    queryKey: ['family', userId],
    queryFn: () => listFamily(userId),
  })

  const add = useMutation({
    mutationFn: () =>
      addFamilyMember(userId, {
        name: form.name.trim(),
        rel: form.rel,
        nak: form.nak,
        dob: form.dob || null,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['family', userId] })
      setForm(BLANK)
    },
  })

  const rows = family.data ?? []

  return (
    <section className="card">
      <h2 className="card__title">Family board</h2>
      <p className="field__hint">
        Who a pooja can be booked for. The star is what a booking actually uses;
        the birth date is optional and only worth filling in when it is known
        exactly — an approximate one would be worse than none.
      </p>

      <Problem error={family.error} />

      <div className="tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Relation</th>
              <th>Star</th>
              <th>Born</th>
              <th>Age</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((m) => (
              <MemberRow key={m.id} userId={userId} member={m} />
            ))}
          </tbody>
        </table>
        {family.isLoading && <p className="empty">Loading…</p>}
      </div>

      <details className="card">
        <summary>Add someone</summary>
        <div className="grid3">
          <Field label="Name">
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </Field>
          <Field label="Relation">
            <select
              value={form.rel}
              onChange={(e) => setForm({ ...form, rel: e.target.value })}
            >
              {RELATIONS.filter(([key]) => key !== 'rSelf').map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Star" hint="What a booking is placed under.">
            <NakPicker value={form.nak} onChange={(nak) => setForm({ ...form, nak })} />
          </Field>
          <Field label="Born" hint="Only if the exact date is known.">
            <input
              type="date"
              value={form.dob}
              onChange={(e) => setForm({ ...form, dob: e.target.value })}
            />
          </Field>
        </div>
        <Problem error={add.error} />
        <button
          className="btn btn--primary btn--inline"
          disabled={!form.name.trim() || add.isPending}
          onClick={() => add.mutate()}
        >
          {add.isPending ? 'Adding…' : 'Add to the board'}
        </button>
      </details>

      {!!rows.length && (
        <p className="field__hint">
          Stars on file: {rows.filter((m) => m.nak !== null).map((m) => nakLabel(m.nak)).join(', ') || 'none yet'}.
          {' '}
          {rows.some((m) => m.nak === null) &&
            'A member with no star cannot be put on a star-day worklist.'}
        </p>
      )}
    </section>
  )
}
