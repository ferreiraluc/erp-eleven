import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { AxiosError } from 'axios'
import RootApp from './App.vue'
import i18n from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { authAPI, type User } from '@/services/api'
import { saveToken, storedToken } from '@/services/sessionStorage'
const mocks = vi.hoisted(() => ({ replace: vi.fn(), route: { path: '/conta', meta: { requiresAuth: true } } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ replace: mocks.replace }), useRoute: () => mocks.route,
  RouterLink: { template: '<a><slot /></a>' }, RouterView: { template: '<input data-private-form value="draft" />' } }))
vi.mock('@/components/NotificationToast.vue', () => ({ default: { template: '<div />' } }))
let app: App | undefined, container: HTMLDivElement
function token(sid = 'old') { return 'x.' + btoa(JSON.stringify({ sid, exp: Date.now() / 1000 + 3600 })) + '.x' }
const user = { id: 'Sol', nome: 'Sol', email: 'sol@eleven.com', role: 'GERENTE', ativo: true, must_change_password: false, sales_scope: 'own', sales_seller: 'Sol', vendedor_id: 'Sol', created_at: '', updated_at: '' } as User
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
function mount() {
  const pinia = createPinia(); setActivePinia(pinia)
  const auth = useAuthStore(); saveToken(token()); auth.token = storedToken(); auth.user = user; auth.status = 'authenticated'
  container = document.createElement('div'); document.body.append(container)
  app = createApp(RootApp).use(pinia).use(i18n); app.mount(container)
  return auth
}
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); mocks.replace.mockReset(); i18n.global.locale.value = 'pt' })
afterEach(() => { app?.unmount(); container?.remove() })
describe('Root session recovery and consumer ownership', () => {
  it.each(['success', 'error'])('does not navigate again when an old logout finishes with %s', async outcome => {
    const pending = deferred<void>(); vi.spyOn(authAPI, 'logout').mockReturnValueOnce(pending.promise)
    const auth = mount(); (container.querySelector('.account-bar button') as HTMLButtonElement).click(); await nextTick()
    expect(mocks.replace).toHaveBeenCalledExactlyOnceWith('/login')
    saveToken(token('new')); auth.token = storedToken(); auth.user = { ...user, id: 'Lucas' }; auth.status = 'authenticated'
    if (outcome === 'success') pending.resolve(); else pending.reject(new Error('Old failure'))
    await nextTick(); await nextTick()
    expect(mocks.replace).toHaveBeenCalledTimes(1); expect(auth.user?.id).toBe('Lucas')
  })
  it('shows a translated retry state after password rotation succeeds but session verification fails', async () => {
    const response = { access_token: token('rotated'), token_type: 'bearer', expires_in: 3600 }
    const unavailable = new AxiosError('offline'); unavailable.response = { status: 503, data: {}, statusText: '', headers: {}, config: { headers: {} as never } }
    vi.spyOn(authAPI, 'changePassword').mockResolvedValueOnce(response)
    const check = vi.spyOn(authAPI, 'getCurrentUser').mockRejectedValueOnce(unavailable)
    const auth = mount(); await expect(auth.changePassword('old-test-password', 'new-test-password')).rejects.toThrow(); await nextTick()
    expect(container.querySelector('[data-private-form]')).toBeNull()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível validar')
    expect(storedToken()).toBe(response.access_token)
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Could not verify')
    check.mockResolvedValueOnce(user)
    ;(container.querySelector('.session-error button') as HTMLButtonElement).click()
    await vi.waitFor(() => expect(container.querySelector('[data-private-form]')).not.toBeNull())
    expect(auth.isAuthenticated).toBe(true); expect(authAPI.changePassword).toHaveBeenCalledTimes(1)
  })
  it('preserves the exact private form element during an ordinary focus validation', async () => {
    const pending = deferred<User>(); vi.spyOn(authAPI, 'getCurrentUser').mockReturnValueOnce(pending.promise)
    const auth = mount(), input = container.querySelector('[data-private-form]') as HTMLInputElement
    input.value = 'unsaved work'
    const check = auth.ensureSession(true); await nextTick()
    expect(container.querySelector('[data-private-form]')).toBe(input)
    pending.resolve({ ...user }); await check; await nextTick()
    expect(container.querySelector('[data-private-form]')).toBe(input); expect(input.value).toBe('unsaved work')
  })
})
