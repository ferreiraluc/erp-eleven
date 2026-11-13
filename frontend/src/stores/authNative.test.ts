import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
const secure = vi.hoisted(() => ({ get: vi.fn(), set: vi.fn(), remove: vi.fn(), getVolatileSession: vi.fn(), setVolatileSession: vi.fn(), clearVolatileSession: vi.fn() }))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => true }, registerPlugin: () => secure }))
vi.mock('@/services/catalogIndex', () => ({ clearCatalogIndex: vi.fn() }))
vi.mock('@/services/notificationPush', () => ({ clearNotificationDevice: vi.fn() }))
import { useAuthStore } from './auth'
import { authAPI, type User } from '@/services/api'
import { clearSession, flushSessionStorage, initializeNativeSession, saveToken, saveSessionExpiry, sessionExpiry, sessionIsRemembered, storedToken } from '@/services/sessionStorage'
const sessionToken = (sid: string) => 'x.' + btoa(JSON.stringify({ sid, exp: Date.now() / 1000 + 3600 })) + '.x'
const account = { id:'qa',nome:'Consulta',email:'qa@example.test',role:'VENDEDOR',access_profile:'reseller',ativo:true,must_change_password:false,sales_scope:'own',created_at:'',updated_at:'' } as User
const credentials = { email: 'qa@example.test', senha: 'isolated-password' }
const deferred = () => { let resolve!: () => void; const promise = new Promise<void>(yes => { resolve = yes }); return { promise, resolve } }
beforeEach(async () => {
  vi.restoreAllMocks(); secure.get.mockReset().mockResolvedValue({value:null}); secure.set.mockReset().mockResolvedValue(undefined); secure.remove.mockReset().mockResolvedValue(undefined)
  secure.getVolatileSession.mockReset().mockResolvedValue({value:null}); secure.setVolatileSession.mockReset().mockResolvedValue(undefined); secure.clearVolatileSession.mockReset().mockResolvedValue(undefined)
  localStorage.clear(); sessionStorage.clear(); setActivePinia(createPinia())
  await initializeNativeSession(); clearSession(); await flushSessionStorage()
})
describe('Native authentication integration', () => {
  it('verifies the server role only after the credential is durably stored', async () => {
    const pending = deferred(), token = sessionToken('first')
    secure.set.mockImplementationOnce(() => pending.promise)
    vi.spyOn(authAPI,'login').mockResolvedValue({access_token:token,token_type:'bearer',expires_in:3600})
    const verify = vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(account)
    const auth = useAuthStore(), login = auth.login(credentials)
    await vi.waitFor(() => expect(secure.set).toHaveBeenCalled())
    expect(verify).not.toHaveBeenCalled(); expect(auth.isAuthenticated).toBe(false)
    pending.resolve(); await login
    expect(auth.isReseller).toBe(true); expect(auth.user?.id).toBe('qa')
    expect(localStorage.getItem('auth_token')).toBeNull(); expect(sessionStorage.getItem('auth_token')).toBeNull()
  })
  it('does not authenticate or fall back to browser storage when the secure write fails', async () => {
    secure.set.mockRejectedValueOnce(new Error('Keystore unavailable'))
    vi.spyOn(authAPI,'login').mockResolvedValue({access_token:sessionToken('failed'),token_type:'bearer',expires_in:3600})
    const verify = vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(account), auth = useAuthStore()
    await expect(auth.login(credentials)).rejects.toThrow('native_secure_session_unavailable')
    expect(verify).not.toHaveBeenCalled(); expect(auth.isAuthenticated).toBe(false); expect(storedToken()).toBeNull()
    expect(auth.error).toContain('armazenamento seguro'); expect(localStorage.getItem('auth_token')).toBeNull()
  })
  it('preserves remember choice through password rotation and never extends signed or verified expiry', async () => {
    const original = sessionToken('old'), changed = sessionToken('changed')
    saveToken(original, true); await flushSessionStorage()
    const signed = sessionExpiry(original)!
    saveSessionExpiry(original,new Date(signed - 1000).toISOString()); await flushSessionStorage()
    saveSessionExpiry(original,new Date(signed + 10000).toISOString()); await flushSessionStorage()
    expect(sessionExpiry(original)).toBe(signed - 1000)
    vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(account)
    vi.spyOn(authAPI,'changePassword').mockResolvedValue({access_token:changed,token_type:'bearer',expires_in:3600})
    const auth=useAuthStore(); await auth.ensureSession(); await auth.changePassword('old-password','new-password')
    expect(storedToken()).toBe(changed); expect(sessionIsRemembered(changed)).toBe(true)
    expect(localStorage.getItem('auth_session_expiry')).toBeNull()
  })
  it('keeps an unchecked remember choice in native process memory without disk credentials', async () => {
    const token = sessionToken('temporary')
    vi.spyOn(authAPI,'login').mockResolvedValue({access_token:token,token_type:'bearer',expires_in:3600})
    vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(account)
    const auth = useAuthStore(); await auth.login(credentials, false)
    expect(auth.isAuthenticated).toBe(true); expect(sessionIsRemembered(token)).toBe(false)
    expect(secure.set).not.toHaveBeenCalled()
    expect(secure.setVolatileSession).toHaveBeenCalledWith({value:expect.stringContaining(token)})
    expect(localStorage.getItem('auth_token')).toBeNull(); expect(sessionStorage.getItem('auth_token')).toBeNull()
  })

  it('revokes the captured server session even if native logout cleanup fails', async () => {
    const token = sessionToken('logout'); saveToken(token,true); await flushSessionStorage()
    vi.spyOn(authAPI,'getCurrentUser').mockResolvedValue(account)
    const revoke=vi.spyOn(authAPI,'logout').mockResolvedValue(undefined), auth=useAuthStore(); await auth.ensureSession()
    secure.remove.mockRejectedValueOnce(new Error('disk failed'))
    await expect(auth.logout()).rejects.toThrow('native_secure_session_unavailable')
    expect(revoke).toHaveBeenCalledWith(token); expect(auth.user).toBeNull(); expect(storedToken()).toBeNull()
  })
})
