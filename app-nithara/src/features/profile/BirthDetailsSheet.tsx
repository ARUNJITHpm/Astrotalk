// Birth details → a real jathakam.
//
// Nithara's accounts start anonymous, and until now the only writer of these
// three fields was the signup form an anonymous account never sees. So the
// profile could read a chart it had no way to create, and said "coming soon".
//
// The one design decision worth defending: birth time is optional and the form
// says so out loud. A required field makes people guess, and a guessed hour
// produces a confidently wrong lagna — worse than an honestly narrowed reading.

import { useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { apiPut } from '../../api/client'
import { useT } from '../../i18n'
import type { Chart } from '../../api/types'

export interface BirthDraft {
  dob: string
  birth_time: string
  birth_place: string
}

const EMPTY: BirthDraft = { dob: '', birth_time: '', birth_place: '' }

export function BirthDetailsSheet({
  open,
  initial,
  onClose,
}: {
  open: boolean
  initial?: BirthDraft
  onClose: () => void
}) {
  const { t: T } = useT()
  const qc = useQueryClient()
  const [form, setForm] = useState<BirthDraft>(initial ?? EMPTY)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const ready = !!form.dob && !!form.birth_place.trim()

  // Matches MemberSheet — this app has no form-field class in globals.css, and
  // adding one here would leave the two sheets looking subtly different.
  const inputStyle = {
    width: '100%',
    boxSizing: 'border-box' as const,
    padding: '12px 14px',
    border: '1.5px solid var(--line-2)',
    borderRadius: 'var(--r-md)',
    background: 'var(--surface)',
    fontSize: 15,
  }
  const labelStyle = {
    fontSize: 12,
    fontWeight: 700,
    color: 'var(--muted)',
    marginBottom: 6,
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      // A body, never a query string. GUARDRAILS §4 — a date of birth in a URL
      // is a date of birth in every access log along the way.
      await apiPut<Chart>('/identity/me/birth', {
        dob: form.dob,
        birth_time: form.birth_time || null,
        birth_place: form.birth_place.trim(),
      })
      await qc.invalidateQueries({ queryKey: ['chart'] })
      onClose()
    } catch {
      setError(T('saveFailed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Sheet open={open} onClose={onClose}>
      <div className="sheet-bar">
        <button className="iconbtn" onClick={onClose} aria-label={T('a11yClose')}>
          <Icon name="i-close" />
        </button>
        <h2>{T('birthDetails')}</h2>
      </div>
      <div
        className="sheet-scroll"
        style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 14 }}
      >
        <p className="hint" style={{ margin: 0 }}>
          {T('birthDetailsWhy')}
        </p>

        <label style={{ display: 'block' }}>
          <div style={labelStyle}>{T('dobLabel')}</div>
          <input
            type="date"
            style={inputStyle}
            value={form.dob}
            onChange={(e) => setForm({ ...form, dob: e.target.value })}
          />
        </label>

        <label style={{ display: 'block' }}>
          <div style={labelStyle}>{T('birthTimeLabel')}</div>
          <input
            type="time"
            style={inputStyle}
            value={form.birth_time}
            onChange={(e) => setForm({ ...form, birth_time: e.target.value })}
          />
          <small className="hint">{T('birthTimeOptional')}</small>
        </label>

        <label style={{ display: 'block' }}>
          <div style={labelStyle}>{T('birthPlaceLabel')}</div>
          <input
            type="text"
            style={inputStyle}
            placeholder={T('birthPlaceHint')}
            value={form.birth_place}
            onChange={(e) => setForm({ ...form, birth_place: e.target.value })}
          />
        </label>

        <p className="hint" style={{ margin: 0 }}>
          {T('birthPrivacyNote')}
        </p>
      </div>
      <div className="dcta" style={{ flexDirection: 'column', gap: 8 }}>
        {error && (
          <p style={{ color: 'var(--kumkum)', fontSize: 13, textAlign: 'center', margin: 0 }} role="alert">
            {error}
          </p>
        )}
        <button className="btn btn-pri btn-block" disabled={!ready || busy} onClick={save}>
          {busy ? T('computing') : T('computeChart')}
        </button>
      </div>
    </Sheet>
  )
}
