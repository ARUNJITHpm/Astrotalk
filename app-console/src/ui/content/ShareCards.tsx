// The public daily nakshatram cards — what people actually forward.
//
// The star is picked from a list rather than typed. The endpoint takes a name
// or an index and 404s on anything else, and "Thiruvonam" has enough plausible
// spellings that a text box would mostly produce errors. Sending the **index**
// also sidesteps the transliteration question entirely.
//
// One card per (day, star), created on first request and then served from the
// same row, so opening this page is not generating anything new — it is looking
// at what the app and the WhatsApp Status already point at.

import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'

import { dailyCard, type ShareCard } from '../../api/content'
import { NAKSHATRAMS } from '../../lib/nakshatrams'
import { Field, Problem } from '../bits'

export function ShareCards() {
  const [index, setIndex] = useState('0')
  const [card, setCard] = useState<ShareCard | null>(null)
  const [copied, setCopied] = useState(false)

  const fetchCard = useMutation({
    mutationFn: () => dailyCard(index),
    onSuccess: (data) => {
      setCard(data)
      setCopied(false)
    },
  })

  const copy = async () => {
    if (!card) return
    try {
      await navigator.clipboard.writeText(card.share_url)
      setCopied(true)
    } catch {
      // Clipboard access can be refused outright; the URL is on screen and
      // selectable either way, so this is not worth an error banner.
    }
  }

  return (
    <section className="page">
      <h1 className="page__title">Share cards</h1>
      <p className="page__lede">
        The branded daily card for one nakshatram, and the public page a shared
        link lands on.
      </p>

      <div className="card">
        <div className="row">
          <Field label="Nakshatram">
            <select value={index} onChange={(e) => setIndex(e.target.value)}>
              {NAKSHATRAMS.map(([en, ml], i) => (
                <option key={en} value={String(i)}>
                  {en} · {ml}
                </option>
              ))}
            </select>
          </Field>
          <button
            className="btn btn--primary"
            disabled={fetchCard.isPending}
            onClick={() => fetchCard.mutate()}
          >
            {fetchCard.isPending ? 'Rendering…' : 'Show the card'}
          </button>
        </div>
        <p className="field__hint">
          One card exists per star per day. Asking for today's again returns the
          same image and the same link, so a card already shared does not change
          underneath the people who have it.
        </p>
        <Problem error={fetchCard.error} />
      </div>

      {card && (
        <div className="card">
          <div className="card__head">
            <h3 className="card__title">{card.title || card.slug}</h3>
            <span className="badge">{card.hits} opens</span>
          </div>
          <img className="photo" src={card.media_url} alt={`Daily card — ${card.title}`} />
          <div className="deftrow">
            <span className="deftrow__label">Share link</span>
            <span className="deftrow__value">
              <a href={card.share_url} target="_blank" rel="noreferrer">
                {card.share_url}
              </a>
            </span>
          </div>
          <div className="row">
            <button className="btn" onClick={copy}>
              {copied ? 'Copied' : 'Copy the link'}
            </button>
          </div>
          <p className="field__hint">
            The count is real opens of the landing page. It is not a like, a
            follower or a reach figure — the product does not have those and will
            not display numbers it cannot stand behind.
          </p>
        </div>
      )}
    </section>
  )
}
