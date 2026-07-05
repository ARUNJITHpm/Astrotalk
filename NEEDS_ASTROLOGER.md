# Needs astrologer review

Items Tara's developers could NOT verify and therefore did not wire into
suggestions or the knowledge corpus. A qualified Kerala astrologer / temple
tradition expert should confirm, correct, or reject each before it ships.

## Unverified folk terms (parked — not in any lexicon or corpus)

| Term | What we think it might be | Status |
|---|---|---|
| ദേഹമുട്ട് (dehamuttu) | Possibly a folk vazhipadu/vow related to "മുട്ട്" (obstacle) affecting the body, or a regional name for a known offering. We could not verify a canonical meaning. | ❓ needs definition + which deity/temples + which concern |

Add new uncertain terms here rather than guessing them into the product.

## Drafted content awaiting review (all `reviewed=False` in code)

- `app/modules/knowledge/seed_data.py` — ~250 chunks: planet-in-house grid,
  nakshatras, dashas, lagnas, doshas, prashnam (37), vazhipadu (30),
  deities (15). The vazhipadu/deity texts especially need checking for
  regional accuracy (which offering at which temple, deity associations).
- `app/modules/temples/seed_data.py` — 53 temples: deity, famous_for,
  vazhipadu lists. Coordinates are Google-Places-verified (2026-07-05);
  the devotional content is not.
- `app/modules/temples/remedy_map.py` — concern→deity, graha→deity,
  dosha→deity tables (Kerala remedial convention as we understand it).
- `app/modules/astrology_engine/prashnam.py` — thamboola count scheme is a
  simplified draft; arudha/lagna house classes follow Prasna Marga
  conventions.
- `app/modules/tone_safety/crisis_classifier.py` — keyword screen is a
  PLACEHOLDER; a clinically-reviewed classifier is required before launch.

## Review workflow

Flip `reviewed: False → True` per chunk/entry as the astrologer signs off;
`git blame` records who/when. Items failing review should be corrected or
deleted, never left unreviewed in production.
