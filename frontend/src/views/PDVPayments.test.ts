import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import i18n from '@/i18n'
import PDVView from './PDVView.vue'
import { usePdvStore } from '@/stores/pdv'
import { paymentMethods, paymentSymbol } from '@/services/pdvPayments'
const mocks = vi.hoisted(() => ({ rates: {} as Record<string, number>, getItems: vi.fn(), createSale: vi.fn() }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItems: mocks.getItems }, pdvAPI: { createSale: mocks.createSale } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ user: { id: 'test', role: 'ADMIN' } }) }))
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ exchangeRates: mocks.rates }) }))
let app: App | undefined, root: HTMLDivElement
async function tick() { await nextTick(); await Promise.resolve(); await nextTick() }
const input = (selector: string) => root.querySelector(selector) as HTMLInputElement
async function set(selector: string, value: string, event = 'input') { const el = input(selector); el.value = value; el.dispatchEvent(new Event(event, { bubbles: true })); await tick() }
async function method(value: string) { await set('.pay-select', value, 'change') }
const button = (selector: string) => root.querySelector(selector) as HTMLButtonElement
beforeEach(async () => {
  vi.useFakeTimers(); vi.clearAllMocks(); i18n.global.locale.value = 'pt'
  mocks.rates = reactive({ 'G$': 6500, 'R$': 5, EUR: .9 })
  mocks.getItems.mockResolvedValue({items: [{id:'one',name:'Produto sintético',sku_internal:'TEST',sale_price:100,sale_currency:'USD',stock_loja:5,stock_deposito:0,current_stock:5,is_active:true}]})
  const pinia = createPinia(); setActivePinia(pinia)
  usePdvStore().addItem({item_id:null,item_name:'Peça teste',item_sku:null,item_category:null,item_size:null,item_color:null,quantity:1,unit_price_gs:650000,original_price_gs:650000,original_price:100,sale_currency:'USD',image_data:null,discount_gs:0,is_avulso:true,location:'loja'})
  root = document.createElement('div'); document.body.append(root)
  app = createApp(PDVView).use(pinia).use(i18n); app.config.globalProperties.$tr = (text:string) => text
  app.mount(root); await tick()
})
afterEach(() => { app?.unmount(); root?.remove(); vi.clearAllTimers(); vi.useRealTimers(); i18n.global.locale.value = 'pt' })

it('offers exactly the requested methods and locks each amount to its currency', async () => {
  expect(Array.from(root.querySelectorAll('.pay-select option')).map(el => (el as HTMLOptionElement).value)).toEqual(paymentMethods.map(m => m.value))
  for (const m of paymentMethods) {
    await method(m.value)
    expect(root.querySelector('.pay-fixed-currency')?.textContent).toBe(paymentSymbol(m.currency))
    expect(input('.pay-amount-input').getAttribute('aria-label')).toContain(paymentSymbol(m.currency))
    expect(root.querySelector('.pay-select-sm')).toBeNull()
  }
  await method('pix_personal'); await set('.pay-amount-input','50'); await method('card_debit_py')
  expect(input('.pay-amount-input').value).toBe('0')
  expect(root.querySelector('.pay-rate-input')).toBeNull()
  expect(mocks.createSale).not.toHaveBeenCalled()
})

it('fills the remaining amount in reais, permits negotiated rates and keeps mixed payment snapshots', async () => {
  await method('pix_thais'); button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value)).toBe(500)
  await set('.pay-rate-input','1250'); await set('.pay-amount-input','100'); button('.pay-btn-add').click(); await tick()
  expect(root.querySelector('.pay-entry')?.textContent).toContain('R$ 100')
  expect(root.querySelector('.pay-entry')?.textContent).toContain('125.000')
  await method('cash_usd'); button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value)).toBe(80.77)
  mocks.rates['G$']=7000; await tick()
  expect(usePdvStore().total).toBe(700000)
  expect(root.querySelector('.pay-entry')?.textContent).toContain('125.000')
  expect(root.querySelector('.pdv-total-usd')?.textContent).toContain('R$ 500')
})

it('does not add invalid rates and requires a customer for fiado; USDT starts at the USD rate', async () => {
  await method('usdt')
  expect(input('.pay-rate-input').value).toBe('6500')
  await set('.pay-amount-input','10'); await set('.pay-rate-input','0')
  expect(button('.pay-btn-add').disabled).toBe(true)
  input('.pay-amount-input').dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); await tick()
  expect(root.querySelector('.pay-entry')).toBeNull()
  await method('fiado'); await set('.pay-amount-input','100')
  expect(button('.pay-btn-add').disabled).toBe(true)
  usePdvStore().clienteId='synthetic'; await tick()
  expect(button('.pay-btn-add').disabled).toBe(false)
})

it('shows product search and cart prices in G$, U$ and R$ and uses current exchange rates', async () => {
  await set('.pdv-search-input','Produto'); await vi.advanceTimersByTimeAsync(310); await tick()
  const price = root.querySelector('.pdv-result-price')?.textContent
  expect(price).toContain('U$ 100'); expect(price).toContain('G$ 650.000'); expect(price).toContain('R$ 500')
  expect(root.querySelector('.ci-gs-equiv')?.textContent).toContain('R$ 500')
  mocks.rates['R$']=5.5; await tick()
  expect(root.querySelector('.pdv-result-price')?.textContent).toContain('R$ 550')
  expect(root.querySelector('.pdv-total-usd')?.textContent).toContain('R$ 550')
})
