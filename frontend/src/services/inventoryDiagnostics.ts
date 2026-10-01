import api from './api'

export type InventoryIssue = 'stock_mismatch' | 'negative_stock' | 'missing_stock' | 'duplicate_barcode'
export type InventoryIssueFilter = 'all' | InventoryIssue

export interface InventoryDiagnosticItem {
  id: string
  name: string
  sku_internal: string
  barcode: string | null
  normalized_barcode: string | null
  brand: string | null
  size: string | null
  color: string | null
  current_stock: number | null
  stock_loja: number | null
  stock_deposito: number | null
  expected_stock: number | null
  delta: number | null
  issues: string[]
  duplicate_count: number
}

export interface InventoryDiagnostics {
  checked_at: string
  total_active_items: number
  affected_items: number
  counts: Record<InventoryIssue, number> & { duplicate_barcode_groups: number }
  total_items: number
  page: number
  page_size: number
  items: InventoryDiagnosticItem[]
}

export interface InventoryDiagnosticsQuery {
  issue?: InventoryIssueFilter
  q?: string
  page?: number
  page_size?: number
}

/** Read only. These limits mirror the API; no correction is performed by this service. */
export const inventoryDiagnosticsAPI = {
  get(query: InventoryDiagnosticsQuery = {}, signal?: AbortSignal): Promise<InventoryDiagnostics> {
    const integer = (value: number | undefined, fallback: number) =>
      value !== undefined && Number.isFinite(value) ? Math.floor(value) : fallback
    return api.get('/api/inventory/diagnostics', {
      params: {
        issue: query.issue || 'all',
        q: query.q?.trim().slice(0, 150) || undefined,
        page: Math.max(1, integer(query.page, 1)),
        page_size: Math.min(100, Math.max(1, integer(query.page_size, 25))),
      },
      signal,
      timeout: 20000,
    }).then(response => response.data)
  },
}
