import { expect, it } from 'vitest'
import i18n from '@/i18n'
import { usd, saleUsd } from './saleUsd'
it('formats dollars using a frozen rate and preserves zero and refunds', () => {
  i18n.global.locale.value = 'pt'
  expect(saleUsd('480000', '6000')).toBe('US$ 80,00')
  expect(saleUsd('-60000', '6000')).toBe('US$ -10,00')
  expect(usd(0)).toBe('US$ 0,00')
})
it('never turns unknown or invalid rates into a zero dollar amount', () => {
  for (const rate of [undefined, null, '0', '-1', 'Infinity', 'NaN']) expect(saleUsd(480000, rate)).toBe('US$ —')
  for (const value of [undefined, null, '', 'NaN']) expect(usd(value)).toBe('US$ —')
})
