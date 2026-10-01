import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'
import { useAuthStore } from './auth'
import { authAPI, type LoginResponse, type User } from '@/services/api'
import { saveToken, storedToken } from '@/services/sessionStorage'

function token(id: string) { return 'x.' + btoa(JSON.stringify({ sid: id, exp: Date.now() / 1000 + 3600 })) + '.x' }
function account(name: string): User { return { id: name, nome: name, email: name.toLowerCase() + '@eleven.com', role: name === 'Lucas' ? 'ADMIN' : 'GERENTE', ativo: true, must_change_password: false, sales_scope: name === 'Lucas' ? 'all' : 'own', sales_seller: name, vendedor_id: name, created_at: '', updated_at: '' } }
function session(name: string): LoginResponse { return { access_token: token(name), token_type: 'bearer', expires_in: 3600 } }
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
// Tokens include an expiry instant. Compare the sid for mocks independent of elapsed milliseconds.
function verifyBySid() { return vi.spyOn(authAPI, 'getCurrentUser').mockImplementation(async () => account(JSON.parse(atob(storedToken()!.split('.')[1])).sid)) }
const credentials = (name: string) => ({ email: `${name}@eleven.com`, senha: 'isolated-test-password' })
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); setActivePinia(createPinia()) })

describe('Authentication operation races', () => {
  it('does not restore a login whose response arrives after local expiry', async () => {
    const pending = deferred<LoginResponse>(); vi.spyOn(authAPI, 'login').mockReturnValueOnce(pending.promise); verifyBySid()
    const auth = useAuthStore(), login = auth.login(credentials('Lucas')).catch(() => undefined)
    auth.expire(); pending.resolve(session('Lucas')); await login
    expect(storedToken()).toBeNull(); expect(auth.user).toBeNull(); expect(auth.status).toBe('guest')
  })

  it('keeps the latest identity when an earlier login succeeds afterwards', async () => {
    const earlier = deferred<LoginResponse>(); vi.spyOn(authAPI, 'login').mockReturnValueOnce(earlier.promise).mockResolvedValueOnce(session('Sol')); verifyBySid()
    const auth = useAuthStore(), first = auth.login(credentials('Lucas')).catch(() => undefined)
    await auth.login(credentials('Sol')); const currentToken = storedToken()
    earlier.resolve(session('Lucas')); await first
    expect(storedToken()).toBe(currentToken); expect(auth.user?.id).toBe('Sol'); expect(auth.isOwner).toBe(false)
  })

  it('does not let an old login failure change the newer pending spinner or error', async () => {
    const earlier = deferred<LoginResponse>(), latest = deferred<LoginResponse>()
    vi.spyOn(authAPI, 'login').mockReturnValueOnce(earlier.promise).mockReturnValueOnce(latest.promise); verifyBySid()
    const auth = useAuthStore(), first = auth.login(credentials('Lucas')).catch(() => undefined), second = auth.login(credentials('Sol')).catch(() => undefined)
    earlier.reject(new AxiosError('Old request failed')); await first
    const loadingWhileLatestIsPending = auth.isLoading, errorWhileLatestIsPending = auth.error
    latest.resolve(session('Sol')); await second
    expect(loadingWhileLatestIsPending).toBe(true); expect(errorWhileLatestIsPending).toBeNull(); expect(auth.user?.id).toBe('Sol')
  })

  it('does not restore an older account after its password-change response arrives', async () => {
    const changed = deferred<LoginResponse>(); vi.spyOn(authAPI, 'changePassword').mockReturnValueOnce(changed.promise); verifyBySid()
    saveToken(token('Lucas')); const auth = useAuthStore(); await auth.ensureSession()
    const first = auth.changePassword('old-test-password', 'new-test-password').catch(() => undefined)
    vi.spyOn(authAPI, 'login').mockResolvedValueOnce(session('Sol')); await auth.login(credentials('Sol')); const currentToken = storedToken()
    changed.resolve(session('Lucas')); await first
    expect(storedToken()).toBe(currentToken); expect(auth.user?.id).toBe('Sol')
  })

  it('does not restore a password-change session after explicit local expiry', async () => {
    const changed = deferred<LoginResponse>(); vi.spyOn(authAPI, 'changePassword').mockReturnValueOnce(changed.promise); verifyBySid()
    saveToken(token('Lucas')); const auth = useAuthStore(); await auth.ensureSession()
    const change = auth.changePassword('old-test-password', 'new-test-password').catch(() => undefined)
    auth.expire(); changed.resolve(session('Lucas')); await change
    expect(storedToken()).toBeNull(); expect(auth.isAuthenticated).toBe(false)
  })

  it('does not expire a new account when an earlier logout finishes', async () => {
    const loggedOut = deferred<void>(); vi.spyOn(authAPI, 'logout').mockReturnValueOnce(loggedOut.promise); verifyBySid()
    saveToken(token('Lucas')); const auth = useAuthStore(); await auth.ensureSession()
    const logout = auth.logout().catch(() => undefined)
    vi.spyOn(authAPI, 'login').mockResolvedValueOnce(session('Sol')); await auth.login(credentials('Sol')); const currentToken = storedToken()
    loggedOut.resolve(); await logout
    expect(storedToken()).toBe(currentToken); expect(auth.user?.id).toBe('Sol'); expect(auth.isAuthenticated).toBe(true)
  })
})

describe('External token changes during validation', () => {
  it.each(['success', 'error'] as const)('validates the new token independently and ignores old %s', async outcome => {
    const old = deferred<User>(), latest = deferred<User>()
    const get = vi.spyOn(authAPI, 'getCurrentUser').mockResolvedValueOnce(account('Lucas')).mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
    const oldToken = token('Lucas'), newToken = token('Sol')
    saveToken(oldToken); const auth = useAuthStore(); await auth.ensureSession()
    const first = auth.ensureSession(true); expect(auth.status).toBe('authenticated')
    saveToken(newToken); const second = auth.ensureSession()
    expect(auth.status).toBe('checking'); expect(get).toHaveBeenCalledTimes(3)
    expect(get).toHaveBeenLastCalledWith(newToken)
    latest.resolve(account('Sol')); expect(await second).toBe(true)
    if (outcome === 'success') old.resolve(account('Lucas'))
    else old.reject(new AxiosError('Old failure'))
    expect(await first).toBe(false); expect(auth.user?.id).toBe('Sol'); expect(auth.status).toBe('authenticated'); expect(auth.error).toBeNull()
  })

  it('ignores a password error from an expired session and retains the new login error/loading state', async () => {
    const password = deferred<LoginResponse>(), login = deferred<LoginResponse>()
    vi.spyOn(authAPI, 'changePassword').mockReturnValueOnce(password.promise)
    vi.spyOn(authAPI, 'login').mockReturnValueOnce(login.promise); verifyBySid()
    saveToken(token('Lucas')); const auth = useAuthStore(); await auth.ensureSession()
    const changed = auth.changePassword('old-test-password', 'new-test-password').catch(error => error)
    const entered = auth.login(credentials('Sol')).catch(() => undefined)
    password.reject(new AxiosError('Old password rejected')); expect((await changed).name).toBe('AuthOperationSuperseded')
    expect(auth.error).toBeNull(); expect(auth.isLoading).toBe(true)
    login.resolve(session('Sol')); await entered; expect(auth.user?.id).toBe('Sol')
  })

  it('keeps the new account after the older logout rejects and expires locally before waiting', async () => {
    const oldLogout = deferred<void>(); vi.spyOn(authAPI, 'logout').mockReturnValueOnce(oldLogout.promise); verifyBySid()
    saveToken(token('Lucas')); const auth = useAuthStore(); await auth.ensureSession()
    const logout = auth.logout().catch(() => undefined)
    expect(auth.status).toBe('guest'); expect(storedToken()).toBeNull()
    vi.spyOn(authAPI, 'login').mockResolvedValueOnce(session('Sol')); await auth.login(credentials('Sol'))
    oldLogout.reject(new Error('Old logout failed')); await logout
    expect(auth.user?.id).toBe('Sol'); expect(auth.isAuthenticated).toBe(true)
  })

  it('does not send a password mutation without a live captured session', async () => {
    const request = vi.spyOn(authAPI, 'changePassword')
    await expect(useAuthStore().changePassword('old-test-password', 'new-test-password')).rejects.toThrow('auth_operation_superseded')
    expect(request).not.toHaveBeenCalled()
  })
})
