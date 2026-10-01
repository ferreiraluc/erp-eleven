import i18n from './index'
import messages from '@/locales/uiText.json'

type Locale = 'pt' | 'es' | 'en'
const catalog: Record<string, Record<Locale, string>> = messages
/** Only explicit interface literals use this catalog. Customer/product data are never translated. */
export function uiText(source: string, params?: Record<string, string | number>): string {
  const translated = catalog[source]?.[i18n.global.locale.value as Locale] ?? source
  if (!params || typeof translated !== 'string') return translated
  return translated.replace(/\{(\w+)\}/g, (placeholder, name: string) =>
    Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder)
}
export function uiLocale(): string {
  return ({ pt: 'pt-BR', es: 'es-PY', en: 'en-US' } as const)[i18n.global.locale.value as Locale] || 'pt-BR'
}

/** Display only: do not use localized strings in API numeric payloads. */
export function uiNumber(value: number | string | null | undefined, digits = 2): string {
  if (value == null || value === '') return '—'
  const numeric = Number(value)
  return Number.isFinite(numeric)
    ? numeric.toLocaleString(uiLocale(), { minimumFractionDigits: digits, maximumFractionDigits: digits })
    : '—'
}
