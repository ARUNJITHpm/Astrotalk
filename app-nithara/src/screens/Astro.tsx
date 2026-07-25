import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Icon } from '../components/Icon'
import { useT } from '../i18n'
import { apiGet, qs } from '../api/client'
import { useMembers } from '../api/hooks'
import { nakName } from '../lib/nakshatrams'
import { ChatSheet } from '../features/chat/ChatSheet'
import { MuhurthamSheet, PoruthamSheet } from '../features/astro/ToolSheets'
import { MemberSheet } from '../features/member/MemberSheet'
import type { Member, Today } from '../api/types'

export default function Astro() {
  const { t: T, lang } = useT()
  const [chatOpen, setChatOpen] = useState(false)
  const [poruthamOpen, setPoruthamOpen] = useState(false)
  const [muhurthamOpen, setMuhurthamOpen] = useState(false)
  const [editing, setEditing] = useState<Member | 'new' | null>(null)

  const { data: members = [], isSuccess: membersLoaded } = useMembers()
  const self = members.find((m) => m.self)
  const myNak = self?.nak ?? null

  // "Today" is personalised to the caller's OWN nakshatram when known — never a
  // placeholder star. Wait for members before asking, otherwise the first render
  // (myNak still null) both fires a wasted request and flashes "add your
  // nakshatram" at users who have one.
  const { data: today } = useQuery({
    queryKey: ['today', myNak],
    queryFn: () => apiGet<Today>('/astrology/today' + qs({ nak: myNak ?? undefined })),
    enabled: membersLoaded,
  })

  return (
    <section className="screen" data-active id="s-astro">
      <header className="top">
        <div className="g">
          <div className="hi ml">{T('astroSub')}</div>
          <div className="nm">{T('astroTitle')}</div>
        </div>
      </header>

      {/* Nithara — the same chat brain as the website and WhatsApp */}
      <div className="nithara">
        <div className="stars" aria-hidden="true" />
        <div className="r">
          <div className="av">
            <Icon name="i-sparkle" cls="ic lg" />
          </div>
          <div>
            <b>
              Nithara <span className="free">{T('free')}</span>
            </b>
          </div>
        </div>
        <p>{T('nitharaBlurb')}</p>
        <button className="btn go" onClick={() => setChatOpen(true)}>
          <Icon name="i-sparkle" cls="ic sm" />
          {T('chatNithara')}
        </button>
      </div>

      {/* Today, personalised to the caller's own star when it is known */}
      {today && (
        <div className="today">
          <div className="th">
            <div className="ni">
              <Icon name="i-moon" />
            </div>
            <div>
              <b>
                {today.is_star_day
                  ? T('isStarDay')
                  : myNak != null
                    ? `${T('yourStar')} · ${nakName(myNak, lang)}`
                    : T('todayHead')}
              </b>
              <span>
                {today.date} · {today.tithi}
              </span>
            </div>
          </div>
          <p>{today.note}</p>
          {myNak == null && (
            <button
              className="btn btn-sec btn-block"
              style={{ marginTop: 12 }}
              onClick={() => setEditing(self ?? 'new')}
            >
              {T('starNotSetYet')}
            </button>
          )}
        </div>
      )}

      {/* Free tools */}
      <div className="sec">
        <h2>{T('secTools')}</h2>
      </div>
      <div className="tools" id="tools">
        <button className="tool" onClick={() => setChatOpen(true)}>
          <span className="ti">
            <Icon name="i-sparkle" />
          </span>
          <b>{T('tJathakam')}</b>
          <span>{T('tJathakamS')}</span>
        </button>
        <button className="tool blue" onClick={() => setPoruthamOpen(true)}>
          <span className="ti">
            <Icon name="i-heart" />
          </span>
          <b>{T('tPorutham')}</b>
          <span>{T('tPoruthamS')}</span>
        </button>
        <button className="tool slate" onClick={() => setMuhurthamOpen(true)}>
          <span className="ti">
            <Icon name="i-clock" />
          </span>
          <b>{T('tMuhurtham')}</b>
          <span>{T('tMuhurthamS')}</span>
        </button>
      </div>
      <div className="toolnote">
        <span className="free2">{T('allFree')}</span>
        <span>{T('toolNote')}</span>
      </div>

      {/* Astrologers — intentionally NOT rendered yet. The directory is still
          placeholder data (names are machine slugs like "thrissur-astro-1" and
          the ratings/experience are computed, see astrologers/seed_data.py
          "⚠️ DUMMY DATA"). Showing those as real practitioners with real
          ratings would be fabricated social proof (GUARDRAILS §1). This block
          returns once real, consented practitioners exist. */}

      <ChatSheet open={chatOpen} onClose={() => setChatOpen(false)} />
      <PoruthamSheet open={poruthamOpen} onClose={() => setPoruthamOpen(false)} />
      <MuhurthamSheet open={muhurthamOpen} onClose={() => setMuhurthamOpen(false)} />
      <MemberSheet editing={editing} onClose={() => setEditing(null)} />
    </section>
  )
}
