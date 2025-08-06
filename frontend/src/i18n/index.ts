import { createI18n } from 'vue-i18n'
import en from '@/locales/en.json'
import es from '@/locales/es.json'
import pt from '@/locales/pt.json'

const messages = {
  en,
  es,
  pt
}

// Get stored locale or default to Portuguese (BR)
const getStoredLocale = (): string => {
  const stored = localStorage.getItem('locale')
  return stored && ['en', 'es', 'pt'].includes(stored) ? stored : 'pt'
}

export const i18n = createI18n({
  legacy: false,
  locale: getStoredLocale(),
  fallbackLocale: 'en',
  messages,
  globalInjection: true
})

export const availableLocales = [
  { code: 'en', name: 'English', flag: '🇺🇸' },
  { code: 'es', name: 'Español', flag: '🇪🇸' },
  { code: 'pt', name: 'Português (BR)', flag: '🇧🇷' }
]

export const setLocale = (locale: string) => {
  if (availableLocales.some(l => l.code === locale)) {
    i18n.global.locale.value = locale as 'en' | 'es' | 'pt'
    localStorage.setItem('locale', locale)
    document.documentElement.lang = locale
  }
}

export default i18n