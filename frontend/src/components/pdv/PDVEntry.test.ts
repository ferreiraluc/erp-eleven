import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, defineComponent, h, nextTick, reactive, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import PDVAvulsoModal from './PDVAvulsoModal.vue'
import PDVCustomerPicker from './PDVCustomerPicker.vue'

const mocks = vi.hoisted(() => ({ searchCustomers: vi.fn(), selectCustomer: vi.fn(), auth: {} as any }))
vi.mock('@/services/api', () => ({ pdvAPI: mocks }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => mocks.auth }))
let app: App | undefined, container: HTMLDivElement
const fixture = { id: 'main-1', source: 'cadastro', nome: 'João Ávila', doc: '123.456.789-09', telefone: '+595972123456', ceps: ['85865-310'] }
const tick = async () => { await vi.advanceTimersByTimeAsync(260); await nextTick() }
function mount(component: any, props: any = {}) {
  container = document.createElement('div'); document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(component, props).use(i18n); app.mount(container)
  return i18n
}
async function set(selector: string, value: string, event = 'input') {
  const input = container.querySelector(selector) as HTMLInputElement
  input.value = value; input.dispatchEvent(new Event(event, { bubbles: true })); await nextTick()
}
beforeEach(() => {
  vi.useFakeTimers(); mocks.auth = reactive({ token: 'one', user: { id: 'one' } })
  mocks.searchCustomers.mockResolvedValue({ items: [fixture], has_more: false })
  mocks.selectCustomer.mockResolvedValue({ id: 'pdv-1', nome: fixture.nome })
})
afterEach(() => { app?.unmount(); container?.remove(); vi.clearAllTimers(); vi.useRealTimers(); vi.resetAllMocks() })

describe('manual item currency', () => {
  const rates = { PYG: 1, BRL: 1280, USD: 6400, EUR: 7000 }
  it.each([['PYG', 25], ['BRL', 32000], ['USD', 160000], ['EUR', 175000]])('converts %s while preserving its original price', async (currency, expected) => {
    const add = vi.fn()
    mount(PDVAvulsoModal, { rates, onAdd: add })
    await set('input[type=text]', 'Peça avulsa')
    await set('#avulso-currency', currency as string, 'change')
    await set('#avulso-price', '25')
    ;(container.querySelector('.avulso-btn-add') as HTMLButtonElement).click(); await nextTick()
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ original_price: 25, sale_currency: currency, unit_price_gs: expected, is_avulso: true }))
    if (currency !== 'PYG') expect(container.querySelector('.avulso-conversion')?.textContent).toContain('Equivalente por unidade')
  })
  it('uses decimal prices, switches preview currency, and never applies an unavailable rate as 1', async () => {
    const add = vi.fn()
    const i18n = mount(PDVAvulsoModal, { rates: { ...rates, EUR: 0 }, onAdd: add })
    await set('input[type=text]', 'Peça avulsa'); await set('#avulso-price', '12.50')
    await set('#avulso-currency', 'BRL', 'change')
    expect(container.querySelector('.avulso-conversion')?.textContent).toContain('16.000')
    await set('#avulso-currency', 'USD', 'change')
    expect(container.querySelector('.avulso-conversion')?.textContent).toContain('80.000')
    await set('#avulso-currency', 'EUR', 'change')
    expect((container.querySelector('.avulso-btn-add') as HTMLButtonElement).disabled).toBe(true)
    expect(container.textContent).toContain('Câmbio indisponível')
    ;(container.querySelector('#avulso-price') as HTMLInputElement).dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    expect(add).not.toHaveBeenCalled()
    i18n.global.locale.value = 'es'; await nextTick(); expect(container.textContent).toContain('Moneda del artículo')
    i18n.global.locale.value = 'en'; await nextTick(); expect(container.textContent).toContain('Item currency')
  })
})

describe('PDV customer picker', () => {
  function picker() {
    const id = ref<string | null>(null), name = ref<string | null>(null), busy = ref(false)
    const i18n = mount(defineComponent({ setup: () => () => h(PDVCustomerPicker, {
      customerId: id.value, customerName: name.value,
      'onUpdate:customerId': (v: string | null) => id.value = v,
      'onUpdate:customerName': (v: string | null) => name.value = v,
      onBusy: (v: boolean) => busy.value = v,
    }) }))
    return { id, name, busy, i18n }
  }
  it('selects an explicit result by keyboard and clears both IDs and names', async () => {
    const state = picker()
    await set('input', '85865310'); await tick()
    expect(container.textContent).toContain('João Ávila')
    expect(container.textContent).toContain('85865-310')
    expect(state.id.value).toBeNull()
    for (const key of ['ArrowDown', 'Enter']) (container.querySelector('input') as HTMLInputElement).dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }))
    await tick()
    expect(mocks.selectCustomer).toHaveBeenCalledWith({ id: 'main-1', source: 'cadastro' })
    expect(state.id.value).toBe('pdv-1'); expect(state.name.value).toBe('João Ávila')
    ;(container.querySelector('.customer-selected button') as HTMLButtonElement).click(); await nextTick()
    expect(state.id.value).toBeNull(); expect(state.name.value).toBeNull()
  })
  it('debounces search, discards stale responses and never treats a telephone as a name', async () => {
    let finish!: (value: any) => void
    mocks.searchCustomers.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    picker(); await set('input', 'João'); await tick()
    await set('input', '9999'); mocks.searchCustomers.mockResolvedValue({ items: [], has_more: false }); await tick()
    finish({ items: [fixture], has_more: false }); await tick()
    expect(container.textContent).not.toContain('João Ávila')
    expect(container.textContent).toContain('Nenhum cliente encontrado')
    expect(container.querySelector('.customer-name-only')).toBeNull()
  })
  it('requires an explicit action for a name-only sale and resets after checkout', async () => {
    const state = picker(); await set('input', 'Visitante'); await tick()
    expect(state.name.value).toBeNull()
    ;(container.querySelector('.customer-name-only') as HTMLButtonElement).click(); await nextTick()
    expect(state.name.value).toBe('Visitante'); expect(state.id.value).toBeNull()
    state.name.value = null; await nextTick()
    expect((container.querySelector('input') as HTMLInputElement).value).toBe('')
  })
  it('does not link an old session response and clears pending state on logout', async () => {
    let finish!: (value: any) => void
    mocks.selectCustomer.mockImplementation(() => new Promise(resolve => { finish = resolve }))
    const state = picker(); await set('input', 'João'); await tick()
    ;(container.querySelector('li button') as HTMLButtonElement).click(); await nextTick()
    expect(state.busy.value).toBe(true)
    mocks.auth.token = 'two'; await nextTick()
    finish({ id: 'stale', nome: fixture.nome }); await tick()
    expect(state.id.value).toBeNull(); expect(state.busy.value).toBe(false)
  })
  it('shows lookup and selection failures, preserving the search for a retry', async () => {
    mocks.searchCustomers.mockRejectedValueOnce(new Error('offline'))
    picker(); await set('input', 'João'); await tick()
    expect(container.textContent).toContain('Não foi possível buscar')
    await set('input', 'Joao'); await tick()
    mocks.selectCustomer.mockRejectedValueOnce({ response: { data: { detail: 'Confira o cadastro PDV.' } } })
    ;(container.querySelector('li button') as HTMLButtonElement).click(); await tick()
    expect(container.textContent).toContain('Confira o cadastro PDV.')
    expect((container.querySelector('input') as HTMLInputElement).disabled).toBe(false)
  })
})
