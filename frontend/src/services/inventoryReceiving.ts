import api from './api'
export interface ReceivingLot {
  id: string
  name: string
  notes: string
  received_on: string
  created_at: string
  item_count: number
}
export interface ReceivingCandidate {
  id: string
  name: string
  sku_internal?: string
  size?: string | null
  color?: string | null
  created_at?: string
}
export interface ReceivingMember extends ReceivingCandidate {
  item_id: string | null
  deleted: boolean
}
export interface ReceivingDetails {
  name: string
  notes: string
  received_on: string
}
export const receivingAPI = {
  list: async (page = 1) =>
    (
      await api.get<{ items: ReceivingLot[]; total: number }>('/api/inventory/receiving-lots', {
        params: { page, page_size: 30 },
      })
    ).data,
  candidates: async (date_from: string, date_to: string) =>
    (
      await api.get<{ items: ReceivingCandidate[]; total: number }>(
        '/api/inventory/receiving-candidates',
        { params: { date_from, date_to } },
      )
    ).data,
  create: async (
    body: ReceivingDetails & { request_id: string; item_ids: string[]; confirm: true },
  ) => (await api.post<ReceivingLot>('/api/inventory/receiving-lots', body)).data,
  edit: async (id: string, body: ReceivingDetails) =>
    (await api.patch<ReceivingLot>(`/api/inventory/receiving-lots/${id}`, body)).data,
  attach: async (id: string, item_ids: string[]) =>
    (
      await api.post<ReceivingLot>(`/api/inventory/receiving-lots/${id}/items`, {
        item_ids,
        confirm: true,
      })
    ).data,
  members: async (id: string, page = 1) =>
    (
      await api.get<{ lot: ReceivingLot; items: ReceivingMember[] }>(
        `/api/inventory/receiving-lots/${id}/items`,
        { params: { page } },
      )
    ).data,
  detach: async (id: string, member: string) =>
    api.delete(`/api/inventory/receiving-lots/${id}/items/${member}`),
}
