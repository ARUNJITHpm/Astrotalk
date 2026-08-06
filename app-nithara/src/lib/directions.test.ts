// Getting somebody to the temple.

import { afterEach, describe, expect, it, vi } from 'vitest'

import { directionsUrl, openDirections } from './directions'

const GURUVAYUR = { lat: 10.5946, lng: 76.0402, name: 'Guruvayur' }

afterEach(() => {
  vi.restoreAllMocks()
})

describe('directionsUrl', () => {
  it('navigates by coordinates', () => {
    // A search by name finds the wrong Mahadeva temple — there are dozens.
    const url = directionsUrl(GURUVAYUR)!
    expect(url).toContain('destination=10.5946,76.0402')
    expect(url).toMatch(/^https:\/\/www\.google\.com\/maps\//)
  })

  it('carries nothing that does not work', () => {
    // An earlier version appended the name as a fragment and claimed it
    // labelled the pin. Google's Maps URLs API does not read the fragment.
    const url = directionsUrl(GURUVAYUR)!
    expect(url).not.toContain('#')
    expect(url).not.toContain('destination_place_id=')
  })

  it('refuses a temple with no coordinates', () => {
    expect(directionsUrl({ lat: NaN, lng: 76, name: 'x' })).toBeNull()
  })
})

describe('openDirections', () => {
  it('reports success even though window.open returns null', () => {
    // The bug this exists for. Passing `noopener` in the feature string makes
    // window.open return null BY SPEC, even when the tab opened perfectly — so
    // treating the return value as the success signal showed "Couldn't open
    // directions" on every single tap, immediately after Maps had opened.
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    expect(openDirections(GURUVAYUR)).toBe(true)
    expect(open).toHaveBeenCalled()
  })

  it('severs the opener when a window came back', () => {
    const fake = { opener: window } as unknown as Window
    vi.spyOn(window, 'open').mockReturnValue(fake)
    expect(openDirections(GURUVAYUR)).toBe(true)
    expect(fake.opener).toBeNull()
  })

  it('reports failure only when there is nothing to open', () => {
    const open = vi.spyOn(window, 'open').mockReturnValue(null)
    expect(openDirections({ lat: NaN, lng: NaN, name: 'x' })).toBe(false)
    expect(open).not.toHaveBeenCalled()
  })
})
