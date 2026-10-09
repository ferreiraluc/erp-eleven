import { afterEach, beforeEach, expect, it } from 'vitest'
import { createApp, nextTick, reactive, type App } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import SaleEditForm from './SaleEditForm.vue'
import i18n from '@/i18n'
import { useCurrencyStore } from '@/stores/currency'
import type { PdvSaleCreate } from '@/services/api'
let app: App, root: HTMLDivElement, model: PdvSaleCreate
beforeEach(async () => {
  const pinia = createPinia(); setActivePinia(pinia)
  useCurrencyStore().updateExchangeRates({'G$':6500,'R$':5,EUR:.9})
  model = reactive({items:[],desconto_gs:0,payments:[{method:'card',currency:'USD',amount_original:100,exchange_rate:6500,amount_gs:650000}]})
  root=document.createElement('div'); document.body.append(root)
  app=createApp(SaleEditForm,{modelValue:model,sellers:[]}).use(pinia).use(i18n); app.mount(root); await nextTick()
})
afterEach(() => { app.unmount(); root.remove(); i18n.global.locale.value='pt' })
it('keeps legacy currency untouched until a current method is explicitly chosen', async () => {
  expect(root.textContent).toContain('Cartão (antigo)')
  const amount = root.querySelector('article input[type=number]') as HTMLInputElement
  expect(amount.disabled).toBe(true); expect(model.payments[0].amount_original).toBe(100)
  const select = root.querySelector('article select') as HTMLSelectElement
  select.value='pix_thais'; select.dispatchEvent(new Event('change',{bubbles:true})); await nextTick()
  expect(model.payments[0]).toMatchObject({method:'pix_thais',currency:'BRL',amount_original:0,amount_gs:0,exchange_rate:1300})
  expect(root.querySelector('article input[readonly]')?.getAttribute('readonly')).not.toBeNull()
  amount.value='100'; amount.dispatchEvent(new Event('input',{bubbles:true})); await nextTick()
  expect(model.payments[0].amount_gs).toBe(130000)
  select.value='card_credit_py'; select.dispatchEvent(new Event('change',{bubbles:true})); await nextTick()
  expect(model.payments[0]).toMatchObject({currency:'GS',exchange_rate:1,amount_original:0,amount_gs:0})
  expect((root.querySelectorAll('article input[type=number]')[1] as HTMLInputElement).disabled).toBe(true)
})
it('translates the new method labels and retains proprietary names', async () => {
  i18n.global.locale.value='es'; await nextTick()
  expect(root.textContent).toContain('Tarjeta de crédito PY'); expect(root.textContent).toContain('MaquinaThais')
  i18n.global.locale.value='en'; await nextTick()
  expect(root.textContent).toContain('PY credit card'); expect(root.textContent).toContain('On account (credit)')
})
