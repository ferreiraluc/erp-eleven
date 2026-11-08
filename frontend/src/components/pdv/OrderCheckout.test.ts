import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import i18n from '@/i18n'
import OrderCheckout from './OrderCheckout.vue'
import { chooseDropdown, openDropdown } from '@/test/dropdown'
import type { ReservationDetail } from '@/services/orderReservations'

const mocks = vi.hoisted(() => ({ detail: vi.fn(), payment: vi.fn(), checkout: vi.fn(), push: vi.fn(), loadRates: vi.fn(), rates: { 'G$': 6000, 'R$': 5, EUR: .9 } }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: mocks.push }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'seller-qa' } }) }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ exchangeRates: mocks.rates, loadCurrentRates: mocks.loadRates }) }))
vi.mock('@/services/orderReservations', async importOriginal => ({ ...await importOriginal<typeof import('@/services/orderReservations')>(), orderReservations: mocks }))
vi.mock('./PDVReceiptModal.vue', () => ({ default: { props: ['sale'], template: '<div class="qa-receipt">{{sale.id}}</div>' } }))
const initial: ReservationDetail = { id: 'order-qa', numero_pedido: 'PED-QA', commerce_status: 'reserved', commerce_version: 2,
  pdv_cliente_id: 'client-qa', cliente_id: 'directory-qa', cliente_nome: 'Cliente QA', vendedor_id: 'seller-qa', vendedor_nome: 'Sol QA',
  reserved_at: '2026-11-08T16:00:00Z', created_at: '2026-11-08T16:00:00Z', usd_rate_gs: 6000, subtotal_gs: 480000, desconto_gs: 0,
  total_gs: 480000, paid_gs: 120000, balance_gs: 360000, sale_id: null, notas: null,
  items: [{ id: 'line', item_id: 'product-qa', item_name: 'Camiseta QA', item_sku: 'INV-QA', item_size: 'L', item_color: 'Bege', location: 'loja', quantity: 2, unit_price_gs: 240000, total_gs: 480000 }],
  payments: [{ id: 'payment-qa', method: 'cash_usd', currency: 'USD', amount_original: 20, exchange_rate: 6000, amount_gs: 120000,
    cambista_id: null, reference: null, created_at: '2026-11-07T16:00:00Z', created_by: 'seller-qa', reversed_at: null, reversal_reason: null }],
}
let app: App | undefined, root: HTMLDivElement
async function tick() { for (let n = 0; n < 5; n++) { await Promise.resolve(); await nextTick() } }
async function mount() {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(OrderCheckout, { pedidoId: 'order-qa' }).use(i18n)
  app.config.globalProperties.$tr = (text: string) => text
  app.mount(root); await tick()
}
const button = (selector: string) => root.querySelector(selector) as HTMLButtonElement
async function amount(value: string) {
  const field = root.querySelector('input[aria-label="Valor recebido"]') as HTMLInputElement
  field.value = value; field.dispatchEvent(new Event('input', { bubbles: true })); await tick()
}
beforeEach(() => {
  vi.clearAllMocks(); sessionStorage.clear(); i18n.global.locale.value = 'pt'
  mocks.detail.mockResolvedValue(structuredClone(initial)); mocks.loadRates.mockResolvedValue(true)
})
afterEach(() => { app?.unmount(); root?.remove(); sessionStorage.clear() })

it('shows frozen customer, seller, reserved items and prior payments without editable product controls', async () => {
  await mount()
  expect(root.textContent).toContain('Cliente QA')
  expect(root.textContent).toContain('Sol QA')
  expect(root.textContent).toContain('US$ 80')
  expect(root.textContent).toContain('Camiseta QA')
  expect(root.querySelector('.pdv-qty-stepper')).toBeNull()
  expect(button('.order-finish').disabled).toBe(true)
  expect((await openDropdown(root.querySelector('.erp-dropdown'))).some(option => option.value === 'fiado')).toBe(false)
  expect(mocks.payment).not.toHaveBeenCalled(); expect(mocks.checkout).not.toHaveBeenCalled()
})

it('registers a partial receipt and keeps the reservation, without creating a sale', async () => {
  await mount(); await amount('20')
  mocks.payment.mockResolvedValue({ ...initial, commerce_version: 3, paid_gs: 240000, balance_gs: 240000 })
  button('.order-save-payment').click(); await tick()
  expect(mocks.payment).toHaveBeenCalledOnce()
  expect(mocks.payment.mock.calls[0][1]).toMatchObject({ confirm: true, expected_version: 2, payment: { method: 'cash_usd', amount_original: 20, amount_gs: 120000 } })
  expect(root.textContent).toContain('Pedido mantido separado')
  expect(mocks.checkout).not.toHaveBeenCalled()
})

it('finishes with only the new balance, leaving prior deposits for the server to reconcile once', async () => {
  await mount(); button('.order-total-button').click(); await tick()
  mocks.checkout.mockResolvedValue({ id: 'sale-qa' })
  button('.order-finish').click(); await tick()
  expect(mocks.checkout).toHaveBeenCalledOnce()
  expect(mocks.checkout.mock.calls[0][1]).toMatchObject({ expected_version: 2, confirm: true, print_receipt: true, payments: [{ amount_original: 60, amount_gs: 360000 }] })
  expect(mocks.checkout.mock.calls[0][1].payments).toHaveLength(1)
  expect(root.querySelector('.qa-receipt')?.textContent).toBe('sale-qa')
  expect(root.textContent).toContain('Este pedido já foi convertido em venda')
})

it('finishes an already paid order without asking for another payment or current exchange rates', async () => {
  mocks.detail.mockResolvedValue({ ...initial, balance_gs: 0, paid_gs: 480000 })
  mocks.loadRates.mockRejectedValue(new Error('offline rate provider'))
  await mount(); mocks.checkout.mockResolvedValue({ id: 'sale-qa' })
  expect(button('.order-finish').disabled).toBe(false)
  button('.order-finish').click(); await tick()
  expect(mocks.checkout.mock.calls[0][1].payments).toEqual([])
})

it('replays the same payment identity after an uncertain connection, including remount', async () => {
  await mount(); await amount('20')
  mocks.payment.mockRejectedValueOnce(new Error('response lost'))
  button('.order-save-payment').click(); await tick()
  const original = mocks.payment.mock.calls[0][1]
  expect(root.querySelector('fieldset')?.disabled).toBe(true)
  app!.unmount(); root.remove(); await mount()
  expect(root.textContent).toContain('aguardando confirmação')
  mocks.payment.mockResolvedValueOnce({ ...initial, commerce_version: 3, paid_gs: 240000, balance_gs: 240000 })
  button('.order-error button').click(); await tick()
  expect(mocks.payment.mock.calls[1][1]).toEqual(original)
  expect(sessionStorage.getItem('eleven.order-payment.seller-qa.order-qa')).toBeNull()
})

it('rejects noncash excess and preserves the optional 6% card gross-up', async () => {
  await mount()
  await chooseDropdown(root.querySelector('.erp-dropdown'), 'card_credit_py'); await tick()
  button('.order-total-button').click(); await tick()
  expect(root.textContent).toContain('Acréscimo cartão')
  const checkbox = root.querySelector('input[type="checkbox"]') as HTMLInputElement
  checkbox.click(); await tick(); button('.order-total-button').click(); await tick()
  mocks.checkout.mockResolvedValue({ id: 'sale-qa' })
  button('.order-finish').click(); await tick()
  expect(mocks.checkout.mock.calls[0][1].payments[0]).toMatchObject({ amount_original: 360000, amount_gs: 360000, card_fee_gs: 0, card_fee_percent: 0 })
})

it('does not post the stale version again after a definitive conflict', async () => {
  await mount(); await amount('20')
  mocks.payment.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'O pedido mudou em outro aparelho.' } } })
  button('.order-save-payment').click(); await tick()
  expect(root.textContent).toContain('O pedido mudou em outro aparelho')
  expect(sessionStorage.length).toBe(0)
  expect(mocks.payment).toHaveBeenCalledOnce()
})

it('ignores an old payment response after switching orders and preserves its recovery key', async () => {
  const activeId = ref('order-qa')
  root = document.createElement('div'); document.body.append(root)
  app = createApp({ setup: () => () => h(OrderCheckout, { pedidoId: activeId.value }) }).use(i18n)
  app.config.globalProperties.$tr = (text: string) => text
  app.mount(root); await tick(); await amount('20')
  let settle!: (value: ReservationDetail) => void
  mocks.payment.mockImplementationOnce(() => new Promise<ReservationDetail>(resolve => { settle = resolve }))
  button('.order-save-payment').click(); await tick()
  const recovery = sessionStorage.getItem('eleven.order-payment.seller-qa.order-qa')
  expect(recovery).toBeTruthy()
  mocks.detail.mockResolvedValue({ ...initial, id: 'second-order', cliente_nome: 'Outro cliente QA' })
  activeId.value = 'second-order'; await tick()
  expect(root.textContent).toContain('Outro cliente QA')
  settle({ ...initial, commerce_version: 3, paid_gs: 240000, balance_gs: 240000 }); await tick()
  expect(root.textContent).toContain('Outro cliente QA')
  expect(root.textContent).not.toContain('Cliente QA')
  expect(sessionStorage.getItem('eleven.order-payment.seller-qa.order-qa')).toBe(recovery)
  expect(sessionStorage.getItem('eleven.order-payment.seller-qa.second-order')).toBeNull()
  expect(root.querySelector('fieldset')?.disabled).toBe(false)
})
