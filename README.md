# Tara — താര

An honest, Malayalam-first AI astrology companion. The product promise is
**guidance and comfort, never fear**.

Backend is a **modular monolith** (FastAPI / Python): a single deployable split
into strongly-bounded modules that talk only through public service interfaces
and the shared event bus — never by reaching into each other's files or tables.

## Read first
- [`Tara-Project-Documentation.md`](./Tara-Project-Documentation.md) — full human spec.
- [`AGENTS.md`](./AGENTS.md) — rules for AI agents working in this repo.
- [`GUARDRAILS.md`](./GUARDRAILS.md) — absolute, non-negotiable rules.

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
tests/                     pytest suite
```
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
