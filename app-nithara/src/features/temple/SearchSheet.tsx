import { useEffect, useState } from 'react'
import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { DEFAULT_LOC, useTemples } from '../../api/hooks'
import { useT } from '../../i18n'

const fmt = (k: number | null) => (k == null ? '' : k < 1 ? `${Math.round(k * 1000)} m` : `${k.toFixed(1)} km`)

export function SearchSheet({
  open,
  onClose,
  onPick,
}: {
  open: boolean
  onClose: () => void
  onPick: (id: string) => void
}) {
  const { t: T, lang } = useT()
  const [mode, setMode] = useState<'name' | 'place'>('name')
  const [q, setQ] = useState('')
  const [debounced, setDebounced] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebounced(q.trim()), 250)
    return () => clearTimeout(t)
  }, [q])
  const { data = [] } = useTemples({
    q: debounced || undefined,
    by: mode,
    lat: DEFAULT_LOC.lat,
    lng: DEFAULT_LOC.lng,
    sort: 'near',
    limit: 200,
  })

  return (
    <Sheet open={open} onClose={onClose}>
      <div className="sheet-bar">
        <button className="iconbtn" onClick={onClose} aria-label={T('a11yBack')}>
          <Icon name="i-back" />
        </button>
        <div className="spin">
          <Icon name="i-search" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={mode === 'place' ? T('phPlace') : T('phName')}
            aria-label={mode === 'place' ? T('phPlace') : T('phName')}
            autoComplete="off"
          />
        </div>
      </div>
      <div className="seg">
        <button aria-selected={mode === 'name'} onClick={() => setMode('name')}>
          <Icon name="i-search" cls="ic sm" />
          {T('byName')}
        </button>
        <button aria-selected={mode === 'place'} onClick={() => setMode('place')}>
          <Icon name="i-pin" cls="ic sm" />
          {T('byPlace')}
        </button>
      </div>
      <div className="sheet-scroll">
        <div style={{ padding: '16px var(--s5) 6px', fontSize: 11, fontWeight: 800, letterSpacing: '.08em', color: 'var(--muted)' }}>
          {data.length} {mode === 'place' ? T('results') : T('templesUp')}
        </div>
        {data.length ? (
          data.map((temple) => {
            const name = lang === 'ml' ? temple.ml : temple.en
            const name2 = lang === 'ml' ? temple.en : temple.ml
            const place = temple.mplace && lang === 'ml' ? temple.mplace : temple.place
            return (
              <button
                key={temple.id}
                className="sres"
                onClick={() => {
                  onClose()
                  setTimeout(() => onPick(temple.id), 260)
                }}
              >
                <span className={`glyph ${temple.sig}`}>
                  <Icon name={`i-${temple.sig}`} />
                </span>
                <span className="m">
                  <b>{name}</b>
                  <span>{mode === 'place' ? `${place} · ${fmt(temple.distance_km)}` : `${name2} · ${place}`}</span>
                </span>
                <span className="d">{fmt(temple.distance_km)}</span>
              </button>
            )
          })
        ) : (
          <div style={{ textAlign: 'center', color: 'var(--muted)', padding: 40 }}>
            <Icon name="i-search" />
            <p style={{ marginTop: 10 }}>{T('nothingFound')}</p>
          </div>
        )}
      </div>
    </Sheet>
  )
}
