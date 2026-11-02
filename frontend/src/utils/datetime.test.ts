import { afterEach, describe, expect, it, vi } from 'vitest'
import { setLocale } from '@/i18n'
import { formatDate, formatDateTime, formatRelativeTime, formatTime, isToday, businessDateKey, formatBusinessDateTime, parseDateTime, businessDateTimeInput } from './datetime'

afterEach(()=>{vi.useRealTimers();setLocale('pt')})
describe('localized dates retain the business timezone',()=>{
  it('changes display language without moving a Brasília timestamp to another day',()=>{
    const instant='2026-10-01T02:30:00Z'
    for(const [locale,intl] of [['pt','pt-BR'],['es','es-PY'],['en','en-US']]){
      setLocale(locale)
      expect(formatDate(instant)).toBe(new Date(instant).toLocaleDateString(intl,{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'America/Sao_Paulo'}))
      expect(formatDateTime(instant)).toContain('2026')
      expect(formatTime(instant)).toBe(new Date(instant).toLocaleTimeString(intl,{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}))
    }
  })
  it('computes elapsed time from instants and translates future and past values',()=>{
    vi.useFakeTimers();vi.setSystemTime(new Date('2026-09-30T18:00:00Z'))
    setLocale('en');expect(formatRelativeTime('2026-09-30T16:00:00Z')).toBe('2 hours ago')
    expect(formatRelativeTime('2026-09-30T20:00:00Z')).toBe('in 2 hours')
    setLocale('pt');expect(formatRelativeTime('2026-09-30T16:00:00Z')).toBe('há 2 horas')
    setLocale('es');expect(formatRelativeTime('2026-09-30T16:00:00Z')).toBe('hace 2 horas')
  })
  it('checks today in Brasília around the UTC midnight boundary',()=>{
    vi.useFakeTimers();vi.setSystemTime(new Date('2026-10-01T02:30:00Z'))
    expect(isToday('2026-09-30T20:00:00Z')).toBe(true)
    expect(isToday('2026-10-01T04:00:00Z')).toBe(false)
  })
})

it('treats legacy naive ERP timestamps as UTC, independently of the device timezone', () => {
  expect(formatDateTime('2026-11-02T18:15:00.123456')).toBe(formatDateTime('2026-11-02T18:15:00.123Z'))
  expect(formatTime('2026-11-02T18:15:00')).toBe('15:15')
  expect(formatTime('2026-11-02T15:15:00-03:00')).toBe('15:15')
  expect(formatTime(Date.parse('2026-11-02T18:15:00Z'))).toBe('15:15')
})

it('preserves calendar-only dates and keeps provider wall clocks explicit', () => {
  expect(formatDate('2026-11-02')).toBe('02/11/2026')
  expect(businessDateKey('2026-11-02')).toBe('2026-11-02')
  expect(businessDateKey('2026-11-02T02:59:59Z')).toBe('2026-11-01')
  expect(formatBusinessDateTime('2026-11-02 15:15:00.000000')).toContain('15:15')
  expect(parseDateTime('2026-11-02 15:15:00', 'business').toISOString()).toBe('2026-11-02T18:15:00.000Z')
  expect(formatDateTime('2026-11-02T18:15:00Z', { dateStyle: 'short', timeStyle: 'short' })).toContain('15:15')
})

it('handles invalid values without breaking cards and computes naive elapsed time from UTC', () => {
  expect(formatDateTime('not a date')).toBe('—')
  expect(formatDateTime(new Date(NaN))).toBe('—')
  expect(businessDateKey('not a date')).toBe('')
  vi.useFakeTimers(); vi.setSystemTime(new Date('2026-11-02T18:00:00Z'))
  expect(formatRelativeTime('2026-11-02T16:00:00')).toBe('há 2 horas')
})

it('keeps notification schedule controls in Brasília across device timezones', () => {
  expect(businessDateTimeInput('2026-11-02T03:15:00Z')).toBe('2026-11-02T00:15')
  expect(parseDateTime('2026-11-02T00:15', 'business').toISOString()).toBe('2026-11-02T03:15:00.000Z')
})
