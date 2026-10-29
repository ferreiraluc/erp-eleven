import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import CustomerMergeSelectionModal from './CustomerMergeSelectionModal.vue'
import type { CustomerMergePlan, CustomerMergePreview } from '@/services/customerMerge'
import type { Cliente } from '@/services/api'

const calls = vi.hoisted(() => ({ preview: vi.fn(), confirm: vi.fn() }))
vi.mock('@/services/customerMerge', () => ({ customerMergeAPI: calls }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
const auth = reactive({ isOwner: true, token: 'owner-session' as string | null })
const customers: Cliente[] = [
  { id: 'one', nome: 'Ana Maria Silva QA', ativo: true, telefone: '5511999990000', endereco: 'Rua QA, 10', created_at: '', updated_at: '' },
  { id: 'two', nome: 'Ana Silva QA', ativo: true, telefone: '5511999991111', endereco: 'Rua QA, 10', created_at: '', updated_at: '' },
]
const counts = { orders: 2, tracking: 3, addresses: 1, pdv_customers: 2 }
const plan: CustomerMergePlan = {
  state: 'ready', target_id: 'one', source_ids: ['two'], plan_token: 'token-reviewed-plan',
  customers: customers.map(customer => ({ id: customer.id, name: customer.nome, telefone: customer.telefone, endereco: customer.endereco })),
  conflicting_fields: [], conflicts: [], fields_added: [], links_to_move: counts, history: counts,
  requires_reviewed_conflicts: false,
}
let app: App, root: HTMLDivElement
const changed = vi.fn(), closed = vi.fn()
const settle = async () => { for (let i = 0; i < 8; i++) await nextTick() }
const button = (text: string) => Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(row => row.textContent?.trim() === text)!
async function check() { button('Conferir união').click(); await settle() }
function checkBox(index = 0) { document.querySelectorAll<HTMLInputElement>('.merge-check input')[index].click() }
beforeEach(async () => {
  auth.isOwner = true; auth.token = 'owner-session'; changed.mockClear(); closed.mockClear()
  calls.preview.mockResolvedValue(plan); calls.confirm.mockResolvedValue({ state: 'merged', target_id: 'one', source_ids: ['two'] })
  root = document.createElement('div'); document.body.append(root)
  app = createApp({ render: () => h(CustomerMergeSelectionModal, { customers, onChanged: changed, onClose: closed }) })
  app.use(createI18n({ legacy: false, locale: 'pt', messages: {} }))
  app.mount(root); await settle()
})
afterEach(() => { app.unmount(); root.remove(); vi.resetAllMocks() })

describe('Selected customer merge review', () => {
  it('requires a reviewed plan and identity confirmation, submitting only the chosen records once', async () => {
    expect(calls.preview).not.toHaveBeenCalled(); expect(calls.confirm).not.toHaveBeenCalled()
    await check()
    expect(calls.preview).toHaveBeenCalledWith('one', ['two'], 'owner-session', expect.any(AbortSignal))
    expect(document.querySelector('.merge-summary')?.textContent).toContain('Histórico reunido no principal')
    expect(button('Unificar cadastros').disabled).toBe(true)
    checkBox(); await settle()
    const submit = button('Unificar cadastros'); submit.click(); submit.click(); await settle()
    expect(calls.confirm).toHaveBeenCalledTimes(1)
    expect(calls.confirm).toHaveBeenCalledWith(plan, false, 'owner-session', expect.any(AbortSignal))
    expect(changed).toHaveBeenCalledWith('one', ['two'])
  })

  it('requires explicit review of differences in addition to confirmation of identity', async () => {
    calls.preview.mockResolvedValueOnce({ ...plan, state: 'review_conflicts', conflicting_fields: ['nome', 'telefone'], conflicts: [{ source_id: 'two', fields: ['nome', 'telefone'] }], requires_reviewed_conflicts: true })
    await check()
    expect(document.querySelector('.merge-conflicts')?.textContent).toContain('Ana Silva QA: Nome, Telefone')
    checkBox(); await settle()
    expect(button('Unificar cadastros').disabled).toBe(true)
    checkBox(1); await settle()
    button('Unificar cadastros').click(); await settle()
    expect(calls.confirm).toHaveBeenCalledWith(expect.objectContaining({ requires_reviewed_conflicts: true }), true, 'owner-session', expect.any(AbortSignal))
  })

  it('uses the custom dropdown and invalidates the old plan when changing the principal', async () => {
    await check(); checkBox(); await settle()
    document.querySelector<HTMLButtonElement>('[aria-label="Cadastro principal"]')!.click(); await settle()
    const option = Array.from(document.querySelectorAll<HTMLButtonElement>('[role="option"]')).find(row => row.textContent?.trim() === 'Ana Silva QA')!
    option.click(); await settle()
    expect(button('Unificar cadastros')).toBeUndefined()
    calls.preview.mockResolvedValueOnce({ ...plan, target_id: 'two', source_ids: ['one'] })
    await check()
    expect(calls.preview).toHaveBeenLastCalledWith('two', ['one'], 'owner-session', expect.any(AbortSignal))
    expect(button('Unificar cadastros').disabled).toBe(true)
  })

  it('requires a fresh preview after a changed record or an uncertain request result', async () => {
    await check(); checkBox(); await settle()
    calls.confirm.mockRejectedValueOnce({ response: { status: 409 } })
    button('Unificar cadastros').click(); await settle()
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('Os cadastros mudaram')
    expect(button('Unificar cadastros')).toBeUndefined(); expect(calls.confirm).toHaveBeenCalledTimes(1)
    calls.preview.mockResolvedValueOnce({ ...plan, state: 'already_merged' })
    await check()
    expect(changed).toHaveBeenCalledWith('one', ['two'])
    expect(calls.confirm).toHaveBeenCalledTimes(1)
  })

  it('aborts an old session request and ignores a late result after an account change', async () => {
    let finish!: (value: CustomerMergePreview) => void
    calls.preview.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    button('Conferir união').click(); await settle()
    const signal = calls.preview.mock.calls[0][3]
    auth.token = 'different-session'; await settle()
    expect(signal.aborted).toBe(true); expect(closed).toHaveBeenCalled()
    finish(plan); await settle()
    expect(document.querySelector('.merge-summary')).toBeNull(); expect(changed).not.toHaveBeenCalled()
  })

  it('preserves selection on cancellation and never writes from preview or close', async () => {
    await check(); button('Cancelar').click(); await settle()
    expect(closed).toHaveBeenCalledTimes(1); expect(calls.confirm).not.toHaveBeenCalled(); expect(changed).not.toHaveBeenCalled()
  })
})
