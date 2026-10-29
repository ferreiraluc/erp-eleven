import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import FiadoView from './FiadoView.vue'
import { chooseDropdown, openDropdown } from '@/test/dropdown'

const calls = vi.hoisted(() => ({ getClients: vi.fn(), createClient: vi.fn(), recordFiadoPayment: vi.fn() }))
vi.mock('@/services/api', () => ({ pdvAPI: calls }))
let app: App, root: HTMLDivElement
const settle = async () => { for (let i = 0; i < 8; i++) await nextTick() }
const button = (text: string) => Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(row => row.textContent?.trim() === text)!
async function fillNameAndDocument() {
  const name = root.querySelector<HTMLInputElement>('.fiado-new-body .fiado-input')!
  name.value = 'Cliente sintético QA'; name.dispatchEvent(new Event('input'))
  const number = root.querySelector<HTMLInputElement>('#fiado-document-number')!
  number.value = '80012345-6'; number.dispatchEvent(new Event('input')); await settle()
}
beforeEach(async () => {
  calls.getClients.mockResolvedValue([]); calls.createClient.mockResolvedValue({ id: 'local-only-qa' })
  root = document.createElement('div'); document.body.append(root)
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/', component: { render: () => null } }] })
  await router.push('/'); await router.isReady()
  app = createApp(FiadoView).use(createI18n({ legacy: false, locale: 'pt', messages: {} })).use(router)
  app.config.globalProperties.$tr = (text: string) => text
  app.mount(root); await settle(); button('+ Novo cliente').click(); await settle()
})
afterEach(() => { app.unmount(); root.remove(); vi.resetAllMocks() })

describe('Fiado customer document identity', () => {
  it('creates a typed Paraguayan document with the correct country and retains its original number', async () => {
    await fillNameAndDocument()
    const type = root.querySelector('[aria-label="Tipo de documento"]')
    expect((await openDropdown(type)).map(option => option.value)).toEqual(['', 'CPF', 'CNPJ', 'RG', 'CI', 'RUC'])
    await chooseDropdown(type, 'RUC')
    button('Cadastrar').click(); await settle()
    expect(calls.createClient).toHaveBeenCalledWith(expect.objectContaining({ nome: 'Cliente sintético QA', doc: '80012345-6', doc_tipo: 'RUC', doc_pais: 'PY' }))
    expect(calls.recordFiadoPayment).not.toHaveBeenCalled()
  })

  it('leaves an unknown legacy document untyped and derives BR only after selecting a Brazilian type', async () => {
    await fillNameAndDocument()
    button('Cadastrar').click(); await settle()
    const untyped = calls.createClient.mock.calls[0][0]
    expect(untyped.doc).toBe('80012345-6'); expect(untyped).not.toHaveProperty('doc_tipo'); expect(untyped).not.toHaveProperty('doc_pais')
    button('+ Novo cliente').click(); await settle(); await fillNameAndDocument()
    await chooseDropdown(root.querySelector('[aria-label="Tipo de documento"]'), 'RG')
    button('Cadastrar').click(); await settle()
    expect(calls.createClient).toHaveBeenLastCalledWith(expect.objectContaining({ doc: '80012345-6', doc_tipo: 'RG', doc_pais: 'BR' }))
  })

  it('does not submit duplicate creates while a request is pending', async () => {
    let finish!: (value: { id: string }) => void
    calls.createClient.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    await fillNameAndDocument()
    const submit = button('Cadastrar'); submit.click(); submit.click(); await settle()
    expect(calls.createClient).toHaveBeenCalledTimes(1)
    finish({ id: 'local-only-qa' }); await settle()
    expect(calls.recordFiadoPayment).not.toHaveBeenCalled()
  })
})
