import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import PDVView from './PDVView.vue'
import { usePdvStore } from '@/stores/pdv'
import type { InventoryItem, PdvSaleResponse } from '@/services/api'

const mocks = vi.hoisted(() => ({ getItems: vi.fn(), getByBarcode: vi.fn(), createSale: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/services/api', () => ({ inventoryAPI: mocks, pdvAPI: { createSale: mocks.createSale } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'fixture-user', role: 'USER' } }) }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ currentRates: {}, loadCurrentRates: vi.fn().mockResolvedValue(true), exchangeRates: { 'G$': 6500, 'R$': 5, EUR: .9 } }) }))
vi.mock('@/components/inventory/BarcodeScanner.vue', () => ({ default: {
  emits: ['barcode-detected', 'close'],
  template: '<button class="scan-fixture" @click="$emit(\'barcode-detected\', \'FIXTURE-CODE\')">Read fixture</button>',
} }))
vi.mock('@/components/pdv/PDVReceiptModal.vue', () => ({ default: { template: '<div class="receipt-fixture" />' } }))

const item = { id: 'fixture-product', name: 'Produto sintético', sku_internal: 'FIXTURE', sale_price: 100,
  sale_currency: 'PYG', current_stock: 3, stock_loja: 3, stock_deposito: 0, is_active: true } as InventoryItem
let app: App | undefined, root: HTMLDivElement
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>(res => { resolve = res })
  return { promise, resolve }
}
async function flush() { for (let n = 0; n < 6; n++) await Promise.resolve(); await nextTick() }
async function click(selector: string) { root.querySelector<HTMLElement>(selector)!.click(); await flush() }
async function search(value: string) {
  const input = root.querySelector<HTMLInputElement>('.pdv-search-input')!
  input.value = value; input.dispatchEvent(new Event('input', { bubbles: true }))
  await vi.advanceTimersByTimeAsync(300); await flush()
}
async function scan() { await click('.pdv-scan-btn'); await click('.scan-fixture') }
async function preparePayment() {
  await click('.pdv-result-row')
  const select = root.querySelector<HTMLSelectElement>('.pay-select')!
  select.value = 'cash_gs'; select.dispatchEvent(new Event('change', { bubbles: true })); await flush()
  await click('.pay-btn-total'); await click('.pay-btn-add')
}
async function mount() {
  const pinia = createPinia(); setActivePinia(pinia)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  root = document.createElement('div'); document.body.append(root)
  app = createApp(PDVView).use(pinia).use(i18n)
  app.config.globalProperties.$tr = (text: string) => text
  app.mount(root); await flush()
}
beforeEach(() => {
  vi.useFakeTimers()
  mocks.getItems.mockResolvedValue({ items: [{ ...item }] })
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})
afterEach(() => { app?.unmount(); app = undefined; root?.remove(); vi.clearAllTimers(); vi.useRealTimers(); vi.resetAllMocks() })

describe('PDV asynchronous product selection', () => {
  it('keeps shared barcode matches selectable without adding a product automatically', async () => {
    const matches = [
      { ...item, id: 'shoe-8', name: 'Tênis QA 8', image_data: null, has_image: false },
      { ...item, id: 'shoe-9', name: 'Tênis QA 9', image_data: null, has_image: false },
    ]
    mocks.getByBarcode.mockResolvedValueOnce(matches)
    await mount(); await scan()
    expect(mocks.getByBarcode).toHaveBeenCalledWith('FIXTURE-CODE', false)
    expect(root.querySelectorAll('.pdv-result-row')).toHaveLength(2)
    expect(root.textContent).toContain('Tênis QA 8')
    expect(root.textContent).toContain('Tênis QA 9')
    expect(usePdvStore().cart).toEqual([])
    await click('.pdv-result-row')
    expect(usePdvStore().cart).toHaveLength(1)
    expect(usePdvStore().cart[0].item_id).toBe('shoe-8')
    expect(mocks.createSale).not.toHaveBeenCalled()
  })

  it('does not restore cached recent stock over a newer search snapshot when the row is clicked', async () => {
    await mount()
    mocks.getItems.mockResolvedValueOnce({ items: [{ ...item, current_stock: 0, stock_loja: 0 }] })
    await search('Fixture'); await click('.pdv-search-clear')
    expect(usePdvStore().availableStock(item.id, 'loja')).toBe(0)
    expect(root.querySelector<HTMLButtonElement>('.pdv-result-add')!.disabled).toBe(true)
    await click('.pdv-result-row')
    expect(usePdvStore().cart).toEqual([])
    expect(usePdvStore().availableStock(item.id, 'loja')).toBe(0)
    expect(mocks.createSale).not.toHaveBeenCalled()
  })

  it('discards a pending barcode result when the operator clears the cart', async () => {
    const barcode = deferred<InventoryItem[]>()
    mocks.getByBarcode.mockReturnValueOnce(barcode.promise)
    await mount(); await click('.pdv-result-row'); await scan()
    expect(mocks.getByBarcode).toHaveBeenCalledWith('FIXTURE-CODE', false)
    await click('.pdv-cart-clear')
    barcode.resolve([{ ...item, id: 'late-product', name: 'Produto atrasado' }]); await flush()
    expect(usePdvStore().cart).toEqual([])
    expect(root.textContent).not.toContain('Produto atrasado')
    expect(mocks.createSale).not.toHaveBeenCalled()
  })

  it('waits for the pending barcode selection before accepting checkout and still blocks duplicate submissions', async () => {
    const barcode = deferred<InventoryItem[]>(), checkout = deferred<PdvSaleResponse>()
    mocks.getByBarcode.mockReturnValueOnce(barcode.promise)
    mocks.createSale.mockReturnValueOnce(checkout.promise)
    await mount(); await preparePayment(); await scan()
    expect(root.querySelector('.pdv-search-loading')).not.toBeNull()
    expect(root.querySelector<HTMLButtonElement>('.pay-confirm-btn')!.disabled).toBe(true)
    await click('.pay-confirm-btn')
    expect(mocks.createSale).not.toHaveBeenCalled()
    barcode.resolve([{ ...item }]); await flush()
    expect(usePdvStore().cart[0]!.quantity).toBe(2)
    expect(root.querySelector<HTMLButtonElement>('.pay-confirm-btn')!.disabled).toBe(true)
    await click('.pay-btn-total'); await click('.pay-btn-add')
    const button = root.querySelector<HTMLButtonElement>('.pay-confirm-btn')!
    button.click(); button.click(); await flush()
    expect(mocks.createSale).toHaveBeenCalledTimes(1)
    expect(mocks.createSale.mock.calls[0]![0].items[0].quantity).toBe(2)
    checkout.resolve({ id: 'fixture-sale', items: [], payments: [] } as unknown as PdvSaleResponse); await flush()
    expect(usePdvStore().cart).toEqual([])
  })

  it('restores the recent list after a quick search cancelled its initial load', async () => {
    const initial = deferred<{ items: InventoryItem[] }>()
    mocks.getItems.mockReturnValueOnce(initial.promise)
    await mount(); await search('Fixture')
    await click('.pdv-search-clear')
    expect(mocks.getItems).toHaveBeenCalledTimes(3)
    expect(mocks.getItems.mock.calls[2]![0]).toMatchObject({ search: undefined, page_size: 8, sort_by: 'created_at' })
    expect(root.querySelector('.pdv-result-row')?.textContent).toContain('Produto sintético')
    initial.resolve({ items: [{ ...item, name: 'Resposta descartada' }] }); await flush()
    expect(root.textContent).not.toContain('Resposta descartada')
  })

  it('lets a newer text search cancel barcode selection without leaving checkout blocked', async () => {
    const barcode = deferred<InventoryItem[]>()
    mocks.getByBarcode.mockReturnValueOnce(barcode.promise)
    await mount(); await preparePayment(); await scan()
    await search('Outra busca')
    expect(root.querySelector<HTMLButtonElement>('.pay-confirm-btn')!.disabled).toBe(false)
    barcode.resolve([{ ...item, id: 'late-barcode', name: 'Código antigo' }]); await flush()
    expect(usePdvStore().cart).toHaveLength(1)
    expect(usePdvStore().cart[0]!.quantity).toBe(1)
    expect(root.textContent).not.toContain('Código antigo')
    expect(root.querySelector('.pdv-search-loading')).toBeNull()
    expect(mocks.createSale).not.toHaveBeenCalled()
  })
})
