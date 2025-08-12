/**
 * Utilities for handling datetime with correct timezone (GMT-3 / America/Sao_Paulo)
 */

// Timezone configuration
export const TIMEZONE = 'America/Sao_Paulo' // GMT-3

/**
 * Format a date string to local timezone with Brazilian format
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
  
  return date.toLocaleDateString('pt-BR', defaultOptions)
}

/**
 * Format a datetime string to local timezone with Brazilian format
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
  
  return date.toLocaleString('pt-BR', defaultOptions)
}

/**
 * Format time only
 */
export function formatTime(dateString: string | Date): string {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  
  return date.toLocaleTimeString('pt-BR', {
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
  const now = nowInBrazil()
  const diffMs = now.getTime() - date.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSeconds < 60) {
    return 'agora mesmo'
  } else if (diffMinutes < 60) {
    return `há ${diffMinutes} minuto${diffMinutes !== 1 ? 's' : ''}`
  } else if (diffHours < 24) {
    return `há ${diffHours} hora${diffHours !== 1 ? 's' : ''}`
  } else if (diffDays < 7) {
    return `há ${diffDays} dia${diffDays !== 1 ? 's' : ''}`
  } else {
    return formatDate(date)
  }
}

/**
 * Check if a date is today in Brazil timezone
 */
export function isToday(dateString: string | Date): boolean {
  const date = typeof dateString === 'string' ? new Date(dateString) : dateString
  const today = nowInBrazil()
  
  return date.toDateString() === today.toDateString()
}