import api from './api'

export interface ItemDeletionPreview {
  item: { id: string; name: string; sku_internal: string; size: string | null; color: string | null;
    current_stock: number | null; stock_loja: number | null; stock_deposito: number | null }
  allowed: boolean
  blockers: Array<{ code: 'sales' | 'inventory_counts' | 'linked_movements'; count: number }>
  movement_count: number
  plan_token: string | null
  preserve_history_token?: string
}

export const inventoryDeletionAPI = {
  preview: (id: string): Promise<ItemDeletionPreview> =>
    api.get(`/api/inventory/items/${id}/deletion-preview`).then(r => r.data),
  preserveHistory: (id: string, body: { sku: string; plan_token: string; confirm: true }): Promise<{ deleted: boolean; id: string }> =>
    api.post(`/api/inventory/items/${id}/delete-from-catalog`, body).then(r => r.data),
  remove: (id: string, body: { sku: string; plan_token: string; confirm: true }): Promise<{ deleted: boolean; id: string }> =>
    api.delete(`/api/inventory/items/${id}/permanent`, { data: body }).then(r => r.data),
}
