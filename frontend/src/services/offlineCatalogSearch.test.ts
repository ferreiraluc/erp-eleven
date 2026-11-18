import { expect, it } from 'vitest'
import { offlineIndex, offlineSearch, offlineFacets, normalizeOfflineItem, validOfflineThumbnail, type OfflineCatalogItem } from './offlineCatalogSearch'

const item = (i: number, changes: Partial<OfflineCatalogItem> = {}): OfflineCatalogItem => ({
  id: String(i), name: `Camiseta modelo ${i}`, sku_internal: `SKU-${i}`, inventory_code: `INV-${String(i).padStart(6, '0')}`,
  sale_price: 80, sale_currency: 'USD', is_active: true, created_at: '2026-11-01', updated_at: '2026-11-01',
  unit: 'un', min_stock: 1, max_stock: 10, current_stock: 5, stock_loja: 2, stock_deposito: 3,
  reserved_loja: 1, reserved_deposito: 0, available_loja: 1, available_deposito: 3, available_stock: 4,
  stock_confirmed: true, snapshot_at: '2026-11-01T12:00:00Z', ...changes,
})
it('paginates all 50,000 synthetic products and resolves an exact identity beyond the first page', () => {
  const index = offlineIndex(Array.from({ length: 50000 }, (_, i) => item(i)))
  const first = offlineSearch(index, '', {}, 50, 0), next = offlineSearch(index, '', {}, 50, 50)
  expect(first.total).toBe(50000); expect(first.items).toHaveLength(50); expect(next.items).toHaveLength(50)
  expect(new Set([...first.items, ...next.items].map(row => row.id)).size).toBe(100)
  expect(offlineSearch(index, 'INV-049999', {}).items[0]?.id).toBe('49999')
})
it('keeps physical/reserved/available quantities distinct and never treats unknown stock as zero', () => {
  const known = item(1, { brand: 'Boss', category: 'Roupas' }), unknown = item(2, { stock_confirmed: false, available_stock: null, stock_loja: null })
  const out = item(3, { current_stock: -1, stock_loja: -1, available_stock: -1, available_loja: -1 })
  const index = offlineIndex([known, unknown, out])
  expect(offlineSearch(index, '', { status: 'out' }).items.map(row => row.id)).toEqual(['3'])
  expect(offlineSearch(index, '', { status: 'review' }).items.map(row => row.id)).toEqual(['2'])
  expect(offlineSearch(index, '', { location_stock: 'loja' }).items.map(row => row.id)).toEqual(['1'])
  expect(offlineSearch(index, '', { receiving_lot_id: 'unavailable' }).items).toEqual([])
  expect(offlineFacets([known, unknown])).toMatchObject({ brands: ['Boss'], categories: ['Roupas'] })
})
it('accepts only bounded JPEG preview data, never arbitrary URLs, SVG or full originals', () => {
  expect(validOfflineThumbnail('data:image/jpeg;base64,/9j/AA==')).toBe(true)
  for (const value of ['https://example.com/photo.jpg', 'data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,/9j/AA==', 'data:image/jpeg;base64,/9j/' + 'A'.repeat(48 * 1024)]) expect(validOfflineThumbnail(value)).toBe(false)
})
it('normalizes legacy dates and removes unexpected fields before a generation can be indexed', () => {
  const legacy = normalizeOfflineItem({ ...item(1), created_at: null, updated_at: null, brand: null, cost_price: 999, image_data: 'private', sale_price: null })
  expect(legacy.created_at).toBe(''); expect(legacy.updated_at).toBe(''); expect(legacy.sale_price).toBeNull()
  expect(legacy).not.toHaveProperty('cost_price'); expect(legacy).not.toHaveProperty('image_data')
  expect(offlineSearch(offlineIndex([legacy]), '', {}).items).toHaveLength(1)
  expect(() => normalizeOfflineItem({ ...item(1), snapshot_at: 'invalid' })).toThrow()
})
