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
  dateTbc: 'To be confirmed',
  loadFailed: 'Couldn’t load that — pull to retry.',
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
  dateTbc: 'തീയതി സ്ഥിരീകരിക്കാനുണ്ട്',
  loadFailed: 'ലോഡ് ചെയ്യാനായില്ല — വീണ്ടും ശ്രമിക്കൂ.',
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
