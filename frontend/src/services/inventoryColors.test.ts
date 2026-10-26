import { expect, it } from 'vitest'
import { colorKey, uniqueColors } from './inventoryColors'
import { inScope, scopeOptions } from './inventoryBulkDetails'
import type { InventoryItem } from './api'

it.each([
  ['Black', 'Preta'],
  ['Blanco', 'White'],
  ['Azul marino', 'Navy blue'],
  ['Gris', 'Grey'],
  ['Marrón', 'Brown'],
  ['Bege + Preto', 'Black y Beige'],
  ['Preto e Branco', 'White/Negro'],
])('recognizes %s / %s without rewriting stored labels', (a, b) => {
  expect(colorKey(a)).toBe(colorKey(b))
  expect(uniqueColors([a, b])).toEqual([a])
})
it('keeps shades, compositions and unknown references distinct', () => {
  expect(colorKey('Azul')).not.toBe(colorKey('Navy'))
  expect(colorKey('White')).not.toBe(colorKey('Off White'))
  expect(colorKey('Black')).not.toBe(colorKey('Black+White'))
  expect(colorKey('Green 260')).not.toBe(colorKey('Green 270'))
})
it('applies a batch by the same color across languages and preserves other shades', () => {
  const items = ['Preta', 'Black', 'Negro', 'Navy'].map(
    (color, i) => ({ id: String(i), color, size: 'M' }) as InventoryItem,
  )
  expect(scopeOptions(items).filter((option) => option.kind === 'Cor')).toHaveLength(2)
  expect(items.filter((item) => inScope(item, 'color:preto')).map((item) => item.id)).toEqual([
    '0',
    '1',
    '2',
  ])
})
