// Razorpay Checkout, on the web.
//
// The script is loaded from Razorpay's CDN and cannot be self-hosted or
// bundled — that is a condition of their PCI scope, not an oversight. So it is
// fetched lazily, on the first checkout only: a devotee who never books never
// makes a request to a third party, and the home screen does not wait on one.
//
// What this file deliberately does NOT do is decide whether a booking is paid.
// Checkout succeeding means Razorpay took the money; our booking flips to `ok`
// when the signed webhook reaches the server (`/commerce/webhook/razorpay`).
// Those are different facts seconds apart, and on a bad day much further apart.
// A client that wrote "paid" on the strength of its own callback would be
// telling a devotee their pooja is booked on the word of a browser tab.

const SRC = 'https://checkout.razorpay.com/v1/checkout.js'

interface RazorpayInstance {
  open(): void
  on(event: string, handler: (payload: unknown) => void): void
}

interface RazorpayOptions {
  key: string
  order_id: string
  amount?: number
  currency: string
  name: string
  description?: string
  prefill?: { name?: string; contact?: string }
  theme?: { color?: string }
  handler: (response: RazorpayResponse) => void
  modal?: { ondismiss?: () => void }
}

interface RazorpayResponse {
  razorpay_payment_id: string
  razorpay_order_id: string
  razorpay_signature: string
}

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => RazorpayInstance
  }
}

let loading: Promise<void> | null = null

/**
 * How long to wait for checkout.js before giving up.
 *
 * A script tag that is never answered fires NEITHER onload nor onerror — the
 * request just hangs. That is what a captive portal does, and a very slow
 * connection, and it is the failure a test caught: without a deadline the
 * promise never settles, the Pay button stays disabled forever, and the devotee
 * is left watching a dead button with a booking they cannot see. An outright
 * network error is the easy case; this is the one that strands people.
 */
const LOAD_TIMEOUT_MS = 12_000

/** Fetch checkout.js once. Concurrent callers share the same promise. */
function loadScript(): Promise<void> {
  if (window.Razorpay) return Promise.resolve()
  if (loading) return loading
  loading = new Promise<void>((resolve, reject) => {
    const el = document.createElement('script')
    // Let the next attempt try again rather than caching the failure — this
    // fails on a flaky connection far more often than on a real outage.
    const giveUp = () => {
      loading = null
      el.remove()
      reject(new Error('checkout-unavailable'))
    }
    const timer = setTimeout(giveUp, LOAD_TIMEOUT_MS)
    el.src = SRC
    el.async = true
    el.onload = () => {
      clearTimeout(timer)
      resolve()
    }
    el.onerror = () => {
      clearTimeout(timer)
      giveUp()
    }
    document.head.appendChild(el)
  })
  return loading
}

/**
 * What came back from checkout.
 *
 * `paid` is NOT "the booking is confirmed" — see the note at the top. It means
 * Razorpay reported a successful payment and the server should now be asked.
 */
export type CheckoutOutcome =
  | { kind: 'paid'; paymentId: string }
  | { kind: 'dismissed' }
  | { kind: 'failed'; reason: string }
  | { kind: 'unavailable' }

export interface CheckoutRequest {
  keyId: string
  orderId: string
  /** Paise, from the server's own figure — never arithmetic done here. */
  amountPaise: number
  description: string
  prefill?: { name?: string; contact?: string }
}

/**
 * Open Razorpay Checkout and resolve once the user is finished with it.
 *
 * Always resolves, never rejects: every ending — paid, cancelled, card
 * declined, script blocked — is an outcome the caller has to render, and by
 * this point the booking already exists server-side with a reference number.
 * Throwing here would risk that reference being lost in a catch block, which is
 * the one thing that must not happen: the devotee would have no way to ask
 * about the booking they just made.
 */
export async function openCheckout(req: CheckoutRequest): Promise<CheckoutOutcome> {
  // On a device the web checkout still works — it renders in the Capacitor
  // WebView like any other page — so the native SDK is NOT wired here.
  //
  // That is a deliberate scope call rather than an oversight. The native SDK
  // buys a nicer sheet and UPI-intent handoff to GPay/PhonePe, which matters in
  // India; it also needs the Android and iOS platforms added, a Razorpay
  // account, and a real device to test on, none of which exist yet. Shipping an
  // untestable payment path would be worse than shipping the one that works.
  // Part 9b picks this up alongside the store builds.
  try {
    await loadScript()
  } catch {
    return { kind: 'unavailable' }
  }
  const Razorpay = window.Razorpay
  if (!Razorpay) return { kind: 'unavailable' }

  return new Promise<CheckoutOutcome>((resolve) => {
    // Razorpay can fire both `payment.failed` and `ondismiss` for one attempt.
    // First outcome wins; a Promise ignores later settles, but the guard keeps
    // the intent legible.
    let settled = false
    const finish = (outcome: CheckoutOutcome) => {
      if (settled) return
      settled = true
      resolve(outcome)
    }

    const checkout = new Razorpay({
      key: req.keyId,
      order_id: req.orderId,
      // Razorpay takes the authoritative amount from the order itself; this is
      // only what shows before the order loads. It is the server's number, so
      // the two cannot disagree.
      amount: req.amountPaise,
      currency: 'INR',
      name: 'Nithara',
      description: req.description,
      prefill: req.prefill,
      theme: { color: '#8c1c13' },
      handler: (response) => finish({ kind: 'paid', paymentId: response.razorpay_payment_id }),
      modal: { ondismiss: () => finish({ kind: 'dismissed' }) },
    })

    checkout.on('payment.failed', (payload) => {
      const description = (payload as { error?: { description?: string } })?.error?.description
      finish({ kind: 'failed', reason: description || 'payment-failed' })
    })

    checkout.open()
  })
}
