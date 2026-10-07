import { describe, expect, it } from 'vitest'
import { foregroundBounds } from './productPhoto'
describe('Catalog foreground bounds', () => {
  it('preserves a rectangular garment and excludes background', () => {
    const mask = new Float32Array(100)
    for (let y = 2; y < 9; y++) for (let x = 3; x < 7; x++) mask[y * 10 + x] = 1
    expect(foregroundBounds(mask, 10, 10)).toEqual({ left: 3, top: 2, width: 4, height: 7 })
  })
  it('rejects empty, fully opaque, malformed and non-finite masks', () => {
    for (const mask of [new Float32Array(100), new Float32Array(100).fill(1), new Float32Array(99), new Float32Array(100).fill(NaN)]) {
      expect(() => foregroundBounds(mask, 10, 10)).toThrow('cutout_failed')
    }
  })
})

import { vi } from 'vitest'
import { analyzePhoto, generateCatalog, photoStatus } from './productPhoto'
const http = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('./api', () => ({ default: http }))
describe('Product photo API transport', () => {
  it('uses the authenticated API prefix and only confirms paid catalog requests', async () => {
    http.get.mockResolvedValue({ data: { editing_available: true } })
    http.post.mockResolvedValue({ data: {} })
    const signal = new AbortController().signal
    await photoStatus(); await analyzePhoto('image', signal); await generateCatalog('image', signal)
    expect(http.get).toHaveBeenCalledWith('/api/product-photo/status')
    expect(http.post).toHaveBeenCalledWith('/api/product-photo/analyze', { image: 'image' }, expect.objectContaining({ signal }))
    expect(http.post).toHaveBeenCalledWith('/api/product-photo/catalog', { image: 'image', confirmed: true }, expect.objectContaining({ signal, timeout: 145000 }))
  })
})
