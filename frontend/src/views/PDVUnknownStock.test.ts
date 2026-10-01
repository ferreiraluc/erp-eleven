import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import PDVView from './PDVView.vue'
import { createPinia } from 'pinia'
import { usePdvStore } from '@/stores/pdv'

const mocks = vi.hoisted(() => ({ getItems: vi.fn(), createSale: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItems: mocks.getItems }, pdvAPI: { createSale: mocks.createSale } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { role: 'USER' } }) }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ exchangeRates: { 'G$': 7500, 'R$': 5.5, EUR: 0.9 } }) }))
let app: App | undefined, container: HTMLDivElement
const item = { id: 'test', name: 'Fixture', sku_internal: 'SKU-1', sale_price: 100, current_stock: null, stock_loja: null, stock_deposito: 0 }
async function mountAndSearch() {
  container = document.createElement('div'); document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(PDVView).use(createPinia()).use(i18n)
  app.config.globalProperties.$tr = (text: string) => text
  app.mount(container); await nextTick()
  const input = container.querySelector('.pdv-search-input') as HTMLInputElement
  input.value = 'Fixture'; input.dispatchEvent(new Event('input', { bubbles: true }))
  await vi.advanceTimersByTimeAsync(300); await nextTick()
  return { input, i18n }
}
beforeEach(() => { vi.useFakeTimers(); mocks.getItems.mockResolvedValue({ items: [item] }) })
afterEach(() => { app?.unmount(); container?.remove(); vi.clearAllTimers(); vi.useRealTimers(); vi.resetAllMocks() })
describe('PDV with missing stock', () => {
  it('shows missing stock and blocks both click and Enter without adding an unknown item to the cart', async () => {
    const { input, i18n } = await mountAndSearch()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('—')
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('Revisar estoque')
    expect((container.querySelector('.pdv-result-add') as HTMLButtonElement).disabled).toBe(true)
    ;(container.querySelector('.pdv-result-row') as HTMLElement).click(); await nextTick()
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true })); await nextTick()
    expect(usePdvStore().cart).toEqual([])
    expect(container.textContent).toContain('Nenhuma movimentação foi registrada')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('Revisar stock')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('Review stock')
  })
  it('blocks a positive total with an unknown location but preserves the normal known-stock path', async () => {
    mocks.getItems.mockResolvedValueOnce({ items: [{ ...item, current_stock: 5, stock_loja: 5, stock_deposito: null }] })
    const { input } = await mountAndSearch()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('—')
    expect((container.querySelector('.pdv-result-add') as HTMLButtonElement).disabled).toBe(true)
    mocks.getItems.mockResolvedValueOnce({ items: [{ ...item, current_stock: 5, stock_loja: 5, stock_deposito: 0 }] })
    input.dispatchEvent(new Event('input', { bubbles: true })); await vi.advanceTimersByTimeAsync(300); await nextTick()
    expect((container.querySelector('.pdv-result-add') as HTMLButtonElement).disabled).toBe(false)
    ;(container.querySelector('.pdv-result-row') as HTMLElement).click(); await nextTick()
    expect(usePdvStore().cart[0]).toMatchObject({ item_id: item.id, location: 'loja', quantity: 1 })
  })
})


describe('PDV quantity and checkout UI', () => {
  const known = { ...item, current_stock: 3, stock_loja: 1, stock_deposito: 2, is_active: true }
  function click(selector: string) { (container.querySelector(selector) as HTMLElement).click() }
  async function addKnown() {
    mocks.getItems.mockResolvedValueOnce({ items: [known] })
    const result = await mountAndSearch(); click('.pdv-result-row'); await nextTick(); return result
  }
  async function pay() {
    click('.pay-btn-total'); await nextTick(); click('.pay-btn-add'); await nextTick()
  }
  it('rejects invalid typed quantities without changing them or silently changing the accepted line', async () => {
    const { i18n } = await addKnown()
    const input = container.querySelector('.qty-input') as HTMLInputElement
    input.value = '1.5'; input.dispatchEvent(new Event('input', { bubbles: true })); input.dispatchEvent(new Event('change', { bubbles: true }))
    await nextTick()
    expect(input.value).toBe('1.5'); expect(usePdvStore().cart[0].quantity).toBe(1)
    expect(container.querySelector('.pdv-quantity-error')?.textContent).toContain('quantidade inteira')
    expect((container.querySelector('.pay-confirm-btn') as HTMLButtonElement).disabled).toBe(true)
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.querySelector('.pdv-quantity-error')?.textContent).toContain('cantidad entera')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('.pdv-quantity-error')?.textContent).toContain('whole quantity')
  })
  it('shows stock local and requires an explicit local choice instead of overflowing the store balance', async () => {
    const { input } = await addKnown()
    mocks.getItems.mockResolvedValue({ items: [known] })
    input.value = 'Fixture'; input.dispatchEvent(new Event('input', { bubbles: true }))
    await vi.advanceTimersByTimeAsync(300); await nextTick()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('Disponível: 0')
    expect((container.querySelector('.pdv-result-add') as HTMLButtonElement).disabled).toBe(true)
    const select = container.querySelector('.pdv-stock-location select') as HTMLSelectElement
    expect(select.closest('[aria-disabled="true"]')).toBeNull()
    expect(select.disabled).toBe(false)
    expect(select.value).toBe('loja')
    select.value = 'deposito'; select.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('Disponível: 2')
    click('.pdv-result-row'); await nextTick()
    expect(usePdvStore().cart.map(line => line.location)).toEqual(['loja', 'deposito'])
  })
  it('keeps payments/cart after409 and shows a readable422 without automatic retry', async () => {
    mocks.createSale.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Saldo insuficiente' } } })
    await addKnown(); await pay(); click('.pay-confirm-btn'); await vi.advanceTimersByTimeAsync(1); await nextTick()
    expect(container.querySelector('.pdv-checkout-error')?.textContent).toContain('Saldo insuficiente')
    expect(usePdvStore().cart).toHaveLength(1); expect(usePdvStore().payments).toHaveLength(1)
    expect(container.querySelectorAll('.pay-entry')).toHaveLength(1); expect(mocks.createSale).toHaveBeenCalledTimes(1)
    mocks.createSale.mockRejectedValueOnce({ response: { status: 422, data: { detail: [{ loc: ['body', 'items', 0, 'quantity'], msg: 'Must be positive' }] } } })
    click('.pay-confirm-btn'); await vi.advanceTimersByTimeAsync(1); await nextTick()
    expect(container.querySelector('.pdv-checkout-error')?.textContent).toContain('Revise os campos')
    expect(container.textContent).not.toContain('[object Object]')
  })
  it('blocks repeat checkout after a timeout and keeps a persistent translated warning', async () => {
    mocks.createSale.mockRejectedValue(new Error('timeout'))
    const { i18n } = await addKnown(); await pay(); click('.pay-confirm-btn'); await vi.advanceTimersByTimeAsync(1); await nextTick()
    expect(container.querySelector('.pdv-checkout-error')?.textContent).toContain('A venda pode ter sido registrada')
    expect((container.querySelector('.pay-confirm-btn') as HTMLButtonElement).disabled).toBe(true)
    click('.pay-confirm-btn'); await nextTick(); expect(mocks.createSale).toHaveBeenCalledTimes(1)
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('.pdv-checkout-error')?.textContent).toContain('sale may have been recorded')
    expect(usePdvStore().cart).toHaveLength(1); expect(usePdvStore().payments).toHaveLength(1)
  })
  it('reports a failed search without offering a not-found manual product flow', async () => {
    mocks.getItems.mockRejectedValueOnce(new Error('offline'))
    await mountAndSearch()
    expect(container.querySelector('.pdv-search-error')?.textContent).toContain('Não foi possível consultar')
    expect(container.querySelector('.pdv-btn-avulso')).toBeNull()
    expect(container.querySelector('.pdv-result-avulso')).toBeNull()
  })
})


describe('PDV incomplete prices', () => {
  it('renders a missing USD price and its conversion as unknown instead of crashing or showing zero', async () => {
    mocks.getItems.mockResolvedValueOnce({ items: [{ ...item, current_stock: 2, stock_loja: 2, stock_deposito: 0, sale_price: null, sale_currency: 'USD' }] })
    await mountAndSearch()
    expect(container.querySelector('.pdv-price-orig')?.textContent).toBe('U$ —')
    expect(container.querySelector('.pdv-price-gs')?.textContent).toBe('≈ G$ —')
    expect(container.querySelector('.pdv-search-loading')).toBeNull()
    expect(container.querySelector('.pdv-result-row')).not.toBeNull()
  })
})
