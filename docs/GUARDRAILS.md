# GUARDRAILS.md — Tara

Operational rules that must be **enforced in code**, not just followed by convention. If an agent finds a guardrail it cannot satisfy, it stops and asks rather than weakening the rule.

---

## 1. No fear-mongering (product-ethics guardrail)

**Enforced in:** `tone_safety` (system prompt + output checks), `content` (daily message templates).

- Never generate or allow output that invents a dosha, predicts misfortune as certain, or links a "problem" to a paid remedy in the same turn.
- Never use urgency language ("act now", "before it's too late") anywhere — chat, WhatsApp content, or notifications.
- Reports and porutham results must always present the balanced picture and must always include a real, friction-free decline option (e.g. "No thanks") with no follow-up pressure.
- If a generated response reads as fear-based on review, that's a bug — file it against `tone_safety`/`content`, don't patch it as a one-off prompt tweak.

## 2. Crisis & safety routing

**Enforced in:** `tone_safety.screen()`, called first on every chat turn before any astrology logic runs.

- The classifier checks for distress, hopelessness, or self-harm signals before the message reaches the astrology/RAG pipeline.
- On a positive signal: respond with empathy, drop the astrology frame entirely for that turn, and surface Tele-MANAS (14416) or another current, accurate helpline. No horoscope, no remedy, no upsell in that response.
- This path must never be deprioritized, A/B tested away, or skipped for latency/cost reasons.
- Log (without storing unnecessary raw sensitive content) that a crisis-route fired, for review — not for product analytics.

## 3. WhatsApp compliance

**Enforced in:** `whatsapp` module.

- **Opt-in required** before any PROACTIVE send; track in `wa_consent` keyed by phone number.
- Every proactive message includes a visible **opt-out** instruction and discloses it's from an **AI-assisted** service.
- **Hard cap: 3 business-initiated messages per user per 24 hours.** Enforce with a counter, not a manual process.
- **Two-way AI chat** is available on WhatsApp via WAHA (approved 2026-07-09). User-initiated messages receive full Tara responses (same brain as the website). Every outbound reply carries the AI disclosure. The daily cap does NOT apply to user-initiated messages.
- Users who send **STOP** are opted out immediately; sending **START** re-subscribes them.
- Never programmatically join or add a bot to a WhatsApp group the business does not own. Temple/community distribution happens via shared Channel links, by invitation.

## 4. Birth-data & PII privacy

**Enforced in:** `identity`, and every module that touches user data.

- Birth date/time/place are sensitive — never log them in plaintext, never put them in URL query params, never include them in error messages or analytics events.
- Cross-module access to birth data goes only through `identity`'s public service interface — no module reads the `users`/`charts` tables directly.
- Right-to-delete: deleting a user must cascade to `charts`, `conversations`, `messages`, `memories`, and `wa_consent`.

## 5. Payments

**Enforced in:** `commerce`.

- All payment flows go through Razorpay's documented APIs — no custom card/UPI handling.
- Pricing shown to the user before any charge must match what's actually charged; no surprise amounts.
- Refund/cancellation logic for subscriptions must exist before subscriptions ship, not after the first support ticket.

## 6. Secrets & infrastructure

- No API keys, tokens, or credentials in source, commit history, or logs. Use environment variables locally and AWS Secrets Manager in deployed environments.
- Infra changes (ECS, RDS, IAM policies, Secrets Manager entries) require human approval — agents may propose via an Artifact (e.g. a Terraform/CDK diff) but not apply.

## 7. Community moderation

**Enforced in:** `community`.

- Every audio room has a reporting action and at least one designated moderator before it can go live.
- A basic code of conduct must be shown on first join to a room.

---

## When a guardrail and a feature request conflict
The guardrail wins. If a requested feature would require weakening any rule above, the agent should implement the feature in a way that preserves the guardrail and flag the tension to a human rather than silently relaxing the rule.