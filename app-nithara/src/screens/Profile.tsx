import { useState } from 'react'
import { Icon } from '../components/Icon'
import { useT } from '../i18n'
import { setHomeTempleId, useHomeTempleId } from '../lib/homeTemple'
import { nakName } from '../lib/nakshatrams'
import {
  useBirthDetails,
  useBookings,
  useChart,
  useMembers,
  useMilestones,
  useStats,
  useTemple,
} from '../api/hooks'
import { apiPost } from '../api/client'
import { MemberSheet } from '../features/member/MemberSheet'
import { SearchSheet } from '../features/temple/SearchSheet'
import { ChatSheet } from '../features/chat/ChatSheet'
import { BirthDetailsSheet } from '../features/profile/BirthDetailsSheet'
import { ChartCard } from '../features/profile/ChartCard'
import type { Member, ShareCard } from '../api/types'
import type { NatalChart } from '../lib/chart'

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
  const { data: chart } = useChart()
  const [editingBirth, setEditingBirth] = useState(false)
  const [sharing, setSharing] = useState(false)
  // Only fetched while the sheet is open — birth data should not sit in a query
  // cache on a screen that does not need it.
  const { data: birth } = useBirthDetails(editingBirth)
  const bookings = useBookings().data ?? []

  const [editing, setEditing] = useState<Member | 'new' | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  const self = members.find((m) => m.self)
  const templeName = temple ? (lang === 'ml' ? temple.ml : temple.en) : ''

  /**
   * Share the reading, not the birth data.
   *
   * The card lands on a PUBLIC /s/ page, so what goes on it is deliberately the
   * two facts a person volunteers about themselves — janma nakshatram and rasi
   * — and never the date, time or place of birth. Those three are what a chart
   * is recomputed from; putting them on a shareable image would hand anyone who
   * saw it the whole jathakam.
   */
  async function shareChart() {
    const natal = chart?.natal_json as NatalChart | undefined
    if (!natal) return
    setSharing(true)
    try {
      const parts = [
        natal.nakshatram ? `${T('yourStar')}: ${natal.nakshatram}` : '',
        natal.rasi ? `${T('rasiWord')}: ${natal.rasi}` : '',
      ].filter(Boolean)
      const card = await apiPost<ShareCard>('/content/cards', {
        title: T('myJathakam'),
        body: parts.join('\n'),
        template: 'story',
      })
      if (navigator.share) {
        await navigator.share({ title: T('myJathakam'), url: card.share_url })
      } else {
        await navigator.clipboard?.writeText(card.share_url)
      }
    } catch {
      // Sharing is an extra, never a step in anything. A failure here leaves the
      // chart exactly as it was, so there is nothing to roll back and nothing
      // the person needs to do differently.
    } finally {
      setSharing(false)
    }
  }

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

      {/* Birth chart. The CTA used to offer only "set your nakshatram", because
          an anonymous account had no way to create a chart — the signup form was
          the only writer of birth details and an anon account never sees it.
          PUT /identity/me/birth closed that, so the offer is now the real one. */}
      {chart ? (
        <ChartCard
          chart={chart.natal_json as NatalChart}
          onEdit={() => setEditingBirth(true)}
          onShare={shareChart}
          sharing={sharing}
        />
      ) : (
        <div className="pcard">
          <h2>{T('birthChart')}</h2>
          <div className="setup">
            <div className="si">
              <Icon name="i-sparkle" />
            </div>
            <div className="st">
              <b>{T('chartNotSet')}</b>
              <span>{T('chartSetupBlurb')}</span>
            </div>
          </div>
          <button className="btn btn-pri btn-block" onClick={() => setEditingBirth(true)}>
            <Icon name="i-star" cls="ic sm" />
            {T('computeChart')}
          </button>
        </div>
      )}

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

      <BirthDetailsSheet
        open={editingBirth}
        initial={
          birth
            ? {
                dob: birth.dob ?? '',
                birth_time: birth.birth_time?.slice(0, 5) ?? '',
                birth_place: birth.birth_place ?? '',
              }
            : undefined
        }
        onClose={() => setEditingBirth(false)}
      />

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
