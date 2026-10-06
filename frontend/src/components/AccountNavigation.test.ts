import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import RootApp from '@/App.vue'
import DashboardView from '@/views/DashboardView.vue'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import { useAuthStore } from '@/stores/auth'
import { authAPI, exchangeRateAPI, healthAPI, inventoryAPI, type User } from '@/services/api'
import { saveToken } from '@/services/sessionStorage'

vi.mock('@/components/NotificationToast.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/RastreamentoCard.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/FolgasCard.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/dashboard/AddressSummaryCard.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/dashboard/SalesSummaryCard.vue', () => ({ default: { render: () => null } }))

let app: App | undefined, element: HTMLElement
const account = (owner: boolean): User => ({
  id: owner ? 'owner' : 'employee', nome: owner ? 'Lucas' : 'Sol',
  email: owner ? 'lucas@eleven.com' : 'sol@eleven.com', role: owner ? 'ADMIN' : 'GERENTE',
  ativo: true, must_change_password: false, sales_scope: owner ? 'all' : 'own',
  sales_seller: owner ? 'Lucas' : 'Sol', vendedor_id: null, created_at: '', updated_at: '',
})
async function mount(owner = true, path = '/dashboard') {
  const pinia = createPinia(); setActivePinia(pinia)
  const auth = useAuthStore(); auth.user = account(owner); auth.token = 'fixture-token'; auth.status = 'authenticated'; saveToken('fixture-token')
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/dashboard', component: DashboardView, meta: { requiresAuth: true } },
    ...['/conta', '/usuarios', '/auditoria', '/pedidos'].map(path => ({ path, component: { template: '<main>Fixture</main>' }, meta: { requiresAuth: true } })),
    { path: '/login', component: { template: '<main>Login</main>' } },
  ] })
  await router.push(path); await router.isReady()
  element = document.createElement('div'); document.body.append(element)
  app = createApp(RootApp).use(pinia).use(router).use(i18n)
  app.config.globalProperties.$tr = uiText
  app.mount(element); await nextTick()
  return { auth, router }
}
beforeEach(() => {
  localStorage.clear(); sessionStorage.clear(); i18n.global.locale.value = 'pt'
  vi.spyOn(exchangeRateAPI, 'getCurrentRates').mockResolvedValue({ usd_to_pyg: 7500, usd_to_brl: 5.2, eur_to_usd: 1, eur_to_brl: 5.2, last_updated: null, source: 'fixture' })
  vi.spyOn(inventoryAPI, 'getAlertsSummary').mockResolvedValue({} as never)
  vi.spyOn(inventoryAPI, 'getItems').mockResolvedValue({ items: [] } as never)
  vi.spyOn(healthAPI, 'check').mockResolvedValue({ api: 'online', database: 'online', timestamp: 0 })
})
afterEach(() => { app?.unmount(); element?.remove() })

describe('Account navigation inside the dashboard header', () => {
  it('shows one navigation within the personalized header, including owner actions', async () => {
    await mount()
    expect(element.querySelectorAll('.account-navigation')).toHaveLength(1)
    expect(element.querySelector('.account-bar')).toBeNull()
    const header = element.querySelector('.dashboard-header')!
    expect(header.querySelector('.app-title')?.textContent).toBe('ERP Eleven, Lucas')
    const nav = header.querySelector('nav')!
    expect(nav.getAttribute('aria-label')).toBe(i18n.global.t('access.navigation'))
    expect(Array.from(nav.querySelectorAll('a')).map(a => a.getAttribute('href'))).toEqual(['/conta', '/usuarios', '/auditoria'])
    expect(nav.querySelector('button')?.textContent).toContain('Sair')
    expect(header.querySelector('.header-preferences .currency-selector-group')).not.toBeNull()
    expect(header.querySelector('.current-time')?.textContent?.trim()).not.toBe('')
  })

  it('keeps a single header when the dashboard URL has a trailing slash', async () => {
    await mount(true, '/dashboard/')
    expect(element.querySelectorAll('.account-navigation')).toHaveLength(1)
    expect(element.querySelector('.dashboard-header nav')).not.toBeNull()
    expect(element.querySelector('.account-bar')).toBeNull()
  })

  it('keeps employee account/logout access while hiding owner-only links', async () => {
    const { router } = await mount(false)
    const nav = element.querySelector('.dashboard-header nav')!
    expect(nav.querySelector('a[href="/conta"]')).not.toBeNull()
    expect(nav.querySelector('a[href="/usuarios"]')).toBeNull()
    expect(nav.querySelector('a[href="/auditoria"]')).toBeNull()
    ;(nav.querySelector('a[href="/conta"]') as HTMLAnchorElement).click()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/conta'))
    expect(element.querySelectorAll('.account-navigation')).toHaveLength(1)
    expect(element.querySelector('.account-bar a[href="/dashboard"]')).not.toBeNull()
  })

  it('changes and persists the language through the header selector', async () => {
    await mount()
    const select = element.querySelector('.dashboard-header select') as HTMLSelectElement
    expect(select.getAttribute('aria-label')).toBe('Idioma')
    select.value = 'es'; select.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    expect(i18n.global.locale.value).toBe('es'); expect(localStorage.getItem('locale')).toBe('es')
    expect(document.documentElement.lang).toBe('es')
    expect(element.querySelector('.account-links a')?.textContent).toContain(i18n.global.t('access.account'))
  })

  it('keeps standalone account navigation on other private routes', async () => {
    await mount(true, '/pedidos')
    expect(element.querySelectorAll('.account-navigation')).toHaveLength(1)
    expect(element.querySelector('.account-bar a[href="/usuarios"]')).not.toBeNull()
    expect(element.querySelector('.account-bar select')).not.toBeNull()
  })

  it('logs out immediately from the header without letting an old response redirect a new account', async () => {
    let finish!: () => void
    const { auth, router } = await mount()
    vi.spyOn(authAPI, 'logout').mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    ;(element.querySelector('.dashboard-header nav button') as HTMLButtonElement).click()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/login'))
    expect(auth.isAuthenticated).toBe(false)
    auth.user = account(false); auth.token = 'new-fixture-token'; auth.status = 'authenticated'
    await router.push('/pedidos')
    finish(); await nextTick(); await nextTick()
    expect(auth.user?.id).toBe('employee'); expect(router.currentRoute.value.path).toBe('/pedidos')
  })
})
