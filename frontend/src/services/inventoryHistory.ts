import api from './api'

export type HistorySection = 'movements' | 'sales' | 'counts' | 'changes'
interface HistoryBase { id: string; at: string | null; actor: string | null }
export interface ProductMovement extends HistoryBase {
  kind: 'movements'; type: string; quantity: number; before: number; after: number
  location_from: string | null; location_to: string | null; reason: string | null; notes: string | null
  reference_type: string | null; reference_id: string | null; restricted: boolean
}
export interface ProductSale extends HistoryBase {
  kind: 'sales'; status: string; updated_at: string | null; seller: string | null; customer: string | null
  stock_applied: boolean; sale_total_gs: string | null
  lines: Array<{ id: string; link: 'item_id' | 'legacy_sku'; name: string; sku: string | null
    size: string | null; color: string | null; quantity: string | null; unit_price_gs: string | null
    discount_gs: string | null; total_gs: string | null; location: string | null; is_avulso: boolean }>
}
export interface ProductCount extends HistoryBase {
  kind: 'counts'; session_id: string; name: string; status: string; location: string | null
  system_quantity: number; counted_quantity: number | null; applied_at: string | null
}
export interface ProductChange extends HistoryBase {
  kind: 'changes'; action: string; source: string
  fields: Record<string, { before?: string | number | boolean | null; after?: string | number | boolean | null; changed?: boolean }>
}
export interface ProductHistory {
  product: { id: string; name: string; sku_internal: string; barcode: string | null; brand: string | null
    size: string | null; color: string | null; category: string | null; is_active: boolean
    created_at: string | null; updated_at: string | null; created_by: string | null
    current_stock: number | null; stock_loja: number | null; stock_deposito: number | null
    deleted_at?: string | null; deleted_by?: string | null }
  section: HistorySection; page: number; page_size: number; total: number
  totals: { movements: number; sales: number; counts: number; changes: number | null }
  rows: Array<ProductMovement | ProductSale | ProductCount | ProductChange>
  own_sales_only: boolean; can_view_changes: boolean
}
export const inventoryHistoryAPI = {
  deleted: (q = '', page = 1): Promise<{ total: number; page: number; page_size: number; items: Array<{ id: string; name: string; sku: string; deleted_at: string }> }> =>
    api.get('/api/inventory/items/deleted-history', { params: { q, page } }).then(r => r.data),
  get: (id: string, section: HistorySection, page = 1): Promise<ProductHistory> =>
    api.get(`/api/inventory/items/${id}/history`, { params: { section, page, page_size: 20 } }).then(r => r.data),
}
