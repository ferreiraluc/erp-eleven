import type { InventoryItem } from './api'

type Balances = Pick<InventoryItem, 'current_stock' | 'stock_loja' | 'stock_deposito'>
type KnownBalances = { current_stock: number; stock_loja: number; stock_deposito: number }

export const UNKNOWN_STOCK_MESSAGE = 'Há saldo desconhecido neste produto. Nenhuma movimentação foi registrada; confira os dados do estoque.'

/** Missing balances are not zero and cannot be inferred from a different location. */
export function hasKnownStock<T extends Balances>(item: T): item is T & KnownBalances {
  return [item.current_stock, item.stock_loja, item.stock_deposito].every(value => typeof value === 'number' && Number.isFinite(value))
}

export function displayStock(value: number | null | undefined): string {
  return typeof value === 'number' && Number.isFinite(value) ? String(value) : '—'
}

export function canWithdrawStock(item: Balances): boolean {
  return hasKnownStock(item) && item.current_stock > 0 && (item.stock_loja > 0 || item.stock_deposito > 0)
}

export function stockAlertLevel(item: Balances & { alert_level?: string }): string {
  if (item.alert_level === 'inactive') return 'inactive'
  return hasKnownStock(item) ? item.alert_level || 'ok' : 'unknown'
}
