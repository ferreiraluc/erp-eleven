import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { webcrypto } from 'node:crypto'
const mock = vi.hoisted(() => ({
  platform: 'android', native: true, config: vi.fn(), subscribe: vi.fn(), unsubscribe: vi.fn(),
  get: vi.fn(), set: vi.fn(), check: vi.fn(), request: vi.fn(), register: vi.fn(), channel: vi.fn(), clear: vi.fn(),
  settingsStatus: vi.fn(), settingsOpen: vi.fn(), settingsPrepare: vi.fn(),
  token: 'session-one', expires: 0, current: true, record: null as string | null,
  callbacks: {} as Record<string, ((event: any) => void)[]>,
}))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => mock.native, getPlatform: () => mock.platform },
  registerPlugin: (name: string) => name === 'ElevenNotificationSettings'
    ? { status: mock.settingsStatus, open: mock.settingsOpen, prepareChannel: mock.settingsPrepare } : { get: mock.get, set: mock.set } }))
vi.mock('@capacitor/push-notifications', () => ({ PushNotifications: {
  checkPermissions: mock.check, requestPermissions: mock.request, register: mock.register,
  createChannel: mock.channel, removeAllDeliveredNotifications: mock.clear,
  addListener: vi.fn(async (name: string, callback: (event: any) => void) => {
    ;(mock.callbacks[name] ||= []).push(callback)
    return { remove: vi.fn(async () => { mock.callbacks[name] = mock.callbacks[name]!.filter(value => value !== callback) }) }
  }),
} }))
vi.mock('./notifications', () => ({ notificationsAPI: { nativePushConfig: mock.config, subscribeNative: mock.subscribe, unsubscribe: mock.unsubscribe } }))
vi.mock('./sessionStorage', () => ({ storedToken: () => mock.token, tokenIsCurrent: () => mock.current, sessionExpiry: () => mock.expires }))
const emit = (name: string, value: any) => mock.callbacks[name]?.forEach(callback => callback(value))
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve() }
beforeEach(() => {
  vi.resetModules(); vi.clearAllMocks(); vi.stubEnv('VITE_NATIVE_PUSH_ENABLED', 'true')
  vi.stubGlobal('crypto', webcrypto)
  mock.native = true; mock.platform = 'android'; mock.callbacks = {}; mock.record = null
  mock.token = 'session-one'; mock.expires = Date.now() + 3600000; mock.current = true
  mock.get.mockImplementation(async () => ({ value: mock.record }))
  mock.set.mockImplementation(async ({ value }) => { mock.record = value })
  mock.config.mockImplementation(async (platform) => ({ available: true, platform, reason: 'ready' }))
  mock.check.mockResolvedValue({ receive: 'granted' }); mock.request.mockResolvedValue({ receive: 'granted' })
  mock.settingsStatus.mockResolvedValue({ enabled: true }); mock.settingsOpen.mockResolvedValue(undefined)
  mock.settingsPrepare.mockResolvedValue({ channelId: 'eleven-updates-v2' })
  mock.register.mockImplementation(async () => emit('registration', { value: 'native-provider-fixture' }))
  mock.channel.mockResolvedValue(undefined); mock.clear.mockResolvedValue(undefined); mock.unsubscribe.mockResolvedValue({})
  mock.subscribe.mockImplementation(async (value, token) => ({ id: 'sub', user_id: token === 'session-two' ? 'user-two' : 'user-one',
    active: true, device_token: value.device_token }))
})
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs() })

describe('Native push device and session isolation', () => {
  it('keeps unconfigured builds quiet without native calls or permission requests', async () => {
    vi.stubEnv('VITE_NATIVE_PUSH_ENABLED', 'false')
    const service = await import('./nativePush')
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(false)
    expect(service.nativePushSupport()).toBe('native_pending')
    expect(mock.config).not.toHaveBeenCalled(); expect(mock.check).not.toHaveBeenCalled(); expect(mock.register).not.toHaveBeenCalled()
  })
  it('does not request permissions when the server transport is not configured', async () => {
    mock.config.mockResolvedValue({ available: false, platform: 'android', reason: 'not_configured' })
    const service = await import('./nativePush')
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(false)
    await expect(service.enableNativeNotificationDevice('user-one', mock.token)).rejects.toThrow('unavailable')
    expect(mock.request).not.toHaveBeenCalled(); expect(mock.get).not.toHaveBeenCalled()
  })
  it('asks only from explicit enable and reuses granted OS permission on restore', async () => {
    mock.check.mockResolvedValue({ receive: 'prompt' })
    const service = await import('./nativePush')
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(false)
    expect(mock.request).not.toHaveBeenCalled(); expect(service.nativePushSupport()).toBe('ready')
    await service.enableNativeNotificationDevice('user-one', mock.token)
    expect(mock.request).toHaveBeenCalledOnce()
    mock.check.mockResolvedValue({ receive: 'granted' })
    await service.restoreNativeNotificationDevice('user-one', mock.token)
    expect(mock.request).toHaveBeenCalledOnce()
    const calls = mock.subscribe.mock.calls
    expect(calls[1]![0].device_token).toBe(calls[0]![0].device_token)
    expect(mock.record).not.toContain('session-one')
    expect(mock.set.mock.calls.every(([value]) => value.key === 'notification-installation')).toBe(true)
  })
  it('does not re-prompt a denied device', async () => {
    mock.check.mockResolvedValue({ receive: 'denied' })
    const service = await import('./nativePush')
    await expect(service.enableNativeNotificationDevice('user-one', mock.token)).rejects.toThrow('denied')
    expect(service.nativePushSupport()).toBe('denied')
    expect(mock.request).not.toHaveBeenCalled(); expect(mock.register).not.toHaveBeenCalled()
    expect(mock.settingsPrepare).not.toHaveBeenCalled()
  })
  it('prepares the OS channel before binding and never uses Capacitor raw sound names', async () => {
    const service = await import('./nativePush')
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(true)
    expect(mock.settingsPrepare).toHaveBeenCalledWith()
    expect(mock.settingsPrepare.mock.invocationCallOrder[0]).toBeLessThan(mock.settingsStatus.mock.invocationCallOrder[0]!)
    expect(mock.settingsStatus.mock.invocationCallOrder[0]).toBeLessThan(mock.subscribe.mock.invocationCallOrder[0]!)
    expect(mock.subscribe.mock.calls[0]![0].channel_id).toBe('eleven-updates-v2')
    expect(mock.channel).not.toHaveBeenCalled()
  })
  it('does not register a server binding if the OS did not prepare the expected channel', async () => {
    mock.settingsPrepare.mockResolvedValue({ channelId: 'unexpected-channel' })
    const service = await import('./nativePush')
    await expect(service.restoreNativeNotificationDevice('user-one', mock.token)).rejects.toThrow('notification-channel-unavailable')
    expect(mock.settingsStatus).not.toHaveBeenCalled(); expect(mock.subscribe).not.toHaveBeenCalled()
    expect(mock.register).not.toHaveBeenCalled()
  })
  it('recognizes an OS/channel block even when runtime permission reports granted, and restores after settings', async () => {
    mock.settingsStatus.mockResolvedValue({ enabled: false })
    const service = await import('./nativePush')
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(false)
    expect(service.nativePushSupport()).toBe('denied')
    expect(mock.register).not.toHaveBeenCalled(); expect(mock.request).not.toHaveBeenCalled()
    const settings = await import('./nativeNotificationSettings')
    await settings.openNativeNotificationSettings()
    expect(mock.settingsOpen).toHaveBeenCalledOnce()
    expect(mock.settingsOpen).toHaveBeenCalledWith()
    mock.settingsStatus.mockResolvedValue({ enabled: true })
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(true)
    expect(service.nativePushSupport()).toBe('ready')
    expect(mock.request).not.toHaveBeenCalled()
  })
  it('does not invoke Android settings or Android permission checks from iOS', async () => {
    mock.platform = 'ios'
    const settings = await import('./nativeNotificationSettings')
    expect(await settings.nativeNotificationsAllowed()).toBe(true)
    await expect(settings.openNativeNotificationSettings()).rejects.toThrow('settings-unavailable')
    expect(mock.settingsStatus).not.toHaveBeenCalled(); expect(mock.settingsOpen).not.toHaveBeenCalled()
    const service = await import('./nativePush')
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(true)
    expect(mock.settingsPrepare).not.toHaveBeenCalled(); expect(mock.channel).not.toHaveBeenCalled()
    expect(mock.subscribe.mock.calls[0]![0]).not.toHaveProperty('channel_id')
  })
  it('ignores a late blocked-settings result after logout', async () => {
    let resolve!: (value: { enabled: boolean }) => void
    mock.settingsStatus.mockReturnValueOnce(new Promise(result => { resolve = result }))
    const service = await import('./nativePush')
    const operation = service.restoreNativeNotificationDevice('user-one', mock.token)
    await vi.waitFor(() => expect(mock.settingsStatus).toHaveBeenCalledOnce())
    service.clearNativeNotificationDevice()
    const stale = expect(operation).rejects.toThrow('notification-session-changed')
    resolve({ enabled: false })
    await stale
    expect(service.nativePushSupport()).toBe('native_pending')
    expect(mock.register).not.toHaveBeenCalled(); expect(mock.subscribe).not.toHaveBeenCalled()
  })
  it('retains installation proof but rotates the session binding when another user logs in', async () => {
    const service = await import('./nativePush')
    await service.restoreNativeNotificationDevice('user-one', mock.token)
    const old = JSON.parse(mock.record!)
    service.clearNativeNotificationDevice(); await flush()
    mock.token = 'session-two'
    await service.restoreNativeNotificationDevice('user-two', mock.token)
    const current = JSON.parse(mock.record!)
    expect(current.secret).toBe(old.secret)
    expect(current.binding.device_token).not.toBe(old.binding.device_token)
    expect(current.binding.user_id).toBe('user-two')
    expect(mock.unsubscribe).toHaveBeenCalledWith({ device_token: old.binding.device_token }, 'session-one')
    expect(mock.clear).toHaveBeenCalledOnce()
    const open = vi.fn(); window.addEventListener('erp:native-notification-open', open)
    const id = '4df962ed-e688-4774-984f-dd91a8ad43ca'
    emit('pushNotificationActionPerformed', { notification: { data: { notification_id: id, device_token: old.binding.device_token, expires_at: mock.expires } } })
    expect(open).not.toHaveBeenCalled()
    emit('pushNotificationActionPerformed', { notification: { data: { notification_id: id, device_token: current.binding.device_token, expires_at: mock.expires, action_path: 'https://hostile.test' } } })
    expect(open).toHaveBeenCalledOnce(); expect(open.mock.calls[0]![0].detail).toEqual({ path: '/notificacoes' })
    window.removeEventListener('erp:native-notification-open', open)
  })
  it('does not bind a late subscribe result after logout', async () => {
    let resolve!: (value: any) => void
    mock.subscribe.mockReturnValue(new Promise(result => { resolve = result }))
    const service = await import('./nativePush')
    const operation = service.restoreNativeNotificationDevice('user-one', mock.token)
    await vi.waitFor(() => expect(mock.subscribe).toHaveBeenCalledOnce())
    const payload = mock.subscribe.mock.calls[0]![0]
    service.clearNativeNotificationDevice()
    resolve({ active: true, user_id: 'user-one', device_token: payload.device_token })
    await expect(operation).rejects.toThrow('notification-session-changed')
    await vi.waitFor(() => expect(mock.unsubscribe).toHaveBeenCalledWith({ device_token: payload.device_token }, 'session-one'))
    expect(JSON.parse(mock.record!).binding).toBeUndefined()
  })
  it('ignores malformed and expired payloads and all payloads after session expiry', async () => {
    const service = await import('./nativePush'); await service.restoreNativeNotificationDevice('user-one', mock.token)
    const active = JSON.parse(mock.record!).binding
    const open = vi.fn(); window.addEventListener('erp:native-notification-open', open)
    const base = { notification_id: '4df962ed-e688-4774-984f-dd91a8ad43ca', device_token: active.device_token, expires_at: mock.expires }
    for (const data of [{ ...base, expires_at: Date.now() - 1 }, { ...base, expires_at: mock.expires + 1 }, { ...base, notification_id: '//evil' }])
      emit('pushNotificationActionPerformed', { notification: { data } })
    mock.current = false; emit('pushNotificationActionPerformed', { notification: { data: base } })
    expect(open).not.toHaveBeenCalled(); window.removeEventListener('erp:native-notification-open', open)
  })
  it('fails closed if secure installation data is corrupt', async () => {
    mock.record = '{broken'
    const service = await import('./nativePush')
    await expect(service.restoreNativeNotificationDevice('user-one', mock.token)).rejects.toThrow('native-push-storage')
    expect(mock.set).not.toHaveBeenCalled(); expect(mock.subscribe).not.toHaveBeenCalled()
  })
  it('never registers an installation whose first secure write failed, including retries', async () => {
    mock.set.mockRejectedValue(new Error('secure storage unavailable'))
    const service = await import('./nativePush')
    for (let attempt = 0; attempt < 2; attempt++)
      await expect(service.restoreNativeNotificationDevice('user-one', mock.token)).rejects.toThrow('secure storage unavailable')
    expect(mock.subscribe).not.toHaveBeenCalled()
    expect(mock.register).not.toHaveBeenCalled()
    expect(mock.set).toHaveBeenCalledTimes(2)
    mock.set.mockImplementation(async ({ value }) => { mock.record = value })
    mock.subscribe.mockImplementation(async value => {
      expect(JSON.parse(mock.record!).secret).toBe(value.installation_secret)
      return { id: 'sub', user_id: 'user-one', active: true, device_token: value.device_token }
    })
    expect(await service.restoreNativeNotificationDevice('user-one', mock.token)).toBe(true)
  })
  it('normalizes provider failure without exposing registration details', async () => {
    mock.register.mockImplementation(async () => emit('registrationError', { error: 'provider secret' }))
    const service = await import('./nativePush')
    await expect(service.restoreNativeNotificationDevice('user-one', mock.token)).rejects.toThrow('native-push-registration')
    expect(mock.subscribe).not.toHaveBeenCalled()
    expect(mock.callbacks.registration).toEqual([])
  })
})
