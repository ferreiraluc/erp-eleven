import api, { type PdvPaymentCreate, type PdvPaymentResponse, type PdvSaleResponse } from './api'
import type { ReceiptState } from './pdvReceipts'
import { uiText } from '@/i18n/uiText'

export type ReservationStatus = 'reserved' | 'completed' | 'cancelled'
export interface ReservationItem {
  id: string
  item_id: string
  item_name: string
  item_sku: string | null
  item_size: string | null
  item_color: string | null
  location: 'loja' | 'deposito'
  quantity: number
  unit_price_gs: number
  total_gs: number
  available_loja?: number | null
  available_deposito?: number | null
  has_image?: boolean
  updated_at?: string | null
}
export interface ReservationPayment extends PdvPaymentResponse {
  created_by: string | null
  reversed_at: string | null
  reversal_reason: string | null
}
export interface ReservationDetail {
  id: string
  numero_pedido: string
  commerce_status: ReservationStatus
  commerce_version: number
  pdv_cliente_id: string
  cliente_id: string | null
  cliente_nome: string
  vendedor_id: string
  vendedor_nome: string
  reserved_at: string
  created_at: string
  usd_rate_gs: number
  subtotal_gs: number
  desconto_gs: number
  total_gs: number
  paid_gs: number
  balance_gs: number
  change_gs?: number
  sale_id: string | null
  notas: string | null
  items: ReservationItem[]
  payments: ReservationPayment[]
}
export interface ReservationCommand {
  request_id: string
  confirm: true
  expected_version: number
}
export interface ReservationSave {
  request_id: string
  confirm: true
  expected_version?: number
  pdv_cliente_id: string
  items: Array<Pick<ReservationItem, 'item_id' | 'location' | 'quantity' | 'unit_price_gs'>>
  usd_rate_gs: number
  desconto_gs: number
  notas?: string
}

/** Normalize Decimal JSON once; every caller can safely sum money and quantities. */
export function normalizeReservation(value: ReservationDetail): ReservationDetail {
  return { ...value, commerce_version: Number(value.commerce_version), usd_rate_gs: Number(value.usd_rate_gs),
    subtotal_gs: Number(value.subtotal_gs), desconto_gs: Number(value.desconto_gs), total_gs: Number(value.total_gs),
    paid_gs: Number(value.paid_gs), balance_gs: Number(value.balance_gs), change_gs: Number(value.change_gs || 0),
    items: value.items.map(item => ({ ...item, quantity: Number(item.quantity), unit_price_gs: Number(item.unit_price_gs), total_gs: Number(item.total_gs),
      available_loja: item.available_loja === null || item.available_loja === undefined ? item.available_loja : Number(item.available_loja),
      available_deposito: item.available_deposito === null || item.available_deposito === undefined ? item.available_deposito : Number(item.available_deposito) })),
    payments: value.payments.map(payment => ({ ...payment, amount_gs: Number(payment.amount_gs), amount_original: Number(payment.amount_original),
      exchange_rate: Number(payment.exchange_rate), card_fee_gs: Number(payment.card_fee_gs || 0), card_fee_percent: Number(payment.card_fee_percent || 0) })),
  }
}
const reservation = (promise: Promise<{ data: ReservationDetail }>) => promise.then(result => normalizeReservation(result.data))
export const orderReservations = {
  create: (body: ReservationSave) => reservation(api.post('/api/pedidos/reservas', body)),
  detail: (id: string) => reservation(api.get(`/api/pedidos/${id}/reserva`)),
  update: (id: string, body: ReservationSave) => reservation(api.put(`/api/pedidos/${id}/reserva`, body)),
  payment: (id: string, body: ReservationCommand & { payment: PdvPaymentCreate }) => reservation(api.post(`/api/pedidos/${id}/pagamentos`, body)),
  cancel: (id: string, body: ReservationCommand & { reason: string }) => reservation(api.post(`/api/pedidos/${id}/cancelar`, body)),
  reversePayment: (id: string, paymentId: string, body: ReservationCommand & { reason: string }) => reservation(api.post(`/api/pedidos/${id}/pagamentos/${paymentId}/estornar`, body)),
  checkout: (id: string, body: ReservationCommand & { payments: PdvPaymentCreate[]; print_receipt: boolean }): Promise<PdvSaleResponse> => api.post(`/api/pedidos/${id}/checkout`, body).then(result => result.data),
  ticketPdf: (id: string): Promise<ArrayBuffer> => api.get(`/api/pedidos/${id}/reserva/ticket`, { responseType: 'arraybuffer' }).then(result => result.data),
  ticketState: (id: string): Promise<ReceiptState> => api.get(`/api/pedidos/${id}/reserva/ticket/status`).then(result => result.data),
  printTicket: (id: string, body: ReservationCommand): Promise<ReceiptState> => api.post(`/api/pedidos/${id}/reserva/ticket`, body).then(result => result.data),
}
export function reservationStatusLabel(status: string | null | undefined, paid = 0, balance?: number) {
  if (status === 'completed') return uiText('Venda concluída')
  if (status === 'cancelled') return uiText('Reserva cancelada')
  if (status === 'reserved') return uiText(balance === 0 ? 'Pago · aguardando conclusão' : paid > 0 ? 'Pagamento parcial' : 'Separado')
  return uiText('Pedido sem reserva')
}
export function reservationError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : uiText('Não foi possível concluir. Confira a conexão e tente novamente.')
}
