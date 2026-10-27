import { beforeEach, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from './auth'
const clearDevice = vi.hoisted(() => vi.fn())
vi.mock('@/services/notificationPush', () => ({ clearNotificationDevice: clearDevice }))
beforeEach(() => { vi.resetAllMocks(); localStorage.clear(); sessionStorage.clear(); setActivePinia(createPinia()) })
it('clears a previous device binding even when a fresh page has no in-memory authenticated user', () => {
  const auth = useAuthStore()
  expect(auth.user).toBeNull()
  auth.expire()
  expect(clearDevice).toHaveBeenCalledOnce()
  expect(auth.status).toBe('guest')
})
