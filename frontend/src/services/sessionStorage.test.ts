import { beforeEach, describe, expect, it } from 'vitest'
import { clearSession, saveSessionExpiry, saveToken, sessionExpiry, tokenIsCurrent } from './sessionStorage'

function token(sid = 'current') { return 'x.' + btoa(JSON.stringify({ sid, exp: Date.now() / 1000 + 3600 })) + '.x' }
beforeEach(() => { localStorage.clear(); sessionStorage.clear() })

describe('Verified server deadline storage', () => {
  it('can shorten a legacy signed expiry but never extend it', () => {
    const current = token(); saveToken(current)
    const signed = sessionExpiry(current)!
    saveSessionExpiry(current, new Date(signed + 3600000).toISOString())
    expect(sessionExpiry(current)).toBe(signed)
    saveSessionExpiry(current, new Date(signed - 1800000).toISOString())
    expect(sessionExpiry(current)).toBe(signed - 1800000)
    saveSessionExpiry(current, new Date(signed).toISOString())
    expect(sessionExpiry(current)).toBe(signed - 1800000)
  })

  it('ignores malformed data and deadlines captured by a different session', () => {
    const original = token('original'), latest = token('latest'); saveToken(latest)
    const deadline = sessionExpiry(latest)
    saveSessionExpiry(original, new Date(Date.now() - 1000).toISOString())
    saveSessionExpiry(latest, 'not-a-date')
    expect(sessionExpiry(latest)).toBe(deadline)
    localStorage.setItem('auth_session_expiry', '{broken')
    expect(tokenIsCurrent(latest)).toBe(true)
    localStorage.setItem('auth_session_expiry', JSON.stringify({ token: original, expiresAt: 1 }))
    expect(tokenIsCurrent(latest)).toBe(true)
  })

  it('removes both remembered and per-tab deadline hints on session clearing', () => {
    for (const remember of [true, false]) {
      const current = token(); saveToken(current, remember)
      saveSessionExpiry(current, new Date(Date.now() - 1).toISOString())
      expect(tokenIsCurrent(current)).toBe(false)
      clearSession()
      expect(localStorage.getItem('auth_session_expiry')).toBeNull()
      expect(sessionStorage.getItem('auth_session_expiry')).toBeNull()
    }
  })
})
