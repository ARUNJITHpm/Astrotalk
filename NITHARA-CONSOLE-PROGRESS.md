# Nithara Operator Console — progress log

Findings and work completed per Part of
[`NITHARA-CONSOLE-BUILD-PLAN.md`](NITHARA-CONSOLE-BUILD-PLAN.md).
Newest last. Each Part ends with a code review and its own commit.

---

## Pre-work — security fix (`e224cac`)

Not a numbered Part; it had no dependencies so it shipped first.

**Finding.** `GET /whatsapp/waha-status` and `GET /whatsapp/waha-qr`
(`whatsapp/router.py:427,433`) both said "for admin" in their docstrings and
carried **no guard**. `/waha-qr` returns the pairing QR and session details for
the WhatsApp account — enough for a stranger to attach their own device to it.
`/waha-status` leaks the connected number and session state.

**Done.** Added `dependencies=[AdminGuard]` to both (the gate was already
imported for `/simulate`, so no new auth scheme). New
`tests/whatsapp/test_waha_admin_guard.py` asserts 401 for no token and for a
wrong token, and that the upstream is **never called** on an unauthenticated
request.

---

## Part 1 — Temples out of `seed_data.py`, into Postgres (`dcfac5d`)

### Findings

- **There was no `temples` table.** All 53 temples were a Python literal in
  `temples/seed_data.py` (621 lines), bound in memory at
  `TemplesService.__init__` (`service.py:96`). Adding a temple or correcting a
  price required a code change and a redeploy. This is why no console could be
  built first — there was nothing to edit.
- **`TemplesService` is entirely synchronous** and is called synchronously from
  inside the chat turn. Naively moving to DB reads would have rippled `async`
  through every caller for a directory that changes a few times a month.
- **Data quality.** Verified directly: all 53 entries carry `"reviewed": True`
  while the file's own docstring (`seed_data.py:3`) says *"DRAFT DATA — NOT
  reviewed. Every entry is `reviewed=False`"* — and that flag is served to
  clients via `TempleSuggestion.reviewed`. Zero temples define `poojas`,
  `timings`, `hours` or `rating`; only 2 of 53 define `story`. So every temple
  in the product shows identical hours and an identical 4-item catalogue.

### Done

| File | Change |
|---|---|
| `temples/models.py` | `Temple` — every `TempleSeed` field plus `active`, `image_key`, `sort_order`, `updated_at` |
| `temples/registry.py` | **new** — sync `list[dict]` snapshot loaded from the DB, falling back to the seed |
| `temples/service.py` | `_temples` became a **property** reading the registry |
| `app/main.py` | loads the directory at startup |
| `migrations/…a7b8c9d0e1f2` | creates `temples` and imports the seed in one upgrade |
| `tests/temples/test_temple_registry.py` | **new**, 8 tests |

**Key design decision.** An empty table falls back to `SEED_TEMPLES`. That is
what lets the **untouched** existing suite be the proof of correctness: every
other test builds a fresh database and seeds no temples, so they exercise
exactly the old behaviour. `_temples` had to become a property — bound in
`__init__` it would have pinned the process to the fallback forever, since
routers construct the service at import time.

**Review finding, fixed before commit.** The fallback originally keyed on "no
*active* rows", so an operator retiring every temple would have resurrected the
whole seed directory underneath them. It now keys on the table being empty,
with a test pinning it.

**Decision recorded.** The seed imports **as-is**, `reviewed=True` included.
Part 1's contract is "the API returns what it returned before"; flipping that
flag in a migration would contradict it and silently change what
`/temples/suggest` returns. Flipping it is an operator action against
`PATCH /temples/{id}/review` in Part 4.

### Verification

- `tests/temples` **44 pass**; full suite **314 pass**
- ruff unchanged at its **129** baseline
- Migration against a scratch SQLite: 53 rows, `reviewed` and curated order
  preserved
- Seed path vs DB path **byte-identical** across list, nearby-sort, deity
  filter, search, light rows and full detail for all 53 temples

---

## Part 2 — Astrologers out of `seed_data.py`, into Postgres (`48c1d71`)

### Findings

- **There was no `astrologers` table either**, and no admin-gated route
  anywhere in the module — `astrologers/router.py` never imported `AdminGuard`.
  All 28 entries are **programmatically generated placeholders**
  (`seed_data.py:117-143`: 14 districts × 2, `id == name ==
  "{district}-astro-{n}"`, deterministic experience and rating). The consumer
  app already refuses to render them
  (`app-nithara/src/screens/Astro.tsx:128-133`).
- **No price field existed at all**, though `NITHARA-UI-ENDPOINT-AUDIT.md`
  specifies `p (₹/min)` for the Astrologer entity.
- Consult windows were baked into `_morning_windows()` / `_evening_windows()`
  (`seed_data.py:97-113`) — not editable.

### Done

Mirrors Part 1: `Astrologer` model, `astrologers/registry.py`,
`_astrologers` as a property, migration `b8c9d0e1f2a3` (28 rows, imported
active), and `tests/astrologers/test_astrologer_registry.py` (7 tests).
New columns: `name_ml`, `active`, `price_paise_per_min`, `photo_key`,
`sort_order`.

`app/main.py`'s startup hook was generalised into `_load_directories()` so it
does not grow a block per module. Each registry gets its own session, so one
failing does not stop the other loading.

**Deviation from the plan, deliberate.** The plan called for a separate
`AstrologerAvailability` table. `availability` stays a **JSON array** instead:
that is the exact shape `_open_slots_utc` already iterates
(`service.py:151`), so the booking engine needed no change — which is Part 2's
contract — and a handful of weekly windows per astrologer does not want a join.
The console edits it as a list.

### Verification

- `tests/astrologers` **17 pass**; full suite **321 pass**
- ruff **128** — did not grow (129 baseline)
- Migration against scratch SQLite: 28 rows
- **API output identical** across list / district filter / specialty filter /
  `suggest_for` by concern+district / `suggest_for` by coordinates

**Worth stating plainly:** the raw *dict* comparison did **not** match, unlike
Part 1's. The DB rows carry three keys the seed dicts lacked — `name_ml` and
`price_paise_per_min` (new, for the console) plus `availability`. `AstrologerOut`
declares none of them, so nothing reaches the wire, and the equivalence holds at
the public boundary. A test now pins that so widening the directory dict can
never silently widen the API.

---

## Part 3 — Pooja catalogue + service fee out of constants (`287a8fe`)

### Findings

- **`DEFAULT_POOJAS` was a 4-item Python constant** (`temples/service.py:59`)
  shared verbatim by all 53 temples. The per-temple override slot
  (`TempleSeed.poojas`, read at `service.py:209`) had existed from the start and
  **not one temple used it** — so every temple in the product offered the
  identical four items at identical prices.
- **The ₹15 fee was `SERVICE_FEE_PAISE`** (`bookings/service.py:27`), unchangeable
  without a deploy.
- Two readers consume the catalogue, both synchronously and both via
  `t.get("poojas", DEFAULT_POOJAS)`: `TemplesService.pooja_catalogue` and
  `BookingsService._find_pooja`.

### Done

`poojas` (master), `temple_poojas` (override; NULL columns inherit, so changing a
lead time does not require copying the price), single-row `booking_settings`,
migration `c9d0e1f2a3b4`, and 11 new tests.

**Key design decision.** The catalogue is resolved *during the registry load* and
materialised into each temple's `poojas` key. Both readers therefore needed **no
change at all**, and server-side pricing is preserved by construction. An empty
master table falls through to `DEFAULT_POOJAS`.

`booking_settings` is deliberately narrow rather than an app-wide key/value
store — a shared settings table would be a cross-module surface that
`docs/AGENTS.md` puts behind human approval.

**Review finding, fixed before commit.** Amounts are stored in paise but
`amount` is served in whole rupees (the existing `PoojaCatalogueItem` contract),
and the booking path multiplied that rupee figure back up by 100 — silently
**undercharging any price that is not a whole rupee** (₹101.50 would bill ₹101).
The resolved catalogue now also carries the authoritative `amount_paise` and
bookings prices from it. `PoojaCatalogueItem` does not declare the field, so it
never reaches the wire; a test pins both halves.

### Verification

- `tests/temples` + `tests/bookings` **59 pass**; full suite **332 pass**
- ruff **128** — unchanged
- DB-resolved catalogue identical to the constant path, lead-time locks included
- Applied to production: 4 master offerings, 0 overrides, fee 1500 paise,
  schema at `c9d0e1f2a3b4`

---

## Part 4 — Role-based operator accounts (`774cb73`, `49e1d72`)

Two commits: the auth model first, then the accounts that populate it.

### Findings

- **There was exactly one privilege level.** `require_admin` answered a single
  yes/no question, so a per-temple clerk, a content reviewer and the owner all
  presented the same credential and could do everything.
- **The literal `"chargemod"` was accepted unconditionally** at
  `admin_auth.py:40`, by `POST /admin/login`, and was *printed on screen* by
  `admin.html:363`. Anyone who ever saw a screenshot of the dashboard had full
  admin. This was pulled forward from Part 7 at the owner's instruction.
- **Operators cannot be `users` rows.** That table requires `dob`,
  `birth_place`, `lat`, `lng` and `tz`, all NOT NULL, because it models a
  devotee with a natal chart. A temple clerk should not need a birth time to
  sign in. Hence four new tables.
- **`require_cron_or_admin` was quietly broken** (`cron_auth.py`): it called
  `await require_admin(x_admin_token)`, binding the token string to
  `require_admin`'s *session* parameter. It happened to fail closed, so no test
  caught it.

### Done

| File | Change |
|---|---|
| `platform/admin_auth.py` | rewritten around an `Operator` context: `roles`, `temple_ids`, `can_edit_temple`, `visible_temple_ids`, `require_temple`; `require_operator(*roles)` factory |
| `admin/models.py` | was a 3-line stub — now `Operator`, `OperatorRole`, `OperatorSession`, `OperatorInvite` + the `ROLES` / `SCOPED_ROLES` vocabulary |
| `admin/operators.py` | **new** — invite / accept / login / logout / grant / revoke / set_active / listing |
| `admin/router.py` | 8 operator routes; owner-only except login and accept |
| `platform/cron_auth.py` | the regression above, fixed against `resolve_operator` |
| `scripts/grant_role.py` | **new** — first-owner bootstrap |
| `tests/conftest.py` | **new** — autouse fixture configuring `admin_token`, so the 8 existing admin-token test files needed no edits |
| `migrations/…d0e1f2a3b4c5` | the four tables, seeded empty |

**Roles.** `owner` (everything), `temple_admin` (scoped — must carry a
`temple_id`), `content_reviewer`, `support`. The X-Admin-Token and an
`admin_phones` session both still resolve to a full owner, so nothing that
worked before stopped working.

**Key design decision — invite, never self-register.** The invite records role
and scope up front, so redeeming it is one step: set a password, get exactly
the access you were invited for. The owner passes the link on themselves
(there is no mail transport in this deployment yet), and the account row
materialises on *accept*, not on invite, so a pending invite can never be
mistaken for someone who already has access.

`scripts/grant_role.py` is deliberately **not** a route: creating an owner
should require shell access to the deployment, not merely a valid HTTP request.

**Security properties pinned by tests.** Login returns one indistinguishable
error for unknown account / unset password / deactivated / wrong password, so
it cannot enumerate who has console access. Deactivating drops live sessions —
revoking access has to mean *now*, not whenever the token expires. Logout
revokes server-side and always 204s. 401 means unknown, 403 means known and
denied.

**Review findings, fixed before commit.** (1) `operators.logout` was written
but no route reached it — dead code that let the client decide when a session
ended; a `POST /admin/operators/logout` now exists. (2) A test was named the
opposite of what it asserted (`test_listing_marks_pending_operators` — listing
does not, because no operator exists yet); renamed to
`test_an_unaccepted_invite_creates_no_operator`.

### Verification

- `tests/admin` **26 pass**; full suite **363 pass**
- ruff **127** — one below the 128 baseline
- The two tests that asserted the backdoor were rewritten to assert its
  absence: `test_legacy_admin_chargemod_login_is_rejected` and
  `test_unset_admin_token_authenticates_nobody`
- `d0e1f2a3b4c5` applied to production; four empty tables, no existing row
  touched

> ⚠️ **Do not push to the `hf` remote** until the owner sets `ADMIN_TOKEN` as a
> Space secret. `"chargemod"` is gone, so the only remaining door on the live
> deployment is an `admin_phones` app session.

---

## Part 5 — Temple admin API (`10bfb16`)

### Findings

- **The directory had never had a write path.** Parts 1–3 gave it tables; this
  is the first commit that can change a row. No migration was needed, which is
  the point of having done the data moves first.
- **Partners and festivals were append-only.** `add_festival` (`partners.py`)
  had no counterpart, so a wrong festival date could never be corrected — and
  a festival date is exactly what subscribers get notified about three days
  early. `TemplePartner.active` (`models.py:153`) had no route that could
  write it either: a partnership could be created but never ended.
- **`python-multipart` is not a pinned dependency**, though it is importable
  transitively. A `POST /image` on `UploadFile` would have rested on that.

### Done

| File | Change |
|---|---|
| `temples/admin.py` | **new** — operator data access + validation, the split `partners.py` already uses |
| `temples/router.py` | 15 operator routes; the partner block rescoped |
| `temples/partners.py` | `update_festival`, `delete_festival`, `update_partner` |
| `temples/schemas.py` | the write shapes, kept separate from the app's read contract |
| `tests/temples/test_temple_admin.py` | **new**, 38 tests |

**Role split.** Owner: create/retire a temple, the master catalogue. Owner or
`temple_admin` (then scoped by `require_temple`): edit a temple, its timings,
its photo, its catalogue overrides, its partner and festivals. Owner or
`content_reviewer`: the `reviewed` flag.

**Key design decision — `reviewed` is not part of PATCH.** The flag asserts an
astrologer checked the devotional content (GUARDRAILS §1) and it is served to
clients. Routing it through the generic edit route would let the same role that
writes a temple's copy also certify it, which makes the flag self-issued and
therefore worthless. `TempleAdminPatch` sets `extra="forbid"` so this is
enforced by the schema, not by convention; a test pins it.

**Retire, never delete.** Bookings, visits, partners and festivals all
reference `temples.id` as a plain string with no foreign key, so a real DELETE
would orphan them without a word. `active=False` is the only removal on offer.
The one exception is a festival: nothing references one, and a cancelled
festival should leave the microsite rather than linger as an inactive row.

**Publication.** Every write ends in `_publish()` — commit, then rebuild the
registry snapshot. Without it an operator's edit would not appear until the
next restart, because the readers are synchronous and serve the in-memory
snapshot. The tests therefore assert against the *public* API, never the row.
This is safe only because the container runs a single uvicorn worker
(`Dockerfile:61`); adding `--workers N` would refresh one process and leave the
others stale, and would need a shared invalidation signal first.

**Images without multipart.** `POST /{id}/image` takes the raw file as the
request body — one line for a console (`fetch(url, {method:'POST', body:file})`)
and no new dependency. The format comes from the file's magic bytes, never
from `Content-Type`: the header is a claim, the first bytes are evidence.

### Review findings, fixed before commit

1. **Partner routes were still on the coarse `AdminGuard`** next to the newly
   scoped PATCH. A `temple_admin` could register a partner for a temple they
   are then forbidden to edit, and `GET /temples/partners` returned *every*
   partner's contact phone number. Creation, listing and the QR poster are all
   scoped now. This is precisely the "retro-fitting scopes onto finished
   endpoints" the plan warned about — the endpoints were finished before roles
   existed.
2. **The WebP sniff matched bare `RIFF`**, which is the generic container magic
   that WAV and AVI also carry, so an audio file would have been stored and
   served back as `image/webp`. Both halves of the header are checked now.

### Verification

- `tests/temples` **90 pass**; full suite **401 pass**
- ruff **125** — three below the 128 baseline (an existing `B904` in
  `create_partner` was fixed in passing)
- Route-ordering pin: a test asserts `GET /temples/poojas` reaches the master
  catalogue, so a future re-order that lets `/{temple_id}` claim it fails loudly
- No migration; nothing was applied to production

**Trap worth knowing, pinned by a test.** An empty `temples` table means "never
imported" and serves the curated seed, so creating the *first* temple through
the console on a deployment that never ran `a7b8c9d0e1f2` swaps 53 temples for
1. Production has run it.

---

## Part 6 — Astrologer admin API (`9059633`)

### Findings

- **The module had no admin-gated route at all.** `astrologers/router.py` never
  imported a guard; all six routes were public reads or user-scoped bookings.
- **An astrologer could not see their own diary.** Bookings were only ever
  queryable by the user who made them (`/bookings/me`), so nothing anywhere
  answered "who is coming at 10:30".
- **Nothing recorded that a consult happened.** The status vocabulary was
  `confirmed | cancelled`, and only the booking's own user could change it.
- **Consult windows were baked into `seed_data._morning_windows()` /
  `_evening_windows()`** and could not be edited by anyone.

### Done

| File | Change |
|---|---|
| `astrologers/admin.py` | **new** — data access + validation |
| `astrologers/router.py` | 8 owner-only routes before the `/{astrologer_id}` catch-all |
| `astrologers/models.py` | `BOOKING_STATES` / `TERMINAL_STATES` |
| `astrologers/service.py` | `cancel` hardened against the widened vocabulary |
| `platform/storage.py` | `sniff_image` + `ImageRejected`, lifted out of Part 5 |
| `tests/astrologers/test_astrologer_admin.py` | **new**, 28 tests |

**Owner-only, deliberately.** Unlike temples there is no scoped role: a
`temple_admin` runs a temple, and the astrologer directory is one editorial
surface, not fifty-three of them. A test pins the 403.

**Key design decision — nothing returns to `confirmed`.** An operator may move
a consult to `cancelled`, `completed` or `no_show`, and may correct one
terminal state to another (marking `no_show` by mistake has to be fixable). It
may never go back: `astro_bookings` is unique on (astrologer_id, starts_at) and
a closed row still holds its slot, so reviving one from the console could
re-seat a consult somebody else has since booked. The user booking path revives
deliberately, through `service.book`, which checks the slot is still open first.

Only `cancelled` frees a time — a completed consult occupied it. Pinned.

**Availability is a PUT, not a PATCH.** "These are my hours" is how a person
thinks about it, and a partial update makes removing a window awkward. Already
booked consults are untouched, because a booking holds an absolute instant
rather than a reference to a window: narrowing the schedule stops new bookings
and cancels nothing. Also pinned.

A window shorter than one consult is rejected rather than stored — it yields
zero slots, so the astrologer looks booked solid forever with nothing anywhere
saying why.

### Review finding, fixed before commit

`service.cancel` rejected only the already-cancelled case, because that was the
only closed state there was. Widening the vocabulary would have let a **user**
cancel a consult an operator had recorded as `completed` — rewriting history,
and freeing a slot that was genuinely used. It now refuses every terminal
state, with a test.

### Verification

- `tests/astrologers` **45 pass**; full suite **429 pass**
- ruff **125** — unchanged from Part 5, three below the 128 baseline
- Route-ordering pin for `/astrologers/manage` vs `/{astrologer_id}`
- A test asserts the public `AstrologerOut` still hides `price_paise_per_min`,
  `availability` and `active`, so widening the directory dict can never widen
  the API (the same guarantee Part 2 established)
- No migration; nothing applied to production

---

## Part 7 — Bookings operator API (`c483bed`)

### Findings

- **Operators could see nothing.** Two routes, both hard-scoped to the caller
  (`router.py:31,:45`). Answering "what are we performing tomorrow" meant
  opening the database.
- **`when_label` is free display text** the client composes ("28 Jul, 6:00 AM").
  There was no machine-readable date anywhere on a booking, so a dated worklist
  — the whole point of the operator queue — was not expressible.
- **Nothing but the payment reconciler ever wrote `state`**, and the vocabulary
  was `wait | ok`. There was no cancel path for a pooja at all, for an operator
  *or* a user, and nothing recorded that an offering had been performed.
- **The ₹15 fee got a row in Part 3 but no writer.**

### Done

| File | Change |
|---|---|
| `bookings/admin.py` | **new** — scoped queue, detail, state machine, worklist, CSV |
| `bookings/router.py` | 9 operator routes under `/bookings/queue` |
| `bookings/models.py` | `BOOKING_STATES` widened; `OPERATOR_TRANSITIONS`; `perform_on`, `operator_note`, `updated_at` |
| `bookings/service.py` | the reconciler guard (below) |
| `migrations/…e1f2a3b4c5d6` | the three columns — **not yet applied to production** |
| `tests/bookings/test_booking_queue.py` | **new**, 33 tests |

**Scope is the load-bearing part.** Filtering happens in the query, not after
it, and `visible_temple_ids()` returns `None` for an owner but an **empty set**
for a scoped operator with no grants. The obvious `if temple_ids:` treats them
alike and opens the entire queue — devotee names and phone numbers included. A
test drives the query directly to pin the empty-set branch.

A booking outside scope reads as **missing**, not forbidden. Refs are `NT` plus
six digits; answering "forbidden" for one temple and "unknown" for another
turns the ref lookup into an oracle.

**Two things the state machine must refuse.** An operator cannot assert `ok` —
it means the reconciler saw a captured payment, and a console that could claim
it would make a paid booking indistinguishable from a mistaken click. And
`refunded` is bookkeeping only: it records that a refund was issued in the
Razorpay dashboard. Wiring a real refund touches payments and is gated on human
approval (AGENTS.md), so this stops at recording the fact rather than
pretending.

**The reconciler bug the new states created.** `list_for_user` promoted any
booking whose state was `!= "ok"` — identical to `== "wait"` while those were
the only two states. With a cancel path it would have resurrected a **cancelled**
booking the moment a late capture landed, silently undoing an operator's
decision. Now only `wait` reconciles, with a test.

**`perform_on`.** Nullable and optional, so existing clients keep working. The
worklist *reports* how many bookings it could not place rather than dropping
them — a sheet that quietly omits work is worse than one that says what it is
missing.

### Review findings, fixed before commit

1. **Date filters were a day out for Indian operators.** They compared UTC
   dates, so a booking made at 03:00 IST (21:30 UTC the previous day) fell
   under the wrong day and disappeared from both days' reports. The bounds are
   now the UTC instants that bracket an IST day, computed in Python so the SQL
   stays portable between SQLite (tests) and Postgres (production).
2. **The CSV export reused the queue's 200-row page cap**, so a month's
   settlement would have been cut off in silence. It has its own bound
   (`MAX_EXPORT`, 5000) and a comment saying why the two differ.
3. **A test was named for a branch it never reached** — the role check fired
   first, so `test_an_operator_with_no_grants_sees_nothing` proved only that
   `support` is not a queue role. Split into a direct query-level test of the
   empty scope and a separate role test. (The same class of mistake as Part 4's
   misnamed test; worth watching for.)

### Verification

- `tests/bookings` **40 pass**; full suite **462 pass**
- ruff **123** — five below the 128 baseline
- Migration verified on a throwaway SQLite: upgrade → downgrade → upgrade all
  clean, 53 temples / 28 astrologers / 4 offerings intact, head at
  `e1f2a3b4c5d6`
- A test pins that `/queue/export.csv` is not parsed as a `{booking_id}`

**`e1f2a3b4c5d6` applied to production** (owner approved, 2026-07-27). The
table was empty, so nothing needed backfilling; `perform_on date NULL`,
`operator_note text NOT NULL DEFAULT ''` and `updated_at timestamptz NULL` are
present and every other row count is unchanged (13 users, 53 temples, 28
astrologers, 4 offerings, 1 payment). Head is now `e1f2a3b4c5d6`.

**The operator queries were then run against the real Postgres**, which is the
first time any of Parts 5–7 had left SQLite. Three things could have been
dialect-specific and were checked explicitly: the count-over-subquery that
produces `total`, `IN ()` for the empty-scope branch, and comparing a
`timestamptz` column against tz-aware Python datetimes for the IST date bounds.
All behave. Case-insensitive ref lookup and the CSV shape were checked too.

---

## Migrations applied to production — 2026-07-27

Owner approved running against the real database. Applied
`a7b8c9d0e1f2` (temples) and `b8c9d0e1f2a3` (astrologers) to the managed Neon
Postgres the live Space uses. Both are purely additive — two `CREATE TABLE`
plus inserts; nothing existing was altered or dropped, and
`alembic downgrade f6a7b8c9d0e1` reverses them.

Verified after the run: **53 temples** (all `reviewed=true`, curated
`sort_order` intact) and **28 astrologers** (all `active=true`), schema at
`b8c9d0e1f2a3`, and the live data path returns output **identical to the seed
path** for both directories.

Note for future work: the local `.env` `DATABASE_URL` points at production, not
a scratch database. Test migrations against a throwaway SQLite file first.

## Standing items
- **`ADMIN_TOKEN` is not set on the live Space.** `"chargemod"` was removed in
  Part 4, so pushing to `hf` before the owner adds that secret leaves only the
  `admin_phones` session as a way in.
- Part 14 (retire WAHA) must move `whatsapp_transport`'s default off `"waha"`
  (`config.py:122`) in the same commit, or a Space with no explicit setting
  falls through to a transport that no longer exists.
- **Demo data is live on production** (`scripts/seed_demo_data.py`, 2026-07-27):
  6 users, 24 pooja bookings, 22 payments, 6 consults, 1 partner, 3 festivals.
  Every row is marked (`NTDEMO…` refs, `+9199000000…` phones, `order_demo_…`,
  `[demo]`, `demo-…`), so `--purge` removes exactly those and nothing else.
  **Remove it before launch.**
- Baselines to hold: `ruff check app tests` ≤ 129; full suite green apart from
  the 2 pre-existing `tests/whatsapp/test_whatsapp.py` failures caused by local
  `.env` having `MOCK_WHATSAPP=false`.
