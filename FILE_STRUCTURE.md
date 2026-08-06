# File Structure

Full repo layout, with a one-line note on what each part does. See
[`docs/Tara-Project-Documentation.md`](docs/Tara-Project-Documentation.md) for
the full spec and [`README.md`](README.md) for how to run the project.

```
tara/
├── app/                          FastAPI backend — the modular monolith
│   ├── main.py                   Composes the app from every module's router; single entrypoint
│   ├── platform/                 Shared kernel — change only with human approval
│   │   ├── config.py             App configuration, loaded from env / secret manager
│   │   ├── db.py                 Async SQLAlchemy engine + session factory (Postgres)
│   │   ├── mongo.py               Async pymongo client (chat history / memory store)
│   │   ├── events.py             In-process event bus — the only sanctioned cross-module side-effect channel
│   │   ├── errors.py             Shared error types
│   │   ├── logging_config.py     Application logging setup
│   │   ├── metrics.py            Lightweight in-process operational counters
│   │   ├── storage.py            Object storage for generated media (cards, PDFs, logos)
│   │   ├── cards.py              Shared card-image renderer: (template, texts, branding) → PNG bytes
│   │   ├── celery_app.py         Shared Celery app (queue + scheduler) used by worker.py
│   │   ├── cron_auth.py          Access control for scheduled "cron" HTTP endpoints
│   │   └── admin_auth.py         Access control for admin-facing endpoints
│   ├── modules/                  One bounded module per package; only `service.py` is a public cross-module surface
│   │   ├── identity/             Auth, users, sessions, bearer tokens, password reset
│   │   ├── astrology_engine/     Real Swiss Ephemeris natal charts, dashas, doshas, porutham, prashnam (horary)
│   │   ├── knowledge/            Hybrid BM25 + Chroma RAG retrieval over the interpretation corpus
│   │   ├── tone_safety/          Tara's persona prompt, crisis/self-harm screen, output guardrail on replies
│   │   ├── chat/                 The AI astrologer orchestrator: history, memory, recurrence, curiosity chips
│   │   ├── content/               Daily content pipeline: drafts → share cards → publishers (Meta/YT)
│   │   ├── whatsapp/              WhatsApp channel: Meta Cloud API transport, onboarding, consent ledger
│   │   ├── community/             Audio-room style community features (ENGAGEMENT_PLAN Part A)
│   │   ├── commerce/              Subscriptions, premium PDF reports, billing (GROWTH_PLAN Part 5)
│   │   ├── orgs/                  Multi-tenancy core: white-label orgs, booking, astrologer CRM, SaaS billing
│   │   ├── astrologers/           Dummy astrologer directory + free-consult booking
│   │   ├── temples/               Curated Kerala temple directory + deity/remedy suggestions + partnerships
│   │   ├── notifications/         Cross-module notification delivery (GROWTH_PLAN Part 3)
│   │   └── admin/                 Ops analytics dashboard service + routes
│   │       (each module also has: models.py, schemas.py, router.py — internal/DTO/HTTP layers)
│   └── web/                       The white-label partner surface only (`ui/` → `/a/{handle}/ui`) + shell.js.
│                                  The hand-written operator pages went in console plan Part 14.
│
├── app-nithara/                   The consumer PWA served at `/` — React + Vite + Capacitor, Malayalam-first.
│   └── dist/                      Build output (gitignored). Docker builds it in the `frontend` stage.
│
├── app-console/                   The operator console served at `/console` — React + Vite, desktop only.
│   │                              No PWA, no Capacitor, no i18n: staff work in it for hours, in English.
│   ├── src/api/                   One typed module per section, over a shared fetch wrapper
│   ├── src/lib/                   The pure rules — nav/roles, money, booking + content state machines
│   ├── src/ui/                    One folder per sidebar group (temples, bookings, people, content, …)
│   └── dist/                      Build output (gitignored). Docker builds it in the `console` stage.
│
├── tests/                         pytest suite, one subfolder per `app/modules/*` domain (+ `platform/`)
│   ├── admin/  astrologers/  astrology_engine/  chat/  commerce/  community/
│   ├── content/  identity/  knowledge/  orgs/  platform/  temples/  tone_safety/  whatsapp/
│   └── (each subfolder holds the test_*.py files for that module's endpoints/services/engines)
│
├── docs/                          Specs, plans, guardrails, and generated PDFs (all non-code documentation)
│   ├── AGENTS.md                  Rules for AI agents working in this repo
│   ├── GUARDRAILS.md              Absolute, non-negotiable product/safety rules
│   ├── Tara-Project-Documentation.md   Full human spec
│   ├── GROWTH_PLAN.md             Monetization/growth roadmap (Parts 0–5c)
│   ├── ENGAGEMENT_PLAN.md         Retention/engagement roadmap
│   ├── NEEDS_ASTROLOGER.md        Running list of content awaiting real astrologer sign-off
│   ├── CURRENT-FEATURES.md        Snapshot of what's shipped today
│   ├── COMPETITIVE-ANALYSIS-CLICKASTRO.md   Competitor analysis vs ClickAstro
│   ├── new-ui-prompt.md           Design-brief notes for the current UI
│   ├── *.pdf                      Generated decks/guides (dev guide, content review, pitch decks, hosting, growth plan)
│   └── screenshots/               Loose product screenshots
│
├── scripts/                       One-off / operational Python scripts (not part of the running app)
│   ├── migrate.py                 Runs Alembic migrations at boot (Docker entrypoint calls this before uvicorn)
│   ├── wa_cloud_send.py           Send a real WhatsApp message via the Meta Cloud API (manual/debug tool)
│   ├── wa_cloud_subscribe.py      Check/fix the app's WhatsApp webhook subscription
│   ├── build_growth_pdf.py        Builds docs/GROWTH_PLAN_IMPLEMENTATION.pdf
│   ├── build_growth_plan_pdf_ml.py     Builds docs/Tara_Growth_Plan_Malayalam.pdf
│   ├── build_pitch_deck_en.py     Builds docs/Tara_Pitch_Deck_English.pdf
│   ├── build_pitch_deck_ml.py     Builds docs/Tara_Pitch_Deck_Malayalam.pdf
│   ├── build_temple_partnership_pdf_ml.py   Builds docs/Temple_Partnership_Malayalam.pdf
│   ├── build_whatsapp_production_guide.py   Builds docs/WhatsApp_Cloud_API_Production_Guide.pdf
│   ├── generate_pdf.py            Builds docs/tara_project_overview.pdf
│   ├── generate_dev_guide_pdf.py  Builds docs/Tara_Developer_Guide.pdf (as-built codebase explainer)
│   └── generate_content_review_pdf.py   Builds docs/Tara_Content_Review.pdf (every piece of live content, for astrologer review)
│
├── migrations/                    Alembic migrations (schema history for Postgres)
│   ├── env.py                     Alembic environment — async engine, metadata sourced from the app
│   └── versions/                  One revision per schema change (baseline, orgs, billing, CRM, chat history, ...)
│
├── evals/                         LLM eval harness — real model calls, real cost; run manually, never in pytest
│   ├── golden_set.py               Golden Malayalam conversations used as eval inputs
│   ├── run.py                      Runs the golden set against a live provider and prints a scorecard
│   └── results/                    Eval run outputs (gitignored)
│
├── assets/fonts/                  Bundled fonts (Noto Malayalam, etc.) for card rendering and PDF generation
├── var/                           Local object storage when MOCK_STORAGE=true (gitignored)
│
├── worker.py                      Celery worker + beat entrypoint (daily WhatsApp send job, 05:30 IST)
├── alembic.ini                    Alembic config, points at migrations/
├── Dockerfile                     Single image: runs API, Celery worker, and Celery beat (command overridden per service)
├── docker-compose.yml             Local dev stack: Postgres + Redis + Mongo + API + worker + beat
├── pyproject.toml                 Package metadata, pytest/ruff/mypy config
├── requirements.txt / uv.lock      Pinned dependencies
├── .env.example                   Template for local secrets (never commit the real .env)
└── README.md                      Quickstart, layout summary, HF Space config (frontmatter)
```

## Reorg notes (2026-07-25)

- All root-level `.md` docs and generated PDFs moved into `docs/`; `README.md`
  stays at root (its YAML frontmatter configures the Hugging Face Space).
- The three root `generate_*.py` PDF builders moved into `scripts/`, joining
  the existing `build_*.py` scripts; their output paths and `sys.path`
  bootstrapping were updated to match the new location.
- `tests/*.py` (30 files) were split into one subfolder per `app/modules/*`
  domain (plus `tests/platform/` for platform-level tests), each with an
  `__init__.py`. Mapping was based on each test file's actual imports, not
  just its filename (e.g. `test_crm.py` → `tests/orgs/`, since the CRM lives
  in `app/modules/orgs/`). Verified with `pytest --collect-only` (265 tests
  collected, no import errors) and a full run (263 passed; 2 pre-existing
  failures unrelated to the move — local `.env` has `MOCK_WHATSAPP=false`).
