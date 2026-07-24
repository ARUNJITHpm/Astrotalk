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

## Part 3 — Astrology surface + shared conversational chart-setup
```
Read the Astro tab (renderTools, openPorutham, openMuhurtham), the chat chart-
setup flow (chartQ, chartAns, chartDone), renderProfile()'s Jathakam (rasiHtml,
dasha), AND app/modules/whatsapp/onboarding.py (the FSM) + app/modules/chat/
service.py (the single brain that already grounds on chart-if-present).

--- A. Expose astrology services that already exist ---
In app/modules/astrology_engine/router.py:
- GET /astrology/today?nak= — today-for-nakshatram guidance (tithi + one-line
  reading). Guidance-only per GUARDRAILS.
- GET /astrology/porutham?bride=&groom= — nakshatram compatibility (engine
  already computes porutham; wrap it).
- GET /astrology/muhurtham?date=&purpose= — auspicious windows.

--- B. ONE brain, ONE conversational collector (do NOT build a third path) ---
Architecture rule: Nithara chat, WhatsApp, and the website form must all share
the SAME chat brain (chat/service.py) and the SAME chart-collection FSM. Today
that FSM lives inside whatsapp/onboarding.py keyed by phone (WASession). It must
become channel-agnostic.

1. EXTRACT the onboarding FSM out of app/modules/whatsapp/ into a shared,
   channel-agnostic module (app/modules/chat/onboarding.py, or identity/). Keep
   its parsers (parse_dob, parse_time), step prompts (collect_name → collect_dob
   → collect_time → collect_place), and the final IdentityService.create_user()
   call. Key the FSM state by user_id / anon-session token instead of phone.
2. REFACTOR whatsapp/ to call the extracted collector (phone is just one key
   type). Behavior and the existing whatsapp tests must not change.
3. In POST /chat/message, apply the runtime rule:
     - load chart (identity.get_chart) as service.py already does;
     - if a chart EXISTS -> answer grounded in it (unchanged);
     - if NO chart AND the message is a personal/chart question -> enter the
       shared FSM (ask DOB -> time -> place), save via create_user, then answer
       the ORIGINAL question. This is exactly the WhatsApp behavior, in-app.
   The website profile form remains a non-conversational way to set the same
   details -> same create_user -> same chart. No separate logic.
4. DELETE the prototype's scripted chartQ/chartAns/replies in the frontend
   (Part 8); the in-app "Set up my birth chart" flow becomes real FSM turns over
   POST /chat/message. The profile's chartDone boolean becomes real chart state.

--- C. Extend the chart shape for the profile UI ---
- Extend ChartOut with rasi_grid[12]{sign, planets[]} and
  dasha{current, pct_elapsed, from, to} so the profile rasi grid + dasha bar
  render from real data.

Tests: tests/astrology_engine/ (porutham/muhurtham/today routes);
tests/chat/ (the FSM: no-chart question triggers collection, saves, then answers;
existing-chart question skips collection); tests/whatsapp/ (unchanged behavior
after the extraction); tests/identity/ (chart shape).
```

## Part 4 — Feed, promos, and nakshatram reminders (FCM)
```
Read renderFeed()/renderNotices() (articles[]+FEEDML), PROMOS(), and the
notifications need (nakshatram reminders = the retention loop).

- GET /feed?temple_id=&cat= — public notices/articles from app/modules/content
  (bilingual title/body/who, likes, comments, live flag, optional temple_id).
- GET /home/promos — server-computes the promo rail: Pradosham-today, Nithara,
  featured astrologer, live festival, and per-member kin-star banners inside the
  4-day window. Mirror the priority logic in PROMOS().
- Wire app/modules/notifications for FCM push: schedule a reminder N days before
  each member's nakshatram day (Celery beat, like the existing 05:30 job).
Tests in tests/content/ and tests/notifications/.
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
