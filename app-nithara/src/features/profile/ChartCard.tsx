// The jathakam, once there is one: the rasi grid and the running mahadasha.
//
// This renders positions and says nothing about what they mean. Reading a chart
// is the knowledge corpus and the persona's job — a component that captioned
// "Saturn in the 8th" would be doing astrology in TypeScript, and doing it in
// the fear-forward register GUARDRAILS §2 exists to prevent.

import { Icon } from '../../components/Icon'
import { currentDasha, rasiCells, yearOf, type NatalChart } from '../../lib/chart'
import { useT } from '../../i18n'

export function ChartCard({
  chart,
  onEdit,
  onShare,
  sharing,
}: {
  chart: NatalChart
  onEdit: () => void
  onShare: () => void
  sharing: boolean
}) {
  const { t: T, lang } = useT()
  const cells = rasiCells(chart)
  const dasha = currentDasha(chart)

  return (
    <div className="pcard">
      <h2>
        {T('birthChart')}
        <button className="edit" onClick={onEdit}>
          {T('edit')}
        </button>
      </h2>

      {/* A mocked ephemeris produces a plausible-looking chart from a seed. It
          must never pass for a reading. */}
      {chart.mock && (
        <div className="setup" style={{ marginBottom: 12 }}>
          <div className="si">
            <Icon name="i-sparkle" />
          </div>
          <div className="st">
            <b>{T('chartMockT')}</b>
            <span>{T('chartMockNote')}</span>
          </div>
        </div>
      )}

      <div className="rasi">
        {/* Placed first so CSS grid's auto-placement flows the twelve signs
            around it — see SOUTH_INDIAN_ORDER. */}
        <div className="rc center">
          <div>
            <b>{chart.nakshatram || '—'}</b>
            <span>
              {chart.rasi ? `${T('rasiWord')} ${chart.rasi}` : ''}
              {chart.lagnam ? ` · ${T('lagnaWord')} ${chart.lagnam}` : ''}
            </span>
          </div>
        </div>
        {cells.map((cell) => (
          <div className="rc" key={cell.index}>
            <span>{lang === 'ml' ? cell.ml : cell.en}</span>
            {cell.isLagna && <span className="p">{T('lagnaShort')}</span>}
            {cell.planets.map((p) => (
              <span className="p" key={p}>
                {p}
              </span>
            ))}
          </div>
        ))}
      </div>

      {/* Birth time drives the lagna. When it is unknown the engine says so and
          computes from noon — worth stating, because the ascendant is the part
          of this chart a reader would otherwise take as exact. */}
      {chart.birth_time_known === false && (
        <p className="hint" style={{ marginTop: 10 }}>
          {T('noBirthTimeNote')}
        </p>
      )}

      {dasha && (
        <div className="dasha">
          <div className="bar">
            <i style={{ width: `${Math.round(dasha.progress * 100)}%` }} />
          </div>
          <div className="lg">
            <span>
              {lang === 'ml' ? dasha.lordMl : dasha.lord} {T('dashaWord')}
            </span>
            <span>
              {yearOf(dasha.start)}–{yearOf(dasha.end)}
            </span>
          </div>
        </div>
      )}

      <button
        className="btn btn-ghost btn-block"
        style={{ marginTop: 14 }}
        disabled={sharing}
        onClick={onShare}
      >
        <Icon name="i-share" cls="ic sm" />
        {sharing ? T('sharing') : T('shareChart')}
      </button>
    </div>
  )
}
