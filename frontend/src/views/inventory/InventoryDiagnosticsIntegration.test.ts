import { chooseDropdown, openDropdown } from '@/test/dropdown'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, nextTick, reactive, type App } from 'vue'
import { createI18n } from 'vue-i18n'
import InventoryListView from './InventoryListView.vue'
import type { InventoryItem } from '@/services/api'

const mocks = vi.hoisted(() => ({
  diagnostics: vi.fn(), getItem: vi.fn(), getGroups: vi.fn(), getSuppliers: vi.fn(), getDistinctValues: vi.fn(),
  listItems: [] as InventoryItem[], loadItems: vi.fn(), loadAlerts: vi.fn(), listError: null as string | null,
  listFilters: {} as Record<string, string>, owner: false, role: 'GERENTE' as string, renameGroup: vi.fn(), ungroup: vi.fn(), groupItems: vi.fn(),
  attachItemToGrade: vi.fn(), removeFromGroup: vi.fn(), getItemGradeSuggestions: vi.fn(), getGroupItemSuggestions: vi.fn(), getGradeDirectory: vi.fn(), getGradeMembers: vi.fn(),
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ query: {} }) }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isOwner: mocks.owner, userRole: mocks.role }) }))
vi.mock('@/services/inventoryDiagnostics', () => ({ inventoryDiagnosticsAPI: { get: mocks.diagnostics } }))
vi.mock('@/services/api', () => ({ inventoryAPI: { getItem: mocks.getItem, getGroups: mocks.getGroups,
  getSuppliers: mocks.getSuppliers, getDistinctValues: mocks.getDistinctValues,
  renameGroup: mocks.renameGroup, ungroup: mocks.ungroup, groupItems: mocks.groupItems,
  attachItemToGrade: mocks.attachItemToGrade, removeFromGroup: mocks.removeFromGroup,
  getItemGradeSuggestions: mocks.getItemGradeSuggestions, getGroupItemSuggestions: mocks.getGroupItemSuggestions,
  getGradeDirectory: mocks.getGradeDirectory, getGradeMembers: mocks.getGradeMembers }, ocrAPI: {} }))
vi.mock('@/stores/inventory', () => ({ useInventoryStore: () => ({ items: mocks.listItems, filters: reactive(mocks.listFilters), alerts: null, loading: false, loadingMore: false, loadMoreError: null, hasLoaded: true, error: mocks.listError,
  pagination: { page: 1, total_pages: 1, total: mocks.listItems.length }, loadItems: mocks.loadItems, loadAlerts: mocks.loadAlerts }) }))
vi.mock('@/components/inventory/ItemFormModal.vue', () => ({ default: {
  props: ['item'], emits: ['close', 'saved'],
  setup(props: { item?: InventoryItem }, { emit }: { emit: (event: string, item?: InventoryItem) => void }) {
    return () => h('div', { 'data-editor-id': props.item?.id, 'data-editor-photo': props.item?.image_data }, [
      'Existing product editor', h('button', { onClick: () => emit('saved', props.item) }, 'Save test item'),
    ])
  },
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
  mocks.owner = false; mocks.role = 'GERENTE'; mocks.listError = null; mocks.listItems = []; mocks.listFilters = {}
  mocks.getGroups.mockResolvedValue([]); mocks.getSuppliers.mockResolvedValue([])
  mocks.getItemGradeSuggestions.mockResolvedValue({ groups: [] }); mocks.getGroupItemSuggestions.mockResolvedValue({ items: [] })
  mocks.attachItemToGrade.mockResolvedValue({ item_id: 'new-1', group_key: 'grade' })
  mocks.removeFromGroup.mockResolvedValue({ message: 'ok' })
  mocks.getGradeDirectory.mockResolvedValue({ groups: [] })
  mocks.getGradeMembers.mockResolvedValue({ items: [], total: 0, page: 1, limit: 100 })
  mocks.getDistinctValues.mockResolvedValue({ brands: [], categories: [] })
  mocks.loadItems.mockResolvedValue(undefined); mocks.loadAlerts.mockResolvedValue(undefined)
  mocks.getItem.mockResolvedValue({ id: 'known-item', name: 'Fixture', is_active: true })
  mocks.diagnostics.mockResolvedValue({ checked_at: '2026-10-01T10:15:00-03:00', total_active_items: 1, affected_items: 1,
    counts: { stock_mismatch: 1, negative_stock: 0, missing_stock: 0, duplicate_barcode: 0, duplicate_barcode_groups: 0 }, total_items: 1, page: 1, page_size: 25,
    items: [{ id: 'known-item', name: 'Fixture', sku_internal: 'ITEM-1', barcode: null, normalized_barcode: null, brand: null, size: null, color: null,
      current_stock: 2, stock_loja: 1, stock_deposito: 0, expected_stock: 1, delta: 1, issues: ['stock_mismatch'], duplicate_count: 0 }] })
})
afterEach(() => { app?.unmount(); container?.remove(); vi.useRealTimers(); vi.resetAllMocks(); vi.unstubAllGlobals() })

describe('Inventory empty search recovery', () => {
  it('clears an unmatched search and combined filters once, without opening a product form', async () => {
    mocks.listFilters = { brand: 'Fixture', category: 'shirts', location_stock: 'loja', status: 'low_stock' }
    await mount()
    vi.useFakeTimers()
    const search = container.querySelector<HTMLInputElement>('.search-input')!
    search.value = 'no-match'; search.dispatchEvent(new Event('input', { bubbles: true }))
    await nextTick(); await vi.advanceTimersByTimeAsync(300)
    expect(container.querySelector('.empty-state')?.textContent).toContain('Limpar Filtros')
    expect(container.querySelector('.empty-state')?.textContent).not.toContain('Criar primeiro item')
    const before = mocks.loadItems.mock.calls.length
    button('Limpar Filtros').click()
    await nextTick(); await vi.advanceTimersByTimeAsync(300)
    expect(search.value).toBe('')
    expect(Object.values(mocks.listFilters).every(value => value === '')).toBe(true)
    expect(mocks.loadItems).toHaveBeenCalledTimes(before + 1)
    expect(mocks.loadItems).toHaveBeenLastCalledWith(1, false, false)
    expect(container.querySelector('[data-editor-id]')).toBeNull()
  })

  it('preserves grouped view when resetting filters and offers normal creation for an unfiltered empty list', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    mocks.listFilters = { search: 'no-match' }
    await mount()
    button('Limpar Filtros').click()
    await nextTick()
    expect(mocks.loadItems).toHaveBeenLastCalledWith(1, false, true)
    expect(mocks.getGroups).toHaveBeenLastCalledWith({})
    expect(localStorage.getItem('inv_group_mode')).toBe('true')
    await vi.waitFor(() => expect(container.querySelector('.empty-state')?.textContent).not.toContain('Criar primeiro item'))
  })
})

describe('Grouped stock refresh', () => {
  it('updates the grade total and size count after an item edit', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    const item = { id: 'size-s', sku_internal: 'INV-ABC123', name: 'Camiseta S', size: 'S', group_key: 'grade-1',
      current_stock: 1, stock_loja: 1, stock_deposito: 0, sale_price: 0, is_active: true, alert_level: 'ok' } as InventoryItem
    mocks.getGroups.mockResolvedValueOnce([{ group_key: 'grade-1', total_stock: 1, items: [item] }])
      .mockResolvedValue([{ group_key: 'grade-1', total_stock: 4, items: [{ ...item, current_stock: 4, stock_loja: 4 }] }])
    await mount()
    expect(container.querySelector('.group-total-stock')?.textContent).toContain('1')
    container.querySelector<HTMLElement>('.size-chip .chip-label')!.click()
    await nextTick()
    button('Save test item').click()
    await vi.waitFor(() => expect(container.querySelector('.group-total-stock')?.textContent).toContain('4'))
    expect(container.querySelector('.size-chip .chip-label')?.textContent).toContain('4')
    expect(mocks.getGroups).toHaveBeenCalledTimes(2)
  })

  it('restores saved category filters and selects only uncategorized grade members for bulk editing', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    mocks.listFilters = { category: '__uncategorized__', brand: 'Boss', location_stock: 'loja' }
    const item = { id: 'uncategorized', sku_internal: 'INV-UNC123', name: 'Camiseta sem categoria',
      category: undefined, group_key: 'grade-1', current_stock: 1, stock_loja: 1, stock_deposito: 0,
      sale_price: 0, is_active: true, alert_level: 'ok' } as InventoryItem
    mocks.getGroups.mockResolvedValue([{ group_key: 'grade-1', total_stock: 2, items: [
      item, { ...item, id: 'categorized', name: 'Camiseta categorizada', category: 'Camisetas' },
    ] }])
    await mount()
    expect(document.querySelector('[aria-label="Categoria"]')?.textContent).toContain('Sem categoria')
    expect(mocks.getGroups).toHaveBeenLastCalledWith({ category: '__uncategorized__', brand: 'Boss', location_stock: 'loja' })
    button('Selecionar').click(); await nextTick()
    document.querySelector<HTMLButtonElement>('[aria-label^="Selecionar grade"]')!.click(); await nextTick()
    expect(container.querySelector('.sel-count')?.textContent).toContain('1')
    Array.from(container.querySelectorAll<HTMLButtonElement>('.selection-bar button')).find(button => button.textContent?.includes('Sel. todos'))!.click(); await nextTick()
    expect(container.querySelector('.sel-count')?.textContent).toContain('1')
    Array.from(container.querySelectorAll<HTMLButtonElement>('.selection-bar button')).find(button => button.textContent?.includes('Editar massivo'))!.click(); await nextTick()
    expect(document.querySelectorAll('.modal-container .items-list .item-card')).toHaveLength(1)
    expect(document.querySelector('.modal-container .items-list')?.textContent).toContain('Camiseta sem categoria')
    expect(document.querySelector('.modal-container .items-list')?.textContent).not.toContain('Camiseta categorizada')
  })
})

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


describe('Unknown stock list and group rendering', () => {
  const missing = { id: 'missing', name: 'Missing balance', current_stock: null, stock_loja: null, stock_deposito: 0,
    sale_price: 0, is_active: true, alert_level: 'unknown' } as InventoryItem
  const zero = { ...missing, id: 'zero', name: 'Zero balance', current_stock: 0, stock_loja: 0, alert_level: 'out' }

  it('renders missing separately from zero and blocks movements while preserving edit access', async () => {
    localStorage.setItem('inv_view', 'list'); mocks.listItems = [missing, zero]
    const i18n = await mount()
    const rows = container.querySelectorAll('.item-list-row')
    expect(rows).toHaveLength(2)
    expect(rows[0].querySelector('.list-stock')?.textContent).toContain('L:— D:0')
    expect(rows[0].querySelector('.list-stock')?.textContent).toContain('Revisar estoque')
    expect(rows[1].querySelector('.list-stock')?.textContent).toContain('L:0 D:0')
    expect(rows[1].querySelector('.list-stock')?.textContent).not.toContain('Revisar estoque')
    expect(container.querySelector('.exit-btn')).toBeNull()
    expect((rows[0].querySelector('.move-btn') as HTMLButtonElement).disabled).toBe(true)
    expect((rows[1].querySelector('.move-btn') as HTMLButtonElement).disabled).toBe(false)
    ;(rows[0].querySelector('.edit-btn') as HTMLButtonElement).click(); await nextTick()
    expect(container.querySelector('[data-editor-id="missing"]')).not.toBeNull()
    i18n.global.locale.value = 'en'; await nextTick()
    expect(rows[0].querySelector('.list-stock')?.textContent).toContain('Review stock')
    expect(mocks.diagnostics).not.toHaveBeenCalled()
  })

  it('does not add missing group totals as zero and keeps known zero totals visible', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    mocks.getGroups.mockResolvedValue([
      { group_key: 'Missing', total_stock: null, items: [missing] },
      { group_key: 'Zero', total_stock: 0, items: [zero] },
    ])
    await mount()
    const totals = container.querySelectorAll('.group-total-stock')
    expect(Array.from(totals).map(el => el.textContent?.trim())).toEqual(['Total: —', 'Total: 0'])
    expect(totals[0].getAttribute('title')).toBe('Não informado')
    expect(container.querySelector('.badge-unknown')?.textContent).toBe('Revisar estoque')
    expect(container.textContent).not.toContain('NaN')
  })
})


describe('Inventory selection', () => {
  const item = { id: 'visible', name: 'Produto visível', current_stock: 1, stock_loja: 1, stock_deposito: 0,
    sale_price: 0, is_active: true, alert_level: 'ok', group_key: 'grade-real' } as InventoryItem
  it.each([false, true])('exposes deletion only for owner=%s and selects only the visible catalog', async owner => {
    mocks.owner = owner
    mocks.listItems = [item]
    mocks.getGroups.mockResolvedValue([{group_key:'hidden',total_stock:1,items:[{...item,id:'hidden'}]}])
    await mount(); button('Selecionar').click(); await nextTick()
    container.querySelector<HTMLElement>('[data-item-id="visible"]')!.click(); await nextTick()
    Array.from(container.querySelectorAll<HTMLButtonElement>('.sel-actions button')).find(b => b.querySelector('.sel-label-full')?.textContent === 'Sel. todos')!.click(); await nextTick()
    expect(container.querySelector('.sel-count')?.textContent).toContain('Itens selecionados: 1')
    const deletion = Array.from(container.querySelectorAll('button')).find(b => b.textContent?.trim() === 'Excluir')
    expect(Boolean(deletion)).toBe(owner)
    expect(container.querySelector('.card-grade-label')?.textContent).toContain('Grade 1')
    expect(container.querySelector('[data-item-id="visible"]')?.getAttribute('data-grade-key')).toBe('grade-real')
  })
})


describe('Readable automatic grade names', () => {
  const keyA = 'grade-40dd6437-f51a-4b54-9d8d-f543e8705c16'
  const keyB = 'grade-3c340751-7041-4cab-a20d-296e3394c3f5'
  const item = { id: 'original', name: 'Tênis Givenchy DN0281 11', size: '11', created_at: '2026-10-01T10:00:00Z',
    current_stock: 1, stock_loja: 1, stock_deposito: 0, sale_price: 0, is_active: true, alert_level: 'ok' } as InventoryItem
  function groups() {
    mocks.getGroups.mockResolvedValue([
      { group_key: keyA, total_stock: 1, items: [{ ...item, group_key: keyA }] },
      { group_key: keyB, total_stock: 1, items: [{ ...item, id: 'other', group_key: keyB }] },
    ])
    mocks.getGradeDirectory.mockResolvedValue({ groups: [
      { group_key: keyA, display_name: 'Tênis Givenchy DN0281', member_count: 1 },
      { group_key: keyB, display_name: 'Tênis Givenchy DN0281', member_count: 1 },
    ] })
  }
  it('shows model titles but keeps equally named grades separate and does not rename on unchanged Enter/blur', async () => {
    localStorage.setItem('inv_group_mode', 'true'); groups(); await mount()
    expect(Array.from(container.querySelectorAll('.group-name')).map(el => el.textContent?.trim())).toEqual([
      'Tênis Givenchy DN0281', 'Tênis Givenchy DN0281',
    ])
    const cards = container.querySelectorAll<HTMLElement>('.group-card')
    cards[0].click(); await nextTick()
    expect(cards[0].querySelector('.group-exp-section')).not.toBeNull()
    expect(cards[1].querySelector('.group-exp-section')).toBeNull()
    cards[1].querySelector<HTMLElement>('.group-name')!.click(); await nextTick()
    const input = cards[1].querySelector<HTMLInputElement>('.group-name-input')!
    expect(input.value).toBe('Tênis Givenchy DN0281')
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    input.dispatchEvent(new FocusEvent('blur')); await nextTick()
    expect(mocks.renameGroup).not.toHaveBeenCalled()
    expect(container.textContent).not.toContain('grade-')
  })
  it('renames once using the exact internal key, and cancels Escape without a write', async () => {
    localStorage.setItem('inv_group_mode', 'true'); groups(); await mount()
    container.querySelector<HTMLElement>('.group-name')!.click(); await nextTick()
    let input = container.querySelector<HTMLInputElement>('.group-name-input')!
    input.value = 'Cancelado'; input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    input.dispatchEvent(new FocusEvent('blur')); await nextTick()
    expect(mocks.renameGroup).not.toHaveBeenCalled()
    container.querySelector<HTMLElement>('.group-name')!.click(); await nextTick()
    input = container.querySelector<HTMLInputElement>('.group-name-input')!
    input.value = 'Givenchy DN0281 Branco'; input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }))
    input.dispatchEvent(new FocusEvent('blur')); await nextTick()
    expect(mocks.renameGroup).toHaveBeenCalledExactlyOnceWith(keyA, 'Givenchy DN0281 Branco')
  })
  it('uses readable tooltips and lets users choose the exact existing grade by name', async () => {
    groups()
    mocks.listItems = [{ ...item, group_key: keyA }, { ...item, id: 'new-1' }, { ...item, id: 'new-2' }]
    await mount()
    expect(container.querySelector('.card-grade-label')?.getAttribute('title')).toBe('Tênis Givenchy DN0281')
    button('Selecionar').click(); await nextTick()
    for (const id of ['new-1', 'new-2']) {
      container.querySelector<HTMLElement>(`[data-item-id="${id}"]`)!.click(); await nextTick()
    }
    button('+ Grades').click(); await nextTick()
    await vi.waitFor(() => expect(mocks.getGradeDirectory).toHaveBeenCalledWith(''))
    const select = document.querySelector<HTMLButtonElement>('[aria-label="Grade de destino"]')!
    const choices = (await openDropdown(select)).map(option => option.textContent)
    expect(choices[0]).toBe('Criar uma nova grade')
    expect(choices[1]).toContain('Tênis Givenchy DN0281')
    expect(choices[2]).toContain('Tênis Givenchy DN0281')
    expect(choices[1]).not.toBe(choices[2])
    await chooseDropdown(select, keyB)
    const confirm = Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(b => b.textContent?.trim() === 'Agrupar 2')!
    confirm.click(); await nextTick()
    expect(mocks.groupItems).toHaveBeenCalledExactlyOnceWith(['new-1', 'new-2'], keyB)
    expect(document.body.textContent).not.toContain('grade-')
  })
  it('keeps manual group titles and confirms before ungrouping the whole grade', async () => {
    localStorage.setItem('inv_group_mode', 'true')
    mocks.getGroups.mockResolvedValue([{ group_key: 'Coleção DN0281', total_stock: 1, items: [item] }])
    mocks.getGradeMembers.mockResolvedValue({ items: [item], total: 1, page: 1, limit: 100 })
    await mount()
    expect(container.querySelector('.group-name')?.textContent?.trim()).toBe('Coleção DN0281')
    container.querySelector<HTMLButtonElement>('.group-manage-btn')!.click(); await nextTick()
    const ungroup = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button')).find(node => node.textContent?.trim() === 'Desagrupar toda a grade')!
    await vi.waitFor(() => expect(ungroup.disabled).toBe(false))
    ungroup.click(); await nextTick()
    expect(mocks.ungroup).not.toHaveBeenCalled()
    const confirm = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button')).find(node => node.textContent?.trim() === 'Confirmar')!
    confirm.click(); await nextTick()
    expect(mocks.ungroup).toHaveBeenCalledExactlyOnceWith('Coleção DN0281')
  })
  it('shows a static grade title and no membership actions to a seller', async () => {
    mocks.role = 'VENDEDOR'
    localStorage.setItem('inv_group_mode', 'true')
    mocks.getGroups.mockResolvedValue([{ group_key: keyA, total_stock: 1, items: [{ ...item, group_key: keyA }] }])
    await mount()
    expect(container.querySelector('.group-name')?.textContent?.trim()).toBe('Tênis Givenchy DN0281')
    expect(container.querySelector('.group-name-editable')).toBeNull()
    expect(container.querySelector('.group-manage-btn')).toBeNull()
    expect(container.querySelector('.chip-remove')).toBeNull()
    button('Selecionar').click(); await nextTick()
    expect(Array.from(container.querySelectorAll('button')).some(button => button.textContent?.trim() === '+ Grades')).toBe(false)
    expect(mocks.getGroupItemSuggestions).not.toHaveBeenCalled()
  })
  it('opens grade management for one selected standalone item and links it to an existing grade', async () => {
    mocks.getGroups.mockResolvedValue([{ group_key: keyA, total_stock: 1, items: [{ ...item, group_key: keyA }] }])
    mocks.getGradeDirectory.mockResolvedValue({ groups: [{ group_key: keyA, display_name: 'Tênis Givenchy DN0281', member_count: 1 }] })
    mocks.listItems = [{ ...item, id: 'new-1', group_key: null }]
    await mount()
    button('Selecionar').click(); await nextTick()
    container.querySelector<HTMLElement>('[data-item-id="new-1"]')!.click(); await nextTick()
    button('+ Grades').click(); await nextTick()
    expect(document.body.querySelector('.grade-manager')).not.toBeNull()
    await vi.waitFor(() => expect(mocks.getItemGradeSuggestions).toHaveBeenCalledWith('new-1'))
    await vi.waitFor(() => expect(mocks.getGradeDirectory).toHaveBeenCalledWith(''))
    const destination = Array.from(document.body.querySelectorAll<HTMLButtonElement>('.grade-manager-option'))
      .find(node => node.textContent?.includes('Tênis Givenchy DN0281'))!
    destination.click(); await nextTick()
    expect(mocks.attachItemToGrade).not.toHaveBeenCalled()
    const confirm = Array.from(document.body.querySelectorAll<HTMLButtonElement>('button'))
      .find(node => node.textContent?.trim() === 'Vincular à grade')!
    confirm.click(); await nextTick()
    expect(mocks.attachItemToGrade).toHaveBeenCalledExactlyOnceWith('new-1', keyA, null)
  })
  it('opens grade management for one grouped item and confirms removal of its link', async () => {
    mocks.listItems = [{ ...item, id: 'grouped-1', group_key: keyA }]
    await mount()
    button('Selecionar').click(); await nextTick()
    container.querySelector<HTMLElement>('[data-item-id="grouped-1"]')!.click(); await nextTick()
    button('+ Grades').click(); await nextTick()
    expect(document.body.querySelector('.grade-manager')).not.toBeNull()
    expect(document.body.textContent).toContain('Grade atual:')
    const remove = Array.from(document.body.querySelectorAll<HTMLButtonElement>('.grade-manager button'))
      .find(node => node.textContent?.trim() === 'Remover da grade')!
    remove.click(); await nextTick()
    expect(mocks.removeFromGroup).not.toHaveBeenCalled()
    const confirm = Array.from(document.body.querySelectorAll<HTMLButtonElement>('.grade-manager button'))
      .find(node => node.textContent?.trim() === 'Confirmar')!
    confirm.click(); await nextTick()
    expect(mocks.removeFromGroup).toHaveBeenCalledExactlyOnceWith('grouped-1', keyA)
  })
  it('confirms transfer from the current grade to a suggested grade', async () => {
    mocks.listItems = [{ ...item, id: 'grouped-1', group_key: keyA }]
    mocks.getItemGradeSuggestions.mockResolvedValue({ groups: [
      { group_key: keyB, display_name: 'Tênis Givenchy DN0281 outra cor', member_count: 2, match_reason: 'same_model' },
    ] })
    await mount()
    button('Selecionar').click(); await nextTick()
    container.querySelector<HTMLElement>('[data-item-id="grouped-1"]')!.click(); await nextTick()
    button('+ Grades').click(); await nextTick()
    await vi.waitFor(() => expect(document.body.textContent).toContain('Tênis Givenchy DN0281 outra cor'))
    const destination = Array.from(document.body.querySelectorAll<HTMLButtonElement>('.grade-manager-option'))
      .find(node => node.textContent?.includes('Tênis Givenchy DN0281 outra cor'))!
    destination.click(); await nextTick()
    expect(mocks.attachItemToGrade).not.toHaveBeenCalled()
    const confirm = Array.from(document.body.querySelectorAll<HTMLButtonElement>('.grade-manager button'))
      .find(node => node.textContent?.trim() === 'Confirmar transferência')!
    confirm.click(); await nextTick()
    expect(mocks.attachItemToGrade).toHaveBeenCalledExactlyOnceWith('grouped-1', keyB, keyA)
  })
  it('opens management of the shared grade when two selected items belong to it', async () => {
    mocks.listItems = [
      { ...item, id: 'grouped-1', group_key: keyA },
      { ...item, id: 'grouped-2', group_key: keyA },
    ]
    mocks.getGradeMembers.mockResolvedValue({ items: mocks.listItems, total: 2, page: 1, limit: 100 })
    await mount()
    button('Selecionar').click(); await nextTick()
    for (const id of ['grouped-1', 'grouped-2']) {
      container.querySelector<HTMLElement>(`[data-item-id="${id}"]`)!.click(); await nextTick()
    }
    button('+ Grades').click(); await nextTick()
    expect(document.body.querySelector('.grade-manager')).not.toBeNull()
    await vi.waitFor(() => expect(mocks.getGradeMembers).toHaveBeenCalledWith(keyA, 1))
    expect(document.body.textContent).toContain('Peças desta grade')
    expect(document.body.textContent).toContain('2/2')
    expect(mocks.groupItems).not.toHaveBeenCalled()
  })
})


describe('Editing a lightweight catalog item', () => {
  it('loads the original before opening the form so saving or duplicating cannot erase the photo', async () => {
    mocks.listItems = [{ id: 'photo-item', name: 'Fixture', has_image: true, image_data: null, is_active: true } as InventoryItem]
    let resolve!: (value: unknown) => void
    mocks.getItem.mockReturnValueOnce(new Promise(yes => { resolve = yes }))
    await mount(); button('Editar').click(); await nextTick()
    expect(container.querySelector('[data-editor-id]')).toBeNull()
    expect(mocks.getItem).toHaveBeenCalledWith('photo-item')
    resolve({ ...mocks.listItems[0], image_data: 'data:image/jpeg;base64,original' })
    await vi.waitFor(() => expect(container.querySelector('[data-editor-photo]')?.getAttribute('data-editor-photo')).toBe('data:image/jpeg;base64,original'))
  })
  it('keeps the form closed if the original cannot be loaded', async () => {
    mocks.listItems = [{ id: 'photo-item', name: 'Fixture', has_image: true, is_active: true } as InventoryItem]
    mocks.getItem.mockRejectedValueOnce(new Error('offline'))
    await mount(); button('Editar').click()
    await vi.waitFor(() => expect(container.textContent).toContain('Não foi possível abrir o produto'))
    expect(container.querySelector('[data-editor-id]')).toBeNull()
  })
})
