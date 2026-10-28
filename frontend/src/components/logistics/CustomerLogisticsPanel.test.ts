import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { Cliente } from '@/services/api'
import type { CustomerLogistics } from '@/services/customerLogistics'
import CustomerLogisticsPanel from './CustomerLogisticsPanel.vue'

const api = vi.hoisted(() => ({ get: vi.fn(), findParcel: vi.fn(), link: vi.fn() }))
const mounted = vi.hoisted(() => ({ purchases: vi.fn(), prints: vi.fn() }))
vi.mock('@/services/customerLogistics', () => ({ customerLogisticsAPI: api }))
vi.mock('@/services/api', () => ({ default: { get: vi.fn() }, pedidosAPI: { getByNumber: vi.fn() } }))
vi.mock('./CustomerPurchasesHistory.vue', () => ({ default: { mounted: mounted.purchases, render: () => 'Compras QA' } }))
vi.mock('@/components/addresses/AddressUsageHistory.vue', () => ({ default: { mounted: mounted.prints, render: () => 'Impressões QA' } }))
vi.mock('@/components/clientes/CustomerHistoryAssociation.vue', async () => {
  const { h } = await import('vue')
  return { default: { emits: ['changed'], render() { return h('button', { class: 'association-result', onClick: () => (this as unknown as { $emit: (event: string) => void }).$emit('changed') }, 'Histórico associado QA') } } }
})
const customer = ref<Cliente>({ id: 'customer-one', nome: 'Pessoa sintética', ativo: true, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' })
const result = (code = 'QA123456789BR'): CustomerLogistics => ({ order_total: 0, shipment_total: 1, in_transit: 1, delivered: 0, orders: [], shipments: [{ id: 'parcel', codigo_rastreio: code, status: 'EM_TRANSITO', ativo: true, created_at: '2026-10-28T12:00:00Z' }] })
const changed = vi.fn()
let app: App | undefined, container: HTMLDivElement
const settle = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); await nextTick() }
function button(label: string) { return Array.from(container.querySelectorAll('button')).find(row => row.textContent?.trim() === label)! }
async function mount(owner = false) {
  const pinia = createPinia()
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }, { path: '/rastreamento', component: { render: () => null } }] })
  await router.push('/'); await router.isReady()
  app = createApp({ render: () => h(CustomerLogisticsPanel, { customer: customer.value, onChanged: changed }) })
    .use(pinia).use(router).use(createI18n({ legacy: false, locale: 'pt', messages: {} }))
  const auth = useAuthStore(pinia)
  auth.token = 'synthetic-session'
  if (owner) auth.user = { id: 'owner', email: 'lucas@eleven.com', role: 'ADMIN' } as typeof auth.user
  app.mount(container); await settle()
}
beforeEach(() => {
  customer.value = { id: 'customer-one', nome: 'Pessoa sintética', ativo: true, created_at: '2026-10-28T12:00:00Z', updated_at: '2026-10-28T12:00:00Z' }
  container = document.createElement('div'); document.body.append(container)
  api.get.mockResolvedValue(result()); api.link.mockResolvedValue(undefined)
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.resetAllMocks() })

describe('Customer history navigation', () => {
  it('loads each tab on first use, keeping visited pages mounted instead of fetching every detail on expand', async () => {
    await mount()
    expect(mounted.purchases).toHaveBeenCalledTimes(1)
    expect(mounted.prints).not.toHaveBeenCalled()
    expect(api.get).not.toHaveBeenCalled()
    button('Pedidos e pacotes').click(); await settle()
    expect(api.get).toHaveBeenCalledTimes(1)
    expect(container.textContent).toContain('QA123456789BR')
    button('Compras no PDV').click(); await settle()
    button('Pedidos e pacotes').click(); await settle()
    expect(api.get).toHaveBeenCalledTimes(1)
    button('Endereços e impressões').click(); await settle()
    expect(mounted.prints).toHaveBeenCalledTimes(1)
    button('Compras no PDV').click(); await settle()
    button('Endereços e impressões').click(); await settle()
    expect(mounted.purchases).toHaveBeenCalledTimes(1)
    expect(mounted.prints).toHaveBeenCalledTimes(1)
    expect(api.link).not.toHaveBeenCalled()
    expect(container.querySelector('.association-result')).toBeNull()
  })

  it('refreshes visited histories and the card after a reviewed association while keeping its result mounted', async () => {
    await mount(true)
    button('Pedidos e pacotes').click(); await settle()
    button('Endereços e impressões').click(); await settle()
    const notice = container.querySelector<HTMLButtonElement>('.association-result')!
    notice.click(); await settle()
    expect(changed).toHaveBeenCalledTimes(1)
    expect(container.querySelector('.association-result')).toBe(notice)
    expect(mounted.purchases).toHaveBeenCalledTimes(2)
    expect(mounted.prints).toHaveBeenCalledTimes(2)
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('discards stale logistics after changing customers and resets the tab', async () => {
    await mount()
    let finishOld!: (value: CustomerLogistics) => void
    api.get.mockImplementationOnce(() => new Promise(resolve => { finishOld = resolve }))
    button('Pedidos e pacotes').click(); await settle()
    customer.value = { ...customer.value, id: 'customer-two' }; await settle()
    expect(button('Compras no PDV').getAttribute('aria-pressed')).toBe('true')
    button('Pedidos e pacotes').click(); await settle()
    finishOld(result('OLD987654321BR')); await settle()
    expect(container.textContent).toContain('QA123456789BR')
    expect(container.textContent).not.toContain('OLD987654321BR')
    expect(api.get).toHaveBeenLastCalledWith('customer-two', 0, 0)
  })

  it('previews an existing parcel and links it only after explicit confirmation, then refreshes the card', async () => {
    await mount()
    button('Pedidos e pacotes').click(); await settle()
    const identifier = container.querySelector<HTMLInputElement>('.identifier input')!
    identifier.value = 'QA123456789BR'; identifier.dispatchEvent(new Event('input')); await settle()
    api.findParcel.mockResolvedValue({ ...result().shipments[0], destinatario: 'Pessoa sintética', cliente_id: null })
    container.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true })); await settle()
    expect(api.link).not.toHaveBeenCalled()
    expect(container.textContent).toContain('Vincular este cadastro a Pessoa sintética?')
    button('Confirmar vínculo').click(); await settle()
    expect(api.link).toHaveBeenCalledWith('customer-one', 'rastreamento', 'parcel')
    expect(changed).toHaveBeenCalledTimes(1)
    expect(api.get).toHaveBeenCalledTimes(2)
  })
})
