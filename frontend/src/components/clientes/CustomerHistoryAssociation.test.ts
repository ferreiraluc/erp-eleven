import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import CustomerHistoryAssociation from './CustomerHistoryAssociation.vue'
import type { CustomerAssociationPreview, CustomerAssociationResult } from '@/services/customerAssociation'

const calls = vi.hoisted(() => ({ preview: vi.fn(), apply: vi.fn() }))
vi.mock('@/services/customerAssociation', () => ({ customerAssociationAPI: calls }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
const auth = reactive({ isOwner: true, token: 'owner-session' as string | null })
const customerId = ref('customer-one'), changed = vi.fn()
const preview: CustomerAssociationPreview = {
  token: 'a'.repeat(64), counts: { addresses: 1, orders: 0, tracking: 1, pdv_accounts: 0 },
  items: [
    { kind: 'address', id: 'address-one', label: 'Destinatário sintético', reason: 'name_address' },
    { kind: 'tracking', id: 'tracking-one', label: 'AA123456789BR', reason: 'explicit_order' },
  ], limited: false, scanned: 12, limit: 200,
}
const linked: CustomerAssociationResult = {
  linked: preview.counts, already_applied: false, limited: false,
}
let app: App, root: HTMLDivElement
const settle = async () => { for (let i = 0; i < 8; i++) await nextTick() }
const button = (label: string) => Array.from(root.querySelectorAll('button')).find(row => row.textContent?.trim() === label)!
async function check() { button('Conferir histórico').click(); await settle() }
async function confirm() {
  const input = root.querySelector<HTMLInputElement>('input[type="checkbox"]')!
  input.checked = true; input.dispatchEvent(new Event('change', { bubbles: true })); await settle()
}
beforeEach(async () => {
  auth.isOwner = true; auth.token = 'owner-session'; customerId.value = 'customer-one'
  changed.mockClear(); calls.preview.mockResolvedValue(preview); calls.apply.mockResolvedValue(linked)
  root = document.createElement('div'); document.body.append(root)
  app = createApp({ render: () => h(CustomerHistoryAssociation, { customerId: customerId.value, onChanged: changed }) })
  app.use(createI18n({ legacy: false, locale: 'pt', messages: {} }))
  app.mount(root); await settle()
})
afterEach(() => { app.unmount(); root.remove(); vi.resetAllMocks() })

describe('Customer history association review', () => {
  it('loads only on request and applies the reviewed plan after explicit confirmation', async () => {
    expect(calls.preview).not.toHaveBeenCalled(); expect(calls.apply).not.toHaveBeenCalled()
    await check()
    expect(calls.preview).toHaveBeenCalledWith('customer-one', 'owner-session', expect.any(AbortSignal))
    expect(root.textContent).toContain('AA123456789BR')
    expect(root.textContent).toContain('Nome e endereço compatíveis')
    expect(button('Associar registros conferidos').disabled).toBe(true)
    await confirm()
    const action = button('Associar registros conferidos')
    action.click(); action.click(); await settle()
    expect(calls.apply).toHaveBeenCalledTimes(1)
    expect(calls.apply).toHaveBeenCalledWith('customer-one', preview.token, 'owner-session', expect.any(AbortSignal))
    expect(changed).toHaveBeenCalledTimes(1)
    expect(root.textContent).toContain('Histórico associado')
    expect(root.textContent).not.toContain('AA123456789BR')
  })

  it('shows a bounded partial review and never offers to apply an empty preview', async () => {
    calls.preview.mockResolvedValueOnce({ ...preview, limited: true, items: [], counts: { addresses: 0, orders: 0, tracking: 0, pdv_accounts: 0 } })
    await check()
    expect(root.textContent).toContain('Consulta parcial')
    expect(root.textContent).toContain('Nenhum vínculo seguro')
    expect(root.querySelector('input[type="checkbox"]')).toBeNull()
    expect(calls.apply).not.toHaveBeenCalled()
  })

  it('invalidates stale plans after conflict instead of repeating a changed operation', async () => {
    calls.apply.mockRejectedValueOnce({ response: { status: 409 } })
    await check(); await confirm()
    button('Associar registros conferidos').click(); await settle()
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Os dados mudaram')
    expect(root.querySelector('input[type="checkbox"]')).toBeNull()
    expect(changed).not.toHaveBeenCalled()
    expect(button('Conferir histórico')).toBeTruthy()
  })

  it('preserves the partial-review notice after applying the visible records', async () => {
    calls.preview.mockResolvedValueOnce({ ...preview, limited: true })
    calls.apply.mockResolvedValueOnce({ ...linked, limited: true })
    await check(); await confirm()
    button('Associar registros conferidos').click(); await settle()
    expect(root.querySelector('[role="status"]')?.textContent).toContain('Consulta parcial')
    expect(root.textContent).toContain('Histórico associado')
  })

  it('aborts and ignores a late preview after changing the customer', async () => {
    let finish!: (result: CustomerAssociationPreview) => void
    calls.preview.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    button('Conferir histórico').click(); await settle()
    const signal = calls.preview.mock.calls[0][2]
    customerId.value = 'customer-two'; await settle()
    expect(signal.aborted).toBe(true)
    finish(preview); await settle()
    expect(root.textContent).not.toContain('AA123456789BR')
    expect(changed).not.toHaveBeenCalled()
  })

  it('discards an old account confirmation and removes owner controls after logout', async () => {
    let finish!: (result: CustomerAssociationResult) => void
    calls.apply.mockReturnValueOnce(new Promise(resolve => { finish = resolve }))
    await check(); await confirm()
    button('Associar registros conferidos').click(); await settle()
    const signal = calls.apply.mock.calls[0][3]
    auth.token = null; auth.isOwner = false; await settle()
    finish(linked); await settle()
    expect(signal.aborted).toBe(true)
    expect(root.querySelector('section')).toBeNull()
    expect(changed).not.toHaveBeenCalled()
  })

  it('keeps connection failure distinct from a confirmed empty result', async () => {
    calls.preview.mockRejectedValueOnce(new Error('offline'))
    await check()
    expect(root.querySelector('[role="alert"]')?.textContent).toContain('Confira a conexão')
    expect(root.textContent).not.toContain('Nenhum vínculo seguro')
  })
})
