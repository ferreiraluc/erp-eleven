import { uiText } from '@/i18n/uiText'

export type PaymentCurrency = 'GS' | 'USD' | 'BRL' | 'EUR' | 'USDT'
export const paymentMethods = [
  { value: 'cash_usd', label: 'Dinheiro U$', currency: 'USD' },
  { value: 'cash_brl', label: 'Dinheiro R$', currency: 'BRL' },
  { value: 'cash_gs', label: 'Dinheiro G$', currency: 'GS' },
  { value: 'cash_eur', label: 'Dinheiro EUR', currency: 'EUR' },
  { value: 'card_credit_py', label: 'Cartão Crédito PY', currency: 'GS' },
  { value: 'card_debit_py', label: 'Cartão Débito PY', currency: 'GS' },
  { value: 'qr_py', label: 'QR Máquina PY Débito', currency: 'GS' },
  { value: 'pix_personal', label: 'PIX (pessoal)', currency: 'BRL' },
  { value: 'pix_thais', label: 'PIX (Thais)', currency: 'BRL' },
  { value: 'maquina_thais', label: 'MaquinaThais', currency: 'BRL' },
  { value: 'transfer_py', label: 'TransferenciaPY', currency: 'GS' },
  { value: 'usdt', label: 'USDT', currency: 'USDT' },
  { value: 'mercadopago', label: 'MercadoPago (link)', currency: 'BRL' },
  { value: 'fiado', label: 'Anotar (fiado)', currency: 'GS' },
] as const

// Historical labels remain readable; these methods are not offered for new payments.
const legacyLabels: Record<string, string> = {
  card: 'Cartão (antigo)', pix: 'PIX (antigo)', transfer_br: 'Transf. Brasil',
  pix_cambista: 'PIX Cambista', tigo_money: 'Tigo Money',
}
export const allPaymentFilters = [...paymentMethods.map(m => m.value), ...Object.keys(legacyLabels)]
export function paymentLabel(method: string) {
  return uiText(paymentMethods.find(m => m.value === method)?.label || legacyLabels[method] || method)
}
export function isCardPayment(method: string) {
  return method === 'card_credit_py' || method === 'card_debit_py'
}
/** Whole-guarani charge that leaves the requested merchandise amount after 6%. */
export function cardCharge(netGs: number) {
  return Math.ceil(Math.round(netGs * 100) / 94)
}
export function cardPaymentAmounts(grossGs: number, remainingGs?: number) {
  let net = Math.round(grossGs * 94) / 100
  // The Total button's rounding must not change a product's price or create change.
  if (remainingGs !== undefined && remainingGs > 0 && cardCharge(remainingGs) === grossGs)
    net = Math.round(remainingGs * 100) / 100
  return { amount_gs: net, card_fee_gs: Math.round((grossGs - net) * 100) / 100, card_fee_percent: 6 }
}
export function paymentCurrency(method: string): PaymentCurrency | undefined {
  return paymentMethods.find(m => m.value === method)?.currency
}
export function paymentSymbol(currency: string) {
  return ({ GS: 'G$', PYG: 'G$', USD: 'U$', BRL: 'R$', EUR: 'EUR', USDT: 'USDT' } as Record<string, string>)[currency] || currency
}
export function paymentRate(currency: string, rates: Record<string, number>): number {
  if (currency === 'GS' || currency === 'PYG') return 1
  const usd = rates['G$']
  const divisor = currency === 'BRL' ? rates['R$'] : currency === 'EUR' ? rates.EUR : 1
  const rate = usd / divisor
  return Number.isFinite(rate) && rate > 0 ? Math.round(rate * 1e6) / 1e6 : 0
}
export function validPaymentAmount(amount: number, rate: number) {
  return Number.isFinite(amount) && amount > 0 && Number.isFinite(rate) && rate > 0 &&
    Math.abs(amount * 100 - Math.round(amount * 100)) < .0001 &&
    rate <= 999999999 && amount <= 9999999999999.99 && amount * rate <= 9999999999999.99
}

/** A "Total" amount can differ from the remaining G$ by at most half a cent of its currency. */
export function totalPaymentRoundingDelta(remainingGs: number, amountOriginal: number, rate: number, amountGs: number): number | null {
  if (!Number.isFinite(remainingGs) || remainingGs <= 0 || !validPaymentAmount(amountOriginal, rate) || !Number.isFinite(amountGs)) return null
  const converted = Math.round(amountOriginal * rate * 100) / 100
  if (Math.abs(converted - amountGs) > .000001) return null
  const delta = (Math.round(amountGs * 100) - Math.round(remainingGs * 100)) / 100
  return Math.abs(delta) <= rate * .005 + .000001 ? delta : null
}
