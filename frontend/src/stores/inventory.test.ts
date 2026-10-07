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
