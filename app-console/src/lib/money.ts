// Money, in one place.
//
// Paise are the stored unit everywhere in this product. The app's read contract
// quotes whole rupees, which is a lossy rendering — the console is where the
// authoritative figure is set, so nothing here round-trips through rupees on
// the way to the server.
//
// Three sections now price things (temple offerings, consult minutes, payments)
// and these used to live in the temples module, which stopped making sense the
// moment an astrologer's rate was read by the same function.

/**
 * A number typed into a box that also accepts "leave it empty".
 *
 * The three outcomes are genuinely different and collapsing any two of them
 * causes a real bug. Empty means INHERIT the master value, which the wire
 * carries as null. Nonsense also produces null once it has been through
 * `Number()` and `JSON.stringify` — and the server reads that null as inherit
 * for an override, or writes it straight over a NOT NULL column for a master
 * offering. So nonsense has to be caught here, before either happens.
 */
export interface Entry {
  /** null means inherit. Only meaningful when `ok`. */
  value: number | null
  ok: boolean
}

const BLANK: Entry = { value: null, ok: true }
const BAD: Entry = { value: null, ok: false }

/** Rupees as typed → paise. Fractions are allowed; ₹12.50 is 1250 paise. */
export function readPaise(text: string): Entry {
  const trimmed = text.trim()
  if (!trimmed) return BLANK
  const rupees = Number(trimmed)
  if (!Number.isFinite(rupees) || rupees < 0) return BAD
  return { value: Math.round(rupees * 100), ok: true }
}

/** A whole number of days, never negative. */
export function readDays(text: string): Entry {
  const trimmed = text.trim()
  if (!trimmed) return BLANK
  const days = Number(trimmed)
  if (!Number.isInteger(days) || days < 0) return BAD
  return { value: days, ok: true }
}

/** Paise → "₹1,234.50", trailing ".00" dropped. Display only. */
export function money(paise: number): string {
  const rupees = paise / 100
  return `₹${rupees.toLocaleString('en-IN', {
    minimumFractionDigits: Number.isInteger(rupees) ? 0 : 2,
    maximumFractionDigits: 2,
  })}`
}

/** Rupees without the symbol, for a table column that has one in its header. */
export const rupees = (paise: number): string =>
  (paise / 100).toLocaleString('en-IN', { maximumFractionDigits: 2 })
