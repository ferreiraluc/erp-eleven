import type { InventoryItem } from './api'
import { hasKnownStock } from './inventoryStock'

export type StockLocation = 'loja' | 'deposito'
export type StockDraft = Record<string, Record<StockLocation, number>>
export const MAX_STOCK = 2_147_483_647
export const validStockCount = (value: number) => Number.isInteger(value) && value >= 0 && value <= MAX_STOCK

export function initialStockDraft(items: InventoryItem[]): StockDraft {
  return Object.fromEntries(items.filter(hasKnownStock).map(item => [item.id, {
    loja: item.stock_loja, deposito: item.stock_deposito,
  }]))
}

export function changedStock(items: InventoryItem[], draft: StockDraft) {
  return items.filter(item => hasKnownStock(item) && draft[item.id] && (
    draft[item.id].loja !== item.stock_loja || draft[item.id].deposito !== item.stock_deposito
  ))
}

export function validStockDraft(items: InventoryItem[], draft: StockDraft) {
  return changedStock(items, draft).every(item => {
    const value = draft[item.id]
    return validStockCount(value.loja) && validStockCount(value.deposito) && value.loja + value.deposito <= MAX_STOCK
  })
}
