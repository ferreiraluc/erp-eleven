import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import BulkDeleteModal from './BulkDeleteModal.vue'
const api = vi.hoisted(() => ({ preview: vi.fn(), remove: vi.fn(), preserveHistory: vi.fn() }))
vi.mock('@/services/inventoryDeletion', () => ({ inventoryDeletionAPI: api }))
function preview(id: string, linked = false) { return { allowed: !linked, blockers: linked ? [{ code: 'sales', count: 2 }] : [], movement_count: 1,
  plan_token: linked ? null : `token-${id}`, preserve_history_token: `history-${id}`,
  item: { id, name: `Produto ${id}`, sku_internal: `SKU-${id}`, size: 'M', color: 'Branco', stock_loja: 2, stock_deposito: null } } }
let app: App, root: HTMLDivElement
async function mount(ids = ['a', 'b', 'c'], props = {}) {
  root = document.createElement('div'); document.body.append(root)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(BulkDeleteModal, { items: ids.map(id => ({ id, name: id })), ...props }).use(i18n); app.mount(root)
  await vi.waitFor(() => expect(root.textContent).not.toContain('Conferindo os itens'))
  return i18n
}
function button(text: string) { return Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === text)! }
async function approve() { const check = root.querySelector('input')!; check.checked = true; check.dispatchEvent(new Event('change', { bubbles: true })); await nextTick() }
beforeEach(() => { vi.resetAllMocks(); api.preview.mockImplementation(async id => preview(id)); api.remove.mockImplementation(async id => ({ deleted: true, id })); api.preserveHistory.mockImplementation(async id => ({ deleted: true, id })) })
afterEach(() => { app?.unmount(); root?.remove() })
describe('Reviewed bulk deletion', () => {
  it('reviews unique identities and invokes the correct owner endpoints only after confirmation', async () => {
    api.preview.mockImplementation(async id => preview(id, id === 'b'))
    const deleted = vi.fn(); const i18n = await mount(['a', 'b', 'a'], { onDeleted: deleted })
    expect(api.preview).toHaveBeenCalledTimes(2)
    expect(root.textContent).toContain('SKU-a'); expect(root.textContent).toContain('Não informado')
    expect(button('Excluir 2 itens').disabled).toBe(true); expect(api.remove).not.toHaveBeenCalled()
    await approve(); button('Excluir 2 itens').click(); button('Excluir 2 itens').click()
    await vi.waitFor(() => expect(deleted).toHaveBeenCalledTimes(2))
    expect(api.remove).toHaveBeenCalledExactlyOnceWith('a', { sku: 'SKU-a', plan_token: 'token-a', confirm: true })
    expect(api.preserveHistory).toHaveBeenCalledExactlyOnceWith('b', { sku: 'SKU-b', plan_token: 'history-b', confirm: true })
    expect(root.textContent).toContain('Itens excluídos: 2')
    i18n.global.locale.value = 'es'; await nextTick(); expect(root.textContent).toContain('Artículos eliminados: 2')
  })
  it('stops on an uncertain result and requires fresh preview and confirmation without repeating successes', async () => {
    api.remove.mockImplementation(async id => { if (id === 'b') throw new Error('timeout'); return { deleted: true, id } })
    await mount(); await approve(); button('Excluir 3 itens').click()
    await vi.waitFor(() => expect(root.textContent).toContain('A operação foi interrompida'))
    expect(api.remove.mock.calls.map(call => call[0])).toEqual(['a', 'b'])
    expect(button('Excluir 2 itens')).toBeUndefined()
    api.remove.mockImplementation(async id => ({ deleted: true, id }))
    button('Conferir pendentes novamente').click()
    await vi.waitFor(() => expect(button('Excluir 2 itens')).toBeDefined())
    expect(button('Excluir 2 itens').disabled).toBe(true)
    expect(api.preview.mock.calls.map(call => call[0])).toEqual(['a', 'b', 'c', 'b', 'c'])
    await approve(); button('Excluir 2 itens').click()
    await vi.waitFor(() => expect(root.textContent).toContain('Itens excluídos: 3'))
    expect(api.remove.mock.calls.map(call => call[0])).toEqual(['a', 'b', 'b', 'c'])
  })
  it('does not authorize missing or mismatched previews', async () => {
    api.preview.mockResolvedValue(preview('another-item'))
    await mount(['a']); expect(root.querySelector('input')).toBeNull(); expect(api.remove).not.toHaveBeenCalled()
    expect(root.textContent).toContain('Não foi possível conferir')
  })
  it('blocks closing during deletion and starts no further requests after unmount', async () => {
    let resolve!: (result: unknown) => void
    api.remove.mockReturnValueOnce(new Promise(yes => { resolve = yes }))
    const close = vi.fn(); await mount(['a', 'b'], { onClose: close })
    await approve(); button('Excluir 2 itens').click(); await nextTick()
    expect(button('Voltar').disabled).toBe(true)
    root.querySelector('.bulk-delete-overlay')!.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    expect(close).not.toHaveBeenCalled()
    app.unmount(); resolve({ deleted: true, id: 'a' }); await nextTick(); await nextTick()
    expect(api.remove).toHaveBeenCalledTimes(1)
  })
})
