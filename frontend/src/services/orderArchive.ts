import api from './api'
export interface ArchivePreview {
  total: number
  eligible_count: number
  blocked_count: number
  allowed: boolean
  plan_token: string
  sample: Array<{ id: string; numero_pedido: string; cliente_nome: string; commerce_status: string | null }>
  blockers: ArchivePreview['sample']
}
export interface ArchiveCommand { request_id: string; confirm: true; plan_token: string; expected_count: number }
export const orderArchive = {
  preview: (): Promise<ArchivePreview> => api.get('/api/pedidos/arquivo/preview').then(result => result.data),
  confirm: (body: ArchiveCommand): Promise<{ archived_count: number; archived_at: string; history_preserved: true; remaining_count: number }> => api.post('/api/pedidos/arquivo/confirm', body).then(result => result.data),
}
