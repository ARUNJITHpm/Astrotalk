# AGENTS.md — Tara (Malayalam AI Astrology)

Rules for AI agents working in this repository. Antigravity (and other tools) read this file before acting. Keep it short, specific, and current.

## Project in one line
A modular-monolith backend (FastAPI/Python) + React Native app for an honest, Malayalam-first AI astrology companion. Guidance and comfort, never fear.

## Stack quick reference
FastAPI · PostgreSQL · ChromaDB (vectors) · Redis + Celery/arq (cache & scheduled jobs) · OpenAI `gpt-4o-mini` · React Native (Expo) · Next.js (web/admin) · Razorpay · AWS (ECS/Fargate, RDS, ElastiCache, S3+CloudFront, Secrets Manager).

## Architecture
- **Single deployable, modular monolith.** Modules live in `app/modules/<name>` and share `app/platform/**`.
- A module may import another module's **public service** only. **Never** import another module's internal files and **never** query another module's tables directly.
- Cross-module communication uses the event bus in `app/platform/events`.

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
| whatsapp | `app/modules/whatsapp/**` |
| community | `app/modules/community/**` |
| commerce | `app/modules/commerce/**` |
| admin | `app/modules/admin/**` |
| platform (shared) | `app/platform/**` — change only with human approval |

Run parallel agents only across **orthogonal** modules. Never run two agents in the same module at once.

## Hard guardrails (never violate)
1. **No fear-mongering content.** Do not generate code or copy that invents doshas, threatens consequences, manufactures urgency, or ties remedies to fear. This is the product's core promise.
2. **Safety first.** The `tone_safety` crisis screen runs **before** any astrology logic on every chat turn. Distress → empathetic response + helpline (Tele-MANAS 14416), then stop. No astrology, no upsell. Do not weaken or bypass this path.
3. **WhatsApp compliance.** Opt-in only; opt-out + AI disclosure on every proactive send; max 3/day. No open-ended AI chat on WhatsApp. Never auto-add bots to groups the system does not own.
4. **Birth data is sensitive.** Never log raw birth data or place it in URLs. Never expose it across modules beyond the defined interface.
5. **Secrets.** Never hardcode API keys/tokens. Read from environment variables / AWS Secrets Manager. Never commit `.env`.

## Requires human approval (stop and ask)
- Database schema migrations (Alembic).
- The first live WhatsApp send (and any change to send volume/cadence).
- Anything in `commerce` / payments (Razorpay).
- AWS infrastructure changes (ECS task defs, RDS, IAM, Secrets Manager entries).
- Any edit to `tone_safety` prompts or to `GUARDRAILS.md`.
- Adding a new external dependency or third-party service.

## Python conventions
- Python 3.12+, type hints everywhere, Pydantic v2 models at module boundaries.
- Format/lint with `ruff` + `black`; both must pass before a task is "done".
- Tests with `pytest`; every public service method in a module has a unit test.
- Chat and content changes include a Malayalam regression check (fixed prompt set + reviewed expected tone).
- Async I/O (`async def`) for anything calling the LLM, ephemeris API, or DB — don't block the event loop.
- Conventional commits. Small, module-scoped PRs.
- Write the implementation plan as an Artifact first; wait for review on anything touching guardrails, payments, infra, or migrations.

## Commit workflow (commit every change)
- **Every small change or feature is its own commit** — do not batch unrelated
  edits. As soon as one logical change is complete and its tests pass, commit it
  with a Conventional-Commits message (`feat(...)`, `fix(...)`, `chore(...)`,
  `docs(...)`, `refactor(...)`) whose subject says what changed and why.
- One concern per commit: a bug fix, a new feature, a copy tweak, and a refactor
  each get separate commits even when touched in the same session.
- Keep subjects imperative and scoped to the module (`fix(chat): …`,
  `feat(astrologers): …`); put the reasoning in the body when it isn't obvious.
- Commit before switching to an unrelated task, and before pushing to `origin`
  (GitHub) / `hf` (the Hugging Face Space).

## Definition of done
Code runs, `ruff`/`black`/`pytest` pass, the relevant module's public interface is unchanged or documented, and no guardrail above is touched without explicit human sign-off.