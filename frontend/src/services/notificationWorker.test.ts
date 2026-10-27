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
  }
  return { database, show, open, post, focus, self, dispatch, payload }
}
describe('Push worker privacy and account binding', () => {
  it('displays only generic content for a device owned by the active account', async () => {
    const value = worker()
    await value.dispatch('push', { data: { json: () => value.payload } })
    expect(value.show).toHaveBeenCalledWith(
      'ELEVEN',
      expect.objectContaining({
        body: 'Você tem uma nova notificação no sistema.',
        data: expect.objectContaining({ user_id: 'sol' }),
      }),
    )
    expect(JSON.stringify(value.show.mock.calls)).not.toContain('PRIVATE')
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
})
