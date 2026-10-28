import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia'
import { useAuthStore } from './auth'
import { authAPI, type User } from '@/services/api'
import { saveToken, sessionExpiry, storedToken } from '@/services/sessionStorage'
import { resumeVerifiedSession } from '@/services/sessionResume'

let pinia: Pinia
const closing = '2026-10-28T00:00:00Z' // 21h Brasília on 27 October.
const longExpiry = Date.parse('2026-11-01T00:00:00Z')
function token(sid = 'today', expiresAt = longExpiry) {
  return 'x.' + btoa(JSON.stringify({ sid, exp: expiresAt / 1000 })) + '.x'
}
function account(deadline = closing): User {
  return { id: 'Sol', nome: 'Sol', email: 'sol@eleven.com', role: 'GERENTE', ativo: true,
    must_change_password: false, sales_scope: 'own', sales_seller: 'Sol', vendedor_id: null,
    created_at: '', updated_at: '', session_expires_at: deadline }
}
beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date('2026-10-27T23:59:59Z'))
  localStorage.clear(); sessionStorage.clear()
  pinia = createPinia(); setActivePinia(pinia)
})
afterEach(() => { disposePinia(pinia); vi.useRealTimers() })

describe('Daily authenticated session deadline', () => {
  it('signs out an already open app exactly at 21h without waiting for another request', async () => {
    saveToken(token())
    vi.spyOn(authAPI, 'getCurrentUser').mockResolvedValue(account())
    const auth = useAuthStore()
    expect(await auth.ensureSession()).toBe(true)
    await vi.advanceTimersByTimeAsync(999)
    expect(auth.isAuthenticated).toBe(true)
    await vi.advanceTimersByTimeAsync(1)
    expect(auth.status).toBe('guest'); expect(auth.user).toBeNull(); expect(storedToken()).toBeNull()
    expect(localStorage.getItem('auth_session_expiry')).toBeNull()
  })

  it('uses the persisted server cutoff when resuming after mobile timers were suspended', async () => {
    saveToken(token(), false)
    const get = vi.spyOn(authAPI, 'getCurrentUser').mockResolvedValue(account())
    const auth = useAuthStore(); await auth.ensureSession()
    expect(sessionStorage.getItem('auth_session_expiry')).not.toBeNull()
    vi.setSystemTime(new Date('2026-10-28T00:00:01Z'))
    const replace = vi.fn()
    await resumeVerifiedSession(auth, { replace })
    expect(auth.status).toBe('guest'); expect(replace).toHaveBeenCalledWith('/login')
    expect(get).toHaveBeenCalledTimes(1)
  })

  it('keeps a post-21h login until the following daily cutoff', async () => {
    vi.setSystemTime(new Date('2026-10-28T00:01:00Z'))
    const nextClosing = '2026-10-29T00:00:00Z'
    saveToken(token('after-closing', Date.parse(nextClosing)))
    vi.spyOn(authAPI, 'getCurrentUser').mockResolvedValue(account(nextClosing))
    const auth = useAuthStore(); await auth.ensureSession()
    vi.setSystemTime(new Date('2026-10-28T23:59:59Z'))
    expect(await auth.ensureSession()).toBe(true)
    await vi.advanceTimersByTimeAsync(1000)
    expect(auth.status).toBe('guest')
  })

  it('does not apply an older verification deadline to the next account', async () => {
    let complete!: (user: User) => void
    const get = vi.spyOn(authAPI, 'getCurrentUser').mockReturnValueOnce(new Promise(resolve => { complete = resolve }))
    saveToken(token('old'))
    const auth = useAuthStore(), original = auth.ensureSession()
    const replacement = token('new')
    saveToken(replacement)
    get.mockResolvedValueOnce(account('2026-10-29T00:00:00Z'))
    expect(await auth.ensureSession()).toBe(true)
    complete(account(closing)); expect(await original).toBe(false)
    expect(sessionExpiry(replacement)).toBe(Date.parse('2026-10-29T00:00:00Z'))
    await vi.advanceTimersByTimeAsync(1000)
    expect(auth.isAuthenticated).toBe(true); expect(auth.token).toBe(replacement)
  })

  it('expires a server verification that arrives after its own deadline', async () => {
    let complete!: (user: User) => void
    vi.spyOn(authAPI, 'getCurrentUser').mockReturnValueOnce(new Promise(resolve => { complete = resolve }))
    saveToken(token())
    const auth = useAuthStore(), pending = auth.ensureSession()
    vi.setSystemTime(new Date('2026-10-28T00:00:01Z'))
    complete(account())
    expect(await pending).toBe(false); expect(auth.status).toBe('guest'); expect(storedToken()).toBeNull()
  })
})
