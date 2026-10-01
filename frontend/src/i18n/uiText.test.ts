import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, type App } from 'vue'
import i18n, { setLocale } from './index'
import { uiText, uiLocale, uiNumber } from './uiText'
import catalog from '@/locales/uiText.json'
import pt from '@/locales/pt.json'
import es from '@/locales/es.json'
import en from '@/locales/en.json'
import FolgasCard from '@/components/FolgasCard.vue'
import ColorPicker from '@/components/ColorPicker.vue'
import PDVReceiptModal from '@/components/pdv/PDVReceiptModal.vue'
import ClienteFormModal from '@/components/clientes/ClienteFormModal.vue'
import type { PdvSaleResponse } from '@/services/api'
import { createPinia, setActivePinia } from 'pinia'
import { useCurrencyStore } from '@/stores/currency'

const { createCustomer } = vi.hoisted(() => ({ createCustomer: vi.fn(async (payload: unknown) => ({ ...(payload as object), id: 'customer-1' })) }))
vi.mock('@/services/api', () => ({ exchangeRateAPI: {}, clientesAPI: { create: createCustomer }, vendorsAPI: {
  getFolgasCalendario: vi.fn(async () => []),
  getEstatisticasResumo: vi.fn(async () => ({ vendedores: [] })),
  getAll: vi.fn(async () => []),
} }))

const moduleFiles = [
  ...['VendasView','FiadoView','DashboardView','VendorManagement','ExchangeRateManagement','PedidosView','RastreamentoView','PDVView','ClientesView','AssistantView'].map(name => `../views/${name}.vue`),
  ...['FolgasCard','FolgasCalendarAdvanced','RastreamentoCard','PedidoModal','PedidoDetailsModal','VendasImportCard','TagManagerModal','AnexosCarousel','PedidoCard','ColorPicker','clientes/ClienteFormModal','pdv/PDVAvulsoModal','pdv/PDVReceiptModal'].map(name => `../components/${name}.vue`),
  '../stores/currency.ts', '../stores/rastreamento.ts', '../utils/datetime.ts',
]
const sources = import.meta.glob(['../views/*.vue', '../components/**/*.vue', '../stores/*.ts', '../utils/datetime.ts'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>
const mounted: { app: App; element: HTMLElement }[] = []
afterEach(() => { for (const {app,element} of mounted.splice(0)) { app.unmount();element.remove() } setLocale('pt') })

function flatten(record: object, prefix = ''): Record<string,string> {
  return Object.fromEntries(Object.entries(record).flatMap(([key,value]) => typeof value === 'string' ? [[prefix+key,value]] : Object.entries(flatten(value,prefix+key+'.'))))
}

function mountTest(render: () => ReturnType<typeof h>) {
  const element = document.createElement('div'); document.body.append(element)
  const app = createApp({render}); app.use(i18n); app.config.globalProperties.$tr = uiText
  app.mount(element); mounted.push({app,element}); return element
}

describe('operational interface translations', () => {
  it('has PT, ES and EN for every explicit text with matching parameters', () => {
    for (const [source, translations] of Object.entries(catalog)) {
      expect(Object.keys(translations).sort(),source).toEqual(['en','es','pt'])
      for (const locale of ['pt','es','en'] as const) {
        expect(translations[locale].trim(),source).not.toBe('')
        expect(translations[locale].match(/\{\w+\}/g)?.sort() || [],source).toEqual(translations.pt.match(/\{\w+\}/g)?.sort() || [])
      }
    }
  })

  it('covers all explicit literal calls and existing translation keys in every covered module', () => {
    const locales = [flatten(pt),flatten(es),flatten(en)]
    for (const file of moduleFiles) {
      const source = sources[file]
      for (const match of source.matchAll(/(?:\$tr|uiText)\(\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)/g)) {
        const key = match[1][0] === '"' ? JSON.parse(match[1]) : match[1].slice(1,-1).replace(/\\(['"`\\])/g,'$1')
        expect((catalog as Record<string,unknown>)[key],file+': '+key).toBeDefined()
      }
      for (const match of source.matchAll(/\b\$?t\(\s*(['"])([^'"]+)\1/g)) {
        for (const locale of locales) expect(locale[match[2]],file+': '+match[2]).toBeDefined()
      }
    }
  })

  it('interpolates literal messages without translating or reprocessing customer input', () => {
    setLocale('en')
    const name = 'Cliente {1} <script>literal</script>'
    expect(uiText('{0} adicionado',{0:name})).toBe(`${name} added`)
    expect(uiText('Um texto sem tradução')).toBe('Um texto sem tradução')
    expect(uiText('Tem certeza que deseja remover o rastreamento {0}?',{0:'AB123456789BR'})).toBe('Are you sure you want to remove tracking AB123456789BR?')
  })

  it('switches numbers and locales without changing API values', () => {
    setLocale('pt'); expect(uiLocale()).toBe('pt-BR'); expect(uiNumber(1234.5)).toBe('1.234,50')
    setLocale('en'); expect(uiLocale()).toBe('en-US'); expect(uiNumber(1234.5)).toBe('1,234.50')
    setLocale('es'); expect(uiLocale()).toBe('es-PY'); expect(uiNumber(1234.5)).toBe('1.234,50')
    expect(uiNumber(null)).toBe('—'); expect(uiNumber(Number.NaN)).toBe('—')
  })

  it('updates the existing calendar card and weekday headings without a reload', async () => {
    setLocale('pt')
    const element = document.createElement('div'); document.body.append(element)
    const app = createApp({render:()=>h(FolgasCard)})
    app.use(i18n);app.config.globalProperties.$tr=uiText;app.mount(element);mounted.push({app,element})
    expect(element.textContent).toContain('Controle de Folgas')
    expect(element.querySelector('.mini-weekday')?.textContent?.trim()).toBe('D')
    setLocale('en'); await nextTick()
    expect(element.textContent).toContain(catalog['Controle de Folgas'].en)
    expect(element.querySelector('.mini-weekday')?.textContent?.trim()).toBe('S')
    const expected = new Date().toLocaleDateString('en-US',{month:'long',year:'numeric'})
    expect(element.textContent).toContain(expected)
    setLocale('es'); await nextTick()
    expect(element.textContent).toContain(catalog['Controle de Folgas'].es)
  })
  it('localizes currency names and display values while keeping codes and conversions stable', () => {
    setActivePinia(createPinia())
    const currency = useCurrencyStore()
    currency.updateExchangeRates({'G$':7500})
    setLocale('en');expect(currency.availableCurrencies.find(c=>c.code==='G$')?.name).toBe('Paraguayan guaraní')
    expect(currency.formatCurrency(1234.5,'USD')).toBe('$ 1,234.50')
    setLocale('pt');expect(currency.availableCurrencies.find(c=>c.code==='G$')?.name).toBe('Guarani paraguaio')
    expect(currency.formatCurrency(1234.5,'USD')).toBe('$ 1.234,50')
    expect(currency.convertFromUSD(2,'G$')).toBe(15000)
    expect(currency.availableCurrencies.map(c=>c.code)).toEqual(['USD','G$','R$','EUR'])
  })

  it('updates color labels while preserving the selected hex value', async () => {
    setLocale('pt')
    const element = mountTest(() => h(ColorPicker,{modelValue:'#3B82F6'}))
    expect(element.querySelector('.color-name')?.textContent).toBe('Azul')
    setLocale('en'); await nextTick()
    expect(element.querySelector('.color-name')?.textContent).toBe('Blue')
    expect(element.querySelector<HTMLInputElement>('.color-input')?.value).toBe('#3B82F6')
    setLocale('es'); await nextTick()
    expect(element.querySelector('.color-name')?.textContent).toBe('Azul')
  })

  it('updates receipt labels, payment labels and amounts without translating customer or product data', async () => {
    const sale: PdvSaleResponse = {
      id:'sale-12345678', vendedor_id:null, cliente_id:null, cliente_nome:'Cancelado',
      subtotal_gs:1234, desconto_gs:0, total_gs:1234, status:'completed', stock_applied:false, notas:null,
      created_at:'2026-09-30T15:00:00Z',
      items:[{id:'item-1',item_id:null,item_name:'Vermelho',item_sku:null,item_category:null,
        item_size:'M',item_color:'Azul',quantity:1,unit_price_gs:1234,original_price_gs:null,
        discount_gs:0,total_gs:1234,is_avulso:true,location:'LOJA'}],
      payments:[{id:'payment-1',method:'cash_gs',currency:'GS',amount_original:1234,exchange_rate:1,
        amount_gs:1234,cambista_id:null,reference:null,created_at:'2026-09-30T15:00:00Z'}],
    }
    setLocale('pt'); const element = mountTest(() => h(PDVReceiptModal,{sale}))
    expect(element.textContent).toContain('Dinheiro G$')
    setLocale('en'); await nextTick()
    expect(element.textContent).toContain('Cash G$')
    expect(element.textContent).toContain('G$ 1,234')
    expect(element.textContent).toContain('Thank you for your purchase!')
    expect(element.querySelector('.receipt-client')?.textContent).toContain('Cancelado')
    expect(element.querySelector('.receipt-item-name')?.textContent).toContain('Vermelho')
    expect(element.querySelector('.receipt-item-meta')?.textContent).toContain('Azul')
    expect(sale.payments[0].method).toBe('cash_gs')
    setLocale('es'); await nextTick()
    expect(element.textContent).toContain('Efectivo G$')
    expect(element.textContent).toContain('G$ 1.234')
  })

  it('keeps customer form values and submitted payload unchanged when the language switches', async () => {
    setLocale('pt'); const element = mountTest(() => h(ClienteFormModal,{isVisible:true}))
    const name = element.querySelector<HTMLInputElement>('input[type="text"]')!
    name.value = 'Pendente';name.dispatchEvent(new Event('input',{bubbles:true})); await nextTick()
    const address = element.querySelector<HTMLTextAreaElement>('textarea')!
    address.value = 'Rua Verde 123';address.dispatchEvent(new Event('input',{bubbles:true}))
    setLocale('en'); await nextTick()
    expect(element.querySelector('.modal-title')?.textContent).toBe('New customer')
    expect(name.value).toBe('Pendente');expect(address.value).toBe('Rua Verde 123')
    expect(address.placeholder).toContain('Paste or enter the full address here')
    element.querySelector('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))
    await nextTick()
    expect(createCustomer).toHaveBeenCalledWith(expect.objectContaining({nome:'Pendente',endereco:'Rua Verde 123',ativo:true}))
  })

})
