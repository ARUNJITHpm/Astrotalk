# Nithara app (frontend)

React + Vite + TypeScript PWA, wrapped by Capacitor for Play Store / App Store.
One codebase → web + Android + iOS. Ported from `../nithara-v11.html`.

## Run

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # → dist/ (typechecked; PWA service worker generated)
npm test           # Vitest
npm run typecheck  # tsc --noEmit
```

Set the backend URL in `.env` (see `.env.example`):

```
VITE_API_BASE=http://localhost:8000
```

## Structure

- `src/styles/globals.css` — the prototype's stylesheet, extracted verbatim (keep
  the CSS variables; the Malayalam type system is gated on `.phone[data-lang="ml"]`).
- `src/components/sprite.svg` — the prototype's SVG symbol sheet; injected once by
  `IconSprite`, referenced via `<Icon name="i-…" />`.
- `src/i18n/{en,ml}.json` — the prototype's `STR{}` (334 bilingual keys). `useT()`
  gives `t` (current language) and `t2` (the other language, for the bilingual
  secondary line), mirroring the prototype's `T`/`T2`.
- `src/api/` — typed fetch `client.ts` (bearer token from `lib/session.ts`) + `types.ts`.
- `src/screens/` — one per tab; `src/App.tsx` routes them inside `PhoneFrame` + `TabBar`.

## Deferred (tracked from the Part 5 review)

- **Self-host fonts + Leaflet** (Part 6): `index.html` still pulls Fraunces/Inter/
  Anek Malayalam from the Google Fonts CDN — a service worker / offline / CSP problem
  for the PWA and the native WebView. Bundle them before shipping screens.
- **PWA icons** (later): `vite.config.ts` manifest ships `icons: []` — add real icons
  for installability.
- **Overlay/scrim/inert sheet system** (Parts 6–8): the prototype's `syncOverlay()` and
  `.phone[data-overlay]` behaviour isn't ported yet; every sheet/modal depends on it.
- **Login / anon→account linking**: the app is anonymous-only today (`lib/auth.ts` mints
  a device session). Logging in later must *link* the anon account, or its bookings and
  family board are orphaned. No login route exists yet — decide before shipping accounts.
- **Astrologer directory is hidden** (`screens/Astro.tsx`): the backend seed is explicitly
  dummy (names are slugs like `thrissur-astro-1`, ratings/experience are computed), so
  rendering it would be fabricated social proof. Restore the block when real, consented
  practitioners exist.
- **Chart creation**: the chat brain only *reads* a chart — there is no conversational
  chart-setup path server-side. The profile says so plainly rather than offering a CTA
  that cannot deliver. Wiring real chart creation is a backend task.
- **Chat is per-screen**: `Astro` and `Profile` each mount their own `ChatSheet`, so
  switching tabs starts a new conversation. `GET /chat/history/{user_id}` exists and is
  not read yet — lift chat state and hydrate from history to make it continuous.
