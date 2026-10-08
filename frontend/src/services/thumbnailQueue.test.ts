import { expect, it, vi } from 'vitest'
const getThumbnail = vi.hoisted(() => vi.fn())
vi.mock('@/services/api', () => ({ inventoryAPI: { getThumbnail } }))
import { loadThumbnail } from './thumbnailQueue'

it('limits concurrent requests, skips stale cards and continues after failure', async () => {
  const pending: { resolve: (value: {image_data: string}) => void; reject: (error: Error) => void }[] = []
  getThumbnail.mockImplementation(() => new Promise((resolve, reject) => pending.push({resolve, reject})))
  let current = true
  const results = [loadThumbnail('a', () => true), loadThumbnail('b', () => true),
    loadThumbnail('stale', () => current), loadThumbnail('c', () => true)]
  const settled = Promise.allSettled(results)
  expect(getThumbnail.mock.calls.map(c => c[0])).toEqual(['a', 'b'])
  current = false
  pending[0].reject(new Error('offline'))
  await vi.waitFor(() => expect(getThumbnail.mock.calls.map(c => c[0])).toEqual(['a', 'b', 'c']))
  pending[1].resolve({image_data:'b'}); pending[2].resolve({image_data:'c'})
  expect((await settled).map(r => r.status)).toEqual(['rejected', 'fulfilled', 'fulfilled', 'fulfilled'])
  expect(await results[2]).toBeNull()
})
