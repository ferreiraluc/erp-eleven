import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { notificationDeviceDB } from '@/test/notificationDevice'
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
  database: ReturnType<typeof notificationDeviceDB>
beforeEach(() => {
  vi.resetModules()
  vi.resetAllMocks()
  database = notificationDeviceDB()
  vi.stubGlobal('indexedDB', database.factory)
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
  const subscription = {
    toJSON: () => ({
      endpoint: 'https://fcm.googleapis.com/fcm/send/device',
      keys: { p256dh: 'key', auth: 'auth' },
    }),
    unsubscribe: nativeUnsubscribe,
  }
  nativeSubscribe = vi.fn().mockResolvedValue(subscription)
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: {
      register: vi
        .fn()
        .mockResolvedValue({
          active: { postMessage: vi.fn() },
          pushManager: {
            getSubscription: vi.fn().mockResolvedValue(null),
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
  it('does not silently subscribe a fresh endpoint when reopening the system', async () => {
    vi.stubGlobal('Notification', { permission: 'granted', requestPermission })
    const push = await import('./notificationPush')
    expect(await push.restoreNotificationDevice('sol', 'token-sol')).toBe(false)
    expect(requestPermission).not.toHaveBeenCalled()
    expect(nativeSubscribe).not.toHaveBeenCalled()
    expect(mocks.subscribe).not.toHaveBeenCalled()
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
    expect(navigator.serviceWorker.controller?.postMessage).toHaveBeenCalledWith({
      type: 'eleven-notification-clear',
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
