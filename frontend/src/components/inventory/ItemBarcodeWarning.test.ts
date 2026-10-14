import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, ref, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import ItemFormModal from './ItemFormModal.vue'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getByBarcode: vi.fn(), updateItem: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: api, ocrAPI: {} }))
const item = { id: 'edited-item', name: 'Produto teste', barcode: '', sku_internal: 'QA-1',
  current_stock: 1, stock_loja: 1, stock_deposito: 0, min_stock: 0, max_stock: 0,
  cost_price: 10, sale_price: 20, currency: 'PYG', cost_currency: 'BRL', sale_currency: 'USD',
  is_active: true, created_at: '', updated_at: '', image_data: null } as InventoryItem
const other = { ...item, id: 'other-item' }
let app: App | undefined, root: HTMLDivElement
const open = ref(true)
const flush = async () => { await Promise.resolve(); await nextTick(); await Promise.resolve(); await nextTick() }
function deferred() {
  let resolve!: (value: InventoryItem[]) => void
  const promise = new Promise<InventoryItem[]>(yes => { resolve = yes })
  return { promise, resolve }
}
function button(text: string) { return Array.from(root.querySelectorAll('button')).find(b => b.textContent?.trim() === text)! }
async function stockTab() { button('Estoque').click(); await flush() }
async function mount(mode: 'edit' | 'new' | 'duplicate' = 'edit') {
  root = document.createElement('div'); document.body.append(root)
  const props = mode === 'edit' ? { item } : mode === 'duplicate'
    ? { duplicateContext: { source: item, source_version: 'a'.repeat(64), model_name: item.name, existing: [] } } : {}
  app = createApp({ setup: () => () => open.value ? h(ItemFormModal, { ...props, onClose: () => { open.value = false } }) : null })
    .use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root); await flush()
  if (mode === 'edit') await stockTab()
  if (mode === 'new') { button('Conferir dados').click(); await flush() }
}
async function setCode(value: string) {
  const input = root.querySelector<HTMLInputElement>('.barcode-row input')!
  input.value = value; input.dispatchEvent(new Event('input', { bubbles: true })); await flush()
}
async function startCode(value: string) { await setCode(value); await vi.advanceTimersByTimeAsync(500) }
function warning() { return root.querySelector('.warn-msg')?.textContent }
beforeEach(() => {
  vi.useFakeTimers(); vi.resetAllMocks(); localStorage.clear(); open.value = true
  api.getByBarcode.mockResolvedValue([]); api.updateItem.mockResolvedValue(item)
})
afterEach(() => { app?.unmount(); app = undefined; root?.remove(); vi.clearAllTimers(); vi.useRealTimers() })

describe('Barcode duplicate warning', () => {
  it('discards the previous code response in the new-item review step', async () => {
    const old = deferred(), current = deferred()
    api.getByBarcode.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    await mount('new'); await startCode('OLD'); await startCode('CURRENT')
    current.resolve([]); await flush(); old.resolve([other]); await flush()
    expect(warning()).toBeUndefined()
    expect(root.querySelector<HTMLInputElement>('.barcode-row input')?.value).toBe('CURRENT')
    expect(api.getByBarcode.mock.calls).toEqual([['OLD', false], ['CURRENT', false]])
  })

  it('counts the source as another item when duplicating and discards a response after clearing', async () => {
    const pending = deferred()
    api.getByBarcode.mockResolvedValueOnce([item]).mockReturnValueOnce(pending.promise)
    await mount('duplicate'); await startCode('SOURCE')
    expect(warning()).toContain('Este código já existe em outro item.')
    await startCode('OLD'); await setCode('')
    pending.resolve([item]); await flush()
    expect(warning()).toBeUndefined()
    expect(root.querySelector<HTMLInputElement>('.barcode-row input')?.value).toBe('')
    expect(api.getByBarcode.mock.calls).toEqual([['SOURCE', false], ['OLD', false]])
  })

  it.each([true, false])('keeps the latest result when an older response arrives last (old duplicate: %s)', async oldDuplicate => {
    const old = deferred(), current = deferred()
    api.getByBarcode.mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    await mount(); await startCode('OLD'); await startCode('CURRENT')
    expect(api.getByBarcode.mock.calls).toEqual([['OLD', false], ['CURRENT', false]])
    current.resolve(oldDuplicate ? [] : [other]); await flush()
    expect(!!warning()).toBe(!oldDuplicate)
    old.resolve(oldDuplicate ? [other] : []); await flush()
    expect(!!warning()).toBe(!oldDuplicate)
  })

  it('invalidates a pending response immediately while the replacement is still debouncing', async () => {
    const old = deferred(); api.getByBarcode.mockReturnValueOnce(old.promise)
    await mount(); await startCode('OLD'); await setCode('CURRENT')
    old.resolve([other]); await flush()
    expect(warning()).toBeUndefined()
    expect(api.getByBarcode).toHaveBeenCalledTimes(1)
  })

  it('does not accept the first A response after changing A → B → A', async () => {
    const first = deferred(), last = deferred()
    api.getByBarcode.mockReturnValueOnce(first.promise).mockResolvedValueOnce([]).mockReturnValueOnce(last.promise)
    await mount(); await startCode('A'); await startCode('B'); await startCode('A')
    last.resolve([]); await flush()
    first.resolve([other]); await flush()
    expect(warning()).toBeUndefined()
  })

  it.each([false, true])('clearing the code invalidates both debounce and response (request started: %s)', async started => {
    const pending = deferred(); api.getByBarcode.mockReturnValueOnce(pending.promise)
    await mount(); await setCode('OLD')
    if (started) await vi.advanceTimersByTimeAsync(500)
    await setCode(''); await vi.advanceTimersByTimeAsync(500)
    pending.resolve([other]); await flush()
    expect(warning()).toBeUndefined()
    expect(api.getByBarcode).toHaveBeenCalledTimes(started ? 1 : 0)
  })

  it.each([false, true])('closing and reopening discards the old lookup (request started: %s)', async started => {
    const old = deferred(), current = deferred()
    if (started) api.getByBarcode.mockReturnValueOnce(old.promise)
    api.getByBarcode.mockReturnValueOnce(current.promise)
    await mount(); await setCode('SHARED')
    if (started) await vi.advanceTimersByTimeAsync(500)
    root.querySelector<HTMLButtonElement>('[data-dialog-close]')!.click(); await flush()
    await vi.advanceTimersByTimeAsync(500)
    expect(api.getByBarcode).toHaveBeenCalledTimes(started ? 1 : 0)
    open.value = true; await flush(); await stockTab(); await startCode('SHARED')
    current.resolve([]); await flush(); old.resolve([other]); await flush()
    expect(warning()).toBeUndefined()
  })

  it('ignores the edited item itself and allows saving a code shared with another item', async () => {
    api.getByBarcode.mockResolvedValueOnce([item]).mockResolvedValueOnce([item, other])
    await mount(); await startCode('OWN'); expect(warning()).toBeUndefined()
    await startCode('SHARED'); expect(warning()).toContain('Este código já existe em outro item.')
    button('Atualizar').click(); await flush()
    expect(api.updateItem).toHaveBeenCalledWith(item.id, expect.objectContaining({ barcode: 'SHARED' }))
  })
})
