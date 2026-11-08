import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import OrderReservationDetails from './OrderReservationDetails.vue'

const mock = vi.hoisted(() => ({ detail: vi.fn(), cancel: vi.fn(), reversePayment: vi.fn(), printTicket: vi.fn(), ticketState: vi.fn(), ticketPdf: vi.fn() }))
vi.mock('@/services/orderReservations', async importOriginal => ({ ...await importOriginal<typeof import('@/services/orderReservations')>(), orderReservations: mock }))
const auth = reactive({ isOwner: false })
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
vi.mock('@/components/inventory/ProductThumbnail.vue', () => ({ default: { props: ['item', 'alt'], template: '<img :alt="alt" />' } }))
let app: App | undefined, container: HTMLDivElement
const updated = vi.fn()
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); await nextTick() }
const payment = { id: 'payment-1', method: 'cash_usd', currency: 'USD', amount_original: 30, exchange_rate: 6000, amount_gs: 180000, created_at: '2026-11-08T15:00:00Z', created_by: 'seller', reversed_at: null, reversal_reason: null }
const order = (extra = {}) => ({ id: 'order-1', numero_pedido: 'PED-0001', commerce_status: 'reserved', commerce_version: 4, pdv_cliente_id: 'customer-1', cliente_nome: 'Gustavo', vendedor_nome: 'Sol', reserved_at: '2026-11-08T12:00:00Z', usd_rate_gs: 6000, subtotal_gs: 480000, desconto_gs: 0, total_gs: 480000, paid_gs: 180000, balance_gs: 300000, notas: 'Sacola 3, caixa', items: [{ id: 'line-1', item_id: 'product-1', item_name: 'Camiseta Boss', item_sku: 'INV-AB12', item_size: 'L', item_color: 'Navy', location: 'loja', quantity: 1, unit_price_gs: 480000, total_gs: 480000 }], payments: [payment], ...extra })
async function mount() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }, { path: '/pdv', component: { render: () => null } }, { path: '/vendas-pdv', component: { render: () => null } }] })
  await router.push('/'); await router.isReady()
  app = createApp(OrderReservationDetails, { orderId: 'order-1', onUpdated: updated }).use(router).use(i18n); app.config.globalProperties.$tr = uiText; app.mount(container); await settle(); return router
}
const button = (text: string) => Array.from(document.querySelectorAll('button')).find(node => node.textContent?.trim() === text)!
beforeEach(() => {
  vi.useFakeTimers(); auth.isOwner = false; i18n.global.locale.value = 'pt'; container = document.createElement('div'); document.body.append(container)
  mock.detail.mockResolvedValue(order()); mock.ticketState.mockResolvedValue({ printer: null, job: null }); updated.mockReset()
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.useRealTimers(); vi.resetAllMocks() })

describe('Reserved order details', () => {
  it('opens without printing or charging, and sends the exact order to POS', async () => {
    const router = await mount()
    expect(document.body.textContent).toContain('Gustavo'); expect(document.body.textContent).toContain('Sol'); expect(document.body.textContent).toContain('Pagamento parcial')
    expect(mock.printTicket).not.toHaveBeenCalled(); expect(mock.cancel).not.toHaveBeenCalled()
    const navigate = vi.spyOn(router, 'push')
    button('Receber no PDV').click(); await navigate.mock.results[0].value; await settle()
    expect(router.currentRoute.value.path).toBe('/pdv'); expect(router.currentRoute.value.query.pedido_id).toBe('order-1')
  })
  it('requires explicit print review and reuses the same request after a lost response', async () => {
    mock.printTicket.mockRejectedValueOnce(new Error('lost response')).mockResolvedValueOnce({ printer: { name: '3nStar' }, job: { id: 'job-1', status: 'pending', diagnostic_message: null } })
    await mount(); button('Imprimir separação').click(); await settle()
    expect(button('Imprimir ticket').disabled).toBe(true); expect(mock.printTicket).not.toHaveBeenCalled()
    document.querySelector<HTMLInputElement>('.confirm-check input')!.click(); await settle(); button('Imprimir ticket').click(); await settle()
    const first = structuredClone(mock.printTicket.mock.calls[0][1]); expect(first).toEqual(expect.objectContaining({ confirm: true, expected_version: 4 }))
    button('Repetir confirmação').click(); await settle()
    expect(mock.printTicket.mock.calls[1][1]).toEqual(first)
    expect(button('Imprimir separação').disabled).toBe(true)
  })
  it('blocks cancellation with deposits and exposes refund recording only to Lucas', async () => {
    await mount(); expect(button('Cancelar reserva').disabled).toBe(true); expect(button('Registrar devolução')).toBeUndefined()
    auth.isOwner = true; await settle(); expect(button('Registrar devolução')).toBeDefined()
    mock.reversePayment.mockResolvedValue(order({ commerce_version: 5, paid_gs: 0, balance_gs: 480000, payments: [{ ...payment, reversed_at: '2026-11-08T16:00:00Z', reversal_reason: 'Cliente desistiu' }] }))
    button('Registrar devolução').click(); await settle()
    expect(button('Confirmar').disabled).toBe(true)
    const reason = document.querySelector<HTMLTextAreaElement>('.confirmation-panel textarea')!; reason.value = 'Cliente desistiu'; reason.dispatchEvent(new Event('input'))
    document.querySelector<HTMLInputElement>('.confirm-check input')!.click(); await settle(); button('Confirmar').click(); await settle()
    expect(mock.reversePayment).toHaveBeenCalledWith('order-1', 'payment-1', expect.objectContaining({ reason: 'Cliente desistiu', confirm: true, expected_version: 4 }))
    expect(button('Cancelar reserva').disabled).toBe(false); expect(updated).toHaveBeenCalledTimes(1)
  })
  it('does not cancel until pieces and reason are reviewed', async () => {
    mock.detail.mockResolvedValue(order({ payments: [], paid_gs: 0, balance_gs: 480000 })); mock.cancel.mockResolvedValue(order({ commerce_status: 'cancelled', paid_gs: 0, payments: [] }))
    await mount(); button('Cancelar reserva').click(); await settle(); expect(mock.cancel).not.toHaveBeenCalled(); expect(button('Confirmar').disabled).toBe(true)
    const reason = document.querySelector<HTMLTextAreaElement>('.confirmation-panel textarea')!; reason.value = 'Cliente cancelou'; reason.dispatchEvent(new Event('input'))
    document.querySelector<HTMLInputElement>('.confirm-check input')!.click(); await settle(); button('Confirmar').click(); await settle()
    expect(mock.cancel).toHaveBeenCalledWith('order-1', expect.objectContaining({ reason: 'Cliente cancelou', expected_version: 4, confirm: true }))
    expect(button('Receber no PDV')).toBeUndefined()
  })
})
