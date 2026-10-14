import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createMemoryHistory, createRouter, RouterView, type Router } from 'vue-router'
import i18n from '@/i18n'
import SalesManagementView from './SalesManagementView.vue'
import type { ManagedSale } from '@/services/pdvManagement'

const mocks = vi.hoisted(() => ({ detail: vi.fn(), list: vi.fn(), options: vi.fn(), preview: vi.fn(), commit: vi.fn() }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: false, ownSales: true }) }))
vi.mock('@/services/pdvManagement', async original => ({ ...await original<object>(), pdvManagementAPI: mocks }))
vi.mock('@/services/api', () => ({ default: {}, inventoryAPI: {}, pdvAPI: {} }))

const sale = (id: string): ManagedSale => ({
  id, vendedor_id: 'seller', cliente_id: 'customer', cliente_nome: `Cliente ${id}`,
  subtotal_gs: '100', desconto_gs: '0', total_gs: '100', refunded_gs: '0', fiado_reversed_gs: '0',
  status: 'completed', stock_applied: true, notas: null, version: 1,
  created_at: '2026-10-14T14:00:00-03:00', deleted_at: null, seller: 'Vendedor', actor: 'Vendedor',
  can_manage: false, payments: [], events: [], items: [], payment_difference_gs: '0',
})
let app: App | undefined, container: HTMLElement, router: Router
const settle = async () => { for (let n = 0; n < 12; n++) { await nextTick(); await Promise.resolve() } }
async function mount(path: string) {
  router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/vendas-pdv', component: SalesManagementView }] })
  await router.push(path); await router.isReady()
  app = createApp(RouterView).use(router).use(i18n)
  app.mount(container); await settle()
}
function button(text: string) { return Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim() === text) }
beforeEach(() => {
  vi.resetAllMocks(); i18n.global.locale.value = 'pt'
  container = document.createElement('div'); document.body.append(container)
  mocks.list.mockResolvedValue({ items: [], total: 0, page: 1, page_size: 20, summary: { net_gs: '0', refunded_gs: '0', cancelled: 0 } })
  mocks.options.mockResolvedValue({ sellers: [] })
  mocks.detail.mockImplementation(async id => sale(id))
})
afterEach(() => { app?.unmount(); app = undefined; container.remove() })

describe('Customer-to-sale navigation', () => {
  it('opens a linked sale outside the current page and retains employee permissions', async () => {
    await mount('/vendas-pdv?sale_id=older-sale&origin=customer')
    expect(mocks.detail).toHaveBeenCalledWith('older-sale')
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Cliente older-sale')
    expect(button('Editar venda')).toBeUndefined(); expect(button('Excluir venda')).toBeUndefined()
    button('Fechar')!.click(); await settle()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
    await vi.waitFor(() => expect(router.currentRoute.value.query).toEqual({ origin: 'customer' }))
    expect(mocks.preview).not.toHaveBeenCalled(); expect(mocks.commit).not.toHaveBeenCalled()
  })

  it('surfaces denial from the detail API independently of the sales list and can retry', async () => {
    mocks.detail.mockRejectedValueOnce({ response: { status: 404, data: { detail: 'Venda não encontrada' } } })
    await mount('/vendas-pdv?sale_id=unavailable')
    expect(document.querySelector('[role="dialog"] [role="alert"]')?.textContent).toContain('Venda não encontrada')
    expect(container.querySelector('.sales-results')).not.toBeNull()
    expect(button('Editar venda')).toBeUndefined()
    button('Tentar novamente')!.click(); await settle()
    expect(mocks.detail).toHaveBeenCalledTimes(2)
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Cliente unavailable')
  })

  it('loads each route selection and discards details from the previous sale', async () => {
    let finish!: (value: ManagedSale) => void
    mocks.detail.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    await mount('/vendas-pdv?sale_id=old')
    await router.push('/vendas-pdv?sale_id=new'); await settle()
    expect(mocks.detail).toHaveBeenLastCalledWith('new')
    finish(sale('old')); await settle()
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Cliente new')
    expect(document.querySelector('[role="dialog"]')?.textContent).not.toContain('Cliente old')
    await router.push('/vendas-pdv'); await settle()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })

  it('ignores ambiguous sale parameters rather than selecting a different sale', async () => {
    await mount('/vendas-pdv?sale_id=one&sale_id=two')
    expect(mocks.detail).not.toHaveBeenCalled()
    expect(document.querySelector('[role="dialog"]')).toBeNull()
  })
})
