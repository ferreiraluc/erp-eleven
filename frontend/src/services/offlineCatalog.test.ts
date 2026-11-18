import { afterEach, beforeEach, expect, it, vi } from 'vitest'
const mocks = vi.hoisted(() => ({ token: 'private-session', valid: true, native: true, get: vi.fn(), held: false, failPut: false,
  candidates: [] as { id: string; version: string }[], workers: [] as TestWorker[], deletionHeld: false, deletes: [] as any[] }))
vi.mock('@capacitor/core', () => ({ Capacitor: { isNativePlatform: () => mocks.native } }))
vi.mock('./api', () => ({ default: { get: mocks.get } }))
vi.mock('./sessionStorage', () => ({ storedToken: () => mocks.token, tokenIsCurrent: () => mocks.valid }))
let service: typeof import('./offlineCatalog')
const row = { id: 'one', name: 'Camiseta', sku_internal: 'ONE', sale_price: 80, sale_currency: 'USD', is_active: true, created_at: '2026', updated_at: '2026', stock_loja: 2 }
const page = (next: string | null = null) => ({ data: { schema: 1, owner_id: 'lucas', observed_at: new Date().toISOString(), items: [row], next_cursor: next } })
class TestWorker {
  onmessage: any; onerror: any; calls: any[] = []; terminated = false
  constructor() { mocks.workers.push(this) }
  postMessage(message: any) {
    this.calls.push(message)
    if (message.type === 'search' && mocks.held) return
    const result = message.type === 'init' ? { count: 2, bytes: 123, syncedAt: Date.now(), startedAt: Date.now() }
      : message.type === 'search' ? { items: [row], total: 1, syncedAt: Date.now(), startedAt: Date.now() }
      : message.type === 'finish' ? { count: 3, bytes: 456, syncedAt: Date.now(), startedAt: Date.now() }
      : message.type === 'thumbnail-candidates' ? mocks.candidates : true
    queueMicrotask(() => this.onmessage?.({ data: { id: message.id, result, error: message.type === 'put' && mocks.failPut ? 'QuotaExceededError' : undefined } }))
  }
  terminate() { this.terminated = true }
}
beforeEach(async () => {
  vi.useFakeTimers(); vi.resetModules(); mocks.token = 'private-session'; mocks.valid = mocks.native = true
  mocks.held = mocks.failPut = mocks.deletionHeld = false; mocks.workers = []; mocks.deletes = []; mocks.candidates = []; mocks.get.mockReset()
  vi.stubGlobal('Worker', TestWorker)
  vi.stubGlobal('indexedDB', { deleteDatabase: vi.fn(() => { const request: any = {}; mocks.deletes.push(request); if (!mocks.deletionHeld) queueMicrotask(() => request.onsuccess?.()); return request }) })
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' })
  Object.defineProperty(navigator, 'onLine', { configurable: true, value: true })
  service = await import('./offlineCatalog')
  await service.prepareOfflineCatalog({ userId: 'lucas', token: mocks.token })
})
afterEach(() => { service.stopOfflineCatalog(); vi.useRealTimers(); vi.unstubAllGlobals() })

it('preserves the last complete snapshot on network failure and storage quota failure', async () => {
  mocks.get.mockRejectedValueOnce(new Error('offline'))
  await service.refreshOfflineCatalog()
  expect(service.offlineCatalogState).toMatchObject({ count: 2, bytes: 123, loading: false, error: true })
  mocks.get.mockResolvedValueOnce(page()); mocks.failPut = true
  await service.refreshOfflineCatalog()
  expect(service.offlineCatalogState.count).toBe(2)
  expect(mocks.workers[0].calls.some(call => call.type === 'finish')).toBe(false)
})
it('publishes only a complete cursor walk, never sends credentials to the worker, and rejects repeated cursors', async () => {
  mocks.get.mockResolvedValueOnce(page('next')).mockResolvedValueOnce(page())
  const done = service.refreshOfflineCatalog(); await vi.advanceTimersByTimeAsync(250); await done
  expect(service.offlineCatalogState.count).toBe(3)
  expect(mocks.get.mock.calls[1][1].params.after_id).toBe('next')
  expect(JSON.stringify(mocks.workers[0].calls)).not.toContain(mocks.token)
  mocks.workers[0].calls = []
  mocks.get.mockResolvedValue(page('repeated'))
  const failed = service.refreshOfflineCatalog(); await vi.advanceTimersByTimeAsync(500); await failed
  expect(service.offlineCatalogState.count).toBe(3)
  expect(mocks.workers[0].calls.some(call => call.type === 'finish')).toBe(false)
})
it('waits for previous logout deletion before opening the next account and drops late results', async () => {
  mocks.held = true
  const pending = service.searchOfflineCatalog('camiseta'); await Promise.resolve(); await Promise.resolve()
  mocks.deletionHeld = true
  const deleting = service.clearOfflineCatalog(); await Promise.resolve(); await Promise.resolve()
  expect(await pending).toEqual({ items: [], total: 0, syncedAt: 0, startedAt: 0 })
  expect(mocks.workers[0].terminated).toBe(true)
  mocks.token = 'new-session'
  const preparing = service.prepareOfflineCatalog({ userId: 'sol', token: mocks.token })
  await Promise.resolve(); expect(mocks.workers).toHaveLength(1)
  mocks.deletes[0].onsuccess(); await deleting; await preparing
  expect(mocks.workers).toHaveLength(2)
  expect(mocks.workers[1].calls[0].data.scope).toBe('sol')
})
it('preserves the root authorization guard when the old native search adapter prepares again', async () => {
  let allowed = true
  await service.prepareOfflineCatalog({ userId: 'lucas', token: mocks.token, isCurrent: () => allowed })
  await service.prepareOfflineCatalog({ userId: 'lucas', token: mocks.token })
  allowed = false
  expect((await service.searchOfflineCatalog('camiseta')).items).toEqual([])
  expect(mocks.get).not.toHaveBeenCalled()
})
it('never starts background copying while hidden or on a web browser', async () => {
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
  service.offlineCatalogState.syncedAt = 0
  await vi.advanceTimersByTimeAsync(180000)
  expect(mocks.get).not.toHaveBeenCalled()
  service.stopOfflineCatalog(); mocks.native = false
  await service.prepareOfflineCatalog({ userId: 'lucas', token: mocks.token })
  expect(mocks.workers).toHaveLength(1)
})
it('stops local access on denied permission, but ignores denials belonging to an old account', async () => {
  const expired = vi.fn(); window.addEventListener('erp:session-expired', expired)
  try {
    mocks.get.mockRejectedValueOnce({ isAxiosError: true, response: { status: 403 } })
    await service.refreshOfflineCatalog()
    expect(expired).toHaveBeenCalledOnce(); expect(service.offlineCatalogState.count).toBe(0)
    await service.prepareOfflineCatalog({ userId: 'lucas', token: mocks.token })
    let reject!: (error: unknown) => void
    mocks.get.mockReturnValueOnce(new Promise((_, r) => { reject = r }))
    const pending = service.refreshOfflineCatalog(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve()
    mocks.token = 'other'; service.stopOfflineCatalog(); reject({ isAxiosError: true, response: { status: 403 } }); await pending
    expect(expired).toHaveBeenCalledOnce()
  } finally { window.removeEventListener('erp:session-expired', expired) }
})
it('uses bounded thumbnail retries, stops an empty queue, and rearms on native foreground', async () => {
  await vi.advanceTimersByTimeAsync(20000)
  expect(mocks.workers[0].calls.filter(call => call.type === 'thumbnail-candidates')).toHaveLength(1)
  mocks.candidates = [{ id: 'one', version: '2026' }]; mocks.get.mockRejectedValue(new Error('unavailable'))
  window.dispatchEvent(new Event('erp:native-app-active'))
  await vi.advanceTimersByTimeAsync(300000)
  expect(mocks.get.mock.calls.filter(call => call[0].endsWith('/thumbnails'))).toHaveLength(3)
  await vi.advanceTimersByTimeAsync(300000)
  expect(mocks.get.mock.calls.filter(call => call[0].endsWith('/thumbnails'))).toHaveLength(3)
})
