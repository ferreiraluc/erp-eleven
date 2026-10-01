import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosAdapter } from 'axios'
import api, { authAPI } from './api'
import { saveToken, storedToken } from './sessionStorage'
const previousAdapter = api.defaults.adapter
beforeEach(() => { localStorage.clear(); sessionStorage.clear() })
afterEach(() => { api.defaults.adapter = previousAdapter })

describe('Authentication request ownership', () => {
  it.each([
    ['password', () => authAPI.changePassword('old-test-password', 'new-test-password')],
    ['logout', () => authAPI.logout()],
    ['current user', () => authAPI.getCurrentUser()],
  ] as const)('keeps the original token for %s when storage changes before Axios dispatch', async (_name, request) => {
    let authorization: unknown
    api.defaults.adapter = (async config => { authorization = config.headers.Authorization
      return { status: 200, statusText: 'OK', headers: {}, config, data: {} }
    }) as AxiosAdapter
    saveToken('original-session'); const pending = request(); saveToken('different-session'); await pending
    expect(authorization).toBe('Bearer original-session'); expect(storedToken()).toBe('different-session')
  })

  it('ignores password-required errors belonging to an older identity', async () => {
    const passwordRequired = vi.fn(); window.addEventListener('erp:password-required', passwordRequired)
    try {
      saveToken('original-session')
      const adapter: AxiosAdapter = async config => {
        saveToken('different-session')
        throw new AxiosError('old password required', 'ERR_BAD_REQUEST', config, undefined,
          { status: 403, statusText: '', headers: {}, data: { detail: 'PASSWORD_CHANGE_REQUIRED' }, config })
      }
      await expect(api.get('/api/example', { adapter })).rejects.toThrow()
      expect(passwordRequired).not.toHaveBeenCalled(); expect(storedToken()).toBe('different-session')
    } finally { window.removeEventListener('erp:password-required', passwordRequired) }
  })
})

it.each([
  ['password', () => authAPI.changePassword('old-test-password', 'new-test-password')],
  ['logout', () => authAPI.logout()],
  ['current user', () => authAPI.getCurrentUser()],
] as const)('does not adopt a later session when %s started without a token', async (_name, request) => {
  let authorization: unknown
  api.defaults.adapter = (async config => { authorization = config.headers.Authorization
    return { status: 200, statusText: 'OK', headers: {}, config, data: {} }
  }) as AxiosAdapter
  const pending = request(); saveToken('different-session'); await pending
  expect(authorization == null).toBe(true)
})

it('respects an explicitly captured token even after storage changed before the auth call', async () => {
  let authorization: unknown
  api.defaults.adapter = (async config => { authorization = config.headers.Authorization
    return { status: 200, statusText: 'OK', headers: {}, config, data: {} }
  }) as AxiosAdapter
  saveToken('new-session'); await authAPI.logout('captured-old-session')
  expect(authorization).toBe('Bearer captured-old-session'); expect(storedToken()).toBe('new-session')
})

it('still reports password-required for the currently owned token', async () => {
  const required = vi.fn(); window.addEventListener('erp:password-required', required)
  try {
    saveToken('current')
    const adapter: AxiosAdapter = async config => { throw new AxiosError('password required', 'ERR_BAD_REQUEST', config, undefined,
      { status: 403, statusText: '', headers: {}, data: { detail: 'PASSWORD_CHANGE_REQUIRED' }, config }) }
    await expect(api.get('/api/example', { adapter })).rejects.toThrow()
    expect(required).toHaveBeenCalledOnce()
  } finally { window.removeEventListener('erp:password-required', required) }
})
