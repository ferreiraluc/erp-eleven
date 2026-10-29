import { chooseDropdown, openDropdown } from '@/test/dropdown'
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
vi.mock('@/stores/currency', () => ({ useCurrencyStore: () => ({ currentRates: {}, loadCurrentRates: vi.fn().mockResolvedValue(true), exchangeRates: mocks.rates }) }))
let app: App | undefined, root: HTMLDivElement, pinia: ReturnType<typeof createPinia>
async function tick() { await nextTick(); await Promise.resolve(); await nextTick() }
const input = (selector: string) => root.querySelector(selector) as HTMLInputElement
async function set(selector: string, value: string, event = 'input') { const el = input(selector); if (el.matches('.erp-dropdown')) { await chooseDropdown(el, value); await tick(); return } el.value = value; el.dispatchEvent(new Event(event, { bubbles: true })); await tick() }
async function method(value: string) { await set('.pay-select', value, 'change') }
const button = (selector: string) => root.querySelector(selector) as HTMLButtonElement
beforeEach(async () => {
  vi.useFakeTimers(); vi.clearAllMocks(); i18n.global.locale.value = 'pt'
  mocks.rates = reactive({ 'G$': 6500, 'R$': 5, EUR: .9 })
  mocks.getItems.mockResolvedValue({items: [{id:'one',name:'Produto sintético',sku_internal:'TEST',sale_price:100,sale_currency:'USD',stock_loja:5,stock_deposito:0,current_stock:5,is_active:true}]})
  pinia = createPinia(); setActivePinia(pinia)
  usePdvStore().addItem({item_id:null,item_name:'Peça teste',item_sku:null,item_category:null,item_size:null,item_color:null,quantity:1,unit_price_gs:650000,original_price_gs:650000,original_price:100,sale_currency:'USD',image_data:null,discount_gs:0,is_avulso:true,location:'loja'})
  root = document.createElement('div'); document.body.append(root)
  app = createApp(PDVView).use(pinia).use(i18n); app.config.globalProperties.$tr = (text:string) => text
  app.mount(root); await tick()
})
afterEach(() => { app?.unmount(); root?.remove(); vi.clearAllTimers(); vi.useRealTimers(); i18n.global.locale.value = 'pt' })

it('offers exactly the requested methods and locks each amount to its currency', async () => {
  expect((await openDropdown(root.querySelector('.pay-select'))).map(el => el.value)).toEqual(paymentMethods.map(m => m.value))
  for (const m of paymentMethods) {
    await method(m.value)
    expect(root.querySelector('.pay-input-wrap .pay-currency-prefix')?.textContent).toBe(paymentSymbol(m.currency))
    expect(root.querySelector('.pay-cash-currency')).toBeNull()
    expect(root.querySelector('.pay-fixed-currency')).toBeNull()
    expect(input('.pay-amount-input').getAttribute('aria-label')).toContain(paymentSymbol(m.currency))
    expect(root.querySelector('.pay-select-sm')).toBeNull()
  }
  await method('pix_personal'); await set('.pay-amount-input','50'); await method('card_debit_py')
  expect(input('.pay-amount-input').value).toBe('')
  expect(root.querySelector('.pay-rate-input')).toBeNull()
  expect(mocks.createSale).not.toHaveBeenCalled()
})

it('fills the remaining amount in reais, permits negotiated rates and keeps mixed payment snapshots', async () => {
  await method('pix_thais'); button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(500)
  await set('.pay-rate-input','1250'); await set('.pay-amount-input','100'); button('.pay-btn-add').click(); await tick()
  expect(root.querySelector('.pay-entry')?.textContent).toContain('R$ 100')
  expect(root.querySelector('.pay-entry')?.textContent).toContain('125.000')
  await method('cash_usd'); button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(80.77)
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


it('updates prices while typing comma decimals, changes currency and keeps removal beside the inputs', async () => {
  const price=input('.pdv-ci-price');price.focus()
  await set('.pdv-ci-price','80,50')
  expect(price.value).toBe('80,50')
  expect(usePdvStore().total).toBe(523250)
  await set('.pdv-ci-currency','BRL','change')
  expect(usePdvStore().cart[0].sale_currency).toBe('BRL')
  expect(usePdvStore().cart[0].original_price).toBe(402.5)
  await set('.pdv-ci-price','')
  expect(button('.pay-confirm-btn').disabled).toBe(true)
  await set('.pdv-ci-price','10,25')
  expect(usePdvStore().total).toBe(13325)
  expect(root.querySelector('.pdv-ci-controls .pdv-ci-remove')).not.toBeNull()
  await method('cash_brl')
  expect(root.querySelector('.pay-select')?.textContent).toContain('Dinheiro R$')
  await set('.pay-amount-input','10,25')
  expect(root.querySelector('.pay-converted')?.textContent).toContain('13.325')
  expect(mocks.createSale).not.toHaveBeenCalled()
})

it('shows a bounded recent list without original photos and ignores late search responses', async () => {
  expect(mocks.getItems).toHaveBeenCalledWith(expect.objectContaining({page_size:8,sort_by:'created_at',include_images:false}),expect.any(AbortSignal))
  expect(root.textContent).toContain('Produtos recentes')
  let finish!: (value:unknown)=>void
  mocks.getItems.mockReturnValueOnce(new Promise(resolve=>{finish=resolve}))
  await set('.pdv-search-input','old');await vi.advanceTimersByTimeAsync(300)
  await set('.pdv-search-input','new');await vi.advanceTimersByTimeAsync(300)
  finish({items:[{id:'old',name:'Stale result'}]});await tick()
  expect(root.textContent).not.toContain('Stale result')
})

it('does not open or retain the input keyboard when Total, Add or Confirm are clicked', async () => {
  const amount = input('.pay-amount-input')
  button('.pay-btn-total').click(); await tick()
  expect(document.activeElement).not.toBe(amount)
  amount.focus(); button('.pay-btn-total').click(); await tick()
  expect(document.activeElement).not.toBe(amount)
  expect(Number(amount.value.replace(',', '.'))).toBe(100)
  amount.focus(); button('.pay-btn-add').click(); await tick()
  expect(document.activeElement).not.toBe(amount)
  expect(root.querySelectorAll('.pay-entry')).toHaveLength(1)
  mocks.createSale.mockRejectedValueOnce({ response: { status: 409, data: { detail: 'Conferir venda' } } })
  input('.pdv-ci-price').focus(); button('.pay-confirm-btn').click(); await tick()
  expect(document.activeElement?.tagName).not.toBe('INPUT')
  expect(mocks.createSale).toHaveBeenCalledOnce()
  expect(usePdvStore().cart).toHaveLength(1)
})

it('still accepts explicit typing, Enter to add a payment, and the F5 keyboard shortcut', async () => {
  const amount = input('.pay-amount-input'); amount.focus()
  await set('.pay-amount-input','100')
  amount.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',bubbles:true})); await tick()
  expect(root.querySelectorAll('.pay-entry')).toHaveLength(1)
  expect(document.activeElement).toBe(amount)
  amount.blur()
  document.dispatchEvent(new KeyboardEvent('keydown',{key:'F5',bubbles:true})); await tick()
  expect(document.activeElement).toBe(amount)
  expect(mocks.createSale).not.toHaveBeenCalled()
})

it('reloads products after checkout and does not offer old stock while the response is pending', async () => {
  button('.pay-btn-total').click(); await tick(); button('.pay-btn-add').click(); await tick()
  let finish!: (value: unknown) => void
  mocks.getItems.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
  mocks.createSale.mockResolvedValueOnce({id:'completed-fixture',vendedor_id:'test',items:[],payments:[],subtotal_gs:650000,desconto_gs:0,total_gs:650000,status:'completed',created_at:'2026-10-12T12:00:00Z'})
  button('.pay-confirm-btn').click(); await vi.advanceTimersByTimeAsync(0); await tick()
  expect(usePdvStore().cart).toEqual([])
  expect(root.querySelectorAll('.pdv-result-row')).toHaveLength(0)
  expect(root.querySelector('.pdv-search-loading')).not.toBeNull()
  finish({items:[{id:'one',name:'Produto sintético',sale_price:'100.00',sale_currency:'USD',stock_loja:0,stock_deposito:0,current_stock:0,is_active:true}]})
  await tick()
  expect(root.querySelector('.pdv-result-stock')?.textContent).toContain('Disponível: 0')
  expect(button('.pdv-result-add').disabled).toBe(true)
  expect(root.querySelector('.pdv-price-orig')?.textContent).toBe('U$ 100')
})


it('edits the discount below the rate and before Paid, recalculating the outstanding amount', async () => {
  const rate = root.querySelector('.pay-rate-row')!, discount = root.querySelector('.pay-discount-row')!, paid = root.querySelector('.pay-summary-inline')!
  expect(rate.compareDocumentPosition(discount) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  expect(discount.compareDocumentPosition(paid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  await set('.pay-discount-input', '65000')
  expect(usePdvStore().total).toBe(585000)
  button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value)).toBe(90)
  expect(mocks.createSale).not.toHaveBeenCalled()
})

async function setRoundingExample() {
  mocks.rates['G$'] = 6000
  await tick()
  const item = usePdvStore().cart[0]
  item.unit_price_gs = 2571450
  item.original_price_gs = 2571450
  item.original_price = 428.575
  await tick()
}

it('closes a Total payment without artificial change and restores the draft after navigating away', async () => {
  await setRoundingExample()
  button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(428.58)
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().total).toBe(2571480)
  expect(root.querySelector('.pay-troco')).toBeNull()
  expect(usePdvStore().payments).toHaveLength(1)

  app?.unmount()
  app = createApp(PDVView).use(pinia).use(i18n)
  app.config.globalProperties.$tr = (text: string) => text
  app.mount(root); await tick()
  expect(root.querySelectorAll('.pay-entry')).toHaveLength(1)
  expect(root.querySelector('.pay-troco')).toBeNull()
  button('.pay-entry-remove').click(); await tick()
  expect(usePdvStore().total).toBe(2571450)
  expect(usePdvStore().payments).toHaveLength(0)
})

it('rounds a manually entered noncash final amount but preserves genuine cash change', async () => {
  await setRoundingExample()
  await method('pix_personal')
  await set('.pay-amount-input', '2142,88')
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().total).toBe(2571456)
  expect(root.querySelector('.pay-troco')).toBeNull()
  button('.pay-entry-remove').click(); await tick()
  expect(usePdvStore().total).toBe(2571450)

  await method('cash_usd')
  await set('.pay-amount-input', '428,58')
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().total).toBe(2571450)
  expect(root.querySelector('.pay-troco')?.textContent).toContain('30')
})

it('uses the smallest cash cent when the G$ remainder is less than half a foreign cent', async () => {
  mocks.rates['G$'] = 6000; await tick()
  usePdvStore().cart[0].unit_price_gs = 20
  await tick()
  button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(0.01)
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().total).toBe(20)
  expect(root.querySelector('.pay-troco')?.textContent).toContain('40')
})

it('blocks noncash overpayment before checkout and tolerates rates changing during checkout', async () => {
  await setRoundingExample()
  button('.pay-btn-total').click(); await tick()
  button('.pay-btn-add').click(); await tick()
  usePdvStore().loading = true
  mocks.rates['G$'] = 7000
  await tick()
  usePdvStore().loading = false
  await tick()
  expect(usePdvStore().cart[0].unit_price_gs).toBe(Math.round(428.575 * 7000))

  button('.pay-entry-remove').click(); await tick()
  await method('pix_personal')
  await set('.pay-amount-input', '3000')
  button('.pay-btn-add').click(); await tick()
  expect(root.querySelector('.pay-validation[role="alert"]')?.textContent).toContain('dinheiro')
  expect(button('.pay-confirm-btn').disabled).toBe(true)
})

it.each(['card_credit_py','card_debit_py'])('grosses up %s by dividing by .94 without changing goods, and submits both amounts', async (selected) => {
  mocks.rates['G$'] = 5850; await tick()
  await set('.pdv-ci-price', '80')
  await method(selected)
  expect(root.querySelector('.pay-card-preview')?.textContent).toContain('497.873')
  expect(mocks.rates['G$']).toBe(5850)
  button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(497873)
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().total).toBe(468000)
  expect(usePdvStore().payments[0]).toMatchObject({amount_original:497873,amount_gs:468000,card_fee_gs:29873,card_fee_percent:6,exchange_rate:1})
  expect(root.querySelector('.pay-summary-troco')).toBeNull()
  expect(button('.pay-confirm-btn').disabled).toBe(false)
  expect(root.querySelector('.pay-card-summary')?.textContent).toContain('85,11')
  mocks.createSale.mockRejectedValueOnce({response:{status:409,data:{detail:'Synthetic validation'}}})
  button('.pay-confirm-btn').click(); await tick()
  expect(mocks.createSale).toHaveBeenCalledWith(expect.objectContaining({payments:[expect.objectContaining({amount_gs:468000,amount_original:497873,card_fee_gs:29873,card_fee_percent:6})]}))
})

it('applies the charge only to the card portion and removes it with the payment', async () => {
  mocks.rates['G$'] = 5850; await tick(); await set('.pdv-ci-price','80')
  await method('cash_usd'); await set('.pay-amount-input','40'); button('.pay-btn-add').click(); await tick()
  await method('card_credit_py'); button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(248937)
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().total).toBe(468000)
  expect(usePdvStore().payments[1]).toMatchObject({amount_original:248937,amount_gs:234000,card_fee_gs:14937})
  root.querySelectorAll<HTMLButtonElement>('.pay-entry-remove')[1].click(); await tick()
  expect(usePdvStore().payments).toHaveLength(1)
  expect(root.querySelector('.pay-card-summary')).toBeNull()
  await method('qr_py'); button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(234000)
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().payments[1].card_fee_gs || 0).toBe(0)
})

it('uses net value for a manual partial card charge, rejects fractional guaranis and never repeats the fee', async () => {
  await method('card_debit_py'); await set('.pay-amount-input','200000,50')
  expect(button('.pay-btn-add').disabled).toBe(true)
  await set('.pay-amount-input','200000'); button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().payments[0]).toMatchObject({amount_gs:188000,card_fee_gs:12000})
  await method('cash_gs'); button('.pay-btn-total').click(); await tick()
  expect(Number(input('.pay-amount-input').value.replace(',', '.'))).toBe(462000)
  button('.pay-btn-add').click(); await tick()
  expect(usePdvStore().total).toBe(650000)
  expect(usePdvStore().payments.reduce((sum,p)=>sum+(p.card_fee_gs||0),0)).toBe(12000)
})
