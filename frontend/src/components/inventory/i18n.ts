import { useI18n } from 'vue-i18n'
import sharedMessages from '@/locales/uiText.json'
import messages from './messages.json'

export const inventoryMessages: Record<string, string[]> = messages
const shared: Record<string, Record<string, string>> = sharedMessages

/** Display text only: item names, stored categories and API values remain unchanged. */
export function useInventoryI18n() {
  const { locale } = useI18n({ useScope: 'global' })
  function tr(source: string, params?: Record<string, string | number>): string {
    // Older endpoints can return a validation array instead of a string detail.
    // Keep it readable without crashing the open modal on an unsuccessful save.
    if (typeof source !== 'string') {
      const detail: unknown = source
      if (Array.isArray(detail)) return detail.map(value =>
        tr(typeof value?.msg === 'string' ? value.msg : 'Erro ao salvar'),
      ).join('; ')
      return tr('Erro ao salvar')
    }
    const insufficient = /^Saldo insuficiente no local de origem: disponível (\d+), solicitado (\d+)\.$/.exec(source)
    if (insufficient) return tr('Saldo insuficiente no local de origem: disponível {available}, solicitado {requested}.', {
      available: insufficient[1], requested: insufficient[2],
    })
    const translations = inventoryMessages[source]
    const text = translations && locale.value !== 'pt'
      ? translations[locale.value === 'es' ? 0 : 1]
      : shared[source]?.[locale.value] || source
    return text.replace(/\{(\w+)\}/g, (placeholder, name) =>
      params && Object.prototype.hasOwnProperty.call(params, name) ? String(params[name]) : placeholder,
    )
  }
  function numberLocale() {
    return locale.value === 'es' ? 'es-PY' : locale.value === 'en' ? 'en-US' : 'pt-BR'
  }
  return { tr, numberLocale }
}
