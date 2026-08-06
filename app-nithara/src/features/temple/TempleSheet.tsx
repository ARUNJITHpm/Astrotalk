import { useEffect, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Sheet } from '../../components/Sheet'
import { Doors } from '../../components/Doors'
import { Icon } from '../../components/Icon'
import { toast } from '../../components/Toast'
import { apiPost } from '../../api/client'
import { useTemple } from '../../api/hooks'
import { openDirections } from '../../lib/directions'
import { useT } from '../../i18n'
import type { CheckinResult, PoojaCatalogueItem, TempleDetail } from '../../api/types'

const money = (n: number) => '₹' + n.toLocaleString('en-IN')

/**
 * Record a darshan.
 *
 * This button raised a toast saying "darshan recorded" and recorded nothing.
 * POST /temples/{id}/checkin has existed since Part 2 and the entire
 * streak/badges/temples-visited system is fed by it, so every one of those
 * figures has been counting an event the app never created.
 *
 * The server is idempotent per day, and `fresh` says which happened — so a
 * second visit on the same day is acknowledged honestly rather than claiming a
 * new one.
 */
function useCheckin(templeId: string, T: (k: string) => string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiPost<CheckinResult>(`/temples/${templeId}/checkin`, {}),
    onSuccess: (result) => {
      toast(result.fresh ? T('darshanRecorded') : T('darshanAlready'))
      qc.invalidateQueries({ queryKey: ['stats'] })
      qc.invalidateQueries({ queryKey: ['milestones'] })
    },
    onError: () => toast(T('darshanFailed')),
  })
}

type Tab = 'about' | 'timings' | 'poojas'

export function TempleSheet({
  id,
  isHome,
  onClose,
  onBook,
}: {
  id: string | null
  isHome: boolean
  onClose: () => void
  onBook: (poojaKey: string, amountRupees: number) => void
}) {
  const { t: T, lang } = useT()
  // Retain the last opened id so the temple content stays rendered through the
  // ~460ms slide-out (when `id` flips to null on close) instead of blanking.
  const [shownId, setShownId] = useState<string | null>(id)
  const { data, isLoading } = useTemple(shownId)
  const [tab, setTab] = useState<Tab>('about')
  const [doors, setDoors] = useState(false)

  useEffect(() => {
    if (id) {
      setShownId(id)
      setTab('about')
      setDoors(true)
    }
  }, [id])

  return (
    <>
      <Doors run={doors} onDone={() => setDoors(false)} />
      <Sheet open={!!id} onClose={onClose} dir="right">
        {data ? (
          <TempleBody t={data} isHome={isHome} tab={tab} setTab={setTab} T={T} lang={lang} onClose={onClose} onBook={onBook} />
        ) : (
          <div className="sheet-scroll" style={{ padding: 24 }}>{isLoading ? '…' : ''}</div>
        )}
      </Sheet>
    </>
  )
}

function TempleBody({
  t,
  isHome,
  tab,
  setTab,
  T,
  lang,
  onClose,
  onBook,
}: {
  t: TempleDetail
  isHome: boolean
  tab: Tab
  setTab: (tab: Tab) => void
  T: (k: string) => string
  lang: string
  onClose: () => void
  onBook: (poojaKey: string, amountRupees: number) => void
}) {
  const name = lang === 'ml' ? t.ml : t.en
  const name2 = lang === 'ml' ? t.en : t.ml
  const checkin = useCheckin(t.id, T)
  const place = t.mplace && lang === 'ml' ? t.mplace : t.place
  const story = lang === 'ml' && t.story_ml ? t.story_ml : t.story
  const fmt = (k: number | null) => (k == null ? '' : k < 1 ? `${Math.round(k * 1000)} m` : `${k.toFixed(1)} km`)

  return (
    <div className="sheet-scroll">
      <header className={`dhero ${isHome ? 'is-def' : ''}`}>
        <div className="wash" />
        <Icon name="i-gopuram" cls="silh" />
        <div className="navr">
          <button className="iconbtn" onClick={onClose} aria-label={T('a11yBack')}>
            <Icon name="i-back" />
          </button>
          <button className="iconbtn" onClick={() => toast(T(isHome ? 'isHome' : 'savedTemple'))} aria-label={T('savedTemple')}>
            <Icon name="i-star" />
          </button>
        </div>
        <div className="dtitle">
          <div className="k">
            {isHome ? T('yourTemple') + ' · ' : ''}
            {T('k' + t.deity) === 'k' + t.deity ? t.deity : T('k' + t.deity)}
          </div>
          <h1>{name}</h1>
          <div className="ml">
            {name2} · {place}
          </div>
        </div>
      </header>

      <div className="statrow">
        <div className="stat">
          <b>{fmt(t.distance_km)}</b>
          <span>{T('away')}</span>
        </div>
        <div className="stat">
          <b style={{ color: t.open ? 'var(--blue-700)' : 'var(--kumkum)' }}>{t.open ? T('openW') : T('closedW')}</b>
          <span>{t.open ? `${T('till')} ${t.closes}` : T('opens5')}</span>
        </div>
        <div className="stat">
          <b>
            <Icon name="i-star" cls="ic sm" /> {t.rating ?? '—'}
          </b>
          <span>{t.reviews ?? ''}</span>
        </div>
      </div>

      <div className="dtabs">
        {(['about', 'timings', 'poojas'] as Tab[]).map((key) => (
          <button key={key} aria-selected={tab === key} onClick={() => setTab(key)}>
            {T(key === 'about' ? 'about' : key === 'timings' ? 'timings' : 'poojas')}
          </button>
        ))}
      </div>

      {tab === 'about' && (
        <div className="block">
          <h3>{T('about')}</h3>
          <p className="prose">{story}</p>
        </div>
      )}

      {tab === 'timings' && (
        <div className="block">
          <h3>{T('darshanTimings')}</h3>
          <div className="timings">
            <div className="trow">
              <span>
                <Icon name="i-lamp" cls="ic sm" /> {T('nirmalyam')}
              </span>
              <b>{t.timings.nirmalyam}</b>
            </div>
            <div className="trow">
              <span>{T('morning')}</span>
              <b>{t.timings.morning}</b>
            </div>
            <div className="trow">
              <span>{T('evening')}</span>
              <b>{t.timings.evening}</b>
            </div>
          </div>
        </div>
      )}

      {tab === 'poojas' && (
        <div className="block">
          <h3>{T('bookAPooja')}</h3>
          {t.poojas.map((p: PoojaCatalogueItem) => (
            <div className="pooja" key={p.key}>
              <div className="pi">
                <Icon name="i-lamp" />
              </div>
              <div className="pm">
                <b>{lang === 'ml' ? p.name_ml : p.name}</b>
              </div>
              <div className="price">{money(p.amount)}</div>
              <button className="btn btn-pri" onClick={() => onBook(p.key, p.amount)}>
                {T('book')}
              </button>
            </div>
          ))}
        </div>
      )}

      <div style={{ height: 22 }} />
      <div className="dcta">
        <button
          className="btn btn-pri"
          disabled={checkin.isPending}
          onClick={() => checkin.mutate()}
        >
          {T('checkinDarshan')}
        </button>
        <button
          className="btn btn-nav"
          aria-label={T('directions')}
          onClick={() => {
            if (!openDirections({ lat: t.lat, lng: t.lng, name })) toast(T('dirFailed'))
          }}
        >
          <Icon name="i-navigate" cls="ic sm" />
        </button>
      </div>
    </div>
  )
}
