// The scheduled morning content pack: draft, review, publish.
//
// This screen replaces TWO independent implementations — admin.js:692-813 and
// console.html:286-340 — which drifted apart, as two implementations of one
// thing do. Only console.html had "mark posted by hand", which is the action
// that matters most, because three of the four platforms cannot be posted to
// automatically at all. That one is kept.
//
// The review step is the whole point of the pack. A generator writes the copy;
// a person decides whether it goes out under the product's name. So the text is
// editable at the moment of approval rather than in a separate edit mode — an
// operator who has to leave the queue to fix a word usually approves the word.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import {
  approvePost,
  listPosts,
  markPostPublished,
  publishPost,
  runDaily,
  type ContentPost,
} from '../../api/content'
import { integrationFlags } from '../../api/system'
import {
  platformLabel,
  postActions,
  postKindLabel,
  publishNote,
  runSummary,
  today,
  urlProblem,
} from '../../lib/content'
import { Field, Problem } from '../bits'

function StatusBadge({ status }: { status: string }) {
  const tone =
    status === 'published' ? ' badge--on' : status === 'failed' ? ' badge--off' : ''
  return <span className={`badge${tone}`}>{status}</span>
}

function PostCard({ post, whatsappLive }: { post: ContentPost; whatsappLive?: boolean }) {
  const queryClient = useQueryClient()
  const can = postActions(post.status)
  const [body, setBody] = useState(post.body)
  const [url, setUrl] = useState('')
  const [recording, setRecording] = useState(false)

  const done = () => queryClient.invalidateQueries({ queryKey: ['content', 'posts'] })
  // The edited text rides along with approval; unchanged text is not resent, so
  // an approval never overwrites a body somebody else corrected meanwhile.
  const approve = useMutation({
    mutationFn: () => approvePost(post.id, body === post.body ? undefined : body),
    onSuccess: done,
  })
  const publish = useMutation({ mutationFn: () => publishPost(post.id), onSuccess: done })
  const mark = useMutation({
    mutationFn: () => markPostPublished(post.id, url.trim()),
    onSuccess: async () => {
      await done()
      setRecording(false)
      setUrl('')
    },
  })

  const note = publishNote(post.platform, whatsappLive)
  const urlIssue = urlProblem(url)

  return (
    <article className="card">
      <div className="card__head">
        <h3 className="card__title">{platformLabel(post.platform)}</h3>
        <span className="badge">{postKindLabel(post.kind)}</span>
        <StatusBadge status={post.status} />
        <span className="cell__sub">{post.day}</span>
      </div>

      <textarea
        className="input--ml"
        lang="ml"
        spellCheck={false}
        rows={6}
        value={body}
        disabled={!can.approve}
        onChange={(e) => setBody(e.target.value)}
      />

      {post.media_url && (
        <p className="field__hint">
          <a href={post.media_url} target="_blank" rel="noreferrer">
            The rendered card ↗
          </a>
        </p>
      )}
      {post.external_id && (
        <p className="field__hint">
          Recorded as <code>{post.external_id}</code>
          {post.published_at ? ` on ${post.published_at.slice(0, 10)}` : ''}
        </p>
      )}

      <div className="row">
        {can.approve && (
          <button
            className="btn btn--primary"
            disabled={approve.isPending}
            onClick={() => approve.mutate()}
          >
            {post.status === 'failed'
              ? 'Approve again'
              : body === post.body
                ? 'Approve'
                : 'Save the edit and approve'}
          </button>
        )}
        {can.publish && (
          <button className="btn" disabled={publish.isPending} onClick={() => publish.mutate()}>
            Publish
          </button>
        )}
        {can.markPublished && !recording && (
          <button className="btn btn--ghost" onClick={() => setRecording(true)}>
            Mark posted by hand
          </button>
        )}
      </div>

      {can.publish && note && (
        <p className="banner banner--warn" role="status">
          {note}
        </p>
      )}
      {post.status === 'failed' && (
        <p className="field__hint">
          The publish attempt did not go through. Approving again puts it back in
          line for another try.
        </p>
      )}

      {recording && (
        <div className="row">
          <Field label="Where you posted it" hint="the public URL, so the record is checkable">
            <input
              value={url}
              placeholder="https://…"
              onChange={(e) => setUrl(e.target.value)}
            />
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

      <Problem error={approve.error ?? publish.error ?? mark.error} />
    </article>
  )
}

export function DailyPack() {
  const queryClient = useQueryClient()
  const [day, setDay] = useState('')
  const [filterDay, setFilterDay] = useState('')

  const posts = useQuery({
    queryKey: ['content', 'posts', filterDay],
    queryFn: () => listPosts(filterDay || undefined),
  })
  // Only for the honest publish label, and only the flags: a content_reviewer
  // has no business being handed the devotee count to read one boolean. Cached
  // hard because it changes on a redeploy, not between clicks.
  const system = useQuery({
    queryKey: ['integrations'],
    queryFn: integrationFlags,
    staleTime: 5 * 60 * 1000,
  })
  const whatsappLive = system.data?.integrations?.whatsapp

  const run = useMutation({
    mutationFn: () => runDaily(day || undefined),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['content', 'posts'] }),
  })

  const rows = posts.data ?? []

  return (
    <section className="page">
      <h1 className="page__title">Daily pack</h1>
      <p className="page__lede">
        One piece per platform, drafted each morning and held until somebody
        approves it.
      </p>

      <div className="card">
        <div className="row">
          <Field label="Day" hint="blank means today">
            <input type="date" value={day} onChange={(e) => setDay(e.target.value)} />
          </Field>
          <button
            className="btn btn--primary"
            disabled={run.isPending}
            onClick={() => run.mutate()}
          >
            {run.isPending ? 'Drafting…' : 'Draft the pack'}
          </button>
        </div>
        <p className="field__hint">
          The scheduler already does this every morning. Pressing it again is
          safe — a platform that already has a piece for the day is left alone.
        </p>
        {run.data && (
          <p className="banner banner--ok" role="status">
            {runSummary(run.data)}
          </p>
        )}
        <Problem error={run.error} />
      </div>

      <div className="toolbar">
        <label className="toolbar__field">
          <span>Show</span>
          <input
            type="date"
            value={filterDay}
            onChange={(e) => setFilterDay(e.target.value)}
          />
        </label>
        {filterDay && (
          <button className="btn btn--ghost" onClick={() => setFilterDay('')}>
            Every day
          </button>
        )}
        <button className="btn btn--ghost" onClick={() => setFilterDay(today())}>
          Today
        </button>
      </div>

      <Problem error={posts.error} />
      {posts.isLoading && <p className="empty">Loading…</p>}
      {!posts.isLoading && !rows.length && (
        <p className="empty">
          {filterDay
            ? `Nothing was drafted for ${filterDay}.`
            : 'No pieces yet. Draft the pack above.'}
        </p>
      )}

      {rows.map((post) => (
        <PostCard key={post.id} post={post} whatsappLive={whatsappLive} />
      ))}
    </section>
  )
}
