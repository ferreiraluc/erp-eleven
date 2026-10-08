import { describe, expect, it } from 'vitest'
import { inventoryGroupName } from './inventoryGroupNames'

const uuid = '40dd6437-f51a-4b54-9d8d-f543e8705c16'
const source = { id: 'source', name: 'Tênis Givenchy DN0281 11', size: '11', created_at: '2026-10-01T10:00:00Z' }
const copy = { id: 'copy', name: 'Nome alterado da cópia 8', size: '8', created_at: '2026-10-02T10:00:00Z' }

describe('Automatic grade titles', () => {
  it.each([uuid, `grade-${uuid}`, uuid.toUpperCase(), uuid.replaceAll('-', '')])('uses the original product for %s, regardless of result order', key => {
    expect(inventoryGroupName(key, [copy, source], 'Grade')).toBe('Tênis Givenchy DN0281')
    expect(inventoryGroupName(key, [source, copy], 'Grade')).toBe('Tênis Givenchy DN0281')
  })
  it.each([
    ['Tênis DN0281', '281', 'Tênis DN0281'],
    ['Polo EA7', '7', 'Polo EA7'],
    ['Tênis DN0281 11.5', '11.5', 'Tênis DN0281'],
    ['Camiseta DN0281 xl', 'XL', 'Camiseta DN0281'],
    ['TÊNIS GIVENCHY DN0281', '', 'TÊNIS GIVENCHY DN0281'],
  ])('removes only the variant size from %s', (name, size, expected) => {
    expect(inventoryGroupName(`grade-${uuid}`, [{ ...source, name, size }], 'Grade')).toBe(expected)
  })
  it('preserves custom and legacy readable titles', () => {
    for (const key of ['Coleção DN0281', 'grade-verão', 'Tênis Givenchy Preto']) {
      expect(inventoryGroupName(key, [source], 'Grade')).toBe(key)
    }
  })
  it('does not expose an internal identifier while members are unavailable', () => {
    expect(inventoryGroupName(`grade-${uuid}`, [], 'Variant group')).toBe('Variant group')
  })
})
