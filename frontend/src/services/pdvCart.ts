import type { InventoryItem } from './api'
import { hasKnownStock } from './inventoryStock'

export type StockLocation = 'loja' | 'deposito'
export type CatalogStockSnapshot = Pick<InventoryItem, 'id' | 'current_stock' | 'stock_loja' | 'stock_deposito' | 'is_active'>
export type CartIssue = 'catalogQuantity' | 'manualQuantity' | 'invalidLocation' | 'missingProduct' | 'unknownStock' | 'invalidStock' | 'inactiveProduct' | 'insufficientStock' | 'busy' | 'emptyCart' | 'uncertain'
export class PdvCartError extends Error {
  constructor(public code: CartIssue, public params: Record<string, string | number> = {}) { super(code); this.name = 'PdvCartError' }
}
export function validateQuantity(quantity: number, catalog: boolean): void {
  const valid = typeof quantity === 'number' && Number.isFinite(quantity) && quantity > 0 &&
    (catalog ? Number.isInteger(quantity) && quantity <= 9_999_999 : quantity <= 9_999_999.999 && Number(quantity.toFixed(3)) === quantity)
  if (!valid) throw new PdvCartError(catalog ? 'catalogQuantity' : 'manualQuantity')
}
export function validateLocation(location: string): asserts location is StockLocation {
  if (location !== 'loja' && location !== 'deposito') throw new PdvCartError('invalidLocation')
}
export function stockAt(snapshot: CatalogStockSnapshot | undefined, location: string): number {
  validateLocation(location)
  if (!snapshot || !hasKnownStock(snapshot)) throw new PdvCartError('unknownStock')
  if (snapshot.is_active === false) throw new PdvCartError('inactiveProduct')
  if (![snapshot.current_stock, snapshot.stock_loja, snapshot.stock_deposito].every(value => Number.isSafeInteger(value) && value >= 0) ||
      snapshot.current_stock !== snapshot.stock_loja + snapshot.stock_deposito) throw new PdvCartError('invalidStock')
  return location === 'loja' ? snapshot.stock_loja : snapshot.stock_deposito
}
