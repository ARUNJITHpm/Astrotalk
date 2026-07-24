# Tara — Malayalam AI Astrology Companion

**Project documentation for building in Google Antigravity**
Working name: *Tara* (താര — "star"). An honest, Malayalam-first astrology companion. The product promise is **guidance and comfort, never fear**.

> This document is the human-readable spec. The machine-readable rules that Antigravity's agents must follow live in `AGENTS.md` and `GUARDRAILS.md` at the repo root. Keep all three in sync.

---

## 1. Vision & non-negotiables

Tara is an AI astrologer that knows the user's birth chart, speaks Malayalam, and talks like a warm, trusted elder. It is framed as **reflection and guidance**, not deterministic fortune-telling. Three rules are absolute and are encoded as guardrails for every agent:

1. **No fear-mongering.** Never invent a dosha, never use "pay or doom", never manufacture urgency.
2. **Safety over engagement.** Real distress is routed to a human/helpline, not answered with a horoscope.
3. **Compliance is not optional.** WhatsApp, payments, and birth-data privacy rules are enforced in code.

---

## 2. Why a modular monolith (and why it fits Antigravity)

A **modular monolith** is a single deployable application divided internally into strongly-bounded modules that talk to each other only through explicit interfaces — never by reaching into each other's database tables.

This is the right choice here for three reasons:

- **Small team, early stage.** One deployable is far cheaper to run and reason about than microservices. You can split modules into services *later* if a module needs independent scaling (the community audio service is the likely first candidate).
- **Clear seams without distributed-systems pain.** You get the separation benefits (testability, ownership, replaceability) without network calls, service discovery, or eventual-consistency headaches.
- **It is the ideal shape for agent-first development.** Antigravity works best when multiple agents operate on *orthogonal* modules so they don't collide. Each module below becomes an isolated agent domain with file boundaries declared in `AGENTS.md`.

```
                ┌─────────────────────────────────────────────┐
                │              Tara Monolith (API)             │
                │                                              │
  Mobile/Web ──▶│  identity   astrology_engine   knowledge     │──▶ Postgres + ChromaDB
                │  chat       tone_safety         content       │──▶ Redis (cache/queues)
                │  whatsapp   community           commerce      │
                │  notifications   admin                        │
                │                                              │
                │  ── shared platform: events, config, db ──    │
                └───────┬───────────────┬──────────────┬───────┘
                        │               │              │
                  Ephemeris API   LLM (OpenAI)   WhatsApp BSP / Razorpay

  Hosted on AWS (ECS/Fargate + RDS + ElastiCache).
```

---

## 3. Stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI (Python)** | Fast to build, first-class async + typing (Pydantic), and the natural home for the LLM/RAG ecosystem. Modules map 1:1 to packages and to agent domains. |
| Database | **PostgreSQL** (relational) + **ChromaDB** (vectors) | Postgres for the relational core; ChromaDB as the dedicated vector store for RAG retrieval. |
| Cache / queue | **Redis** + **Celery** (or **arq**) | Caches daily transits; runs scheduled jobs (daily WhatsApp message). |
| LLM | **OpenAI `gpt-4o-mini`** via API | Chat generation + Malayalam message drafting. Cheap, fast, streams well for the chat UI. |
| Ephemeris | **Hosted Astrology API** for MVP → self-hosted **Swiss Ephemeris** at scale | Don't reinvent planetary math. |
| WhatsApp | Official **BSP** (Gupshup / Wati / Twilio) + a **WhatsApp Channel** | Compliant broadcast. No open AI chat on WhatsApp. |
| Mobile | **React Native (Expo)** | One codebase, fast iteration. |
| Web / Admin | **Next.js** | Marketing site + astrologer/moderation dashboards. |
| Payments | **Razorpay** | India-standard; UPI/cards. |
| Hosting | **AWS** | API on **ECS/Fargate**, Postgres on **RDS**, Redis on **ElastiCache**, static/web on **S3 + CloudFront**, secrets in **Secrets Manager**. |

> **Note on Antigravity + AWS:** Antigravity's deployment shortcuts are more native to Google Cloud (Cloud Run, Firebase). AWS is fully supported, but agents will deploy to it via terminal/CLI commands rather than a built-in integration — budget a little extra setup time for the `platform`/CI module.

---

## 4. Module breakdown

Each module is an isolated directory (`app/modules/<name>`), exposes a small public service interface, and emits/handles domain events through the shared event bus. The "Agent domain" column is what you declare in `AGENTS.md` so a given agent only edits its own module.

| Module | Responsibility | Talks to | Agent domain |
|---|---|---|---|
| `identity` | Auth (JWT/OAuth), user profile, **birth data** capture, timezone/geocoding | — | `app/modules/identity/**` |
| `astrology_engine` | Natal chart, transits, dasha, **porutham**; wraps ephemeris API; caches results | external ephemeris | `app/modules/astrology_engine/**` |
| `knowledge` | RAG knowledge base (planet×sign×house, transit rulebook) in ChromaDB; retrieval | — | `app/modules/knowledge/**` |
| `tone_safety` | Builds the persona system prompt; runs the **crisis/safety classifier** before any astrology logic | — | `app/modules/tone_safety/**` |
| `chat` | Conversation orchestrator: assembles chart + transits + RAG + persona, calls LLM, streams reply, async memory extraction | astrology_engine, knowledge, tone_safety | `app/modules/chat/**` |
| `content` | Generates daily/weekly/monthly readings, panchangam, nakshatraphalam | astrology_engine | `app/modules/content/**` |
| `whatsapp` | **Daily message generation + send** via BSP; opt-in/opt-out ledger; AI disclosure | content | `app/modules/whatsapp/**` |
| `community` | Audio rooms (temple / area / nakshatra), membership, **moderation**, gifting | identity | `app/modules/community/**` |
| `commerce` | Subscriptions, paid reports (PDF), consult billing, temple pooja booking, Razorpay | identity | `app/modules/commerce/**` |
| `notifications` | Push notifications | content | `app/modules/notifications/**` |
| `admin` | Astrologer onboarding, moderation queue, analytics | most modules (read) | `app/modules/admin/**` |
| `platform` (shared) | Event bus, config, logging, DB access, error types | — | `app/platform/**` |

**Module rule:** a module may import another module's *public service*, never its internal files or its tables. Cross-module side effects go through domain events (e.g. `chat.crisis_detected`, `commerce.report_purchased`).

---

## 5. WhatsApp message generation subsystem

The deep AI conversation lives **in the app**. WhatsApp's only job is one calm, opt-in daily note delivered through a **WhatsApp Channel**. (General-purpose AI chatbots are prohibited on the WhatsApp Business API, so the bot cannot live there.)

### Daily pipeline (Celery beat / arq cron, runs ~05:30 IST)

```
[scheduled task]
   → astrology_engine.get_panchangam(today)        # nakshatram, nalla neram, tithi
   → content.generate_daily_message(panchangam)     # gpt-4o-mini drafts Malayalam copy from a fixed template
   → whatsapp.publish_to_channel(message)            # send via BSP  (HUMAN CHECKPOINT before first live send)
   → log + store for the in-app "today" card
```

### Generation prompt (template the `content` module fills)

```
SYSTEM: You write ONE short Malayalam WhatsApp Channel message for an astrology app.
Tone: warm, calm, like a kind elder. STRICT RULES:
- Max ~45 words. One useful fact + one gentle thought + one soft CTA.
- NEVER predict doom, never mention remedies/payments, never create urgency.
- End with: "സ്വകാര്യമായി ചോദിക്കണോ? 👉 {app_link}"
INPUT: nakshatram={…}, nalla_neram={…}, date={…}
OUTPUT: the message text only.
```

### Compliance (enforced in `whatsapp` module, not left to copy)
- **Opt-in only**; maintain a consent ledger keyed by phone number.
- Every proactive send carries an **opt-out** line and an **AI disclosure**.
- **Max 3 business-initiated messages per user per 24h.**
- Temple admins **share the Channel link**; the system never auto-adds a bot to groups it doesn't own.

---

## 6. Chatbot — the AI astrologer (Tara)

### Request flow
```
user message
  → tone_safety.screen(message)            # crisis classifier FIRST
      ├─ if distress  → safety response + helpline (Tele-MANAS 14416); STOP. no astrology, no upsell.
      └─ else continue
  → identity.get_birth_chart(user_id)        # or compute on first run
  → astrology_engine.get_transits(now, chart)
  → knowledge.retrieve(transits + question)   # RAG over interpretation base (ChromaDB)
  → tone_safety.build_system_prompt(persona, chart, transits, retrieved)
  → chat.call_llm(system_prompt, history, message)   # gpt-4o-mini, streamed
  → stream to client
  → async: chat.extract_memory(conversation)  # store durable facts/preferences (Celery task)
```

### Persona rules (in the system prompt, owned by `tone_safety`)
1. Discloses it is an AI astrologer, warmly.
2. Acknowledges feelings **before** the chart.
3. Every claim ties to a **real transit/placement** — no generic sun-sign filler, no invented dosha.
4. Frames challenges with **agency** ("the stars incline, they don't compel").
5. Knows its limits — hands off to a human or helpline in distress (see `GUARDRAILS.md`).

### Notes
- **Malayalam quality must be tested**, not assumed — `gpt-4o-mini` is noticeably weaker in Malayalam than in English. Keep a regression set of real prompts + reviewed good answers, and spot-check against a stronger model occasionally to catch drift.
- Memory extraction runs as a **Celery task, async** — never block the user's reply on it.

---

## 7. Core data model (starting point)

```
users(id, name, dob, birth_time, birth_place, lat, lng, tz, created_at)
charts(id, user_id, natal_json, computed_at)
conversations(id, user_id, started_at)
messages(id, conversation_id, role, text, created_at)
memories(user_id, key, value, source_msg_id)            # durable facts (Postgres)
knowledge_chunks(id, topic, text, embedding)            # stored in ChromaDB
wa_consent(phone, opted_in, opted_in_at, opted_out_at)  # WhatsApp ledger
daily_content(date, nakshatram, nalla_neram, message_ml)
subscriptions(user_id, tier, status, renews_at)
orders(id, user_id, kind, amount, status, razorpay_id)  # reports, consults, pooja
rooms(id, kind, area_or_temple, host_id, status)        # community audio
room_members(room_id, user_id, role)
astrologers(id, name, langs, rate_per_min, verified)
```

---

## 8. Build sequence in Antigravity

Use the **Agent Manager** with one **manager agent** coordinating module-scoped worker agents. Isolate domains so agents don't conflict; require human checkpoints on anything irreversible.

**Phase 0 — scaffold (manager agent):** repo, FastAPI modular skeleton (`app/modules/*`, `app/platform/*`), Postgres + ChromaDB + Redis wiring, CI, Dockerfile, `AGENTS.md` + `GUARDRAILS.md`.

**Phase 1 — MVP loop (the cheapest thing that proves demand):**
- `identity` → onboarding + birth data
- `astrology_engine` → natal chart + transits via hosted API
- `tone_safety` + `chat` → working AI astrologer (with crisis screen)
- `content` + `whatsapp` → daily Channel message on a Celery/arq schedule

**Phase 2 — money:** `commerce` (subscriptions, porutham/Jathakam reports, Razorpay), human-astrologer consult handoff.

**Phase 3 — moat:** `community` audio rooms with moderation from day one; `admin` dashboards; `notifications`.

**Agent assignment tips**
- One agent per module; declare its file boundary in `AGENTS.md`.
- Run agents in parallel only across **orthogonal** modules (e.g. `knowledge` + `whatsapp`), never two agents in `chat` at once.
- Use **scheduled tasks** for the daily content/WhatsApp job and nightly knowledge re-embedding.
- Require **human approval** for: DB migrations (Alembic), the first live WhatsApp send, anything in `commerce`/payments, AWS infra changes, and changes to `tone_safety` or `GUARDRAILS.md`.

---

## 9. External integrations

| Integration | Module | Via |
|---|---|---|
| Ephemeris / charts | `astrology_engine` | REST (hosted API) → later self-hosted Swiss Ephemeris; expose as an MCP server for agents |
| LLM | `chat`, `content`, `tone_safety` | OpenAI API (`gpt-4o-mini`) |
| WhatsApp | `whatsapp` | BSP (Gupshup/Wati/Twilio) + Channel |
| Payments | `commerce` | Razorpay |
| Geocoding/timezone | `identity` | OpenCage/Google + IANA tz |

Secrets live in **AWS Secrets Manager** (local dev: `.env`, never committed). This is a hard guardrail.

---

## 10. Risks to keep visible
- **Monetization vs. ethics:** removing fear lowers conversion. Lean on consults, reports, community, and temple commerce — not anxiety.
- **Malayalam LLM quality:** test continuously, especially with `gpt-4o-mini` — verify it isn't silently degrading to generic or English-influenced phrasing.
- **Scope creep:** ship Phase 1 before touching audio rooms.
- **Community moderation:** build reporting + room admins before launch, not after an incident.
- **AWS + Antigravity friction:** deployment automation is CLI-driven, not native — keep the `platform`/CI module agent-friendly with clear scripts an agent can run and verify.