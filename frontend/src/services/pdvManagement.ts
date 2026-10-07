import api, { type PdvSaleCreate, type PdvSaleItemResponse, type PdvPaymentResponse } from './api'
export type SaleOperation = 'edit' | 'return' | 'cancel' | 'delete'
export interface ManagedLine extends PdvSaleItemResponse { returned_quantity: number | string; product_deleted?: boolean }
export interface ManagedSale {
  id: string; vendedor_id: string | null; cliente_id: string | null; cliente_nome: string | null
  subtotal_gs: string; desconto_gs: string; total_gs: string; refunded_gs: string; fiado_reversed_gs: string
  status: string; stock_applied: boolean; notas: string | null; version: number; created_at: string
  deleted_at: string | null; seller: string | null; actor: string | null; can_manage: boolean
  items: ManagedLine[]; payments: PdvPaymentResponse[]; events: SaleEvent[]; payment_difference_gs: string
}
export interface SaleEvent { id: string; operation: SaleOperation; reason: string; at: string; actor: string | null
  before: ManagedSale; after: ManagedSale; effects: SalePreview }
export interface SaleCommand { operation: SaleOperation; reason: string; edit?: PdvSaleCreate
  lines?: Array<{ line_id: string; quantity: number; restock: boolean }>; restock?: boolean }
export interface SalePreview { operation: SaleOperation; reason: string; plan_token: string
  before_total_gs: string; after_total_gs: string; refund_gs: string; fiado_credit_gs: string; cash_refund_gs: string
  stock: Array<{ item_id: string; name: string; location: string; delta: number; before: number; after: number }>
  fiado: Array<{ customer_id: string; name: string; before: string; after: string; delta: string }>
  returns: Array<{ line_id: string; name: string; quantity: string; restock: boolean; refund_gs: string }>
  warnings: string[]; payment_notice: string; correction?: PdvSaleCreate | null }
export interface SaleCommit { command: SaleCommand; plan_token: string; request_id: string; confirm: true }
export interface SaleListing { page: number; page_size: number; total: number; own_sales_only: boolean; can_manage: boolean
  summary: { gross_gs: string; refunded_gs: string; net_gs: string; cancelled: number }
  items: Array<{ id: string; created_at: string; cliente_nome: string | null; seller: string | null; total_gs: string
    refunded_gs: string; status: string; items_count: number; payment_methods: string[]; deleted_at: string | null; version: number }> }
export const pdvManagementAPI = {
  list: (params: Record<string, unknown>): Promise<SaleListing> => api.get('/api/pdv/management', { params }).then(r => r.data),
  options: (): Promise<{ sellers: Array<{ id: string; name: string }> }> => api.get('/api/pdv/management/options').then(r => r.data),
  detail: (id: string): Promise<ManagedSale> => api.get(`/api/pdv/management/${id}`).then(r => r.data),
  preview: (id: string, command: SaleCommand): Promise<SalePreview> => api.post(`/api/pdv/management/${id}/preview`, command).then(r => r.data),
  commit: (id: string, body: SaleCommit): Promise<{ ok: boolean; sale_id: string; replayed: boolean }> => api.post(`/api/pdv/management/${id}/commit`, body).then(r => r.data),
}
export function saleError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return detail.map(d => typeof d?.msg === 'string' ? d.msg : '').filter(Boolean).join('; ')
  return 'Não foi possível concluir. Confira sua conexão e tente novamente.'
}
