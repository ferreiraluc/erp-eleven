import type { InventoryItem } from './api'

type Balances = Pick<InventoryItem, 'current_stock' | 'stock_loja' | 'stock_deposito'>
type KnownBalances = { current_stock: number; stock_loja: number; stock_deposito: number }
type ReservedBalances = Pick<InventoryItem, 'reserved_loja' | 'reserved_deposito'>

export const UNKNOWN_STOCK_MESSAGE = 'Há saldo desconhecido neste produto. Nenhuma movimentação foi registrada; confira os dados do estoque.'

/** Missing balances are not zero and cannot be inferred from a different location. */
export function hasKnownStock<T extends Balances>(item: T): item is T & KnownBalances {
  return [item.current_stock, item.stock_loja, item.stock_deposito].every(value => typeof value === 'number' && Number.isFinite(value))
}

export function displayStock(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '—'
}

/** A group balance is known only when every member has a balance for that location. */
export function sumStock(items: readonly Balances[], field: keyof Balances): number | null {
  let total = 0
  for (const item of items) {
    const value = item[field]
    if (typeof value !== 'number' || !Number.isFinite(value)) return null
    total += value
  }
  return total
}

export function availableStock(item: Balances & ReservedBalances, location: 'loja' | 'deposito'): number | null {
  const stock = item[`stock_${location}`]
  if (typeof stock !== 'number' || !Number.isFinite(stock)) return null
  return stock - (item[`reserved_${location}`] ?? 0)
}

export function canWithdrawStock(item: Balances & ReservedBalances): boolean {
  return hasKnownStock(item) && ((availableStock(item, 'loja') ?? 0) > 0 || (availableStock(item, 'deposito') ?? 0) > 0)
}

export function stockAlertLevel(item: Balances & { alert_level?: string }): string {
  if (item.alert_level === 'inactive') return 'inactive'
  return hasKnownStock(item) ? item.alert_level || 'ok' : 'unknown'
}
