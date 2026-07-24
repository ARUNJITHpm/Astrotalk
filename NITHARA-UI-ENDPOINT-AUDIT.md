# Nithara UI — Endpoint Audit

> **Source of truth: `nithara-v11.html`.** This audit maps every screen and
> sheet in the final UI to the data + actions it needs, then to a backend
> endpoint. The UI drives the contract — where the current backend doesn't
> match, the backend changes, not the UI.
>
> Legend: ✅ exists & usable · 🟡 exists but wrong shape / not public · 🔨 must build

---

## 1. What the prototype actually is

A single-file, offline mobile prototype. **All data is faked in JS** and the
Nithara chat is **scripted**. Nothing calls a server. The job is to replace
these in-page fakes with real endpoints:

| In-page fake (JS) | Becomes |
|---|---|
| `temples[]` (5 hardcoded) | `GET /temples` + `GET /temples/{id}` (real, ~53 seeded) |
| `astros[]` | `GET /astrologers` (already exists) |
| `articles[]` + `FEEDML` | `GET /feed` (public content) |
| `CHAT`/`replies`/`chartQ` (scripted) | `POST /chat/message` + chart setup via astrology engine |
| `MEMBERS[]` | family-members CRUD |
| `BOOKINGS[]` / `CATALOGUE[]` | pooja catalogue + booking orders |
| `PROMOS()` / panchangam strip | `GET /home/promos` + `GET /astrology/panchangam` |
| `ME=[lat,lng]` haversine | device geolocation → `?lat&lng` on temple list |
| `chartDone` boolean | real chart state on the profile |

---

## 2. Data entities the UI requires

Field names below are taken verbatim from the prototype so the frontend needs
no remapping.

**Temple** — `id, en, ml, place, mplace, deity, sig, lat, lng, pooja(bool),
open(bool), closes, rating, reviews, story, mstory, timings{nirmalyam,
morning, evening}, poojas[]` (per-temple catalogue).

**PoojaCatalogueItem** — `key, name{en,ml}, amt, lead(days), note/desc`.

**Booking** — `id, ref, pooja(key|label), temple_id, when(date), state(ok|wait),
member_id`.

**Member (family)** — `id, name, rel(rSelf|rMother|rFather|…), nak(0–26 index),
self(bool)`.

**Astrologer** — `name{en,ml}, sp{en,ml}, ex(yrs), r(rating), p(₹/min), on(bool)`.

**FeedItem** — `img, glyph, live(bool), cat(Festival|Darshan|AstroTalk),
title{en,ml}, body{en,ml}, who{en,ml}, likes, comments, temple_id?`.

**Panchangam / Today** — `date, tithi(e.g. Pradosham), nakshatram(user),
guidance(text)`.

**Chart / Jathakam** — `dob, tob, pob, nakshatram, rasi, lagnam, pada,
dasha{current, pct_elapsed, from, to}, rasi_grid[12]{sign, planets[]}`.

**Nakshatram-day** — next occurrence per nakshatram + `days_until` (27-day cycle).

**Profile stats** — `temples_visited, poojas, streak, badges, milestones[]`.

---

## 3. Per-screen → endpoint map

### Onboarding — "Choose your temple" (`onboard`, `obRoutes`)
Three entry routes: **scan a QR poster**, **search**, **use location**.

| Needs | Endpoint | Status |
|---|---|---|
| Nearby temples by GPS | `GET /temples?lat&lng&sort=near` | 🔨 |
| Search temples by name/place | `GET /temples?q=&by=name\|place` | 🔨 |
| Resolve a scanned temple QR | `GET /temples/by-qr/{token}` | 🔨 |
| Set chosen home temple | `POST /me/home-temple {temple_id}` | 🔨 |
| Anonymous session (no signup) | `POST /identity/anon` (device token) | 🔨 (identity has auth, not anon) |

### Home tab (`s-home`)
| Needs | Endpoint | Status |
|---|---|---|
| Header place + live date | client + `GET /me` | 🟡 |
| Promo rail (Pradosham, Nithara, astrologer, festival, kin-star) | `GET /home/promos` (computed) | 🔨 |
| Panchangam strip | `GET /astrology/panchangam` | ✅ |
| My Temple hero (chosen temple + "reason") | `GET /temples/{id}` + `GET /me/home-temple` | 🔨 |
| Today's poojas (2) | `GET /temples/{id}/poojas?today=1` | 🔨 |
| Nearby (3) | `GET /temples?lat&lng&limit=3` | 🔨 |
| Notices rail (feed) | `GET /feed?temple_id=` | 🔨 |
| Map card + deity filter + count | `GET /temples?lat&lng` (client filters) | 🔨 |

### Poojas tab (`s-poojas`, `renderPoojas`)
| Needs | Endpoint | Status |
|---|---|---|
| Soonest nakshatram day across family | `GET /nakshatram/next?members=` | 🔨 |
| Pooja catalogue w/ lead-time lock | `GET /temples/{id}/poojas` | 🔨 |
| Your bookings (upcoming) | `GET /bookings` | 🔨 |
| Book for star day | `POST /bookings` → order | 🔨 |

### Astro / Jyothisham tab (`s-astro`)
| Needs | Endpoint | Status |
|---|---|---|
| Nithara chat | `POST /chat/message` | ✅ (wire; unscript) |
| "Today for {nakshatram}" | `GET /astrology/today?nak=` | 🔨 (engine exists) |
| Tool: Jathakam (chart setup) | chart-setup flow → `POST /identity/recompute-chart` | 🟡 |
| Tool: Porutham (match) | `GET /astrology/porutham?bride=&groom=` | 🔨 (engine has it, no route) |
| Tool: Muhurtham | `GET /astrology/muhurtham?…` | 🔨 |
| Astrologer list | `GET /astrologers` | ✅ |
| Consult / book astrologer | `POST /astrologers/{id}/book` | ✅ |

### Profile tab (`s-profile`, `renderProfile`)
| Needs | Endpoint | Status |
|---|---|---|
| Chosen temple header + change | `GET /me/home-temple` | 🔨 |
| Stats (temples/poojas/streak/badges) | `GET /me/stats` | 🔨 (community has `streak`) |
| Nakshatram / chart-pending state | `GET /identity/me` (chart) | 🟡 |
| Birth details + Jathakam (rasi grid, dasha bar) | `GET /users/{id}/chart` | 🟡 (shape needs rasi_grid + dasha pct) |
| Bookings | `GET /bookings` | 🔨 |
| Milestones / badges | `GET /me/milestones` | 🔨 |
| Family board (members) | `GET /me/members` | 🔨 |
| Sync / sign-in upsell | `POST /identity/login` (link anon→account) | 🟡 |

### Sheets & flows
| Sheet | Needs | Endpoint | Status |
|---|---|---|---|
| Temple detail (`openTemple`) | story, timings, per-temple poojas, check-in | `GET /temples/{id}` + `POST /temples/{id}/checkin` | 🔨 |
| Search (`openSearch`) | name/place search | `GET /temples?q=&by=` | 🔨 |
| Full map (`openMap`) | all temples + rail cards | `GET /temples?lat&lng` | 🔨 |
| Booking review (`openBook`/`bookDone`) | who-for, fee, confirm, ref no. | `POST /bookings` (+Razorpay) | 🔨 |
| Feed (`openFeed`) | article cards | `GET /feed` | 🔨 |
| Chat (`openChat`) | message + suggestions + chart setup | `POST /chat/message`, `GET /chat/suggestions` | ✅/🔨 |
| Member add/edit (`openMember`) | name, relation, nakshatram | `POST/PATCH/DELETE /me/members` | 🔨 |
| Share (`openShare`) | chart/booking share card | `POST /share/card` (cards.py exists) | 🟡 |
| Location (`openLocation`) | place picker | geolocation + `GET /geo/reverse` | 🔨 |

---

## 4. Consolidated list of endpoints to BUILD

Grouped by module. These are the net-new / newly-public routes.

**temples (public read — the biggest gap; today it's admin/suggest only)**
- `GET /temples` — list/search/nearby (`q`, `by`, `lat`, `lng`, `deity`, `sort`, `limit`)
- `GET /temples/{id}` — full detail (story, timings, ratings)
- `GET /temples/{id}/poojas` — catalogue (`today` filter, lead-time)
- `GET /temples/by-qr/{token}` — resolve scanned poster
- `POST /temples/{id}/checkin` — record darshan

**identity / me**
- `POST /identity/anon` — anonymous device session (no-signup promise)
- `GET /me/home-temple` · `POST /me/home-temple`
- `GET /me/stats` · `GET /me/milestones`
- `GET /me/members` · `POST /me/members` · `PATCH /me/members/{id}` · `DELETE /me/members/{id}`
- chart shape: extend `ChartOut` with `rasi_grid[12]` + `dasha.pct_elapsed`

**poojas / bookings (extend commerce)**
- `GET /nakshatram/next` — soonest star day across members
- `POST /bookings` · `GET /bookings` — pooja booking (Razorpay order under the hood)

**astrology_engine (expose existing services)**
- `GET /astrology/today?nak=` — today-for-nakshatram guidance
- `GET /astrology/porutham?bride=&groom=`
- `GET /astrology/muhurtham?…`

**content / feed**
- `GET /feed` — public notices/articles (`temple_id`, `cat` filters)

**home**
- `GET /home/promos` — computed promo rail

**Reused as-is:** `POST /chat/message`, `GET /chat/history`, `GET /astrology/panchangam`,
`GET /astrologers`, `GET /astrologers/{id}`, `POST /astrologers/{id}/book`,
`POST /notifications/*` (for nakshatram reminders / FCM).

---

## 5. Backend features NOT surfaced by this UI (out of scope for v1)

Present in the codebase, but the Nithara UI doesn't use them — leave running,
don't build UI for them now: `orgs/` (white-label/SaaS), `commerce` subscriptions
& premium PDFs (Nithara uses per-pooja booking instead), `whatsapp/` channel,
`community` polls/audio-rooms, `admin` dashboard, `knowledge` RAG (used *inside*
chat, not a screen).

---

## 6. Effort summary

- **~18 new/newly-public endpoints**, concentrated in **temples** (public read),
  **bookings**, and **me/members** — these are the temple-first pivot the old
  astrologer-first backend never needed.
- **Reused with zero change:** chat brain, panchangam, astrologers, notifications.
- **Reused with a shape tweak:** chart (`ChartOut`), share cards, login/link.
- The astrology *math* (porutham, muhurtham, panchangam, dasha) all exists in
  `astrology_engine` — most of that work is exposing routes, not new logic.
