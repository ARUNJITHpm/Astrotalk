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
- Removing the `"chargemod"` fallback (Part 7) can lock the owner out of the
  live Space if `ADMIN_TOKEN` is not set there — confirm before shipping it.
- Part 14 (retire WAHA) must move `whatsapp_transport`'s default off `"waha"`
  (`config.py:122`) in the same commit, or a Space with no explicit setting
  falls through to a transport that no longer exists.
- Baselines to hold: `ruff check app tests` ≤ 129; full suite green apart from
  the 2 pre-existing `tests/whatsapp/test_whatsapp.py` failures caused by local
  `.env` having `MOCK_WHATSAPP=false`.
