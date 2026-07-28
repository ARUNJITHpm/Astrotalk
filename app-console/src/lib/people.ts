// Pure rules for the PEOPLE section: derived age, weekly availability, and
// what makes a role grant valid.

import type { AvailabilityWindow, OperatorRow } from '../api/people'

// ---- age ----

/**
 * Age in whole years from a birth date.
 *
 * Derived, never stored. An age is right for one year and silently wrong after
 * it, so `family_members.dob` holds the date and this computes what an operator
 * reads. `today` is a parameter so a page rendering many rows uses one instant
 * and so the boundary cases are testable.
 *
 * Returns null for an absent or unparseable date rather than 0 — "we do not
 * know" and "born this year" are different facts, and a newborn is real.
 */
export function ageFrom(dob: string | null | undefined, today?: Date): number | null {
  if (!dob) return null
  const born = new Date(`${dob}T00:00:00`)
  if (Number.isNaN(born.getTime())) return null
  const now = today ?? new Date()
  let age = now.getFullYear() - born.getFullYear()
  // The birthday has not come round yet this year.
  const monthDiff = now.getMonth() - born.getMonth()
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < born.getDate())) age -= 1
  return age < 0 ? null : age
}

/** "62" for display, or an em dash when no date is on file. */
export function ageLabel(dob: string | null | undefined, today?: Date): string {
  const age = ageFrom(dob, today)
  return age === null ? '—' : String(age)
}

// ---- operators ----

export const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

/**
 * Why the server would refuse this grant, or null if it would not.
 *
 * Mirrors `_validate_grant` in admin/operators.py. Both directions matter and
 * both are easy to get wrong from a form: a temple_admin with no temple can see
 * nothing at all and looks like a broken account, and a temple on any other
 * role is a scope that nothing reads — stored, ignored, and misleading to
 * whoever audits the grants later.
 */
export function grantProblem(
  role: string,
  templeId: string | null,
  scopedRoles: readonly string[],
): string | null {
  if (!role) return 'Choose a role.'
  if (scopedRoles.includes(role) && !templeId) {
    return 'A temple admin must be given a temple, or they can see nothing.'
  }
  if (!scopedRoles.includes(role) && templeId) {
    return 'Only a temple admin is scoped to a temple.'
  }
  return null
}

/** "Owner", or "Temple admin · 2 temples", or "No roles yet". */
export function roleSummary(operator: OperatorRow): string {
  if (!operator.roles.length) return 'No roles yet'
  const names = [...new Set(operator.roles.map((r) => r.role.replace(/_/g, ' ')))]
  const temples = operator.roles.filter((r) => r.temple_id).length
  const label = names.join(', ')
  return temples ? `${label} · ${temples} temple${temples > 1 ? 's' : ''}` : label
}

/** How this person signs in. One of the two is always set; the invite requires it. */
export function operatorIdentifier(operator: OperatorRow): string {
  return operator.email || operator.phone || `#${operator.id}`
}

// ---- availability ----

/**
 * Why the weekly schedule would not work, or null.
 *
 * The server stores whatever it is handed here — `availability` is a JSON
 * column — so these are the only checks there are. Each one corresponds to a
 * schedule that silently produces no bookable slots, which is indistinguishable
 * from "nobody wants this astrologer" until somebody reads the JSON.
 */
export function availabilityProblem(windows: AvailabilityWindow[]): string | null {
  for (const w of windows) {
    if (w.weekday < 0 || w.weekday > 6) return 'Every window needs a weekday.'
    const start = minutesOf(w.start)
    const end = minutesOf(w.end)
    if (start === null || end === null) return 'Times must be HH:MM.'
    if (end <= start) return 'A window must end after it starts.'
    if (w.duration_min <= 0) return 'A consult must be at least a minute long.'
    if (w.duration_min > end - start) {
      return 'A consult is longer than the window it sits in, so no slot fits.'
    }
  }
  // Overlaps on the same day would offer the same instant twice, and
  // astro_bookings is unique on (astrologer_id, starts_at) — so the second
  // booking of that slot fails at the database rather than in the UI.
  for (let i = 0; i < windows.length; i += 1) {
    for (let j = i + 1; j < windows.length; j += 1) {
      const a = windows[i]
      const b = windows[j]
      if (a.weekday !== b.weekday) continue
      const [aStart, aEnd] = [minutesOf(a.start) ?? 0, minutesOf(a.end) ?? 0]
      const [bStart, bEnd] = [minutesOf(b.start) ?? 0, minutesOf(b.end) ?? 0]
      if (aStart < bEnd && bStart < aEnd) {
        return `Two ${WEEKDAYS[a.weekday]} windows overlap.`
      }
    }
  }
  return null
}

function minutesOf(clock: string): number | null {
  const hit = /^(\d{1,2}):(\d{2})$/.exec(clock.trim())
  if (!hit) return null
  const h = Number(hit[1])
  const m = Number(hit[2])
  if (h > 24 || m > 59 || h * 60 + m > 24 * 60) return null
  return h * 60 + m
}

/** Windows grouped by weekday, Monday first, for rendering a week. */
export function byWeekday(
  windows: AvailabilityWindow[],
): { weekday: number; windows: AvailabilityWindow[] }[] {
  return WEEKDAYS.map((_, weekday) => ({
    weekday,
    windows: windows
      .filter((w) => w.weekday === weekday)
      .sort((a, b) => a.start.localeCompare(b.start)),
  })).filter((day) => day.windows.length)
}
