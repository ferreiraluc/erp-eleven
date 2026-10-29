import { chooseDropdown, openDropdown } from '@/test/dropdown'
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
  it('keeps PY essentials visible and preserves optional address data when changing country', async () => {
    const data = ref<AddressData>({ ...blankAddress('PY'), nome: 'Cliente fixture', cidade: 'Asunción', telefone: '00000000' })
    app = createApp({ setup: () => () => h(AddressFields, { modelValue: data.value, 'onUpdate:modelValue': value => { data.value = value } }) }).use(translation())
    app.mount(container); await nextTick()
    expect(container.querySelector('details')?.open).toBe(false)
    const directLabels = Array.from(container.querySelectorAll('.fields > label')).filter(el => !el.closest('details')).map(el => el.textContent?.trim())
    expect(directLabels).toEqual(expect.arrayContaining(['Nome do destinatário', 'Telefone', 'Cidade', 'RUC/C.I (opcional na impressão)']))
    data.value.endereco = 'Rua informada'; await nextTick()
    expect(container.querySelector('details')?.open).toBe(true)
    data.value.pais = 'BR'; await nextTick()
    expect(container.querySelector('details')).toBeNull()
    expect(data.value.endereco).toBe('Rua informada')
    data.value.pais = 'PY'; await nextTick()
    expect(container.querySelector('details')?.open).toBe(true)
    expect(data.value.endereco).toBe('Rua informada')
    expect(api.post).not.toHaveBeenCalled()
  })

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
    await chooseDropdown(container.querySelector('.erp-dropdown'), 'BR')
    expect(container.textContent).toContain('CPF / document')
    expect(container.textContent).not.toContain('RUC/C.I')
    expect(data.value.cpf).toBe('80012345-6')
    await chooseDropdown(container.querySelector('.erp-dropdown'), 'PY')
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
      expect((await openDropdown(Array.from(br!.querySelectorAll('.erp-dropdown')).at(-1))).find(o => o.value === 'cpf')?.textContent).toBe('CPF')
      expect((await openDropdown(Array.from(py!.querySelectorAll('.erp-dropdown')).at(-1))).find(o => o.value === 'cpf')?.textContent).toBe('RUC/C.I')
    }
    py!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await flush()
    expect(api.put).toHaveBeenCalledOnce()
    expect(api.put).toHaveBeenCalledWith('/api/address-manager/layouts/py', expect.objectContaining({
      config: expect.objectContaining({ fields: ['nome', 'cpf', 'cidade'] }),
    }))
    expect(api.post).not.toHaveBeenCalled()
  })

  it('offers typed documents by country without inferring a type or changing historical document text', async () => {
    const data = ref<AddressData>({ ...blankAddress('PY'), cpf: '80012345-6' })
    app = createApp({ setup: () => () => h(AddressFields, { modelValue: data.value, 'onUpdate:modelValue': value => { data.value = value } }) }).use(translation())
    app.mount(container); await nextTick()
    const typeControl = () => container.querySelector('[aria-label="Tipo de documento"]')
    expect((await openDropdown(typeControl())).map(option => option.value)).toEqual(['', 'CI', 'RUC'])
    expect(data.value.documento_tipo).toBeUndefined()
    await chooseDropdown(typeControl(), 'RUC')
    expect(data.value.documento_tipo).toBe('RUC')
    expect(data.value.cpf).toBe('80012345-6')
    await chooseDropdown(container.querySelector('[aria-label="País"]'), 'BR')
    expect(data.value.documento_tipo).toBeUndefined()
    expect(data.value.cpf).toBe('80012345-6')
    expect((await openDropdown(typeControl())).map(option => option.value)).toEqual(['', 'CPF', 'CNPJ', 'RG'])
    expect(api.post).not.toHaveBeenCalled()
  })

  it('keeps the optional RG issuer in its namespace and clears it when changing document kind', async () => {
    const data = ref<AddressData>({ ...blankAddress('BR'), cpf: '12.345.678-X' })
    app = createApp({ setup: () => () => h(AddressFields, { modelValue: data.value, 'onUpdate:modelValue': value => { data.value = value } }) }).use(translation())
    app.mount(container); await nextTick()
    await chooseDropdown(container.querySelector('[aria-label="Tipo de documento"]'), 'RG')
    const issuer = Array.from(container.querySelectorAll('label')).find(label => label.textContent?.includes('Emissor / UF'))!.querySelector('input')!
    issuer.value = 'SSP-SP'; issuer.dispatchEvent(new Event('input', { bubbles: true })); await nextTick()
    expect(data.value.documento_emissor).toBe('SSP-SP')
    await chooseDropdown(container.querySelector('[aria-label="Tipo de documento"]'), '')
    expect(data.value.documento_tipo).toBeUndefined()
    expect(data.value.documento_emissor).toBeUndefined()
    expect(data.value.cpf).toBe('12.345.678-X')
    expect(container.textContent).not.toContain('Emissor / UF')
  })

  it('translates document type and optional issuer labels without translating stored identifiers', async () => {
    const data = ref<AddressData>({ ...blankAddress('BR'), cpf: '12.345.678-X', documento_tipo: 'RG', documento_emissor: 'SSP-QA' })
    const i18n = translation()
    app = createApp({ setup: () => () => h(AddressFields, { modelValue: data.value, 'onUpdate:modelValue': value => { data.value = value } }) }).use(i18n)
    app.mount(container); await nextTick()
    for (const [locale, type, issuer] of [
      ['pt', 'Tipo de documento', 'Emissor / UF do RG (opcional)'],
      ['es', 'Tipo de documento', 'Emisor / UF del RG (opcional)'],
      ['en', 'Document type', 'RG issuer / state (optional)'],
    ] as const) {
      i18n.global.locale.value = locale; await nextTick()
      expect(container.querySelector(`[aria-label="${type}"]`)).not.toBeNull()
      expect(container.textContent).toContain(issuer)
      expect(data.value.documento_emissor).toBe('SSP-QA')
      expect(data.value.cpf).toBe('12.345.678-X')
    }
  })

  it('labels the stored document number with the selected type instead of CPF or the legacy combined label', async () => {
    const data = ref<AddressData>({ ...blankAddress('BR'), documento_tipo: 'RG', cpf: '12.345.678-X' })
    const i18n = translation()
    app = createApp({ setup: () => () => h(AddressFields, { modelValue: data.value, 'onUpdate:modelValue': value => { data.value = value } }) }).use(i18n)
    app.mount(container); await nextTick()
    for (const [pais, tipo, numero] of [['BR', 'RG', '12.345.678-X'], ['PY', 'RUC', '80012345-6'], ['PY', 'CI', '7654321']] as const) {
      data.value = { ...blankAddress(pais), documento_tipo: tipo, cpf: numero }
      for (const [locale, suffix] of [['pt', '(opcional na impressão)'], ['es', '(opcional para impresión)'], ['en', '(optional for printing)']] as const) {
        i18n.global.locale.value = locale; await nextTick()
        const numberLabel = Array.from(container.querySelectorAll('label')).find(label => label.querySelector('input')?.value === numero)!
        expect(numberLabel.textContent?.trim()).toBe(`${tipo} ${suffix}`)
        expect(data.value.cpf).toBe(numero)
      }
    }
  })

  it('uses the sender document type in the printable preview without changing historical sender blocks', async () => {
    const initialGet = api.get.getMockImplementation()!
    api.get.mockImplementation(async (url: string) => url.endsWith('/senders') ? { data: [{ id: 'sender-qa', name: 'Remetente QA', lines: ['CPF/CNPJ: bloco anterior preservado'], data: { ...blankAddress('BR'), nome: 'Remetente QA', cpf: '12.345.678-X', documento_tipo: 'RG' }, active: true, version: 1 }] } : initialGet(url))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/enderecos', component: { template: '<div />' } }, { path: '/dashboard', component: { template: '<div />' } }] })
    await router.push('/enderecos?tab=senders'); await router.isReady()
    app = createApp(AddressesView).use(router).use(translation()); app.mount(container); await flush()
    Array.from(container.querySelectorAll<HTMLButtonElement>('button')).find(button => button.textContent?.trim() === 'Editar remetente')!.click(); await nextTick()
    const preview = container.querySelector<HTMLTextAreaElement>('textarea[readonly]')!
    expect(preview.value).toContain('RG: 12.345.678-X')
    expect(preview.value).not.toContain('CPF/CNPJ:')
    expect(container.querySelector('details .preline')?.textContent).toBe('CPF/CNPJ: bloco anterior preservado')
    await chooseDropdown(container.querySelector('[aria-label="País"]'), 'PY')
    await chooseDropdown(container.querySelector('[aria-label="Tipo de documento"]'), 'RUC')
    expect(preview.value).toContain('RUC: 12.345.678-X')
    expect(api.post).not.toHaveBeenCalled(); expect(api.put).not.toHaveBeenCalled()
  })
})
