// Read-only chat history, for support.
//
// Somebody rings and says "Tara told my mother something about her health and
// now she's frightened". Answering that means reading what was actually said,
// and until now it meant reading the database.
//
// Read-only, and there is no reply box. A support operator's job is to find out
// what happened, not to speak as the product to a devotee who thinks they are
// talking to it — and the moment a console can post into someone's conversation
// the transcript stops being evidence of anything.
//
// The turn is shown as the model saw it: the messages that went in, the reply
// that came out. That ordering is what makes "why did it say that" answerable.

import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { chatHistory, chatUsers } from '../../api/system'
import { whenStamp } from '../../lib/booking'
import { Problem } from '../bits'

function Turn({
  turn,
}: {
  turn: {
    messages: { role: string; content: string }[]
    reply: string
    created_at: string
    llm_provider: string | null
    llm_model: string | null
    total_tokens: number | null
  }
}) {
  // The stored request carries the whole prompt — system persona, retrieved
  // context, prior turns. Only the user's own last message belongs on screen:
  // the rest is ours, it is long, and it buries the thing being looked for.
  const asked = [...turn.messages].reverse().find((m) => m.role === 'user')

  return (
    <article className="card">
      <div className="card__head">
        <span className="cell__sub">{whenStamp(turn.created_at)}</span>
        {turn.llm_model && <span className="badge">{turn.llm_model}</span>}
        {turn.total_tokens != null && (
          <span className="cell__sub">{turn.total_tokens} tokens</span>
        )}
      </div>
      <div className="snippet">
        <p className="field__hint">They wrote</p>
        <p lang="ml">{asked?.content ?? '—'}</p>
      </div>
      <div className="snippet">
        <p className="field__hint">Tara replied</p>
        <p lang="ml">{turn.reply}</p>
      </div>
    </article>
  )
}

export function ChatExplorer() {
  const [phone, setPhone] = useState<string | null>(null)
  const [q, setQ] = useState('')

  const users = useQuery({ queryKey: ['chat-users'], queryFn: chatUsers })
  const history = useQuery({
    queryKey: ['chat-history', phone],
    queryFn: () => chatHistory(phone as string),
    enabled: phone !== null,
  })

  const needle = q.trim().toLowerCase()
  const rows = (users.data ?? []).filter(
    (u) =>
      !needle ||
      u.name.toLowerCase().includes(needle) ||
      u.phone.toLowerCase().includes(needle),
  )

  return (
    <section className="page">
      <h1 className="page__title">Chat explorer</h1>
      <p className="page__lede">
        What a devotee asked and what Tara answered. Read-only — nothing here
        writes back into their conversation.
      </p>

      <div className="toolbar">
        <label className="toolbar__field toolbar__field--grow">
          <span>Find</span>
          <input
            value={q}
            placeholder="name or mobile"
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
      </div>

      <Problem error={users.error} />
      {users.isLoading && <p className="empty">Loading…</p>}
      {!users.isLoading && !rows.length && (
        <p className="empty">
          {needle ? 'Nobody matches that.' : 'Nobody has a stored conversation yet.'}
        </p>
      )}

      {rows.length > 0 && (
        <div className="tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th>Who</th>
                <th>Mobile</th>
                <th>Turns</th>
                <th>Last wrote</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.phone} className={u.phone === phone ? 'row--window' : undefined}>
                  <td>{u.name}</td>
                  <td>{u.phone}</td>
                  <td className="num">{u.turns}</td>
                  <td>{u.last_active ? whenStamp(u.last_active) : '—'}</td>
                  <td className="cell__acts">
                    <button className="btn" onClick={() => setPhone(u.phone)}>
                      Read
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {phone && (
        <>
          <h2 className="section__title">{phone}</h2>
          <p className="field__hint">
            Newest first, up to the last hundred turns.
          </p>
          <Problem error={history.error} />
          {history.isLoading && <p className="empty">Loading…</p>}
          {history.data?.length === 0 && (
            <p className="empty">
              Nothing stored for this number. The list counts turns the chat
              store knows about, so a gap here usually means the store was
              mocked when they wrote in.
            </p>
          )}
          {history.data?.map((turn, i) => <Turn key={i} turn={turn} />)}
        </>
      )}
    </section>
  )
}
