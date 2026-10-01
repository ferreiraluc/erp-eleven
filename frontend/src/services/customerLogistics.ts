import api, { type Pedido } from './api'

export interface CustomerParcel {
  id: string
  codigo_rastreio: string
  status: string
  destinatario?: string | null
  pedido_id?: string | null
  cliente_id?: string | null
  numero_pedido?: string | null
  ativo: boolean
  created_at: string
}
export interface CustomerLogistics {
  order_total: number
  shipment_total: number
  in_transit: number
  delivered: number
  orders: Pedido[]
  shipments: CustomerParcel[]
}
export const customerLogisticsAPI = {
  get: (id: string, ordersSkip = 0, shipmentsSkip = 0): Promise<CustomerLogistics> =>
    api.get(`/api/clientes/${id}/logistica`, { params: { orders_skip: ordersSkip, shipments_skip: shipmentsSkip, limit: 20 } }).then(r => r.data),
  link: (id: string, kind: 'pedido' | 'rastreamento', targetId: string): Promise<void> =>
    api.post(`/api/clientes/${id}/vinculos`, { kind, target_id: targetId }).then(() => undefined),
  findParcel: (code: string): Promise<CustomerParcel> =>
    api.get(`/api/rastreamento/codigo/${encodeURIComponent(code.trim().toUpperCase())}`).then(r => r.data),
  orderParcels: (orderId: string, skip = 0): Promise<CustomerParcel[]> =>
    api.get(`/api/pedidos/${orderId}/rastreamentos`, { params: { skip, limit: 50 } }).then(r => r.data),
  linkParcelToOrder: (parcelId: string, orderId: string): Promise<CustomerParcel> =>
    api.put(`/api/rastreamento/${parcelId}`, { pedido_id: orderId }).then(r => r.data),
}
