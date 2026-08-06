import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '../components/Icon'
import { toast } from '../components/Toast'
import { toggleLang, useT } from '../i18n'
import { clearHomeTempleCache, useHomeTempleId } from '../lib/homeTemple'
import { useFeed, useNearbyTemples, usePanchangam, useTemple, useTemplePoojas } from '../api/hooks'
import { TempleSheet } from '../features/temple/TempleSheet'
import { SearchSheet } from '../features/temple/SearchSheet'
import { MapCard, MapSheet } from '../features/temple/Map'
import { Onboarding } from '../features/onboarding/Onboarding'
import type { FeedItem, Temple } from '../api/types'

const money = (n: number) => '₹' + n.toLocaleString('en-IN')
const fmt = (k: number | null) => (k == null ? '' : k < 1 ? `${Math.round(k * 1000)} m` : `${k.toFixed(1)} km`)

export default function Home() {
  const homeId = useHomeTempleId()
  if (!homeId) return <Onboarding onDone={() => undefined} />
  return <HomeInner homeId={homeId} />
}

function HomeInner({ homeId }: { homeId: string }) {
  const { t: T, lang } = useT()
  const navigate = useNavigate()
  const [openId, setOpenId] = useState<string | null>(null)
  const [searchOpen, setSearchOpen] = useState(false)
  const [mapOpen, setMapOpen] = useState(false)

  const templeQuery = useTemple(homeId)
  const temple = templeQuery.data
  // If the saved home temple no longer resolves (data changed / migrated),
  // drop the local copy so onboarding runs again instead of showing an empty
  // hero. The account keeps its id: a temple pulled from the directory this
  // morning may be back this afternoon, and erasing somebody's choice over our
  // own data problem is worse than asking them once.
  useEffect(() => {
    if (templeQuery.isError) clearHomeTempleCache()
  }, [templeQuery.isError])
  const poojas = useTemplePoojas(homeId).data?.poojas ?? []
  const nearby = (useNearbyTemples().data ?? []).filter((t) => t.id !== homeId).slice(0, 3)
  const feed = useFeed().data ?? []
  const panchangam = usePanchangam().data

  const book = (key: string, amt: number) => toast(`${T('book')} · ${money(amt)}`)
  const today = new Date().toLocaleDateString(lang === 'ml' ? 'ml-IN' : 'en-IN', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  })

  return (
    <section className="screen" data-active id="s-home">
      <header className="hometop">
        <div className="brandrow">
          <span className="mark">
            <Icon name="i-lamp" />
          </span>
          <span className="wordmark">Nithara</span>
          <button className="iconbtn" onClick={() => setSearchOpen(true)} aria-label={T('searchPlaceholder')}>
            <Icon name="i-search" cls="ic sm" />
          </button>
          <button className="iconbtn lang" onClick={toggleLang} aria-label="Language">
            <Icon name="i-globe" cls="ic sm" />
            <b>{lang === 'en' ? 'ML' : 'EN'}</b>
          </button>
        </div>
        <div className="placerow">
          <button className="placechip" onClick={() => toast(T('locToast'))}>
            <Icon name="i-pin" />
            <span className="nm">Thrissur, Kerala</span>
            <Icon name="i-navigate" cls="cv" />
          </button>
          <span className="datechip">{today}</span>
        </div>
      </header>

      {panchangam && (
        <button className="panch" onClick={() => navigate('/astro')}>
          <span className="moon">
            <Icon name="i-moon" cls="ic sm" />
          </span>
          <span className="pt">
            <b>{panchangam.nakshatram}</b>
            <span>
              {panchangam.tithi} · {panchangam.nalla_neram}
            </span>
          </span>
          <Icon name="i-navigate" />
        </button>
      )}

      <div className="sec" data-sec="temple" style={{ marginTop: 'var(--s6)' }}>
        <h2>{T('secTempleHead')}</h2>
      </div>
      {temple && <MyTemple t={temple} T={T} lang={lang} onEnter={() => setOpenId(homeId)} onBook={book} />}

      {poojas.length > 0 && (
        <>
          <div className="sec" data-sec="poojas">
            <h2>{T('secPoojasToday')}</h2>
          </div>
          <div style={{ padding: '0 var(--s5)' }}>
            {poojas.slice(0, 2).map((p) => (
              <div className="pooja" key={p.key}>
                <div className="pi">
                  <Icon name="i-lamp" />
                </div>
                <div className="pm">
                  <b>{lang === 'ml' ? p.name_ml : p.name}</b>
                </div>
                <div className="price">{money(p.amount)}</div>
                <button className="btn btn-pri" onClick={() => book(p.key, p.amount)}>
                  {T('book')}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="sec" data-sec="nearby">
        <h2>{T('secNearbyHead')}</h2>
        <button className="more" onClick={() => setSearchOpen(true)}>
          <span>{T('seeAll')}</span>
          <Icon name="i-navigate" cls="ic sm" />
        </button>
      </div>
      <div>
        {nearby.map((x: Temple) => (
          <button className="tmini" key={x.id} onClick={() => setOpenId(x.id)}>
            <span className={`glyph ${x.sig}`}>
              <Icon name={`i-${x.sig}`} />
            </span>
            <span className="m">
              <b>{lang === 'ml' ? x.ml : x.en}</b>
              <span>
                {lang === 'ml' ? x.en : x.ml} · {x.place}
              </span>
            </span>
            <span className="d">{fmt(x.distance_km)}</span>
          </button>
        ))}
      </div>

      {feed.length > 0 && (
        <>
          <div className="sec" data-sec="notices">
            <h2>{T('secNotices')}</h2>
          </div>
          <div className="noticerail">
            {feed.map((a: FeedItem) => (
              <button
                key={a.id}
                className="notice"
                onClick={() => (a.temple_id ? setOpenId(a.temple_id) : undefined)}
              >
                <span className={`nimg ${a.image}`}>
                  <Icon name={a.glyph} />
                </span>
                <span className="nb">
                  <span className="cat">{a.cat}</span>
                  <h3>{lang === 'ml' ? a.title_ml : a.title_en}</h3>
                  <span className="who">
                    <Icon name="i-user" cls="ic sm" />
                    {lang === 'ml' ? a.who_ml : a.who_en}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </>
      )}

      <div className="sec" data-sec="map">
        <h2>{T('secMapHead')}</h2>
      </div>
      <MapCard homeId={homeId} onOpenFull={() => setMapOpen(true)} />

      <TempleSheet id={openId} isHome={openId === homeId} onClose={() => setOpenId(null)} onBook={book} />
      <SearchSheet open={searchOpen} onClose={() => setSearchOpen(false)} onPick={setOpenId} />
      <MapSheet open={mapOpen} homeId={homeId} onClose={() => setMapOpen(false)} onPick={(id) => { setMapOpen(false); setTimeout(() => setOpenId(id), 260) }} />
    </section>
  )
}

function MyTemple({
  t,
  T,
  lang,
  onEnter,
  onBook,
}: {
  t: Temple
  T: (k: string) => string
  lang: string
  onEnter: () => void
  onBook: (key: string, amt: number) => void
}) {
  const name = lang === 'ml' ? t.ml : t.en
  const name2 = lang === 'ml' ? t.en : t.ml
  return (
    <div className="mytemple" style={{ margin: '0 var(--s5)' }}>
      <div className="mt-thread" />
      <div className="mt-head">
        <span className="mt-glyph">
          <Icon name={`i-${t.sig}`} />
        </span>
        <div style={{ minWidth: 0 }}>
          <div className="mt-badge">
            <Icon name="i-star" />
            {T('yourTemple')}
          </div>
          <div className="mt-name">{name}</div>
          <div className="mt-ml">
            {name2} · {t.place}
          </div>
          {t.rating && (
            <div className="mt-rate">
              <Icon name="i-star" cls="ic sm" />
              <b>{t.rating}</b>
              <span>
                {t.reviews} {T('reviews')}
              </span>
            </div>
          )}
        </div>
      </div>
      <div className="mt-pills">
        {t.open ? (
          <span className="pill pill-open">
            <Icon name="i-clock" />
            {T('openTill')} {t.closes}
          </span>
        ) : (
          <span className="pill pill-shut">
            <Icon name="i-clock" />
            {T('closedNow')}
          </span>
        )}
        <span className="pill pill-dist">
          <Icon name="i-pin" />
          {fmt(t.distance_km)}
        </span>
        {t.pooja && (
          <span className="pill pill-pooja">
            <Icon name="i-lamp" />
            {T('poojaToday')}
          </span>
        )}
      </div>
      <div className="mt-cta">
        <button className="enter" onClick={onEnter}>
          <Icon name="i-temple" cls="ic sm" />
          {T('enterTemple')}
        </button>
        <button className="btn btn-sec" onClick={() => toast(`${T('openingDir')} ${name}`)}>
          <Icon name="i-navigate" cls="ic sm" />
        </button>
      </div>
      <div className="mt-quick">
        <button onClick={() => onBook('pushpanjali', 101)}>
          <Icon name="i-lamp" />
          {T('bookPooja')}
        </button>
        <button onClick={() => toast(T('darshanRecorded'))}>
          <Icon name="i-check" />
          {T('checkIn')}
        </button>
      </div>
    </div>
  )
}
