import { useState } from 'react'
import { Icon } from '../components/Icon'
import { useT } from '../i18n'
import { setHomeTempleId, useHomeTempleId } from '../lib/homeTemple'
import { nakName } from '../lib/nakshatrams'
import { useBookings, useMembers, useMilestones, useStats, useTemple } from '../api/hooks'
import { MemberSheet } from '../features/member/MemberSheet'
import { SearchSheet } from '../features/temple/SearchSheet'
import { ChatSheet } from '../features/chat/ChatSheet'
import type { Member } from '../api/types'

// Badge icon + i18n label key per milestone key returned by /me/milestones.
// Without the label map the UI would render raw snake_case in both languages.
const MILESTONES: Record<string, { icon: string; label: string }> = {
  first_temple: { icon: 'i-temple', label: 'msFirstTemple' },
  ten_temples: { icon: 'i-shiva', label: 'msTenTemples' },
  first_pooja: { icon: 'i-lamp', label: 'msFirstPooja' },
  week_streak: { icon: 'i-star', label: 'msWeekStreak' },
  five_districts: { icon: 'i-pin', label: 'msFiveDistricts' },
}

export default function Profile() {
  const { t: T, lang } = useT()
  const homeId = useHomeTempleId()
  const temple = useTemple(homeId).data
  const { data: members = [] } = useMembers()
  const { data: stats } = useStats()
  const { data: milestones = [] } = useMilestones()
  const bookings = useBookings().data ?? []

  const [editing, setEditing] = useState<Member | 'new' | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  const self = members.find((m) => m.self)
  const templeName = temple ? (lang === 'ml' ? temple.ml : temple.en) : ''

  return (
    <section className="screen" data-active id="s-profile">
      <div className="phead2">
        <div className="eyebrow2">{T('profileWord')}</div>
        <div className="pcardhead">
          {temple && (
            <div className="pidrow">
              <span className="pav">
                <Icon name={`i-${temple.sig}`} />
              </span>
              <div className="pm">
                <div className="kk">
                  <Icon name="i-star" />
                  {T('yourTemple')}
                </div>
                <h1>{templeName}</h1>
                <div className="sub">
                  {lang === 'ml' ? temple.en : temple.ml} · {temple.place}
                </div>
              </div>
              <button className="chg" onClick={() => setSearchOpen(true)}>
                {T('changeTemple')}
              </button>
            </div>
          )}
          {stats && (
            <div className="pstatsrow">
              <div className="pstat2">
                <b>{stats.temples_visited}</b>
                <span>{T('stTemples')}</span>
              </div>
              <div className="pstat2">
                <b>{stats.poojas}</b>
                <span>{T('stPoojas')}</span>
              </div>
              <div className="pstat2">
                <b>{stats.streak}</b>
                <span>{T('stStreak')}</span>
              </div>
              <div className="pstat2">
                <b>{stats.badges}</b>
                <span>{T('stBadges')}</span>
              </div>
            </div>
          )}
        </div>
        <div className={`pnak ${self?.nak != null ? 'set' : ''}`}>
          <Icon name={self?.nak != null ? 'i-star' : 'i-sparkle'} />
          <span>{self?.nak != null ? nakName(self.nak, lang) : T('nakNotSet')}</span>
        </div>
      </div>

      {/* Birth chart. This build is anonymous-only and the chat brain has no
          chart-creation path (it only READS a chart), so we must not promise
          "three questions and Nithara builds your jathakam" — that CTA would be
          a dead end. We state the position plainly and offer what does work:
          setting your nakshatram, which really does personalise the app. */}
      <div className="pcard">
        <h2>{T('birthChart')}</h2>
        <div className="setup">
          <div className="si">
            <Icon name="i-sparkle" />
          </div>
          <div className="st">
            <b>{T('chartNotSet')}</b>
            <span>{T('chartComingSoon')}</span>
          </div>
        </div>
        <button
          className="btn btn-pri btn-block"
          disabled={!self}
          onClick={() => setEditing(self ?? 'new')}
        >
          <Icon name="i-star" cls="ic sm" />
          {T('setYourStar')}
        </button>
      </div>

      {/* Family board */}
      <div className="pcard">
        <h2>
          {T('family')}
          <button className="edit" onClick={() => setEditing('new')}>
            {T('addSomeone')}
          </button>
        </h2>
        {members.map((m) => (
          <button key={m.id} className="frow" style={{ width: '100%' }} onClick={() => setEditing(m)}>
            <span>{m.name || T('addYourName')}</span>
            <b>{m.nak != null ? nakName(m.nak, lang) : T('nakUnset')}</b>
          </button>
        ))}
      </div>

      {/* Bookings */}
      <div className="pcard">
        <h2>{T('bookings')}</h2>
        {bookings.length ? (
          bookings.map((b) => (
            <div className="booking" key={b.id}>
              <div className="bi">
                <Icon name="i-lamp" />
              </div>
              <div className="bm">
                <b>
                  {b.pooja_name}
                  {b.member_name ? ` · ${b.member_name}` : ''}
                </b>
                <span>{b.when}</span>
              </div>
              <span className={`pill ${b.state === 'ok' ? 'pill-open' : 'pill-def'}`}>
                <Icon name={b.state === 'ok' ? 'i-check' : 'i-clock'} />
                {T(b.state === 'ok' ? 'confirmed' : 'pending')}
              </span>
            </div>
          ))
        ) : (
          <div className="frow">
            <span>{T('noPast')}</span>
          </div>
        )}
      </div>

      {/* Milestones */}
      {milestones.length > 0 && (
        <div className="pcard">
          <h2>{T('milestones')}</h2>
          <div className="milestones">
            {milestones.map((m) => (
              <div className={`ms ${m.got ? 'got' : 'lock'}`} key={m.key}>
                <Icon name={MILESTONES[m.key]?.icon ?? 'i-star'} />
                <b>{MILESTONES[m.key] ? T(MILESTONES[m.key].label) : m.key.replace(/_/g, ' ')}</b>
                <span>
                  {m.current} / {m.target}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <MemberSheet editing={editing} onClose={() => setEditing(null)} />
      <SearchSheet
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onPick={(id) => {
          setHomeTempleId(id)
          setSearchOpen(false)
        }}
      />
      <ChatSheet open={chatOpen} onClose={() => setChatOpen(false)} />
    </section>
  )
}
