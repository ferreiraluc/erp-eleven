import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import PedidosView from './PedidosView.vue'
import { orderTrackingLocation } from '@/services/orderNavigation'

const api = vi.hoisted(() => ({ getPage: vi.fn(), getById: vi.fn(), tags: vi.fn() }))
vi.mock('@/services/api', () => ({ pedidosAPI: api, tagsAPI: { getAll: api.tags } }))
vi.mock('@/components/PedidoModal.vue', () => ({ default: { render: () => null } }))
vi.mock('@/components/PedidoDetailsModal.vue', () => ({ default: { props: ['pedido'], template: '<div data-details>{{ pedido.numero_pedido }}</div>' } }))
let app: App | undefined
let container: HTMLDivElement
const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); await nextTick() }
const order = (id: string) => ({ id, numero_pedido: id, cliente_nome: `Cliente ${id}`, tags: [], status: 'PENDENTE', created_at: '2026-10-14', codigo_rastreio: 'QA123456789BR' })
const page = (id: string, total = 45) => ({ items: [order(id)], total, page: 1, page_size: 20 })
async function mount(path = '/') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }, { path: '/rastreamento', name: 'rastreamento', component: { render: () => null } }] })
  await router.push(path); await router.isReady()
  app = createApp(PedidosView).use(router).use(i18n)
  app.config.globalProperties.$tr = uiText
  app.mount(container); await settle()
  return router
}
const button = (label: string) => Array.from(container.querySelectorAll('button')).find(el => el.textContent?.trim() === label)!
beforeEach(() => {
  vi.useFakeTimers()
  i18n.global.locale.value = 'pt'
  container = document.createElement('div'); document.body.append(container)
  api.getPage.mockResolvedValue(page('Inicial'))
  api.tags.mockResolvedValue([])
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.useRealTimers(); vi.resetAllMocks() })

describe('Order directory navigation', () => {
  it('fetches another page and applies search to the server, resetting the page', async () => {
    await mount()
    api.getPage.mockResolvedValueOnce(page('Segunda'))
    button('Próxima').click(); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2, page_size: 20 }))
    expect(container.textContent).toContain('Segunda')
    expect(container.textContent).not.toContain('Cliente Inicial')
    const search = container.querySelector('input')!
    search.value = 'Antigo'; search.dispatchEvent(new Event('input')); await nextTick()
    api.getPage.mockResolvedValueOnce(page('Antigo', 1))
    await vi.advanceTimersByTimeAsync(300); await settle()
    expect(api.getPage).toHaveBeenLastCalledWith(expect.objectContaining({ page: 1, search: 'Antigo' }))
    expect(container.textContent).toContain('Cliente Antigo')
  })

  it('discards the old response while a changed search is waiting for debounce', async () => {
    let resolveOld!: (value: unknown) => void
    api.getPage.mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve }))
    await mount()
    const search = container.querySelector('input')!
    search.value = 'novo'; search.dispatchEvent(new Event('input')); await nextTick()
    resolveOld(page('Obsoleto')); await settle()
    expect(container.textContent).not.toContain('Obsoleto')
    expect(container.textContent).toContain('Carregando pedidos')
    await vi.advanceTimersByTimeAsync(300); await settle()
    expect(container.textContent).toContain('Cliente Inicial')
  })

  it('offers retry for a request error instead of presenting an empty directory', async () => {
    api.getPage.mockRejectedValueOnce(new Error('offline'))
    await mount()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível')
    expect(container.textContent).not.toContain('Nenhum pedido encontrado')
    button('Tentar novamente').click(); await settle()
    expect(container.querySelector('[role="alert"]')).toBeNull()
  })

  it('opens an order linked from another screen even outside the loaded page', async () => {
    api.getById.mockResolvedValueOnce(order('Antigo'))
    await mount('/?pedido_id=Antigo')
    expect(api.getById).toHaveBeenCalledWith('Antigo')
    expect(container.querySelector('[data-details]')?.textContent).toBe('Antigo')
  })

  it('links to the existing tracking route with the code or recipient, without creating a shipment', async () => {
    const router = await mount()
    const location = orderTrackingLocation(order('Inicial'))
    expect(router.resolve(location).href).toContain('/rastreamento?search=QA123456789BR')
    expect(orderTrackingLocation({ codigo_rastreio: '', cliente_nome: 'Ana' }).query.search).toBe('Ana')
  })

  it('keeps the directory visible and retries the failed deep link independently', async () => {
    api.getById.mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce(order('Antigo'))
    await mount('/?pedido_id=Antigo')
    expect(container.textContent).toContain('Cliente Inicial')
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('abrir o pedido')
    button('Tentar novamente').click(); await settle()
    expect(api.getPage).toHaveBeenCalledTimes(1)
    expect(api.getById).toHaveBeenCalledTimes(2)
    expect(container.querySelector('[data-details]')?.textContent).toBe('Antigo')
  })
})
