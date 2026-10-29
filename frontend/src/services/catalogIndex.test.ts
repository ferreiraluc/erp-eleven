import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({
  token: 'session',
  valid: true,
  get: vi.fn(),
  held: false,
  workers: [] as any[],
}))
vi.mock('./api', () => ({ default: { get: mocks.get } }))
vi.mock('./sessionStorage', () => ({
  storedToken: () => mocks.token,
  tokenIsCurrent: () => mocks.valid,
}))
let service: typeof import('./catalogIndex')
const entry = {
  id: 'one',
  name: 'Camiseta',
  sku_internal: 'ONE',
  sale_price: 80,
  sale_currency: 'USD',
  is_active: true,
  created_at: '2026',
  updated_at: '2026',
}
class TestWorker {
  onmessage: any
  onerror: any
  calls: any[] = []
  terminated = false
  constructor() {
    mocks.workers.push(this)
  }
  postMessage(message: any) {
    this.calls.push(message)
    if (message.type === 'search' && mocks.held) return
    const result =
      message.type === 'init'
        ? { count: 2, bytes: 123, syncedAt: Date.now() }
        : message.type === 'search'
          ? [entry]
          : message.type === 'finish'
            ? { count: 3, bytes: 456, syncedAt: Date.now() }
            : true
    queueMicrotask(() => this.onmessage?.({ data: { id: message.id, result } }))
  }
  terminate() {
    this.terminated = true
  }
}
beforeEach(async () => {
  vi.useFakeTimers()
  vi.resetModules()
  mocks.token = 'session'
  mocks.valid = true
  mocks.held = false
  mocks.workers = []
  mocks.get.mockReset()
  vi.stubGlobal('Worker', TestWorker)
  vi.stubGlobal('indexedDB', { deleteDatabase: vi.fn(() => ({})) })
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  service = await import('./catalogIndex')
  await service.prepareCatalogIndex('lucas')
})
afterEach(() => {
  service.clearCatalogIndex()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
it('returns provisional rows with unknown balances, and discards replies after sign-out', async () => {
  expect(await service.searchDeviceCatalog('camiseta')).toMatchObject([
    { id: 'one', catalog_cached: true, current_stock: null, stock_loja: null },
  ])
  mocks.held = true
  const pending = service.searchDeviceCatalog('camiseta')
  await Promise.resolve()
  await Promise.resolve()
  service.clearCatalogIndex()
  expect(await pending).toEqual([])
  expect(mocks.workers[0].terminated).toBe(true)
})
it('never replaces a complete index with a failed background copy', async () => {
  mocks.get.mockRejectedValueOnce(new Error('Disconnected'))
  await service.refreshCatalogIndex(true)
  expect(service.catalogCacheState).toMatchObject({
    count: 2,
    bytes: 123,
    error: true,
    loading: false,
  })
  expect(mocks.workers[0].calls.some((call: any) => call.type === 'finish')).toBe(false)
})
it('publishes a new complete copy only after its final page and never puts a token into worker messages', async () => {
  mocks.get
    .mockResolvedValueOnce({ data: { items: [entry], next_cursor: 'cursor' } })
    .mockResolvedValueOnce({ data: { items: [], next_cursor: null } })
  const synced = service.refreshCatalogIndex(true)
  await vi.advanceTimersByTimeAsync(500)
  await synced
  expect(mocks.get).toHaveBeenCalledTimes(2)
  expect(mocks.get.mock.calls[1][1].params.after_id).toBe('cursor')
  expect(service.catalogCacheState).toMatchObject({
    count: 3,
    bytes: 456,
    error: false,
    loading: false,
  })
  expect(JSON.stringify(mocks.workers[0].calls)).not.toContain('session')
})
it('does not query persisted data under another or expired session', async () => {
  mocks.token = 'other-session'
  expect(await service.searchDeviceCatalog('camiseta')).toEqual([])
  mocks.token = 'session'
  mocks.valid = false
  expect(await service.searchDeviceCatalog('camiseta')).toEqual([])
})
