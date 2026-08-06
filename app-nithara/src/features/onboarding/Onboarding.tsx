import { useMemo, useState } from 'react'
import { Icon } from '../../components/Icon'
import { useNearbyTemples } from '../../api/hooks'
import { useQueryClient } from '@tanstack/react-query'

import { setHomeTempleId } from '../../lib/homeTemple'
import { useT } from '../../i18n'

const fmt = (k: number | null) => (k == null ? '' : k < 1 ? `${Math.round(k * 1000)} m` : `${k.toFixed(1)} km`)

// First run: "Choose your temple." No sign-up, no name (GUARDRAILS / product
// promise). Picks are persisted client-side for now (see lib/homeTemple).
export function Onboarding({ onDone }: { onDone: () => void }) {
  const { t: T, lang } = useT()
  const { data = [] } = useNearbyTemples()
  const [q, setQ] = useState('')
  const [picked, setPicked] = useState<string | null>(null)

  const list = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return data
    return data.filter((t) => `${t.en} ${t.ml} ${t.place}`.toLowerCase().includes(needle))
  }, [data, q])

  const qc = useQueryClient()

  async function finish() {
    if (!picked) return
    // Close the sheet first: the choice is cached locally straight away, so the
    // home screen is already right, and a slow network must not leave somebody
    // staring at onboarding they have finished with.
    onDone()
    try {
      await setHomeTempleId(picked, qc)
    } catch {
      // The account write failed. The local cache still holds the choice, and
      // the next successful read reconciles — so the devotee is not asked again
      // over a dropped request.
    }
  }

  return (
    <div className="onboard" style={{ display: 'flex', flexDirection: 'column', position: 'fixed', inset: 0, zIndex: 100, background: 'var(--paper)' }}>
      <div className="ob-scroll" style={{ flex: 1, overflowY: 'auto' }}>
        <div className="ob-brand">
          <span className="mk">
            <Icon name="i-lamp" cls="ic sm" />
          </span>
          <b>Nithara</b>
        </div>
        <div className="ob-hero">
          <h1>{T('obH1')}</h1>
          <p>{T('obP')}</p>
        </div>
        <div className="spin" style={{ margin: '0 var(--s5)' }}>
          <Icon name="i-search" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={T('phName')}
            aria-label={T('phName')}
            autoComplete="off"
          />
        </div>
        <div style={{ marginTop: 12 }}>
          {list.map((t) => {
            const name = lang === 'ml' ? t.ml : t.en
            const name2 = lang === 'ml' ? t.en : t.ml
            const active = t.id === picked
            return (
              <button
                key={t.id}
                className="sres"
                aria-pressed={active}
                style={active ? { background: 'var(--saffron-tint)' } : undefined}
                onClick={() => setPicked(t.id)}
              >
                <span className={`glyph ${t.sig}`}>
                  <Icon name={`i-${t.sig}`} />
                </span>
                <span className="m">
                  <b>{name}</b>
                  <span>
                    {name2} · {t.place}
                  </span>
                </span>
                <span className="d">{active ? <Icon name="i-check" cls="ic sm" /> : fmt(t.distance_km)}</span>
              </button>
            )
          })}
        </div>
      </div>
      <div className="ob-foot">
        <button className="btn btn-pri btn-block" disabled={!picked} onClick={finish}>
          {T('obStart')}
        </button>
        <p className="ob-fine">{T('obFine')}</p>
      </div>
    </div>
  )
}
