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
 * Coordinates first, name second. A search by name finds the wrong
 * Mahadeva temple — there are dozens in Kerala — and the directory's
 * coordinates were verified against Places, so they are the trustworthy half.
 * The name rides along only as the label on the pin.
 *
 * Google Maps rather than a `geo:` URI: `geo:` is Android-only, and this one
 * URL is handled by the Maps app on Android and iOS and by the web on desktop.
 */
export function directionsUrl(to: Destination): string | null {
  if (!Number.isFinite(to.lat) || !Number.isFinite(to.lng)) return null
  const destination = `${to.lat},${to.lng}`
  const label = encodeURIComponent(to.name || 'Temple')
  return `https://www.google.com/maps/dir/?api=1&destination=${destination}&destination_place_id=&travelmode=driving#${label}`
}

/** Open directions in whatever handles maps here. Returns false if we could
 *  not — a temple with no coordinates, or a blocked popup. */
export function openDirections(to: Destination): boolean {
  const url = directionsUrl(to)
  if (!url) return false
  const opened = window.open(url, '_blank', 'noopener,noreferrer')
  return !!opened
}
