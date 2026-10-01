import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createAuthGuard } from './authGuard'
import { clearSession, saveToken } from '@/services/sessionStorage'
import type { useAuthStore } from '@/stores/auth'
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes }); return { promise, resolve } }
function fixture() {
  const auth = { token: 'first', isLoading: false, status: 'authenticated', isOwner: false, ownSales: true, user: { must_change_password: false, role: 'GERENTE' }, ensureSession: vi.fn().mockResolvedValue(true) } as unknown as ReturnType<typeof useAuthStore>
  const routes = ['/dashboard', '/pedidos', '/inventory', '/conta', '/usuarios'].map(path => ({ path, component: { template: '<div />' }, meta: { requiresAuth: true, requiresOwner: path === '/usuarios' } }))
  const router = createRouter({ history: createMemoryHistory(), routes: [...routes, { path: '/login', component: { template: '<div />' }, meta: { requiresGuest: true } }] })
  router.beforeEach(createAuthGuard(() => auth))
  return { router, auth }
}
beforeEach(() => { clearSession(); saveToken('first') })
describe('Authentication navigation guard ownership', () => {
  it('cancels a delayed failed guard instead of redirecting a newer successful navigation', async () => {
    const { router, auth } = fixture(); await router.push('/dashboard')
    const old = deferred<boolean>(); vi.mocked(auth.ensureSession).mockReturnValueOnce(old.promise)
    const first = router.push('/inventory'); await vi.waitFor(() => expect(auth.ensureSession).toHaveBeenCalledTimes(2))
    await router.push('/pedidos'); expect(router.currentRoute.value.path).toBe('/pedidos')
    old.resolve(false); await first
    expect(router.currentRoute.value.path).toBe('/pedidos')
  })
  it('cancels an old privileged request when another token takes ownership without a second navigation', async () => {
    const { router, auth } = fixture(); await router.push('/dashboard')
    const old = deferred<boolean>(); vi.mocked(auth.ensureSession).mockReturnValueOnce(old.promise)
    const pending = router.push('/inventory'); await vi.waitFor(() => expect(auth.ensureSession).toHaveBeenCalledTimes(2))
    saveToken('new-account'); auth.token = 'new-account'; old.resolve(false); await pending
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })
  it('redirects a genuine expiry to login after validation clears its token', async () => {
    const { router, auth } = fixture(); await router.push('/dashboard')
    vi.mocked(auth.ensureSession).mockImplementation(async () => { clearSession(); auth.token = null; auth.status = 'guest'; return false })
    await router.push('/inventory')
    expect(router.currentRoute.value.path).toBe('/login')
  })
  it('preserves current account restrictions and first-password navigation', async () => {
    const { router, auth } = fixture(); await router.push('/usuarios')
    expect(router.currentRoute.value.path).toBe('/dashboard')
    auth.user!.must_change_password = true; await router.push('/pedidos')
    expect(router.currentRoute.value.path).toBe('/conta')
  })
})
