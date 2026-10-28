import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import NotificationBell from './NotificationBell.vue'
import type { NotificationItem } from '@/services/notifications'
const mocks = vi.hoisted(() => ({
  auth: {} as Record<string, unknown>,
  center: {} as Record<string, unknown>,
  act: vi.fn(),
  load: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/stores/notificationCenter', () => ({ useNotificationCenter: () => mocks.center }))
vi.mock('./NotificationPreferences.vue', () => ({
  default: {
    template: '<details class="notification-preferences"><summary>Preferências</summary></details>',
  },
}))
let app: App | undefined, root: HTMLElement, pinia: Pinia
const item: NotificationItem = {
  id: 'notice',
  title: 'Conferir venda #8B316EBBCA',
  body: 'Sol, informe o motivo.',
  category: 'sales',
  severity: 'warning',
  action_path: '/vendas-pdv?sale_id=fixture',
  requires_ack: true,
  requires_response: true,
  created_at: '2026-10-27T12:00:00Z',
  published_at: null,
  scheduled_at: null,
  read_at: null,
  acknowledged_at: null,
  version: 2,
  cancelled_at: null,
}
beforeEach(() => {
  vi.resetAllMocks()
  mocks.act.mockResolvedValue(true)
  mocks.auth = reactive({
    isAuthenticated: true,
    user: { id: 'lucas', must_change_password: false },
    token: 'fixture-token',
  })
  mocks.center = reactive({
    items: [{ ...item }],
    total: 2,
    unread: 1,
    loading: false,
    error: '',
    pending: [],
    unreadOnly: false,
    online: true,
    act: mocks.act,
    load: mocks.load,
  })
  pinia = createPinia()
  setActivePinia(pinia)
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
    left: 370,
    right: 402,
    top: 8,
    bottom: 40,
    width: 32,
    height: 32,
    x: 370,
    y: 8,
    toJSON() {
      return {}
    },
  })
  vi.stubGlobal('innerWidth', 412)
  vi.stubGlobal('innerHeight', 800)
})
afterEach(() => {
  app?.unmount()
  root?.remove()
  disposePinia(pinia)
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
async function mount() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/dashboard', '/notificacoes', '/vendas-pdv'].map((path) => ({
      path,
      component: { template: '<main />' },
    })),
  })
  await router.push('/dashboard')
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(NotificationBell).use(pinia).use(router)
  app.mount(root)
  await nextTick()
  return router
}
async function open() {
  root.querySelector<HTMLButtonElement>('.notification-bell')!.click()
  await nextTick()
  await nextTick()
}
const menu = () => document.querySelector<HTMLElement>('.notification-dropdown')!
const button = (text: string) =>
  Array.from(menu().querySelectorAll('button')).find((node) => node.textContent?.includes(text))!
describe('Dashboard notification dropdown', () => {
  it('opens an anchored, bounded menu without navigation, modal scroll lock or focusing an input', async () => {
    const router = await mount(),
      previousOverflow = document.body.style.overflow
    await open()
    expect(router.currentRoute.value.path).toBe('/dashboard')
    expect(root.querySelector('.notification-bell')?.getAttribute('aria-expanded')).toBe('true')
    expect(menu().parentElement).toBe(document.body)
    expect(Number.parseFloat(menu().style.width)).toBeCloseTo(288.4)
    expect(Number.parseFloat(menu().style.left)).toBeCloseTo(113.6)
    expect(menu().style.top).toBe('46px')
    expect(menu().getAttribute('aria-modal')).toBeNull()
    expect(document.body.style.overflow).toBe(previousOverflow)
    expect(document.activeElement?.tagName).not.toBe('TEXTAREA')
    expect(mocks.load).toHaveBeenCalledWith()
    expect(menu().textContent).toContain('Conferir venda #8B316EBBCA')
    expect(menu().querySelector('svg.lucide-x')).not.toBeNull()
  })
  it('shares inbox read, required response, version, mark-all and pagination behavior', async () => {
    await mount()
    await open()
    button('Enviar resposta').click()
    await nextTick()
    expect(mocks.act).not.toHaveBeenCalled()
    expect(menu().textContent).toContain('Informe o motivo antes de confirmar')
    const textarea = menu().querySelector('textarea')!
    textarea.value = 'Produto avulso confirmado'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    button('Enviar resposta').click()
    await nextTick()
    expect(mocks.act).toHaveBeenCalledWith('notice', 'ack', 'Produto avulso confirmado', 2)
    button('Marcar como lida').click()
    expect(mocks.act).toHaveBeenCalledWith('notice', 'read')
    button('Marcar todas').click()
    expect(mocks.act).toHaveBeenCalledWith('all', 'all')
    button('Carregar mais').click()
    expect(mocks.load).toHaveBeenCalledWith(true)
  })
  it('closes on Escape and outside pointer, restoring focus only for explicit dismissal', async () => {
    await mount()
    await open()
    menu().querySelector('textarea')!.focus()
    menu()
      .querySelector('textarea')!
      .dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await nextTick()
    expect(root.querySelector('.notification-bell')?.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(root.querySelector('.notification-bell'))
    await open()
    document.body.dispatchEvent(new Event('pointerdown', { bubbles: true }))
    await nextTick()
    expect(root.querySelector('.notification-bell')?.getAttribute('aria-expanded')).toBe('false')
  })
  it('keeps a draft on a brief close but clears it when the authenticated account changes', async () => {
    await mount()
    await open()
    const textarea = menu().querySelector('textarea')!
    textarea.value = 'Resposta em andamento'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    document.dispatchEvent(new CustomEvent('erp:dropdown-open', { detail: 'currency-menu' }))
    await nextTick()
    expect(root.querySelector('.notification-bell')?.getAttribute('aria-expanded')).toBe('false')
    await open()
    expect(menu().querySelector('textarea')?.value).toBe('Resposta em andamento')
    mocks.auth.user = { id: 'sol', must_change_password: false }
    mocks.auth.token = 'other-fixture'
    await nextTick()
    expect(document.querySelector('.notification-dropdown')).toBeNull()
    await open()
    expect(menu().querySelector('textarea')?.value).toBe('')
  })
  it('opens the full history or an entity link only after the matching action is clicked', async () => {
    const router = await mount()
    await open()
    menu().querySelector<HTMLAnchorElement>('article a')!.click()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/vendas-pdv'))
    expect(mocks.act).toHaveBeenCalledWith('notice', 'read')
    expect(root.querySelector('.notification-bell')?.getAttribute('aria-expanded')).toBe('false')
    await router.push('/dashboard')
    await open()
    menu().querySelector<HTMLAnchorElement>('.notification-dropdown__history')!.click()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/notificacoes'))
  })
  it('hides and removes the private menu on logout or a forced password change', async () => {
    await mount()
    await open()
    mocks.auth.isAuthenticated = false
    await nextTick()
    expect(root.querySelector('.notification-bell')).toBeNull()
    expect(document.querySelector('.notification-dropdown')).toBeNull()
    mocks.auth.isAuthenticated = true
    mocks.auth.user = { id: 'sol', must_change_password: true }
    await nextTick()
    expect(root.querySelector('.notification-bell')).toBeNull()
  })
})
