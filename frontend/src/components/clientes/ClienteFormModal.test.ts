import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ClienteFormModal from './ClienteFormModal.vue'
import type { Cliente } from '@/services/api'

const calls = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn() }))
vi.mock('@/services/api', () => ({ clientesAPI: calls }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
const auth = reactive({ token: 'current-session' as string | null })
let app: App, root: HTMLDivElement
const saved = vi.fn(), closed = vi.fn()
const customer: Cliente = { id: 'customer-qa', nome: 'Cliente sintético QA', ativo: true, cpf: '12345678909', documentos: [{ tipo: 'CI', pais: 'PY', numero: '1234567' }], created_at: '', updated_at: '' }
const settle = async () => { for (let i = 0; i < 8; i++) await nextTick() }
const button = (text: string) => Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(row => row.textContent?.trim() === text)!
async function mount(cliente: Cliente | null = null) {
  root = document.createElement('div'); document.body.append(root)
  app = createApp({ render: () => h(ClienteFormModal, { isVisible: true, cliente, onSaved: saved, onClose: closed }) })
  app.use(createI18n({ legacy: false, locale: 'pt', messages: {} })); app.mount(root); await settle()
}
async function submit() { root.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true })); await settle() }
beforeEach(() => {
  auth.token = 'current-session'; saved.mockClear(); closed.mockClear()
  calls.create.mockResolvedValue(customer); calls.update.mockResolvedValue(customer)
})
afterEach(() => { app?.unmount(); root?.remove(); vi.resetAllMocks() })

describe('Customer document fields', () => {
  it('preserves typed Paraguayan documents and the legacy CPF in separate namespaces', async () => {
    await mount(customer)
    expect(root.querySelectorAll('.document-row')).toHaveLength(2)
    await submit()
    expect(calls.update).toHaveBeenCalledWith(customer.id, expect.objectContaining({
      cpf: '12345678909', documentos: [{ tipo: 'CI', pais: 'PY', numero: '1234567' }, { tipo: 'CPF', pais: 'BR', numero: '12345678909' }],
    }))
    expect(saved).toHaveBeenCalledWith(customer)
  })

  it('sends an explicit null when removing the CPF while keeping other documents', async () => {
    await mount(customer)
    root.querySelectorAll<HTMLElement>('.document-row')[1].querySelector<HTMLButtonElement>('[aria-label="Remover documento"]')!.click(); await settle(); await submit()
    expect(calls.update).toHaveBeenCalledWith(customer.id, expect.objectContaining({ cpf: null, documentos: [{ tipo: 'CI', pais: 'PY', numero: '1234567' }] }))
  })

  it('does not populate a merged primary’s empty legacy CPF from a document retained by an alias when editing its phone', async () => {
    const primary: Cliente = { ...customer, cpf: null, documentos: [{ tipo: 'CPF', pais: 'BR', numero: '12345678909' }] }
    await mount(primary)
    const phone = root.querySelector<HTMLInputElement>('#customer-form-phone')!
    phone.value = '5511000000000'; phone.dispatchEvent(new Event('input')); await settle(); await submit()
    expect(calls.update).toHaveBeenCalledWith(primary.id, expect.objectContaining({ telefone: '5511000000000', cpf: null, documentos: primary.documentos }))
  })

  it('updates only the explicitly edited original legacy CPF rather than picking another CPF from the document list', async () => {
    await mount({ ...customer, documentos: [{ tipo: 'CPF', pais: 'BR', numero: '99988877766' }] })
    const original = root.querySelectorAll<HTMLInputElement>('[aria-label="Número do documento"]')[1]
    original.value = '11122233344'; original.dispatchEvent(new Event('input')); await settle(); await submit()
    expect(calls.update).toHaveBeenCalledWith(customer.id, expect.objectContaining({ cpf: '11122233344', documentos: [{ tipo: 'CPF', pais: 'BR', numero: '99988877766' }, { tipo: 'CPF', pais: 'BR', numero: '11122233344' }] }))
  })

  it('clears the original legacy CPF when its row is removed even if another CPF remains in documents', async () => {
    await mount({ ...customer, documentos: [{ tipo: 'CPF', pais: 'BR', numero: '99988877766' }] })
    root.querySelectorAll<HTMLElement>('.document-row')[1].querySelector<HTMLButtonElement>('[aria-label="Remover documento"]')!.click(); await settle(); await submit()
    expect(calls.update).toHaveBeenCalledWith(customer.id, expect.objectContaining({ cpf: null, documentos: [{ tipo: 'CPF', pais: 'BR', numero: '99988877766' }] }))
  })

  it('uses the standard dropdown to create a CI without labeling its digits as a CPF', async () => {
    await mount()
    const name = root.querySelector<HTMLInputElement>('#customer-form-name')!
    name.value = 'Cliente novo QA'; name.dispatchEvent(new Event('input')); await settle()
    button('+ Adicionar documento').click(); await settle()
    root.querySelector<HTMLButtonElement>('[aria-label="Tipo de documento"]')!.click(); await settle()
    Array.from(document.querySelectorAll<HTMLButtonElement>('[role="option"]')).find(row => row.textContent?.trim() === 'CI · PY')!.click(); await settle()
    const number = root.querySelector<HTMLInputElement>('[aria-label="Número do documento"]')!
    number.value = '7654321'; number.dispatchEvent(new Event('input')); await settle(); await submit()
    expect(calls.create).toHaveBeenCalledWith(expect.objectContaining({ cpf: null, documentos: [{ tipo: 'CI', pais: 'PY', numero: '7654321' }] }))
  })

  it('keeps an untyped historical document as a reference unless explicitly classified', async () => {
    await mount({ ...customer, cpf: 'CI anterior 12345', documentos: [] })
    expect(root.querySelector('.legacy-document')?.textContent).toContain('Documento anterior sem tipo')
    await submit()
    expect(calls.update).toHaveBeenCalledWith(customer.id, expect.objectContaining({ cpf: 'CI anterior 12345', documentos: [] }))
  })

  it('does not emit another account’s saved customer after the session changes', async () => {
    let finish!: (value: Cliente) => void
    calls.update.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    await mount(customer); await submit()
    auth.token = 'another-account'; await settle(); finish(customer); await settle()
    expect(closed).toHaveBeenCalledTimes(1); expect(saved).not.toHaveBeenCalled()
  })
})
