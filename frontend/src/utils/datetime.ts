import { uiLocale, uiText } from '@/i18n/uiText'

/** Business display is independent of the browser/device timezone. */
export const TIMEZONE = 'America/Sao_Paulo'
type DateValue = string | Date | number
const calendarDate = /^\d{4}-\d{2}-\d{2}$/

/** ERP timestamps without an offset are legacy UTC instants, not device-local time.
 * Provider wall-clock events (Correios) must explicitly use `business` instead.
 * Calendar-only dates are kept on their original day and never shifted by UTC.
 */
export function parseDateTime(value: DateValue, naive: 'utc' | 'business' = 'utc'): Date {
  if (value instanceof Date) return new Date(value.getTime())
  if (typeof value === 'number') return new Date(value)
  const text = value.trim()
  if (calendarDate.test(text)) return new Date(`${text}T12:00:00-03:00`)
  const normalized = text.replace(' ', 'T').replace(/(\.\d{3})\d+/, '$1')
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(normalized)) return new Date(NaN)
  const explicit = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)
  return new Date(explicit ? normalized : normalized + (naive === 'business' ? '-03:00' : 'Z'))
}

function display(value: DateValue, options: Intl.DateTimeFormatOptions, naive: 'utc' | 'business' = 'utc'): string {
  const date = parseDateTime(value, naive)
  return Number.isNaN(date.getTime()) ? '—' : new Intl.DateTimeFormat(uiLocale(), { ...options, timeZone: TIMEZONE }).format(date)
}

export function formatDate(value: DateValue, options: Intl.DateTimeFormatOptions = {}): string {
  return display(value, options.dateStyle ? options : { year: 'numeric', month: '2-digit', day: '2-digit', ...options })
}

export function formatDateTime(value: DateValue, options: Intl.DateTimeFormatOptions = {}): string {
  return display(value, options.dateStyle || options.timeStyle ? options : {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', ...options,
  })
}

/** A provider's timezone-less event is a Brasília wall clock, unlike ERP timestamps. */
export function formatBusinessDateTime(value: DateValue, options: Intl.DateTimeFormatOptions = {}): string {
  return display(value, options.dateStyle || options.timeStyle ? options : {
    year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', ...options,
  }, 'business')
}

export function formatTime(value: DateValue, options: Intl.DateTimeFormatOptions = {}): string {
  return display(value, { hour: '2-digit', minute: '2-digit', ...options })
}

/** A Date always represents an instant. Format it with the business helpers. */
export function nowInBrazil(): Date { return new Date() }

/** Stable YYYY-MM-DD for filters and date inputs; not the UTC/device calendar day. */
export function businessDateKey(value: DateValue = new Date()): string {
  if (typeof value === 'string' && calendarDate.test(value)) return value
  const date = parseDateTime(value)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: TIMEZONE, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date)
  const part = (name: string) => parts.find(entry => entry.type === name)?.value || ''
  return `${part('year')}-${part('month')}-${part('day')}`
}

/** Value for datetime-local controls, always interpreted as Brasília by the submitter. */
export function businessDateTimeInput(value: DateValue): string {
  const date = parseDateTime(value)
  if (Number.isNaN(date.getTime())) return ''
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: TIMEZONE, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(date)
  const part = (name: string) => parts.find(entry => entry.type === name)?.value || ''
  return `${businessDateKey(date)}T${part('hour')}:${part('minute')}`
}

export function formatRelativeTime(value: DateValue): string {
  const date = parseDateTime(value)
  if (Number.isNaN(date.getTime())) return '—'
  const seconds = Math.trunc((date.getTime() - Date.now()) / 1000)
  const relative = new Intl.RelativeTimeFormat(uiLocale(), { numeric: 'auto' })
  if (Math.abs(seconds) < 60) return uiText('agora mesmo')
  const minutes = Math.trunc(seconds / 60)
  if (Math.abs(minutes) < 60) return relative.format(minutes, 'minute')
  const hours = Math.trunc(minutes / 60)
  if (Math.abs(hours) < 24) return relative.format(hours, 'hour')
  const days = Math.trunc(hours / 24)
  if (Math.abs(days) < 7) return relative.format(days, 'day')
  return formatDate(date)
}

export function isToday(value: DateValue): boolean {
  const key = businessDateKey(value)
  return !!key && key === businessDateKey()
}
