import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Sheet } from '../../components/Sheet'
import { Icon } from '../../components/Icon'
import { toast } from '../../components/Toast'
import { ApiError, api, apiPost } from '../../api/client'
import { NAKSHATRAMS, RELATIONS } from '../../lib/nakshatrams'
import { useT } from '../../i18n'
import type { Member } from '../../api/types'

// Add or edit a family member (the "in whose name" a pooja is booked). The self
// row's relation is fixed and it can't be deleted (the backend enforces both).
export function MemberSheet({ editing, onClose }: { editing: Member | 'new' | null; onClose: () => void }) {
  const { t: T, lang } = useT()
  const qc = useQueryClient()
  const isNew = editing === 'new'
  const existing = editing && editing !== 'new' ? editing : null

  const [name, setName] = useState('')
  const [rel, setRel] = useState('rMother')
  const [nak, setNak] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (existing) {
      setName(existing.name)
      setRel(existing.rel)
      setNak(existing.nak)
    } else if (isNew) {
      setName('')
      setRel('rMother')
      setNak(null)
    }
  }, [editing])

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['members'] })
    qc.invalidateQueries({ queryKey: ['stats'] })
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      const body = { name: name.trim(), rel, nak }
      if (isNew) await apiPost('/identity/me/members', body)
      else await api(`/identity/me/members/${existing!.id}`, { method: 'PATCH', body: JSON.stringify(body) })
      refresh()
      toast(T(isNew ? 'memberAdded' : 'saved'))
      onClose()
    } catch (e) {
      // Surface the real reason (e.g. 400 "Family board is full") instead of
      // leaving the sheet open with no feedback and inviting repeat taps.
      setError(e instanceof ApiError && e.status === 400 ? T('boardFull') : T('saveFailed'))
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!existing) return
    setBusy(true)
    setError(null)
    try {
      await api(`/identity/me/members/${existing.id}`, { method: 'DELETE' })
      refresh()
      onClose()
    } catch {
      setError(T('saveFailed'))
    } finally {
      setBusy(false)
    }
  }

  const inputStyle = {
    width: '100%',
    boxSizing: 'border-box' as const,
    padding: '12px 14px',
    border: '1.5px solid var(--line-2)',
    borderRadius: 'var(--r-md)',
    background: 'var(--surface)',
    fontSize: 15,
  }

  return (
    <Sheet open={editing !== null} onClose={onClose} dir="right">
      <div className="sheet-bar">
        <button className="iconbtn" onClick={onClose} aria-label={T('a11yBack')}>
          <Icon name="i-back" />
        </button>
        <h2>{isNew ? T('addSomeone') : existing?.name || T('addYourName')}</h2>
      </div>
      <div className="sheet-scroll" style={{ padding: 'var(--s5)', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <label style={{ display: 'block' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>{T('mName')}</div>
          <input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} placeholder={T('addYourName')} />
        </label>

        {!existing?.self && (
          <label style={{ display: 'block' }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>{T('whoFor')}</div>
            <select style={inputStyle} value={rel} onChange={(e) => setRel(e.target.value)}>
              {RELATIONS.map((r) => (
                <option key={r} value={r}>
                  {T(r)}
                </option>
              ))}
            </select>
          </label>
        )}

        <label style={{ display: 'block' }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>{T('fNak')}</div>
          <select
            style={inputStyle}
            value={nak ?? ''}
            onChange={(e) => setNak(e.target.value === '' ? null : Number(e.target.value))}
          >
            <option value="">{T('nakNotSet')}</option>
            {NAKSHATRAMS.map(([en, ml], i) => (
              <option key={i} value={i}>
                {lang === 'ml' ? ml : en}
              </option>
            ))}
          </select>
        </label>

        {error && (
          <p style={{ color: 'var(--kumkum)', fontSize: 13, margin: 0 }} role="alert">
            {error}
          </p>
        )}
        <button className="btn btn-pri btn-block" disabled={busy} onClick={save} style={{ marginTop: 8 }}>
          {T('save')}
        </button>
        {existing && !existing.self && (
          <button className="btn btn-sec btn-block" disabled={busy} onClick={remove}>
            {T('remove')}
          </button>
        )}
      </div>
    </Sheet>
  )
}
