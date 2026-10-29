import { expect, it } from 'vitest'
import { searchable, searchCatalog, cachedItem, type CatalogRow } from './catalogSearch'
const row = (id: string, name: string, extra: Partial<CatalogRow> = {}): CatalogRow => ({
  id,
  name,
  sku_internal: id,
  brand: 'Emporio Armani',
  size: 'L',
  color: 'Black',
  category: 'Camisetas',
  sale_price: 80,
  sale_currency: 'USD',
  is_active: true,
  created_at: '2026-10-28',
  updated_at: '2026-10-28',
  ...extra,
})
it('matches model-letter typos after literals, aliases, descriptions and brand typos', () => {
  const index = [
    row('a', 'Camiseta 1JRGZ', { description: 'Placa de metal' }),
    row('b', 'Camiseta 1HRGZ'),
    row('c', 'Calça DN0281', { category: 'Calças' }),
    row('d', 'Camiseta 2JRGZ'),
  ].map(searchable)
  expect(searchCatalog(index, '1HRGZ').map((r) => r.id)).toEqual(['b', 'a'])
  expect(searchCatalog(index, 'tsirt Emprio armani G').map((r) => r.id)).toEqual(['b', 'a', 'd'])
  expect(searchCatalog(index, 'placa').map((r) => r.id)).toEqual(['a'])
  expect(searchCatalog(index, 'DN0282')).toEqual([])
  expect(searchCatalog(index, 'calsa').map((r) => r.id)).toEqual(['c'])
  expect(searchCatalog(index, '1HRGZ', { color: 'Preto' })).toHaveLength(2)
  expect(searchCatalog(index, '1HRGZ', { status: 'low_stock' })).toEqual([])
})
it('keeps internal QR identity exact and cached quantities explicitly unknown', () => {
  const value = row('a', 'Camiseta', { inventory_code: 'INV-ABC234' })
  expect(searchCatalog([searchable(value)], 'INV-ABC235')).toEqual([])
  expect(searchCatalog([searchable(value)], 'INV-ABC234')).toHaveLength(1)
  expect(cachedItem(value)).toMatchObject({
    catalog_cached: true,
    current_stock: null,
    stock_loja: null,
    stock_deposito: null,
    image_data: null,
  })
})
it('bounds UI results for a synthetic catalog of 50,000 products', () => {
  const index = Array.from({ length: 50000 }, (_, i) =>
    searchable(row(String(i), 'Camiseta modelo X' + String(i).padStart(6, '0'))),
  )
  expect(searchCatalog(index, 'camiseta')).toHaveLength(50)
  expect(searchCatalog(index, 'X049999').map((r) => r.id)).toEqual(['49999'])
})
