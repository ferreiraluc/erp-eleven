import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import FreightAvailability from './FreightAvailability.vue'
import AddressesView from '@/views/AddressesView.vue'
import { blankAddress } from './types'

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('@/services/api', () => ({ default: api }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: false }) }))
const cpfError = 'CPF/CNPJ do destinatário inválido. Confira os dígitos com o titular e corrija o endereço; nenhum pagamento foi realizado.'
const states = {
  unavailable: ['Emissão de etiquetas temporariamente fora do ar.', 'Emisión de etiquetas temporalmente fuera de servicio.', 'Label issuance is temporarily unavailable.'],
  unknown: ['Não foi possível verificar a integração agora.', 'No se pudo verificar la integración.', 'The integration could not be checked.'],
  configuration: ['Confira o token, o contato técnico', 'Revise el token, contacto técnico', 'Check the SuperFrete token, technical contact'],
  available: ['A SuperFrete voltou a responder.', 'SuperFrete vuelve a responder.', 'SuperFrete is responding again.'],
}
let app: App | undefined, container: HTMLDivElement
const locales = ['pt', 'es', 'en'] as const
const translation = () => createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
const flush = async () => { for (let n = 0; n < 6; n++) await Promise.resolve(); await nextTick() }
const statusResponse = (availability: string) => ({ data: { availability, configured: availability !== 'configuration', environment: 'sandbox' } })
let status: () => Promise<ReturnType<typeof statusResponse>>
let orders: unknown[]
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(r => { resolve = r }); return { promise, resolve } }

beforeEach(() => {
  vi.useFakeTimers()
  container = document.createElement('div'); document.body.append(container)
  status = async () => statusResponse('available'); orders = []
  api.get.mockImplementation(async (url: string) => {
    if (url.endsWith('/overview')) return { data: { addresses: 1, statuses: {}, devices: [] } }
    if (url.endsWith('/addresses')) return { data: { total: 1, items: [{ id: 'address-fixture', label: 'Fixture', data: { ...blankAddress('BR'), nome: 'Pessoa fixture' }, active: true, version: 1 }] } }
    if (url.endsWith('/senders')) return { data: [] }
    if (url.endsWith('/layouts')) return { data: [] }
    if (url.endsWith('/status')) return status()
    if (url.endsWith('/orders')) return { data: { total: orders.length, items: orders } }
    throw new Error(`Unexpected request: ${url}`)
  })
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.clearAllTimers(); vi.useRealTimers(); vi.resetAllMocks() })

async function mountView(tab = 'freight') {
  const router = createRouter({ history: createMemoryHistory(), routes: [
    { path: '/enderecos', component: { template: '<div />' } }, { path: '/dashboard', component: { template: '<div />' } },
  ] })
  await router.push(`/enderecos?tab=${tab}`); await router.isReady()
  const i18n = translation()
  app = createApp(AddressesView).use(router).use(i18n); app.mount(container); await flush()
  return { i18n, router }
}

describe('SuperFrete availability copy', () => {
  it.each(Object.keys(states) as (keyof typeof states)[])('translates %s reactively and distinguishes accessible status from configuration', async availability => {
    const props = ref({ availability, restored: true })
    const i18n = translation()
    app = createApp({ setup: () => () => h(FreightAvailability, props.value) }).use(i18n)
    app.mount(container); await nextTick()
    for (const [index, locale] of locales.entries()) {
      i18n.global.locale.value = locale; await nextTick()
      expect(container.textContent).toContain(states[availability][index])
      expect(container.querySelector(availability === 'configuration' ? '[role="alert"]' : '[role="status"]')).not.toBeNull()
    }
    props.value = { availability: 'available', restored: false }; await nextTick()
    expect(container.textContent).toBe('')
  })

  it('keeps a failed first check unknown instead of falsely reporting missing configuration', async () => {
    status = async () => { throw new Error('offline') }
    const { i18n } = await mountView()
    for (const [index, locale] of locales.entries()) {
      i18n.global.locale.value = locale; await nextTick()
      expect(container.querySelector('.freight-status')?.textContent).toContain(states.unknown[index])
      expect(container.textContent).not.toContain(['Configuração pendente', 'Configuración pendiente', 'Configuration pending'][index])
      expect(container.textContent).not.toContain(['A integração precisa do token', 'La integración necesita el token', 'The integration needs the token'][index])
    }
    expect(api.post).not.toHaveBeenCalled()
  })

  it('does not let a delayed old outage overwrite a newer successful check', async () => {
    const first = deferred<ReturnType<typeof statusResponse>>()
    let calls = 0
    status = () => ++calls === 1 ? first.promise : Promise.resolve(statusResponse('available'))
    await mountView()
    first.resolve(statusResponse('unavailable')); await flush()
    expect(container.querySelector('.freight-status')).toBeNull()
    expect(api.post).not.toHaveBeenCalled()
  })

  it('announces recovery after an outage and polls without buying or printing', async () => {
    status = async () => statusResponse('unavailable')
    const { i18n } = await mountView()
    expect(container.querySelector('.freight-status')?.textContent).toContain(states.unavailable[0])
    status = async () => { throw new Error('temporary network failure') }
    await vi.advanceTimersByTimeAsync(10000); await flush()
    expect(container.querySelector('.freight-status')?.textContent).toContain(states.unknown[0])
    status = async () => statusResponse('available')
    await vi.advanceTimersByTimeAsync(10000); await flush()
    for (const [index, locale] of locales.entries()) {
      i18n.global.locale.value = locale; await nextTick()
      expect(container.querySelector('.freight-status')?.textContent).toContain(states.available[index])
    }
    expect(api.post).not.toHaveBeenCalled()
    expect(container.querySelector('.purchase')).toBeNull()
    app!.unmount(); app = undefined
    const before = api.get.mock.calls.length
    await vi.advanceTimersByTimeAsync(10000)
    expect(api.get).toHaveBeenCalledTimes(before)
  })

  it('shows invalid CPF in a rejected quote as a correction, never an outage or payment', async () => {
    api.post.mockRejectedValue({ response: { status: 400, data: { detail: cpfError } } })
    const { i18n } = await mountView('addresses')
    const freightButton = Array.from(container.querySelectorAll<HTMLButtonElement>('.card-actions button')).find(button => button.textContent?.trim() === 'Frete')!
    freightButton.click(); await nextTick()
    // Dispatch submit to exercise server validation handling, with no actual provider request.
    container.querySelector('.dialog form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush()
    for (const [index, locale] of locales.entries()) {
      i18n.global.locale.value = locale; await nextTick()
      const message = container.querySelector('.dialog [role="alert"]')?.textContent
      expect(message).toContain(['CPF/CNPJ do destinatário inválido.', 'CPF/CNPJ del destinatario inválido.', 'Invalid recipient CPF/CNPJ.'][index])
      expect(message).toContain(['nenhum pagamento foi realizado.', 'no se realizó ningún pago.', 'no payment was made.'][index])
      expect(message).not.toContain(states.unavailable[index])
      expect(container.querySelector('.freight-status')).toBeNull()
    }
    expect(api.post).toHaveBeenCalledOnce()
    expect(api.post.mock.calls[0]![0]).toBe('/api/freight/quotes')
    expect(container.querySelector('.purchase')).toBeNull()
  })

  it('renders stored validation errors and scheduled recovery separately without changing customer data', async () => {
    const retryAt = '2026-10-04T12:05:00Z'
    orders = [
      { id: 'fixture-order', recipient: 'PRIVATE Customer Fixture', state: 'rejected', environment: 'sandbox', error: cpfError, created_at: '2026-10-04T12:00:00Z', price: null, provider_id: null, label_status: 'none' },
      { id: 'retry-fixture', recipient: 'Retry Fixture', state: 'retry_waiting', environment: 'sandbox', recovery_kind: 'quote', recovery_check_at: retryAt, error_category: 'unavailable', recovery_attempts: 1, created_at: '2026-10-04T12:00:00Z', price: null, provider_id: null, label_status: 'none' },
    ]
    const { i18n } = await mountView()
    for (const [index, locale] of locales.entries()) {
      i18n.global.locale.value = locale; await nextTick()
      expect(container.querySelector('tbody')?.textContent).toContain('PRIVATE Customer Fixture')
      expect(container.querySelector('tbody')?.textContent).toContain(['Dados ou conta precisam de correção', 'Revise datos o cuenta', 'Details or account need correction'][index])
      expect(container.querySelector('tbody .danger')?.textContent).toContain(['CPF/CNPJ do destinatário inválido.', 'CPF/CNPJ del destinatario inválido.', 'Invalid recipient CPF/CNPJ.'][index])
      expect(container.querySelectorAll('tbody tr')[1]?.textContent).toContain(['Aguardando recuperação automática', 'Esperando recuperación automática', 'Awaiting automatic recovery'][index])
      expect(container.querySelectorAll('tbody tr')[1]?.textContent).toContain(['Próxima consulta automática:', 'Próxima consulta automática:', 'Next automatic check:'][index])
      expect(container.querySelectorAll('tbody tr')[1]?.textContent).toContain(new Date(retryAt).toLocaleString(['pt-BR', 'es-PY', 'en-US'][index], { timeZone: 'America/Sao_Paulo' }))
      expect(container.querySelector('.freight-status')).toBeNull()
    }
    expect(api.post).not.toHaveBeenCalled()
  })
})
