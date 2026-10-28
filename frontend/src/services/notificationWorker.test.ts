import { readFileSync } from 'node:fs'
import { runInNewContext } from 'node:vm'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { notificationDeviceDB } from '@/test/notificationDevice'
const source = readFileSync(resolve('public/notifications-sw.js'), 'utf8')
function worker(binding: unknown = { user_id: 'sol', device_token: 'device-sol' }) {
  const database = notificationDeviceDB(binding),
    callbacks: Record<string, (event: unknown) => void> = {},
    show = vi.fn().mockResolvedValue(undefined),
    open = vi.fn().mockResolvedValue(undefined),
    post = vi.fn(),
    focus = vi.fn().mockResolvedValue(undefined)
  const self = {
    location: { origin: 'https://eleven.test' },
    addEventListener: (name: string, callback: (event: unknown) => void) => {
      callbacks[name] = callback
    },
    skipWaiting: vi.fn(),
    clients: { claim: vi.fn(), matchAll: vi.fn().mockResolvedValue([]), openWindow: open },
    registration: { showNotification: show, getNotifications: vi.fn().mockResolvedValue([]) },
  }
  runInNewContext(source, { self, indexedDB: database.factory, URL, Promise })
  async function dispatch(name: string, payload: Record<string, unknown>) {
    let completion: Promise<unknown> = Promise.resolve()
    callbacks[name]({
      ...payload,
      waitUntil: (value: Promise<unknown>) => {
        completion = value
      },
    })
    await completion
  }
  const payload = {
    notification_id: 'notice',
    version: 1,
    user_id: 'sol',
    device_token: 'device-sol',
    title: 'PRIVATE SALE DATA',
    body: 'PRIVATE CUSTOMER DATA',
    action_path: '/vendas-pdv?sale=secret',
    sound: true,
    expires_at: Date.now() + 3600000,
  }
  return { database, show, open, post, focus, self, dispatch, payload }
}
describe('Push worker privacy and account binding', () => {
  it('displays the actual title and message only for the currently bound account', async () => {
    const value = worker()
    await value.dispatch('push', { data: { json: () => value.payload } })
    expect(value.show).toHaveBeenCalledWith(
      'PRIVATE SALE DATA',
      expect.objectContaining({
        body: 'PRIVATE CUSTOMER DATA',
        data: expect.objectContaining({ user_id: 'sol' }),
      }),
    )
  })
  it('bounds content and falls back to a generic message for missing text', async () => {
    const value = worker()
    await value.dispatch('push', {
      data: { json: () => ({ ...value.payload, title: 'A'.repeat(200), body: 'B'.repeat(2000) }) },
    })
    expect(value.show.mock.calls[0][0]).toHaveLength(120)
    expect(value.show.mock.calls[0][1].body).toHaveLength(1000)
    await value.dispatch('push', {
      data: { json: () => ({ ...value.payload, title: null, body: '' }) },
    })
    expect(value.show.mock.calls[1][0]).toBe('ELEVEN')
    expect(value.show.mock.calls[1][1].body).toBe('Você tem uma nova notificação no sistema.')
  })
  it('rejects previous-account, previous-device and missing-binding pushes', async () => {
    const value = worker()
    await value.dispatch('push', { data: { json: () => ({ ...value.payload, user_id: 'lucas' }) } })
    await value.dispatch('push', {
      data: { json: () => ({ ...value.payload, device_token: 'previous' }) },
    })
    value.database.values.delete('current')
    await value.dispatch('push', { data: { json: () => value.payload } })
    expect(value.show).not.toHaveBeenCalled()
  })
  it('drops provider-delayed delivery and clicks after the daily session deadline', async () => {
    const value = worker()
    const expired = { ...value.payload, expires_at: Date.now() - 1 }
    await value.dispatch('push', { data: { json: () => expired } })
    await value.dispatch('notificationclick', { notification: { close: vi.fn(), data: expired } })
    expect(value.show).not.toHaveBeenCalled()
    expect(value.open).not.toHaveBeenCalled()
  })
  it('does not display private content if logout completes while clients are being enumerated', async () => {
    const value = worker()
    let finish!: (value: never[]) => void
    value.self.clients.matchAll.mockReturnValueOnce(
      new Promise((resolve) => {
        finish = resolve
      }),
    )
    const delivery = value.dispatch('push', { data: { json: () => value.payload } })
    await vi.waitFor(() => expect(value.self.clients.matchAll).toHaveBeenCalled())
    value.database.values.delete('current')
    finish([])
    await delivery
    expect(value.show).not.toHaveBeenCalled()
  })
  it('rejects notification clicks after logout, even if the OS still shows an old notification', async () => {
    const value = worker(null)
    await value.dispatch('notificationclick', {
      notification: { close: vi.fn(), data: value.payload },
    })
    expect(value.open).not.toHaveBeenCalled()
  })
  it('opens only a safe same-origin ERP route', async () => {
    const value = worker()
    await value.dispatch('notificationclick', {
      notification: {
        close: vi.fn(),
        data: { ...value.payload, action_path: 'https://evil.test' },
      },
    })
    expect(value.open).toHaveBeenCalledWith('https://eleven.test/#/notificacoes')
  })
  it('focuses and messages an existing app instead of reloading a live sales cart', async () => {
    const value = worker()
    value.self.clients.matchAll.mockResolvedValue([
      { url: 'https://eleven.test/#/pdv', postMessage: value.post, focus: value.focus } as never,
    ])
    await value.dispatch('notificationclick', {
      notification: { close: vi.fn(), data: value.payload },
    })
    expect(value.post).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'eleven-notification-open',
        action_path: '/vendas-pdv?sale=secret',
      }),
    )
    expect(value.focus).toHaveBeenCalled()
    expect(value.open).not.toHaveBeenCalled()
  })
  it('clears the stored binding and visible notifications on session cleanup', async () => {
    const value = worker(),
      close = vi.fn()
    value.self.registration.getNotifications.mockResolvedValue([{ close } as never])
    await value.dispatch('message', { data: { type: 'eleven-notification-clear' } })
    expect(value.database.values.has('current')).toBe(false)
    expect(close).toHaveBeenCalledOnce()
  })
  it('does not let a delayed previous-account logout erase the next account binding or message', async () => {
    const value = worker({ user_id: 'lucas', device_token: 'device-lucas' })
    const close = vi.fn()
    value.self.registration.getNotifications.mockResolvedValue([
      { close, data: { user_id: 'lucas', device_token: 'device-lucas' } } as never,
    ])
    await value.dispatch('message', {
      data: {
        type: 'eleven-notification-clear',
        binding: { user_id: 'sol', device_token: 'device-sol' },
      },
    })
    expect(value.database.values.get('current')).toEqual({
      user_id: 'lucas',
      device_token: 'device-lucas',
    })
    expect(close).not.toHaveBeenCalled()
  })
  it('does not erase a newer binding when a clearing page has not captured its old nonce yet', async () => {
    const value = worker()
    await value.dispatch('message', {
      data: { type: 'eleven-notification-clear', binding: null },
    })
    expect(value.database.values.get('current')).toEqual({
      user_id: 'sol',
      device_token: 'device-sol',
    })
  })
})
