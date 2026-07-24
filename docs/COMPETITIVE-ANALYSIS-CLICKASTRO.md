# Tara vs. ClickAstro — Competitive Feature Analysis

Compiled 2026-07-15. Tara's side is verified against the codebase (see `CURRENT-FEATURES.md`). ClickAstro's side is from its public site (clickastro.com) — reports, pricing pages, and app-store listing — not an account audit, so treat it as what they advertise rather than a full internal inventory.

## Snapshot

| | **Tara** | **ClickAstro** |
|---|---|---|
| Core identity | AI conversational astrologer, WhatsApp-native, Kerala/Malayalam-first | Report/consultation marketplace, since 1984, 110M+ customers claimed |
| Primary interaction | Chat with an AI persona, ongoing conversation + memory | One-off report purchase or paid live consult |
| Astrology compute | Self-hosted Swiss Ephemeris, full transparency | Proprietary, not exposed to the user as "how it's computed" |
| Languages | Malayalam-first (by design, not yet multi-language) | 11 regional languages incl. Malayalam |
| Monetization | Freemium chat + ₹199 premium report + org SaaS | Pay-per-report (₹1200+ in-depth) + pay-per-minute live consult (₹10–100/min) |

## Where Tara is ahead

- **Conversational AI astrologer with memory.** ClickAstro has no chatbot — it's forms → PDF report, or a human on a paid call. Tara holds a running conversation, remembers durable facts about the user, and grounds every claim in the user's actual computed chart rather than a static report.
- **Safety-first architecture.** Crisis screening before any astrology response, and a code-level output guardrail that blocks fear-mongering/doom/manufactured urgency — ClickAstro (and most of the category) has no equivalent; astrology content in this space is often fear- and remedy-upsell-driven.
- **WhatsApp-native onboarding.** A user can complete signup and get answers to a real personal question entirely inside WhatsApp, in Malayalam, no app/website visit required. ClickAstro's WhatsApp presence (if any) isn't part of its advertised product.
- **Kerala-specific depth.** 10 classical *poruthams* computed directly (not just a generic compatibility score), Kerala-specific temple directory (53 temples) with festival calendars and partner microsites, Kerala-district astrologer directory. ClickAstro's matching/porutham features are more generic pan-India Vedic, not Kerala-specialized.
- **White-label SaaS.** Tara can spin up a branded, multi-tenant instance for a temple/astrologer/business (own persona, billing, CRM) — ClickAstro has no equivalent offering-as-a-platform.
- **Transparent, self-hosted computation.** No reliance on a black-box ephemeris vendor; every chart/dasha/dosha is computed and testable in-repo (29 test files covering the astrology math specifically).
- **Community layer.** Live panchangam feed, streaks, polls — light social/habit-forming engagement ClickAstro doesn't have.

## Where ClickAstro is ahead

- **Scale and trust.** 40+ years in market, huge claimed user base, brand recognition — Tara has none of this yet.
- **Human astrologer marketplace at volume.** Real, paid, phone/chat consultations with a large panel of astrologers today. Tara's astrologer directory is **explicitly placeholder data** (28 dummy entries) — booking logic exists but there are no real practitioners behind it yet.
- **Breadth of calculators/tools.** Moon/sun sign, nakshatra finder, lucky number, birth-time rectification, sade-sati calculator, etc. — many small stand-alone tools driving SEO/organic traffic. Tara doesn't expose these as discrete public tools.
- **Report catalog depth.** Career, wealth, education, numerology, feng shui, gemstone recommendations, baby naming, celebrity horoscopes — a much wider product catalog than Tara's single premium-report SKU.
- **Pandit/puja booking marketplace.** Books real pandits for pujas/havans across 20+ categories — Tara's temple module suggests temples/remedies but doesn't book a pandit/ritual.
- **Multi-language reach.** 11 languages vs. Tara's deliberate Malayalam-only focus — a scale advantage if Tara ever expands beyond Kerala.
- **Native mobile apps** on Play Store/App Store plus PC software — Tara is web/WhatsApp only today, no packaged app.
- **Social publishing reach** (implied, via SEO/blog/RSS breadth) — though notably ClickAstro's own site shows no AI chat, no live community feed, and no WhatsApp-native flow, so its "reach" is content-marketing breadth, not engagement depth.

## Net read

Tara is not competing on ClickAstro's terms (report catalog breadth, live-astrologer marketplace scale, SEO tool sprawl) — it's differentiated on **depth of one relationship** (an ongoing, memory-holding, safety-guarded AI conversation) and **Kerala-specific trust surfaces** (temples, Kerala poruthams, Malayalam-native WhatsApp onboarding). The two biggest gaps to close before that differentiation converts to revenue at ClickAstro's scale: real astrologers behind the booking system (currently dummy data), and a wider report/tool catalog if organic/SEO acquisition matters to the growth plan.
