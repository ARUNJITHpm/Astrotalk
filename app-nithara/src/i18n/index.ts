import i18n from 'i18next'
import { initReactI18next, useTranslation } from 'react-i18next'
import en from './en.json'
import ml from './ml.json'

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
  resources: { en: { translation: en }, ml: { translation: ml } },
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
