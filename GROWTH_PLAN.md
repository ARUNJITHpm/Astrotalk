# Tara Growth Plan — Partwise Implementation Roadmap

How the five growth initiatives (Content Engine, Virality, Temple Partnerships,
Astrologer Platform, White-label SaaS) map onto the existing modular monolith.
Each part lists the modules touched, new tables, new endpoints, and external
integrations — written so any part can be picked up and coded independently
once its dependencies (see "Build order") are done.

**Existing foundations this plan reuses:**
- `content/` — already generates a daily panchangam message via LLM (`ContentService.generate_daily_message`).
- `whatsapp/` — consent (opt-in/opt-out), 24h send throttle, `publish_to_channel` (mock BSP), `tasks.send_daily_message`.
- `commerce/`, `community/`, `notifications/` — empty stubs with routers already mounted.
- `astrology_engine/` — real Swiss Ephemeris panchangam/natal/dasha/porutham.
- `temples/` — 53 temples with verified coordinates, festival data.
- `admin/` — token-gated API + dashboard; `platform/metrics.py`.
- Razorpay + WhatsApp BSP config fields already in `platform/config.py` (mocked).

---

## Part 0 — Platform enablers (do first, everything depends on these)

The prod host (HF Spaces Docker + Neon) has no Redis/Celery, no Mongo, and an
ephemeral filesystem. Three gaps must close before any growth feature works in
production:

1. **Scheduling without Celery.** Add token-gated "cron endpoints"
   (e.g. `POST /content/run-daily` with `X-Cron-Token`), triggered by an
   external scheduler — GitHub Actions cron (free, already have the repo) or
   cron-job.org. Bonus: the ping keeps the HF Space awake each morning.
   - New: `cron_token` setting in `config.py`; a small
     `app/platform/cron_auth.py` dependency reused by every scheduled endpoint.
2. **Media/object storage.** Generated card images, report PDFs, and astrologer
   logos can't live on the Space's disk. Add a `platform/storage.py` with a
   `Storage` interface: local-disk impl for dev (`MOCK_STORAGE=true`), and
   Cloudflare R2 (S3-compatible, free 10 GB) for prod.
3. **Real migrations (Alembic).** `create_all` won't alter existing tables
   (already bitten by the phone column). Parts 3–5 add columns to existing
   tables (users, temples), so introduce Alembic now:
   `alembic init`, autogenerate baseline from current models, wire
   `alembic upgrade head` into the Docker entrypoint before uvicorn starts.
4. **Card image renderer.** One shared `app/platform/cards.py` using Pillow:
   takes (template, texts, branding) → PNG. Used by Parts 1, 2, and 3.
   Ship Malayalam-capable fonts (Noto Sans Malayalam) in the Docker image.

*Effort: ~3–4 sessions. No user-visible features, but everything after this is
pure feature work.*

---

## Part 1 — Content Engine (daily morning content across platforms)

**Goal:** every morning, one generated "content pack": Instagram Reel script +
card, YouTube Short script, Facebook post, and one value-driven WhatsApp
Channel message. Human-reviewed at first, automated later.

**Module:** extend `content/` (service + templates already exist).

**New tables** (Postgres):
- `content_posts` — id, date, platform (`ig_reel|yt_short|fb_post|wa_channel`),
  kind (`panchangam|nakshatra|festival|tip`), body, media_key (storage key of
  rendered card), status (`draft|approved|published|failed`), published_at,
  external_id (post ID returned by the platform API).

**Pipeline** (`content/pipeline.py`):
1. Gather the day's raw material: panchangam (astrology_engine), festivals
   today/upcoming (temples seed data), nakshatra of the day, one knowledge
   nugget (knowledge corpus).
2. Per-platform generation via the existing LLM path (Sarvam-105B) with
   platform-specific templates in `content/templates.py` — a Reel script is
   30s spoken Malayalam; a WA Channel message is short text + one actionable
   tip; FB post is longer-form.
3. Every piece passes the existing `tone_safety` screen before it can be
   approved.
4. Render the day's card via `platform/cards.py` (1080×1350 feed +
   1080×1920 story sizes).

**Endpoints:**
- `POST /content/run-daily` (cron-token) — generate today's pack as drafts.
- `GET /content/posts?date=` / `POST /content/posts/{id}/approve` /
  `POST /content/posts/{id}/publish` (admin-token).

**Admin UI:** new "Content" tab in `/admin` — today's pack, preview cards,
edit text inline, approve, publish, see publish status.

**Publishing adapters** (`content/publishers.py`, each behind a `MOCK_*` flag,
rolled out in this order):
1. **WhatsApp Channel** — reuse `whatsapp.service.publish_to_channel`; wire the
   real BSP (Gupshup) call. Easiest, highest value for the Kerala audience.
2. **Facebook Page + Instagram** — Meta Graph API (one app, one token).
   Reels upload = video; start with image posts + card, add Reels once a
   video pipeline exists (see stretch).
3. **YouTube Shorts** — YouTube Data API v3. Needs video too, so same stretch.
- *Stretch:* auto-video from card + TTS voiceover (Sarvam has Malayalam TTS) +
  ffmpeg slideshow → real Reels/Shorts without a human editor.

**Share-for-premium hook:** after a user gets value in chat, show "share Tara
with 3 friends → unlock your detailed report" — the mechanics live in Part 2
(referrals) and Part 5 (premium report product); the content engine just
provides the shareable assets.

*Effort: ~4–6 sessions to reviewed-manual publishing; +2–3 per platform API.*

---## Part 2 — Virality (shareable cards + referral loop)

**Goal:** every good moment inside Tara can leave Tara as a branded image, and
sharing is rewarded with premium reports.

**Modules:** `content/` (cards), `identity/` (referrals), web UI.

**Features:**
1. **Personal share cards.** After a chat reading / porutham result / daily
   nakshatra insight, a "Share" button renders a card via `platform/cards.py`:
   the insight in Malayalam, Tara branding, and a QR/deep link. Endpoint:
   `POST /content/cards` (session auth) → returns storage URL. Web UI: share
   button using the Web Share API (native share sheet on mobile → WhatsApp
   Status / Instagram Stories directly).
2. **Public daily cards.** `GET /content/cards/daily/{nakshatra}` — cacheable,
   no auth, 27 cards/day generated by the Part 1 cron. These are the WhatsApp
   Status / Stories fodder.
3. **Link landing with OG tags.** `GET /s/{card_id}` — a tiny HTML page with
   `og:image` = the card, so shared links unfurl beautifully in WhatsApp; page
   CTA = "Get your own reading" → `/ui/login?ref=...`.
4. **Referral loop.** New table `referrals` — code (per user), referred_user_id,
   status, reward_granted. Registration accepts `?ref=` code; when N referred
   users complete onboarding (birth chart created = real activation, not just
   signup), the referrer's premium report unlocks (grant recorded in
   `commerce`, Part 5).
5. **Metrics.** Extend `platform/metrics.py` + admin dashboard: cards created,
   shares clicked (via `/s/{id}` hits), referral conversion funnel.

*Effort: ~3–4 sessions (renderer exists from Part 0; referral reward needs
Part 5's grant table, but can stub as a flag on the user until then).*

---

## Part 3 — Temple Partnerships (QR codes, festival updates, panchangam widgets)

**Goal:** temples become distribution partners — a QR at the temple opens a
useful page, not spam.

**Modules:** extend `temples/`, use `notifications/` (first real feature for
that stub), `whatsapp/` consent framework.

**New tables:**
- `temple_partners` — temple_id, slug, contact_name, contact_phone, tier
  (`free|partner`), branding fields, active.
- `temple_subscriptions` — user_id, temple_id, channel (`whatsapp|web`),
  created_at (rides on the existing WAConsent opt-in).

**Features:**
1. **Temple microsite.** `GET /t/{slug}` — mobile-first public page per partner
   temple: today's panchangam (astrology_engine), upcoming festivals, vazhipadu
   list (knowledge corpus already has 30), timings, and an "Ask Tara" CTA into
   `/ui`. Track visits with `?src=qr`.
2. **QR generation.** Admin endpoint `POST /admin/temples/{id}/qr` → QR PNG
   (python `qrcode` lib) pointing at `/t/{slug}?src=qr`, sized for print.
3. **Festival update notifications.** `notifications/` gets its first real job:
   a cron endpoint `POST /notifications/run-festivals` that finds festivals
   T-3 days at subscribed temples and sends a WhatsApp template message to
   opted-in subscribers (consent + 24h throttle already enforced by the
   whatsapp module — this is the anti-spam guarantee that differentiates from
   group spamming).
4. **Embeddable panchangam widget.** `GET /widget/panchangam?temple={slug}` —
   a self-contained iframe page temples can embed on their own websites;
   Tara-branded footer link. One static JS snippet doc for their webmasters.
5. **Partner console (lite).** A section in `/admin` first; graduates to a
   partner-facing login in Part 4's multi-tenant work.

*Effort: ~4–5 sessions. Depends on Part 0 (cron, Alembic); notification sends
depend on real BSP wiring from Part 1 step 1.*

---

## Part 4 — Astrologer Platform (white-label AI assistant, bookings, CRM)

**Goal:** an astrologer gets their own branded Tara — their name/logo/persona
on the assistant, a booking system, and a customer list. This is the biggest
lift because it introduces **multi-tenancy**; do it after Parts 1–3 have
proven distribution.

**Modules:** new `orgs/` module (tenancy core), extend `identity/`, `chat/`,
`commerce/`, new astrologer-facing UI.

**Step 4a — Tenancy core:**
- `orgs` table — id, handle (URL slug), name, logo_key, theme colors,
  persona_overlay (text merged into the tone_safety system persona), plan,
  owner_user_id.
- `users.org_id` (nullable — null = Tara-direct user). Alembic migration.
- Resolution: `/a/{handle}/ui` serves the same chat UI with org branding
  injected; `POST /chat/message` reads org from the user → persona overlay +
  org-scoped history. **Rule: tone_safety guardrails are NOT overridable by
  the overlay** — persona adds flavor, never removes safety.

**Step 4b — Booking system:**
- Tables: `availability_slots` (org_id, weekday, start, end, duration_min,
  price), `bookings` (org_id, user_id, slot datetime, status
  `pending|confirmed|completed|cancelled`, payment_id, meeting_link/phone).
- Endpoints under `/orgs/{handle}/booking/...`; payment via Part 5's Razorpay
  order flow; confirmation + reminder via WhatsApp template (consent flow
  exists).
- Booking UI: a page on the org's white-label site; astrologer manages slots
  in their dashboard.

**Step 4c — Customer management (CRM-lite):**
- Astrologer dashboard (`/a/{handle}/dashboard`, org-owner auth): customer
  list, their birth charts (computed by the engine — the astrologer's prep
  work done for them), booking history, private notes
  (`customer_notes` table), chat transcript access **only with explicit
  customer consent flag**.
- Reuse the admin dashboard's patterns (auth header, fetch-render JS) — it's
  the same shape of app scoped to one org.

*Effort: ~8–12 sessions across the three steps. 4a is the prerequisite; 4b and
4c can proceed in parallel after it.*

---

## Part 5 — Commerce & White-label SaaS subscriptions

**Goal:** the money layer — premium reports for users (funds Part 2's
share-to-unlock), and subscription billing for astrologers (funds Part 4).

**Module:** `commerce/` (stub exists, Razorpay config fields exist).

**Step 5a — Payments core:**
- Real Razorpay integration behind existing `mock_razorpay`: create order,
  webhook `POST /commerce/webhook/razorpay` (signature-verified), payment
  records table `payments` (user_id, org_id, product, amount, razorpay ids,
  status).
- `entitlements` table — user_id/org_id, product_key, granted_by
  (`purchase|referral|admin`), expires_at. Referral rewards (Part 2) and
  purchases both land here; feature code checks entitlements, never payment
  rows.

**Step 5b — Premium user products:**
- Detailed porutham PDF report (porutham.py + the reportlab pattern already
  used for the dev-guide PDFs), full dasha report, yearly forecast.
  Generated server-side, stored in R2, delivered as a download link + optional
  WhatsApp doc message.
- Unlock paths: one-time purchase (₹) or referral reward.

**Step 5c — SaaS subscriptions (white-label plans):**
- Razorpay Subscriptions for org plans (`starter|pro`), plan gates in `orgs`
  (customer cap, booking on/off, custom domain later).
- Billing status page in the astrologer dashboard; dunning = plan features
  soft-lock on failed renewal, data never deleted.

*Effort: 5a ~2–3 sessions, 5b ~2–3, 5c ~3–4. 5a can start any time after
Part 0; 5b unblocks Part 2's reward; 5c only matters once Part 4a exists.*

---

## Build order & dependency graph

```
Part 0 (enablers: cron endpoints, storage, Alembic, card renderer)
  ├── Part 1  Content Engine  ──── needs cron + cards; BSP wiring feeds Part 3 sends
  ├── Part 2  Virality        ──── needs cards; reward needs 5a entitlements
  ├── Part 5a Payments core   ──── independent after Part 0
  │     └── 5b Premium reports (completes Part 2's loop)
  ├── Part 3  Temple partners ──── needs cron; WA sends need Part 1's BSP
  └── Part 4  Astrologer platform (4a tenancy → 4b booking + 4c CRM)
        └── 5c SaaS subscriptions
```

**Recommended sequence:** 0 → 1 → 2 + 5a (parallel) → 5b → 3 → 4a → 4b/4c → 5c.
Rationale: content + virality compound daily from day one and need no sales
effort; payments early so the referral loop actually pays off; temples next
(distribution with a real-world moat); the SaaS platform last — it's the
biggest build and is far easier to sell once Tara has visible daily content,
users, and temple presence.

**Cross-cutting rules for every part:**
- Every external integration gets a `MOCK_*` flag defaulting to `true`
  (existing convention) so dev/tests stay hermetic.
- Every send-to-user path goes through consent + throttle (whatsapp module) —
  no exceptions, this is the "not spamming groups" promise.
- Every generated public text passes the tone_safety screen.
- Every part lands with tests following the existing `tests/test_*.py`
  patterns, and metrics counters in `platform/metrics.py` + an admin
  dashboard panel, so growth is measurable from the first day of each feature.
