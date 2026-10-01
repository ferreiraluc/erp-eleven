import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import LoginView from './LoginView.vue'
import AccountView from './AccountView.vue'
import i18n from '@/i18n'
import { useAuthStore } from '@/stores/auth'
import { authAPI, type User, type LoginResponse } from '@/services/api'
import { AuthOperationSuperseded } from '@/services/authOperation'
import { saveToken } from '@/services/sessionStorage'
const mocks = vi.hoisted(() => ({ route: { value: { path: '/conta' } }, navigate: vi.fn(), replace: vi.fn(), resolve: vi.fn(() => ({ href: '/dashboard' })) }))
vi.mock('@/services/loginNavigation', () => ({ navigateAfterLogin: mocks.navigate }))
vi.mock('vue-router', () => ({ useRouter: () => ({ currentRoute: mocks.route, replace: mocks.replace, resolve: mocks.resolve }), RouterLink: { template: '<a><slot /></a>' } }))
let app: App | undefined, container: HTMLDivElement
function token() { return 'x.' + btoa(JSON.stringify({ sid: 'Sol', exp: Date.now() / 1000 + 3600 })) + '.x' }
const user = { id: 'Sol', nome: 'Sol', email: 'sol@eleven.com', role: 'GERENTE', ativo: true, must_change_password: false, sales_scope: 'own', sales_seller: 'Sol', vendedor_id: 'Sol', created_at: '', updated_at: '' } as User
function deferred<T>() { let resolve!: (value: T) => void, reject!: (error: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
function fill(input: HTMLInputElement, value: string) { input.value = value; input.dispatchEvent(new Event('input', { bubbles: true })) }
function mount(component: Parameters<typeof createApp>[0]) {
  const pinia = createPinia(); setActivePinia(pinia)
  container = document.createElement('div'); document.body.append(container)
  app = createApp(component).use(pinia).use(i18n); app.mount(container)
  return useAuthStore()
}
beforeEach(() => { localStorage.clear(); sessionStorage.clear(); mocks.navigate.mockReset(); mocks.replace.mockReset(); mocks.route.value.path = '/conta' })
afterEach(() => { app?.unmount(); container?.remove() })
describe('Authentication consumers', () => {
  it('finishes normal login even when App-style checking and user keys unmount its original form', async () => {
    const verified = deferred<User>()
    vi.spyOn(authAPI, 'login').mockResolvedValue({ access_token: token(), token_type: 'bearer', expires_in: 3600 })
    vi.spyOn(authAPI, 'getCurrentUser').mockReturnValueOnce(verified.promise)
    const Harness = defineComponent({ setup() { const auth = useAuthStore()
      return () => auth.status === 'checking' ? h('div', { 'data-checking': '' }, 'Checking') : h(LoginView, { key: auth.user?.id || 'guest' })
    } })
    const auth = mount(Harness)
    fill(container.querySelector('input[type="email"]') as HTMLInputElement, 'sol@eleven.com')
    fill(container.querySelector('input[type="password"]') as HTMLInputElement, 'test-password')
    container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(container.querySelector('[data-checking]')).not.toBeNull())
    expect(container.querySelector('form')).toBeNull()
    verified.resolve(user)
    await vi.waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith('/dashboard'))
    expect(auth.isAuthenticated).toBe(true)
  })
  it('does not navigate or show password errors for a superseded Account submission', async () => {
    const auth = mount(AccountView), pending = deferred<LoginResponse>()
    vi.spyOn(auth, 'changePassword').mockReturnValueOnce(pending.promise)
    for (const input of Array.from(container.querySelectorAll<HTMLInputElement>('input'))) fill(input, 'test-password')
    container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await nextTick()
    pending.reject(new AuthOperationSuperseded()); await nextTick(); await nextTick()
    expect(mocks.replace).not.toHaveBeenCalled(); expect(container.querySelector('[role="alert"]')).toBeNull()
  })
  it('ignores a password success after its Account view is closed', async () => {
    const auth = mount(AccountView), pending = deferred<LoginResponse>()
    vi.spyOn(auth, 'changePassword').mockReturnValueOnce(pending.promise)
    for (const input of Array.from(container.querySelectorAll<HTMLInputElement>('input'))) fill(input, 'test-password')
    container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await nextTick()
    const result = { access_token: token(), token_type: 'bearer', expires_in: 3600 }
    auth.token = result.access_token; auth.user = user; auth.status = 'authenticated'
    mocks.route.value.path = '/pedidos'
    app!.unmount(); app = undefined; pending.resolve(result); await nextTick(); await nextTick()
    expect(mocks.replace).not.toHaveBeenCalled()
  })
})


describe('Password rotation consumer', () => {
  it('navigates a normal password change after checking unmounts the original Account form', async () => {
    const checked = deferred<User>()
    const oldToken = 'x.' + btoa(JSON.stringify({ sid: 'before-change', exp: Date.now() / 1000 + 3600 })) + '.x'
    const result = { access_token: token(), token_type: 'bearer', expires_in: 3600 }
    vi.spyOn(authAPI, 'changePassword').mockResolvedValue(result)
    vi.spyOn(authAPI, 'getCurrentUser').mockReturnValueOnce(checked.promise)
    const Harness = defineComponent({ setup() { const auth = useAuthStore()
      return () => auth.status === 'checking' ? h('div', { 'data-checking': '' }, 'Checking') : h(AccountView, { key: auth.user?.id || 'guest' })
    } })
    const auth = mount(Harness)
    saveToken(oldToken); auth.token = oldToken; auth.user = user; auth.status = 'authenticated'; await nextTick()
    for (const input of Array.from(container.querySelectorAll<HTMLInputElement>('input'))) fill(input, 'test-password')
    container.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await vi.waitFor(() => expect(container.querySelector('[data-checking]')).not.toBeNull())
    checked.resolve(user)
    await vi.waitFor(() => expect(mocks.replace).toHaveBeenCalledWith('/dashboard'))
    expect(auth.token).toBe(result.access_token)
  })
})
