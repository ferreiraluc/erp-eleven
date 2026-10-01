import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'

const mocks = vi.hoisted(() => ({
  diagnostics: vi.fn(), getItem: vi.fn(), getGroups: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn(),
  loadItems: vi.fn(), loadAlerts: vi.fn(), listError: null as string | null,
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/services/inventoryDiagnostics', () => ({ inventoryDiagnosticsAPI: { get: mocks.diagnostics } }))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItem: mocks.getItem, getGroups: mocks.getGroups,
  getSuppliers: mocks.getSuppliers, getDistinctValues: mocks.getDistinctValues }, ocrAPI: {} }))
vi.mock('@/stores/inventory', () => ({ useInventoryStore: () => ({ items: [], filters: {}, alerts: null, loading: false, error: mocks.listError,
  pagination: { page: 1, total_pages: 1 }, loadItems: mocks.loadItems, loadAlerts: mocks.loadAlerts }) }))
vi.mock('@/components/inventory/ItemFormModal.vue', () => ({ default: {
  props: ['item'], emits: ['close'], render(this: { item: { id: string } }) { return h('div', { 'data-editor-id': this.item?.id }, 'Existing product editor') },
} }))

let app: App | undefined, container: HTMLDivElement
async function mount() {
  container = document.createElement('div'); document.body.append(container)
  const i18n = createI18n({ legacy: false, locale: 'pt', fallbackLocale: 'pt', messages: { pt: {}, es: {}, en: {} } })
  app = createApp(InventoryListView).use(i18n); app.mount(container)
  await vi.waitFor(() => expect(mocks.getDistinctValues).toHaveBeenCalled())
  await nextTick()
  return i18n
}
function button(text: string) {
  const found = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.trim() === text)
  if (!found) throw new Error(`Button missing: ${text}`)
  return found
}
async function openPanel() {
  button('Conferir estoque').click()
  await vi.waitFor(() => expect(container.querySelector('.open-product')).not.toBeNull())
}
beforeEach(() => {
  vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} unobserve() {} })
  localStorage.clear()
  mocks.listError = null
  mocks.getGroups.mockResolvedValue([]); mocks.getSuppliers.mockResolvedValue([])
  mocks.getDistinctValues.mockResolvedValue({ brands: [], categories: [] })
  mocks.loadItems.mockResolvedValue(undefined); mocks.loadAlerts.mockResolvedValue(undefined)
  mocks.getItem.mockResolvedValue({ id: 'known-item', name: 'Fixture', is_active: true })
  mocks.diagnostics.mockResolvedValue({ checked_at: '2026-10-01T10:15:00-03:00', total_active_items: 1, affected_items: 1,
    counts: { stock_mismatch: 1, negative_stock: 0, missing_stock: 0, duplicate_barcode: 0, duplicate_barcode_groups: 0 }, total_items: 1, page: 1, page_size: 25,
    items: [{ id: 'known-item', name: 'Fixture', sku_internal: 'ITEM-1', barcode: null, normalized_barcode: null, brand: null, size: null, color: null,
      current_stock: 2, stock_loja: 1, stock_deposito: 0, expected_stock: 1, delta: 1, issues: ['stock_mismatch'], duplicate_count: 0 }] })
})
afterEach(() => { app?.unmount(); container?.remove(); vi.resetAllMocks(); vi.unstubAllGlobals() })

describe('Inventory diagnostics entry point', () => {
  it('shows a translated recoverable list error instead of an empty inventory and keeps diagnostics available', async () => {
    mocks.listError = 'Internal server error from a legacy null balance'
    const i18n = await mount()
    expect(container.querySelector('.list-load-error')?.textContent).toContain('Não foi possível carregar a lista de produtos.')
    expect(container.querySelector('.empty-state')).toBeNull()
    expect(container.textContent).not.toContain('Nenhum item encontrado')
    expect(container.textContent).not.toContain('Criar primeiro item')
    expect(mocks.diagnostics).not.toHaveBeenCalled()
    const before = mocks.loadItems.mock.calls.length
    button('Tentar novamente').click()
    expect(mocks.loadItems).toHaveBeenCalledTimes(before + 1)
    expect(mocks.loadItems).toHaveBeenLastCalledWith(1, false, false)
    await openPanel()
    expect(container.querySelector('#inventory-diagnostics')).not.toBeNull()
    i18n.global.locale.value = 'es'; await nextTick()
    expect(container.querySelector('.list-load-error')?.textContent).toContain('No se pudo cargar la lista de productos.')
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('.list-load-error')?.textContent).toContain('Could not load the product list.')
  })

  it('does not fetch diagnostics until opened and loads the existing editor by item ID', async () => {
    await mount()
    expect(mocks.diagnostics).not.toHaveBeenCalled()
    await openPanel()
    expect(mocks.diagnostics).toHaveBeenCalledTimes(1)
    button('Abrir produto').click()
    await vi.waitFor(() => expect(container.querySelector('[data-editor-id="known-item"]')).not.toBeNull())
    expect(mocks.getItem).toHaveBeenCalledWith('known-item')
  })

  it('keeps diagnostics open with a recoverable product error, including legacy null balances', async () => {
    mocks.getItem.mockRejectedValueOnce(new Error('Legacy ItemResponse rejected a null balance'))
    await mount(); await openPanel(); button('Abrir produto').click()
    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')?.textContent).toContain('Não foi possível abrir esse produto'))
    expect(container.querySelector('[data-editor-id]')).toBeNull()
    expect(container.querySelector('#inventory-diagnostics')).not.toBeNull()
    button('Abrir produto').click()
    await vi.waitFor(() => expect(container.querySelector('[data-editor-id="known-item"]')).not.toBeNull())
  })

  it('ignores a product response after the operator closes diagnostics', async () => {
    let resolve!: (value: unknown) => void
    mocks.getItem.mockReturnValueOnce(new Promise(yes => { resolve = yes }))
    await mount(); await openPanel(); button('Abrir produto').click(); await nextTick()
    const close = container.querySelector('[aria-label="Fechar conferência"]') as HTMLButtonElement
    close.click(); await nextTick()
    resolve({ id: 'known-item', name: 'Late response', is_active: true }); await nextTick()
    expect(container.querySelector('#inventory-diagnostics')).toBeNull()
    expect(container.querySelector('[data-editor-id]')).toBeNull()
  })

  it('does not reopen an item deactivated since the diagnostic snapshot', async () => {
    mocks.getItem.mockResolvedValueOnce({ id: 'known-item', is_active: false })
    const i18n = await mount(); await openPanel(); button('Abrir produto').click()
    await vi.waitFor(() => expect(container.querySelector('[role="alert"]')?.textContent).toContain('foi desativado'))
    i18n.global.locale.value = 'en'; await nextTick()
    expect(container.querySelector('[role="alert"]')?.textContent).toContain('was deactivated')
    expect(container.querySelector('[data-editor-id]')).toBeNull()
  })
})
