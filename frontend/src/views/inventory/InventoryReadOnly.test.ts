import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import { createPinia } from 'pinia'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'
import ItemFormModal from '@/components/inventory/ItemFormModal.vue'
import MovementModal from '@/components/inventory/MovementModal.vue'
import type { InventoryItem } from '@/services/api'

const api = vi.hoisted(() => ({ getItems: vi.fn(), getGroups: vi.fn(), getSuggestions: vi.fn(), getAlertsSummary: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn(), getItemPhotos: vi.fn(), getByBarcode: vi.fn(), updateItem: vi.fn(), createItem: vi.fn(), createMovement: vi.fn(), createBatchMovement: vi.fn(), removeFromGroup: vi.fn() }))
const auth = vi.hoisted(() => ({ userRole: 'VENDEDOR', isOwner: false, isReseller: true }))
const route = vi.hoisted(() => ({ query: {} as Record<string, string> }))
vi.mock('@/services/api', () => ({ inventoryAPI: api, ocrAPI: {} }))
vi.mock('vue-router', () => ({ useRoute: () => route, useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => auth }))
let app: App | undefined, root: HTMLDivElement
const item = { id: 'item-a', name: 'Camiseta Azul', description: 'Peça de algodão', size: 'M', color: 'Blue', barcode: '', sku_internal: 'QA-1',
  current_stock: 3, stock_loja: 1, stock_deposito: 2, reserved_loja: 1, min_stock: 0, max_stock: 0,
  cost_price: 10, sale_price: 20, currency: 'PYG', cost_currency: 'BRL', sale_currency: 'USD',
  is_active: true, created_at: '', updated_at: '', image_data: null } as InventoryItem
const flush = async () => { for (let i=0; i<12; i++) { await Promise.resolve(); await nextTick() } }
async function mount(component: any, props = {}) {
  root = document.createElement('div'); document.body.append(root)
  app = createApp(component, props).use(createPinia()).use(createI18n({ legacy: false, locale: 'pt', messages: { pt: {} } }))
  app.mount(root); await flush()
  return (app as any)._instance.setupState
}
function button(label: string) { return Array.from(root.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === label)! }
beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); route.query = {}; auth.isReseller = true
  vi.stubGlobal('IntersectionObserver', class { observe() {} disconnect() {} unobserve() {} })
  api.getItems.mockResolvedValue({ items: [item], page: 1, page_size: 50, total: 1, total_pages: 1 })
  api.getGroups.mockResolvedValue([]); api.getSuggestions.mockResolvedValue([]); api.getAlertsSummary.mockResolvedValue(null)
  api.getSuppliers.mockResolvedValue([]); api.getDistinctValues.mockResolvedValue({ brands: [], categories: [] })
  api.getItemPhotos.mockResolvedValue({ additional_images: [] }); api.getByBarcode.mockResolvedValue([])
})
afterEach(() => { app?.unmount(); app=undefined; root?.remove(); vi.unstubAllGlobals(); vi.restoreAllMocks() })

describe('reseller inventory consultation', () => {
  it('preserves search, filters and selection but blocks creation, bulk operations and print before any API call', async () => {
    route.query.new='1'
    const state = await mount(InventoryListView)
    expect(root.querySelector('.modal-container')).toBeNull()
    expect(button('Novo item').disabled).toBe(true)
    button('Filtros').click(); await flush()
    expect(root.querySelector<HTMLElement>('#inventory-filter-panel')?.style.display).not.toBe('none')
    button('Selecionar').click(); await flush()
    root.querySelector<HTMLElement>('[data-item-id="item-a"]')!.click(); await flush()
    expect(root.querySelector('.sel-count')?.textContent).toContain('1')
    for (const text of ['Imprimir lista', 'Imprimir etiquetas', 'Vincular a lote', '+ Grades']) expect(button(text)?.disabled).toBe(true)
    for (const action of ['openCreate','openBulkEdit','openBulkTransfer','openBulkDelete','confirmGroup']) await state[action]()
    await state.removeItemFromGroup(item.id, 'Grade')
    await flush()
    expect(root.querySelector('.modal-container, .gmodal')).toBeNull()
    expect(api.removeFromGroup).not.toHaveBeenCalled()
    expect(root.querySelector('a.reserved-count')).toBeNull()
  })

  it('opens Edit and Move normally with read-only props and keeps stock by location visible', async () => {
    await mount(InventoryListView)
    root.querySelector<HTMLButtonElement>('[aria-label="Editar Camiseta Azul"]')!.click(); await flush()
    expect(root.querySelector('fieldset.readonly-fields')?.hasAttribute('disabled')).toBe(true)
    expect(button('Histórico').disabled).toBe(true)
    expect(button('Atualizar').disabled).toBe(true)
    button('Cancelar').click(); await flush()
    root.querySelector<HTMLButtonElement>('[aria-label="Movimentar Camiseta Azul"]')!.click(); await flush()
    expect(root.querySelector('.item-stock-row')?.textContent).toContain('Depósito: 2')
    expect(root.querySelector('fieldset.movement-fields')?.hasAttribute('disabled')).toBe(true)
    expect(button('Registrar').disabled).toBe(true)
  })

  it('guards product save/history/photo handlers in addition to disabled controls, leaving tabs and photos usable', async () => {
    const state = await mount(ItemFormModal, { item, readOnly: true, canCreateVariants: true })
    await state.handleSubmit(); state.openHistory('movements'); state.openProductPhoto(true); await state.openDuplicate(); await flush()
    expect(api.updateItem).not.toHaveBeenCalled(); expect(api.createItem).not.toHaveBeenCalled()
    expect(root.querySelector('.history-overlay')).toBeNull()
    expect(state.showProductPhoto).toBe(false); expect(state.duplicateDraft).toBeNull()
    button('Foto').click(); await flush()
    expect(button('Editar foto').closest('fieldset')?.disabled).toBe(true)
    expect(root.querySelector<HTMLInputElement>('.product-gallery input[type=file]')?.disabled).toBe(true)
    expect(button('＋ Adicionar fotos').disabled).toBe(true)
  })

  it('guards stock mutations even if submission is invoked directly, without emitting success', async () => {
    const saved = vi.fn(), state = await mount(MovementModal, { item, readOnly: true, onSaved: saved })
    await state.handleSubmit(); state.batchMode = true; await state.handleSubmit()
    expect(api.createMovement).not.toHaveBeenCalled(); expect(api.createBatchMovement).not.toHaveBeenCalled(); expect(saved).not.toHaveBeenCalled()
  })
})
