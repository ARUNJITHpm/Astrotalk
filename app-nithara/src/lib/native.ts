// Native capabilities, and what to do when there aren't any.
//
// One codebase serves the web PWA and the Capacitor wrapper, so every function
// here has to answer twice: once on a phone with the plugin, once in a browser
// without it. The rule throughout is that the web answer is a real answer — a
// clear "no" the caller can render — and never a thrown error or a promise that
// never settles.
//
// The plugins are imported dynamically for the same reason. Push and barcode
// scanning have no web implementation at all; a static import would pull their
// code into the browser bundle to sit there and throw if anything touched it.

import { Capacitor } from '@capacitor/core'

import { apiPost } from '../api/client'

/** Running inside the Capacitor shell rather than a browser tab. */
export const isNative = (): boolean => Capacitor.isNativePlatform()

/** 'android' | 'ios' | 'web' — the value /notifications/devices records. */
export const platformName = (): string => Capacitor.getPlatform()

// ---- push notifications ----

/**
 * Ask for permission, register with FCM, and hand the token to the server.
 *
 * This is the missing half of a feature that has existed for weeks: Part 4
 * built the device-token store and the T-3 nakshatram reminder run, and nothing
 * ever registered a token — so the whole retention loop has never delivered a
 * single notification to a real phone.
 *
 * Returns what happened rather than throwing, because every outcome is one the
 * caller has to live with: declining permission is a normal choice, and a web
 * build simply cannot do this.
 */
export type PushResult = 'registered' | 'denied' | 'unsupported' | 'failed'

export async function enablePush(onOpen?: (data: Record<string, unknown>) => void): Promise<PushResult> {
  // Web push would need a service-worker subscription and a VAPID key, which is
  // a different mechanism from FCM device tokens. Saying "unsupported" is
  // honest; pretending otherwise would register a token that never receives.
  if (!isNative()) return 'unsupported'

  try {
    const { PushNotifications } = await import('@capacitor/push-notifications')

    let status = await PushNotifications.checkPermissions()
    if (status.receive === 'prompt' || status.receive === 'prompt-with-rationale') {
      status = await PushNotifications.requestPermissions()
    }
    if (status.receive !== 'granted') return 'denied'

    const token = await new Promise<string | null>((resolve) => {
      // Registration answers through one of two events and neither is
      // guaranteed, so this must not be able to hang. A phone with no Play
      // Services simply never replies.
      const timer = setTimeout(() => resolve(null), 15_000)
      PushNotifications.addListener('registration', (t) => {
        clearTimeout(timer)
        resolve(t.value)
      })
      PushNotifications.addListener('registrationError', () => {
        clearTimeout(timer)
        resolve(null)
      })
      void PushNotifications.register()
    })
    if (!token) return 'failed'

    // A tap on a reminder should land on the thing it is about.
    if (onOpen) {
      await PushNotifications.addListener('pushNotificationActionPerformed', (action) => {
        onOpen(action.notification.data ?? {})
      })
    }

    await apiPost('/notifications/devices', { token, platform: platformName() })
    return 'registered'
  } catch {
    return 'failed'
  }
}

// ---- location ----

export interface Coords {
  lat: number
  lng: number
}

/**
 * Where the phone is, or null.
 *
 * Null covers refusal, a timeout and an unavailable sensor alike, because the
 * caller does the same thing for all three: fall back to the curated "nearby"
 * list instead of an empty screen. A location this app cannot get is not an
 * error state, it is Tuesday.
 */
export async function currentPosition(): Promise<Coords | null> {
  try {
    const { Geolocation } = await import('@capacitor/geolocation')
    const permission = await Geolocation.checkPermissions()
    if (permission.location === 'denied') return null
    const position = await Geolocation.getCurrentPosition({
      enableHighAccuracy: false, // a temple list does not need GPS-grade fixes
      timeout: 8000,
      maximumAge: 5 * 60 * 1000, // a five-minute-old fix is fine for this
    })
    return { lat: position.coords.latitude, lng: position.coords.longitude }
  } catch {
    return null
  }
}

// ---- QR scanning ----

/**
 * Scan a temple poster and return the token it carries, or null.
 *
 * Native only — there is no camera API behind this plugin on the web, and the
 * onboarding screen offers the scan route only when this can actually run.
 * Offering a scan button in a browser that opens nothing is the dead end the
 * build plan warned about.
 */
export async function scanTempleQr(): Promise<string | null> {
  if (!isNative()) return null
  try {
    const { BarcodeScanner } = await import('@capacitor-mlkit/barcode-scanning')
    const granted = await BarcodeScanner.requestPermissions()
    if (granted.camera !== 'granted' && granted.camera !== 'limited') return null
    const { barcodes } = await BarcodeScanner.scan()
    const raw = barcodes[0]?.rawValue
    return raw ? tokenFromQr(raw) : null
  } catch {
    return null
  }
}

/**
 * The temple token inside a scanned value.
 *
 * Posters carry a full URL (`https://…/t/guruvayur`), but a QR code is a string
 * a stranger controls and this one is about to become a path segment. So the
 * token is extracted and then constrained to the shape a slug actually has —
 * anything else is refused rather than passed along to the server to sort out.
 */
export function tokenFromQr(raw: string): string | null {
  let candidate = raw.trim()
  try {
    const url = new URL(candidate)
    const segments = url.pathname.split('/').filter(Boolean)
    candidate = segments[segments.length - 1] ?? ''
  } catch {
    // Not a URL — treat the whole value as the token.
  }
  return /^[a-z0-9][a-z0-9-]{1,60}$/i.test(candidate) ? candidate : null
}
