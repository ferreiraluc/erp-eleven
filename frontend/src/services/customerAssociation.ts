import api from './api'

export interface CustomerAssociationCounts {
  addresses: number
  orders: number
  tracking: number
  pdv_accounts: number
}
export interface CustomerAssociationPreview {
  token: string
  counts: CustomerAssociationCounts
  items: Array<{
    kind: 'address' | 'order' | 'tracking' | 'pdv_account'
    id: string
    label: string
    reason: 'name_address' | 'name_phone' | 'name_email' | 'document' | 'explicit_order'
  }>
  limited: boolean
  scanned: number
  limit: number
}
export interface CustomerAssociationResult {
  linked: CustomerAssociationCounts
  already_applied: boolean
  limited: boolean
}
export const customerAssociationAPI = {
  preview: (id: string, token: string, signal?: AbortSignal): Promise<CustomerAssociationPreview> =>
    api.post(`/api/clientes/${encodeURIComponent(id)}/conciliacao/previa`, undefined, {
      headers: { Authorization: `Bearer ${token}` }, signal,
    }).then(r => r.data),
  apply: (id: string, expectedToken: string, token: string, signal?: AbortSignal): Promise<CustomerAssociationResult> =>
    api.post(`/api/clientes/${encodeURIComponent(id)}/conciliacao`, {
      expected_token: expectedToken, confirm: true,
    }, { headers: { Authorization: `Bearer ${token}` }, signal }).then(r => r.data),
}
