import { describe, expect, it } from 'vitest'
import { canWithdrawStock, displayStock, hasKnownStock, stockAlertLevel } from './inventoryStock'

const complete = { current_stock: 5, stock_loja: 5, stock_deposito: 0, alert_level: 'ok' }
describe('Nullable inventory stock', () => {
  it('preserves zero and missing balances distinctly', () => {
    expect(displayStock(0)).toBe('0')
    expect(displayStock(null)).toBe('—')
    expect(displayStock(undefined)).toBe('—')
    expect(hasKnownStock({ current_stock: 0, stock_loja: 0, stock_deposito: 0 })).toBe(true)
    expect(canWithdrawStock({ current_stock: 0, stock_loja: 0, stock_deposito: 0 })).toBe(false)
  })
  it.each(['current_stock', 'stock_loja', 'stock_deposito'] as const)('blocks unknown %s without inferring it from other balances', key => {
    const item = { ...complete, [key]: null }
    expect(hasKnownStock(item)).toBe(false)
    expect(canWithdrawStock(item)).toBe(false)
    expect(stockAlertLevel(item)).toBe('unknown')
  })
  it('retains inactive status priority and permits a known positive withdrawal', () => {
    expect(stockAlertLevel({ ...complete, stock_loja: null, alert_level: 'inactive' })).toBe('inactive')
    expect(canWithdrawStock(complete)).toBe(true)
  })
})
