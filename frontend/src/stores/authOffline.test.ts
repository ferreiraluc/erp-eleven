import { createCipheriv, createDecipheriv, randomBytes } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia'
import { AxiosError, CanceledError } from 'axios'

const runtime = vi.hoisted(() => ({ native: true, vault: null as unknown }))
vi.mock('@/services/nativeSessionVault', async importOriginal => {
  const actual = await importOriginal<typeof import('@/services/nativeSessionVault')>()
  return { ...actual, isNativeSession: () => runtime.native, nativeSessionVault: () => runtime.vault }
})
vi.mock('@/services/catalogIndex', () => ({ clearCatalogIndex: vi.fn() }))
vi.mock('@/services/notificationPush', () => ({ clearNotificationDevice: vi.fn() }))

import { useAuthStore } from './auth'
import { authAPI, type User } from '@/services/api'
import { NativeSessionVault, NATIVE_SESSION_GUARD, type NativeSecureStoragePlugin } from '@/services/nativeSessionVault'
import { flushSessionStorage, saveToken, storedToken } from '@/services/sessionStorage'
import { isOfflineReadOnly, setOfflineReadOnly } from '@/services/offlineAccess'

const NOW = Date.parse('2026-11-18T12:00:00Z')
const DEADLINE = Date.parse('2026-11-19T00:00:00Z') // 21:00 in Brasília.
const ALICE = '00000000-0000-4000-8000-000000000001'
const BRUNO = '00000000-0000-4000-8000-000000000002'
let pinia: Pinia
let fixture: ReturnType<typeof secureFixture>
let online: boolean

function token(subject = ALICE, sid = 'isolated-session', expires = DEADLINE) {
  return `test.${btoa(JSON.stringify({ sub: subject, sid, exp: expires / 1000 }))}.test`
}
function account(id = ALICE, overrides: Partial<User> = {}): User {
  return { id, nome: 'Synthetic user', email: 'synthetic@example.test', role: 'VENDEDOR',
    access_profile: 'standard', ativo: true, must_change_password: false, sales_scope: 'own',
    sales_seller: null, vendedor_id: null, created_at: '', updated_at: '',
    session_expires_at: new Date(DEADLINE).toISOString(), ...overrides }
}
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

// Exercise the actual vault with a native-boundary substitute. This proves the
// profile/credential go through the secure plugin rather than WebStorage; it
// does not substitute for Android Keystore or iOS Keychain device validation.
function secureFixture() {
  const sealed = new Map<string, Buffer>(), key = randomBytes(32)
  let volatile: string | null = null, nonce = 0
  const seal = (value: string) => {
    const iv = randomBytes(12), cipher = createCipheriv('aes-256-gcm', key, iv)
    return Buffer.concat([iv, cipher.update(value, 'utf8'), cipher.final(), cipher.getAuthTag()])
  }
  const open = (value: Buffer) => {
    const decipher = createDecipheriv('aes-256-gcm', key, value.subarray(0, 12))
    decipher.setAuthTag(value.subarray(-16))
    return Buffer.concat([decipher.update(value.subarray(12, -16)), decipher.final()]).toString('utf8')
  }
  const plugin: NativeSecureStoragePlugin = {
    get: vi.fn(async ({ key }) => ({ value: sealed.has(key) ? open(sealed.get(key)!) : null })),
    set: vi.fn(async ({ key, value }) => { sealed.set(key, seal(value)) }),
    remove: vi.fn(async ({ key }) => { sealed.delete(key) }),
    getVolatileSession: vi.fn(async () => ({ value: volatile })),
    setVolatileSession: vi.fn(async ({ value }) => { volatile = value }),
    clearVolatileSession: vi.fn(async () => { volatile = null }),
  }
  const createVault = () => new NativeSessionVault(plugin, localStorage, () => `offline-test-${++nonce}`)
  return { plugin, sealed, createVault,
    readRecord: () => JSON.parse(open(sealed.get('session')!)),
    replaceRecord: (record: unknown) => sealed.set('session', seal(JSON.stringify(record))) }
}

function newStore() {
  if (pinia) disposePinia(pinia)
  pinia = createPinia()
  setActivePinia(pinia)
  return useAuthStore()
}
async function reopen() {
  runtime.vault = fixture.createVault()
  await (runtime.vault as NativeSessionVault).initialize()
  return newStore()
}
async function verified(overrides: Partial<User> = {}, session = token()) {
  saveToken(session, true)
  await flushSessionStorage()
  const request = vi.spyOn(authAPI, 'getCurrentUser').mockResolvedValue(account(ALICE, overrides))
  const auth = useAuthStore()
  expect(await auth.ensureSession(true)).toBe(true)
  return { auth, request, session }
}
function transportError(status?: number) {
  const error = new AxiosError('Synthetic connection unavailable', status ? 'ERR_BAD_RESPONSE' : 'ERR_NETWORK')
  if (status) error.response = { status, statusText: 'Synthetic', data: {}, headers: {}, config: {} as never }
  return error
}

beforeEach(async () => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(NOW)
  vi.restoreAllMocks()
  localStorage.clear(); sessionStorage.clear(); setOfflineReadOnly(null)
  runtime.native = true
  online = true
  vi.spyOn(navigator, 'onLine', 'get').mockImplementation(() => online)
  fixture = secureFixture()
  runtime.vault = fixture.createVault()
  await (runtime.vault as NativeSessionVault).initialize()
  newStore()
})
afterEach(() => {
  disposePinia(pinia)
  setOfflineReadOnly(null)
  vi.useRealTimers()
})

describe('Native offline catalog identity', () => {
  it('reopens a previously verified encrypted record without network or online permissions', async () => {
    const { request, session } = await verified()
    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem('user_data')).toBeNull()
    expect(Object.values(localStorage).join(' ')).not.toContain('Synthetic user')
    expect(fixture.sealed.get('session')!.includes(Buffer.from(session))).toBe(false)
    const auth = await reopen()
    request.mockClear(); online = false
    expect(await auth.ensureSession()).toBe(false)
    expect(request).not.toHaveBeenCalled()
    expect(auth.status).toBe('offline')
    expect(auth.offlineViewer?.id).toBe(ALICE)
    expect(auth.user).toBeNull()
    expect(auth.isAuthenticated).toBe(false)
    expect(auth.isOwner).toBe(false)
    expect(isOfflineReadOnly(session)).toBe(true)
  })

  it('uses the last verified identity when connectivity claims online but the request fails', async () => {
    const { request } = await verified()
    const auth = await reopen()
    request.mockRejectedValueOnce(transportError())
    expect(await auth.ensureSession()).toBe(false)
    expect(auth.status).toBe('offline')
    expect(auth.offlineViewer?.id).toBe(ALICE)
  })

  it.each([502, 503, 504])('offers read-only consultation for server unavailability %s', async status => {
    const { request } = await verified(), auth = await reopen()
    request.mockRejectedValueOnce(transportError(status))
    await auth.ensureSession()
    expect(auth.status).toBe('offline'); expect(auth.isAuthenticated).toBe(false)
  })

  it.each([401, 403])('invalidates the cached identity on HTTP %s rather than restoring it offline', async status => {
    const { request, session } = await verified(), auth = await reopen()
    request.mockRejectedValueOnce(transportError(status))
    await auth.ensureSession(); await flushSessionStorage()
    expect(auth.status).toBe('guest'); expect(storedToken()).toBeNull()
    expect(auth.offlineViewer).toBeNull(); expect(isOfflineReadOnly(session)).toBe(false)
    expect(fixture.sealed.has('session')).toBe(false)
    online = false
    expect(await auth.ensureSession()).toBe(false)
    expect(auth.status).toBe('guest')
  })

  it('requires a successful online validation before normal operations resume', async () => {
    const { auth, session } = await verified()
    online = false; await auth.ensureSession()
    expect(auth.status).toBe('offline')
    online = true
    expect(await auth.ensureSession(true)).toBe(true)
    expect(auth.status).toBe('authenticated'); expect(auth.offlineViewer).toBeNull()
    expect(isOfflineReadOnly(session)).toBe(false)
  })

  it.each([{ must_change_password: true }, { ativo: false }])('does not retain offline access for restricted profiles %j', async overrides => {
    const { auth } = await verified(overrides)
    online = false
    vi.spyOn(authAPI, 'getCurrentUser').mockRejectedValue(transportError())
    await auth.ensureSession(true)
    expect(auth.status).not.toBe('offline'); expect(auth.offlineViewer).toBeNull()
    expect(fixture.readRecord().offlineViewer).toBeUndefined()
  })

  it('removes a previously valid offline profile when password rotation becomes required', async () => {
    const { auth, request } = await verified()
    request.mockResolvedValueOnce(account(ALICE, { must_change_password: true }))
    await auth.ensureSession(true)
    expect(fixture.readRecord().offlineViewer).toBeUndefined()
    online = false; request.mockRejectedValueOnce(transportError())
    await auth.ensureSession(true)
    expect(auth.offlineViewer).toBeNull(); expect(auth.status).not.toBe('offline')
  })

  it('expires at the server Brasília deadline even when the signed token has a later expiry', async () => {
    const { request } = await verified({}, token(ALICE, 'longer-jwt', DEADLINE + 3600000))
    vi.setSystemTime(DEADLINE)
    const auth = await reopen()
    request.mockClear(); online = false
    await auth.ensureSession(); await flushSessionStorage()
    expect(auth.status).toBe('guest'); expect(auth.offlineViewer).toBeNull()
    expect(storedToken()).toBeNull(); expect(request).not.toHaveBeenCalled()
  })

  it('does not extend a signed token that expires before the server deadline', async () => {
    const earlier = NOW + 3600000
    await verified({}, token(ALICE, 'earlier-expiry', earlier))
    vi.setSystemTime(earlier)
    const auth = await reopen(); online = false
    await auth.ensureSession()
    expect(auth.status).toBe('guest'); expect(auth.offlineViewer).toBeNull()
  })

  it('does not fall back offline after a cancelled request', async () => {
    const { request } = await verified(), auth = await reopen()
    request.mockRejectedValueOnce(new CanceledError('Superseded request'))
    await auth.ensureSession()
    expect(auth.status).toBe('error'); expect(auth.offlineViewer).toBeNull()
    expect(isOfflineReadOnly(storedToken())).toBe(false)
  })

  it('does not enable browser offline access from a native cached profile', async () => {
    const { request, session } = await verified()
    runtime.native = false
    localStorage.setItem('auth_token', session)
    const auth = newStore(); request.mockRejectedValueOnce(transportError())
    await auth.ensureSession()
    expect(auth.status).toBe('error'); expect(auth.offlineViewer).toBeNull()
  })

  it.each([
    { id: BRUNO }, { id: '' }, { name: 42 }, { profile: 'owner' }, { verifiedAt: null },
  ])('rejects malformed or foreign cached profile fields %j', async changes => {
    const { request } = await verified(), record = fixture.readRecord()
    record.offlineViewer = { ...record.offlineViewer, ...changes }
    fixture.replaceRecord(record)
    const auth = await reopen(); request.mockRejectedValueOnce(transportError())
    await auth.ensureSession()
    expect(auth.status).not.toBe('offline'); expect(auth.offlineViewer).toBeNull()
  })

  it('does not reuse a verified profile for a different session id, even for the same user', async () => {
    const { request, session } = await verified()
    const changed = token(ALICE, 'different-session')
    expect((runtime.vault as NativeSessionVault).offlineViewer(changed)).toBeNull()
    saveToken(changed, true); await flushSessionStorage()
    const auth = await reopen(); request.mockRejectedValueOnce(transportError())
    await auth.ensureSession()
    expect(auth.status).not.toBe('offline'); expect(auth.offlineViewer).toBeNull()
    expect(storedToken()).not.toBe(session)
  })

  it('rejects a clock that moved behind the successful server verification', async () => {
    const { request } = await verified()
    vi.setSystemTime(NOW - 120000)
    const auth = await reopen(); request.mockRejectedValueOnce(transportError())
    await auth.ensureSession()
    expect(auth.status).not.toBe('offline'); expect(auth.offlineViewer).toBeNull()
  })

  it('does not restore a cached account from a different installation marker', async () => {
    const { request } = await verified()
    localStorage.setItem(NATIVE_SESSION_GUARD, 'different-installation')
    const auth = await reopen(); request.mockClear(); online = false
    await auth.ensureSession()
    expect(auth.status).toBe('guest'); expect(storedToken()).toBeNull()
    expect(request).not.toHaveBeenCalled()
  })

  it.each(['success', 'network error'] as const)('does not restore an older user when their /me %s arrives after a new session', async outcome => {
    const { auth, request } = await verified()
    const old = deferred<User>(), latest = deferred<User>()
    request.mockReturnValueOnce(old.promise).mockReturnValueOnce(latest.promise)
    const pendingOld = auth.ensureSession(true)
    const nextToken = token(BRUNO, 'next-user')
    saveToken(nextToken, true); await flushSessionStorage()
    const pendingLatest = auth.ensureSession(true)
    latest.resolve(account(BRUNO, { nome: 'Second synthetic user' }))
    expect(await pendingLatest).toBe(true)
    if (outcome === 'success') old.resolve(account())
    else old.reject(transportError())
    expect(await pendingOld).toBe(false)
    expect(fixture.readRecord().offlineViewer.id).toBe(BRUNO)
    online = false; await auth.ensureSession()
    expect(auth.offlineViewer?.id).toBe(BRUNO)
  })

  it('does not restore a cached identity after logout races with a pending /me response', async () => {
    const { auth, request } = await verified(), pending = deferred<User>()
    request.mockReturnValueOnce(pending.promise)
    const validation = auth.ensureSession(true)
    auth.expire()
    pending.resolve(account())
    expect(await validation).toBe(false)
    await flushSessionStorage()
    expect(auth.status).toBe('guest'); expect(auth.offlineViewer).toBeNull()
    expect(storedToken()).toBeNull(); expect(fixture.sealed.has('session')).toBe(false)
  })

  it('fails closed when persisting the new verified profile fails', async () => {
    const { auth } = await verified()
    vi.mocked(fixture.plugin.set).mockRejectedValueOnce(new Error('Synthetic secure storage failure'))
    expect(await auth.ensureSession(true)).toBe(false)
    expect(auth.status).toBe('error'); expect(auth.offlineViewer).toBeNull()
    expect(auth.isAuthenticated).toBe(false); expect(storedToken()).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
  })
})
