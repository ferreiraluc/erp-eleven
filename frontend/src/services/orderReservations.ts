import api, { type PdvPaymentCreate, type PdvPaymentResponse, type PdvSaleResponse } from './api'
import type { ReceiptState } from './pdvReceipts'
import { uiText } from '@/i18n/uiText'

export type ReservationStatus = 'reserved' | 'conditional' | 'returned' | 'completed' | 'cancelled'
export interface ReservationItem {
  id: string
  item_id: string
  item_name: string
  item_sku: string | null
  item_size: string | null
  item_color: string | null
  location: 'loja' | 'deposito'
  quantity: number
  returned_quantity?: number
  remaining_quantity?: number
  remaining_total_gs?: number
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
  refunded_gs?: number
  remaining_gs?: number
  remaining_original?: number
  refunded_original?: number
  refunds?: Array<{ id: string; amount_gs: number; amount_original: number; reason: string; created_at: string; created_by: string }>
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
  delivered_at?: string | null
  delivered_total_gs?: number | null
  refund_due_gs?: number
  archived_at?: string | null
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
    refund_due_gs: Number(value.refund_due_gs || 0), delivered_total_gs: value.delivered_total_gs == null ? null : Number(value.delivered_total_gs),
    paid_gs: Number(value.paid_gs), balance_gs: Number(value.balance_gs), change_gs: Number(value.change_gs || 0),
    items: value.items.map(item => ({ ...item, quantity: Number(item.quantity), returned_quantity: Number(item.returned_quantity || 0), remaining_quantity: Number(item.remaining_quantity ?? item.quantity), remaining_total_gs: Number(item.remaining_total_gs ?? item.total_gs), unit_price_gs: Number(item.unit_price_gs), total_gs: Number(item.total_gs),
      available_loja: item.available_loja === null || item.available_loja === undefined ? item.available_loja : Number(item.available_loja),
      available_deposito: item.available_deposito === null || item.available_deposito === undefined ? item.available_deposito : Number(item.available_deposito) })),
    payments: value.payments.map(payment => ({ ...payment, refunded_gs: Number(payment.refunded_gs || 0), refunded_original: Number(payment.refunded_original || 0), remaining_gs: Number(payment.remaining_gs ?? (payment.reversed_at ? 0 : payment.amount_gs)), remaining_original: Number(payment.remaining_original ?? (payment.reversed_at ? 0 : payment.amount_original)), refunds: (payment.refunds || []).map(refund => ({ ...refund, amount_gs: Number(refund.amount_gs), amount_original: Number(refund.amount_original) })), amount_gs: Number(payment.amount_gs), amount_original: Number(payment.amount_original),
      exchange_rate: Number(payment.exchange_rate), card_fee_gs: Number(payment.card_fee_gs || 0), card_fee_percent: Number(payment.card_fee_percent || 0) })),
  }
}
const reservation = (promise: Promise<{ data: ReservationDetail }>) => promise.then(result => normalizeReservation(result.data))
export const orderReservations = {
  create: (body: ReservationSave) => reservation(api.post('/api/pedidos/reservas', body)),
  detail: (id: string) => reservation(api.get(`/api/pedidos/${id}/reserva`)),
  update: (id: string, body: ReservationSave) => reservation(api.put(`/api/pedidos/${id}/reserva`, body)),
  payment: (id: string, body: ReservationCommand & { payment: PdvPaymentCreate }) => reservation(api.post(`/api/pedidos/${id}/pagamentos`, body)),
  dispatch: (id: string, body: ReservationCommand) => reservation(api.post(`/api/pedidos/${id}/condicional`, body)),
  returnItems: (id: string, body: ReservationCommand & { reason: string; lines: Array<{ line_id: string; quantity: number }> }) => reservation(api.post(`/api/pedidos/${id}/devolver-itens`, body)),
  cancel: (id: string, body: ReservationCommand & { reason: string }) => reservation(api.post(`/api/pedidos/${id}/cancelar`, body)),
  refundPreview: (id: string, paymentId: string, body: ReservationCommand & { reason: string; amount_gs?: number }): Promise<{ payment_id: string; currency: string; amount_gs: number; amount_original: number; card_fee_gs: number; remaining_gs: number; remaining_original: number; expected_version: number }> => api.post(`/api/pedidos/${id}/pagamentos/${paymentId}/estorno-previa`, body).then(result => result.data),
  reversePayment: (id: string, paymentId: string, body: ReservationCommand & { reason: string; amount_gs?: number }) => reservation(api.post(`/api/pedidos/${id}/pagamentos/${paymentId}/estornar`, body)),
  checkout: (id: string, body: ReservationCommand & { payments: PdvPaymentCreate[]; print_receipt: boolean }): Promise<PdvSaleResponse> => api.post(`/api/pedidos/${id}/checkout`, body).then(result => result.data),
  ticketPdf: (id: string): Promise<ArrayBuffer> => api.get(`/api/pedidos/${id}/reserva/ticket`, { responseType: 'arraybuffer' }).then(result => result.data),
  ticketState: (id: string): Promise<ReceiptState> => api.get(`/api/pedidos/${id}/reserva/ticket/status`).then(result => result.data),
  printTicket: (id: string, body: ReservationCommand): Promise<ReceiptState> => api.post(`/api/pedidos/${id}/reserva/ticket`, body).then(result => result.data),
}
export function reservationStatusLabel(status: string | null | undefined, paid = 0, balance?: number) {
  if (status === 'conditional') return uiText('Condicional pendente')
  if (status === 'returned') return uiText('Condicional devolvida')
  if (status === 'completed') return uiText('Venda concluída')
  if (status === 'cancelled') return uiText('Reserva cancelada')
  if (status === 'reserved') return uiText(balance === 0 ? 'Pago · aguardando conclusão' : paid > 0 ? 'Pagamento parcial' : 'Separado')
  return uiText('Pedido sem reserva')
}
export function reservationError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  return typeof detail === 'string' ? detail : uiText('Não foi possível concluir. Confira a conexão e tente novamente.')
}
