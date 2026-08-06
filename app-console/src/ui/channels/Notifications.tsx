// Notification runs: festival updates and star-day reminders.
//
// Two buttons that reach out to real people, so the screen is built around one
// question — did anything actually get sent? A run reports `sent: 12` whether
// WhatsApp is wired or mocked, and "12 sent" is exactly the sentence an
// operator would repeat to a temple. So the integration state is fetched first
// and every result is narrated through it.
//
// GUARDRAILS §3 makes the FIRST live WhatsApp send a human-approval gate. That
// is a decision about this installation, not something a button can grant, so
// the screen states plainly which mode it is in and never implies otherwise.
//
// Both runs are idempotent — a unique row per (festival, phone) in the
// notification log — which is what makes a manual "run now" safe at all. The
// scheduler fires the same endpoints every morning.

import { useMutation, useQuery } from '@tanstack/react-query'

import { runFestivals, runNakshatramReminders } from '../../api/channels'
import { integrationFlags } from '../../api/system'
import { sendReality } from '../../lib/channels'
import { Problem } from '../bits'

export function Notifications() {
  const system = useQuery({
    queryKey: ['integrations'],
    queryFn: integrationFlags,
    staleTime: 5 * 60 * 1000,
  })
  const whatsappLive = system.data?.integrations?.whatsapp

  const festivals = useMutation({ mutationFn: () => runFestivals() })
  const reminders = useMutation({ mutationFn: () => runNakshatramReminders() })

  return (
    <section className="page">
      <h1 className="page__title">Notifications</h1>
      <p className="page__lede">
        The two scheduled runs, and a way to fire either one now.
      </p>

      {whatsappLive === false && (
        <p className="banner banner--warn" role="status">
          WhatsApp is mocked on this installation. Both runs will select
          recipients and write what they would have said to the log. Nothing
          reaches a phone.
        </p>
      )}
      {whatsappLive === true && (
        <p className="banner banner--warn" role="status">
          WhatsApp is live. Pressing either button sends real messages to real
          numbers.
        </p>
      )}
      <Problem error={system.error} />

      <article className="card">
        <div className="card__head">
          <h3 className="card__title">Festival updates</h3>
        </div>
        <p>
          Every temple with a festival exactly three days out, to the people who
          subscribed on that temple's page.
        </p>
        <div className="row">
          <button
            className="btn btn--primary"
            disabled={festivals.isPending}
            onClick={() => festivals.mutate()}
          >
            {festivals.isPending ? 'Running…' : 'Run it now'}
          </button>
        </div>
        {festivals.data && (
          <div className="banner banner--ok" role="status">
            <p>
              {festivals.data.festivals} festival
              {festivals.data.festivals === 1 ? '' : 's'} on{' '}
              {festivals.data.target_day}.
            </p>
            <p>{sendReality(festivals.data.sent, whatsappLive)}</p>
            {festivals.data.skipped > 0 && (
              <p>
                {festivals.data.skipped} skipped — already notified, or not opted
                in.
              </p>
            )}
          </div>
        )}
        <Problem error={festivals.error} />
        <p className="field__hint">
          Safe to press twice. Each (festival, number) pair is logged once, so a
          second run finds nothing left to do rather than sending again.
        </p>
      </article>

      <article className="card">
        <div className="card__head">
          <h3 className="card__title">Star-day reminders</h3>
        </div>
        <p>
          A push to registered devices three days before someone's nakshatram
          comes round.
        </p>
        <div className="row">
          <button
            className="btn btn--primary"
            disabled={reminders.isPending}
            onClick={() => reminders.mutate()}
          >
            {reminders.isPending ? 'Running…' : 'Run it now'}
          </button>
        </div>
        {reminders.data && (
          <p className="banner banner--ok" role="status">
            {reminders.data.reminders_sent} reminder
            {reminders.data.reminders_sent === 1 ? '' : 's'} for star days{' '}
            {reminders.data.target_lead_days} days out.
          </p>
        )}
        <Problem error={reminders.error} />
        <p className="field__hint">
          These go to app installs that registered a device token, not over
          WhatsApp — a devotee who has never opened the app receives nothing.
        </p>
      </article>
    </section>
  )
}
