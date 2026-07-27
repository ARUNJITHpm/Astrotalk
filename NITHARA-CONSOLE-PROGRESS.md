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
- Baselines to hold: `ruff check app tests` ≤ 129; full suite green apart from
  the 2 pre-existing `tests/whatsapp/test_whatsapp.py` failures caused by local
  `.env` having `MOCK_WHATSAPP=false`.
