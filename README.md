---
title: Tara
emoji: 🔮
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 3000
pinned: false
---

# Tara — താര

An honest, Malayalam-first AI astrology companion. The product promise is
**guidance and comfort, never fear**.

Backend is a **modular monolith** (FastAPI / Python): a single deployable split
into strongly-bounded modules that talk only through public service interfaces
and the shared event bus — never by reaching into each other's files or tables.

## Read first
- [`FILE_STRUCTURE.md`](./FILE_STRUCTURE.md) — full repo layout with a brief note on what each part does.
- [`docs/Tara-Project-Documentation.md`](./docs/Tara-Project-Documentation.md) — full human spec.
- [`docs/AGENTS.md`](./docs/AGENTS.md) — rules for AI agents working in this repo.
- [`docs/GUARDRAILS.md`](./docs/GUARDRAILS.md) — absolute, non-negotiable rules.

## Layout
```
app/
  main.py                  FastAPI app — wires every module router
  platform/                shared kernel — change only with human approval
    config.py  db.py  events.py  logging.py  errors.py
  modules/                 one bounded module per package
    identity/  astrology_engine/  knowledge/  tone_safety/
    chat/  content/  whatsapp/  community/  commerce/
    notifications/  admin/
tests/                     pytest suite, one subfolder per module
docs/                       specs, guardrails, growth plans, pitch decks, PDFs
scripts/                    migrations, PDF builders, WhatsApp Cloud API utils
```
See [`FILE_STRUCTURE.md`](./FILE_STRUCTURE.md) for the full tree.
Each module exposes a single public `service.py` (the only cross-module surface)
and keeps internals in `router.py`, `models.py`, `schemas.py`.

> Note: Python package names use underscores, so `astrology-engine` →
> `astrology_engine` and `tone-safety` → `tone_safety` on disk.

## Getting started
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env       # fill in secrets — never commit .env
uvicorn app.main:app --reload --port 3000
```
API docs at `http://localhost:3000/docs`.

### The frontend
`/` serves the Nithara app — a React PWA whose source is in
[`app-nithara/`](./app-nithara) and whose build output (`app-nithara/dist`) is
gitignored. Docker builds it in a Node stage; locally you need it once:

```bash
cd app-nithara && npm ci && npm run build
```

Until then `/` answers 503 and the API is unaffected. For frontend work run
Vite instead (`npm run dev`, with `VITE_API_BASE` pointing at this server) —
uvicorn's reloader does not rebuild `dist`.

`/console` serves the operator console — a second React app, source in
[`app-console/`](./app-console), built the same way and equally gitignored:

```bash
cd app-console && npm ci && npm run build
```

It is a desktop tool for staff: no PWA, no service worker, no Malayalam UI. Nine
sections cover temples, bookings, people, content, astrology, channels and
system, each gated by the signed-in operator's role. Until it is built `/console`
answers 503.

The three hand-written operator pages this replaced — `/admin`, the old
`/console` and `/whatsapp` — were deleted in console plan Part 14. Those
addresses now redirect into the console. `app/web/` keeps only `shell.js` and
`ui/`, the white-label partner surface (`/a/{handle}/ui`, `/login`,
`/dashboard`). The pre-Nithara consumer UI was removed when Nithara took the
root; it is preserved on the `legacy-tara-ui` branch.

## Checks
```bash
ruff check .      # lint
ruff format .     # format
mypy app          # type check
pytest            # tests
```

## Build sequence (docs §8)
- **Phase 0** scaffold — this skeleton.
- **Phase 1** MVP loop — identity → astrology_engine → tone_safety + chat → content + whatsapp.
- **Phase 2** money — commerce (subscriptions, reports, consults).
- **Phase 3** moat — community audio rooms, admin, notifications.
