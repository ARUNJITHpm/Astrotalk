// One temple, every field.
//
// Three things here are not obvious and each has a reason:
//
//   1. **Save sends a diff, not the form.** `PATCH /temples/{id}` treats an
//      explicit null as "clear this column", so restating every field would
//      wipe a temple's darshan windows whenever someone fixed a typo in its
//      name. `diffTemple` is the whole of that rule and it is tested apart
//      from this screen.
//   2. **Sign-off and listing are not part of Save.** They have their own
//      routes and their own roles — `reviewed` says an astrologer checked the
//      devotional copy (GUARDRAILS §1), and letting the role that writes that
//      copy also certify it would make the flag self-issued.
//   3. **Rating and reviews are editable but not invented.** They stay null
//      until real data exists; the field carries that warning rather than
//      relying on everyone remembering it.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  DEITIES,
  TIMING_KEYS,
  createTemple,
  listTemples,
  mediaUrl,
  patchTemple,
  setTempleActive,
  setTempleReviewed,
  uploadTempleImage,
  type Temple,
  type TemplePatch,
} from '../../api/temples'
import { useAuth } from '../../lib/auth'
import {
  clockToMinutes,
  diffTemple,
  hoursProblem,
  minutesToClock,
  parseCoords,
} from '../../lib/temple'
import { Badge, Field, Problem } from './bits'

const ID_RE = /^[a-z0-9][a-z0-9-]{1,60}$/

/** A temple that does not exist yet. Coordinates start as NaN rather than 0,0:
 *  a blank field says "unfilled", while a plausible number says "checked". */
const BLANK: Temple = {
  id: '',
  name: '',
  name_ml: '',
  deity: 'shiva',
  district: '',
  town: '',
  town_ml: '',
  lat: Number.NaN,
  lng: Number.NaN,
  famous_for: '',
  vazhipadu: [],
  reviewed: false,
  story: '',
  story_ml: '',
  hours: null,
  timings: null,
  rating: null,
  reviews: null,
  active: true,
  image_key: null,
  sort_order: 0,
  updated_at: '',
}

function draftFrom(t: Temple) {
  return {
    name: t.name,
    name_ml: t.name_ml,
    deity: t.deity,
    district: t.district,
    town: t.town,
    town_ml: t.town_ml,
    lat: t.lat,
    lng: t.lng,
    famous_for: t.famous_for,
    vazhipadu: t.vazhipadu,
    story: t.story,
    story_ml: t.story_ml,
    hours: t.hours,
    timings: t.timings,
    rating: t.rating,
    reviews: t.reviews,
    sort_order: t.sort_order,
  }
}

type Draft = ReturnType<typeof draftFrom>

const DEFAULT_WINDOW: [number, number] = [4 * 60 + 30, 11 * 60]

/** What the server would reject, said before the round trip. */
function problems(draft: Draft, creating: boolean, id: string): string[] {
  const out: string[] = []
  if (creating && !ID_RE.test(id)) {
    out.push('The id must be lowercase letters, digits and hyphens (e.g. tsr-guruvayur).')
  }
  if (!draft.name.trim()) out.push('A name is required.')
  if (!draft.district.trim()) out.push('A district is required.')
  // Guarded rather than merely validated: JSON.stringify turns NaN into null,
  // and a null latitude reaches the server's range check as a type error.
  if (!Number.isFinite(draft.lat) || !Number.isFinite(draft.lng)) {
    out.push('Latitude and longitude are required.')
  }
  if (draft.hours) {
    const bad = hoursProblem(draft.hours)
    if (bad) out.push(bad)
  }
  if (draft.timings && TIMING_KEYS.some((k) => !draft.timings?.[k]?.trim())) {
    out.push('Fill all three darshan windows, or switch back to the defaults.')
  }
  return out
}

function numberOrNaN(text: string): number {
  return text.trim() === '' ? Number.NaN : Number(text)
}

export function TempleEditor() {
  const { templeId } = useParams<{ templeId?: string }>()
  const creating = !templeId
  const { me } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: temples, isLoading } = useQuery({
    queryKey: ['temples'],
    queryFn: listTemples,
  })
  const temple = creating ? BLANK : temples?.find((t) => t.id === templeId)

  const [newId, setNewId] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [paste, setPaste] = useState('')
  const [pasteError, setPasteError] = useState('')
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  // A blank create form fails every check. Announcing that as an alert before
  // the operator has typed anything is noise — and, to a screen reader, four
  // errors about a form they have not started.
  const [touched, setTouched] = useState(false)

  // Load the row into the form when it arrives, again if the operator navigates
  // straight from one temple to another, and again after a save — the server's
  // version is the truth, and re-reading it is what makes a rejected field
  // visible instead of leaving the form showing something that was not stored.
  // Keyed on id + updated_at rather than the object, which is a new reference
  // on every refetch and would wipe the form mid-edit.
  useEffect(() => {
    if (temple) setDraft(draftFrom(temple))
  }, [temple?.id, temple?.updated_at])

  // Anything remembered about the temple just left has to go with it — a photo
  // just uploaded for one temple would otherwise show as the next one's.
  useEffect(() => {
    setSaved(false)
    setTouched(false)
    setImageUrl(null)
    setPaste('')
    setPasteError('')
  }, [templeId])

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['temples'] })

  const save = useMutation({
    mutationFn: async () => {
      if (!draft) return null
      if (creating) {
        return createTemple({ ...draft, id: newId, lat: draft.lat, lng: draft.lng })
      }
      const patch: TemplePatch = diffTemple(temple as Temple, draft)
      if (!Object.keys(patch).length) return temple as Temple
      return patchTemple(templeId as string, patch)
    },
    onSuccess: async (row) => {
      await refresh()
      setSaved(true)
      if (creating && row) navigate(`/temples/${encodeURIComponent(row.id)}`)
    },
  })

  const review = useMutation({
    mutationFn: (reviewed: boolean) => setTempleReviewed(templeId as string, reviewed),
    onSuccess: refresh,
  })

  const listing = useMutation({
    mutationFn: (active: boolean) => setTempleActive(templeId as string, active),
    onSuccess: refresh,
  })

  const image = useMutation({
    mutationFn: (file: File) => uploadTempleImage(templeId as string, file),
    onSuccess: async (res) => {
      setImageUrl(res.url)
      await refresh()
    },
  })

  if (isLoading) return <p className="empty">Loading…</p>
  if (!temple || !draft) {
    return (
      <section className="page">
        <h1 className="page__title">No such temple</h1>
        <p className="page__lede">
          It may have been renamed, or it may not be one of yours.{' '}
          <Link to="/temples">Back to the directory</Link>.
        </p>
      </section>
    )
  }

  const set = (patch: Partial<Draft>) => {
    setDraft((d) => (d ? { ...d, ...patch } : d))
    setSaved(false)
    setTouched(true)
  }
  const canReview = me?.is_owner || me?.roles.includes('content_reviewer')
  const issues = problems(draft, creating, newId)
  const pending = save.isPending
  // Nothing to send is not the same as a successful save, and a Save button
  // that reports "Saved" without a request is how an operator comes to believe
  // an edit landed when the field never changed.
  const unchanged = !creating && !Object.keys(diffTemple(temple, draft)).length

  const applyPaste = () => {
    const found = parseCoords(paste)
    if (!found) {
      setPasteError('No coordinates in that. Paste a Maps link or "9.9312, 76.2673".')
      return
    }
    setPasteError('')
    setPaste('')
    set({ lat: found.lat, lng: found.lng })
  }

  const setWindow = (index: number, side: 0 | 1, clock: string) => {
    const minutes = clockToMinutes(clock)
    if (minutes === null || !draft.hours) return
    const hours = draft.hours.map((w, i) =>
      i === index ? (side === 0 ? [minutes, w[1]] : [w[0], minutes]) : w,
    )
    set({ hours })
  }

  return (
    <section className="page">
      <div className="page__head">
        <div>
          <h1 className="page__title">{creating ? 'Add a temple' : temple.name}</h1>
          <p className="page__lede">
            {creating ? (
              'A new directory entry. It is listed to the app the moment it is saved, and unreviewed until an astrologer signs it off.'
            ) : (
              <>
                <code>{temple.id}</code> · <Badge on={temple.reviewed} yes="Reviewed" no="Draft" />{' '}
                <Badge on={temple.active} yes="Listed" no="Retired" />
              </>
            )}
          </p>
        </div>
        <Link className="btn btn--inline" to="/temples">
          Back to the directory
        </Link>
      </div>

      <Problem error={save.error ?? review.error ?? listing.error ?? image.error} />
      {saved && !issues.length && (
        <p className="banner banner--ok" role="status">
          Saved. The app is serving the new version already.
        </p>
      )}

      <form
        className="form"
        onSubmit={(e) => {
          e.preventDefault()
          if (!issues.length) save.mutate()
        }}
      >
        <fieldset className="card">
          <legend>Identity</legend>
          {creating && (
            <Field
              label="Id"
              hint="Permanent. It appears in booking references and URLs, so it cannot be changed later."
            >
              <input
                value={newId}
                onChange={(e) => {
                  setNewId(e.target.value)
                  setTouched(true)
                }}
                placeholder="tsr-guruvayur"
              />
            </Field>
          )}
          <div className="grid2">
            <Field label="Name">
              <input value={draft.name} onChange={(e) => set({ name: e.target.value })} />
            </Field>
            <Field label="Name" ml>
              <input
                lang="ml"
                spellCheck={false}
                value={draft.name_ml}
                onChange={(e) => set({ name_ml: e.target.value })}
              />
            </Field>
            <Field label="Deity" hint="Drives the remedy suggestions the chat makes.">
              <select value={draft.deity} onChange={(e) => set({ deity: e.target.value })}>
                {DEITIES.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="District">
              <input
                value={draft.district}
                onChange={(e) => set({ district: e.target.value })}
              />
            </Field>
            <Field label="Town">
              <input value={draft.town} onChange={(e) => set({ town: e.target.value })} />
            </Field>
            <Field label="Town" ml>
              <input
                lang="ml"
                spellCheck={false}
                value={draft.town_ml ?? ''}
                onChange={(e) => set({ town_ml: e.target.value })}
              />
            </Field>
          </div>
        </fieldset>

        <fieldset className="card">
          <legend>Location</legend>
          <div className="grid2">
            <Field label="Latitude">
              <input
                inputMode="decimal"
                value={Number.isFinite(draft.lat) ? String(draft.lat) : ''}
                onChange={(e) => set({ lat: numberOrNaN(e.target.value) })}
              />
            </Field>
            <Field label="Longitude">
              <input
                inputMode="decimal"
                value={Number.isFinite(draft.lng) ? String(draft.lng) : ''}
                onChange={(e) => set({ lng: numberOrNaN(e.target.value) })}
              />
            </Field>
          </div>
          <Field
            label="Paste from Google Maps"
            hint='A share link, the address bar, or a plain "9.9312, 76.2673".'
          >
            <div className="row">
              <input
                value={paste}
                placeholder="https://maps.app.goo.gl/… or 9.9312, 76.2673"
                onChange={(e) => setPaste(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    applyPaste()
                  }
                }}
              />
              <button type="button" className="btn" onClick={applyPaste}>
                Use it
              </button>
            </div>
          </Field>
          {pasteError && <p className="field__error">{pasteError}</p>}
          {Number.isFinite(draft.lat) && Number.isFinite(draft.lng) && (
            <p className="field__hint">
              <a
                href={`https://www.google.com/maps/search/?api=1&query=${draft.lat},${draft.lng}`}
                target="_blank"
                rel="noreferrer"
              >
                Check this point on a map ↗
              </a>{' '}
              — a swapped pair lands in the sea, and the app sorts by distance.
            </p>
          )}
        </fieldset>

        <fieldset className="card">
          <legend>What it is known for</legend>
          <Field label="Famous for" hint="One line. The app shows it under the name.">
            <input
              value={draft.famous_for}
              onChange={(e) => set({ famous_for: e.target.value })}
            />
          </Field>
          <Field
            label="Vazhipadu"
            hint="One offering per line. These are the names devotees recognise, not the booking catalogue."
          >
            <textarea
              rows={4}
              value={draft.vazhipadu.join('\n')}
              onChange={(e) =>
                set({
                  vazhipadu: e.target.value
                    .split('\n')
                    .map((v) => v.trim())
                    .filter(Boolean),
                })
              }
            />
          </Field>
          <div className="grid2">
            <Field label="Story">
              <textarea
                rows={7}
                value={draft.story ?? ''}
                onChange={(e) => set({ story: e.target.value })}
              />
            </Field>
            <Field label="Story" ml>
              <textarea
                rows={7}
                lang="ml"
                spellCheck={false}
                value={draft.story_ml ?? ''}
                onChange={(e) => set({ story_ml: e.target.value })}
              />
            </Field>
          </div>
          <p className="field__hint">
            The Malayalam story is what most devotees read. Leaving it empty falls
            back to the English one rather than showing nothing.
          </p>
        </fieldset>

        <fieldset className="card">
          <legend>Darshan</legend>
          <label className="check">
            <input
              type="checkbox"
              checked={draft.timings === null}
              onChange={(e) =>
                set({
                  timings: e.target.checked
                    ? null
                    : { nirmalyam: '', morning: '', evening: '' },
                })
              }
            />
            <span>Use the standard timings for this temple</span>
          </label>
          {draft.timings && (
            <div className="grid3">
              {TIMING_KEYS.map((key) => (
                <Field key={key} label={key}>
                  <input
                    value={draft.timings?.[key] ?? ''}
                    placeholder="4:30 AM – 11:00 AM"
                    onChange={(e) =>
                      set({ timings: { ...draft.timings, [key]: e.target.value } })
                    }
                  />
                </Field>
              ))}
            </div>
          )}

          <label className="check">
            <input
              type="checkbox"
              checked={draft.hours === null}
              onChange={(e) => set({ hours: e.target.checked ? null : [DEFAULT_WINDOW] })}
            />
            <span>Use the standard open/closed windows</span>
          </label>
          {draft.hours && (
            <>
              <p className="field__hint">
                These decide the “open now” badge, so they are the clock, not the
                display text above.
              </p>
              {draft.hours.map((window, i) => (
                <div className="row row--window" key={i}>
                  <input
                    type="time"
                    value={minutesToClock(window[0])}
                    onChange={(e) => setWindow(i, 0, e.target.value)}
                  />
                  <span className="row__dash">to</span>
                  <input
                    type="time"
                    value={minutesToClock(window[1])}
                    onChange={(e) => setWindow(i, 1, e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn"
                    onClick={() =>
                      set({ hours: draft.hours?.filter((_, j) => j !== i) ?? null })
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
              <button
                type="button"
                className="btn"
                onClick={() => set({ hours: [...(draft.hours ?? []), [17 * 60, 20 * 60]] })}
              >
                Add a window
              </button>
            </>
          )}
        </fieldset>

        <fieldset className="card">
          <legend>Presentation</legend>
          <div className="grid2">
            <Field
              label="Rating"
              hint="Only from a real source. An invented figure is a claim the app then repeats."
            >
              <input
                value={draft.rating ?? ''}
                placeholder="leave empty"
                onChange={(e) => set({ rating: e.target.value || null })}
              />
            </Field>
            <Field label="Reviews" hint="Same rule. Empty is the honest default.">
              <input
                value={draft.reviews ?? ''}
                placeholder="leave empty"
                onChange={(e) => set({ reviews: e.target.value || null })}
              />
            </Field>
          </div>
          <Field label="Sort order" hint="Lower sorts first in the directory.">
            <input
              type="number"
              value={draft.sort_order}
              onChange={(e) => set({ sort_order: Number(e.target.value) || 0 })}
            />
          </Field>
        </fieldset>

        {issues.length > 0 && touched && (
          <ul className="banner banner--warn" role="alert">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        )}

        <div className="formfoot">
          <button
            className="btn btn--primary btn--inline"
            disabled={pending || !!issues.length || unchanged}
          >
            {pending ? 'Saving…' : creating ? 'Create temple' : 'Save changes'}
          </button>
          {!creating && (
            <button
              type="button"
              className="btn"
              onClick={() => setDraft(draftFrom(temple))}
              disabled={pending || unchanged}
            >
              Discard changes
            </button>
          )}
        </div>
      </form>

      {!creating && (
        <>
          <section className="card">
            <h2 className="card__title">Photo</h2>
            {(imageUrl || temple.image_key) && (
              <img
                className="photo"
                alt={`${temple.name} as the app shows it`}
                src={imageUrl ?? mediaUrl(temple.image_key as string)}
                onError={(e) => {
                  e.currentTarget.style.display = 'none'
                }}
              />
            )}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) image.mutate(file)
              }}
            />
            <p className="field__hint">
              {image.isPending
                ? 'Uploading…'
                : temple.image_key
                  ? `Stored as ${temple.image_key}.`
                  : 'No photo yet — the app falls back to a generic illustration.'}
            </p>
          </section>

          <section className="card">
            <h2 className="card__title">Offerings</h2>
            <p className="field__hint">
              What this temple charges, and which of the master offerings it
              actually performs, are set in the{' '}
              <Link to="/temples/poojas">pooja catalogue</Link>.
            </p>
          </section>

          <section className="card">
            <h2 className="card__title">Sign-off and listing</h2>
            <div className="row">
              <button
                type="button"
                className="btn"
                disabled={!canReview || review.isPending}
                onClick={() => review.mutate(!temple.reviewed)}
              >
                {temple.reviewed ? 'Withdraw the sign-off' : 'Mark as reviewed'}
              </button>
              {me?.is_owner && (
                <button
                  type="button"
                  className="btn"
                  disabled={listing.isPending}
                  onClick={() => listing.mutate(!temple.active)}
                >
                  {temple.active ? 'Retire from the app' : 'List in the app again'}
                </button>
              )}
            </div>
            <p className="field__hint">
              {canReview
                ? 'Marking a temple reviewed asserts that an astrologer checked its devotional content.'
                : 'Only an owner or a content reviewer may sign a temple off — the role that writes the story cannot certify it.'}
            </p>
            {me?.is_owner && (
              <p className="field__hint">
                Retiring hides a temple from the app without deleting it: bookings,
                visits and festivals still point at this id.
              </p>
            )}
          </section>
        </>
      )}
    </section>
  )
}
