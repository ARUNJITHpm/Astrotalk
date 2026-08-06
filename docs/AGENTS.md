# AGENTS.md — Nithara (നിതാര)

Rules for AI agents working in this repository. Read this before acting. Keep it
short, specific, and current.

## Project in one line
A temple-first Malayalam companion for Kerala — find your temple, book a
vazhipadu for your nakshatram day, keep a family board — with an honest
astrology assistant alongside it. **Guidance and comfort, never fear.**

> **Naming.** The product is **Nithara**. "Tara" is the previous,
> astrology-chat-first product. The FastAPI app object is still `title="Tara"`
> and the HF Space is still named for it; those are cosmetic leftovers, not a
> second product. The pre-Nithara consumer UI lives only on the
> `legacy-tara-ui` branch.

## Read first
- [`../NITHARA-BUILD-PLAN.md`](../NITHARA-BUILD-PLAN.md) — how the product was
  built, Parts 0–10. Parts 0–8 are shipped.
- [`../NITHARA-CONSOLE-BUILD-PLAN.md`](../NITHARA-CONSOLE-BUILD-PLAN.md) — the
  operator console, Parts 1–14. **This is the active plan.**
- [`../NITHARA-CONSOLE-PROGRESS.md`](../NITHARA-CONSOLE-PROGRESS.md) — findings
  and decisions per completed Part. Append to it; do not rewrite history.
- [`../NITHARA-UI-ENDPOINT-AUDIT.md`](../NITHARA-UI-ENDPOINT-AUDIT.md) — every
  screen mapped to its endpoint.
- [`GUARDRAILS.md`](GUARDRAILS.md) — absolute, non-negotiable rules.

## Stack quick reference
**Backend** FastAPI · Python 3.12 · PostgreSQL (Neon, managed/external) ·
MongoDB (chat history + durable memory) · ChromaDB + BM25 (RAG) ·
Redis + Celery (scheduled jobs) · Swiss Ephemeris (`pyswisseph`, real charts) ·
Razorpay (mock by default).
**LLM** Sarvam `sarvam-105b` is the default chat model, with an OpenAI fallback
on empty completions. Never hardcode a model id — read it from settings.
**Frontend** React + Vite + TypeScript.
[`app-nithara/`](../app-nithara) is the consumer PWA (vite-plugin-pwa +
Capacitor → web/Android/iOS); `app-console/` will be the desktop operator
console. Both build to a gitignored `dist/` that Docker produces in its own
Node stage.
**Hosting** A single Docker image on a Hugging Face Space (`talk-to/nitara`),
config in the root `README.md` YAML frontmatter. **Not AWS.**
Docker Desktop (WSL2) **is** installed on the dev machine, so build and run the
image locally before pushing rather than letting the Space build be the first
test. The CLI is not on `PATH` — it lives at
`%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe`. If every
command returns `500 … /_ping`, the `docker-desktop` WSL distro is stopped
(`wsl --list --verbose`); restarting Docker Desktop fixes it. Never pipe
`docker build` into `tail`/`Select-Object`: the exit code then comes from the
pager, so a failed build reads as a success.

## Product promises (from `NITHARA-BUILD-PLAN.md`; treat as requirements)
- **Bilingual by default.** Every user-facing string in the consumer app ships
  `{en, ml}` and lives in `app-nithara/src/i18n/{en,ml}.json`. Never hardcode a
  visible English string in a component. *(The operator console is the
  exception: English only, it is a staff tool.)*
- **No-signup.** An anonymous device session comes first
  (`POST /identity/anon`); an account is optional and only ever **links** an
  existing anonymous session. Never gate a consumer feature behind a login.
- **The UI is the source of truth for shape.** Field names come from
  `nithara-v11.html` (`en`, `ml`, `place`, `sig`, `closes`, …) so the frontend
  needs no remapping. Match them; do not "tidy" them.
- **No birth data on temple endpoints**, and guidance-only framing on every
  astrology surface.

## Architecture
- **Single deployable, modular monolith.** Modules live in `app/modules/<name>`
  and share `app/platform/**`.
- A module may import another module's **public `service.py`** only. **Never**
  import another module's internal files and **never** query another module's
  tables directly.
- Cross-module communication uses the event bus in `app/platform/events`.

### Two patterns you will meet immediately

**The directory registry.** `temples` and `astrologers` each expose a
synchronous read API that the chat turn calls inline, but their data lives in
Postgres. Each has a `registry.py` holding a `list[dict]` snapshot loaded at
startup (`app/main.py:_load_directories`), with the module's `seed_data.py` as
the fallback when the table is empty. Consequences:
- Service read methods stay **sync**. Do not make them async.
- `_temples` / `_astrologers` are **properties**, never bound in `__init__` —
  routers construct services at import time, before the database is read.
- After any operator write, reload the registry or the process serves stale data.
- An empty table falls back to the seed, which is why the existing test suite
  (fresh DB, no seeded rows) still exercises the original behaviour.

**Route registration order.** Starlette matches routes and mounts in one
ordered list. `app/main.py` mounts the SPA at `/` **last**, so anything
registered after that mount is dead. Add new routes above it. Inside a router,
declare literal paths before a `/{id}` catch-all.

**Adding a consumer SPA route touches three files, not one.** The PWA service
worker claims navigations at the root scope, so a route must be added to
`app-nithara/src/App.tsx`, to the explicit list in `app/main.py`, **and** to
`workbox.navigateFallbackAllowlist` in `app-nithara/vite.config.ts`. Miss the
third and the server-rendered page still works in curl but the browser silently
gets the React shell instead — that exact bug shipped once
(fixed in `776399b`). **Never verify a page a service worker could shadow with
curl alone**; use a browser or read `dist/sw.js`.

## Module ownership (agents stay inside their domain)
| Agent task area | May edit |
|---|---|
| identity | `app/modules/identity/**` |
| astrology_engine | `app/modules/astrology_engine/**` |
| knowledge | `app/modules/knowledge/**` |
| tone_safety | `app/modules/tone_safety/**` |
| chat | `app/modules/chat/**` |
| content | `app/modules/content/**` |
| temples | `app/modules/temples/**` |
| bookings | `app/modules/bookings/**` |
| astrologers | `app/modules/astrologers/**` |
| notifications | `app/modules/notifications/**` |
| whatsapp | `app/modules/whatsapp/**` |
| community | `app/modules/community/**` |
| commerce | `app/modules/commerce/**` |
| orgs | `app/modules/orgs/**` |
| admin | `app/modules/admin/**` |
| consumer app | `app-nithara/**` |
| operator console | `app-console/**` |
| platform (shared) | `app/platform/**` — change only with human approval |

Run parallel agents only across **orthogonal** modules. Never run two agents in
the same module at once.

**New admin routes belong to the owning module** — temple CRUD in
`temples/router.py`, not in `admin/`. Gate them with `AdminGuard`
(`app/platform/admin_auth.py:82`); do not invent a second auth scheme.

## Hard guardrails (never violate)
1. **No fear-mongering content.** Do not generate code or copy that invents
   doshas, threatens consequences, manufactures urgency, or ties remedies or
   bookings to fear. This is the product's core promise.
2. **Safety first.** The `tone_safety` crisis screen runs **before** any
   astrology logic on every chat turn. Distress → empathetic response +
   helpline (Tele-MANAS 14416), then stop. No astrology, no upsell. Do not
   weaken or bypass this path.
3. **Don't invent facts about a temple.** Ratings, review counts, timings and
   offerings stay unset until real data exists — the service must never
   fabricate them. `reviewed` means an astrologer signed off the devotional
   content; only an operator may flip it.
4. **Birth data is sensitive.** Never log raw birth data or place it in a URL.
   Never expose it across modules beyond the defined interface.
5. **Pricing is server-side truth.** A client never sends an amount; bookings
   re-price from the catalogue. Do not weaken that.
6. **WhatsApp compliance.** Opt-in only; opt-out + AI disclosure on every
   proactive send; max 3/day. Never auto-add bots to groups the system does not
   own.
7. **Secrets.** Never hardcode API keys/tokens. Read from environment / Space
   secrets. Never commit `.env`.

## Requires human approval (stop and ask)
- Database schema migrations (Alembic) — **writing** one is fine, **running**
  it against a real database is not. Note the local `.env` `DATABASE_URL`
  points at the **production Neon database**, not a scratch one: verify the
  target before running anything, and test migrations against a throwaway
  SQLite file first.
- Anything in `commerce` / payments (Razorpay), especially refunds.
- The first live WhatsApp send, and any change to send volume or cadence.
- Any edit to `tone_safety` prompts or to `GUARDRAILS.md`.
- Adding a new external dependency or third-party service.
- Deleting a user-facing surface.

## Conventions
- Python 3.12+, type hints everywhere, Pydantic v2 at module boundaries.
- Async I/O for anything hitting the LLM, the DB, or the network — except the
  two directory services above, which are sync by design.
- **Lint/format with `ruff` only** (`ruff check .`, `ruff format .`) and type
  check with `mypy app`. There is no `black` in this project.
- New Alembic revisions must use `sa.DateTime(timezone=True)` for timestamps —
  asyncpg rejects aware datetimes into a naive column.
- Tests with `pytest`, one subfolder per module under `tests/`. **Every backend
  Part adds pytest; every frontend Part adds a Vitest/RTL test** for the
  screen's loading / empty / error states.
- Never put client-controlled text into `users.phone` — it is the identity key
  across Postgres and Mongo.
- **WAHA is gone** (console plan Part 15, 2026-08-06). `waha_client.py`,
  `keepalive.py` and the three `/waha-*` routes were deleted; WhatsApp goes
  through the official Meta Cloud API only. Until that transport's send-timeout
  problem is fixed, the WhatsApp surface people actually use is the console's
  simulator at Channels → WhatsApp sim, which drives the real brain through
  `POST /whatsapp/simulate`.
- **The AI disclosure lives in `whatsapp/disclosure.py`**, not in a transport.
  It used to sit inside `waha_client.py` with the Cloud client importing it from
  there, which meant deleting a transport could have silently removed a
  GUARDRAILS §3 requirement from every outbound message. Any new sender appends
  it from that module.

## Working baselines (do not regress)
- `pytest` — **321 pass**. Two failures in `tests/whatsapp/test_whatsapp.py` are
  pre-existing and environmental: a local `.env` with `MOCK_WHATSAPP=false`.
- `ruff check app tests` — **128** findings. A bare `ruff check .` reports ~462
  because it walks the local `vinimon/` venv; always scope it.
- When a Part refactors a service, its existing tests must pass **unchanged** —
  that is the proof the refactor preserved behaviour.

## Commit workflow
- **Every small change or feature is its own commit.** One concern per commit:
  a bug fix, a feature, a copy tweak and a refactor each get their own, even
  when touched in the same session.
- Conventional Commits, scoped to the module (`fix(chat): …`,
  `feat(temples): …`). Put the reasoning in the body when it isn't obvious.
- **When executing a partwise plan, finish each Part with a code review of that
  Part's diff, then a commit,** before starting the next.
- Commit before switching tasks and before pushing to `origin` (GitHub) or `hf`
  (the Space).
- **Never `git stash` in this repo.** OneDrive locks `tara.db` mid-stash and
  uncommitted work is lost. Use `git diff` / `git show`.

## Definition of done
Code runs, `ruff` and `pytest` pass at or below the baselines above, the
module's public interface is unchanged or documented, the relevant plan and
progress file are updated, and no guardrail is touched without explicit human
sign-off.
