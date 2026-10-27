import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { AxiosAdapter } from 'axios'
import api from './api'
import { notificationsAPI, safeNotificationPath } from './notifications'
import { saveToken, storedToken } from './sessionStorage'
const adapter = api.defaults.adapter
beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})
afterEach(() => {
  api.defaults.adapter = adapter
})
describe('Notification API ownership and routes', () => {
  it('keeps the initiating session when account changes before Axios dispatch', async () => {
    let authorization: unknown
    api.defaults.adapter = (async (config) => {
      authorization = config.headers.Authorization
      return {
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
        data: { items: [], total: 0, unread_count: 0 },
      }
    }) as AxiosAdapter
    saveToken('old')
    const pending = notificationsAPI.inbox()
    saveToken('new')
    await pending
    expect(authorization).toBe('Bearer old')
    expect(storedToken()).toBe('new')
  })
  it('does not adopt a later account when a guest notification request started', async () => {
    let authorization: unknown
    api.defaults.adapter = (async (config) => {
      authorization = config.headers.Authorization
      return { status: 200, statusText: 'OK', headers: {}, config, data: {} }
    }) as AxiosAdapter
    const pending = notificationsAPI.preferences()
    saveToken('new')
    await pending
    expect(authorization == null).toBe(true)
  })
  it.each([
    'https://evil.example/',
    '//evil.example/',
    '/\\evil.example/',
    '/vendas-pdv\n',
    '/login',
    '/notificacoes/../../login',
    'javascript:alert(1)',
    '/unknown',
  ])('rejects unsafe or unsupported notification destination %s', (value) => {
    expect(safeNotificationPath(value)).toBeNull()
  })
  it.each(['/notificacoes', '/vendas-pdv?sale=abc', '/rastreamento', '/inventory?code=INV-ABC12'])(
    'preserves authorized internal destination %s',
    (value) => {
      expect(safeNotificationPath(value)).toBe(value)
    },
  )
})
