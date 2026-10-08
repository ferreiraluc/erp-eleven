import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useInventoryStore } from './inventory'
import type { InventoryItem } from '@/services/api'
import { UNKNOWN_STOCK_MESSAGE } from '@/services/inventoryStock'
const api = vi.hoisted(() => ({ getItems: vi.fn(), quickExit: vi.fn(), createMovement: vi.fn(), createBatchMovement: vi.fn(), updateItem: vi.fn() }))
vi.mock('@/services/api', () => ({ inventoryAPI: api }))
const item = { id: 'missing', name: 'Fixture', current_stock: null, stock_loja: null, stock_deposito: 0, alert_level: 'out' } as InventoryItem
beforeEach(() => { vi.resetAllMocks(); setActivePinia(createPinia()) })
it('does not restore a permanently deleted item from an older list response', async () => {
  const store = useInventoryStore()
  let resolve!: (value: unknown) => void
  api.getItems.mockReturnValue(new Promise(done => { resolve = done }))
  store.items = [item]; store.currentItem = item
  const loading = store.loadItems()
  store.forgetDeletedItem(item.id)
  resolve({ items: [item], total: 1, page: 1, page_size: 50, total_pages: 1 }); await loading
  expect(store.items).toEqual([]); expect(store.currentItem).toBeNull()
})
describe('Inventory store with missing balances', () => {
  it('preserves nulls while loading the unknown-stock filter and excludes them from low/out lists', async () => {
    const store = useInventoryStore()
    store.filters.status = 'unknown_stock'
    api.getItems.mockResolvedValue({ items: [item, { ...item, id: 'low', alert_level: 'low' }], total: 2, page: 1, page_size: 50, total_pages: 1 })
    await store.loadItems()
    expect(api.getItems).toHaveBeenCalledWith(expect.objectContaining({ status: 'unknown_stock' }))
    expect(store.items[0].current_stock).toBeNull()
    expect(store.items[0].stock_deposito).toBe(0)
    expect(store.lowStockItems).toEqual([])
    expect(store.outOfStockItems).toEqual([])
  })
  it('guards all cached movement entry points before calling the API', async () => {
    const store = useInventoryStore(); store.items = [item]
    await expect(store.quickExit(item.id)).rejects.toThrow(UNKNOWN_STOCK_MESSAGE)
    await expect(store.createMovement({ item_id: item.id, quantity: 1 })).rejects.toThrow(UNKNOWN_STOCK_MESSAGE)
    await expect(store.createBatchMovement({ items: [{ item_id: item.id, quantity: 1 }] })).rejects.toThrow(UNKNOWN_STOCK_MESSAGE)
    expect(api.quickExit).not.toHaveBeenCalled()
    expect(api.createMovement).not.toHaveBeenCalled()
    expect(api.createBatchMovement).not.toHaveBeenCalled()
  })
  it('preserves missing balances after a metadata update', async () => {
    const store = useInventoryStore(); store.items = [item]
    api.updateItem.mockResolvedValue({ ...item, name: 'Renamed' })
    await store.updateItem(item.id, { name: 'Renamed' })
    expect(store.items[0].name).toBe('Renamed')
    expect(store.items[0].current_stock).toBeNull()
    expect(store.items[0].stock_loja).toBeNull()
    expect(store.items[0].stock_deposito).toBe(0)
    expect(api.updateItem).toHaveBeenCalledWith(item.id, { name: 'Renamed' })
  })
})

function deferred() {
  let resolve!: (value: unknown) => void, reject!: (reason: unknown) => void
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const page = (ids: string[], n = 1, total = 3) => ({ items: ids.map(id => ({ ...item, id })), total, page: n, page_size: 2, total_pages: Math.ceil(total / 2) })

describe('Search and infinite-scroll progress', () => {
  it('tracks the full result count and preserves loaded items/count on an append failure, then retries that same page', async () => {
    const store = useInventoryStore()
    api.getItems.mockResolvedValueOnce(page(['a', 'b']))
    await store.loadItems()
    expect(store.hasLoaded).toBe(true); expect(store.pagination.total).toBe(3)
    expect(api.getItems).toHaveBeenCalledWith(expect.objectContaining({ include_images: false }))
    const next = deferred(); api.getItems.mockReturnValueOnce(next.promise)
    const loading = store.loadItems(2, true)
    expect(store.loadingMore).toBe(true); expect(store.hasLoaded).toBe(true)
    next.reject(new Error('offline')); await loading
    expect(store.items.map(row => row.id)).toEqual(['a', 'b'])
    expect(store.pagination.page).toBe(1); expect(store.pagination.total).toBe(3)
    expect(store.error).toBeNull(); expect(store.loadMoreError).toBeTruthy(); expect(store.loadingMore).toBe(false)
    api.getItems.mockResolvedValueOnce(page(['c'], 2))
    await store.loadItems(2, true)
    expect(store.items.map(row => row.id)).toEqual(['a', 'b', 'c']); expect(store.loadMoreError).toBeNull()
    expect(api.getItems).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 }))
  })
  it('prevents duplicate page requests and discards old scroll responses when a new query starts', async () => {
    const store = useInventoryStore()
    api.getItems.mockResolvedValueOnce(page(['old-a', 'old-b']))
    await store.loadItems()
    const old = deferred(); api.getItems.mockReturnValueOnce(old.promise)
    const append = store.loadItems(2, true)
    await store.loadItems(2, true)
    expect(api.getItems).toHaveBeenCalledTimes(2)
    store.filters.search = 'camiseta S'
    const fresh = deferred(); api.getItems.mockReturnValueOnce(fresh.promise)
    const searching = store.loadItems()
    expect(store.hasLoaded).toBe(false); expect(store.loadingMore).toBe(false)
    fresh.resolve(page(['new'], 1, 1)); await searching
    old.resolve(page(['old-c'], 2)); await append
    expect(store.items.map(row => row.id)).toEqual(['new'])
    expect(store.pagination.total).toBe(1); expect(store.loading).toBe(false)
  })
  it('does not append after changing filters or beyond the last page', async () => {
    const store = useInventoryStore()
    api.getItems.mockResolvedValueOnce(page(['a', 'b']))
    await store.loadItems()
    store.filters.brand = 'Boss'
    await store.loadItems(2, true)
    store.filters.brand = ''
    await store.loadItems(3, true)
    expect(api.getItems).toHaveBeenCalledTimes(1)
  })
  it('does not present the previous query total as confirmed after a failed new search', async () => {
    const store = useInventoryStore()
    api.getItems.mockResolvedValueOnce(page(['a', 'b']))
    await store.loadItems()
    store.filters.search = 'calçados'
    api.getItems.mockRejectedValueOnce(new Error('offline'))
    await store.loadItems()
    expect(store.hasLoaded).toBe(false); expect(store.error).toBeTruthy()
    expect(store.items).toHaveLength(2)
  })
})
