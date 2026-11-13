import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NativeSessionVault, NativeSessionStorageError, NATIVE_SESSION_GUARD, type NativeSecureStoragePlugin } from './nativeSessionVault'

function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
function fixture() {
  const values = new Map<string, string>()
  const plugin: NativeSecureStoragePlugin = {
    get: vi.fn(async ({ key }) => ({ value: values.get(key) ?? null })),
    set: vi.fn(async ({ key, value }) => { values.set(key, value) }),
    remove: vi.fn(async ({ key }) => { values.delete(key) }),
    getVolatileSession: vi.fn(async () => ({ value: values.get('volatile:session') ?? null })),
    setVolatileSession: vi.fn(async ({ value }) => { values.set('volatile:session', value) }),
    clearVolatileSession: vi.fn(async () => { values.delete('volatile:session') }),
  }
  let nonce = 0
  return { plugin, values, vault: new NativeSessionVault(plugin, localStorage, () => `nonce-${++nonce}`) }
}
beforeEach(() => { localStorage.clear(); sessionStorage.clear() })

describe('Native secure session durability and isolation', () => {
  it('keeps credentials out of WebStorage and restores only the matching install marker', async () => {
    const { vault, plugin, values } = fixture(); await vault.initialize()
    vault.save('private-test-token', true); await vault.flush()
    expect(vault.token).toBe('private-test-token')
    expect(Object.values(localStorage)).not.toContain('private-test-token')
    expect(localStorage.getItem('auth_token')).toBeNull()
    expect(localStorage.getItem(NATIVE_SESSION_GUARD)).toBe('nonce-1')
    const reopened = new NativeSessionVault(plugin, localStorage); await reopened.initialize()
    expect(reopened.token).toBe('private-test-token')
    expect(JSON.parse(values.get('session')!).token).toBe('private-test-token')
  })

  it('does not adopt a Keychain credential from an earlier installation or uncommitted write', async () => {
    const { vault, plugin, values } = fixture()
    values.set('session', JSON.stringify({ version: 1, token: 'old-install-token', nonce: 'old', expiresAt: null }))
    values.set('notification-installation', 'installation-secret')
    await vault.initialize()
    expect(vault.token).toBeNull(); expect(values.has('session')).toBe(false)
    expect(values.get('notification-installation')).toBe('installation-secret')
    expect(plugin.get).not.toHaveBeenCalled()
    localStorage.setItem(NATIVE_SESSION_GUARD, 'new')
    values.set('session', JSON.stringify({ version: 1, token: 'partial-write', nonce: 'old', expiresAt: null }))
    const retry = new NativeSessionVault(plugin, localStorage); await retry.initialize()
    expect(retry.token).toBeNull(); expect(localStorage.getItem(NATIVE_SESSION_GUARD)).toBeNull()
  })

  it('serializes an in-flight save, logout and next account without restoring the old identity', async () => {
    const { vault, plugin, values } = fixture(); await vault.initialize()
    const oldWrite = deferred<void>()
    vi.mocked(plugin.set).mockImplementationOnce(async ({ key, value }) => { await oldWrite.promise; values.set(key, value) })
    vault.save('Lucas-token', true); const first = vault.flush(); await vi.waitFor(() => expect(plugin.set).toHaveBeenCalled())
    vault.clear()
    expect(vault.token).toBeNull(); expect(localStorage.getItem(NATIVE_SESSION_GUARD)).toBeNull()
    vault.save('Sol-token', true)
    oldWrite.resolve(); await first; await vault.flush()
    expect(vault.token).toBe('Sol-token')
    expect(JSON.parse(values.get('session')!).token).toBe('Sol-token')
    const reopened = new NativeSessionVault(plugin, localStorage); await reopened.initialize()
    expect(reopened.token).toBe('Sol-token')
  })

  it('invalidates an interrupted logout immediately even when native deletion fails', async () => {
    const { vault, plugin, values } = fixture(); await vault.initialize()
    vault.save('old-session', true); await vault.flush()
    vi.mocked(plugin.remove).mockRejectedValueOnce(new Error('disk locked'))
    vault.clear(); expect(vault.token).toBeNull()
    await expect(vault.flush()).rejects.toBeInstanceOf(NativeSessionStorageError)
    expect(values.has('session')).toBe(true)
    const reopened = new NativeSessionVault(plugin, localStorage); await reopened.initialize()
    expect(reopened.token).toBeNull(); expect(values.has('session')).toBe(false)
  })

  it('keeps non-remembered login through WebView reload but loses it when the native process ends', async () => {
    const { vault, plugin, values } = fixture(); await vault.initialize()
    vault.save('old-remembered', true); await vault.flush()
    vault.save('current-memory-only', false); await vault.flush()
    expect(vault.token).toBe('current-memory-only'); expect(vault.isRemembered).toBe(false)
    expect(values.has('session')).toBe(false); expect(localStorage.getItem(NATIVE_SESSION_GUARD)).toBeNull()
    const reloaded = new NativeSessionVault(plugin, localStorage); await reloaded.initialize(); expect(reloaded.token).toBe('current-memory-only')
    expect(reloaded.isRemembered).toBe(false)
    // A new process has empty native memory even if WebKit retained sessionStorage.
    values.delete('volatile:session')
    const reopened = new NativeSessionVault(plugin, localStorage); await reopened.initialize(); expect(reopened.token).toBeNull()
  })

  it('fails closed on secure writes and can recover without a plaintext fallback', async () => {
    const { vault, plugin } = fixture(); await vault.initialize()
    vi.mocked(plugin.set).mockRejectedValueOnce(new Error('locked'))
    vault.save('private-token', true)
    await expect(vault.flush()).rejects.toThrow('native_secure_session_unavailable')
    expect(vault.token).toBeNull(); expect(localStorage.getItem(NATIVE_SESSION_GUARD)).toBeNull()
    expect(localStorage.getItem('auth_token')).toBeNull()
    vault.save('new-token', true); await vault.flush(); expect(vault.token).toBe('new-token')
  })

  it('allows retry after a native read error and rejects corrupted records', async () => {
    const { vault, plugin, values } = fixture()
    localStorage.setItem(NATIVE_SESSION_GUARD, 'expected')
    vi.mocked(plugin.get).mockRejectedValueOnce(new Error('device locked'))
    await expect(vault.initialize()).rejects.toBeInstanceOf(NativeSessionStorageError)
    values.set('session', '{broken')
    await vault.initialize(); expect(vault.token).toBeNull(); expect(values.has('session')).toBe(false)
  })

  it('does not restore a session when logout happens during startup hydration', async () => {
    const { vault, plugin, values } = fixture()
    const reading = deferred<{ value: string | null }>()
    localStorage.setItem(NATIVE_SESSION_GUARD, 'old')
    vi.mocked(plugin.get).mockReturnValueOnce(reading.promise)
    const initialization = vault.initialize()
    vault.clear()
    reading.resolve({ value: JSON.stringify({ version: 1, token: 'old', nonce: 'old', expiresAt: null }) })
    await initialization; await vault.flush()
    expect(vault.token).toBeNull(); expect(values.has('session')).toBe(false)
  })

  it('a failed old write cannot clear the newer account waiting to persist', async () => {
    const { vault, plugin, values } = fixture(); await vault.initialize()
    const old = deferred<void>()
    vi.mocked(plugin.set).mockImplementationOnce(() => old.promise)
    vault.save('old', true); const failed = vault.flush().catch(error => error); await vi.waitFor(() => expect(plugin.set).toHaveBeenCalled())
    vault.clear(); vault.save('latest', true)
    old.reject(new Error('old write failed'))
    expect(await failed).toBeInstanceOf(NativeSessionStorageError)
    await vault.flush()
    expect(vault.token).toBe('latest'); expect(JSON.parse(values.get('session')!).token).toBe('latest')
  })

  it('ignores expiry updates from the previous account and invalidates stale persisted deadlines', async () => {
    const { vault, values } = fixture(); await vault.initialize()
    vault.save('current', true); await vault.flush()
    const oldNonce = localStorage.getItem(NATIVE_SESSION_GUARD)
    vault.shorten('previous', 10); expect(vault.expiresAt).toBeNull()
    vault.shorten('current', 100); await vault.flush()
    expect(vault.expiresAt).toBe(100)
    expect(localStorage.getItem(NATIVE_SESSION_GUARD)).not.toBe(oldNonce)
    expect(JSON.parse(values.get('session')!).expiresAt).toBe(100)
  })
})
