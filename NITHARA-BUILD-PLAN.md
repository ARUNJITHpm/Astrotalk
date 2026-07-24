# Nithara — Partwise Build Plan

> Builds the entire new product from `nithara-v11.html`.
> **Backend:** keep the existing FastAPI modular monolith in `app/` — add the
> public endpoints from [`NITHARA-UI-ENDPOINT-AUDIT.md`](NITHARA-UI-ENDPOINT-AUDIT.md).
> **Frontend:** new **React + Vite + TypeScript PWA**, wrapped in **Capacitor**
> for Play Store / App Store. One codebase → web + Android + iOS.
>
> Each **Part** below is a self-contained prompt. Paste it into Claude Code and
> let it run; parts are ordered so each builds on the last. Backend parts (0–4)
> and the frontend scaffold (5) can proceed in parallel once 0 lands.

---

## Ground rules (applies to every part)

- **Do not fork the backend.** All new routes live in the existing
  `app/modules/*`. The UI is the source of truth for shape — match field names
  in `nithara-v11.html` so the frontend needs no remapping.
- **Bilingual by default.** Every user-facing string ships `{en, ml}`; this maps
  1:1 to the prototype's `STR{}` and to `react-i18next`.
- **No-signup promise.** Anonymous device session first; account is optional and
  only *links* an existing anon session.
- **Guardrails.** Honor `docs/GUARDRAILS.md` (no birth data on temple-suggest
  endpoints, guidance-only disclaimers on chat/tools).
- **Tests.** Every backend part adds pytest under `tests/<module>/`. Every
  frontend part adds a Vitest/RTL test for the screen's data states.

---

# BACKEND

## Part 0 — Temples public read API + data enrichment
```
Read NITHARA-UI-ENDPOINT-AUDIT.md §3–4 and nithara-v11.html (temples[] array,
openTemple(), doSearch(), renderMap()).

In app/modules/temples/, add a PUBLIC read surface (no admin guard):
- GET /temples  — list/search/nearby. Query: q, by(name|place), lat, lng,
  deity(Shiva|Devi|Vishnu), sort(near|rating), limit. Returns the Temple shape
  the UI uses: id, en, ml, place, mplace, deity, sig, lat, lng, pooja, open,
  closes, rating, reviews. Compute `open`/`closes` from timings + server time,
  and haversine distance when lat/lng given.
- GET /temples/{id} — full detail incl. story, mstory, timings{nirmalyam,
  morning, evening}.
- GET /temples/by-qr/{token} — resolve a scanned poster to a temple id.

Enrich seed_data.py so the ~53 temples carry: story (en) + mstory (ml),
timings, rating, reviews, deity→sig, and a per-temple pooja catalogue
(pushpanjali/pArchana/pNeyvilakku/ganapathi with amt + lead days).
Add Pydantic schemas TempleOut, TempleDetailOut, PoojaCatalogueItem.
Add tests/temples/ covering search, nearby-sort, open/closed computation.
Do NOT change /suggest or the admin/partner routes.
```

## Part 1 — Poojas, nakshatram-day engine & bookings
```
Read renderPoojas(), openBook(), bookDone(), the CATALOGUE, BOOKINGS, and the
STAR_CYCLE/nextStarFor()/soonestStar() logic in nithara-v11.html.

- GET /temples/{id}/poojas?today=  — per-temple catalogue with lead-time lock
  (a pooja is locked when lead > days_until_star).
- GET /nakshatram/next?members=csv — soonest star day across the given members,
  using the real 27-day nakshatram cycle from astrology_engine (not the demo
  offset). Returns {nakshatram, member_id, date, days_until} sorted soonest.
- POST /bookings {temple_id, pooja_key, member_id, when} — creates a booking,
  returns {id, ref}. Route the payment through app/modules/commerce (Razorpay
  order); ₹15 service fee as in the UI. GET /bookings lists upcoming with
  state(ok|wait).
Add models + migration (Alembic) for bookings. Tests in tests/commerce/ or a
new tests/bookings/.
```

## Part 2 — Family members, profile stats, milestones, check-in
```
Read MEMBERS[], openMember(), whoStrip(), renderProfile() (stats + milestones),
and openTemple()'s check-in button.

- CRUD /me/members: GET, POST, PATCH/{id}, DELETE/{id}. Member = {id, name,
  rel, nak, self}. Exactly one self row; deleting reassigns whoId to self.
- GET /me/stats — {temples_visited, poojas, streak, badges}. Reuse
  community.streak for streak.
- GET /me/milestones — the badge list (msFirst, msTen, msPooram, msRank,
  msDistrict) with got/target.
- POST /temples/{id}/checkin — records a darshan, advances streak + stats.
Migration for members + check-ins. Tests in tests/identity/.
```

## Part 3 — Astrology surface (chat just reuses /chat/message)
```
Read the Astro tab (renderTools, openPorutham, openMuhurtham) and
renderProfile()'s Jathakam (rasiHtml, dasha).

--- A. Astrology tool endpoints (astrology_engine) ---
- GET /astrology/today?nak= — today's panchangam, flagged when it is that
  nakshatram's day. Guidance-only per GUARDRAILS (facts + a light note).
- GET /astrology/porutham?bride=&groom= — the ten Kerala poruthams from two
  nakshatram indices (each star's rasi = the sign at its midpoint; the engine's
  compute_porutham does the grading). Facts only.
- GET /astrology/muhurtham?date=&purpose= — auspicious-window guidance from the
  day's nalla neram (Abhijit muhurta).

--- B. Chat: reuse the SAME route, no new machinery ---
IMPORTANT (design decision): the Nithara app chat calls the existing
POST /chat/message directly, synchronously. The WhatsApp module's extra
machinery (WASession FSM, async send, egress-window background retry) exists
ONLY to work around the WhatsApp Cloud API's send-timeout — the frontend has no
such constraint. So DO NOT extract or rebuild the onboarding FSM. The one brain
in chat/service.py already grounds answers on the chart when one exists; birth
details are set via the profile form (recompute-chart). Same route, that's it.

--- C. Chart shape: derive on the frontend, no ChartOut change ---
The natal chart already embeds `planets` (each with rasi + whole-sign house) and
a `dasha` timeline. The profile's rasi grid and dasha bar are derived on the
frontend from that existing JSON — no backend restructure.

Tests: tests/astrology_engine/ (porutham/today/muhurtham routes + bad-index).
```

## Part 4 — Feed + nakshatram reminders (promos stay frontend-composed)
```
Read renderFeed()/renderNotices() (articles[]+FEEDML), PROMOS(), and the
notifications need (nakshatram reminders = the retention loop).

- GET /feed?temple_id=&cat= — curated bilingual notices/articles seed in
  app/modules/content (title/body/who both languages, likes, comments, live
  flag, optional temple_id → a real seed temple). Read-only MVP; admin CRUD +
  real reaction counts (community already reacts to content) can layer later.
- FCM push (app/modules/notifications): DeviceToken store +
  POST /notifications/devices (user registers an FCM token); a mock push client
  (mock_fcm, logs not dispatches); POST /notifications/run-nakshatram-reminders
  — a cron endpoint (like run-festivals) that pushes T-3 reminders per family
  member's star day, idempotent via notification_log. Uses the Part 1
  nakshatram cycle + Part 2 members.

- GET /home/promos: NOT built server-side. The promo rail is presentation logic
  the frontend composes from data already exposed — panchangam (today's tithi),
  astrologers, members, and /astrology/nakshatram/next (kin-star banners) —
  exactly as the prototype's PROMOS() does client-side. Keeping it out of the
  backend avoids baking UI banner logic into an endpoint.

Tests in tests/content/ (feed) and tests/notifications/ (reminders).
```

---

# FRONTEND  (React + Vite + TypeScript · PWA · Capacitor)

## Part 5 — Scaffold: Vite PWA + design tokens + i18n + API client + Capacitor
```
Create a new frontend app in /app-nithara (sibling to app/), do NOT touch app/web.

Stack: Vite + React + TypeScript, vite-plugin-pwa (service worker + manifest),
react-router, react-i18next, @tanstack/react-query, leaflet + react-leaflet,
Capacitor core.

Migration from nithara-v11.html (mechanical):
1. Move the ENTIRE <style> block into src/styles/globals.css VERBATIM. KEEP the
   CSS custom properties (:root variables) exactly — do NOT convert to Tailwind.
2. Move the <svg><symbol> sprite sheet into src/components/IconSprite.tsx.
3. Convert STR{} (and SEC/SECSUB) into src/i18n/{en,ml}.json resources; build a
   T()/T2() equivalent on top of react-i18next. Language toggle persists.
4. Build the app shell: fixed 432px .phone frame, .screen router, the floating
   .nav tab bar (home/poojas/astro/profile), .scrim + sheet system, and the
   overlay/inert logic from syncOverlay().
5. src/api/client.ts — typed fetch wrapper (base URL from env, bearer/anon
   token, react-query hooks). Define TS types from the audit's entity list.
6. capacitor.config.ts + init; web build target = dist/. Add npm scripts:
   dev, build, cap:sync, cap:android, cap:ios.
Deliver a running shell with all four empty tabs, language toggle, and a health
call to the backend. No screen content yet.
```

## Part 6 — Home + Onboarding + Temple detail + Search + Map
```
Port these screens from nithara-v11.html into React components, driven by the
Part 0/1/4 endpoints (react-query):

- Onboarding (Choose your temple): scan / search / nearby routes; POST home-temple.
- Home: promo rail (auto-advance, dots), panchangam strip, My Temple hero,
  today's poojas, nearby(3), notices rail, deity-filtered map card.
- Temple detail sheet: the 3D "darshan doors" reveal (port revealWithDoors +
  the .doors CSS), tabs (About/Timings/Poojas), check-in, directions.
- Search sheet (name/place segments) and Full map sheet (Leaflet, pins, rail
  cards, deity chips, recenter).
Reuse Leaflet exactly (tiles/attribution/divIcon pins). Each component reads real
data; keep the field names. Vitest tests for loading/empty/error states.
```

## Part 7 — Poojas tab + Booking flow + Family members
```
Port renderPoojas(), the booking review/confirm sheets (openBook/bookDone), and
member add/edit (openMember/whoStrip). Wire to Part 1 + Part 2:
- Star countdown card, catalogue with lead-time locks, upcoming bookings.
- Booking review → Razorpay (Capacitor native SDK on device, web checkout on
  web) → confirmation with ref number → optimistic insert into bookings list.
- "Who for" member chips; add/edit/delete members with relation + nakshatram.
Tests for the lock logic and the who-for selection.
```

## Part 8 — Astro tab + Profile tab
```
Port the Astro screen (Nithara chat, Today-for-nakshatram, the three tools,
astrologer list) and the Profile screen (before/after chart states).
- Chat: real POST /chat/message with typing indicator, suggestion chips, and the
  chart-setup flow that persists a real chart (Part 3). Replace ALL scripted
  replies.
- Tools: Porutham + Muhurtham sheets backed by /astrology/*.
- Profile: home-temple header, stats, milestones, family board; before-chart
  (setup CTA) vs after-chart (birth details + rasi grid + dasha bar) driven by
  real chart state. Share card via existing cards.py.
Tests for both chart states and a mocked chat exchange.
```

## Part 9 — Capacitor native + store builds
```
Add the native capabilities the product needs:
- @capacitor/push-notifications → FCM; register token with /notifications;
  handle nakshatram reminder taps → deep-link to Poojas.
- @capacitor/geolocation → feed lat/lng into /temples nearby + onboarding.
- QR scan (barcode plugin) for the onboarding "scan poster" route → /temples/by-qr.
- Razorpay native SDK on device.
- Verify offline: service worker caches shell + last temple; graceful offline UI.
Produce signed Android (AAB) and iOS builds; document the release steps in
docs/NITHARA_MOBILE_RELEASE.md.
```

## Part 10 — Phase 2 (deferred): public SEO website
```
NOT month one. Build nithara.com as a separate Astro static site for SEO:
server-rendered temple pages + festival articles from the same backend
(GET /temples, GET /feed). This is the organic-acquisition channel a
Capacitor SPA can't provide. Kept separate so the app stays a clean static-export
PWA. (If one framework is ever mandated, Next.js can do both — but that config
cost isn't worth paying now.)
```

---

## Sequencing at a glance

```
Part 0 (temples API) ──┬─► Part 1 (poojas/bookings) ─► Part 2 (members/profile)
                       ├─► Part 3 (astrology surface)
                       └─► Part 4 (feed/promos/FCM)
Part 5 (scaffold) ─────► Part 6 (home/temple) ─► Part 7 (poojas) ─► Part 8 (astro/profile)
                                                                    └─► Part 9 (native/stores)
Part 10 (SEO site) — after launch
```

Backend 0–4 and frontend scaffold 5 run in parallel. Frontend 6–8 each consume a
finished backend part, so land backend slightly ahead of its matching screen.
