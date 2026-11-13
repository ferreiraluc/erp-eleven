import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import OrderReservationDetails from './OrderReservationDetails.vue'

const mock = vi.hoisted(() => ({ detail: vi.fn(), dispatch: vi.fn(), returnItems: vi.fn(), refundPreview: vi.fn(), cancel: vi.fn(), reversePayment: vi.fn(), printTicket: vi.fn(), ticketState: vi.fn(), ticketPdf: vi.fn(), native: false, share: vi.fn() }))
vi.mock('@/services/orderReservations', async importOriginal => ({ ...await importOriginal<typeof import('@/services/orderReservations')>(), orderReservations: mock }))
vi.mock('@/services/nativeFiles', async original => ({ ...await original<typeof import('@/services/nativeFiles')>(), usesNativeFiles: () => mock.native, shareNativePdf: mock.share }))
const auth = reactive({ isOwner: false, token: 'qa-session', user: { id: 'seller-qa' } })
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
  vi.useFakeTimers(); mock.native = false; auth.token = 'qa-session'; sessionStorage.clear(); auth.isOwner = false; i18n.global.locale.value = 'pt'; container = document.createElement('div'); document.body.append(container)
  mock.refundPreview.mockResolvedValue({ payment_id: payment.id, currency: 'USD', amount_gs: 180000, amount_original: 30, card_fee_gs: 0, expected_version: 4 }); mock.detail.mockResolvedValue(order()); mock.ticketState.mockResolvedValue({ printer: null, job: null }); updated.mockReset()
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
    const reason = document.querySelector<HTMLTextAreaElement>('.confirmation-panel textarea')!; reason.value = 'Cliente desistiu'; reason.dispatchEvent(new Event('input')); await settle(); button('Calcular devolução').click(); await settle()
    expect(document.body.textContent).toContain('Devolva ao cliente'); expect(mock.reversePayment).not.toHaveBeenCalled()
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

it('delivers only after reviewing identity, then exposes return and pending-ticket actions', async () => {
  mock.detail.mockResolvedValue(order({ paid_gs: 0, payments: [] })); mock.dispatch.mockResolvedValue(order({ commerce_status: 'conditional', delivered_at: '2026-11-08T16:00:00Z', commerce_version: 5 }))
  await mount(); button('Entregar em condicional').click(); await settle()
  expect(mock.dispatch).not.toHaveBeenCalled(); expect(button('Confirmar').disabled).toBe(true)
  document.querySelector<HTMLInputElement>('.confirm-check input')!.click(); await settle(); button('Confirmar').click(); await settle()
  expect(mock.dispatch).toHaveBeenCalledWith('order-1', expect.objectContaining({ expected_version: 4, confirm: true }))
  expect(button('Receber peças de volta')).toBeDefined(); expect(button('Imprimir condicional')).toBeDefined(); expect(button('Cancelar reserva')).toBeUndefined(); expect(mock.printTicket).not.toHaveBeenCalled()
})

it('returns selected quantities once after remount, keeping exact lines and version on retry', async () => {
  mock.detail.mockResolvedValue(order({ commerce_status: 'conditional', delivered_at: '2026-11-08T16:00:00Z' })); mock.returnItems.mockRejectedValueOnce(new Error('response lost')).mockResolvedValueOnce(order({ commerce_status: 'returned', items: [] }))
  await mount(); button('Receber peças de volta').click(); await settle()
  const qty = document.querySelector<HTMLInputElement>('.return-lines input')!; qty.value = '1'; qty.dispatchEvent(new Event('input'))
  const reason = document.querySelector<HTMLTextAreaElement>('.confirmation-panel textarea')!; reason.value = 'Cliente devolveu'; reason.dispatchEvent(new Event('input')); await settle()
  document.querySelector<HTMLInputElement>('.confirm-check input')!.click(); await settle(); button('Confirmar').click(); await settle()
  const first = structuredClone(mock.returnItems.mock.calls[0][1]); expect(first.lines).toEqual([{ line_id: 'line-1', quantity: 1 }])
  app!.unmount(); app = undefined; await mount(); expect(button('Repetir confirmação')).toBeDefined(); button('Repetir confirmação').click(); await settle()
  expect(mock.returnItems.mock.calls[1][1]).toEqual(first); expect(sessionStorage.getItem('eleven.order-action.seller-qa.order-1')).toBeNull()
})

it('blocks settlement with a refund due and invalidates the quote when the refund amount changes', async () => {
  auth.isOwner = true; mock.detail.mockResolvedValue(order({ commerce_status: 'conditional', delivered_at: '2026-11-08T16:00:00Z', refund_due_gs: 60000, total_gs: 120000, balance_gs: 0 }))
  mock.refundPreview.mockResolvedValue({ payment_id: payment.id, currency: 'USD', amount_gs: 60000, amount_original: 10, card_fee_gs: 0, expected_version: 4 })
  await mount(); expect(button('Concluir venda no PDV').disabled).toBe(true); button('Registrar devolução').click(); await settle()
  const reason = document.querySelector<HTMLTextAreaElement>('.confirmation-panel textarea')!; reason.value = 'Uma peça devolvida'; reason.dispatchEvent(new Event('input')); await settle(); button('Calcular devolução').click(); await settle()
  expect(mock.refundPreview.mock.calls[0][2]).toMatchObject({ amount_gs: 60000 }); expect(document.querySelector('.refund-preview')!.textContent).toContain('10,00')
  const field = document.querySelector<HTMLInputElement>('input[aria-label="Valor do pedido a devolver (G$)"]')!; field.value = '30000'; field.dispatchEvent(new Event('input')); await settle()
  expect(document.querySelector('.refund-preview')).toBeNull(); expect(button('Confirmar').disabled).toBe(true); expect(mock.reversePayment).not.toHaveBeenCalled()
})


it('offers a reserved-order PDF natively without enqueueing a print or payment', async () => {
  mock.native = true; mock.share.mockResolvedValueOnce('cancelled').mockResolvedValueOnce('opened')
  mock.ticketPdf.mockResolvedValue(new TextEncoder().encode('%PDF-1.4\nfixture\n%%EOF').buffer)
  const blob = vi.spyOn(URL, 'createObjectURL')
  await mount(); button('Opções do PDF').click(); await settle()
  expect(mock.share).toHaveBeenCalledTimes(1); expect(blob).not.toHaveBeenCalled()
  expect(document.body.textContent).toContain('Compartilhamento cancelado')
  const file = mock.share.mock.calls[0][0] as File
  expect(file.name).toMatch(/^eleven-separacao-.*\.pdf$/); expect(file.type).toBe('application/pdf')
  button('Opções do PDF').click(); await settle()
  expect(mock.share).toHaveBeenCalledTimes(2); expect(mock.printTicket).not.toHaveBeenCalled(); expect(mock.dispatch).not.toHaveBeenCalled()
  const current = mock.share.mock.calls[1][1] as () => boolean
  expect(current()).toBe(true); auth.token = 'other-session'; expect(current()).toBe(false)
  blob.mockRestore()
})
