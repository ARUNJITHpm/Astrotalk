import { useMemo, useState } from 'react'
import { MapContainer, Marker, TileLayer } from 'react-leaflet'
import L from 'leaflet'
import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { toast } from '../../components/Toast'
import { DEFAULT_LOC, useNearbyTemples } from '../../api/hooks'
import { useT } from '../../i18n'
import type { Temple } from '../../api/types'

const TILES = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png'
const ATTR = '© OpenStreetMap © CARTO'
const fmt = (k: number | null) => (k == null ? '' : k < 1 ? `${Math.round(k * 1000)} m` : `${k.toFixed(1)} km`)

const ME_ICON = L.divIcon({
  className: '',
  html: '<div class="me-dot"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
})

function pinIcon(t: Temple, homeId: string | null, label: boolean) {
  const isDef = t.id === homeId
  const size: [number, number] = isDef ? [48, 56] : [40, 48]
  const html = `<div class="pin ${t.sig} ${isDef ? 'def' : ''}">${
    label && isDef ? '<span class="tag">Your temple</span>' : ''
  }<span class="disc"><svg class="ic" aria-hidden="true"><use href="#i-${t.sig}"/></svg></span></div>`
  return L.divIcon({ className: '', html, iconSize: size, iconAnchor: [size[0] / 2, size[1] - 4] })
}

const DEITY_FILTERS = [
  ['all', 'all', 'i-temple'],
  ['shiva', 'dShiva', 'i-shiva'],
  ['devi', 'dDevi', 'i-devi'],
  ['vishnu', 'dVishnu', 'i-vishnu'],
] as const

function TempleMap({
  temples,
  homeId,
  filter,
  label,
  interactive,
  onPick,
}: {
  temples: Temple[]
  homeId: string | null
  filter: string
  label: boolean
  interactive: boolean
  onPick?: (t: Temple) => void
}) {
  const shown = temples.filter((t) => filter === 'all' || t.sig === filter)
  return (
    <MapContainer
      center={[DEFAULT_LOC.lat, DEFAULT_LOC.lng]}
      zoom={12}
      style={{ height: '100%', width: '100%' }}
      zoomControl={interactive}
      dragging={interactive}
      scrollWheelZoom={interactive}
      doubleClickZoom={interactive}
      touchZoom={interactive}
      keyboard={interactive}
      attributionControl
    >
      <TileLayer url={TILES} attribution={ATTR} />
      <Marker position={[DEFAULT_LOC.lat, DEFAULT_LOC.lng]} icon={ME_ICON} interactive={false} />
      {shown.map((t) => (
        <Marker
          key={t.id}
          position={[t.lat, t.lng]}
          icon={pinIcon(t, homeId, label)}
          interactive={interactive}
          eventHandlers={onPick ? { click: () => onPick(t) } : undefined}
        />
      ))}
    </MapContainer>
  )
}

/** The home screen's map preview card (non-interactive, deity-filterable). */
export function MapCard({ homeId, onOpenFull }: { homeId: string | null; onOpenFull: () => void }) {
  const { t: T } = useT()
  const { data = [] } = useNearbyTemples()
  const [filter, setFilter] = useState('all')
  const count = data.filter((t) => filter === 'all' || t.sig === filter).length

  return (
    <div className="mapcard">
      <div className="mapfilter">
        {DEITY_FILTERS.map(([f, key, icon]) => (
          <button key={f} data-f={f} aria-pressed={f === filter} onClick={() => setFilter(f)}>
            <Icon name={icon} />
            {T(key)}
          </button>
        ))}
      </div>
      <div className="mapview">
        <div className="mapcanvas" style={{ pointerEvents: 'none' }}>
          <TempleMap temples={data} homeId={homeId} filter={filter} label interactive={false} />
        </div>
        <span className="mapchrome">
          <span className="mapcount">
            <Icon name="i-temple" cls="ic sm" />
            <span>
              {count} {count === 1 ? T('temple') : T('temples')}
            </span>
          </span>
        </span>
        <button className="maphit" onClick={onOpenFull} aria-label={T('openMap')} />
      </div>
    </div>
  )
}

/** Full-screen map sheet with deity chips and a bottom rail of temple cards. */
export function MapSheet({
  open,
  homeId,
  onClose,
  onPick,
}: {
  open: boolean
  homeId: string | null
  onClose: () => void
  onPick: (id: string) => void
}) {
  const { t: T, lang } = useT()
  const { data = [] } = useNearbyTemples()
  const [filter, setFilter] = useState('all')
  const list = useMemo(() => data.filter((t) => filter === 'all' || t.sig === filter), [data, filter])

  return (
    <Sheet open={open} onClose={onClose}>
      <div style={{ position: 'absolute', inset: 0 }}>
        <TempleMap
          temples={data}
          homeId={homeId}
          filter={filter}
          label
          interactive
          onPick={(t) => onPick(t.id)}
        />
      </div>
      <div className="maptop">
        <div className="mtop">
          <button className="iconbtn" onClick={onClose} aria-label={T('a11yBack')}>
            <Icon name="i-back" />
          </button>
          <button className="searchfield" onClick={onClose}>
            <Icon name="i-search" />
            <span className="txt">{T('searchPlaceholder')}</span>
          </button>
        </div>
        <div className="mchips" role="group">
          {DEITY_FILTERS.map(([f, key, icon]) => (
            <button key={f} data-f={f} aria-pressed={f === filter} onClick={() => setFilter(f)}>
              <Icon name={icon} />
              {T(key)}
            </button>
          ))}
        </div>
      </div>
      <div className="mapbottom">
        <div className="maptools">
          <button className="iconbtn" onClick={() => toast(T('here'))} aria-label={T('a11yLocate')}>
            <Icon name="i-navigate" />
          </button>
        </div>
        <div className="railhead">
          <span>
            {list.length} {list.length === 1 ? T('temple') : T('temples')} · {T('nearestFirst')}
          </span>
        </div>
        <div className="mrail">
          {list.map((t) => {
            const isDef = t.id === homeId
            const name = lang === 'ml' ? t.ml : t.en
            return (
              <article className={`mrcard ${isDef ? 'is-def' : ''}`} key={t.id} onClick={() => onPick(t.id)}>
                <div className="row">
                  <span className={`glyph ${t.sig}`}>
                    <Icon name={`i-${t.sig}`} />
                  </span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {isDef ? (
                      <div className="mrbadge">
                        <Icon name="i-star" />
                        {T('yourTemple')}
                      </div>
                    ) : (
                      <div className="mrdist">
                        <Icon name="i-pin" cls="ic sm" />
                        {fmt(t.distance_km)}
                      </div>
                    )}
                    <h3>{name}</h3>
                    <div className="mrml">{lang === 'ml' ? t.en : t.ml}</div>
                  </div>
                </div>
                <div className="acts">
                  <button
                    className="btn btn-pri"
                    onClick={(e) => {
                      e.stopPropagation()
                      onPick(t.id)
                    }}
                  >
                    {T('details')}
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      </div>
    </Sheet>
  )
}
