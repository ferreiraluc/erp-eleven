import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import type { CustomerPurchases } from '@/services/customerLogistics'
import CustomerPurchasesHistory from './CustomerPurchasesHistory.vue'

const api = vi.hoisted(() => ({ purchases: vi.fn() }))
vi.mock('@/services/customerLogistics', () => ({ customerLogisticsAPI: api }))

const result = (page = 1, name = 'Camisa sintética'): CustomerPurchases => ({
  page, page_size: 1, total: 2, own_sales_only: true,
  summary: { net_gs: '75.00', refunded_gs: '25.00', cancelled: 1 },
  items: [{ id: `sale-${page}`, created_at: '2026-10-14T14:00:00-03:00',
    account_id: 'account-one', account_name: 'Conta revisada', customer_name: 'Nome histórico',
    seller: 'Vendedor sintético', status: page === 1 ? 'partially_refunded' : 'cancelled',
    total_gs: '100.00', refunded_gs: '25.00', net_gs: page === 1 ? '75.00' : '0.00',
    lines: [{ id: 'line-one', name, quantity: '2.000', returned_quantity: '1.000' }],
  }],
})
let app: App | undefined, container: HTMLDivElement
const customerId = ref('customer-one')
const settle = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); await nextTick() }
async function mount() {
  app = createApp({ render: () => h(CustomerPurchasesHistory, { customerId: customerId.value }) })
    .use(createI18n({ legacy: false, locale: 'pt', messages: {} }))
  app.mount(container); await settle()
}
function button(label: string) {
  return Array.from(container.querySelectorAll('button')).find(row => row.textContent?.trim() === label)!
}
beforeEach(() => {
  customerId.value = 'customer-one'
  container = document.createElement('div'); document.body.append(container)
  api.purchases.mockImplementation(async (_id: string, page: number) => result(page))
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.resetAllMocks() })

describe('Customer POS history', () => {
  it('shows financial scope, original items and independently paginated sales', async () => {
    await mount()
    expect(api.purchases).toHaveBeenLastCalledWith('customer-one', 1)
    expect(container.textContent).toContain('Você está consultando apenas suas vendas.')
    expect(container.textContent).toContain('Conta revisada')
    expect(container.textContent).toContain('Nome histórico')
    expect(container.textContent).toContain('2 × Camisa sintética')
    expect(container.textContent).toContain('Devolvido: 1')
    expect(container.textContent).toContain('Devolução parcial')
    expect(button('Anterior').disabled).toBe(true)
    button('Próxima').click(); await settle()
    expect(api.purchases).toHaveBeenLastCalledWith('customer-one', 2)
    expect(container.textContent).toContain('#sale-2')
    expect(container.textContent).not.toContain('#sale-1')
    expect(container.querySelector('.purchase-stats')?.textContent).toContain('G$ 75,00')
    expect(button('Próxima').disabled).toBe(true)
    expect(button('Anterior').disabled).toBe(false)
  })

  it('keeps failed pages distinct from an empty history and retries the requested page', async () => {
    await mount()
    api.purchases.mockRejectedValueOnce(new Error('offline'))
    button('Próxima').click(); await settle()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível carregar as compras.')
    expect(container.textContent).not.toContain('Nenhuma compra vinculada')
    expect(container.querySelector('.purchase-stats')).toBeNull()
    button('Tentar novamente').click(); await settle()
    expect(api.purchases).toHaveBeenLastCalledWith('customer-one', 2)
    expect(container.querySelector('[role="alert"]')).toBeNull()
    expect(container.textContent).toContain('#sale-2')
  })

  it('clears old customer data and discards a late response after switching customers', async () => {
    let finishOld!: (value: CustomerPurchases) => void
    api.purchases.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    await mount()
    customerId.value = 'customer-two'; await settle()
    expect(api.purchases).toHaveBeenLastCalledWith('customer-two', 1)
    finishOld(result(2, 'Compra de outra pessoa')); await settle()
    expect(container.textContent).toContain('Camisa sintética')
    expect(container.textContent).not.toContain('Compra de outra pessoa')
    expect(container.textContent).not.toContain('#sale-2')
  })
})
