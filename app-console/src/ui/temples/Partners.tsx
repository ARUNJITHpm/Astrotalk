// Partner temples: the microsite, the printable QR, the embeddable widget.
//
// Ported from console.html:503-588, which could register a partner and add a
// festival and then never touch either again. Editing and ending a partnership
// are the additions; the QR and embed panels are the old ones kept because they
// were the useful part.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

import {
  PARTNER_TIERS,
  createPartner,
  listPartners,
  listTemples,
  partnerQrUrl,
  patchPartner,
  type Partner,
} from '../../api/temples'
import { Badge, Field, Problem } from './bits'

function embedSnippet(slug: string): string {
  return `<iframe src="${window.location.origin}/widget/panchangam?temple=${slug}" width="320" height="200" frameborder="0"></iframe>`
}

function Qr({ slug }: { slug: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)

  // Object URLs live until the document unloads unless revoked, so a console
  // left open all day would accumulate one per QR ever opened. The `live` flag
  // covers the panel being closed mid-fetch: without it the URL arrives after
  // the cleanup has already run and is never revoked at all.
  useEffect(() => {
    let live = true
    let objectUrl: string | null = null
    partnerQrUrl(slug).then(
      (u) => {
        if (!live) {
          URL.revokeObjectURL(u)
          return
        }
        objectUrl = u
        setUrl(u)
      },
      (e) => {
        if (live) setError(e)
      },
    )
    return () => {
      live = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [slug])

  if (error) return <Problem error={error} />
  if (!url) return <p className="field__hint">Rendering the poster…</p>
  return (
    <div>
      <img className="qr" src={url} alt={`QR poster for ${slug}`} />
      <p>
        <a className="btn btn--inline" href={url} download={`${slug}-qr.png`}>
          Download the poster
        </a>
      </p>
    </div>
  )
}

function PartnerCard({ partner }: { partner: Partner }) {
  const queryClient = useQueryClient()
  const [panel, setPanel] = useState<'' | 'qr' | 'embed' | 'edit'>('')
  const [form, setForm] = useState({
    contact_name: partner.contact_name,
    contact_phone: '',
    tier: partner.tier,
  })
  const [copied, setCopied] = useState(false)

  const done = () => queryClient.invalidateQueries({ queryKey: ['partners'] })
  const edit = useMutation({
    mutationFn: () =>
      patchPartner(partner.slug, {
        contact_name: form.contact_name,
        // Only sent when retyped: the list never returns the stored number, so
        // an empty box means "unchanged", not "delete it".
        ...(form.contact_phone.trim() ? { contact_phone: form.contact_phone.trim() } : {}),
        tier: form.tier,
      }),
    onSuccess: async () => {
      await done()
      setPanel('')
    },
  })
  const end = useMutation({
    mutationFn: () => patchPartner(partner.slug, { active: !partner.active }),
    onSuccess: done,
  })

  const toggle = (which: typeof panel) => setPanel((p) => (p === which ? '' : which))

  return (
    <article className="card">
      <div className="card__head">
        <div>
          <h3 className="card__title">{partner.slug}</h3>
          <p className="cell__sub">
            {partner.temple_id} · {partner.tier}
            {partner.contact_name ? ` · ${partner.contact_name}` : ''}
          </p>
        </div>
        <Badge on={partner.active} yes="Live" no="Ended" />
      </div>

      <div className="row row--wrap">
        <a className="btn btn--inline" href={`/t/${partner.slug}`} target="_blank" rel="noreferrer">
          Microsite ↗
        </a>
        <button className="btn" onClick={() => toggle('qr')}>
          QR poster
        </button>
        <button className="btn" onClick={() => toggle('embed')}>
          Widget embed
        </button>
        <button className="btn" onClick={() => toggle('edit')}>
          Edit
        </button>
        <button className="btn" disabled={end.isPending} onClick={() => end.mutate()}>
          {partner.active ? 'End the partnership' : 'Restore it'}
        </button>
      </div>

      <Problem error={end.error} />

      {panel === 'qr' && <Qr slug={partner.slug} />}

      {panel === 'embed' && (
        <div>
          <p className="field__hint">Paste this on the temple's own website:</p>
          <pre className="snippet">{embedSnippet(partner.slug)}</pre>
          <button
            className="btn"
            onClick={() => {
              void navigator.clipboard?.writeText(embedSnippet(partner.slug))
              setCopied(true)
            }}
          >
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      )}

      {panel === 'edit' && (
        <div className="grid3">
          <Field label="Contact name">
            <input
              value={form.contact_name}
              onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
            />
          </Field>
          <Field label="Contact phone" hint="Leave empty to keep the stored number.">
            <input
              value={form.contact_phone}
              placeholder="unchanged"
              onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
            />
          </Field>
          <Field label="Tier">
            <select
              value={form.tier}
              onChange={(e) => setForm({ ...form, tier: e.target.value })}
            >
              {PARTNER_TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <div className="formfoot">
            <Problem error={edit.error} />
            <button
              className="btn btn--primary btn--inline"
              disabled={edit.isPending}
              onClick={() => edit.mutate()}
            >
              Save
            </button>
          </div>
        </div>
      )}
    </article>
  )
}

export function Partners() {
  const queryClient = useQueryClient()
  const partners = useQuery({ queryKey: ['partners'], queryFn: listPartners })
  const temples = useQuery({ queryKey: ['temples'], queryFn: listTemples })
  const [form, setForm] = useState({
    temple_id: '',
    slug: '',
    contact_name: '',
    contact_phone: '',
    tier: 'free',
  })

  const register = useMutation({
    mutationFn: () => createPartner({ ...form, slug: form.slug.trim() }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['partners'] })
      setForm({ ...form, slug: '', contact_name: '', contact_phone: '' })
    },
  })

  const ready = form.temple_id && form.slug.trim()

  return (
    <section className="page">
      <h1 className="page__title">Partners &amp; QR</h1>
      <p className="page__lede">
        A partner temple gets a public page at <code>/t/&lt;slug&gt;</code>, a printable
        QR poster pointing at it, and a panchangam widget for its own website.
      </p>

      <details className="card">
        <summary>Register a partner temple</summary>
        <div className="grid3">
          <Field label="Temple">
            <select
              value={form.temple_id}
              onChange={(e) => setForm({ ...form, temple_id: e.target.value })}
            >
              <option value="">Choose…</option>
              {(temples.data ?? []).map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} — {t.district}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Slug" hint="Becomes the public URL. One partner per temple.">
            <input
              value={form.slug}
              placeholder="guruvayur"
              onChange={(e) => setForm({ ...form, slug: e.target.value })}
            />
          </Field>
          <Field label="Tier">
            <select value={form.tier} onChange={(e) => setForm({ ...form, tier: e.target.value })}>
              {PARTNER_TIERS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Contact name">
            <input
              value={form.contact_name}
              onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
            />
          </Field>
          <Field label="Contact phone">
            <input
              value={form.contact_phone}
              onChange={(e) => setForm({ ...form, contact_phone: e.target.value })}
            />
          </Field>
        </div>
        <Problem error={register.error} />
        <button
          className="btn btn--primary btn--inline"
          disabled={!ready || register.isPending}
          onClick={() => register.mutate()}
        >
          Register
        </button>
      </details>

      <Problem error={partners.error} />

      {partners.isLoading && <p className="empty">Loading…</p>}
      {!partners.isLoading && !(partners.data ?? []).length && (
        <p className="empty">No partner temples yet.</p>
      )}
      {(partners.data ?? []).map((p) => (
        <PartnerCard key={p.id} partner={p} />
      ))}
    </section>
  )
}
