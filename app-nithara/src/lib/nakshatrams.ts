// The 27 nakshatrams, English + Malayalam, in canonical order (index 0 = Ashwathi).
// Matches the backend's NAKSHATRAS ordering, so an index round-trips to the API.
export const NAKSHATRAMS: Array<[string, string]> = [
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

export function nakName(index: number | null, lang: string): string {
  if (index == null || index < 0 || index > 26) return ''
  return lang === 'ml' ? NAKSHATRAMS[index][1] : NAKSHATRAMS[index][0]
}

// Relations offered when adding a family member (labels come from i18n r* keys).
export const RELATIONS = ['rMother', 'rFather', 'rSpouse', 'rSon', 'rDaughter', 'rBrother', 'rSister', 'rOther']
