import api from './api'

export interface CustomerMergeIdentity {
  id: string
  name: string
  details?: string | null
  cpf?: string | null
  telefone?: string | null
  email?: string | null
  endereco?: string | null
  documents?: Array<{ tipo: string; pais: string; numero: string; emissor?: string }>
}
export interface CustomerMergeCounts {
  orders: number
  tracking: number
  addresses: number
  pdv_customers: number
}
export interface CustomerMergePlan {
  state: 'ready' | 'review_conflicts'
  target_id: string
  source_ids: string[]
  plan_token: string
  customers: CustomerMergeIdentity[]
  conflicting_fields: string[]
  conflicts: Array<{ source_id: string; fields: string[] }>
  fields_added: string[]
  links_to_move: CustomerMergeCounts
  history: CustomerMergeCounts
  requires_reviewed_conflicts: boolean
}
export interface CustomerMergeResult {
  state: 'merged' | 'already_merged'
  target_id: string
  source_ids: string[]
}
export type CustomerMergePreview = CustomerMergePlan | (CustomerMergeResult & { state: 'already_merged' })
const options = (token: string, signal?: AbortSignal) => ({
  headers: { Authorization: `Bearer ${token}` }, signal,
})
export const customerMergeAPI = {
  preview: (targetId: string, sourceIds: string[], token: string, signal?: AbortSignal): Promise<CustomerMergePreview> =>
    api.post('/api/clientes/maintenance/customers/preview', {
      target_id: targetId, source_ids: sourceIds,
    }, options(token, signal)).then(response => response.data),
  confirm: (plan: CustomerMergePlan, reviewedConflicts: boolean, token: string, signal?: AbortSignal): Promise<CustomerMergeResult> =>
    api.post('/api/clientes/maintenance/customers/confirm', {
      target_id: plan.target_id, source_ids: plan.source_ids, plan_token: plan.plan_token,
      confirm: true, reviewed_conflicts: reviewedConflicts,
    }, options(token, signal)).then(response => response.data),
}
