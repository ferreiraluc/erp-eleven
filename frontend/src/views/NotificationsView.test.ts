import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createPinia, disposePinia, setActivePinia, type Pinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import NotificationsView from './NotificationsView.vue'
import type { NotificationItem } from '@/services/notifications'
const mocks = vi.hoisted(() => ({
  center: {} as Record<string, unknown>,
  auth: {} as Record<string, unknown>,
  act: vi.fn(),
  load: vi.fn(),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
vi.mock('@/stores/notificationCenter', () => ({ useNotificationCenter: () => mocks.center }))
vi.mock('@/components/ModuleHeader.vue', () => ({
  default: { template: '<header><slot /></header>' },
}))
vi.mock('@/components/notifications/NotificationPreferences.vue', () => ({
  default: { template: '<aside>Preferências</aside>' },
}))
let app: App | undefined, root: HTMLElement, pinia: Pinia
const item: NotificationItem = {
  id: 'notice',
  title: 'Conferir venda',
  body: '<img src=x onerror=alert(1)> Informe o motivo.',
  category: 'sales',
  severity: 'urgent',
  action_path: '/vendas-pdv?sale_id=fixture',
  requires_ack: true,
  requires_response: true,
  created_at: '2026-10-26T12:00:00Z',
  published_at: '2026-10-26T12:00:00Z',
  scheduled_at: null,
  read_at: null,
  acknowledged_at: null,
  cancelled_at: null,
  version: 3,
}
beforeEach(() => {
  vi.resetAllMocks()
  pinia = createPinia()
  setActivePinia(pinia)
  mocks.auth = reactive({ user: { id: 'lucas' }, token: 'first-session', status: 'authenticated' })
  mocks.act.mockResolvedValue(true)
  mocks.center = reactive({
    items: [{ ...item }],
    total: 1,
    unread: 1,
    loading: false,
    error: '',
    pending: [],
    unreadOnly: false,
    online: true,
    act: mocks.act,
    load: mocks.load,
  })
})
afterEach(() => {
  app?.unmount()
  root?.remove()
  disposePinia(pinia)
})
async function mount() {
  root = document.createElement('div')
  document.body.append(root)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      { path: '/vendas-pdv', component: { template: '<div />' } },
    ],
  })
  await router.push('/')
  app = createApp(NotificationsView).use(pinia).use(router)
  app.mount(root)
  await nextTick()
}
describe('User notification inbox', () => {
  it('clears a private draft and its validation error on account or session changes even for the same notice', async () => {
    await mount()
    const respond = Array.from(root.querySelectorAll('button')).find((node) =>
      node.textContent?.includes('Enviar resposta'),
    )!
    respond.click()
    await nextTick()
    expect(root.textContent).toContain('Informe o motivo antes de confirmar')
    const textarea = root.querySelector('textarea')!
    textarea.value = 'Rascunho privado de Lucas'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    mocks.auth.user = { id: 'sol' }
    mocks.auth.token = 'second-session'
    await nextTick()
    expect(root.querySelector('textarea')?.value).toBe('')
    expect(root.textContent).not.toContain('Informe o motivo antes de confirmar')
    textarea.value = 'Rascunho privado de Sol'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    mocks.auth.token = 'third-session'
    await nextTick()
    expect(root.querySelector('textarea')?.value).toBe('')
  })

  it('requires a response before acknowledging a review request and sends the displayed revision', async () => {
    await mount()
    const respond = Array.from(root.querySelectorAll('button')).find((node) =>
      node.textContent?.includes('Enviar resposta'),
    )!
    respond.click()
    await nextTick()
    expect(mocks.act).not.toHaveBeenCalled()
    expect(root.textContent).toContain('Informe o motivo antes de confirmar')
    const textarea = root.querySelector('textarea')!
    textarea.value = 'Cliente pediu item avulso.'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    respond.click()
    await nextTick()
    expect(mocks.act).toHaveBeenCalledWith('notice', 'ack', 'Cliente pediu item avulso.', 3)
  })
  it('renders plain text, styled urgency and a scoped internal sale link', async () => {
    await mount()
    expect(root.querySelector('article')?.classList.contains('notification-card--urgent')).toBe(
      true,
    )
    expect(root.textContent).toContain('<img src=x onerror=alert(1)>')
    expect(root.querySelector('article img')).toBeNull()
    expect(root.querySelector('article a')?.getAttribute('href')).toBe(
      '/vendas-pdv?sale_id=fixture',
    )
  })
  it('retains a failed response for retry instead of clearing the entered motive', async () => {
    mocks.act.mockResolvedValue(false)
    await mount()
    const textarea = root.querySelector('textarea')!
    textarea.value = 'Minha justificativa'
    textarea.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick()
    Array.from(root.querySelectorAll('button'))
      .find((node) => node.textContent?.includes('Enviar resposta'))!
      .click()
    await nextTick()
    expect(textarea.value).toBe('Minha justificativa')
  })
})
