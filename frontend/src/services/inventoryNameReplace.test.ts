import { expect, it } from 'vitest'
import { replaceProductName } from './inventoryNameReplace'
import { canonicalSize, taxonomyKey } from './inventoryTaxonomy'
import { parseGradeSizes } from './inventoryGradeOptions'
it('corrects names without changing variant sizes, model casing or partial words', () => {
  for (const size of ['S', 'P', 'M', 'L', 'XL']) {
    expect(replaceProductName(`T-shirt Biss Y-26-09 ${size}`, 'biss', 'Boss')).toBe(`T-shirt Boss Y-26-09 ${size}`)
  }
  expect(replaceProductName('Bissau Biss DN0281', 'Biss', 'Boss')).toBe('Bissau Boss DN0281')
  expect(replaceProductName('T-shirt D.G S', 'D.G', '$&')).toBe('T-shirt $& S')
  expect(replaceProductName('Camiseta S', '', 'Boss')).toBe('Camiseta S')
})
it('normalizes brands and sizes in presets, deduplicating aliases only', () => {
  expect(['DG', 'DolceGabbana', 'Dolce&Gabbana'].map(taxonomyKey)).toEqual(Array(3).fill('dolce & gabbana'))
  expect(parseGradeSizes('P S M G L GG XL XXL 2XL')).toEqual(['S', 'M', 'L', 'XL', '2XL'])
  expect(canonicalSize('11.5 US')).toBe('11.5 US')
})
