// The CHANNELS section's pure rules.

/**
 * Mirror of identity/service.py `normalize_phone`: keep a leading `+`, drop
 * everything that is not a digit.
 *
 * This has to agree with the server exactly. The phone IS the identity key
 * across the whole product — SQL rows, Mongo history, WhatsApp sessions — so a
 * console that normalised `+91 98765 43210` differently from the backend would
 * open a *second* conversation for a person who already has one, and the
 * operator would see an empty history and conclude the devotee had never
 * written in.
 */
export function normalizePhone(raw: string): string {
  const text = raw.trim()
  const digits = text.replace(/\D/g, '')
  return text.startsWith('+') ? `+${digits}` : digits
}

/**
 * Why this number cannot be used, or null.
 *
 * The 8-digit floor is the server's (`whatsapp/router.py` `simulate`). Checking
 * it here is not duplication for its own sake — the server answers a too-short
 * number with a friendly Malayalam "❌ Invalid phone number" *as a chat reply*,
 * so the mistake would arrive looking like something the brain said.
 */
export function phoneProblem(raw: string): string | null {
  const phone = normalizePhone(raw)
  if (!phone) return 'Enter a number to send from.'
  if (phone.replace(/\D/g, '').length < 8) return 'That is too short to be a mobile number.'
  return null
}

/** A wall-clock stamp for a bubble: "09:15". */
export function clockStamp(at: Date = new Date()): string {
  const h = `${at.getHours()}`.padStart(2, '0')
  const m = `${at.getMinutes()}`.padStart(2, '0')
  return `${h}:${m}`
}

/**
 * Whether a notification run actually put messages on phones.
 *
 * `sent` counts recipients the run decided to notify. When WhatsApp is mocked
 * that number is still non-zero and nothing left the building — which is the
 * single most misreadable figure in the console, because "12 sent" is exactly
 * what an operator would quote back to a temple.
 */
export function sendReality(sent: number, whatsappLive: boolean | undefined): string {
  if (whatsappLive === undefined) {
    return `${sent} recipient${sent === 1 ? '' : 's'} — could not check whether WhatsApp is live, so treat this as unconfirmed.`
  }
  if (!whatsappLive) {
    return `${sent} recipient${sent === 1 ? '' : 's'} were selected and written to the log. WhatsApp is mocked on this installation, so no message was delivered.`
  }
  return `${sent} message${sent === 1 ? '' : 's'} sent.`
}
