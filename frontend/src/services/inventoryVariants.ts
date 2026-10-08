import api, { type InventoryItem } from './api'
export type VariantSummary = Pick<InventoryItem, 'id' | 'name' | 'sku_internal' | 'size' | 'color' | 'barcode' | 'is_active'>
export interface VariantContext { source: InventoryItem; source_version: string; model_name: string; existing: VariantSummary[] }
export interface VariantRequest { sizes: string[]; model_name: string; base_barcode: string | null; source_version: string; initial_stock: number; stock_location: 'loja' | 'deposito'; confirm: true }
export interface VariantResult { group_key: string | null; created: VariantSummary[]; existing: VariantSummary[] }
export const inventoryVariantsAPI = {
  context: async (id: string) => (await api.get<VariantContext>(`/api/inventory/items/${id}/variants`)).data,
  create: async (id: string, body: VariantRequest) => (await api.post<VariantResult>(`/api/inventory/items/${id}/variants`, body)).data,
}
