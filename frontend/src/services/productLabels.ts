import api from './api'

export interface LabelProduct {
  id: string
  name: string
  inventory_code: string | null
  size: string | null
  color: string | null
  group_key: string | null
  stock_loja: number | null
  stock_deposito: number | null
  current_stock: number | null
}
export interface LabelCollection {
  id?: string
  name: string
  group_key?: string
  count?: number
  received_on?: string
  notes?: string
}
export interface LabelDevice {
  id: string
  name: string
  last_seen_at: string | null
}
export interface LabelLine {
  item_id: string
  code: string
  name: string
  color: string | null
  size: string | null
  copies: number
}
export interface LabelRequest {
  request_key: string
  confirm: true
  items: LabelLine[]
}
export interface LabelJob {
  id: string
  name: string
  code: string
  color: string | null
  size: string | null
  copies: number
  status: string
  diagnostic_message: string | null
}
export interface LabelBatch {
  id: string
  request_key: string
  total: number
  jobs: LabelJob[]
}
export interface LabelSelection {
  item_ids?: string[]
  group_keys?: string[]
  lot_ids?: string[]
}

export const productLabels = {
  device: () =>
    api.get<{ device: LabelDevice | null }>('/api/inventory-labels/device').then((r) => r.data),
  configure: (rotate = false) =>
    api
      .post<{
        device: LabelDevice
        token: string | null
      }>('/api/inventory-labels/device', { confirm: true, rotate })
      .then((r) => r.data),
  catalog: (mode: 'products' | 'grades' | 'lots', q: string, page: number) =>
    api
      .get<{
        items: (LabelProduct | LabelCollection)[]
        total: number
      }>('/api/inventory-labels/catalog', { params: { mode, q, page } })
      .then((r) => r.data),
  selection: (body: LabelSelection) =>
    api
      .post<{ items: LabelProduct[] }>('/api/inventory-labels/selection', body)
      .then((r) => r.data.items),
  preview: (id: string) =>
    api
      .get<Blob>(`/api/inventory-labels/preview/${id}`, { responseType: 'blob' })
      .then((r) => r.data),
  enqueue: (body: LabelRequest) =>
    api.post<LabelBatch>('/api/inventory-labels/batches', body).then((r) => r.data),
  batch: (id: string) =>
    api.get<LabelBatch>(`/api/inventory-labels/batches/${id}`).then((r) => r.data),
  history: () =>
    api
      .get<{ id: string; name: string; created_at: string }[]>('/api/inventory-labels/batches')
      .then((r) => r.data),
  cancel: (id: string) =>
    api
      .post<LabelBatch>(`/api/inventory-labels/batches/${id}/cancel`, { confirm: true })
      .then((r) => r.data),
  installer: () =>
    api
      .get<Blob>('/api/printing/agent-package', {
        params: { profile: 'product_labels' },
        responseType: 'blob',
      })
      .then((r) => r.data),
}

export function mergeLabelSelection(
  current: (LabelProduct & { copies: number })[],
  incoming: LabelProduct[],
) {
  const ids = new Set(current.map((p) => p.id))
  return [...current, ...incoming.filter((p) => !ids.has(p.id)).map((p) => ({ ...p, copies: 1 }))]
}

export function labelRequest(
  rows: (LabelProduct & { copies: number })[],
  key: string,
): LabelRequest {
  if (
    !rows.length ||
    rows.length > 500 ||
    rows.some(
      (p) =>
        !/^INV-[23456789ABCDEFGHJKLMNPQRSTUVWXYZ]{6}$/.test(p.inventory_code || '') ||
        !Number.isInteger(p.copies) ||
        p.copies < 1 ||
        p.copies > 100,
    ) ||
    rows.reduce((sum, p) => sum + p.copies, 0) > 2000
  ) {
    throw new Error(
      'Confira os códigos e quantidades: até 500 produtos, 100 cópias por produto e 2.000 etiquetas por envio.',
    )
  }
  return {
    request_key: key,
    confirm: true,
    items: rows.map((p) => ({
      item_id: p.id,
      code: p.inventory_code!,
      name: p.name,
      color: p.color,
      size: p.size,
      copies: p.copies,
    })),
  }
}
