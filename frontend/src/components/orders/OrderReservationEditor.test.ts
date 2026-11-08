import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import i18n from '@/i18n'
import { uiText } from '@/i18n/uiText'
import OrderReservationEditor from './OrderReservationEditor.vue'

const mock = vi.hoisted(() => ({ getItems: vi.fn(), getItemForSale: vi.fn(), getByBarcode: vi.fn(), detail: vi.fn(), create: vi.fn(), update: vi.fn(), loadRates: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItems: mock.getItems, getItemForSale: mock.getItemForSale, getByBarcode: mock.getByBarcode } }))
vi.mock('@/services/orderReservations', async importOriginal => ({ ...await importOriginal<typeof import('@/services/orderReservations')>(), orderReservations: { create: mock.create, update: mock.update, detail: mock.detail } }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ exchangeRates: { 'G$': 6000, 'R$': 5, EUR: .9, USD: 1 }, loadCurrentRates: mock.loadRates }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'seller' } }) }))
vi.mock('@/components/inventory/ProductThumbnail.vue', () => ({ default: { props: ['item', 'alt'], template: '<img :alt="alt" />' } }))
vi.mock('@/components/pdv/PDVCustomerPicker.vue', () => ({ default: { props: ['customerName', 'disabled'], emits: ['update:customerId', 'update:customerName', 'busy'], template: '<button data-customer :disabled="disabled" @click="$emit(\'update:customerId\', \'customer-1\'); $emit(\'update:customerName\', \'Gustavo\')">{{ customerName || \'Escolher cliente\' }}</button>' } }))
vi.mock('@/components/inventory/BarcodeScanner.vue', () => ({ default: { emits: ['barcode-detected', 'close'], template: '<button data-scan @click="$emit(\'barcode-detected\', \'INV-AB12\')">Escanear</button>' } }))

let app: App | undefined, container: HTMLDivElement
const saved = vi.fn()
const settle = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); await nextTick() }
const product = (extra = {}) => ({ id: 'product-1', name: 'Camiseta Boss', size: 'L', color: 'Navy', sku_internal: 'old-sku', inventory_code: 'INV-AB12', sale_price: 80, sale_currency: 'USD', stock_loja: 4, stock_deposito: 3, current_stock: 7, available_loja: 1, available_deposito: 3, is_active: true, updated_at: '2026-11-08', ...extra })
const reservation = (extra = {}) => ({ id: 'order-1', numero_pedido: 'PED-0001', commerce_status: 'reserved', commerce_version: 3, pdv_cliente_id: 'customer-1', cliente_nome: 'Gustavo', vendedor_nome: 'Sol', reservado_at: '2026-11-08T12:00:00Z', usd_rate_gs: 6000, subtotal_gs: 480000, desconto_gs: 0, total_gs: 480000, paid_gs: 0, balance_gs: 480000, notas: '', items: [{ id: 'line-1', item_id: 'product-1', item_name: 'Camiseta Boss', item_sku: 'INV-AB12', item_size: 'L', item_color: 'Navy', location: 'loja', quantity: 1, unit_price_gs: 480000, total_gs: 480000, available_loja: 0, available_deposito: 3 }], payments: [], ...extra })
async function mount(orderId?: string) { app = createApp(OrderReservationEditor, { orderId, onSaved: saved }).use(i18n); app.config.globalProperties.$tr = uiText; app.mount(container); await settle() }
const button = (text: string) => Array.from(document.querySelectorAll('button')).find(node => node.textContent?.trim().startsWith(text))!
const addButton = () => document.querySelector<HTMLButtonElement>('[aria-label="Separar Camiseta Boss"]')!
async function prepare() { document.querySelector<HTMLButtonElement>('[data-customer]')!.click(); addButton().click(); await settle(); document.querySelector<HTMLInputElement>('.review-checkbox input')!.click(); await settle() }
beforeEach(() => {
  vi.useFakeTimers(); sessionStorage.clear(); i18n.global.locale.value = 'pt'; container = document.createElement('div'); document.body.append(container)
  mock.loadRates.mockResolvedValue(true); mock.getItems.mockResolvedValue({ items: [product()] }); mock.getItemForSale.mockResolvedValue(product()); mock.detail.mockResolvedValue(reservation()); mock.create.mockResolvedValue(reservation()); mock.update.mockResolvedValue(reservation()); saved.mockReset()
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); sessionStorage.clear(); vi.useRealTimers(); vi.resetAllMocks() })

describe('Order separation editor', () => {
  it('requires a registered customer and reviewed reservation, and respects available rather than physical stock', async () => {
    await mount(); expect(mock.create).not.toHaveBeenCalled(); expect(button('Confirmar reserva').disabled).toBe(true)
    addButton().click(); await settle(); expect(addButton().disabled).toBe(true) // 4 physical, but only 1 available.
    expect(button('Confirmar reserva').disabled).toBe(true)
    document.querySelector<HTMLButtonElement>('[data-customer]')!.click(); await settle()
    document.querySelector<HTMLInputElement>('.review-checkbox input')!.click(); await settle()
    button('Confirmar reserva').click(); await settle()
    expect(mock.create).toHaveBeenCalledWith(expect.objectContaining({ pdv_cliente_id: 'customer-1', confirm: true, usd_rate_gs: 6000, items: [{ item_id: 'product-1', location: 'loja', quantity: 1, unit_price_gs: 480000 }] }))
    expect(saved).toHaveBeenCalledTimes(1)
  })
  it('keeps the exact request and disables edits while retrying a lost save response', async () => {
    mock.create.mockRejectedValueOnce(new Error('lost response')).mockResolvedValueOnce(reservation())
    await mount(); await prepare(); button('Confirmar reserva').click(); await settle()
    const first = structuredClone(mock.create.mock.calls[0][0])
    expect(document.querySelector<HTMLInputElement>('.catalog-search input')!.disabled).toBe(true)
    expect(button('Cancelar').disabled).toBe(true)
    button('Repetir confirmação').click(); await settle()
    expect(mock.create.mock.calls[1][0]).toEqual(first); expect(saved).toHaveBeenCalledTimes(1)
  })
  it('recovers an unresolved creation after reopening without automatically resubmitting', async () => {
    mock.create.mockRejectedValueOnce(new Error('lost response'))
    await mount(); await prepare(); button('Confirmar reserva').click(); await settle()
    const first = structuredClone(mock.create.mock.calls[0][0]); app!.unmount(); app = undefined
    await mount(); expect(mock.create).toHaveBeenCalledTimes(1)
    button('Repetir confirmação').click(); await settle()
    expect(mock.create.mock.calls[1][0]).toEqual(first)
  })
  it('edits a reservation with its frozen rate and does not count another client’s reserved pieces as available', async () => {
    mock.detail.mockResolvedValue(reservation({ usd_rate_gs: 5500 })); mock.getItems.mockResolvedValue({ items: [product({ available_loja: 0 })] })
    await mount('order-1')
    document.querySelector<HTMLButtonElement>('[aria-label="Aumentar quantidade"]')!.click(); await settle()
    expect(document.querySelector<HTMLInputElement>('[aria-label="Quantidade de Camiseta Boss"]')!.value).toBe('1')
    document.querySelector<HTMLInputElement>('.review-checkbox input')!.click(); await settle(); button('Salvar separação').click(); await settle()
    expect(mock.update).toHaveBeenCalledWith('order-1', expect.objectContaining({ expected_version: 3, usd_rate_gs: 5500 }))
  })
  it('does not choose automatically when a scanned barcode belongs to multiple variations', async () => {
    mock.getByBarcode.mockResolvedValue([product(), product({ id: 'product-2', size: 'XL' })]); await mount()
    document.querySelector<HTMLButtonElement>('[aria-label="Ler QR ou código de barras"]')!.click(); await settle(); document.querySelector<HTMLButtonElement>('[data-scan]')!.click(); await settle()
    expect(document.querySelectorAll('.catalog-product')).toHaveLength(2); expect(document.querySelectorAll('.selected-line')).toHaveLength(0)
    expect(document.body.textContent).toContain('Escolha a variação correta')
  })
})
