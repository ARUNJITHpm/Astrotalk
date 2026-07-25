import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { apiGet, qs } from '../../api/client'
import { NAKSHATRAMS } from '../../lib/nakshatrams'
import { useT } from '../../i18n'

// The two free astrology tools from the Astro tab, backed by the engine:
//   GET /astrology/porutham?bride=&groom=   GET /astrology/muhurtham?day=&purpose=
// Both report computed facts only — no "should they marry" verdict (GUARDRAILS).

interface PoruthamOut {
  score: number
  max_score: number
  rajju_dosha: boolean
  favourable: string[]
  unfavourable: string[]
  poruthams: Record<string, { grade: string; points: number; reason: string }>
}

interface MuhurthamOut {
  date: string
  tithi: string
  nakshatram: string
  nalla_neram: string
  note: string
}

const selectStyle = {
  width: '100%',
  boxSizing: 'border-box' as const,
  padding: '12px 14px',
  border: '1.5px solid var(--line-2)',
  borderRadius: 'var(--r-md)',
  background: 'var(--surface)',
  fontSize: 15,
}

export function PoruthamSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t: T, lang } = useT()
  const [bride, setBride] = useState(0)
  const [groom, setGroom] = useState(0)
  // Don't score a pair the user never chose — the prototype's defaults would
  // otherwise render a Rohini×Chithira result the moment the sheet opens.
  const [touched, setTouched] = useState(false)
  const { data } = useQuery({
    queryKey: ['porutham', bride, groom],
    queryFn: () => apiGet<PoruthamOut>('/astrology/porutham' + qs({ bride, groom })),
    enabled: open && touched,
  })

  return (
    <Sheet open={open} onClose={onClose} dir="right">
      <div className="sheet-bar">
        <button className="iconbtn" onClick={onClose} aria-label={T('a11yBack')}>
          <Icon name="i-back" />
        </button>
        <h2>{T('poruthamH')}</h2>
      </div>
      <div className="sheet-scroll" style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <label>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>{T('bride')}</div>
          <select
            style={selectStyle}
            value={bride}
            onChange={(e) => {
              setBride(Number(e.target.value))
              setTouched(true)
            }}
          >
            {NAKSHATRAMS.map(([en, ml], i) => (
              <option key={i} value={i}>
                {lang === 'ml' ? ml : en}
              </option>
            ))}
          </select>
        </label>
        <label>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>{T('groom')}</div>
          <select
            style={selectStyle}
            value={groom}
            onChange={(e) => {
              setGroom(Number(e.target.value))
              setTouched(true)
            }}
          >
            {NAKSHATRAMS.map(([en, ml], i) => (
              <option key={i} value={i}>
                {lang === 'ml' ? ml : en}
              </option>
            ))}
          </select>
        </label>

        {data && (
          <>
            <div className="rvcard">
              <div className="rvrow total">
                <span className="k">{T('score')}</span>
                <span className="v">
                  {data.score} / {data.max_score}
                </span>
              </div>
              {data.rajju_dosha && (
                <div className="rvrow">
                  <span className="k">Rajju</span>
                  <span className="v">{T('rajjuNote')}</span>
                </div>
              )}
            </div>
            <div className="rvcard">
              {Object.entries(data.poruthams).map(([key, r]) => (
                <div className="rvrow" key={key}>
                  <span className="k" style={{ textTransform: 'capitalize' }}>
                    {key}
                  </span>
                  <span className="v">{r.grade}</span>
                </div>
              ))}
            </div>
            <div className="rvnote">
              <Icon name="i-shield" cls="ic sm" />
              {/* State plainly that this is the nakshatram count only — a score
                  with no caveat reads as a full compatibility verdict. */}
              <span>{T('poruthamNote')}</span>
            </div>
          </>
        )}
      </div>
    </Sheet>
  )
}

/** Today in the viewer's own timezone. `toISOString()` would give the UTC date,
 *  which before 05:30 IST is yesterday. */
function localToday(): string {
  const d = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function MuhurthamSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t: T } = useT()
  const [day, setDay] = useState(localToday)
  const [purpose, setPurpose] = useState('')
  const [debouncedPurpose, setDebouncedPurpose] = useState('')

  // Re-anchor to "today" each time the sheet opens, so a PWA left open across
  // midnight doesn't keep yesterday's date.
  useEffect(() => {
    if (open) setDay(localToday())
  }, [open])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedPurpose(purpose.trim()), 300)
    return () => clearTimeout(t)
  }, [purpose])

  const { data } = useQuery({
    queryKey: ['muhurtham', day, debouncedPurpose],
    queryFn: () =>
      apiGet<MuhurthamOut>('/astrology/muhurtham' + qs({ day, purpose: debouncedPurpose })),
    enabled: open,
  })

  return (
    <Sheet open={open} onClose={onClose} dir="right">
      <div className="sheet-bar">
        <button className="iconbtn" onClick={onClose} aria-label={T('a11yBack')}>
          <Icon name="i-back" />
        </button>
        <h2>{T('tMuhurtham')}</h2>
      </div>
      <div className="sheet-scroll" style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <label>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>{T('rDate')}</div>
          <input type="date" style={selectStyle} value={day} onChange={(e) => setDay(e.target.value)} />
        </label>
        <label>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>{T('tMuhurthamS')}</div>
          <input style={selectStyle} value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="griha pravesham" />
        </label>
        {data && (
          <>
            <div className="rvcard">
              <div className="rvrow">
                <span className="k">{T('fNak')}</span>
                <span className="v">{data.nakshatram}</span>
              </div>
              <div className="rvrow">
                <span className="k">Tithi</span>
                <span className="v">{data.tithi}</span>
              </div>
              <div className="rvrow total">
                <span className="k">{T('nallaNeram')}</span>
                <span className="v">{data.nalla_neram}</span>
              </div>
            </div>
            <div className="rvnote">
              <Icon name="i-shield" cls="ic sm" />
              <span>{data.note}</span>
            </div>
          </>
        )}
      </div>
    </Sheet>
  )
}
