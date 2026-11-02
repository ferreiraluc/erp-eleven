import api from './api'

export interface CountListItem {
  id: string
  code: string
  name: string
  color: string | null
  size: string | null
  location: string | null
  stock_loja: number | null
  stock_deposito: number | null
}
export interface CountListSnapshot {
  version: 1
  user_id: string
  created_at: string
  items: CountListItem[]
  totals: { items: number; stock_loja: number; stock_deposito: number; unknown_loja: number; unknown_deposito: number }
}
export interface SignedCountList { snapshot: CountListSnapshot; signature: string }
export interface CountListDevice { id: string; name: string; last_seen_at: string | null }
export interface CountListPreview extends SignedCountList {
  devices: CountListDevice[]
  suggested_device_id: string | null
  filename: string
}
export interface CountListRequest extends SignedCountList {
  device_id: string
  request_key: string
  confirm: true
}
export interface CountListJob {
  id: string
  status: string
  device_id: string
  device_name: string
  created_at: string
  diagnostic_message: string | null
}

export const inventoryCountList = {
  preview: (item_ids: string[]) => api.post<CountListPreview>('/api/inventory-count-list/preview', { item_ids }).then(r => r.data),
  pdf: (body: SignedCountList) => api.post<Blob>('/api/inventory-count-list/pdf', body, { responseType: 'blob', timeout: 120_000 }).then(r => r.data),
  print: (body: CountListRequest) => api.post<CountListJob>('/api/inventory-count-list/print', body, { timeout: 120_000 }).then(r => r.data),
  job: (id: string) => api.get<CountListJob>(`/api/inventory-count-list/jobs/${id}`).then(r => r.data),
  jobPdf: (id: string) => api.get<Blob>(`/api/inventory-count-list/jobs/${id}/pdf`, { responseType: 'blob', timeout: 120_000 }).then(r => r.data),
}

/** The server revalidates signature, actor and snapshot. Corrupt recovery must never become a new print. */
export function restoreCountListRequest(value: string, userId: string): CountListRequest {
  const body = JSON.parse(value) as CountListRequest
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
  if (!body || body.confirm !== true || !uuid.test(body.request_key || '') || !uuid.test(body.device_id || '') ||
      typeof body.signature !== 'string' || !body.signature || body.signature.length > 256 ||
      body.snapshot?.version !== 1 || body.snapshot.user_id !== userId ||
      !Number.isFinite(Date.parse(body.snapshot.created_at)) || !Array.isArray(body.snapshot.items) ||
      !body.snapshot.items.length || body.snapshot.items.length > 5000 ||
      body.snapshot.items.some(row => !row || !uuid.test(row.id || '') || typeof row.code !== 'string' ||
        typeof row.name !== 'string' || ![row.color, row.size, row.location].every(s => s === null || typeof s === 'string') ||
        ![row.stock_loja, row.stock_deposito].every(n => n === null || Number.isSafeInteger(n)))) {
    throw new Error('invalid-count-list-recovery')
  }
  const rows = body.snapshot.items
  const totals = body.snapshot.totals
  if (new Set(rows.map(row => row.id)).size !== rows.length || !totals || totals.items !== rows.length ||
      totals.stock_loja !== rows.reduce((n, row) => n + (row.stock_loja ?? 0), 0) ||
      totals.stock_deposito !== rows.reduce((n, row) => n + (row.stock_deposito ?? 0), 0) ||
      totals.unknown_loja !== rows.filter(row => row.stock_loja === null).length ||
      totals.unknown_deposito !== rows.filter(row => row.stock_deposito === null).length) throw new Error('invalid-count-list-recovery')
  return body
}

export async function countListError(error: unknown, fallback: string): Promise<string> {
  const data = (error as { response?: { data?: unknown } })?.response?.data
  try {
    const detail = data instanceof Blob ? JSON.parse(await data.text())?.detail : (data as { detail?: unknown })?.detail
    return typeof detail === 'string' ? detail : typeof detail?.message === 'string' ? detail.message : fallback
  } catch { return fallback }
}

/** Only these locked server rejections prove that no request with this key was queued. */
export function countListDefinitelyNotQueued(error: unknown): boolean {
  const response = (error as { response?: { status?: number; data?: { detail?: { code?: string; not_queued?: boolean } } } })?.response
  const detail = response?.data?.detail
  return response?.status === 409 && detail?.not_queued === true &&
    ['inventory_count_preview_expired', 'inventory_count_device_unavailable'].includes(detail.code || '')
}
