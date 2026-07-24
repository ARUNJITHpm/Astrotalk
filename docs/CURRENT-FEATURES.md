# Tara — Current Feature Inventory (ground truth)

Verified against the code on 2026-07-15 — not the original plan. `Tara-Project-Documentation.md` is the *day-1 spec* (OpenAI, hosted ephemeris, generic BSP) and is stale; this document reflects what actually runs. Re-verify against `app/modules/*` and `app/platform/config.py` (the `MOCK_*` flags are the source of truth for real vs. stubbed) before relying on this after major changes.

Legend: 🟢 real/live · 🟡 real logic, mocked transport/key by default · ⚪ stub/placeholder, not user-facing yet

---

## Core astrology engine 🟢
- Self-computed **Swiss Ephemeris** (pyswisseph) — no external API — natal chart, transits, panchangam (tithi/nakshatram/nalla neram), sidereal Lahiri/KP/Raman ayanamsa, whole-sign houses.
- Divisional charts: D9 (marriage), D10 (career), D7 (children), D3 (siblings), D12 (parents).
- Full Vimshottari dasha (mahadasha + antardasha) from Moon's natal longitude.
- Deterministic dosha detection: Chovva/Mangal (with classical parihara/cancellation rules), Kala Sarpa, Sade Sati.
- 10 classical Kerala poruthams (compatibility matching) computed in code, directional (bride★→groom★).
- Prashnam (horary): 3 modes — thamboola (leaf count), swarna (arudha rasi), sankhya (number 1–108) — each builds a real chart at question-time.
- 🟡 Gated by `MOCK_EPHEMERIS` (default **on**) — mock mode returns deterministic fake charts for dev/demo.

## AI chat astrologer "Tara" 🟢
- Full pipeline: crisis screen → chart+transits → topical divisional chart → RAG retrieval → cross-session memory → persona prompt → LLM → output guardrail screen → follow-up chips.
- **Crisis/distress screening runs first**, unconditionally — routes to Tele-MANAS 14416 helpline, skips astrology/LLM/memory entirely on a hit.
- **Output guardrail**: regex-screens every LLM reply for fear-mongering, payment-linked remedies, manufactured urgency — one corrective retry, then a hardcoded safe fallback. Enforced in code, not just prompted.
- Deterministic temple-remedy suggestion (capped at 1) and human-astrologer escalation offered on recurring concerns.
- Two LLM providers wired: **Sarvam** (105B/30B, Malayalam-first, default) and **OpenAI** (gpt-4o-mini fallback). 🟡 `MOCK_LLM`/`mock_openai` default **on**.
- Two UI skins (`/` classic, `/ui` cosmic) hitting the identical `/chat/message` API and sharing one login session.

## Knowledge / RAG 🟢🟡
- Hybrid retrieval: BM25 (always on, Malayalam-Unicode tokenizer) + optional dense Chroma/OpenAI-embeddings layer (🟡 off by default).
- Curated seed corpus (1180 lines) incl. nakshatra-relationship traits grounding porutham narration; unreviewed/imported content penalized and capped.

## Identity, auth, growth 🟢
- Bearer-session auth (47h TTL, opaque token, server-side session table — no JWT), PBKDF2-SHA256 (200k rounds) passwords.
- Password reset without email: phone+name+DOB re-verification.
- Phone-number identity unifies web and WhatsApp signups.
- Referral program: 8-char codes, 3 activations unlock a free premium report.
- 🟡 Geocoding chain (Google → Open-Meteo → Nominatim → Kochi fallback) — mocked to Kochi by default.
- **Admin backdoor**: phone numbers listed in `admin_phones` get admin-API access on their normal app session, no separate admin login needed.

## WhatsApp 🟢
- Real two-way conversational onboarding over WhatsApp (collects name/DOB/time/place in Malayalam, then answers the original question) — same brain as web chat.
- Dual transport: **WAHA** (self-hosted/unofficial, default) or **Meta Cloud API** (official, HMAC-verified webhook).
- Consent ledger, opt-in/opt-out keywords, AI-disclosure + opt-out footer on every proactive message (enforced in code), 3-messages/day cap on business-initiated sends.
- 🟡 `MOCK_WHATSAPP` default **on** — logs instead of sending.

## Content pipeline 🟢🟡
- Daily pipeline: panchangam + knowledge nugget → per-platform LLM drafts → tone_safety screen → PNG share-card render (Pillow, Malayalam fonts) → admin approve/publish.
- Content Studio: 5 human-approved content kinds (reel script, weekly astro news, festival special, nakshatra episode, myth buster).
- ⚪ **No live Instagram/YouTube/Facebook publishing exists** — those platforms are always mock-only regardless of flags; only WhatsApp Channel actually sends.

## Temples 🟢
- 53 Kerala temples (Google Places-verified coordinates; devotional copy still unreviewed).
- Partner console: festival calendars, printable QR posters, branded public microsites (`/t/{slug}`) with live panchangam + WhatsApp opt-in, embeddable panchangam widget.

## Astrologers directory & booking 🟡
- 28 astrologers, 2/district across all 14 Kerala districts — **explicitly placeholder/dummy data**, district-HQ coordinates.
- Real booking/availability/slot-conflict logic sits behind the placeholder directory (ready for real practitioners to be swapped in).

## Commerce 🟢🟡
- Razorpay Orders + Subscriptions (HMAC-verified webhooks), 🟡 mocked by default.
- One live product: `premium_report` (₹199) — a real generated PDF from the user's actual chart, cached once/day.
- Entitlement ledger unifies purchase- and referral-based unlocks.

## White-label SaaS (`orgs`) 🟢
- Full multi-tenant model: org handles, plan tiers (starter/pro) with customer caps, Razorpay-billed, CRM-lite (customer list, chart, bookings, notes), persona overlay (capped, wrapped around — never replacing — the safety prompt).
- Transcript access requires the *customer's* explicit opt-in, not the org owner's.
- Branded pages: `/a/{handle}/ui`, `/login`, `/dashboard`.

## Community 🟢
- Live feed (today's panchangam + published content), emoji reactions, daily login streaks, polls with live tallies.

## Admin 🟢
- Dashboard: user/chat browser, config view, usage/cost analytics (LLM token spend). Read-only by design.
- Auth: `X-Admin-Token` header **or** a normal bearer session whose phone is in `admin_phones`.

## Notifications 🟢
- Fixed-template festival reminders (T-3 days), deduped per festival/phone, routed through WhatsApp's consent+cap logic.

## Platform
- Storage: local disk (default) or Cloudflare R2.
- Mongo for chat history/durable memory — degrades gracefully (skips persistence) if unavailable/mocked.
- Cron-token-gated endpoints for an external scheduler (no in-app Celery/Redis needed).
- 29 test files + an `evals/` harness for LLM reply quality; 12 Alembic migrations.

---

## What's real vs. what's still a demo, at a glance

| Area | Status |
|---|---|
| Astrology math (charts/dasha/dosha/porutham/prashnam) | 🟢 Real, self-hosted, no external key needed |
| AI chat + safety guardrails | 🟢 Real logic; 🟡 LLM calls mocked unless key configured |
| WhatsApp | 🟢 Real conversational engine; 🟡 send mocked by default |
| Temples | 🟢 Real directory/partners; devotional copy unreviewed |
| Astrologers | 🟡 Real booking engine, **dummy practitioner data** |
| Payments | 🟢 Real Razorpay integration; 🟡 mocked by default; 1 live SKU |
| Social publishing (IG/YT/FB) | ⚪ Not built — mock-only regardless of config |
| Community | 🟢 Real, fully live |
| White-label SaaS | 🟢 Real, fully built |
