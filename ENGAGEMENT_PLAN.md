# Tara — Content, Feed & Channel Growth Plan

Companion to `GROWTH_PLAN.md`. Covers four things:
(A) a user-facing **Feed page** so users engage beyond the chatbot,
(B) an **Admin Content Studio** — generate ready-to-post assets even while
    auto-publishing stays mocked,
(C) the **YouTube + Instagram channel strategy** (manual posting first),
(D) **Malayalam TTS** options for audio/video content.

**What already exists and is reused everywhere below** — do not rebuild:
- `content/pipeline.py` — daily pack (WA/FB/IG/YT drafts) + rendered cards, tone-screened.
- `content/share_cards.py` — personal + 27 daily nakshatra cards, `/s/{slug}` OG landing.
- `/admin` Content tab — list, edit, approve, publish (publishers mocked except WA path).
- `astrology_engine` (panchangam/dasha/porutham), `knowledge` corpus, `temples` festival data.
- `community/` — empty stub with router mounted (this plan gives it its first feature).

**Hard rules carried over (AGENTS.md):** every public text passes `tone_safety`;
no fear-based content ever; migrations need human approval; new external
services (TTS) need human approval + a `MOCK_*` flag.

---

## Part A — User Feed page ("Today" tab)

**Goal:** a reason to open Tara daily that isn't "I have a question." The chat
is pull; the feed is push. This is also where streaks, reactions, and shares live.

**Route:** `/ui/feed` (link it in the chat header as "ഇന്ന്" / Today). Public
read (so shared links work + Google indexes it), session auth for reactions.

**What's on the page (top to bottom):**
1. **Your day** (logged-in): the user's nakshatra card for today — reuses
   `GET /content/cards/daily/{nakshatra}`, pinned first. One-tap Share
   (Web Share API → WhatsApp Status). CTA: "Ask Tara about this" → opens chat
   with a prefilled question. This is the feed→chat funnel.
2. **Today's panchangam post** — the daily pack already drafts a `wa_channel`
   body; surface the approved one as the feed's hero post + card image.
3. **Festival countdown** — next 1–2 festivals from `temples` seed data,
   T-minus days, link to the temple microsite when Part 3 lands.
4. **Knowledge nugget / tip of the day** — one item from the `knowledge` corpus.
5. **Recent days** — scroll back through past published posts (archive =
   SEO surface; see growth ideas).

**Engagement mechanics (ship in this order — each is small):**
- **Reactions** 🙏 ❤️ ✨ — first real `community/` feature. One table:
  `post_reactions (user_id, post_id, emoji, created_at)`, unique per
  user+post. No comments yet — comments need moderation; reactions don't.
- **Daily streak** — `user_checkins (user_id, day)`; feed visit records it;
  show "🔥 7 ദിവസം" chip. Cheap, proven retention lever.
- **Weekly poll** — one lightweight poll post per week (e.g. "ഏത് ദിവസമാണ്
  നിങ്ങൾക്ക് ഏറ്റവും നല്ലത്?"), options + counts. Table: `poll_votes`.
- **Comments — later, deliberately.** Only after moderation exists (tone_safety
  screen on submit + admin delete). Not in v1.

**New endpoints:**
- `GET  /community/feed?before=` — assembled feed (published content_posts +
  today's dynamic items). Public, cacheable.
- `POST /community/posts/{id}/react` (session auth)
- `POST /community/polls/{id}/vote` (session auth)
- `GET  /community/streak` (session auth)

**New tables (one Alembic migration, human-approved):**
`post_reactions`, `user_checkins`, `polls`, `poll_votes`.

**Module boundaries:** `community` owns reactions/streaks/polls and calls
`content`'s public service for posts. It never touches `content_posts` directly.

*Effort: ~3–4 sessions (1 backend tables+endpoints, 1–2 feed UI, 1 polish/tests).*

---

## Part B — Admin Content Studio (manual-first publishing)

**Goal:** auto-publishing to Meta/YouTube stays mocked until those API apps
exist — fine. The studio makes the admin Content tab produce **everything you
need to post manually from your phone**: script, caption, hashtags, card image,
audio file. You post to your own Insta/YouTube by hand; Tara tracks it.

**New generation routes (all admin-token, all under `/content`):**
- `POST /content/generate` — body: `{ kind, platform, topic?, day? }`.
  Kinds beyond the daily pack:
  - `reel_script` — 45–60s spoken-Malayalam script, structured **Hook (3s) /
    Body / CTA**, plus a caption block (Malayalam + 3–5 hashtags).
  - `weekly_astro_news` — "ഈ ആഴ്ചയിലെ ജ്യോതിഷ വിശേഷങ്ങൾ": transits, upcoming
    festivals (temples data), the week's nakshatra highlights. Your weekly
    YouTube script.
  - `festival_special` — auto-picks the next festival ≤7 days out.
  - `nakshatra_episode` — one of 27 evergreen "know your nakshatram" scripts
    (a whole series from one button).
  - `myth_buster` — the brand differentiator: gentle "no-fear" corrections of
    common astrology scares. tone_safety makes this category safe by design.
  Rows land in `content_posts` as `draft` with new `kind` values — the existing
  review→approve flow applies unchanged.
- `POST /content/posts/{id}/audio` — TTS the post body → MP3 in storage
  (Part D). Button in admin: "🔊 Generate audio", then a download link.
- `POST /content/posts/{id}/mark-published` — body: `{ external_url }`. For
  manual posting: you upload to YouTube/Insta yourself, paste the link, the
  row flips to `published` so metrics and the feed archive stay truthful.
- *Stretch:* `POST /content/posts/{id}/video` — ffmpeg: card PNG + audio →
  1080×1920 MP4 (static card with waveform or slow zoom). This is "good
  enough" for daily Shorts; keep human-made video for the weekly hero.

**Admin UI additions (same `admin.html` Content tab):**
- A "Generate…" panel: kind dropdown, optional topic, Go → draft appears.
- Per-post: copy-caption button, card preview (exists), audio player +
  download, "Mark published" with URL field.
- A "Download day pack" that zips card + audio + captions for one day —
  your entire morning posting routine becomes: open admin, download, post.

**Daily manual workflow this enables (~10 min/morning):**
1. Cron drafted the pack at 5:30 (already works). 2. You review/edit/approve
in admin. 3. Generate audio → (stretch: video). 4. Download pack. 5. Post
Short + Reel + Story from your phone; WA Channel publishes via the real path.
6. Paste links back → marked published → appears on the user Feed.

*Effort: ~3–4 sessions (1 generate kinds + templates, 1 TTS route, 1 admin UI,
1 zip/mark-published/tests). Video stretch +2.*

---

## Part C — YouTube + Instagram channel strategy

**Should you start the channel now? Yes — before the automation is ready.**
Channels take months to gather momentum; the algorithm rewards consistency,
not tooling. Manual posting with studio-generated assets is exactly how to
start. One YouTube channel + one Instagram handle, same name/branding as the
app ("Tara" + Malayalam tagline), link-in-bio → the app.

**Daily vs weekly: do both, but they're different products.**
- **Daily = Shorts/Reels (60s), fully pipeline-driven.** ഇന്നത്തെ പഞ്ചാംഗം:
  nakshatram, tithi, nalla neram, one actionable tip. Card + TTS voiceover.
  Post at a fixed time — **6:00–6:30 AM IST** (panchangam is a morning
  ritual; consistency trains both the audience and the algorithm).
- **Weekly = one longer video (3–6 min), your "astro news" show.** "ഈ ആഴ്ച
  ആകാശത്ത്": transits, festivals, what it means — informative, zero fear.
  Script from the studio; **your own voice/face if at all possible** — a
  human host grows a channel far faster than TTS. TTS is the fallback.

**Six content pillars (rotate so the feed isn't monotone):**
1. Daily panchangam Short (the metronome)
2. Weekly astro news (the show)
3. Nakshatra series — 27 evergreen episodes (searchable forever: people
   Google their own nakshatram)
4. Festival specials (Vishu, Onam, Thiruvathira… — traffic spikes)
5. **Myth-busting / no-fear astrology** — nobody else in the Malayalam
   astrology space does this; it's the brand
6. Porutham & relationships (highest-intent audience for the app)

**Channel→app funnel:** every video CTA = "നിങ്ങളുടെ nakshatram-നു വേണ്ടി Tara-യോട്
ചോദിക്കൂ" + link in bio/pinned comment → `/s/` landing or `/ui/login?ref=` so
installs are attributable. Reply to early comments personally; each reply is
free reach.

**Packaging details that matter:** Malayalam title + English keywords in the
description ("Malayalam astrology, panchangam today, [nakshatra] 2026");
consistent thumbnail template (reuse the card renderer); playlists per pillar;
hashtags: 3–5 focused, not 30.

*Cost: ₹0. Time: ~10 min/day + ~1–2 hrs/week for the weekly video.*

---

## Part D — Malayalam TTS (audio) options

All usage below is tiny: a 60s daily script ≈ 900–1,200 chars → **~35K
chars/month**, far inside every free tier. Adding a TTS provider = new
external dependency → needs human approval per AGENTS.md, and gets a
`MOCK_TTS=true` flag like everything else. (Verify current pricing before
signing up — tiers move.)

| Provider | Malayalam quality | Cost at your volume | Notes |
|---|---|---|---|
| **Sarvam AI — Bulbul** | Best-in-class for Indian languages; natural Malayalam voices | Free credits to start; very cheap after (Indian pricing) | **Recommended primary.** You already planned Sarvam for the LLM — one vendor, one API key. Built for exactly this use case. |
| **Azure Speech** | Good — `ml-IN-SobhanaNeural` (F), `ml-IN-MidhunNeural` (M) | Free tier ~500K chars/mo → ₹0 for you | **Recommended fallback.** Reliable, generous free tier. |
| **Google Cloud TTS** | Decent ml-IN voices, slightly flat | ~1M chars/mo free (WaveNet) | Fine alternative to Azure. |
| ElevenLabs | Most expressive, but Malayalam support is newer/less proven | $5+/mo | Only for the weekly hero video if TTS voices there disappoint — test first. |
| AWS Polly | **No Malayalam** | — | Skip. |

**Recommendation:** wire `content/tts.py` against **Sarvam Bulbul** with
**Azure** as the fallback provider behind the same interface. Total spend at
launch: **₹0**. Don't buy any subscription until a provider's free tier is
actually exhausted.

---

## Part E — Growth & engagement ideas (beyond the builds)

**Retention (make them come back):**
- Streaks + a gentle daily WhatsApp/notification nudge ("ഇന്നത്തെ നിങ്ങളുടെ
  നക്ഷത്രഫലം തയ്യാർ") — consent + 3/day cap already enforced by the whatsapp module.
- Personalized feed ordering (user's nakshatra first) — data already exists.
- "This week for you" — one weekly personalized summary post in the feed
  (dasha context from the engine). Premium teaser: first paragraph free.

**Acquisition (make them arrive):**
- **SEO — probably the highest-leverage free channel:** the feed archive as
  public, crawlable pages. "ഇന്നത്തെ പഞ്ചാംഗം", "[nakshatra] ഫലം ഇന്ന്" are
  searched daily in Kerala with weak competition. 27 nakshatra pages ×
  every day = compounding long-tail. (The daily-card endpoints already
  exist; this is mostly making them indexable HTML.)
- WhatsApp Channel as the primary Kerala distribution (already the plan) —
  put the channel link in every video description.
- Collabs: Malayalam astrology/temple/devotional pages and small YouTubers —
  offer them free porutham reports for their audience as a cross-promo.
- Festival campaigns: Vishu and Onam are your Super Bowl. Plan 2 weeks of
  special content + a shareable "Vishu phalam card" ahead of each.
- Temple QR codes (GROWTH_PLAN Part 3) — physical-world distribution nobody
  else has.

**Virality (make them share):**
- After every good chat answer: "ഇത് card ആയി share ചെയ്യൂ" — the personal
  share-card endpoint already exists; the nudge in chat UI is the missing 10%.
- Referral loop (GROWTH_PLAN Part 2): share cards carry the ref code already;
  reward = premium report once commerce lands (5b).
- Poll results as content: "68% പേർക്ക് വ്യാഴാഴ്ചയാണ് നല്ല ദിവസം" — feed polls
  become next week's Reels.

**Trust (the moat, per GUARDRAILS):** the no-fear positioning is the entire
differentiator in a market full of scare-based astrology. Say it out loud in
content: "Tara ഒരിക്കലും ഭയപ്പെടുത്തില്ല." Myth-buster videos, transparent
"AI ആണ്" disclosure, and the crisis-safety behavior are marketing assets, not
just compliance.

---

## Build order

```
Phase 1 (now, ~1 week of sessions)
  ├── B: /content/generate kinds + admin Generate panel + mark-published
  ├── C: create YouTube channel + Insta handle; start manual daily posting
  │      (pipeline output + cards — even before TTS)
  └── D: TTS route (Sarvam primary, MOCK_TTS default) → audio download in admin

Phase 2 (~1–2 weeks)
  ├── A: Feed page — feed endpoint + UI + reactions + streaks   [migration: human approval]
  └── C: weekly astro-news video cadence begins (studio script)

Phase 3
  ├── B-stretch: ffmpeg card+audio → MP4 for daily Shorts
  ├── A: polls; comments only when moderation exists
  └── E: SEO-indexable daily/nakshatra pages

Ongoing: festival campaign calendar (next: check upcoming temple festivals
in seed data each month); collab outreach; reply to every comment.
```

**Explicit human-approval gates hit by this plan:** the Alembic migration for
community tables (Phase 2), and adding the TTS provider (Phase 1). Everything
else is normal module-scoped work inside `content/` and `community/`.
