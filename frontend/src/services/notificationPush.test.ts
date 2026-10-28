import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { notificationDeviceDB } from '@/test/notificationDevice'
import { webcrypto } from 'node:crypto'
const mocks = vi.hoisted(() => ({ config: vi.fn(), subscribe: vi.fn(), unsubscribe: vi.fn() }))
vi.mock('./notifications', () => ({
  notificationsAPI: {
    pushConfig: mocks.config,
    subscribe: mocks.subscribe,
    unsubscribe: mocks.unsubscribe,
  },
}))
let requestPermission: ReturnType<typeof vi.fn>,
  nativeSubscribe: ReturnType<typeof vi.fn>,
  nativeUnsubscribe: ReturnType<typeof vi.fn>,
  getSubscription: ReturnType<typeof vi.fn>,
  subscription: PushSubscription,
  database: ReturnType<typeof notificationDeviceDB>
beforeEach(() => {
  vi.resetModules()
  vi.resetAllMocks()
  database = notificationDeviceDB()
  vi.stubGlobal('indexedDB', database.factory)
  vi.stubGlobal('crypto', webcrypto)
  Object.defineProperty(navigator, 'userActivation', {
    configurable: true,
    value: { isActive: true },
  })
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true })
  Object.defineProperty(navigator, 'userAgent', {
    configurable: true,
    value: 'Mozilla Android SamsungBrowser',
  })
  Object.defineProperty(navigator, 'platform', { configurable: true, value: 'Linux' })
  Object.defineProperty(navigator, 'maxTouchPoints', { configurable: true, value: 1 })
  requestPermission = vi.fn().mockResolvedValue('granted')
  vi.stubGlobal('Notification', { permission: 'default', requestPermission })
  vi.stubGlobal('PushManager', class {})
  window.matchMedia = vi.fn().mockReturnValue({ matches: false })
  nativeUnsubscribe = vi.fn().mockResolvedValue(true)
  subscription = {
    toJSON: () => ({
      endpoint: 'https://fcm.googleapis.com/fcm/send/device',
      keys: { p256dh: 'key', auth: 'auth' },
    }),
    unsubscribe: nativeUnsubscribe,
  } as unknown as PushSubscription
  getSubscription = vi.fn().mockResolvedValue(null)
  nativeSubscribe = vi.fn().mockResolvedValue(subscription)
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      register: vi.fn().mockResolvedValue({
        active: { postMessage: vi.fn() },
        pushManager: {
          getSubscription,
          subscribe: nativeSubscribe,
        },
      }),
      getRegistration: vi.fn().mockResolvedValue(undefined),
      controller: { postMessage: vi.fn() },
    },
  })
  mocks.config.mockResolvedValue({ available: true, public_key: 'AQID' })
  mocks.subscribe.mockImplementation(async (value) => ({
    id: 'subscription',
    device_token: value.device_token,
    user_id: 'sol',
    active: true,
  }))
  mocks.unsubscribe.mockResolvedValue({})
})
afterEach(() => {
  vi.unstubAllGlobals()
})
describe('Explicit device push permission', () => {
  it('requests permission before any network or registration work, never during feature detection', async () => {
    const push = await import('./notificationPush')
    expect(push.pushSupport()).toBe('ready')
    expect(requestPermission).not.toHaveBeenCalled()
    const activation = push.enableNotificationDevice('sol', 'token-sol')
    expect(requestPermission).toHaveBeenCalledOnce()
    expect(mocks.config).not.toHaveBeenCalled()
    expect(navigator.serviceWorker.register).not.toHaveBeenCalled()
    await activation
    expect(nativeSubscribe).toHaveBeenCalledOnce()
    expect(database.values.get('current')).toEqual({
      user_id: 'sol',
      device_token: expect.any(String),
    })
  })
  it('does not subscribe or contact the server when permission is denied', async () => {
    requestPermission.mockResolvedValueOnce('denied')
    const push = await import('./notificationPush')
    await expect(push.enableNotificationDevice('sol', 'token-sol')).rejects.toThrow('denied')
    expect(mocks.config).not.toHaveBeenCalled()
    expect(nativeSubscribe).not.toHaveBeenCalled()
    vi.stubGlobal('Notification', { permission: 'denied', requestPermission })
    expect(push.pushSupport()).toBe('denied')
  })
  it('explains iOS Home Screen requirement and unsupported browsers without invoking the OS prompt', async () => {
    Object.defineProperty(navigator, 'userAgent', { value: 'Mozilla iPhone Safari' })
    const push = await import('./notificationPush')
    expect(push.pushSupport()).toBe('ios')
    await expect(push.enableNotificationDevice('sol', 'token-sol')).rejects.toThrow('ios')
    expect(requestPermission).not.toHaveBeenCalled()
    Object.defineProperty(navigator, 'userAgent', { value: 'Mozilla Android' })
    Object.defineProperty(window, 'isSecureContext', { value: false })
    expect(push.pushSupport()).toBe('unsupported')
  })
  it('restores already granted permission even when a native subscription must be recreated', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    const push = await import('./notificationPush')
    expect(await push.restoreNotificationDevice('sol', 'token-sol')).toBe(true)
    expect(requestPermission).not.toHaveBeenCalled()
    expect(nativeSubscribe).toHaveBeenCalledOnce()
    expect(mocks.subscribe).toHaveBeenCalledOnce()
  })
  it('does not request permission or create an endpoint automatically for default or denied consent', async () => {
    const push = await import('./notificationPush')
    expect(await push.restoreNotificationDevice('sol', 'token-sol')).toBe(false)
    vi.stubGlobal('Notification', { permission: 'denied', requestPermission })
    expect(await push.restoreNotificationDevice('sol', 'token-sol')).toBe(false)
    expect(requestPermission).not.toHaveBeenCalled()
    expect(nativeSubscribe).not.toHaveBeenCalled()
    expect(mocks.config).not.toHaveBeenCalled()
  })
  it('does not invoke the native consent prompt without a current user gesture', async () => {
    Object.defineProperty(navigator, 'userActivation', {
      configurable: true,
      value: { isActive: false },
    })
    const push = await import('./notificationPush')
    await expect(push.enableNotificationDevice('sol', 'token-sol')).rejects.toThrow(
      'gesture-required',
    )
    expect(requestPermission).not.toHaveBeenCalled()
  })
  it('reuses a native endpoint and active binding across a reload of the same session', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    const push = await import('./notificationPush')
    await push.restoreNotificationDevice('sol', 'token-sol')
    const binding = database.values.get('current')
    getSubscription.mockResolvedValue(subscription)
    vi.resetModules()
    const reloaded = await import('./notificationPush')
    expect(await reloaded.restoreNotificationDevice('sol', 'token-sol')).toBe(true)
    expect(database.values.get('current')).toEqual(binding)
    expect(nativeSubscribe).toHaveBeenCalledOnce()
    expect(requestPermission).not.toHaveBeenCalled()
  })
  it('clears display authorization on logout but rebinds the same account next login without new consent', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    const push = await import('./notificationPush')
    await push.restoreNotificationDevice('sol', 'first-session')
    const before = database.values.get('current') as { device_token: string }
    getSubscription.mockResolvedValue(subscription)
    push.clearNotificationDevice()
    await vi.waitFor(() => expect(database.values.has('current')).toBe(false))
    expect(database.values.get('subscription-owner')).toMatchObject({ user_id: 'sol' })
    expect(JSON.stringify([...database.values])).not.toContain('first-session')
    expect(await push.restoreNotificationDevice('sol', 'next-session')).toBe(true)
    expect(database.values.get('current')).toMatchObject({ user_id: 'sol' })
    expect((database.values.get('current') as { device_token: string }).device_token).not.toBe(
      before.device_token,
    )
    expect(nativeUnsubscribe).not.toHaveBeenCalled()
    expect(nativeSubscribe).toHaveBeenCalledOnce()
    expect(requestPermission).not.toHaveBeenCalled()
  })
  it('renews the native endpoint and nonce before binding a different account', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    const push = await import('./notificationPush')
    await push.restoreNotificationDevice('sol', 'token-sol')
    getSubscription.mockResolvedValue(subscription)
    mocks.subscribe.mockImplementation(async (value) => ({
      user_id: 'lucas',
      device_token: value.device_token,
      active: true,
    }))
    expect(await push.restoreNotificationDevice('lucas', 'token-lucas')).toBe(true)
    expect(nativeUnsubscribe).toHaveBeenCalledOnce()
    expect(nativeSubscribe).toHaveBeenCalledTimes(2)
    expect(database.values.get('current')).toMatchObject({ user_id: 'lucas' })
    expect(requestPermission).not.toHaveBeenCalled()
  })
  it('clears stale device identity and rejects an activation that completed after logout', async () => {
    let finish!: (value: unknown) => void
    mocks.subscribe.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    const push = await import('./notificationPush'),
      pending = push.enableNotificationDevice('sol', 'token-sol')
    await vi.waitFor(() => expect(mocks.subscribe).toHaveBeenCalledOnce())
    push.clearNotificationDevice()
    const value = mocks.subscribe.mock.calls[0][0]
    finish({ id: 'sub', user_id: 'sol', device_token: value.device_token, active: true })
    await expect(pending).rejects.toThrow('notification-session-changed')
    await vi.waitFor(() => expect(database.values.has('current')).toBe(false))
    expect(navigator.serviceWorker.controller?.postMessage).not.toHaveBeenCalledWith({
      type: 'eleven-notification-clear',
      binding: null,
    })
  })
  it('revokes a persisted cold-start binding immediately while restore is blocked by network', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    database.values.set('current', { user_id: 'sol', device_token: 'previous-page-binding' })
    const digest = await webcrypto.subtle.digest('SHA-256', new TextEncoder().encode('token-sol'))
    database.values.set('subscription-owner', {
      user_id: 'sol',
      session_key: Buffer.from(digest).toString('hex'),
    })
    let finish!: (value: unknown) => void
    mocks.config.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    const push = await import('./notificationPush')
    const pending = push.restoreNotificationDevice('sol', 'token-sol')
    await vi.waitFor(() => expect(mocks.config).toHaveBeenCalled())
    expect(database.values.has('current')).toBe(true)
    push.clearNotificationDevice()
    await vi.waitFor(() => expect(database.values.has('current')).toBe(false))
    await vi.waitFor(() =>
      expect(navigator.serviceWorker.controller?.postMessage).toHaveBeenCalledWith({
        type: 'eleven-notification-clear',
        binding: { user_id: 'sol', device_token: 'previous-page-binding' },
      }),
    )
    finish({ available: true, public_key: 'AQID' })
    await expect(pending).rejects.toThrow('notification-session-changed')
    expect(database.values.has('current')).toBe(false)
    expect(nativeSubscribe).not.toHaveBeenCalled()
  })
  it('invalidates a different stored account before waiting for configuration on a cold start', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    database.values.set('current', { user_id: 'lucas', device_token: 'previous-account-binding' })
    database.values.set('subscription-owner', { user_id: 'lucas', session_key: 'older-session' })
    let finish!: (value: unknown) => void
    mocks.config.mockImplementationOnce(() => {
      expect(database.values.has('current')).toBe(false)
      return new Promise((resolve) => {
        finish = resolve
      })
    })
    const push = await import('./notificationPush')
    const pending = push.restoreNotificationDevice('sol', 'token-sol')
    await vi.waitFor(() => expect(mocks.config).toHaveBeenCalled())
    expect(database.values.has('current')).toBe(false)
    finish({ available: true, public_key: 'AQID' })
    expect(await pending).toBe(true)
    expect(database.values.get('current')).toMatchObject({ user_id: 'sol' })
  })
  it('does not let a previous cold-start logout erase a newer login of the same account', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    const digest = await webcrypto.subtle.digest(
      'SHA-256',
      new TextEncoder().encode('newer-session'),
    )
    database.values.set('subscription-owner', {
      user_id: 'sol',
      session_key: Buffer.from(digest).toString('hex'),
    })
    database.values.set('current', { user_id: 'sol', device_token: 'newer-login-nonce' })
    let finish!: (value: unknown) => void
    mocks.config.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    const push = await import('./notificationPush')
    const pending = push.restoreNotificationDevice('sol', 'old-session')
    await vi.waitFor(() => expect(mocks.config).toHaveBeenCalled())
    push.clearNotificationDevice()
    finish({ available: true, public_key: 'AQID' })
    await expect(pending).rejects.toThrow('notification-session-changed')
    await vi.waitFor(() => expect(navigator.serviceWorker.getRegistration).toHaveBeenCalled())
    expect(database.values.get('current')).toEqual({
      user_id: 'sol',
      device_token: 'newer-login-nonce',
    })
  })
  it('reports missing server configuration instead of claiming successful activation', async () => {
    mocks.config.mockResolvedValue({ available: false, public_key: '' })
    const push = await import('./notificationPush')
    await expect(push.enableNotificationDevice('sol', 'token-sol')).rejects.toThrow('unavailable')
    expect(nativeSubscribe).not.toHaveBeenCalled()
    expect(database.values.has('current')).toBe(false)
  })
})
