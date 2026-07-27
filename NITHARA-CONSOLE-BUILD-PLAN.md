# Nithara Operator Console — Partwise Build Plan

> Builds the back office the temple-first product never got.
> **Backend:** new admin routes live in the **owning** `app/modules/*` — no
> god-module (`docs/AGENTS.md` module-ownership rule).
> **Frontend:** a new **desktop-first React + Vite + TypeScript** app in
> `/app-console`, separate from the consumer PWA in `/app-nithara`.
>
> Each **Part** below is a self-contained prompt. Paste it into Claude Code and
> let it run; parts are ordered so each builds on the last.

---

## Why this exists

`main` became Nithara on 2026-07-25 and the consumer PWA at `/` is complete
through Part 8 of [`NITHARA-BUILD-PLAN.md`](NITHARA-BUILD-PLAN.md). The back
office never moved with it — [`NITHARA-UI-ENDPOINT-AUDIT.md`](NITHARA-UI-ENDPOINT-AUDIT.md)
§5 explicitly parked the admin dashboard as out of scope for v1.

Today an operator **cannot add a temple, edit a pooja price, onboard a real
astrologer, or see a single booking**.

### The blocker (verified, 2026-07-26)

**There is no `temples` table and no `astrologers` table.**

| Thing | Where it actually lives | Write API |
|---|---|---|
| 53 temples | `temples/seed_data.py` (621 ln), bound in memory at `temples/service.py:96` | **none** |
| 28 astrologers | `astrologers/seed_data.py` — explicitly "DUMMY DATA", ids like `kozhikode-astro-1` | **none** |
| Pooja catalogue | `DEFAULT_POOJAS`, a 4-item constant at `temples/service.py:59` | **none** |
| App feed | `FEED_ITEMS`, 3 hardcoded items in `content/feed.py:17` | **none** |
| ₹15 service fee | `SERVICE_FEE_PAISE`, `bookings/service.py:27` | **none** |

Only relationship tables exist (`temple_partners`, `temple_subscriptions`,
`temple_visits`, `temple_festivals`, `astro_bookings`, `pooja_bookings`).

So no console UI can create or edit a temple until the directory leaves
`seed_data.py`. **That ordering drives this plan: Parts 1–3 before anything
visible.**

### Existing pages this replaces

- `/admin` (`app/web/admin.html` + `admin.js`, 1,369 ln) — Tara-era: LLM
  token/cost accounting, chat-transcript explorer, social content pack. Has
  **no temple, pooja, booking or astrologer panel at all**.
- `/console` (`app/web/console.html`, 684 ln, JS inlined) — models
  temple-as-distribution-channel (microsite, QR, widget, festival blast), not
  temple-as-marketplace. Its Astrologer panel is a static "soon" card.

`app/web/ui/` is **NOT** in scope — it is the white-label B2B surface
(`/a/{handle}/ui`, `/login`, `/dashboard`) and deleting it breaks `tests/orgs/`.

---

## Ground rules (apply to every part)

- **Stay in the owning module.** Temple admin routes go in
  `app/modules/temples/router.py`, astrologer routes in `astrologers/`, and so
  on. Never reach into another module's tables.
- **Reuse the existing gate.** `AdminGuard` (`app/platform/admin_auth.py:82`)
  is the admin dependency. Do not invent a second auth scheme.
- **Migrations need human approval** (`docs/AGENTS.md`). Stop and ask before
  running one. Use `sa.DateTime(timezone=True)` on every timestamp column.
  Current head: `f6a7b8c9d0e1`.
- **The existing test suite is the contract.** Where a part refactors a
  service, `tests/<module>/` must pass **unchanged** — that is the proof.
- **Tests.** Every backend part adds pytest under `tests/<module>/`. Every
  frontend part adds a Vitest test.
- **Commit per `AGENTS.md`:** one logical change per commit, Conventional
  Commits, before switching parts.

## Two product decisions needed before Part 1

1. **Import the 53 temples as `reviewed=False`?** Every entry currently carries
   `"reviewed": True`, while the file's own docstring (`seed_data.py:3`) says
   *"DRAFT DATA — NOT reviewed. Every entry is `reviewed=False`"*. That flag is
   served to clients via `TempleSuggestion.reviewed`. Importing as `False` makes
   the console's review queue meaningful but changes what `/temples/suggest`
   returns today.
2. **Hide the 28 dummy astrologers (`active=False`) on import?** The consumer
   app already refuses to render them (`app-nithara/src/screens/Astro.tsx:128`).

---

# BACKEND

## Part 1 — Temples: out of `seed_data.py`, into Postgres  ✅ DONE (`dcfac5d`)

> Shipped as: `Temple` model, `temples/registry.py` (sync snapshot + seed
> fallback), `TemplesService._temples` as a property, migration
> `a7b8c9d0e1f2`, and `tests/temples/test_temple_registry.py`.
> **The migration has not been run against a real database** — still needs your
> approval. Parts 2 and 3 follow the same registry pattern.

```
Read app/modules/temples/{seed_data.py,service.py,models.py,router.py} and
migrations/versions/ for the current head (f6a7b8c9d0e1).

In app/modules/temples/, add DB-backed temple storage:
- models.py: `Temple` carrying every TempleSeed field (id, name, name_ml, deity,
  district, town, lat, lng, famous_for, vazhipadu, reviewed, story, story_ml,
  rating, reviews) PLUS `active`, `image_key`, `updated_at`. Add `TempleTiming`
  (per-temple hours + display strings; today DEFAULT_TIMINGS at service.py:51
  is shared by all 53).
- One Alembic revision that creates the tables AND imports SEED_TEMPLES in the
  same upgrade, so the app keeps serving on first deploy. Ask before running it.
  Honor the `reviewed` decision above.
- service.py: TemplesService reads from the DB instead of binding SEED_TEMPLES
  in __init__ (service.py:96). KEEP EVERY PUBLIC METHOD SIGNATURE IDENTICAL —
  list_temples, get_temple, suggest, pooja_catalogue, the lot.
- Keep seed_data.py as the import fixture; stop importing it at runtime.

Done when `pytest tests/temples` passes UNCHANGED and GET /temples,
/temples/{id}, /temples/suggest return what they returned before.
```

## Part 2 — Astrologers: out of `seed_data.py`, into Postgres  ✅ DONE (`48c1d71`)

> Shipped as: `Astrologer` model, `astrologers/registry.py`, `_astrologers`
> as a property, migration `b8c9d0e1f2a3`, and
> `tests/astrologers/test_astrologer_registry.py`. `availability` stayed a
> JSON column rather than its own table — see the progress log for why.

```
Read app/modules/astrologers/{seed_data.py,service.py,models.py,router.py}.

Same move as Part 1:
- models.py: `Astrologer` (id, name, name_ml, district, town, lat, lng,
  specialties, experience_years, languages, rating, bio_ml) PLUS `active`,
  `price_paise_per_min` (the UI audit expects ₹/min; the model has no price at
  all) and `photo_key`. Add `AstrologerAvailability` — consult windows are
  currently baked into _morning_windows()/_evening_windows() (seed_data.py:97).
- Alembic revision + data import of SEED_ASTROLOGERS. Ask before running.
  Honor the `active=False` decision above.
- service.py:69 reads from the DB. Public method signatures unchanged.

Done when `pytest tests/astrologers` passes UNCHANGED.
```

## Part 3 — Pooja catalogue + settings  ✅ DONE (`287a8fe`)

> Shipped as: `Pooja` + `TemplePooja` + `BookingSettings`, catalogue resolution
> inside the temple registry load, migration `c9d0e1f2a3b4` (applied to
> production). **Parts 1–3 complete — the data-migration block is closed and
> Parts 4–7 can start.**

```
Read temples/service.py:59 (DEFAULT_POOJAS) and bookings/service.py:27
(SERVICE_FEE_PAISE) and :55-60 (server-side re-pricing).

In app/modules/temples/:
- A master `Pooja` table (key, name, name_ml, description, amount_paise,
  lead_days, active), seeded from DEFAULT_POOJAS.
- A `TemplePooja` table overriding the master per temple (amount, lead_days,
  active). The override slot already exists in the schema (TempleSeed.poojas,
  read at service.py:209) but ZERO of the 53 temples use it — every temple in
  the product currently serves the identical 4-item ₹51–₹1250 list.
- pooja_catalogue() resolves master → per-temple override.
- A small key/value settings table (or a settings row) for the ₹15 service fee,
  read by bookings/service.py instead of the constant.

Pricing MUST stay server-side truth — BookingsService.create re-prices from the
catalogue so a client can never send an amount. Do not weaken that.

Alembic revision + import. Ask before running. `pytest tests/bookings` unchanged.
```

## Part 4 — Operator accounts & roles  ✅ DONE (`774cb73`, `49e1d72`)

> **As built, one deviation from A below.** Operators are **not** `users` rows.
> That table requires `dob`, `birth_place`, `lat`, `lng` and `tz`, all NOT NULL,
> because it models a devotee with a natal chart — a temple clerk cannot be one.
> So `operators` / `operator_roles` / `operator_sessions` / `operator_invites`
> are their own tables, with password hashing reused from `identity.service`
> rather than reimplemented. Accounts are **invite-only** (owner invites by
> email or mobile; nobody self-registers). See `NITHARA-CONSOLE-PROGRESS.md`.

```
Today there is exactly ONE privilege level. The owner, a per-temple operator and
a content reviewer all present the same X-Admin-Token and can do everything —
including editing every temple and reading every user's chat transcript. Build
the role model FIRST so Parts 5-8 are written role-aware; retro-fitting scopes
onto finished endpoints means touching all of them twice.

--- A. Reuse identity; do NOT build a second auth stack ---
Operators are `users` rows. Sessions, password hashing, reset and the bearer
token already exist in app/modules/identity — a parallel operator login is
exactly the duplication AGENTS.md warns about. Add ONE table:

  operator_roles(id, user_id, role, temple_id NULL, created_at)
    unique (user_id, role, temple_id)

  role ∈ {owner, temple_admin, content_reviewer, support}
  temple_id scopes the row. NULL = unscoped (an owner, or a reviewer over all
  content). A temple_admin ALWAYS has a temple_id; one row per temple they run,
  so a person managing three temples has three rows.

--- B. The guard ---
In app/platform/admin_auth.py, keep require_admin working (it is the coarse
gate) but add a role-aware dependency that RETURNS a context rather than
returning None:

  class Operator: user_id, roles: set[str], temple_ids: set[str], is_owner: bool
      def can_edit_temple(self, temple_id) -> bool
      def visible_temple_ids(self) -> set[str] | None   # None = all

  require_operator(*roles) -> Operator     # 401 unauthenticated, 403 wrong role

An X-Admin-Token caller resolves to a synthetic owner Operator, so scripts and
the existing console keep working unchanged. A bearer session resolves to that
user's rows; a phone in `admin_phones` still implies owner (that is the second
door, and the ONLY door once ADMIN_TOKEN is the sole token).

--- C. Retire the chargemod backdoor, in this same part ---
- app/platform/admin_auth.py:40 accepts the literal "chargemod"
  UNCONDITIONALLY. Remove it; the configured admin_token becomes the only token.
- app/modules/admin/router.py:50 accepts admin/chargemod at POST /admin/login,
  and _admin_token() at :36 falls back to the literal. Remove both.
- app/web/admin.html:363 PRINTS "admin / chargemod" on the login screen, and
  admin.js:68-74 prefills it. Delete.
- 8 test files send X-Admin-Token: chargemod. Do NOT edit them one by one — add
  a root tests/conftest.py that sets settings.admin_token for the session. Tests
  then configure a token explicitly, exactly as production does.

⚠️ ADMIN_TOKEN IS NOT YET SET ON THE SPACE (owner, 2026-07-27). Commit this,
but do NOT push to the `hf` remote until they confirm the secret exists.
Deploying it without ADMIN_TOKEN closes the token door entirely; only an
admin_phones bearer session would still get in.

--- D. Seeding the first operator ---
A CLI (scripts/grant_role.py) that grants a role to a phone, so the first owner
exists without a chicken-and-egg. Idempotent. Never a route.

Tests in tests/platform/ (the guard: each role, scope hit and miss, token→owner,
403 vs 401) and tests/admin/ (login without the backdoor).
```

## Part 5 — Temple admin API  ✅ DONE (`10bfb16`)

> **As built.** The image route takes raw bytes rather than a multipart upload
> (`python-multipart` is not a pinned dependency), and `reviewed` is gated on
> `owner`/`content_reviewer` rather than the temple's own admin — see
> `NITHARA-CONSOLE-PROGRESS.md`. The pre-existing partner routes had to be
> rescoped in the same commit.

```
Add operator-gated routes to app/modules/temples/router.py. Gate with
require_operator("owner", "temple_admin") from Part 4 and enforce the scope:
a temple_admin may only touch temples in operator.temple_ids — check it in the
route, and 403 otherwise. Schemas in temples/schemas.py.

- POST/PATCH/DELETE temple records (DELETE = soft, flip `active`).
- PATCH /{id}/timings — per-temple hours + display strings.
- PATCH /{id}/review — flip `reviewed`. The field is served to clients but
  nothing can currently set it.
- POST /{id}/image — temple photo via app/platform/storage.py.
- Per-temple pooja override CRUD + master pooja CRUD (Part 3 tables).
- PATCH/DELETE for partners and festivals: both are append-only today
  (router.py:91, :120) — a wrong festival date can never be fixed, and
  TemplePartner.active (models.py:43) has no route that writes it.

Register new literal paths BEFORE the /{temple_id} catch-all (see the comment
at router.py:152-154). Tests in tests/temples/ covering the 401-without-token
path, happy path, and validation failures.
```

## Part 6 — Astrologer admin API
```
Add operator-gated routes to app/modules/astrologers/router.py, owner-only
(require_operator("owner")) — a temple admin has no business editing the
astrologer directory. The module does not import AdminGuard at all today: all
six routes are public reads or user-scoped bookings.

- POST/PATCH astrologer records; PATCH /{id}/active.
- PUT /{id}/availability — replace the baked-in weekly windows.
- POST /{id}/photo.
- GET /{id}/bookings — an astrologer cannot see their own diary today.
- PATCH /astro-bookings/{id} — set confirmed|completed|no_show. Today only the
  booking's own user can cancel it (router.py:56).

Tests in tests/astrologers/.
```

## Part 7 — Bookings operator API
```
The biggest gap: operators can currently see NOTHING. app/modules/bookings/
has exactly two routes, both hard-scoped to the caller (router.py:31, :45).

- Extend the state machine FIRST: BOOKING_STATES = ("wait","ok")
  (bookings/models.py:21) has no cancelled / completed / refunded. Nothing but
  the payment reconciler (service.py:106-113) ever writes state. Add the terminal
  states and an explicit transition guard. Alembic revision — ask before running.
- GET operator list: filters (temple_id, state, pooja_key, date range, ref,
  user phone) + pagination + sort. SCOPE IT: a temple_admin sees only bookings
  for their own temples (operator.visible_temple_ids()), never the whole queue.
  This is the endpoint where a missing scope check leaks the most.
- GET detail by id and by ref, joined to the user, member name/nakshatram, and
  the commerce payment.
- PATCH /{id}/status; cancel and refund (no cancel path exists for poojas at all
  today, for operator OR user); operator notes.
- GET /temples/{id}/bookings — the temple worklist ("what do we perform
  tomorrow"), grouped by star day.
- CSV export for settlement.

Refunds touch commerce/Razorpay — `AGENTS.md` requires human approval. Stop and
ask before wiring the refund call; land everything else first.
Tests in tests/bookings/.
```

## Part 8 — Users, payments, feed, and auth hardening
```
--- Users (identity) ---
GET /admin/users — paginated, searchable by phone/name. Today the only operator
view is GET /admin/users-chats (admin/router.py:60), which shows ONLY users who
have chat history; a user who never chatted is invisible. Add user detail
(bookings, chart, family, entitlements) and disable/export.
NEVER put birth data in a URL or a log (GUARDRAILS §4).

--- Payments (commerce) ---
GET /admin/payments (filter status/date), payment detail, and
POST /admin/entitlements — `granted_by="admin"` is a declared value
(commerce/models.py:23) with no route that can produce it.

--- Feed (content) ---
CRUD over the app feed, replacing the hardcoded FEED_ITEMS list
(content/feed.py:17). Its own docstring flags this as pending.

--- Auth hardening (do this part regardless of the rest) ---
- [DONE, commit e224cac] AdminGuard on GET /whatsapp/waha-status and /waha-qr.
- Retire the literal "chargemod" accepted unconditionally at
  admin_auth.py:40 and by POST /admin/login (admin/router.py:50).
  CAUTION: this can lock the owner out of the live HF Space if ADMIN_TOKEN is
  not set there. Confirm the Space has an ADMIN_TOKEN secret and that login
  works with it BEFORE removing the fallback, and ship the two changes in
  separate commits so the removal can be reverted on its own.
```

---

# FRONTEND  (React + Vite + TypeScript · desktop)

## Part 9 — `app-console/` scaffold: shell, sidebar, auth, dashboard
```
Create a new frontend app in /app-console (sibling to app/ and app-nithara/).
Do NOT touch app-nithara.

Stack: Vite + React + TypeScript, react-router, @tanstack/react-query, Vitest.
DELIBERATELY NOT: vite-plugin-pwa, Capacitor, react-i18next, the 432px phone
frame. This is a desktop tool for operators, in English.

- Adapt the shape of app-nithara/src/api/client.ts, but send X-Admin-Token.
  Reuse the existing dual-credential scheme (admin_auth.py accepts either
  X-Admin-Token or a Bearer session whose phone is in admin_phones).
- Login screen against POST /admin/login. Do NOT prefill any credential —
  console.html:117 hardcodes a personal email and admin.html:363 prints the
  password on screen; neither carries over.
- Login is a normal identity login (phone + password) that returns the bearer
  token; the console then reads the caller's roles. NOT a shared password.
- The left sidebar is ROLE-AWARE: render only the sections the caller's roles
  allow, and guard the routes too — hiding a nav item is not access control.
  A temple_admin sees Temples (theirs) + Bookings (theirs) and nothing else.
- The routing skeleton for every section in the IA below, unbuilt ones stubbed.
- Dashboard: today's bookings, check-ins, payments, new users, alerts.
- /app-console/dist is already covered by the root .gitignore `dist/` rule.
```

**Sidebar information architecture** — build order is Parts 10 → 13:

```
OVERVIEW    Dashboard        bookings today, check-ins, payments, new users, alerts

TEMPLES     All temples      list/search by district + deity, reviewed + active badges
            Temple editor    identity, bilingual story, location, timings, images, review
            Pooja catalogue  master offerings + per-temple overrides and pricing
            Partners & QR    registration, microsite, QR poster, embed widget   [carried]
            Festivals        add / edit / delete dated festivals

BOOKINGS    Pooja bookings   the queue: filters, ref lookup, status, notes, export
            Temple worklist  "what do we perform tomorrow", grouped by star day
            Consults         astrologer bookings + diary
            Payments         orders, status, refunds, manual entitlement grants

PEOPLE      Users            search by phone/name → bookings, chart, family, entitlements
            Astrologers      onboard real practitioners, availability, pricing, active
            Operators        grant/revoke roles, scope a temple admin to temples
            Engagement       check-ins, streaks, milestones

CONTENT     App feed         CRUD over what the app's notices rail shows
            Daily pack       [carried — dedupe the TWO existing implementations]
            Studio           [carried]
            Share cards      [carried]

ASTROLOGY   Panchangam       date explorer                                      [carried]
            Temple suggest   concern → temples tester                           [carried]

CHANNELS    WhatsApp sim     [carried from /whatsapp]
            Notifications    nakshatram reminders, festival runs                [carried]

SYSTEM      Integrations     health + live/mock status pills                    [carried]
            Chat explorer    read-only, for support                             [carried]
            Org tenants      white-label                                        [carried]
            Settings         service fee, admin token, roles
```

## Part 10 — Temples section
```
Build the TEMPLES group against the Part 5 API:
- All temples: searchable/filterable table (district, deity, reviewed, active).
- Temple editor: every field incl. the bilingual story pair, map-picker for
  lat/lng, timings, image upload, and the review toggle.
  Malayalam fields need a proper input — the operator will paste ML script.
- Pooja catalogue: master list, plus per-temple override with pricing.
- Partners & QR + Festivals: port from console.html:503-588, adding the
  edit/delete the old page never had.

Vitest tests for the list filters and the editor's save path.
```

## Part 11 — Bookings section
```
Build the BOOKINGS group against the Part 7 API. This is the operational heart
of the product — treat it as the most important screen in the console.
- Pooja bookings queue: filters, ref lookup, status transitions, operator notes,
  CSV export. Show member name + nakshatram and the payment state.
- Temple worklist grouped by star day, printable.
- Consults: astrologer diary + status.
- Payments: order list, detail, manual entitlement grant.
Vitest tests for the filter state and a status transition.
```

## Part 12 — People section
```
Build the PEOPLE group against Parts 6 and 8.
- Users: search by phone/name, detail with bookings, family, entitlements.
  Birth data is sensitive (GUARDRAILS §4) — never put it in a URL, and show the
  chart only where an operator genuinely needs it.
- Astrologers: onboarding form for REAL practitioners (the 28 seeded ones are
  placeholders), availability editor, pricing, active toggle. Owner only.
- Operators: grant and revoke roles, scope a temple_admin to their temples.
  Owner only. This is the UI for Part 4's table, and it replaces the
  scripts/grant_role.py bootstrap for everyone after the first.
- Engagement: check-ins, streaks, milestones.
```

## Part 13 — Carried-over sections (incl. the WhatsApp simulator)
```
Port the panels that already work today, so /admin and /console can be deleted:
- CONTENT: daily pack, studio, share cards. NOTE the daily pack is implemented
  TWICE and independently (admin.js:692-813 and console.html:286-340) — build
  ONE, keeping console's extra mark-published action.
- ASTROLOGY: panchangam explorer, temple-suggest tester.
- CHANNELS: **WhatsApp simulator — a first-class console section, not a
  launcher card.** Port app/web/whatsapp.html (413 ln, self-contained: its own
  WhatsApp-brand palette, phone frame, typing indicator, ticks) INTO the
  console as a real page. Until the Cloud API timeout is fixed this simulator
  IS our WhatsApp surface, so it must not be a link to a separate page the way
  console.html:501 has it today. It drives the real brain through
  POST /whatsapp/simulate (admin-gated), so nothing about the conversation
  logic is faked. Keep the sender-number switcher and the Tele-MANAS crisis
  banner. Also notification runs.
- SYSTEM: integration status pills, read-only chat explorer for support, org
  tenants, settings.
Lowest-risk part — these endpoints all exist and are exercised today.
```

---

# SHIP

## Part 14 — Serve it, then retire the old pages
```
--- Serving ---
- Dockerfile: a third stage `FROM node:20-slim AS console`, mirroring the
  existing `frontend` stage, then
  COPY --from=console /build/dist ./app-console/dist
- app/main.py: mount app-console/dist at /console, registered ABOVE the root
  Mount("/") — Starlette matches in registration order and anything after that
  mount is dead (see the comment at main.py:227-231). Add the console paths to
  _NO_STORE_PATHS (main.py:134).
- Confirm app-nithara's service worker does not claim /console. It should not:
  navigateFallbackAllowlist was restricted to the four SPA routes in 776399b.
  VERIFY IN A BROWSER — curl cannot see a service worker, which is exactly how
  the /prototype bug got missed.

--- Retirement (only after Part 13 reaches parity) ---
- Delete app/web/admin.html, admin.js, console.html; drop their routes.
- Point shell.js's nav at the new console.
- Update README.md (still describes three hand-written operator pages) and
  FILE_STRUCTURE.md.
- DO NOT touch app/web/ui/ — white-label B2B surface, breaks tests/orgs/.
- whatsapp.html stays until Part 13 ports it.
```

## Part 15 — Retire the WAHA transport
```
Decision (2026-07-27): drop the self-hosted WAHA path entirely. It is an
unofficial bridge that links a real phone account, needs an external always-on
host, and carries its own keepalive/auto-recover machinery to survive that
host sleeping. Until the official Cloud API is usable we work through the
console's WhatsApp simulator instead, which exercises the same brain.

EXPLICITLY NOT IN SCOPE: the Cloud API send-timeout problem. Leave the Cloud
transport and its egress-window retry exactly as they are; this part only
removes WAHA.

Footprint to remove:
- app/modules/whatsapp/waha_client.py  (166 ln) — delete
- app/modules/whatsapp/keepalive.py    (110 ln) — delete; it exists ONLY to
  keep a scale-to-zero WAHA host awake
- app/main.py — the start_keepalive() call and its cancel in lifespan
- app/modules/whatsapp/router.py — /waha-webhook, /waha-status, /waha-qr
- whatsapp/{service,schemas}.py — the waha branches
- app/platform/config.py — waha_* settings (9 of them) and, critically,
  `whatsapp_transport` whose default is still "waha" (config.py:122)
- tests/whatsapp/test_waha_admin_guard.py — delete with the routes it covers

⚠️ BEFORE MERGING: check what `whatsapp_transport` is set to on the live HF
Space. If it is "waha" (the current default), removing this path takes
WhatsApp down until the Space is switched. Confirm with the owner first, and
change the default in the same commit so a Space with no explicit setting does
not silently fall through to a transport that no longer exists.
```

---

## Roles at a glance

| | owner | temple_admin | content_reviewer | support |
|---|:--:|:--:|:--:|:--:|
| Edit temples | all | **only their own** | — | — |
| Pooja catalogue (master) | ✅ | — | — | — |
| Pooja pricing at a temple | ✅ | **their own** | — | — |
| Bookings queue | all | **their own temples** | — | read-only |
| Astrologers | ✅ | — | — | — |
| Users + payments | ✅ | — | — | read-only |
| Content / feed | ✅ | — | ✅ | — |
| Grant roles | ✅ | — | — | — |
| Settings, WhatsApp, orgs | ✅ | — | — | — |

`temple_admin` is the reason this exists: temple staff should manage **their**
temple's offerings and see **their** bookings, without reading every devotee's
chat transcript or repricing someone else's temple.

## Sequencing at a glance

```
Part 1 (temples→DB) ─┐
Part 2 (astro→DB)  ──┼─► Part 4 (ROLES) ─┬─► Part 5 (temple API) ─► Part 10 (Temples UI) ──┐
Part 3 (poojas→DB) ─┘                    ├─► Part 6 (astro API) ──► Part 12 (People UI) ───┤
                                         ├─► Part 7 (bookings) ───► Part 11 (Bookings UI) ─┼─► Part 14
                                         └─► Part 8 (users/pay/feed) ─► Part 13 (carried) ─┘
Part 9 (console scaffold) — needs Part 4 for role-aware login, Part 5 for content
```

Parts 1–3 are done. **Part 4 now blocks 5–8**: build the role model before the
endpoints so each is written with its scope, rather than having every endpoint
revisited later. Parts 5–8 are independent of each other once 4 lands.

## Verification

- **Parts 1–3:** `pytest tests/temples tests/astrologers tests/bookings` passes
  **unchanged**; `python scripts/migrate.py` on a scratch DB lands 53 temples
  and 28 astrologers with the same ids the app already serves.
- **Parts 4–7:** new tests per module — 401 without a token, happy path,
  validation failure. `ruff check app tests` (**129** pre-existing findings;
  the count must not grow — `ruff check .` reports 462 because it also walks
  the local `vinimon/` venv, so always scope it) and `mypy app`.
- **Parts 8–12:** `npx vitest run` in app-console/, plus one manual end-to-end
  pass: create a temple in the console → see it in the app at `/` → book its
  pooja → watch it land in the console queue → move its status.
- **Part 13:** Docker is **not installed on this machine** — the HF Space build
  is the first real test, as it was for the Nithara frontend stage. Then check
  `/`, `/console`, `/prototype` and the API routes in a **browser**.
- **Final:** full `pytest` — 263 pass today, plus 2 pre-existing WhatsApp
  failures caused by local `.env` having `MOCK_WHATSAPP=false`.

---

## Deferred: consumer-app gaps (NOT built here)

From comparing `/prototype` (`nithara-v11.html`) against the live React app.
The app is mostly **ahead** — the prototype is 100% faked, down to a porutham
score of `(a*7+b*13)%1024` — and some absences are deliberate guardrail calls
(the astrologer directory is hidden because the seed is placeholders). Real
gaps, cheapest first:

**Pure UI:** Home's Book button is a toast (`Home.tsx:42`) and quick-book is
hardcoded to `('pushpanjali',101)` (`:259`); promo/banner rail; notices
"See all" → feed sheet; map count label + `fitPins` re-fit; WEEKDAY box and
lead-time note on the Poojas star card; family-card next-star badges; share
sheet; bilingual dual-line section headers.

**Endpoint exists, unwired:** check-in is cosmetic while
`POST /temples/{id}/checkin` sits unused (`temples/router.py:201`); QR
onboarding needs `GET /temples/by-qr/{token}` (`:173`).

**Needs backend:** `/home/promos`; "why today" reason line; `temple_name` on
`Booking`; upcoming/past filter; multi-window muhurtham; **anon chart creation**
(blocks the whole Jathakam / rasi grid / dasha bar on Profile); **temple devotee
leaderboard** (nothing exists); **login + anon-account linking**.

**Blocked on data:** the astrologer directory stays hidden until real, consented
practitioners exist. Part 5 + Part 11 give you the tool to onboard them.

Useful proxy for the total: **209 of 334 i18n keys are unused**.
