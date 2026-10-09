import { beforeEach, afterEach, expect, it, vi } from 'vitest'
const getThumbnails = vi.hoisted(() => vi.fn())
const storedToken = vi.hoisted(() => vi.fn(() => 'session-a'))
vi.mock('@/services/api', () => ({ inventoryAPI: { getThumbnails } }))
vi.mock('@/services/sessionStorage', () => ({ storedToken }))
beforeEach(() => { vi.resetModules(); getThumbnails.mockReset(); storedToken.mockReturnValue('session-a'); vi.useFakeTimers() })
afterEach(() => vi.useRealTimers())
const response = (ids: string[]) => ({ thumbnails: Object.fromEntries(ids.map(id => [id, { image_data: id }])), retry_ids: [] })

it('batches 12 at a time, limits concurrency and skips stale cards', async () => {
  const { loadThumbnail } = await import('./thumbnailQueue')
  const pending: { ids: string[]; resolve: (value: unknown) => void; reject: (error: Error) => void }[] = []
  getThumbnails.mockImplementation((ids: string[]) => new Promise((resolve, reject) => pending.push({ids, resolve, reject})))
  let current = true
  const results = Array.from({length: 25}, (_, i) => loadThumbnail(String(i), () => true))
  results.push(loadThumbnail('stale', () => current))
  const settled = Promise.allSettled(results)
  current = false
  await vi.advanceTimersByTimeAsync(10)
  expect(pending.map(x => x.ids.length)).toEqual([12, 12])
  pending[0].reject(new Error('offline'))
  await vi.advanceTimersByTimeAsync(10)
  expect(pending[2].ids).toEqual(['24'])
  pending[1].resolve(response(pending[1].ids)); pending[2].resolve(response(pending[2].ids))
  await settled
  expect(await results[25]).toBeNull()
})

it('coalesces duplicate photos and reuses cache across views, invalidates version/session', async () => {
  const { loadThumbnail } = await import('./thumbnailQueue')
  getThumbnails.mockImplementation(async (ids: string[]) => response(ids))
  const a = loadThumbnail('item', () => true, 'v1'), b = loadThumbnail('item', () => true, 'v1')
  await vi.advanceTimersByTimeAsync(10); await Promise.all([a,b])
  expect(getThumbnails).toHaveBeenCalledTimes(1)
  expect(await loadThumbnail('item', () => true, 'v1')).toEqual({image_data:'item'})
  const updated = loadThumbnail('item', () => true, 'v2')
  await vi.advanceTimersByTimeAsync(10); await updated
  expect(getThumbnails).toHaveBeenCalledTimes(2)
  storedToken.mockReturnValue('session-b')
  const changedUser = loadThumbnail('item', () => true, 'v2')
  await vi.advanceTimersByTimeAsync(10); await changedUser
  expect(getThumbnails).toHaveBeenCalledTimes(3)
})

it('retries busy previews once without unbounded retries', async () => {
  const { loadThumbnail } = await import('./thumbnailQueue')
  getThumbnails.mockResolvedValue({thumbnails:{},retry_ids:['busy']})
  const result = loadThumbnail('busy', () => true)
  await vi.advanceTimersByTimeAsync(2050)
  expect(await result).toBeNull()
  expect(getThumbnails).toHaveBeenCalledTimes(2)
})
