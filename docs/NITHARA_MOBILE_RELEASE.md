# Nithara — mobile release

How the Capacitor build is produced, and what is still missing before one can
reach a store. Written at the end of Part 9a (native capabilities); Part 9b is
the signed builds themselves, which need accounts nobody has yet created.

---

## What is built, and what is not

| | state |
|---|---|
| Push notifications (FCM) | **built**, unverified on a device |
| Geolocation | **built**, works on web and native |
| QR poster scanning | **built**, native only |
| Razorpay native SDK | **not built** — see below |
| `android/` platform | **not added** |
| `ios/` platform | **not added** |
| Signed AAB / IPA | **not produced** |

Everything marked "built" typechecks, has unit tests around the parts that can
be tested without a device, and degrades honestly on the web. **None of it has
run on a phone.** That is the single most important sentence in this document:
the plugin code paths are unexercised, and the first person to run
`npx cap sync` should expect to find something.

### Razorpay stays on web checkout, on purpose

The web checkout renders inside the Capacitor WebView like any other page, so
payments work on a device today. The native SDK would buy a nicer sheet and
UPI-intent handoff to GPay/PhonePe — which matters in India — but it needs the
platforms added, a Razorpay account and a real device to test against. Shipping
an untestable payment path would be worse than shipping the one that works.

---

## Adding the platforms

Neither `android/` nor `ios/` exists in the repo. Both are generated, and both
are gitignored via `.dockerignore` for the image build:

```bash
cd app-nithara
npm ci
npm run build            # dist/ must exist before cap add
npx cap add android
npx cap add ios          # macOS only
npx cap sync
```

`capacitor.config.ts` already carries the app id and name. After `cap add`,
three things need doing by hand:

1. **`google-services.json`** into `android/app/` — from the Firebase console,
   for the project whose FCM credentials the backend uses. Push registration
   silently returns `failed` without it.
2. **Camera and location permissions** — the plugins add most of the manifest
   entries, but iOS needs usage strings in `Info.plist`
   (`NSCameraUsageDescription`, `NSLocationWhenInUseUsageDescription`). Write
   them in the first person and say what they are for; App Review rejects vague
   ones, and so should we.
3. **`VITE_API_BASE`** — the web build leaves it empty because the API and the
   app share an origin. A native build does **not**: it loads from
   `capacitor://` or `https://localhost`, so every relative request would go
   nowhere. Set it to the deployed origin before `npm run build`.

That third one is the trap. The app will build, install, launch, and fail every
request with no obvious cause.

---

## What the owner has to supply

None of this is code, and none of it can be done from here.

- **Google Play Console account** (one-off fee) and an upload keystore. Keep the
  keystore and its passwords somewhere that survives a laptop — losing it means
  never updating the app under the same listing again.
- **Apple Developer Program membership** (annual), plus a Mac to build on.
- **Firebase project** for FCM, matching whatever the backend's push credentials
  point at.
- **Razorpay account** in live mode, for Part 9b's native SDK and for payments
  generally — `mock_razorpay` is still true, and going live is a human-approval
  gate under `docs/AGENTS.md`.
- **Store listing material**: icon, screenshots, description in English and
  Malayalam, a privacy policy URL.

The privacy policy is not a formality here. The app collects date, time and
place of birth, and both stores require a data-safety declaration that names it.
GUARDRAILS §4 already governs how that data is handled internally; the listing
has to say the same thing out loud.

---

## Building

```bash
cd app-nithara
VITE_API_BASE=https://talk-to-nitara.hf.space npm run build
npx cap sync

# Android
npx cap open android      # then Build → Generate Signed Bundle

# iOS (macOS)
npx cap open ios          # then Product → Archive
```

---

## Before submitting

- **Offline.** The service worker precaches the shell; confirm the app opens
  with the network off and says something useful rather than showing a blank
  screen. This has not been checked.
- **Push end to end.** Install, accept the prompt, confirm a row appears via
  `POST /notifications/devices`, then fire
  `POST /notifications/run-nakshatram-reminders` and watch for the notification.
  The reminder backend has existed since Part 4 and **has never delivered a
  single notification to a real phone**, because nothing registered a token
  until Part 9a. Assume it is broken until seen working.
- **A denied permission.** Refuse location and camera and confirm the app still
  works: the temple list falls back to Thrissur, and the scan button reports
  that nothing was scanned.
- **The birth-details form** on a real keyboard — date and time inputs are the
  controls most likely to behave differently in a WebView.
