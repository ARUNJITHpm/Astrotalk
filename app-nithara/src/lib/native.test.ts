// The native capability layer.
//
// The plugins themselves cannot be exercised here — they need a device, and
// there is no android/ or ios/ platform in this repo yet. What CAN be tested is
// the part that decides whether to reach for them at all, and the parsing of a
// QR code, which is a string a stranger controls that becomes a path segment.

import { describe, expect, it, vi } from 'vitest'

import { enablePush, scanTempleQr, tokenFromQr } from './native'

vi.mock('@capacitor/core', () => ({
  Capacitor: {
    isNativePlatform: () => false,
    getPlatform: () => 'web',
  },
}))

describe('on the web', () => {
  it('reports push as unsupported instead of registering a dead token', async () => {
    // An FCM device token is not a browser push subscription. Registering one
    // from a browser would put a row in the device store that can never receive
    // anything — and the reminder run would count it as a delivery.
    expect(await enablePush()).toBe('unsupported')
  })

  it('returns nothing from a scan rather than throwing', async () => {
    // There is no camera behind the barcode plugin on the web. The onboarding
    // screen hides the button, and this is the second line of defence.
    expect(await scanTempleQr()).toBeNull()
  })
})

describe('tokenFromQr', () => {
  it('takes the slug out of a poster URL', () => {
    expect(tokenFromQr('https://nithara.app/t/guruvayur')).toBe('guruvayur')
    expect(tokenFromQr('https://nithara.app/t/guruvayur/')).toBe('guruvayur')
  })

  it('accepts a bare slug', () => {
    expect(tokenFromQr('tsr-guruvayur')).toBe('tsr-guruvayur')
    expect(tokenFromQr('  padmanabha  ')).toBe('padmanabha')
  })

  it('refuses anything that is not slug-shaped', () => {
    // This value becomes a path segment on the next request. A QR code is
    // controlled by whoever printed the poster, so it is constrained here
    // rather than handed to the server to sort out.
    expect(tokenFromQr('../../etc/passwd')).toBeNull()
    expect(tokenFromQr('a b c')).toBeNull()
    expect(tokenFromQr('')).toBeNull()
    expect(tokenFromQr('-leading-hyphen')).toBeNull()
    expect(tokenFromQr('x')).toBeNull() // too short to be a real slug
  })

  it('refuses a javascript: payload', () => {
    expect(tokenFromQr('javascript:alert(1)')).toBeNull()
  })

  it('refuses an over-long value rather than truncating it', () => {
    expect(tokenFromQr('a'.repeat(200))).toBeNull()
  })
})
