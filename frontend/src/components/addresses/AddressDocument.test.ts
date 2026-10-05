import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import AddressFields from './AddressFields.vue'
import AddressesView from '@/views/AddressesView.vue'
import { blankAddress, type AddressData } from './types'

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))
vi.mock('@/services/api', () => ({ default: api }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: false }) }))

let app: App | undefined, container: HTMLDivElement
const translation = () => createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
const flush = async () => { await Promise.resolve(); await Promise.resolve(); await nextTick() }

beforeEach(() => {
  container = document.createElement('div'); document.body.append(container)
  api.get.mockImplementation(async (url: string) => {
    if (url.endsWith('/overview')) return { data: { addresses: 0, statuses: {}, devices: [] } }
    if (url.endsWith('/addresses')) return { data: { total: 0, items: [] } }
    if (url.endsWith('/senders')) return { data: [] }
    if (url.endsWith('/layouts')) return { data: ['br', 'py'].map(id => ({
      id, name: `Fixture ${id}`, version: 0,
      config: { title: 'DESTINATÁRIO', font_size: 17, margin: 42, sender_font_size: 12, sender_gap: 40, bold: true, fields: ['nome', 'cpf', 'cidade'] },
    })) }
    if (url.endsWith('/status')) return { data: { configured: false, environment: 'sandbox' } }
    throw new Error(`Unexpected request: ${url}`)
  })
  api.put.mockResolvedValue({ data: { version: 1 } })
})
afterEach(() => { app?.unmount(); app = undefined; container.remove(); vi.resetAllMocks() })

describe('country-specific optional recipient document', () => {
  it('reacts to country and PT/ES/EN without changing the stored cpf key or document text', async () => {
    const data = ref<AddressData>({ ...blankAddress('PY'), nome: 'Cliente fixture', cpf: 'A-4.567.890' })
    const i18n = translation()
    app = createApp({ setup: () => () => h(AddressFields, { modelValue: data.value, 'onUpdate:modelValue': value => { data.value = value } }) }).use(i18n)
    app.mount(container); await nextTick()
    for (const [locale, label] of [
      ['pt', 'RUC/C.I (opcional na impressão)'],
      ['es', 'RUC/C.I (opcional para impresión)'],
      ['en', 'RUC/C.I (optional for printing)'],
    ] as const) {
      i18n.global.locale.value = locale; await nextTick()
      const documentLabel = Array.from(container.querySelectorAll('label')).find(element => element.textContent?.includes('RUC/C.I'))!
      expect(documentLabel.textContent?.trim()).toBe(label)
      expect(documentLabel.querySelector('input')?.value).toBe('A-4.567.890')
      expect(container.textContent).not.toContain('CPF')
    }
    const input = Array.from(container.querySelectorAll('label')).find(element => element.textContent?.includes('RUC/C.I'))!.querySelector('input')!
    input.value = '80012345-6'; input.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    expect(data.value.cpf).toBe('80012345-6')
    expect(Object.keys(data.value)).toEqual(Object.keys(blankAddress()))
    const country = container.querySelector('select')!
    country.value = 'BR'; country.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    expect(container.textContent).toContain('CPF / document')
    expect(container.textContent).not.toContain('RUC/C.I')
    expect(data.value.cpf).toBe('80012345-6')
    country.value = 'PY'; country.dispatchEvent(new Event('change', { bubbles: true })); await nextTick()
    expect(container.textContent).toContain('RUC/C.I')
    expect(data.value.cpf).toBe('80012345-6')
    expect(api.post).not.toHaveBeenCalled()
  })

  it('uses RUC/C.I only for the PY pattern and saves the original cpf layout field', async () => {
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/enderecos', component: { template: '<div />' } },
      { path: '/dashboard', component: { template: '<div />' } },
    ] })
    await router.push('/enderecos?tab=layouts'); await router.isReady()
    const i18n = translation()
    app = createApp(AddressesView).use(router).use(i18n); app.mount(container); await flush()
    const [br, py] = Array.from(container.querySelectorAll<HTMLFormElement>('.layout-form'))
    expect(br).toBeDefined(); expect(py).toBeDefined()
    for (const locale of ['pt', 'es', 'en'] as const) {
      i18n.global.locale.value = locale; await nextTick()
      expect(Array.from(br!.querySelectorAll('.field-order span')).map(element => element.textContent)).toContain('CPF')
      expect(Array.from(py!.querySelectorAll('.field-order span')).map(element => element.textContent)).toContain('RUC/C.I')
      expect(br!.querySelector('option[value="cpf"]')?.textContent).toBe('CPF')
      expect(py!.querySelector('option[value="cpf"]')?.textContent).toBe('RUC/C.I')
    }
    py!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush()
    expect(api.put).toHaveBeenCalledOnce()
    expect(api.put).toHaveBeenCalledWith('/api/address-manager/layouts/py', expect.objectContaining({
      config: expect.objectContaining({ fields: ['nome', 'cpf', 'cidade'] }),
    }))
    expect(api.post).not.toHaveBeenCalled()
  })
})
