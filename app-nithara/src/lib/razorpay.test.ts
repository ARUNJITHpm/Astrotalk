// The checkout loader.
//
// Tested apart from the booking screen because the case that matters is a
// timing one, and driving it through React means fighting fake timers against
// react-query's real promises to prove something about a `setTimeout`.

import { afterEach, describe, expect, it, vi } from 'vitest'

import { openCheckout } from './razorpay'

const REQ = {
  keyId: 'rzp_test_key',
  orderId: 'order_1',
  amountPaise: 11500,
  description: 'Pushpanjali · Guruvayur',
}

afterEach(() => {
  vi.useRealTimers()
  delete window.Razorpay
  document.querySelectorAll('script[src*="razorpay"]').forEach((el) => el.remove())
})

describe('loading checkout.js', () => {
  it('gives up rather than hanging when the script is never answered', async () => {
    // The failure this test exists for. A script tag that goes unanswered fires
    // NEITHER onload nor onerror — a captive portal, a stalled connection. With
    // no deadline the promise never settles: the caller's Pay button stays
    // disabled forever and the devotee is left with a booking they cannot see.
    // jsdom does not fetch external scripts, which reproduces it exactly.
    vi.useFakeTimers()
    const outcome = openCheckout(REQ)
    await vi.advanceTimersByTimeAsync(13_000)
    expect(await outcome).toEqual({ kind: 'unavailable' })
  })

  it('reports unavailable rather than throwing', async () => {
    // openCheckout must never reject. By the time it runs, the booking exists
    // server-side with a reference number, and a throw risks that reference
    // being swallowed by a catch — leaving the devotee no way to ask about it.
    vi.useFakeTimers()
    const outcome = openCheckout(REQ)
    await vi.advanceTimersByTimeAsync(13_000)
    await expect(outcome).resolves.toBeTruthy()
  })

  it('does not cache a failure — the next attempt tries again', async () => {
    vi.useFakeTimers()
    const first = openCheckout(REQ)
    await vi.advanceTimersByTimeAsync(13_000)
    expect(await first).toEqual({ kind: 'unavailable' })

    // A flaky connection is far more common than a real outage, so a second
    // press must fetch again rather than reuse the rejection.
    const second = openCheckout(REQ)
    await vi.advanceTimersByTimeAsync(13_000)
    expect(await second).toEqual({ kind: 'unavailable' })
    // Two attempts means two script tags were appended and cleaned up.
    expect(document.querySelectorAll('script[src*="razorpay"]').length).toBe(0)
  })
})

describe('the options handed to Razorpay', () => {
  it('passes the order id and the caller’s paise figure', async () => {
    let seen: Record<string, unknown> = {}
    window.Razorpay = class {
      constructor(opts: Record<string, unknown>) {
        seen = opts
      }
      on() {}
      open() {
        ;(seen.handler as (r: unknown) => void)({ razorpay_payment_id: 'pay_1' })
      }
    } as never

    const outcome = await openCheckout(REQ)
    expect(outcome).toEqual({ kind: 'paid', paymentId: 'pay_1' })
    expect(seen.order_id).toBe('order_1')
    expect(seen.amount).toBe(11500)
    expect(seen.currency).toBe('INR')
  })

  it('settles once, even when Razorpay reports failure and dismissal', async () => {
    // Razorpay fires `payment.failed` and then `ondismiss` for a single
    // declined attempt. The first outcome is the true one.
    let opts: Record<string, unknown> = {}
    let fail: ((p: unknown) => void) | null = null
    window.Razorpay = class {
      constructor(o: Record<string, unknown>) {
        opts = o
      }
      on(event: string, handler: (p: unknown) => void) {
        if (event === 'payment.failed') fail = handler
      }
      open() {
        fail?.({ error: { description: 'Card declined' } })
        ;(opts.modal as { ondismiss: () => void }).ondismiss()
      }
    } as never

    expect(await openCheckout(REQ)).toEqual({ kind: 'failed', reason: 'Card declined' })
  })
})
