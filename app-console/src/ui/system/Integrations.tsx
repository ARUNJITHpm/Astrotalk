// Which external services are wired, and which are pretending.
//
// This is the most load-bearing page in the console and the least impressive
// one. Almost every confusing thing an operator can see elsewhere — "the
// notification says 12 sent but the temple got nothing", "the panchangam
// doesn't match the calendar", "the payment went through but no money moved" —
// is one of these pills being off.
//
// So the wording is deliberate. "mocked" says what is happening; "off" or
// "disabled" would suggest a feature switched away rather than a stand-in
// quietly answering in its place.
//
// The endpoint reports booleans only. Whether a key is configured is shown;
// what the key is never leaves the server.

import { useQuery } from '@tanstack/react-query'

import { overview } from '../../api/system'
import { Problem } from '../bits'

/** What being off actually costs, in the operator's terms. */
const CONSEQUENCE: Record<string, string> = {
  llm: 'Chat and generated content fall back to canned templates.',
  ephemeris: 'Charts and panchangam are placeholder figures, not calculations.',
  mongo: 'Chat history is not being kept where the explorer reads it.',
  geocoding: 'A birth place cannot be resolved to coordinates.',
  whatsapp: 'Messages are written to the log instead of sent.',
  razorpay: 'Payments complete without any money moving.',
  chroma: 'The knowledge base is not searched; answers lose their citations.',
}

const LABEL: Record<string, string> = {
  llm: 'Language model',
  ephemeris: 'Ephemeris',
  mongo: 'Chat store',
  geocoding: 'Geocoding',
  whatsapp: 'WhatsApp',
  razorpay: 'Payments',
  chroma: 'Knowledge search',
}

export function Integrations() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['overview'],
    queryFn: overview,
    staleTime: 5 * 60 * 1000,
  })

  const system = data?.system
  const integrations = Object.entries(system?.integrations ?? {})
  const keys = Object.entries(system?.api_keys_present ?? {})
  const mocked = integrations.filter(([, live]) => !live)

  return (
    <section className="page">
      <h1 className="page__title">Integrations</h1>
      <p className="page__lede">
        What this installation is really talking to. A mocked service answers
        convincingly and does nothing.
      </p>

      <Problem error={error} />
      {isLoading && <p className="empty">Loading…</p>}

      {system && (
        <>
          <div className="tiles">
            <div className="tile">
              <p className="tile__label">Environment</p>
              <p className="tile__value">{system.app_env}</p>
            </div>
            <div className="tile">
              <p className="tile__label">Chat provider</p>
              <p className="tile__value">{system.chat_provider}</p>
            </div>
            <div className="tile">
              <p className="tile__label">Session length</p>
              <p className="tile__value">{system.session_ttl_hours}h</p>
              <p className="tile__hint">how long a devotee stays signed in</p>
            </div>
            <div className="tile">
              <p className="tile__label">Chat rate limit</p>
              <p className="tile__value">{system.chat_rate_limit_per_hour}</p>
              <p className="tile__hint">messages per user per hour</p>
            </div>
          </div>

          {mocked.length > 0 && (
            <p className="banner banner--warn" role="status">
              {mocked.length} service{mocked.length === 1 ? ' is' : 's are'} mocked:{' '}
              {mocked.map(([name]) => LABEL[name] ?? name).join(', ')}. Anything
              downstream of {mocked.length === 1 ? 'it' : 'them'} is a rehearsal.
            </p>
          )}

          <h2 className="section__title">Services</h2>
          <div className="tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>State</th>
                  <th>What that means here</th>
                </tr>
              </thead>
              <tbody>
                {integrations.map(([name, live]) => (
                  <tr key={name} className={live ? undefined : 'row--off'}>
                    <td>
                      <strong>{LABEL[name] ?? name}</strong>
                      <span className="cell__sub">{name}</span>
                    </td>
                    <td>
                      <span className={live ? 'badge badge--on' : 'badge badge--off'}>
                        {live ? 'live' : 'mocked'}
                      </span>
                    </td>
                    <td>{live ? '—' : (CONSEQUENCE[name] ?? 'A stand-in answers instead.')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h2 className="section__title">Credentials</h2>
          <p className="field__hint">
            Whether a key is configured. The values are never sent to this page.
          </p>
          <div className="tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Key</th>
                  <th>Configured</th>
                </tr>
              </thead>
              <tbody>
                {keys.map(([name, present]) => (
                  <tr key={name}>
                    <td>{name}</td>
                    <td>
                      <span className={present ? 'badge badge--on' : 'badge badge--off'}>
                        {present ? 'set' : 'not set'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data && (
            <p className="field__hint">
              Read at {new Date(data.generated_at).toLocaleString()}. These
              settings change on a redeploy, not while you are looking at them.
            </p>
          )}
        </>
      )}
    </section>
  )
}
