import { useEffect, useRef, useState } from 'react'
import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { ApiError, apiPost } from '../../api/client'
import { useT } from '../../i18n'

// Nithara chat — talks to the SAME POST /chat/message brain the website and
// WhatsApp use. Identity comes from the bearer token, so an anonymous device
// session works; the reply is grounded in the caller's chart when one exists.

interface ChatResponse {
  reply: string
  is_safety_response: boolean
  suggestions: string[]
}

interface Bubble {
  role: 'me' | 'ai'
  text: string
  /** Marks the crisis-path pair so it is shown but never resent (see send()). */
  transient?: boolean
}

const conversationId = () => `nithara-${Date.now().toString(36)}`

export function ChatSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t: T, lang } = useT()
  const [bubbles, setBubbles] = useState<Bubble[]>([])
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const convo = useRef(conversationId())
  const bodyRef = useRef<HTMLDivElement>(null)

  const seed =
    lang === 'ml'
      ? 'നമസ്കാരം 🙏 ഞാൻ നിതാര. ജാതകം, ഇന്നത്തെ പഞ്ചാംഗം, നക്ഷത്രത്തിന് ചേരുന്ന ക്ഷേത്രം — എന്തും ചോദിക്കാം.'
      : 'Namaskaram 🙏 I am Nithara. Ask me about your chart, today’s panchangam, or which temple suits your nakshatram.'

  useEffect(() => {
    if (open && bubbles.length === 0) {
      // Displayed only — the model never produced this greeting, so it must not
      // be replayed to the API as an assistant turn.
      setBubbles([{ role: 'ai', text: seed, transient: true }])
      convo.current = conversationId()
    }
  }, [open])

  // Keep pinned to the newest message — including on reopen, when the sheet
  // remounts a fresh scroll container while the transcript state survives.
  useEffect(() => {
    if (!open) return
    bodyRef.current?.scrollTo({ top: bodyRef.current.scrollHeight })
  }, [bubbles, typing, open])

  async function send(text: string) {
    const content = text.trim()
    if (!content || typing) return
    setInput('')
    setSuggestions([])
    setError(null)
    const outgoing = { role: 'me' as const, text: content }
    setBubbles((prev) => [...prev, outgoing])
    setTyping(true)
    try {
      // GUARDRAILS §2: a crisis turn is deliberately NOT persisted server-side,
      // so it must not be replayed from the client either — resending it would
      // feed the distress text into the next turn's LLM prompt and durable
      // memory extraction. `transient` turns are shown, never sent.
      const sendable = [...bubbles.filter((b) => !b.transient), outgoing]
      const res = await apiPost<ChatResponse>('/chat/message', {
        messages: sendable.map((b) => ({
          role: b.role === 'me' ? 'user' : 'assistant',
          content: b.text,
        })),
        conversation_id: convo.current,
      })
      const crisis = res.is_safety_response
      if (crisis) {
        // Mark the whole exchange transient so it leaves the conversation.
        setBubbles((prev) =>
          prev.map((b) => (b === outgoing ? { ...b, transient: true } : b)).concat({
            role: 'ai',
            text: res.reply,
            transient: true,
          }),
        )
      } else {
        setBubbles((prev) => [...prev, { role: 'ai', text: res.reply }])
      }
      // Never decorate a safety reply with follow-up chips, even if the server
      // were to send some.
      setSuggestions(crisis ? [] : (res.suggestions ?? []))
    } catch (e) {
      // Drop the unsent bubble so the transcript doesn't gain two consecutive
      // user turns, and surface the real reason (e.g. the hourly rate limit).
      setBubbles((prev) => prev.filter((b) => b !== outgoing))
      setInput(content)
      setError(
        e instanceof ApiError && e.status === 429
          ? lang === 'ml'
            ? 'ഈ മണിക്കൂറിൽ ഒരുപാട് സന്ദേശങ്ങൾ — അൽപ്പം കഴിഞ്ഞ് ശ്രമിക്കൂ.'
            : 'Too many messages this hour — please take a short break.'
          : lang === 'ml'
            ? 'ക്ഷമിക്കണം — വീണ്ടും ശ്രമിക്കൂ.'
            : 'Sorry — that didn’t go through. Please try again.',
      )
    } finally {
      setTyping(false)
    }
  }

  return (
    <Sheet open={open} onClose={onClose}>
      <div className="chat" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        <div className="chtop">
          <button className="iconbtn" onClick={onClose} aria-label={T('a11yBack')}>
            <Icon name="i-back" />
          </button>
          <div className="av">
            <Icon name="i-sparkle" />
          </div>
          <div style={{ flex: 1 }}>
            <b>Nithara</b>
            <div className="st">
              <span className="dot" />
              {lang === 'ml' ? 'സൗജന്യം · എപ്പോഴും ലഭ്യം' : 'Free · always available'}
            </div>
          </div>
        </div>

        <div className="chbody" ref={bodyRef}>
          {bubbles.map((b, i) => (
            <div className={`bub ${b.role}`} key={i}>
              {b.text}
            </div>
          ))}
          {typing && (
            <div className="typing">
              <i />
              <i />
              <i />
            </div>
          )}
          {error && (
            <div className="bub ai" style={{ color: 'var(--kumkum)' }} role="alert">
              {error}
            </div>
          )}
        </div>

        {suggestions.length > 0 && (
          <div className="sugg">
            {suggestions.map((s) => (
              <button key={s} onClick={() => send(s)}>
                {s}
              </button>
            ))}
          </div>
        )}

        <p className="chdisc">
          {lang === 'ml'
            ? 'മാർഗനിർദേശം മാത്രം. വൈദ്യ, നിയമ, സാമ്പത്തിക കാര്യങ്ങൾക്ക് വിദഗ്ധരെ സമീപിക്കുക.'
            : 'Guidance only. For medical, legal or financial decisions, consult a professional.'}
        </p>

        <div className="chin">
          <div className="field">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                // Don't send mid-composition — Malayalam transliteration/IME
                // commits a candidate with Enter.
                if (e.key === 'Enter' && !e.nativeEvent.isComposing) send(input)
              }}
              placeholder={lang === 'ml' ? 'നിതാരയോട് ചോദിക്കൂ…' : 'Ask Nithara…'}
              aria-label="Message"
            />
          </div>
          <button className="snd" onClick={() => send(input)} disabled={typing} aria-label="Send">
            <Icon name="i-navigate" />
          </button>
        </div>
      </div>
    </Sheet>
  )
}
