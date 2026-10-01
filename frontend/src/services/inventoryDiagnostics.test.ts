import { beforeEach, expect, it, vi } from 'vitest'
import { inventoryDiagnosticsAPI } from './inventoryDiagnostics'
const get = vi.hoisted(() => vi.fn())
vi.mock('./api', () => ({ default: { get } }))
beforeEach(() => get.mockReset().mockResolvedValue({ data: { items: [] } }))
it('uses only the authenticated GET endpoint and passes cancellation with bounded parameters', async () => {
  const signal = new AbortController().signal
  await inventoryDiagnosticsAPI.get({ issue: 'missing_stock', page: -4, page_size: 500, q: '  ' + 'a'.repeat(170) + '  ' }, signal)
  expect(get).toHaveBeenCalledWith('/api/inventory/diagnostics', { params: { issue: 'missing_stock', page: 1, page_size: 100, q: 'a'.repeat(150) }, signal, timeout: 20000 })
})
it('supplies defaults without a background request', async () => {
  expect(get).not.toHaveBeenCalled()
  expect(await inventoryDiagnosticsAPI.get()).toEqual({ items: [] })
  expect(get).toHaveBeenCalledWith('/api/inventory/diagnostics', expect.objectContaining({ params: { issue: 'all', page: 1, page_size: 25, q: undefined } }))
})
