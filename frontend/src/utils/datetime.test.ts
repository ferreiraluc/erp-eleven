import { afterEach, describe, expect, it, vi } from 'vitest'
import { setLocale } from '@/i18n'
import { formatDate, formatDateTime, formatRelativeTime, formatTime, isToday } from './datetime'

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
