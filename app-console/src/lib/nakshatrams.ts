// The 27 nakshatrams, English + Malayalam, index 0 = Ashwathi.
//
// A copy of app-nithara/src/lib/nakshatrams.ts, not an import: the two frontends
// are separate builds with no shared package, and a relative import across them
// would make the console's bundle depend on the consumer app's source tree.
// The list is fixed by the calendar, so it does not drift.
//
// Ordering matches the backend's `_NAKSHATRAS`, so an index round-trips to the
// API unchanged. That matters here more than in the app: the worklist is
// *grouped* by this index, and an off-by-one would file a booking under the
// wrong star day — a pooja performed on the wrong morning.

export const NAKSHATRAMS: [string, string][] = [
  ['Ashwathi', 'അശ്വതി'],
  ['Bharani', 'ഭരണി'],
  ['Karthika', 'കാർത്തിക'],
  ['Rohini', 'രോഹിണി'],
  ['Makayiram', 'മകയിരം'],
  ['Thiruvathira', 'തിരുവാതിര'],
  ['Punartham', 'പുണർതം'],
  ['Pooyam', 'പൂയം'],
  ['Ayilyam', 'ആയില്യം'],
  ['Makam', 'മകം'],
  ['Pooram', 'പൂരം'],
  ['Uthram', 'ഉത്രം'],
  ['Atham', 'അത്തം'],
  ['Chithira', 'ചിത്തിര'],
  ['Chothi', 'ചോതി'],
  ['Vishakham', 'വിശാഖം'],
  ['Anizham', 'അനിഴം'],
  ['Thrikketta', 'തൃക്കേട്ട'],
  ['Moolam', 'മൂലം'],
  ['Pooradam', 'പൂരാടം'],
  ['Uthradam', 'ഉത്രാടം'],
  ['Thiruvonam', 'തിരുവോണം'],
  ['Avittam', 'അവിട്ടം'],
  ['Chathayam', 'ചതയം'],
  ['Pooruruttathi', 'പൂരുരുട്ടാതി'],
  ['Uthrattathi', 'ഉത്രട്ടാതി'],
  ['Revathi', 'രേവതി'],
]

/**
 * "Thiruvonam · തിരുവോണം", or "No star" when the booking named none.
 *
 * Both scripts, always. The console is in English but a temple's own staff read
 * the sheet in Malayalam, and a worklist that said only "Uthradam" would be
 * the operator translating back at the moment it matters least.
 */
export function nakLabel(index: number | null | undefined): string {
  if (index == null || index < 0 || index > 26) return 'No star'
  const [en, ml] = NAKSHATRAMS[index]
  return `${en} · ${ml}`
}
