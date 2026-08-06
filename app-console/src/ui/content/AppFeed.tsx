// The notices and articles that appear on the app's home screen.
//
// These were three entries in a Python list until Part 8 gave them a table, so
// correcting a festival date meant a code change and a redeploy — the opposite
// of what a notices feed is for. This is the screen that finally makes it a
// feed rather than a constant.
//
// Two rules the server enforces and this screen states rather than discovers:
//
//   * **Every card says whose words it carries.** A notice from a temple is
//     attributed to that temple; anything in our own voice says Nithara. A card
//     with no attribution reads as an anonymous authority making claims about
//     somebody's temple (GUARDRAILS §1).
//   * **Nobody types a like count.** There are no such columns and the schema
//     rejects them outright, so the app shows 0 until real reactions exist.
//
// There is no delete, only withdraw. Pulling a wrong notice off the app should
// not destroy the text that then has to be corrected.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  createFeedItem,
  listFeed,
  patchFeedItem,
  setFeedPublished,
  type FeedItem,
} from '../../api/content'
import { FEED_ART, FEED_CATEGORIES, feedProblem } from '../../lib/content'
import { Field, Problem } from '../bits'

function Card({ item }: { item: FeedItem }) {
  const queryClient = useQueryClient()
  const [draft, setDraft] = useState({
    cat: item.cat,
    title_en: item.title_en,
    title_ml: item.title_ml,
    body_en: item.body_en,
    body_ml: item.body_ml,
    who_en: item.who_en,
    who_ml: item.who_ml,
    sort_order: String(item.sort_order),
  })

  const done = () => queryClient.invalidateQueries({ queryKey: ['feed'] })
  const save = useMutation({
    mutationFn: () =>
      patchFeedItem(item.id, {
        ...draft,
        sort_order: Number(draft.sort_order),
      }),
    onSuccess: done,
  })
  const toggle = useMutation({
    mutationFn: () => setFeedPublished(item.id, !item.published),
    onSuccess: done,
  })

  const order = Number(draft.sort_order)
  const problem =
    !draft.who_en.trim()
      ? 'A card must say whose words it carries.'
      : !draft.title_en.trim()
        ? 'A card needs a title.'
        : !Number.isInteger(order)
          ? 'The order must be a whole number.'
          : null

  const set = (key: keyof typeof draft) => (v: string) =>
    setDraft((d) => ({ ...d, [key]: v }))

  return (
    <details className="card">
      <summary>
        <strong>{item.title_en}</strong>{' '}
        <span className="badge">{item.cat}</span>{' '}
        <span className={item.published ? 'badge badge--on' : 'badge badge--off'}>
          {item.published ? 'on the app' : 'draft'}
        </span>{' '}
        <span className="cell__sub">{item.id}</span>
      </summary>

      <div className="grid2">
        <Field label="Category">
          <select value={draft.cat} onChange={(e) => set('cat')(e.target.value)}>
            {FEED_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Order" hint="lower shows first">
          <input
            className="input--num"
            inputMode="numeric"
            value={draft.sort_order}
            onChange={(e) => set('sort_order')(e.target.value)}
          />
        </Field>
        <Field label="Title">
          <input value={draft.title_en} onChange={(e) => set('title_en')(e.target.value)} />
        </Field>
        <Field label="Title" ml>
          <input
            className="input--ml"
            lang="ml"
            spellCheck={false}
            value={draft.title_ml}
            onChange={(e) => set('title_ml')(e.target.value)}
          />
        </Field>
        <Field label="Whose words" hint="the temple, or Nithara">
          <input value={draft.who_en} onChange={(e) => set('who_en')(e.target.value)} />
        </Field>
        <Field label="Whose words" ml>
          <input
            className="input--ml"
            lang="ml"
            spellCheck={false}
            value={draft.who_ml}
            onChange={(e) => set('who_ml')(e.target.value)}
          />
        </Field>
      </div>

      <Field label="Body">
        <textarea
          rows={4}
          value={draft.body_en}
          onChange={(e) => set('body_en')(e.target.value)}
        />
      </Field>
      <Field label="Body" ml>
        <textarea
          className="input--ml"
          lang="ml"
          spellCheck={false}
          rows={4}
          value={draft.body_ml}
          onChange={(e) => set('body_ml')(e.target.value)}
        />
      </Field>

      <div className="formfoot">
        <button
          className="btn btn--primary"
          disabled={!!problem || save.isPending}
          onClick={() => save.mutate()}
        >
          Save
        </button>
        <button className="btn" disabled={toggle.isPending} onClick={() => toggle.mutate()}>
          {item.published ? 'Withdraw from the app' : 'Publish to the app'}
        </button>
        {problem && <span className="field__error">{problem}</span>}
        <Problem error={save.error ?? toggle.error} />
      </div>
    </details>
  )
}

function NewCard() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    id: '',
    cat: FEED_CATEGORIES[0] as string,
    title_en: '',
    title_ml: '',
    who_en: '',
    body_en: '',
    body_ml: '',
    art: 0,
  })

  const create = useMutation({
    mutationFn: () => {
      const art = FEED_ART[form.art]
      return createFeedItem({
        id: form.id.trim(),
        cat: form.cat,
        title_en: form.title_en.trim(),
        title_ml: form.title_ml.trim(),
        who_en: form.who_en.trim(),
        body_en: form.body_en.trim(),
        body_ml: form.body_ml.trim(),
        image: art.image,
        glyph: art.glyph,
      })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['feed'] })
      setForm({
        id: '',
        cat: FEED_CATEGORIES[0] as string,
        title_en: '',
        title_ml: '',
        who_en: '',
        body_en: '',
        body_ml: '',
        art: 0,
      })
    },
  })

  const problem = feedProblem(form)

  return (
    <details className="card">
      <summary>Add a card</summary>
      <p className="field__hint">
        New cards start as drafts. Nothing reaches the app until you publish it.
      </p>
      <div className="grid2">
        <Field label="Id" hint="lowercase and hyphens; it never changes">
          <input
            value={form.id}
            placeholder="pooram-ilanjithara"
            onChange={(e) => setForm({ ...form, id: e.target.value })}
          />
        </Field>
        <Field label="Category">
          <select value={form.cat} onChange={(e) => setForm({ ...form, cat: e.target.value })}>
            {FEED_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Title">
          <input
            value={form.title_en}
            onChange={(e) => setForm({ ...form, title_en: e.target.value })}
          />
        </Field>
        <Field label="Title" ml>
          <input
            className="input--ml"
            lang="ml"
            spellCheck={false}
            value={form.title_ml}
            onChange={(e) => setForm({ ...form, title_ml: e.target.value })}
          />
        </Field>
        <Field label="Whose words" hint="required — a card is never anonymous">
          <input
            value={form.who_en}
            placeholder="Guruvayur Devaswom"
            onChange={(e) => setForm({ ...form, who_en: e.target.value })}
          />
        </Field>
        <Field label="Artwork">
          <select
            value={String(form.art)}
            onChange={(e) => setForm({ ...form, art: Number(e.target.value) })}
          >
            {FEED_ART.map((a, i) => (
              <option key={a.image} value={String(i)}>
                {a.label}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <Field label="Body">
        <textarea
          rows={3}
          value={form.body_en}
          onChange={(e) => setForm({ ...form, body_en: e.target.value })}
        />
      </Field>
      <Field label="Body" ml>
        <textarea
          className="input--ml"
          lang="ml"
          spellCheck={false}
          rows={3}
          value={form.body_ml}
          onChange={(e) => setForm({ ...form, body_ml: e.target.value })}
        />
      </Field>
      <Problem error={create.error} />
      <div className="formfoot">
        <button
          className="btn btn--primary"
          disabled={!!problem || create.isPending}
          onClick={() => create.mutate()}
        >
          Add the card
        </button>
        {form.id.trim() && problem && <span className="field__error">{problem}</span>}
      </div>
    </details>
  )
}

export function AppFeed() {
  const { data, isLoading, error } = useQuery({ queryKey: ['feed'], queryFn: listFeed })
  const rows = data ?? []

  return (
    <section className="page">
      <h1 className="page__title">App feed</h1>
      <p className="page__lede">
        The notices and articles on the app's home screen, drafts included.
      </p>

      <NewCard />

      <Problem error={error} />
      {isLoading && <p className="empty">Loading…</p>}
      {!isLoading && !rows.length && <p className="empty">No cards yet.</p>}

      {rows.map((item) => (
        <Card key={item.id} item={item} />
      ))}

      <p className="field__hint">
        The app shows likes and comments as zero. There are no such columns and
        nothing here can set them — a count nobody earned is a claim about how
        popular a notice is.
      </p>
    </section>
  )
}
