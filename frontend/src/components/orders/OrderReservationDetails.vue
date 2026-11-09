<template>
  <Teleport to="body">
    <div class="erp-dialog-backdrop" @click.self="close">
      <section v-erp-dialog class="erp-dialog erp-dialog--lg reservation-details" aria-labelledby="reserved-order-title">
        <header class="erp-dialog__header"><div><p class="eyebrow">{{ uiText(order?.delivered_at ? 'CONDICIONAL' : 'PEDIDO SEPARADO') }}</p><h2 id="reserved-order-title">{{ order?.numero_pedido || uiText('Carregando…') }}</h2></div><button type="button" data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :aria-label="uiText('Fechar')" :disabled="busy || commandUncertain" @click="close">×</button></header>
        <div class="erp-dialog__body details-body">
          <div v-if="loading" class="loading" role="status">{{ uiText('Carregando separação…') }}</div>
          <div v-else-if="!order" class="inline-error" role="alert">{{ error }} <button class="erp-button erp-button--secondary" @click="load">{{ uiText('Tentar novamente') }}</button></div>
          <template v-else>
            <div class="order-identity"><div class="bag-icon"><ShoppingBag :size="27" /></div><div><h3>{{ order.cliente_nome }}</h3><p>{{ uiText('Separado por') }} {{ order.vendedor_nome }} · {{ formatDateTime(order.reserved_at) }}</p><span class="commerce-badge" :class="order.commerce_status">{{ reservationStatusLabel(order.commerce_status, order.paid_gs, order.balance_gs) }}</span></div></div>
            <p v-if="order.delivered_at" class="conditional-info">{{ uiText('Peças entregues ao cliente em') }} {{ formatDateTime(order.delivered_at) }}. {{ uiText('Devolva as peças não escolhidas antes de concluir a venda.') }}</p>
            <p v-if="Number(order.refund_due_gs) > 0" class="inline-error">{{ uiText('Valor a devolver ao cliente') }}: <strong>{{ saleUsd(order.refund_due_gs!, order.usd_rate_gs) }}</strong>. {{ uiText('Lucas precisa registrar a devolução do pagamento para concluir.') }}</p>
            <div class="order-metrics"><div><span>{{ uiText('Total') }}</span><strong>{{ saleUsd(order.total_gs, order.usd_rate_gs) }}</strong></div><div><span>{{ uiText('Recebido') }}</span><strong class="paid">{{ saleUsd(order.paid_gs, order.usd_rate_gs) }}</strong></div><div><span>{{ uiText('Falta pagar') }}</span><strong :class="{ paid: order.balance_gs === 0 }">{{ saleUsd(order.balance_gs, order.usd_rate_gs) }}</strong></div></div>
            <p v-if="order.notas" class="order-notes"><MapPin :size="16" /><span>{{ order.notas }}</span></p>
            <p v-if="Number(order.change_gs) > 0" class="order-notes">{{ uiText('Troco') }}: {{ saleUsd(order.change_gs!, order.usd_rate_gs) }}</p>
            <div class="section-heading"><h3>{{ uiText('Peças do pedido') }} <small>{{ pieceCount }}</small></h3><button v-if="order.commerce_status === 'reserved'" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain" @click="emit('edit', order.id)"><Pencil :size="15" />{{ uiText('Editar separação') }}</button></div>
            <div class="reserved-items"><article v-for="item in order.items" :key="item.id" class="reserved-item"><ProductThumbnail :item="{ id: item.item_id, has_image: item.has_image ?? true, updated_at: item.updated_at || order.reserved_at }" :alt="item.item_name" /><div><strong>{{ item.item_name }}</strong><small>{{ [item.item_size, item.item_color, uiText(item.location === 'loja' ? 'Loja' : 'Depósito')].filter(Boolean).join(' · ') }}</small><small>{{ item.item_sku }}</small><small v-if="item.returned_quantity">{{ uiText('Devolvidas') }}: {{ item.returned_quantity }} / {{ item.quantity }}</small></div><div class="item-count"><strong>{{ item.remaining_quantity ?? item.quantity }} <small>{{ uiText('un') }}</small></strong><small>{{ saleUsd(item.remaining_total_gs ?? item.total_gs, order.usd_rate_gs) }}</small></div></article></div>
            <details class="payment-history" :open="order.payments.length > 0"><summary>{{ uiText('Pagamentos registrados') }} <span>{{ order.payments.length }}</span></summary><p v-if="!order.payments.length" class="muted">{{ uiText('Nenhum valor recebido ainda. Use Receber no PDV para registrar um sinal ou quitar o pedido.') }}</p><article v-for="payment in order.payments" :key="payment.id" class="payment-row" :class="{ reversed: !!payment.reversed_at }"><div><strong>{{ paymentLabel(payment.method) }}</strong><small>{{ formatDateTime(payment.created_at) }}</small><small v-if="payment.reversed_at">{{ uiText('Devolução registrada') }} · {{ payment.reversal_reason }}</small><small v-for="refund in payment.refunds || []" :key="refund.id">{{ uiText('Devolução registrada') }}: {{ paymentSymbol(payment.currency) }} {{ uiNumber(refund.amount_original, 2) }} · {{ formatDateTime(refund.created_at) }} · {{ refund.reason }}</small><small v-if="payment.reference">{{ payment.reference }}</small></div><div class="payment-values"><strong>{{ paymentSymbol(payment.currency) }} {{ uiNumber(payment.amount_original, 2) }}</strong><small>{{ saleUsd(payment.amount_gs, order.usd_rate_gs) }}</small><button v-if="auth.isOwner && Number(payment.remaining_gs ?? (payment.reversed_at ? 0 : payment.amount_gs)) > 0 && active" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain" @click="beginReverse(payment.id)">{{ uiText('Registrar devolução') }}</button></div></article></details>
            <div v-if="action" ref="actionPanel" class="confirmation-panel" :class="{ warning: action !== 'print' }">
              <h4>{{ actionTitle }}</h4>
              <p>{{ actionDescription }}</p>
              <div v-if="action === 'return'" class="return-lines">
                <label v-for="item in order.items.filter(line => (line.remaining_quantity ?? line.quantity) > 0)" :key="item.id">
                  <span><strong>{{ item.item_name }}</strong><small>{{ item.item_size }} · {{ item.item_color }} · {{ uiText('Retorna para') }} {{ uiText(item.location === 'loja' ? 'Loja' : 'Depósito') }}</small></span>
                  <input v-model.number="returns[item.id]" type="number" min="0" :max="item.remaining_quantity ?? item.quantity" step="1" :aria-label="uiText('Quantidade devolvida de {0}', { 0: item.item_name })" :disabled="busy || commandUncertain" />
                </label>
              </div>
              <label v-if="action === 'reverse'">{{ uiText('Valor do pedido a devolver (G$)') }}<DecimalInput v-model="refundAmount" :disabled="busy || commandUncertain" :aria-label="uiText('Valor do pedido a devolver (G$)')" /></label>
              <label v-if="needsReason">{{ uiText('Motivo') }}<textarea v-model="reason" rows="2" maxlength="500" :disabled="busy || commandUncertain" /></label>
              <template v-if="action === 'reverse'">
                <button class="erp-button erp-button--secondary" :disabled="busy || commandUncertain || !validAction" @click="previewRefund">{{ uiText('Calcular devolução') }}</button>
                <p v-if="refundPreview" class="refund-preview">{{ uiText('Devolva ao cliente') }}: <strong>{{ paymentSymbol(refundPreview.currency) }} {{ uiNumber(Number(refundPreview.amount_original), 2) }}</strong><small v-if="Number(refundPreview.card_fee_gs) > 0">{{ uiText('Inclui a taxa de cartão correspondente.') }}</small></p>
              </template>
              <label v-if="action !== 'reverse' || refundPreview" class="confirm-check"><input v-model="confirmed" type="checkbox" :disabled="busy || commandUncertain" />{{ actionConfirmation }}</label>
              <div class="confirmation-actions"><button class="erp-button erp-button--secondary erp-button--sm" :disabled="busy || commandUncertain" @click="clearAction">{{ uiText('Voltar') }}</button><button class="erp-button erp-button--primary erp-button--sm" :disabled="busy || (!commandUncertain && (!confirmed || !validAction || action === 'reverse' && !refundPreview))" @click="confirmAction">{{ uiText(busy ? 'Processando…' : commandUncertain ? 'Repetir confirmação' : action === 'print' ? 'Imprimir ticket' : 'Confirmar') }}</button></div>
              <p v-if="commandUncertain" role="alert">{{ uiText('Resposta não confirmada. Repetir recupera a mesma solicitação sem duplicar a operação.') }}</p>
            </div>
            <div v-if="printState?.job" class="print-status" role="status"><Printer :size="17" /><div><strong>{{ printState.printer?.name || uiText('Impressora do caixa') }}</strong><p>{{ printStatus }}</p><small v-if="printState.job.diagnostic_message">{{ printState.job.diagnostic_message }}</small></div><button class="erp-button erp-button--ghost erp-button--sm" :disabled="busy" @click="refreshPrint">{{ uiText('Atualizar') }}</button></div>
            <p v-if="error" class="inline-error" role="alert">{{ error }}</p><p v-if="notice" class="inline-success" role="status">{{ notice }}</p>
            <div class="secondary-actions"><button class="erp-button erp-button--secondary erp-button--sm" :disabled="busy || commandUncertain" @click="download"><Download :size="16" />{{ uiText('Salvar ticket PDF') }}</button><button v-if="active" class="erp-button erp-button--secondary erp-button--sm" :disabled="busy || commandUncertain || !!printState?.job && ['pending', 'claimed'].includes(printState.job.status)" @click="beginPrint"><Printer :size="16" />{{ uiText(order.delivered_at ? 'Imprimir condicional' : 'Imprimir separação') }}</button><button class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain" @click="emit('logistics', order.id)"><Truck :size="16" />{{ uiText('Entrega e anexos') }}</button></div>
            <div v-if="active" class="secondary-actions">
              <button v-if="order.commerce_status === 'reserved'" class="erp-button erp-button--secondary" :disabled="busy || commandUncertain" @click="beginAction('dispatch')">{{ uiText('Entregar em condicional') }}</button>
              <button v-if="order.commerce_status === 'conditional' && pieceCount > 0" class="erp-button erp-button--secondary" :disabled="busy || commandUncertain" @click="beginAction('return')">{{ uiText('Receber peças de volta') }}</button>
            </div>
            <div v-if="order.commerce_status === 'reserved'" class="cancel-area"><button class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain || order.paid_gs > 0" @click="beginCancel">{{ uiText('Cancelar reserva') }}</button><small v-if="order.paid_gs > 0">{{ uiText('Antes de liberar as peças, Lucas precisa conferir e registrar a devolução dos pagamentos.') }}</small></div>
          </template>
        </div>
        <footer v-if="order" class="erp-dialog__footer"><button class="erp-button erp-button--secondary" :disabled="busy || commandUncertain" @click="close">{{ uiText('Fechar') }}</button><button v-if="active" class="erp-button erp-button--primary" :disabled="busy || commandUncertain || !!action || Number(order.refund_due_gs) > 0 || pieceCount === 0" @click="checkout"><CreditCard :size="18" />{{ uiText(order.balance_gs > 0 ? 'Receber no PDV' : 'Concluir venda no PDV') }}</button><button v-else-if="order.sale_id" class="erp-button erp-button--primary" @click="router.push({ path: '/vendas-pdv', query: { sale_id: order.sale_id } })">{{ uiText('Ver venda') }}<ArrowUpRight :size="17" /></button></footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ShoppingBag, MapPin, Pencil, Printer, Download, Truck, CreditCard, ArrowUpRight } from 'lucide-vue-next'
import { vErpDialog } from '@/directives/erpDialog'
import DecimalInput from '@/components/forms/DecimalInput.vue'
import ProductThumbnail from '@/components/inventory/ProductThumbnail.vue'
import { orderReservations, reservationError, reservationStatusLabel, type ReservationCommand, type ReservationDetail } from '@/services/orderReservations'
import type { ReceiptState } from '@/services/pdvReceipts'
import { saleUsd } from '@/services/saleUsd'
import { paymentLabel, paymentSymbol } from '@/services/pdvPayments'
import { uiText, uiNumber } from '@/i18n/uiText'
import { formatDateTime } from '@/utils/datetime'
import { useAuthStore } from '@/stores/auth'
const props = defineProps<{ orderId: string }>()
const emit = defineEmits<{ close: []; edit: [id: string]; updated: [value: ReservationDetail]; logistics: [id: string] }>()
const router = useRouter(), auth = useAuthStore(), order = ref<ReservationDetail | null>(null)
const loading = ref(true), busy = ref(false), error = ref(''), notice = ref(''), action = ref<Action | null>(null)
const confirmed = ref(false), reason = ref(''), reverseId = ref(''), commandUncertain = ref(false), printState = ref<ReceiptState | null>(null)
type Action = 'print' | 'cancel' | 'reverse' | 'dispatch' | 'return'
type Command = ReservationCommand & { reason?: string; amount_gs?: number; lines?: Array<{ line_id: string; quantity: number }> }
const actionPanel = ref<HTMLElement | null>(null)
const returns = ref<Record<string, number>>({}), refundAmount = ref<number | null>(null), refundPreview = ref<Awaited<ReturnType<typeof orderReservations.refundPreview>> | null>(null)
const storageKey = `eleven.order-action.${auth.user?.id || ''}.${props.orderId}`
let previewCommand: Command | null = null
let pending: Command | null = null, disposed = false, printTimer: ReturnType<typeof setTimeout> | undefined
const pieceCount = computed(() => order.value?.items.reduce((sum, item) => sum + (item.remaining_quantity ?? item.quantity), 0) || 0)
const active = computed(() => ['reserved', 'conditional'].includes(order.value?.commerce_status || ''))
const needsReason = computed(() => ['cancel', 'reverse', 'return'].includes(action.value || ''))
const returnLines = computed(() => Object.entries(returns.value).filter(([, quantity]) => Number(quantity) > 0).map(([line_id, quantity]) => ({ line_id, quantity: Number(quantity) })))
const validAction = computed(() => (!needsReason.value || reason.value.trim().length >= 3) && (action.value !== 'return' || returnLines.value.length > 0 && returnLines.value.every(line => Number.isInteger(line.quantity) && line.quantity <= (order.value?.items.find(item => item.id === line.line_id)?.remaining_quantity ?? order.value?.items.find(item => item.id === line.line_id)?.quantity ?? 0))) && (action.value !== 'reverse' || Number(refundAmount.value) > 0 && Number(refundAmount.value) <= Number(order.value?.payments.find(payment => payment.id === reverseId.value)?.remaining_gs ?? order.value?.payments.find(payment => payment.id === reverseId.value)?.amount_gs ?? 0)))
const actionTitle = computed(() => uiText(({ print: 'Ticket de separação', cancel: 'Cancelar e liberar as peças', reverse: 'Registrar devolução do pagamento', dispatch: 'Entregar em condicional', return: 'Receber peças de volta' } as Record<Action, string>)[action.value || 'print']))
const actionDescription = computed(() => uiText(({ print: 'O ticket identifica pedido, cliente, vendedor, peças e horário. Confira a saída anterior antes de solicitar outra cópia.', cancel: 'As unidades voltam a ficar disponíveis para outros clientes. O histórico do pedido é preservado.', reverse: 'Este registro não devolve dinheiro pela operadora. Confirme somente depois de conferir a devolução realizada fora do ERP.', dispatch: 'As peças saem do estoque físico e ficam com o cliente para escolha. Ainda não é uma venda concluída.', return: 'Confira as peças recebidas. Cada quantidade volta ao local de origem indicado abaixo.' } as Record<Action, string>)[action.value || 'print']))
const actionConfirmation = computed(() => uiText(({ print: 'Conferi este pedido e quero imprimir o ticket.', cancel: 'Conferi as peças que serão liberadas.', reverse: 'Conferi a devolução do valor ao cliente.', dispatch: 'Conferi o cliente e todas as peças entregues.', return: 'Recebi e conferi fisicamente estas peças.' } as Record<Action, string>)[action.value || 'print']))
watch([reason, refundAmount], () => { if (action.value === 'reverse' && !commandUncertain.value) { refundPreview.value = null; previewCommand = null; confirmed.value = false } }, { flush: 'sync' })
function stash() { try { if (pending) sessionStorage.setItem(storageKey, JSON.stringify({ action: action.value, body: pending, reverseId: reverseId.value, refundPreview: refundPreview.value })); else sessionStorage.removeItem(storageKey) } catch { /* retry remains available in memory */ } }
const printStatus = computed(() => uiText(({ pending: 'Na fila do caixa. Mantenha o agente conectado.', claimed: 'O agente está processando o ticket.', submitted: 'Enviado à impressora. Confira a saída do papel.', uncertain: 'Envio incerto. Confira a fila e o papel antes de pedir outra cópia.', failed: 'Falha ao enviar. Confira o diagnóstico antes de tentar outra cópia.', cancelled: 'Impressão cancelada.', expired: 'Ticket expirado sem coleta.' } as Record<string, string>)[printState.value?.job?.status || ''] || 'Consulte a fila para conferir o envio.'))
function close() { if (!busy.value && !commandUncertain.value) emit('close') }
async function load() { loading.value = true; error.value = ''; try { const value = await orderReservations.detail(props.orderId); if (!disposed) order.value = value } catch (caught) { if (!disposed) error.value = reservationError(caught) } finally { if (!disposed) loading.value = false } }
function clearAction() { if (busy.value || commandUncertain.value) return; action.value = null; confirmed.value = false; reason.value = ''; pending = null; returns.value = {}; refundAmount.value = null; refundPreview.value = null; previewCommand = null }
function beginPrint() { clearAction(); action.value = 'print'; error.value = ''; notice.value = '' }
function beginCancel() { clearAction(); action.value = 'cancel'; error.value = ''; notice.value = '' }
function beginReverse(id: string) { beginAction('reverse'); reverseId.value = id; const payment = order.value?.payments.find(item => item.id === id); refundAmount.value = Math.min(Number(payment?.remaining_gs ?? payment?.amount_gs ?? 0), Number(order.value?.refund_due_gs) || Infinity) }
function beginAction(value: Action) { if (busy.value || commandUncertain.value) return; clearAction(); action.value = value; if (value === 'return') returns.value = Object.fromEntries((order.value?.items || []).map(item => [item.id, 0])); error.value = ''; notice.value = '' }
watch(action, async value => { if (value) { await nextTick(); actionPanel.value?.scrollIntoView?.({ block: 'start', behavior: 'instant' }) } })
function buildCommand(): Command { return { request_id: crypto.randomUUID(), confirm: true, expected_version: order.value!.commerce_version, ...(needsReason.value ? { reason: reason.value.trim() } : {}), ...(action.value === 'return' ? { lines: returnLines.value } : {}), ...(action.value === 'reverse' ? { amount_gs: Number(refundAmount.value) } : {}) } }
async function previewRefund() {
  if (!order.value || busy.value || commandUncertain.value || !validAction.value) return
  busy.value = true; error.value = ''; confirmed.value = false
  const command = buildCommand()
  try { const preview = await orderReservations.refundPreview(order.value.id, reverseId.value, { ...command, reason: command.reason! }); if (!disposed) { refundPreview.value = preview; previewCommand = command } }
  catch (caught) { if (!disposed) error.value = reservationError(caught) }
  finally { busy.value = false }
}
async function confirmAction() {
  if (!order.value || !action.value || busy.value || (!pending && (!confirmed.value || !validAction.value || action.value === 'reverse' && !refundPreview.value))) return
  pending ||= action.value === 'reverse' ? previewCommand : buildCommand()
  if (!pending) return
  stash(); busy.value = true; error.value = ''
  try {
    if (action.value === 'print') { const state = await orderReservations.printTicket(order.value.id, pending); if (!disposed) { printState.value = state; schedulePrintRefresh() } }
    else {
      const command = { ...pending, reason: pending.reason! }
      const value = action.value === 'cancel' ? await orderReservations.cancel(order.value.id, command)
        : action.value === 'dispatch' ? await orderReservations.dispatch(order.value.id, pending)
        : action.value === 'return' ? await orderReservations.returnItems(order.value.id, { ...command, lines: pending.lines! })
        : await orderReservations.reversePayment(order.value.id, reverseId.value, command)
      if (!disposed) { order.value = value; emit('updated', value); notice.value = uiText(action.value === 'cancel' ? 'Reserva cancelada. As peças foram liberadas.' : action.value === 'dispatch' ? 'Condicional registrada. Imprima o ticket para acompanhar as peças.' : action.value === 'return' ? 'Peças devolvidas ao estoque. Confira o saldo atualizado.' : 'Devolução registrada no histórico do pedido.') }
    }
    pending = null; stash(); commandUncertain.value = false; action.value = null; confirmed.value = false; reason.value = ''
  } catch (caught) {
    const status = (caught as { response?: { status?: number } })?.response?.status
    commandUncertain.value = !status || status >= 500
    if (!commandUncertain.value) { pending = null; stash() }
    if (!disposed) error.value = reservationError(caught)
  } finally { busy.value = false }
}
async function refreshPrint() {
  try { const state = await orderReservations.ticketState(props.orderId); if (!disposed) { printState.value = state; schedulePrintRefresh() } }
  catch { /* Opening details does not require a printer; mutations surface their errors. */ }
}
function schedulePrintRefresh() { clearTimeout(printTimer); if (!disposed && printState.value?.job && ['pending', 'claimed'].includes(printState.value.job.status)) printTimer = setTimeout(refreshPrint, 5000) }
async function download() {
  if (busy.value || !order.value) return
  busy.value = true; error.value = ''
  try {
    const content = await orderReservations.ticketPdf(order.value.id)
    if (disposed) return
    if (new TextDecoder().decode(new Uint8Array(content).slice(0, 5)) !== '%PDF-') throw new Error('pdf')
    const url = URL.createObjectURL(new Blob([content], { type: 'application/pdf' })), anchor = document.createElement('a')
    anchor.href = url; anchor.download = `eleven-separacao-${order.value.numero_pedido.replace(/[^a-zA-Z0-9_-]/g, '')}.pdf`; document.body.append(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (caught) { if (!disposed) error.value = reservationError(caught) }
  finally { busy.value = false }
}
function checkout() { if (!busy.value && !commandUncertain.value) void router.push({ path: '/pdv', query: { pedido_id: props.orderId } }) }
onMounted(() => { try { const saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null'); if (saved?.body?.request_id && ['print', 'cancel', 'reverse', 'dispatch', 'return'].includes(saved.action)) { pending = saved.body; action.value = saved.action; reverseId.value = saved.reverseId || ''; reason.value = pending!.reason || ''; returns.value = Object.fromEntries((pending!.lines || []).map(line => [line.line_id, line.quantity])); refundAmount.value = pending!.amount_gs ?? null; refundPreview.value = saved.refundPreview || null; confirmed.value = true; commandUncertain.value = true } } catch { /* no usable saved request */ } void load(); void refreshPrint() })
onBeforeUnmount(() => { disposed = true; clearTimeout(printTimer) })
</script>

<style scoped>
.conditional-info{font-size:.8rem;line-height:1.6;color:#5b21b6;background:#f5f3ff;padding:12px;border-radius:10px}.return-lines{display:grid;gap:10px;margin:12px 0}.return-lines label{display:flex;gap:10px;align-items:center}.return-lines span{flex:1;min-width:0;font-size:.8rem}.return-lines small,.refund-preview small{display:block;margin-top:4px;font-size:.72rem}.return-lines input{width:70px;padding:10px;border:1px solid #cbd5e1;border-radius:8px;font-size:16px}.refund-preview{background:white;border-radius:8px;padding:12px}.commerce-badge.conditional{background:#f5f3ff;color:#6d28d9}.commerce-badge.returned{background:#f1f5f9;color:#475569}
.erp-dialog-backdrop{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:1000}
.reservation-details{max-width:840px}.eyebrow{margin:0 0 4px;color:#64748b;font-size:.65rem;font-weight:750;letter-spacing:.12em}.reservation-details h2{font-size:1.15rem;margin:0}.details-body{padding:20px!important}.loading{padding:30px;text-align:center;color:#64748b}.order-identity{display:flex;gap:14px;align-items:center;margin-bottom:20px}.bag-icon{display:flex;align-items:center;justify-content:center;width:56px;height:56px;flex-shrink:0;border-radius:16px;color:#2563eb;background:#eff6ff}.order-identity h3{font-size:1.12rem;margin:0 0 4px;color:#0f172a}.order-identity p{font-size:.74rem;color:#64748b;margin:0 0 8px;line-height:1.5}.commerce-badge{display:inline-flex;gap:5px;align-items:center;font-size:.68rem;font-weight:650;padding:4px 8px;border-radius:20px;background:#fff7ed;color:#9a3412}.commerce-badge.completed{background:#ecfdf5;color:#047857}.commerce-badge.cancelled{background:#f1f5f9;color:#64748b}.order-metrics{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;margin-bottom:14px}.order-metrics>div{display:flex;flex-direction:column;gap:6px;padding:16px 14px;background:#f8fafc;min-width:0}.order-metrics>div+div{border-left:1px solid #e2e8f0}.order-metrics span{font-size:.73rem;color:#64748b}.order-metrics strong{font-size:1rem;color:#1e3a5f;overflow-wrap:anywhere}.order-metrics strong.paid{color:#059669}.order-notes{display:flex;gap:8px;align-items:flex-start;background:#fffbeb;color:#92400e;border-radius:10px;padding:12px;font-size:.8rem;line-height:1.5;white-space:pre-wrap}.order-notes svg{flex-shrink:0;margin-top:2px}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:18px 0 8px}.section-heading h3{font-size:.87rem;margin:0}.section-heading h3 small{color:#64748b;background:#f1f5f9;border-radius:10px;padding:2px 7px;margin-left:4px}.reserved-items{border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}.reserved-item{display:flex;gap:12px;align-items:center;padding:12px}.reserved-item+.reserved-item{border-top:1px solid #edf1f6}.reserved-item>img{width:44px;height:56px;object-fit:contain;border-radius:8px;background:#f8fafc}.reserved-item>div{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}.reserved-item strong{font-size:.79rem;line-height:1.4;overflow-wrap:anywhere}.reserved-item small{font-size:.7rem;color:#64748b}.reserved-item .item-count{flex:0 0 auto;align-items:flex-end;text-align:right}.item-count>strong{font-size:.95rem}.payment-history{margin-top:18px;border:1px solid #e2e8f0;border-radius:12px;padding:14px}.payment-history summary{cursor:pointer;font-size:.84rem;font-weight:650;color:#334155}.payment-history summary span{color:#64748b;background:#f1f5f9;border-radius:10px;padding:2px 7px;margin-left:5px}.payment-history .muted{font-size:.78rem;color:#64748b;line-height:1.6}.payment-row{display:flex;justify-content:space-between;gap:12px;margin-top:14px;padding-top:12px;border-top:1px solid #edf1f6}.payment-row>div{display:flex;flex-direction:column;gap:4px}.payment-row strong{font-size:.8rem}.payment-row small{font-size:.7rem;color:#64748b}.payment-values{text-align:right;align-items:flex-end}.payment-row.reversed{opacity:.65}.payment-row.reversed strong{text-decoration:line-through}.confirmation-panel{margin-top:18px;border:1px solid #bfdbfe;border-radius:12px;padding:15px;background:#eff6ff;color:#1e3a5f}.confirmation-panel.warning{border-color:#fed7aa;background:#fff7ed;color:#9a3412}.confirmation-panel h4{margin:0;font-size:.9rem}.confirmation-panel p{font-size:.78rem;line-height:1.6}.confirmation-panel>label{display:flex;flex-direction:column;gap:6px;font-size:.78rem}.confirmation-panel textarea{border:1px solid #cbd5e1;border-radius:8px;padding:9px;font:inherit;resize:vertical}.confirmation-panel .confirm-check{flex-direction:row;align-items:flex-start;margin:12px 0;line-height:1.5}.confirm-check input{width:17px;height:17px;margin-top:1px;accent-color:#2563eb}.confirmation-actions{display:flex;justify-content:flex-end;gap:8px}.secondary-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.cancel-area{display:flex;flex-wrap:wrap;gap:5px;margin-top:12px;align-items:center}.cancel-area button{color:#b45309}.cancel-area small{color:#64748b;font-size:.7rem;line-height:1.5}.inline-error{margin:12px 0;color:#a4420a;background:#fff7ed;border:1px solid #fed7aa;padding:10px 12px;border-radius:10px;font-size:.8rem;line-height:1.5}.inline-success{margin:12px 0;background:#ecfdf5;color:#047857;padding:10px 12px;border-radius:10px;font-size:.8rem}.print-status{display:flex;gap:9px;align-items:flex-start;margin-top:15px;padding:12px;background:#eff6ff;border-radius:10px;color:#1e3a5f;font-size:.78rem}.print-status>div{flex:1;min-width:0}.print-status svg{flex-shrink:0}.print-status p{margin:4px 0;line-height:1.5}.print-status small{font-size:.7rem}.erp-dialog__footer button{gap:7px}
@media(max-width:600px){.details-body{padding:15px!important}.order-metrics>div{padding:12px 9px}.order-metrics strong{font-size:.86rem}.order-metrics span{font-size:.67rem}.bag-icon{width:46px;height:46px;border-radius:13px}.order-identity h3{font-size:1rem}.section-heading{gap:6px}.section-heading button{font-size:.72rem}.reservation-details .erp-dialog__footer>.erp-button--primary{flex:1}.secondary-actions button{flex:1}.reserved-item{padding:10px;gap:8px}.confirmation-panel textarea{font-size:16px}}
</style>
