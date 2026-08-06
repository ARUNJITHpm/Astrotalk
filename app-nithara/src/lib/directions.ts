// Getting somebody to the temple.
//
// The button existed from the Part 6 port and only ever raised a toast saying
// it was opening directions. It was not.

export interface Destination {
  lat: number
  lng: number
  name: string
}

/**
 * A maps URL for the destination.
 *
 * Coordinates only. A search by name finds the wrong Mahadeva temple — there
 * are dozens in Kerala — and the directory's coordinates were verified against
 * Places, so they are the trustworthy half.
 *
 * The name is deliberately NOT in the URL. An earlier version appended it as a
 * fragment and claimed it labelled the pin; Google's Maps URLs API does not
 * read the fragment, so it did nothing. A comment promising behaviour the code
 * does not have is worse than no comment.
 *
 * Google Maps rather than a `geo:` URI: `geo:` is Android-only, and this one
 * URL is handled by the Maps app on Android and iOS and by the web on desktop.
 */
export function directionsUrl(to: Destination): string | null {
  if (!Number.isFinite(to.lat) || !Number.isFinite(to.lng)) return null
  return `https://www.google.com/maps/dir/?api=1&destination=${to.lat},${to.lng}&travelmode=driving`
}

/**
 * Open directions in whatever handles maps here.
 *
 * Returns false ONLY when there is nothing to open — a temple with no
 * coordinates. It deliberately does not treat `window.open`'s return value as
 * the success signal: passing `noopener` in the feature string makes the spec
 * return `null` even when the tab opened perfectly, so the previous version
 * reported failure on every single tap and showed "Couldn't open directions"
 * immediately after Maps had opened.
 *
 * The opener is severed afterwards instead, which buys the same protection.
 */
export function openDirections(to: Destination): boolean {
  const url = directionsUrl(to)
  if (!url) return false
  const opened = window.open(url, '_blank')
  if (opened) opened.opener = null
  return true
}
