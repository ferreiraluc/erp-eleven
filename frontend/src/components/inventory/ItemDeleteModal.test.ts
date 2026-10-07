import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ItemDeleteModal from './ItemDeleteModal.vue'
const api = vi.hoisted(() => ({ preview: vi.fn(), remove: vi.fn(), preserveHistory: vi.fn() }))
vi.mock('@/services/inventoryDeletion', () => ({ inventoryDeletionAPI: api }))
const preview = { allowed: true, blockers: [], movement_count: 1, plan_token: 'reviewed-token',
  item: { id: 'product', name: 'Camiseta Teste', sku_internal: 'SKU-TESTE', size: 'M', color: 'Branco', stock_loja: 2, stock_deposito: 0, current_stock: 2 } }
let app: App, root: HTMLDivElement
async function mount(props = {}) {
  root = document.createElement('div'); document.body.append(root)
  const i18n = createI18n({ legacy: false, locale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(ItemDeleteModal, { itemId: 'product', ...props }).use(i18n); app.mount(root)
  await vi.waitFor(() => expect(root.textContent).not.toContain('Conferindo vínculos'))
  return i18n
}
function button(text: string) { return Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === text)! }
async function approve() { const check = root.querySelector('input')!; check.checked = true; check.dispatchEvent(new Event('change', { bubbles: true })); await nextTick() }
beforeEach(() => { vi.resetAllMocks(); api.preview.mockResolvedValue(preview); api.remove.mockResolvedValue({ deleted: true, id: 'product' }) })
afterEach(() => { app?.unmount(); root?.remove() })
describe('Permanent product deletion', () => {
  it('requires review, shows the exact variant and sends its reviewed token once', async () => {
    const deleted = vi.fn(); const i18n = await mount({ onDeleted: deleted })
    expect(root.textContent).toContain('SKU-TESTE'); expect(root.textContent).toContain('M · Branco')
    expect(button('Excluir definitivamente').disabled).toBe(true)
    await approve(); button('Excluir definitivamente').click(); button('Excluir definitivamente').click()
    await vi.waitFor(() => expect(deleted).toHaveBeenCalledWith('product'))
    expect(api.remove).toHaveBeenCalledTimes(1)
    expect(api.remove).toHaveBeenCalledWith('product', { sku: 'SKU-TESTE', plan_token: 'reviewed-token', confirm: true })
    i18n.global.locale.value = 'es'; await nextTick(); expect(root.textContent).toContain('Eliminar producto definitivamente')
    i18n.global.locale.value = 'en'; await nextTick(); expect(root.textContent).toContain('Permanently delete product')
  })
  it('shows operational blockers without offering deletion', async () => {
    api.preview.mockResolvedValue({ ...preview, allowed: false, plan_token: null, blockers: [{ code: 'sales', count: 1 }] })
    await mount(); expect(root.textContent).toContain('Vendas, inclusive canceladas: 1')
    expect(button('Excluir definitivamente')).toBeUndefined(); expect(root.querySelector('input')).toBeNull()
    expect(api.remove).not.toHaveBeenCalled()
  })
  it('does not delete if checking failed, and requires another review after a stale confirmation', async () => {
    api.preview.mockRejectedValueOnce(new Error('offline'))
    const deleted = vi.fn(); await mount({ onDeleted: deleted })
    expect(button('Excluir definitivamente')).toBeUndefined()
    button('Conferir novamente').click(); await vi.waitFor(() => expect(root.querySelector('input')).not.toBeNull())
    api.remove.mockRejectedValueOnce({ response: { data: { detail: 'O produto mudou ou a confirmação não corresponde. Confira novamente antes de excluir.' } } })
    await approve(); button('Excluir definitivamente').click()
    await vi.waitFor(() => expect(root.textContent).toContain('O produto mudou'))
    expect(deleted).not.toHaveBeenCalled(); expect(button('Excluir definitivamente')).toBeUndefined()
    button('Conferir novamente').click(); await vi.waitFor(() => expect(root.querySelector('input')).not.toBeNull())
    expect((root.querySelector('input') as HTMLInputElement).checked).toBe(false)
    expect(api.remove).toHaveBeenCalledTimes(1)
  })
  it('offers a separately confirmed catalog removal for linked products and keeps the physical deletion blocked', async () => {
    api.preview.mockResolvedValue({ ...preview, allowed:false, plan_token:null, preserve_history_token:'history-token', blockers:[{code:'sales',count:2}] })
    api.preserveHistory.mockResolvedValue({deleted:true,id:'product',history_preserved:true})
    const deleted=vi.fn();await mount({onDeleted:deleted})
    expect(button('Excluir definitivamente')).toBeUndefined()
    expect(button('Excluir e manter histórico').disabled).toBe(true)
    await approve();button('Excluir e manter histórico').click();button('Excluir e manter histórico').click()
    await vi.waitFor(()=>expect(deleted).toHaveBeenCalledWith('product'))
    expect(api.preserveHistory).toHaveBeenCalledTimes(1)
    expect(api.preserveHistory).toHaveBeenCalledWith('product',{sku:'SKU-TESTE',plan_token:'history-token',confirm:true})
    expect(api.remove).not.toHaveBeenCalled()
  })
})
