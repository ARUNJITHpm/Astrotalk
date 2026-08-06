import i18n from 'i18next'
import { initReactI18next, useTranslation } from 'react-i18next'
import en from './en.json'
import ml from './ml.json'

// Section headers the prototype kept in its separate SEC{} object (not STR{}),
// added here so both locales resolve instead of falling back to English.
const EXTRA_EN = {
  secTempleHead: 'Your temple',
  secNearbyHead: 'Nearby temples',
  secMapHead: 'On the map',
  secPoojasToday: 'Poojas today',
  save: 'Save',
  remove: 'Remove',
  bride: "Bride's nakshatram",
  groom: "Groom's nakshatram",
  score: 'Score',
  rajjuNote: 'Rajju is unfavourable — traditionally weighed carefully',
  nallaNeram: 'Nalla neram',
  todayHead: 'Today',
  yourStar: 'Your nakshatram',
  starNotSetYet: 'Add your nakshatram to personalise this',
  saved: 'Saved',
  saveFailed: 'That didn’t save — please try again.',
  boardFull: 'Your family list is full.',
  bookFailed: 'The booking didn’t go through — please try again.',
  bookPendingNote: 'Awaiting payment. It is confirmed once payment completes.',
  // Razorpay has taken the money but our confirmation has not landed yet. Says
  // what is true without claiming the booking is confirmed, and without
  // implying anything went wrong.
  bookReceivedNote: 'Payment received. The temple confirms this shortly — your reference is below.',
  payFailed: 'The payment didn’t go through. Your booking is saved — you can pay from Poojas.',
  payUnavailable: 'Couldn’t open payment just now. Your booking is saved — you can pay from Poojas.',
  dateTbc: 'To be confirmed',
  loadFailed: 'Couldn’t load that — pull to retry.',
  // The prototype's copy named a star the user never gave ("…suits Rohini").
  nitharaBlurb:
    'Your Malayalam astrology companion. Ask about today’s panchangam, what a tithi means, or which temple suits your nakshatram.',
  chartComingSoon: 'Full jathakam is coming. For now, set your nakshatram to personalise the app.',
  setYourStar: 'Set your nakshatram',
  isStarDay: 'Your nakshatram falls today',
  msFirstTemple: 'First darshan',
  msTenTemples: 'Ten temples',
  msFirstPooja: 'First pooja',
  msWeekStreak: 'A week in a row',
  msFiveDistricts: 'Five districts',
}
const EXTRA_ML = {
  secTempleHead: 'നിങ്ങളുടെ ക്ഷേത്രം',
  secNearbyHead: 'അടുത്തുള്ള ക്ഷേത്രങ്ങൾ',
  secMapHead: 'ഭൂപടത്തിൽ',
  secPoojasToday: 'ഇന്നത്തെ പൂജകൾ',
  save: 'സേവ് ചെയ്യൂ',
  remove: 'നീക്കം ചെയ്യൂ',
  bride: 'വധുവിന്റെ നക്ഷത്രം',
  groom: 'വരന്റെ നക്ഷത്രം',
  score: 'സ്കോർ',
  rajjuNote: 'രജ്ജു പൊരുത്തമല്ല — പരമ്പരാഗതമായി ശ്രദ്ധയോടെ പരിഗണിക്കുന്നു',
  nallaNeram: 'നല്ല നേരം',
  todayHead: 'ഇന്ന്',
  yourStar: 'നിങ്ങളുടെ നക്ഷത്രം',
  starNotSetYet: 'നക്ഷത്രം ചേർത്താൽ ഇത് വ്യക്തിഗതമാക്കാം',
  saved: 'സേവ് ചെയ്തു',
  saveFailed: 'സേവ് ആയില്ല — വീണ്ടും ശ്രമിക്കൂ.',
  boardFull: 'കുടുംബ പട്ടിക നിറഞ്ഞു.',
  bookFailed: 'ബുക്കിംഗ് നടന്നില്ല — വീണ്ടും ശ്രമിക്കൂ.',
  bookPendingNote: 'പണമടയ്ക്കൽ കാത്തിരിക്കുന്നു. പൂർത്തിയായാൽ സ്ഥിരീകരിക്കും.',
  bookReceivedNote: 'പണം ലഭിച്ചു. ക്ഷേത്രം ഉടൻ സ്ഥിരീകരിക്കും — റഫറൻസ് താഴെ.',
  payFailed: 'പണമടയ്ക്കൽ നടന്നില്ല. ബുക്കിംഗ് സേവ് ചെയ്തിട്ടുണ്ട് — പൂജകൾ എന്നതിൽ നിന്ന് അടയ്ക്കാം.',
  payUnavailable: 'പേയ്‌മെന്റ് തുറക്കാനായില്ല. ബുക്കിംഗ് സേവ് ചെയ്തിട്ടുണ്ട് — പൂജകൾ എന്നതിൽ നിന്ന് അടയ്ക്കാം.',
  dateTbc: 'തീയതി സ്ഥിരീകരിക്കാനുണ്ട്',
  loadFailed: 'ലോഡ് ചെയ്യാനായില്ല — വീണ്ടും ശ്രമിക്കൂ.',
  nitharaBlurb:
    'നിങ്ങളുടെ മലയാളം ജ്യോതിഷ കൂട്ടുകാരി. ഇന്നത്തെ പഞ്ചാംഗം, തിഥിയുടെ അർത്ഥം, നിങ്ങളുടെ നക്ഷത്രത്തിന് ചേരുന്ന ക്ഷേത്രം — എന്തും ചോദിക്കാം.',
  chartComingSoon: 'പൂർണ ജാതകം ഉടൻ വരുന്നു. തൽക്കാലം നക്ഷത്രം ചേർത്ത് ആപ്പ് വ്യക്തിഗതമാക്കൂ.',
  setYourStar: 'നക്ഷത്രം ചേർക്കൂ',
  isStarDay: 'ഇന്ന് നിങ്ങളുടെ നക്ഷത്രമാണ്',
  msFirstTemple: 'ആദ്യ ദർശനം',
  msTenTemples: 'പത്ത് ക്ഷേത്രങ്ങൾ',
  msFirstPooja: 'ആദ്യ പൂജ',
  msWeekStreak: 'തുടർച്ചയായി ഒരാഴ്ച',
  msFiveDistricts: 'അഞ്ച് ജില്ലകൾ',
}

// The prototype's STR{} (334 bilingual keys) maps 1:1 to i18next resources.
// T() = current language, T2() = the OTHER language (the small secondary line
// under a heading) — exactly the prototype's T/T2 pair.

export const LANGS = ['en', 'ml'] as const
export type Lang = (typeof LANGS)[number]

const STORE_KEY = 'nithara.lang'
const initial = ((): Lang => {
  const saved = localStorage.getItem(STORE_KEY)
  return saved === 'ml' ? 'ml' : 'en'
})()

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: { ...en, ...EXTRA_EN } },
    ml: { translation: { ...ml, ...EXTRA_ML } },
  },
  lng: initial,
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
})

export function setLang(lang: Lang) {
  localStorage.setItem(STORE_KEY, lang)
  void i18n.changeLanguage(lang)
}

export function toggleLang() {
  setLang(i18n.language === 'ml' ? 'en' : 'ml')
}

/** t = current-language lookup, t2 = the other language, lang = current code. */
export function useT() {
  const { t, i18n: inst } = useTranslation()
  const lang = (inst.language === 'ml' ? 'ml' : 'en') as Lang
  const other: Lang = lang === 'en' ? 'ml' : 'en'
  const t2 = inst.getFixedT(other)
  return { t, t2, lang }
}

export default i18n
