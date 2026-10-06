import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import AddressesView from '@/views/AddressesView.vue'
import { blankAddress } from './types'

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/services/api', () => ({ default: api }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: false }) }))
let app: App | undefined, container: HTMLDivElement
let catalogEmpty = false
const fixture = { id: 'fixture-address', label: 'Casa exemplo', data: { ...blankAddress('BR'), nome: 'Pessoa exemplo' }, active: true, version: 1 }
const flush = async () => { for (let n = 0; n < 6; n++) await Promise.resolve(); await nextTick() }

beforeEach(() => {
  vi.useFakeTimers()
  catalogEmpty = false
  container = document.createElement('div'); document.body.append(container)
  api.get.mockImplementation(async (url: string, options?: { params: Record<string, unknown> }) => {
    if (url.endsWith('/overview')) return { data: { addresses: catalogEmpty ? 0 : 1, statuses: {}, devices: [] } }
    if (url.endsWith('/addresses')) {
      const params = options!.params
      const empty = catalogEmpty || !!params.q || !!params.country || params.active === false || !!params.customer_id
      return { data: { total: empty ? 0 : 1, items: empty ? [] : [fixture] } }
    }
    if (url.endsWith('/senders') || url.endsWith('/layouts')) return { data: [] }
    if (url.endsWith('/status')) return { data: { availability: 'available', configured: true, environment: 'sandbox' } }
    throw new Error(`Unexpected request: ${url}`)
  })
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.clearAllTimers(); vi.useRealTimers(); vi.resetAllMocks() })

async function mount(query = '') {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/enderecos', component: { template: '<div />' } }, { path: '/dashboard', component: { template: '<div />' } }] })
  await router.push('/enderecos' + query); await router.isReady()
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(AddressesView).use(router).use(i18n)
  app.mount(container); await flush()
  return i18n
}
function addressRequests() { return api.get.mock.calls.filter(([url]) => url.endsWith('/addresses')) }

describe('Address search empty states', () => {
  it('distinguishes an unmatched search from onboarding, translates it and clears back to saved addresses', async () => {
    const i18n = await mount()
    const search = container.querySelector<HTMLInputElement>('.toolbar input')!
    search.value = 'zz-auditoria-inexistente'
    search.dispatchEvent(new Event('input', { bubbles: true }))
    container.querySelector('form.toolbar')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }))
    await flush()
    expect(addressRequests().at(-1)![1].params).toMatchObject({ q: 'zz-auditoria-inexistente', active: true, country: '', offset: 0 })
    for (const [locale, heading, clear] of [
      ['pt', 'Nenhum endereço encontrado', 'Limpar filtros'],
      ['es', 'No se encontraron direcciones', 'Limpiar filtros'],
      ['en', 'No addresses found', 'Clear filters'],
    ] as const) {
      i18n.global.locale.value = locale; await nextTick()
      expect(container.querySelector('.empty h3')?.textContent).toBe(heading)
      expect(container.querySelector('.empty button')?.textContent).toBe(clear)
    }
    expect(container.querySelector('.pagination span')?.textContent).toBe('0–0 of 0')
    container.querySelector<HTMLButtonElement>('.empty button')!.click(); await flush()
    expect(search.value).toBe('')
    expect(container.querySelector('.address-card')?.textContent).toContain(fixture.label)
    expect(container.querySelector('.pagination span')?.textContent).toBe('1–1 of 1')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('keeps the registration prompt for an empty unfiltered catalog', async () => {
    catalogEmpty = true
    await mount()
    expect(container.querySelector('.empty h3')?.textContent).toBe('Nenhum endereço aqui ainda')
    expect(container.querySelector('.empty button')?.textContent).toBe('Cadastrar endereço')
    expect(container.querySelector('.pagination span')?.textContent).toBe('0–0 de 0')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('applies country, archived and customer filters without changing their query semantics, then explicitly resets them', async () => {
    await mount('?customer_id=fixture-customer')
    const selects = container.querySelectorAll<HTMLSelectElement>('.toolbar select')
    selects[0]!.value = 'PY'; selects[0]!.dispatchEvent(new Event('change', { bubbles: true })); await flush()
    selects[1]!.selectedIndex = 1; selects[1]!.dispatchEvent(new Event('change', { bubbles: true })); await flush()
    expect(addressRequests().at(-1)![1].params).toMatchObject({ country: 'PY', active: false, customer_id: 'fixture-customer', offset: 0 })
    expect(container.querySelector('.empty h3')?.textContent).toBe('Nenhum endereço encontrado')
    container.querySelector<HTMLButtonElement>('.empty button')!.click(); await flush()
    expect(addressRequests().at(-1)![1].params).toEqual({ q: '', country: '', active: true, customer_id: undefined, offset: 0 })
    expect(container.querySelectorAll('.address-card')).toHaveLength(1)
    expect(api.post).not.toHaveBeenCalled()
  })
})
