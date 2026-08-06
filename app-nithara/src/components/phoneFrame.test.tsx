// The offline strip.
//
// The service worker precaches the shell, so the app OPENS with no network —
// and then every screen sits on a failed query with nothing to explain it. This
// is the difference between "disconnected" and "broken", and the app said
// neither until now.

import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PhoneFrame } from './PhoneFrame'

const online = (value: boolean) =>
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(value)

afterEach(() => {
  vi.restoreAllMocks()
})

describe('the offline strip', () => {
  it('appears when the device says there is no network', () => {
    online(false)
    render(
      <PhoneFrame>
        <p>content</p>
      </PhoneFrame>,
    )
    expect(screen.getByRole('status')).toHaveTextContent(/offline/i)
  })

  it('stays out of the way when connected', () => {
    online(true)
    render(
      <PhoneFrame>
        <p>content</p>
      </PhoneFrame>,
    )
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('never hides the screen behind it', () => {
    // A strip above the content, not an overlay across it. Being offline does
    // not stop somebody reading the temple timings they already have.
    online(false)
    render(
      <PhoneFrame>
        <p>content</p>
      </PhoneFrame>,
    )
    expect(screen.getByText('content')).toBeVisible()
  })
})
