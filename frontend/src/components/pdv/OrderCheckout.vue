<template>
  <main class="order-checkout">
    <ModuleHeader :title="uiText('PDV · Pedido separado')" :show-back="false">
      <button class="erp-button erp-button--secondary" :disabled="busy || !!pending" @click="back">{{ uiText('Voltar ao pedido') }}</button>
    </ModuleHeader>
    <ErpLoadingState v-if="loading" :label="uiText('Carregando pedido…')" :rows="3" />
    <div v-if="error" class="order-error" role="alert">
      {{ error }}
      <button v-if="pending" class="erp-button erp-button--secondary" :disabled="busy" @click="retry">{{ uiText('Conferir e tentar novamente') }}</button>
      <button v-else class="erp-button erp-button--secondary" :disabled="busy" @click="load">{{ uiText('Atualizar pedido') }}</button>
    </div>
    <p v-if="notice" class="order-notice" role="status">{{ notice }}</p>
    <div v-if="order" class="order-columns">
      <section class="order-card">
        <header class="order-heading">
          <span class="order-eyebrow">{{ order.numero_pedido }}</span>
          <h2>{{ order.cliente_nome }}</h2>
          <p>{{ order.vendedor_nome }} · {{ formatDateTime(order.reserved_at) }}</p>
          <span class="order-badge">{{ reservationStatusLabel(order.commerce_status, order.paid_gs, order.balance_gs) }}</span>
        </header>
        <div v-for="item in order.items" :key="item.id" class="order-line">
          <div class="order-piece-count">{{ item.quantity }}×</div>
          <div><strong>{{ item.item_name }}</strong><small>{{ [item.item_size, item.item_color, item.location === 'loja' ? uiText('Loja') : uiText('Depósito')].filter(Boolean).join(' · ') }}</small><small>{{ item.item_sku }}</small></div>
          <strong class="order-line-value">{{ usd(item.total_gs) }}</strong>
        </div>
        <footer class="order-totals">
          <div><span>{{ uiText('Subtotal') }}</span><span>{{ usd(order.subtotal_gs) }}</span></div>
          <div v-if="order.desconto_gs"><span>{{ uiText('Desconto') }}</span><span>− {{ usd(order.desconto_gs) }}</span></div>
          <div class="order-total"><span>{{ uiText('Total do pedido') }}</span><strong>{{ usd(order.total_gs) }}</strong></div>
          <small>{{ uiText('Preços e câmbio preservados da separação.') }} {{ gs(order.usd_rate_gs) }} / U$</small>
        </footer>
      </section>
      <section class="order-card order-payments">
        <div class="order-payment-summary">
          <div><span>{{ uiText('Recebido') }}</span><strong>{{ usd(order.paid_gs) }}</strong></div>
          <div><span>{{ uiText('Saldo a pagar') }}</span><strong>{{ usd(order.balance_gs) }}</strong><small>{{ gs(order.balance_gs) }}</small></div>
        </div>
        <details v-if="order.payments.length" class="order-history">
          <summary>{{ uiText('Histórico de pagamentos') }} · {{ order.payments.length }}</summary>
          <div v-for="payment in order.payments" :key="payment.id" class="order-payment" :class="{ reversed: payment.reversed_at }">
            <div><strong>{{ paymentLabel(payment.method) }}</strong><small>{{ formatDateTime(payment.created_at) }}</small><small v-if="payment.reversed_at">{{ uiText('Estornado') }} · {{ payment.reversal_reason }}</small></div>
            <span>{{ paymentSymbol(payment.currency) }} {{ number(payment.amount_original) }}</span>
          </div>
        </details>
        <fieldset v-if="order.commerce_status === 'reserved'" :disabled="busy || !!pending" class="order-payment-form">
          <template v-if="order.balance_gs > 0">
            <h3>{{ uiText('Novo recebimento') }}</h3>
            <label>{{ uiText('Método de pagamento') }}
              <ErpSelect v-model="method" :label="uiText('Método de pagamento')"><option v-for="option in methods" :key="option.value" :value="option.value">{{ paymentLabel(option.value) }}</option></ErpSelect>
            </label>
            <label>{{ uiText('Valor recebido') }} ({{ paymentSymbol(currency) }})
              <div class="order-amount-row"><DecimalInput v-model="amount" :aria-label="uiText('Valor recebido')" /><button type="button" class="erp-button erp-button--secondary order-total-button" :disabled="!validRate" @click="fillTotal">{{ uiText('Total') }}</button></div>
            </label>
            <label v-if="currency !== 'GS'">{{ uiText('Câmbio para G$') }}<DecimalInput v-model="rate" :aria-label="uiText('Câmbio para G$')" /></label>
            <label v-if="card" class="order-checkbox"><input v-model="fee" type="checkbox" />{{ uiText('Repassar taxa de 6% do cartão') }}</label>
            <label v-if="!method.startsWith('cash_')">{{ uiText('Referência') }}<input v-model="reference" maxlength="200" :placeholder="uiText('Opcional')" /></label>
            <div v-if="payment" class="order-payment-preview" role="status">
              <span>{{ uiText('Aplicado ao pedido') }}: <strong>{{ gs(payment.amount_gs) }}</strong></span>
              <span v-if="payment.card_fee_gs">{{ uiText('Acréscimo cartão') }}: {{ gs(payment.card_fee_gs) }}</span>
              <span v-if="change > 0">{{ uiText('Troco') }}: {{ gs(change) }}</span>
            </div>
            <p v-if="invalidChange" class="order-error">{{ uiText('Troco só pode vir de pagamento em dinheiro.') }}</p>
            <p v-if="ratesError" class="order-error">{{ uiText('Confira o câmbio deste recebimento antes de confirmar.') }}</p>
            <button class="erp-button erp-button--secondary order-save-payment" :disabled="!canDeposit" @click="submit('payment')">{{ uiText('Registrar e manter separado') }}</button>
            <small>{{ uiText('Confirme somente valores já recebidos. O pedido continua reservado.') }}</small>
          </template>
          <div v-else class="order-paid" role="status">{{ uiText('Pedido pago. Os itens continuam separados até concluir a venda.') }}</div>
          <button class="erp-button erp-button--primary order-finish" :disabled="!canComplete" @click="submit('checkout')">
            {{ uiText(order.balance_gs > 0 ? 'Receber saldo, concluir e imprimir' : 'Concluir venda e imprimir') }}
          </button>
          <small v-if="order.balance_gs > 0 && canComplete">{{ uiText('A conclusão registra o recebimento acima e aproveita os pagamentos anteriores.') }}</small>
          <small>{{ uiText('Para mudar produtos, preços ou desconto, volte ao pedido.') }}</small>
        </fieldset>
        <div v-else-if="order.sale_id" class="order-completed">
          <p>{{ uiText('Este pedido já foi convertido em venda.') }}</p>
          <button class="erp-button erp-button--secondary" @click="router.push({ path: '/vendas-pdv', query: { sale_id: order.sale_id } })">{{ uiText('Ver venda') }}</button>
        </div>
      </section>
    </div>
    <PDVReceiptModal v-if="lastSale && showReceipt" :sale="lastSale" @close="showReceipt = false" />
  </main>
</template>

<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import ModuleHeader from '@/components/ModuleHeader.vue'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import ErpLoadingState from '@/components/ui/ErpLoadingState.vue'
import DecimalInput from '@/components/forms/DecimalInput.vue'
import PDVReceiptModal from './PDVReceiptModal.vue'
import { uiText, uiLocale } from '@/i18n/uiText'
import { formatDateTime } from '@/utils/datetime'
import { saleUsd } from '@/services/saleUsd'
import { useAuthStore } from '@/stores/auth'
import { useCurrencyStore } from '@/stores/currency'
import type { PdvPaymentCreate, PdvSaleResponse } from '@/services/api'
import { orderReservations, reservationError, reservationStatusLabel, type ReservationDetail, type ReservationCommand } from '@/services/orderReservations'
import { paymentMethods, paymentLabel, paymentCurrency, paymentSymbol, paymentRate, validPaymentAmount, isCardPayment, cardCharge, cardPaymentAmounts } from '@/services/pdvPayments'

const props = defineProps<{ pedidoId: string }>()
const router = useRouter(), auth = useAuthStore(), rates = useCurrencyStore()
const order = ref<ReservationDetail | null>(null), loading = ref(false), busy = ref(false)
const error = ref(''), notice = ref(''), ratesError = ref(false)
const lastSale = ref<PdvSaleResponse | null>(null), showReceipt = ref(false)
const method = ref('cash_usd'), amount = ref<number | null>(null), rate = ref<number | null>(null), fee = ref(true), reference = ref('')
const methods = paymentMethods.filter(option => option.value !== 'fiado')
const currency = computed(() => paymentCurrency(method.value) || 'USD')
const card = computed(() => isCardPayment(method.value))
const validRate = computed(() => Number.isFinite(rate.value) && Number(rate.value) > 0)
const number = (value: number) => value.toLocaleString(uiLocale(), { maximumFractionDigits: 2 })
const gs = (value: number) => 'G$ ' + number(value)
const usd = (value: number) => saleUsd(value, order.value?.usd_rate_gs)
const cents = (value: number) => Math.round(value * 100) / 100
const payment = computed<PdvPaymentCreate | null>(() => {
  if (!validPaymentAmount(Number(amount.value), Number(rate.value))) return null
  if (card.value && fee.value && !Number.isInteger(amount.value)) return null
  const effectiveRate = currency.value === 'GS' ? 1 : Math.round(Number(rate.value) * 1e6) / 1e6
  const result: PdvPaymentCreate = { method: method.value, currency: currency.value, amount_original: Number(amount.value), exchange_rate: effectiveRate,
    amount_gs: cents(Number(amount.value) * effectiveRate), card_fee_gs: 0, card_fee_percent: 0, reference: reference.value || undefined }
  if (card.value) Object.assign(result, cardPaymentAmounts(Number(amount.value), order.value?.balance_gs, fee.value))
  return result
})
const change = computed(() => Math.max(0, cents((payment.value?.amount_gs || 0) - (order.value?.balance_gs || 0))))
const invalidChange = computed(() => change.value > 0 && !method.value.startsWith('cash_'))
const canDeposit = computed(() => !!payment.value && !invalidChange.value && !!order.value && payment.value.amount_gs > 0 && payment.value.amount_gs <= order.value.balance_gs)
const canComplete = computed(() => !!order.value && order.value.commerce_status === 'reserved' && !invalidChange.value && (order.value.balance_gs === 0 || !!payment.value && cents(payment.value.amount_gs) >= cents(order.value.balance_gs)))
type Pending = { kind: 'payment' | 'checkout'; orderId: string; userId: string; body: ReservationCommand & { payment?: PdvPaymentCreate; payments?: PdvPaymentCreate[]; print_receipt?: boolean } }
const pending = ref<Pending | null>(null)
const storageKey = computed(() => `eleven.order-payment.${auth.user?.id || ''}.${props.pedidoId}`)
let generation = 0, disposed = false
function stash() { try { if (pending.value) sessionStorage.setItem(storageKey.value, JSON.stringify(pending.value)); else sessionStorage.removeItem(storageKey.value) } catch { /* in-memory retry remains available */ } }
function setRate() {
  // The order is priced in dollars at its saved quote. Changing today's USD/G$
  // must not make a US$60 balance become US$59 after reserving the merchandise.
  const quote = { ...rates.exchangeRates, 'G$': order.value?.usd_rate_gs || rates.exchangeRates['G$'] }
  rate.value = paymentRate(currency.value, quote) || null
}
watch(method, () => { amount.value = null; reference.value = ''; fee.value = true; setRate() })
watch(fee, () => { amount.value = null })
function fillTotal() {
  if (!order.value || !validRate.value) return
  if (card.value) amount.value = cardCharge(order.value.balance_gs, fee.value)
  else {
    // Preserve the reserved prices: cash can supply real change; other methods
    // take the lower cent, leaving a visible balance to settle in another method.
    const value = order.value.balance_gs / Number(rate.value) * 100
    amount.value = (method.value.startsWith('cash_') ? Math.ceil(value - 1e-8) : Math.floor(value + 1e-8)) / 100
  }
}
async function load() {
  if (busy.value) return
  const request = ++generation
  loading.value = true; error.value = ''
  try { const result = await orderReservations.detail(props.pedidoId); if (!disposed && request === generation) order.value = result }
  catch (err) { if (!disposed && request === generation) { order.value = null; error.value = reservationError(err) } }
  finally { if (!disposed && request === generation) loading.value = false }
}
function back() { router.push({ path: '/pedidos', query: { pedido_id: props.pedidoId } }) }
async function submit(kind: Pending['kind']) {
  if (busy.value || pending.value || !order.value || !(kind === 'payment' ? canDeposit.value : canComplete.value)) return
  const body: Pending['body'] = { request_id: crypto.randomUUID(), confirm: true, expected_version: order.value.commerce_version }
  if (kind === 'payment') body.payment = payment.value!
  else { body.payments = order.value.balance_gs > 0 && payment.value ? [payment.value] : []; body.print_receipt = true }
  pending.value = { kind, orderId: props.pedidoId, userId: auth.user!.id, body }
  stash(); await retry()
}
async function retry() {
  const intent = pending.value
  if (!intent || busy.value || intent.userId !== auth.user?.id || intent.orderId !== props.pedidoId) return
  const request = generation
  busy.value = true; error.value = ''; notice.value = ''
  try {
    if (intent.kind === 'payment') {
      const updated = await orderReservations.payment(intent.orderId, { ...intent.body, payment: intent.body.payment! })
      if (disposed || request !== generation) return
      order.value = updated; notice.value = uiText('Recebimento registrado. Pedido mantido separado.')
    } else {
      const sale = await orderReservations.checkout(intent.orderId, { ...intent.body, payments: intent.body.payments || [], print_receipt: true })
      if (disposed || request !== generation) return
      lastSale.value = sale; showReceipt.value = true
      // A committed checkout stays successful even if the subsequent read fails.
      if (order.value) order.value = { ...order.value, commerce_status: 'completed', sale_id: sale.id, balance_gs: 0, paid_gs: order.value.total_gs }
      notice.value = uiText('Venda concluída. Os pagamentos anteriores foram aproveitados.')
      void orderReservations.detail(intent.orderId).then(updated => {
        if (!disposed && request === generation && updated.commerce_status === 'completed') order.value = updated
      }).catch(() => { /* the sale is already committed; its receipt remains available */ })
    }
    pending.value = null; stash(); amount.value = null; reference.value = ''
  } catch (err) {
    if (disposed || request !== generation) return
    error.value = reservationError(err)
    const status = (err as { response?: { status?: number } })?.response?.status
    if (status && status < 500) { pending.value = null; stash() }
    else error.value = uiText('A conexão falhou antes da confirmação. Confira e tente novamente; a mesma solicitação será recuperada sem duplicar o recebimento.')
  } finally { if (!disposed && request === generation) busy.value = false }
}
watch(() => props.pedidoId, async () => {
  generation++; busy.value = false
  const requestedOrder = props.pedidoId
  order.value = null; pending.value = null; amount.value = null
  try {
    const saved = JSON.parse(sessionStorage.getItem(storageKey.value) || 'null') as Pending | null
    if (saved && saved.orderId === props.pedidoId && saved.userId === auth.user?.id && ['payment', 'checkout'].includes(saved.kind) && saved.body?.request_id) {
      pending.value = saved
      error.value = uiText('Há um recebimento aguardando confirmação. Confira e tente novamente para recuperar o resultado.')
    }
  } catch { /* no usable saved request */ }
  await load()
  if (disposed || props.pedidoId !== requestedOrder) return
  if (pending.value) error.value = uiText('Há uma solicitação aguardando confirmação. Confira e tente novamente para recuperar o resultado.')
  try { await rates.loadCurrentRates(); ratesError.value = !!rates.error } catch { ratesError.value = true }
  if (!disposed) setRate()
}, { immediate: true })
watch(() => auth.user?.id, () => { generation++; order.value = null; pending.value = null; busy.value = false })
onBeforeUnmount(() => { disposed = true; generation++ })
</script>

<style scoped>
.order-checkout { min-height: 100%; background: #f7f9fc; color: #182235; }
.order-columns { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(320px, 1fr); gap: 20px; max-width: 1150px; margin: 20px auto; padding: 0 20px 28px; align-items: start; }
.order-card { background: white; border: 1px solid #e0e7f0; border-radius: 18px; overflow: hidden; box-shadow: 0 3px 14px #14243b05; }
.order-heading, .order-totals { padding: 22px; }
.order-eyebrow { color: #64748b; font-size: 12px; font-weight: 650; }
.order-heading h2 { margin: 6px 0; font-size: 23px; letter-spacing: -.025em; }
.order-heading p { margin: 8px 0 15px; color: #64748b; font-size: 13px; }
.order-badge { color: #166534; background: #eaf8ef; border-radius: 8px; padding: 5px 9px; font-size: 12px; }
.order-line { padding: 16px 22px; border-top: 1px solid #edf1f6; display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; align-items: start; gap: 10px; font-size: 14px; }
.order-line small, .order-payment small { display: block; color: #64748b; margin-top: 5px; font-size: 12px; }
.order-piece-count { color: #2563eb; font-weight: 700; }
.order-line-value { font-size: 13px; white-space: nowrap; }
.order-totals { border-top: 1px solid #edf1f6; background: #fbfcff; }
.order-totals > div { display: flex; justify-content: space-between; gap: 15px; margin: 8px 0; }
.order-total { font-size: 19px; }
.order-totals small, .order-payment-form > small { color: #64748b; line-height: 1.5; font-size: 12px; }
.order-payment-summary { background: #f0f6ff; padding: 22px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.order-payment-summary span, .order-payment-summary small { display: block; color: #52627c; font-size: 12px; }
.order-payment-summary strong { display: block; margin: 6px 0; font-size: 22px; }
.order-payment-summary > div:first-child strong { color: #15805b; }
.order-payment-summary > div:last-child strong { color: #2153ca; }
.order-history { padding: 18px 22px; border-bottom: 1px solid #edf1f6; }
.order-history summary { cursor: pointer; font-size: 13px; font-weight: 600; }
.order-payment { display: flex; justify-content: space-between; gap: 16px; padding-top: 16px; font-size: 13px; }
.order-payment.reversed { opacity: .6; }
.order-payment-form { padding: 22px; border: 0; margin: 0; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.order-payment-form h3 { font-size: 16px; margin: 0 0 3px; }
.order-payment-form label:not(.order-checkbox) { display: flex; flex-direction: column; gap: 7px; color: #475569; font-size: 13px; }
.order-payment-form :deep(input:not([type=checkbox])) { min-height: 44px; border: 1px solid #d3dce8; background: white; padding: 9px 12px; border-radius: 10px; width: 100%; min-width: 0; font-size: 16px; box-sizing: border-box; }
.order-amount-row { display: flex; gap: 8px; }
.order-total-button { --button-bg: #f5f3ff; --button-fg: #6d28d9; --button-border: #ddd6fe; }
.order-checkbox { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.order-payment-preview { display: flex; flex-direction: column; gap: 6px; padding: 12px; border-radius: 10px; background: #f8fafc; font-size: 13px; }
.order-finish { width: 100%; min-height: 48px; margin-top: 6px; }
.order-error { color: #9f3030; background: #fff1f1; padding: 14px; margin: 12px 20px; border-radius: 10px; font-size: 14px; line-height: 1.5; }
.order-error button { margin: 8px 0 0 8px; }
.order-payment-form .order-error { margin: 0; }
.order-notice, .order-paid { color: #166534; background: #eaf8ef; padding: 14px; border-radius: 10px; font-size: 14px; }
.order-notice { margin: 12px 20px; }
.order-completed { padding: 22px; }
@media (max-width: 760px) { .order-columns { grid-template-columns: 1fr; padding: 0 12px 20px; gap: 14px; margin-top: 12px; } .order-heading, .order-totals, .order-payment-form, .order-payment-summary { padding: 17px; } .order-line { padding: 14px 17px; } }
</style>
