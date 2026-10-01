import { uiLocale, uiText } from '@/i18n/uiText'

/**
 * Utilities for handling datetime with correct timezone (GMT-3 / America/Sao_Paulo)
 */

// Timezone configuration
export const TIMEZONE = 'America/Sao_Paulo' // GMT-3

/**
 * Format a date string to local timezone with the selected display locale
 */
export function formatDate(dateString: string | Date, options?: Intl.DateTimeFormatOptions): string {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: TIMEZONE,
    ...options
  }
  
  return date.toLocaleDateString(uiLocale(), defaultOptions)
}

/**
 * Format a datetime string to local timezone with the selected display locale
 */
export function formatDateTime(dateString: string | Date, options?: Intl.DateTimeFormatOptions): string {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  
  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: TIMEZONE,
    ...options
  }
  
  return date.toLocaleString(uiLocale(), defaultOptions)
}

/**
 * Format time only
 */
export function formatTime(dateString: string | Date): string {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  
  return date.toLocaleTimeString(uiLocale(), {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: TIMEZONE
  })
}

/**
 * Get current date in Brazil timezone
 */
export function nowInBrazil(): Date {
  return new Date(new Date().toLocaleString("en-US", { timeZone: TIMEZONE }))
}

/**
 * Format relative time (e.g., "há 2 horas")
 */
export function formatRelativeTime(dateString: string | Date): string {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
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

/**
 * Check if a date is today in Brazil timezone
 */
export function isToday(dateString: string | Date): boolean {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  const calendarDate = new Intl.DateTimeFormat('en-CA', { timeZone: TIMEZONE })
  return calendarDate.format(date) === calendarDate.format(new Date())
}