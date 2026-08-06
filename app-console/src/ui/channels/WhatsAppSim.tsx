// The WhatsApp simulator, as a first-class console page.
//
// Ported from app/web/whatsapp.html, which the old console linked out to. Until
// the Cloud API send timeout is fixed this simulator IS our WhatsApp surface,
// and a surface you leave the tool to reach is one nobody checks.
//
// It looks like WhatsApp on purpose. The thing being tested is what a devotee
// sees on a phone — line breaks, bubble width, whether a reply is a wall of
// text — and none of that is visible in a JSON pane.
//
// Two things carried over unchanged from the original page:
//   * the **sender switcher**, because a WhatsApp identity IS a phone number
//     and a new number is a new user with a fresh onboarding;
//   * the **Tele-MANAS line**, because the note explaining what this screen is
//     is also the only place the helpline appears on it.
//
// One thing deliberately dropped: the admin-token box. The operator is already
// signed in, and a second credential typed into a page is a credential that
// ends up in localStorage.

import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { simulate } from '../../api/channels'
import { clockStamp, normalizePhone, phoneProblem } from '../../lib/channels'
import { Problem } from '../bits'

interface Bubble {
  side: 'in' | 'out'
  text: string
  at: string
}

const STORAGE_KEY = 'nithara.console.sim.phone'

export function WhatsAppSim() {
  const [phone, setPhone] = useState<string>(
    () => localStorage.getItem(STORAGE_KEY) ?? '',
  )
  const [draft, setDraft] = useState('')
  const [bubbles, setBubbles] = useState<Bubble[]>([])
  const [switching, setSwitching] = useState(!phone)
  const [pendingPhone, setPendingPhone] = useState(phone)
  const chatRef = useRef<HTMLDivElement>(null)

  const send = useMutation({
    mutationFn: (text: string) => simulate(phone, text),
    onSuccess: (data) =>
      setBubbles((prev) => [...prev, { side: 'in', text: data.reply, at: clockStamp() }]),
  })

  // Follow the conversation down as it grows, including while "typing…" shows.
  useEffect(() => {
    const el = chatRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [bubbles, send.isPending])

  const submit = () => {
    const text = draft.trim()
    if (!text || !phone || send.isPending) return
    setBubbles((prev) => [...prev, { side: 'out', text, at: clockStamp() }])
    setDraft('')
    send.mutate(text)
  }

  const acceptNumber = () => {
    const next = normalizePhone(pendingPhone)
    if (phoneProblem(next)) return
    if (next !== phone) {
      // A different number is a different person. The server keeps its own
      // state per phone, so clearing the transcript here only stops one
      // conversation being read as the continuation of another.
      setBubbles([])
      send.reset()
    }
    setPhone(next)
    localStorage.setItem(STORAGE_KEY, next)
    setSwitching(false)
  }

  const numberIssue = phoneProblem(pendingPhone)

  return (
    <section className="page">
      <h1 className="page__title">WhatsApp simulator</h1>
      <p className="page__lede">
        The same brain the real WhatsApp webhook uses — onboarding, registration
        and chat — with the reply shown here instead of sent.
      </p>

      <p className="banner banner--warn" role="note">
        Whatever you type here reaches the live conversation state for this
        number. Use a test number: sending as a real devotee's mobile moves
        their onboarding along as if they had written in themselves.
      </p>

      <div className="wa">
        <header className="wa__head">
          <span className="wa__avatar" aria-hidden="true">
            ✦
          </span>
          <span className="wa__meta">
            <span className="wa__name">Tara · താര</span>
            <span className="wa__status">
              {send.isPending ? 'typing…' : phone ? `as ${phone}` : 'no number'}
            </span>
          </span>
          <button
            className="wa__switch"
            onClick={() => {
              setPendingPhone(phone)
              setSwitching(true)
            }}
          >
            Change number
          </button>
        </header>

        <div className="wa__chat" ref={chatRef}>
          <p className="wa__day">Today</p>
          <p className="wa__note">
            A simulator of the real WhatsApp flow, onboarding included — the same
            brain writes the replies. Tara is an AI, for guidance only. In an
            emergency: Tele-MANAS 14416.
          </p>

          {bubbles.map((b, i) => (
            <div key={i} className={`wa__bubble wa__bubble--${b.side}`}>
              <span className="wa__txt">{b.text}</span>
              <span className="wa__stamp">
                {b.at}
                {b.side === 'out' && (
                  <span className="wa__tick" aria-hidden="true">
                    ✓✓
                  </span>
                )}
              </span>
            </div>
          ))}

          {send.isPending && (
            <div className="wa__bubble wa__bubble--in" role="status" aria-label="Tara is typing">
              <span className="wa__typing">
                <span />
                <span />
                <span />
              </span>
            </div>
          )}
        </div>

        <div className="wa__composer">
          <textarea
            className="wa__input"
            lang="ml"
            spellCheck={false}
            rows={1}
            placeholder={phone ? 'Message' : 'Choose a number first'}
            value={draft}
            disabled={!phone}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
          />
          <button
            className="wa__send"
            aria-label="Send"
            disabled={!phone || send.isPending || !draft.trim()}
            onClick={submit}
          >
            ➤
          </button>
        </div>

        {switching && (
          <div className="wa__gate">
            <div className="wa__gatecard">
              <h2>Send as which number?</h2>
              <p>
                A WhatsApp identity is a phone number. A number that has never
                written in starts at the very beginning of onboarding.
              </p>
              <input
                type="tel"
                value={pendingPhone}
                placeholder="+91 98765 43210"
                autoFocus
                onChange={(e) => setPendingPhone(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    acceptNumber()
                  }
                }}
              />
              <p className="wa__gateerr">{pendingPhone.trim() ? numberIssue : ''}</p>
              <button className="btn btn--primary" disabled={!!numberIssue} onClick={acceptNumber}>
                Use this number
              </button>
              {phone && (
                <button className="btn btn--ghost" onClick={() => setSwitching(false)}>
                  Cancel
                </button>
              )}
            </div>
          </div>
        )}
      </div>

      <Problem error={send.error} />
    </section>
  )
}
