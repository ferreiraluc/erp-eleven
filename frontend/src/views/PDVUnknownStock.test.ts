import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import PDVView from './PDVView.vue'

const mocks = vi.hoisted(() => ({ getItems: vi.fn(), addItem: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItems: mocks.getItems } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { role: 'USER' } }) }))
vi.mock('@/stores/pdv', () => ({ usePdvStore: () => ({ cart: [], payments: [], total: 0, cartCount: 0, addItem: mocks.addItem }) }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ exchangeRates: { 'G$': 7500, 'R$': 5.5, EUR: 0.9 } }) }))
let app: App | undefined, container: HTMLDivElement
const item = { id: 'test', name: 'Fixture', sku_internal: 'SKU-1', sale_price: 100, current_stock: null, stock_loja: null, stock_deposito: 0 }
async function mountAndSearch() {
  container = document.createElement('div'); document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(PDVView).use(i18n)
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
    expect(mocks.addItem).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Nenhuma movimentação foi registrada')
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('Revisar stock')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('Review stock')
  })
  it('blocks a positive total with an unknown location but preserves the normal known-stock path', async () => {
    mocks.getItems.mockResolvedValueOnce({ items: [{ ...item, current_stock: 5, stock_loja: 5, stock_deposito: null }] })
    const { input } = await mountAndSearch()
    expect(container.querySelector('.pdv-result-stock')?.textContent).toContain('5')
    expect((container.querySelector('.pdv-result-add') as HTMLButtonElement).disabled).toBe(true)
    mocks.getItems.mockResolvedValueOnce({ items: [{ ...item, current_stock: 5, stock_loja: 5, stock_deposito: 0 }] })
    input.dispatchEvent(new Event('input', { bubbles: true })); await vi.advanceTimersByTimeAsync(300); await nextTick()
    expect((container.querySelector('.pdv-result-add') as HTMLButtonElement).disabled).toBe(false)
    ;(container.querySelector('.pdv-result-row') as HTMLElement).click(); await nextTick()
    expect(mocks.addItem).toHaveBeenCalledWith(expect.objectContaining({ item_id: item.id, location: 'loja' }))
  })
})
