// On-demand creative pieces: reel scripts, weekly news, nakshatram episodes.
//
// The studio and the daily pack look like the same screen and are not. These
// formats are for YouTube and Instagram, which the product does not post to, so
// there is no Publish button here at all — every piece leaves through a human.
// That absence is deliberate and the screen says so, because a missing button
// reads as "not built yet" unless something tells you otherwise.
//
// The caption is separated from the script for one reason: they go into two
// different boxes on the platform, and an operator copying the whole card into
// the description is the mistake this layout is trying to prevent.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  approveStudio,
  deleteStudio,
  generateStudio,
  listStudio,
  markStudioPublished,
  type StudioDraft,
} from '../../api/content'
import { STUDIO_KINDS, draftActions, studioKindLabel, urlProblem } from '../../lib/content'
import { Field, Problem } from '../bits'

function DraftCard({ draft }: { draft: StudioDraft }) {
  const queryClient = useQueryClient()
  const can = draftActions(draft.status)
  const [body, setBody] = useState(draft.body)
  const [url, setUrl] = useState('')
  const [recording, setRecording] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const done = () => queryClient.invalidateQueries({ queryKey: ['studio'] })
  const approve = useMutation({
    mutationFn: () => approveStudio(draft.id, body === draft.body ? undefined : body),
    onSuccess: done,
  })
  const mark = useMutation({
    mutationFn: () => markStudioPublished(draft.id, url.trim()),
    onSuccess: async () => {
      await done()
      setRecording(false)
      setUrl('')
    },
  })
  const remove = useMutation({ mutationFn: () => deleteStudio(draft.id), onSuccess: done })

  const urlIssue = urlProblem(url)
  const edited = body !== draft.body

  return (
    <article className="card">
      <div className="card__head">
        <h3 className="card__title">{draft.title || studioKindLabel(draft.kind)}</h3>
        <span className="badge">{studioKindLabel(draft.kind)}</span>
        {draft.topic && <span className="badge">{draft.topic}</span>}
        <span className={`badge${draft.status === 'published' ? ' badge--on' : ''}`}>
          {draft.status}
        </span>
      </div>

      <textarea
        className="input--ml"
        lang="ml"
        spellCheck={false}
        rows={10}
        value={body}
        disabled={!can.approve}
        onChange={(e) => setBody(e.target.value)}
      />

      {draft.caption && (
        <div className="snippet">
          <p className="field__hint">Caption — this goes in the post's description box.</p>
          <p lang="ml">{draft.caption}</p>
        </div>
      )}

      {draft.external_url && (
        <p className="field__hint">
          Posted at{' '}
          <a href={draft.external_url} target="_blank" rel="noreferrer">
            {draft.external_url}
          </a>
        </p>
      )}

      <div className="row">
        {can.approve && (
          <button
            className="btn btn--primary"
            disabled={approve.isPending}
            onClick={() => approve.mutate()}
          >
            {edited ? 'Save the edit and approve' : 'Approve'}
          </button>
        )}
        {can.markPublished && !recording && (
          <button className="btn" onClick={() => setRecording(true)}>
            Mark posted
          </button>
        )}
        {can.delete && !confirming && (
          <button className="btn btn--ghost" onClick={() => setConfirming(true)}>
            Delete
          </button>
        )}
      </div>

      {confirming && (
        <div className="confirmbox">
          <p>Delete this draft? Nothing here has been posted anywhere, so nothing breaks — but the script is gone.</p>
          <div className="row">
            <button
              className="btn btn--danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete it
            </button>
            <button className="btn btn--ghost" onClick={() => setConfirming(false)}>
              Keep it
            </button>
          </div>
        </div>
      )}

      {recording && (
        <div className="row">
          <Field label="Where you posted it" hint="the YouTube or Instagram URL">
            <input value={url} placeholder="https://…" onChange={(e) => setUrl(e.target.value)} />
          </Field>
          <button
            className="btn btn--primary"
            disabled={!!urlIssue || mark.isPending}
            onClick={() => mark.mutate()}
          >
            Record it
          </button>
          <button className="btn btn--ghost" onClick={() => setRecording(false)}>
            Cancel
          </button>
          {url.trim() && urlIssue && <span className="field__error">{urlIssue}</span>}
        </div>
      )}

      <Problem error={approve.error ?? mark.error ?? remove.error} />
    </article>
  )
}

export function Studio() {
  const queryClient = useQueryClient()
  const [kind, setKind] = useState(STUDIO_KINDS[0].key)
  const [topic, setTopic] = useState('')

  const drafts = useQuery({ queryKey: ['studio'], queryFn: listStudio })
  const generate = useMutation({
    mutationFn: () => generateStudio(kind, topic.trim()),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['studio'] })
      setTopic('')
    },
  })

  const chosen = STUDIO_KINDS.find((k) => k.key === kind)
  const rows = drafts.data ?? []

  return (
    <section className="page">
      <h1 className="page__title">Studio</h1>
      <p className="page__lede">
        Scripts and episodes you post by hand. Nithara does not publish to
        YouTube or Instagram, so nothing here goes out without you.
      </p>

      <div className="card">
        <div className="row">
          <Field label="Format" hint={chosen?.hint}>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {STUDIO_KINDS.map((k) => (
                <option key={k.key} value={k.key}>
                  {k.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Topic" hint="optional — a nakshatram, a festival, a myth">
            <input
              value={topic}
              placeholder="e.g. Vishu, Ashwathi"
              onChange={(e) => setTopic(e.target.value)}
            />
          </Field>
          <button
            className="btn btn--primary"
            disabled={generate.isPending}
            onClick={() => generate.mutate()}
          >
            {generate.isPending ? 'Writing…' : 'Generate'}
          </button>
        </div>
        <Problem error={generate.error} />
      </div>

      <Problem error={drafts.error} />
      {drafts.isLoading && <p className="empty">Loading…</p>}
      {!drafts.isLoading && !rows.length && (
        <p className="empty">No drafts yet. Generate one above.</p>
      )}

      {rows.map((draft) => (
        <DraftCard key={draft.id} draft={draft} />
      ))}
    </section>
  )
}
