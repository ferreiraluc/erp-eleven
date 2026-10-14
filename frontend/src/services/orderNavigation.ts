import type { Pedido } from './api'

/** Read-only destination. Creating a shipment remains an explicit action. */
export function orderTrackingLocation(order: Pick<Pedido, 'codigo_rastreio' | 'cliente_nome'>) {
  return {
    name: 'rastreamento',
    query: { search: order.codigo_rastreio?.trim() || order.cliente_nome?.trim() || '' },
  }
}
