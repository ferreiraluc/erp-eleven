import { describe, expect, it } from 'vitest'
import { taxonomyKey, uniqueLabels } from './inventoryTaxonomy'
import { optionKey } from './inventoryGradeOptions'

describe('inventory taxonomy', () => {
  it('compares case, accents and category spacing consistently', () => {
    expect(taxonomyKey('CALÇADOS> tênis')).toBe(taxonomyKey('calçados > Tênis'))
    expect(taxonomyKey('EA7 Empório Armani')).toBe(taxonomyKey('Emporio Armani'))
    expect(optionKey(' AZÚL  MARINHO ')).toBe(optionKey('Azul Marinho'))
  })
  it('consolidates labels but keeps distinct brands and color meanings', () => {
    expect(uniqueLabels(['Prada', 'PRADA', 'pRADA', 'Prada Sport'])).toEqual(['Prada', 'Prada Sport'])
    expect(taxonomyKey('Armani Exchange')).not.toBe(taxonomyKey('Emporio Armani'))
    expect(taxonomyKey('Navy')).not.toBe(taxonomyKey('Azul'))
  })
})
