import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { AxiosAdapter } from 'axios'
import api from './api'
import { saveToken } from './sessionStorage'
import { isOfflineReadOnly, setOfflineReadOnly } from './offlineAccess'

const originalAdapter = api.defaults.adapter
const adapter = vi.fn<AxiosAdapter>(async config => ({ status: 200, statusText: 'Synthetic', data: {}, headers: {}, config }))

beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); setOfflineReadOnly(null)
  adapter.mockClear(); api.defaults.adapter = adapter
  saveToken('synthetic-session'); setOfflineReadOnly('synthetic-session')
})
afterEach(() => { api.defaults.adapter = originalAdapter; setOfflineReadOnly(null) })

describe('Offline read-only request boundary', () => {
  it.each(['post', 'put', 'patch', 'delete'])('blocks %s before any network adapter or stale UI handler can mutate data', async method => {
    await expect(api.request({ method, url: '/api/inventory/items/synthetic', data: { stock: 10 } }))
      .rejects.toMatchObject({ code: 'ERR_OFFLINE_READ_ONLY' })
    expect(adapter).not.toHaveBeenCalled()
  })

  it('also blocks a mutation that explicitly captured the current authorization header', async () => {
    await expect(api.post('/api/pdv/sales', {}, { headers: { Authorization: 'Bearer synthetic-session' } }))
      .rejects.toMatchObject({ code: 'ERR_OFFLINE_READ_ONLY' })
    expect(adapter).not.toHaveBeenCalled()
  })

  it('allows current-user validation while preserving the write block until successful verification', async () => {
    await api.get('/api/auth/me')
    expect(adapter).toHaveBeenCalledOnce()
    expect(adapter.mock.calls[0][0].headers.Authorization).toBe('Bearer synthetic-session')
    await expect(api.post('/api/orders', {})).rejects.toMatchObject({ code: 'ERR_OFFLINE_READ_ONLY' })
    expect(adapter).toHaveBeenCalledOnce()
  })

  it('allows a new login without attaching the previously cached credential', async () => {
    await api.post('/api/auth/login', { email: 'synthetic@example.test', senha: 'test-only' })
    expect(adapter).toHaveBeenCalledOnce()
    expect(adapter.mock.calls[0][0].headers.has('Authorization')).toBe(false)
  })

  it('only permits writes after read-only mode is explicitly cleared', async () => {
    setOfflineReadOnly(null)
    await api.post('/api/inventory/items', {})
    expect(adapter).toHaveBeenCalledOnce()
  })

  it('does not apply an old identity flag to a different account', () => {
    expect(isOfflineReadOnly('synthetic-session')).toBe(true)
    expect(isOfflineReadOnly('different-session')).toBe(false)
    expect(isOfflineReadOnly(null)).toBe(false)
    window.dispatchEvent(new Event('erp:session-cleared'))
    expect(isOfflineReadOnly('synthetic-session')).toBe(false)
  })
})
