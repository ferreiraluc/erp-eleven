import { paymentMethods as methods, paymentLabel } from '@/services/pdvPayments'
import i18n from '@/i18n'
import { uiText, uiNumber, uiLocale } from '@/i18n/uiText'
import messages from './messages.json'
const catalog: Record<string, string[]> = messages
export function tr(text: string) { const locale = i18n.global.locale.value; return catalog[text]?.[locale === 'es' ? 0 : 1] && locale !== 'pt' ? catalog[text][locale === 'es' ? 0 : 1] : uiText(text) }
export const gs = (value: string | number) => `G$ ${uiNumber(value, 2)}`
export const qty = (value: string | number) => Number(value).toLocaleString(uiLocale(), { maximumFractionDigits: 3 })
export const amount = (value: string | number) => uiNumber(value, 2)
export const saleDate = (value: string) => new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : value + '-03:00').toLocaleString(uiLocale(), { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' })
export const statusText = (status: string) => tr(({ completed: 'Concluída', partially_refunded: 'Devolução parcial', refunded: 'Estornada', cancelled: 'Cancelada' } as Record<string, string>)[status] || status)
export const operationText = (operation: string) => tr(({ edit: 'Editar venda', return: 'Devolução parcial', cancel: 'Estorno integral', delete: 'Excluir venda' } as Record<string, string>)[operation] || operation)
export const paymentMethods = methods.map(m => m.value)
export const paymentText = paymentLabel
