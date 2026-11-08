<template>
  <Teleport to="body">
    <div class="erp-dialog-backdrop" @click.self="close">
      <section v-erp-dialog class="erp-dialog erp-dialog--lg reservation-details" aria-labelledby="reserved-order-title">
        <header class="erp-dialog__header"><div><p class="eyebrow">{{ uiText('PEDIDO SEPARADO') }}</p><h2 id="reserved-order-title">{{ order?.numero_pedido || uiText('Carregando…') }}</h2></div><button type="button" data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :aria-label="uiText('Fechar')" :disabled="busy || commandUncertain" @click="close">×</button></header>
        <div class="erp-dialog__body details-body">
          <div v-if="loading" class="loading" role="status">{{ uiText('Carregando separação…') }}</div>
          <div v-else-if="!order" class="inline-error" role="alert">{{ error }} <button class="erp-button erp-button--secondary" @click="load">{{ uiText('Tentar novamente') }}</button></div>
          <template v-else>
            <div class="order-identity"><div class="bag-icon"><ShoppingBag :size="27" /></div><div><h3>{{ order.cliente_nome }}</h3><p>{{ uiText('Separado por') }} {{ order.vendedor_nome }} · {{ formatDateTime(order.reserved_at) }}</p><span class="commerce-badge" :class="order.commerce_status">{{ reservationStatusLabel(order.commerce_status, order.paid_gs, order.balance_gs) }}</span></div></div>
            <div class="order-metrics"><div><span>{{ uiText('Total') }}</span><strong>{{ saleUsd(order.total_gs, order.usd_rate_gs) }}</strong></div><div><span>{{ uiText('Recebido') }}</span><strong class="paid">{{ saleUsd(order.paid_gs, order.usd_rate_gs) }}</strong></div><div><span>{{ uiText('Falta pagar') }}</span><strong :class="{ paid: order.balance_gs === 0 }">{{ saleUsd(order.balance_gs, order.usd_rate_gs) }}</strong></div></div>
            <p v-if="order.notas" class="order-notes"><MapPin :size="16" /><span>{{ order.notas }}</span></p>
            <p v-if="Number(order.change_gs) > 0" class="order-notes">{{ uiText('Troco') }}: {{ saleUsd(order.change_gs!, order.usd_rate_gs) }}</p>
            <div class="section-heading"><h3>{{ uiText('Peças do pedido') }} <small>{{ pieceCount }}</small></h3><button v-if="order.commerce_status === 'reserved'" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain" @click="emit('edit', order.id)"><Pencil :size="15" />{{ uiText('Editar separação') }}</button></div>
            <div class="reserved-items"><article v-for="item in order.items" :key="item.id" class="reserved-item"><ProductThumbnail :item="{ id: item.item_id, has_image: item.has_image ?? true, updated_at: item.updated_at || order.reserved_at }" :alt="item.item_name" /><div><strong>{{ item.item_name }}</strong><small>{{ [item.item_size, item.item_color, uiText(item.location === 'loja' ? 'Loja' : 'Depósito')].filter(Boolean).join(' · ') }}</small><small>{{ item.item_sku }}</small></div><div class="item-count"><strong>{{ item.quantity }} <small>{{ uiText('un') }}</small></strong><small>{{ saleUsd(item.total_gs, order.usd_rate_gs) }}</small></div></article></div>
            <details class="payment-history" :open="order.payments.length > 0"><summary>{{ uiText('Pagamentos registrados') }} <span>{{ order.payments.length }}</span></summary><p v-if="!order.payments.length" class="muted">{{ uiText('Nenhum valor recebido ainda. Use Receber no PDV para registrar um sinal ou quitar o pedido.') }}</p><article v-for="payment in order.payments" :key="payment.id" class="payment-row" :class="{ reversed: !!payment.reversed_at }"><div><strong>{{ paymentLabel(payment.method) }}</strong><small>{{ formatDateTime(payment.created_at) }}</small><small v-if="payment.reversed_at">{{ uiText('Devolução registrada') }} · {{ payment.reversal_reason }}</small><small v-else-if="payment.reference">{{ payment.reference }}</small></div><div class="payment-values"><strong>{{ paymentSymbol(payment.currency) }} {{ uiNumber(payment.amount_original, 2) }}</strong><small>{{ saleUsd(payment.amount_gs, order.usd_rate_gs) }}</small><button v-if="auth.isOwner && !payment.reversed_at && order.commerce_status === 'reserved'" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain" @click="beginReverse(payment.id)">{{ uiText('Registrar devolução') }}</button></div></article></details>
            <div v-if="action" class="confirmation-panel" :class="{ warning: action !== 'print' }">
              <h4>{{ uiText(action === 'print' ? 'Ticket de separação' : action === 'cancel' ? 'Cancelar e liberar as peças' : 'Registrar devolução do pagamento') }}</h4>
              <p>{{ uiText(action === 'print' ? 'O ticket identifica pedido, cliente, vendedor, peças e horário. Confira a saída anterior antes de solicitar outra cópia.' : action === 'cancel' ? 'As unidades voltam a ficar disponíveis para outros clientes. O histórico do pedido é preservado.' : 'Este registro não devolve dinheiro pela operadora. Confirme somente depois de conferir a devolução realizada fora do ERP.') }}</p>
              <label v-if="action !== 'print'">{{ uiText('Motivo') }}<textarea v-model="reason" rows="2" maxlength="500" :disabled="busy || commandUncertain" /></label>
              <label class="confirm-check"><input v-model="confirmed" type="checkbox" :disabled="busy || commandUncertain" />{{ uiText(action === 'print' ? 'Conferi este pedido e quero imprimir o ticket.' : action === 'cancel' ? 'Conferi as peças que serão liberadas.' : 'Conferi a devolução do valor ao cliente.') }}</label>
              <div class="confirmation-actions"><button class="erp-button erp-button--secondary erp-button--sm" :disabled="busy || commandUncertain" @click="clearAction">{{ uiText('Voltar') }}</button><button class="erp-button erp-button--primary erp-button--sm" :disabled="busy || (!commandUncertain && (!confirmed || (action !== 'print' && reason.trim().length < 3)))" @click="confirmAction">{{ uiText(busy ? 'Processando…' : commandUncertain ? 'Repetir confirmação' : action === 'print' ? 'Imprimir ticket' : 'Confirmar') }}</button></div>
              <p v-if="commandUncertain" role="alert">{{ uiText('Resposta não confirmada. Repetir recupera a mesma solicitação sem duplicar a operação.') }}</p>
            </div>
            <div v-if="printState?.job" class="print-status" role="status"><Printer :size="17" /><div><strong>{{ printState.printer?.name || uiText('Impressora do caixa') }}</strong><p>{{ printStatus }}</p><small v-if="printState.job.diagnostic_message">{{ printState.job.diagnostic_message }}</small></div><button class="erp-button erp-button--ghost erp-button--sm" :disabled="busy" @click="refreshPrint">{{ uiText('Atualizar') }}</button></div>
            <p v-if="error" class="inline-error" role="alert">{{ error }}</p><p v-if="notice" class="inline-success" role="status">{{ notice }}</p>
            <div class="secondary-actions"><button class="erp-button erp-button--secondary erp-button--sm" :disabled="busy || commandUncertain" @click="download"><Download :size="16" />{{ uiText('Salvar ticket PDF') }}</button><button v-if="order.commerce_status === 'reserved'" class="erp-button erp-button--secondary erp-button--sm" :disabled="busy || commandUncertain || !!printState?.job && ['pending', 'claimed'].includes(printState.job.status)" @click="beginPrint"><Printer :size="16" />{{ uiText('Imprimir separação') }}</button><button class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain" @click="emit('logistics', order.id)"><Truck :size="16" />{{ uiText('Entrega e anexos') }}</button></div>
            <div v-if="order.commerce_status === 'reserved'" class="cancel-area"><button class="erp-button erp-button--ghost erp-button--sm" :disabled="busy || commandUncertain || order.paid_gs > 0" @click="beginCancel">{{ uiText('Cancelar reserva') }}</button><small v-if="order.paid_gs > 0">{{ uiText('Antes de liberar as peças, Lucas precisa conferir e registrar a devolução dos pagamentos.') }}</small></div>
          </template>
        </div>
        <footer v-if="order" class="erp-dialog__footer"><button class="erp-button erp-button--secondary" :disabled="busy || commandUncertain" @click="close">{{ uiText('Fechar') }}</button><button v-if="order.commerce_status === 'reserved'" class="erp-button erp-button--primary" :disabled="busy || commandUncertain" @click="checkout"><CreditCard :size="18" />{{ uiText(order.balance_gs > 0 ? 'Receber no PDV' : 'Concluir venda no PDV') }}</button><button v-else-if="order.sale_id" class="erp-button erp-button--primary" @click="router.push({ path: '/vendas-pdv', query: { sale_id: order.sale_id } })">{{ uiText('Ver venda') }}<ArrowUpRight :size="17" /></button></footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ShoppingBag, MapPin, Pencil, Printer, Download, Truck, CreditCard, ArrowUpRight } from 'lucide-vue-next'
import { vErpDialog } from '@/directives/erpDialog'
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
const loading = ref(true), busy = ref(false), error = ref(''), notice = ref(''), action = ref<'print' | 'cancel' | 'reverse' | null>(null)
const confirmed = ref(false), reason = ref(''), reverseId = ref(''), commandUncertain = ref(false), printState = ref<ReceiptState | null>(null)
let pending: (ReservationCommand & { reason?: string }) | null = null, disposed = false, printTimer: ReturnType<typeof setTimeout> | undefined
const pieceCount = computed(() => order.value?.items.reduce((sum, item) => sum + item.quantity, 0) || 0)
const printStatus = computed(() => uiText(({ pending: 'Na fila do caixa. Mantenha o agente conectado.', claimed: 'O agente está processando o ticket.', submitted: 'Enviado à impressora. Confira a saída do papel.', uncertain: 'Envio incerto. Confira a fila e o papel antes de pedir outra cópia.', failed: 'Falha ao enviar. Confira o diagnóstico antes de tentar outra cópia.', cancelled: 'Impressão cancelada.', expired: 'Ticket expirado sem coleta.' } as Record<string, string>)[printState.value?.job?.status || ''] || 'Consulte a fila para conferir o envio.'))
function close() { if (!busy.value && !commandUncertain.value) emit('close') }
async function load() { loading.value = true; error.value = ''; try { const value = await orderReservations.detail(props.orderId); if (!disposed) order.value = value } catch (caught) { if (!disposed) error.value = reservationError(caught) } finally { if (!disposed) loading.value = false } }
function clearAction() { if (busy.value || commandUncertain.value) return; action.value = null; confirmed.value = false; reason.value = ''; pending = null }
function beginPrint() { clearAction(); action.value = 'print'; error.value = ''; notice.value = '' }
function beginCancel() { clearAction(); action.value = 'cancel'; error.value = ''; notice.value = '' }
function beginReverse(id: string) { clearAction(); reverseId.value = id; action.value = 'reverse'; error.value = ''; notice.value = '' }
async function confirmAction() {
  if (!order.value || !action.value || busy.value || (!pending && (!confirmed.value || (action.value !== 'print' && reason.value.trim().length < 3)))) return
  pending ||= { request_id: crypto.randomUUID(), confirm: true, expected_version: order.value.commerce_version, ...(action.value === 'print' ? {} : { reason: reason.value.trim() }) }
  busy.value = true; error.value = ''
  try {
    if (action.value === 'print') { const state = await orderReservations.printTicket(order.value.id, pending); if (!disposed) { printState.value = state; schedulePrintRefresh() } }
    else {
      const command = { ...pending, reason: pending.reason! }
      const value = action.value === 'cancel' ? await orderReservations.cancel(order.value.id, command) : await orderReservations.reversePayment(order.value.id, reverseId.value, command)
      if (!disposed) { order.value = value; emit('updated', value); notice.value = uiText(action.value === 'cancel' ? 'Reserva cancelada. As peças foram liberadas.' : 'Devolução registrada no histórico do pedido.') }
    }
    pending = null; commandUncertain.value = false; action.value = null; confirmed.value = false; reason.value = ''
  } catch (caught) {
    const status = (caught as { response?: { status?: number } })?.response?.status
    commandUncertain.value = !status || status >= 500
    if (!commandUncertain.value) pending = null
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
onMounted(() => { void load(); void refreshPrint() })
onBeforeUnmount(() => { disposed = true; clearTimeout(printTimer) })
</script>

<style scoped>
.erp-dialog-backdrop{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:1000}
.reservation-details{max-width:840px}.eyebrow{margin:0 0 4px;color:#64748b;font-size:.65rem;font-weight:750;letter-spacing:.12em}.reservation-details h2{font-size:1.15rem;margin:0}.details-body{padding:20px!important}.loading{padding:30px;text-align:center;color:#64748b}.order-identity{display:flex;gap:14px;align-items:center;margin-bottom:20px}.bag-icon{display:flex;align-items:center;justify-content:center;width:56px;height:56px;flex-shrink:0;border-radius:16px;color:#2563eb;background:#eff6ff}.order-identity h3{font-size:1.12rem;margin:0 0 4px;color:#0f172a}.order-identity p{font-size:.74rem;color:#64748b;margin:0 0 8px;line-height:1.5}.commerce-badge{display:inline-flex;gap:5px;align-items:center;font-size:.68rem;font-weight:650;padding:4px 8px;border-radius:20px;background:#fff7ed;color:#9a3412}.commerce-badge.completed{background:#ecfdf5;color:#047857}.commerce-badge.cancelled{background:#f1f5f9;color:#64748b}.order-metrics{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;margin-bottom:14px}.order-metrics>div{display:flex;flex-direction:column;gap:6px;padding:16px 14px;background:#f8fafc;min-width:0}.order-metrics>div+div{border-left:1px solid #e2e8f0}.order-metrics span{font-size:.73rem;color:#64748b}.order-metrics strong{font-size:1rem;color:#1e3a5f;overflow-wrap:anywhere}.order-metrics strong.paid{color:#059669}.order-notes{display:flex;gap:8px;align-items:flex-start;background:#fffbeb;color:#92400e;border-radius:10px;padding:12px;font-size:.8rem;line-height:1.5;white-space:pre-wrap}.order-notes svg{flex-shrink:0;margin-top:2px}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:18px 0 8px}.section-heading h3{font-size:.87rem;margin:0}.section-heading h3 small{color:#64748b;background:#f1f5f9;border-radius:10px;padding:2px 7px;margin-left:4px}.reserved-items{border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}.reserved-item{display:flex;gap:12px;align-items:center;padding:12px}.reserved-item+.reserved-item{border-top:1px solid #edf1f6}.reserved-item>img{width:44px;height:56px;object-fit:contain;border-radius:8px;background:#f8fafc}.reserved-item>div{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}.reserved-item strong{font-size:.79rem;line-height:1.4;overflow-wrap:anywhere}.reserved-item small{font-size:.7rem;color:#64748b}.reserved-item .item-count{flex:0 0 auto;align-items:flex-end;text-align:right}.item-count>strong{font-size:.95rem}.payment-history{margin-top:18px;border:1px solid #e2e8f0;border-radius:12px;padding:14px}.payment-history summary{cursor:pointer;font-size:.84rem;font-weight:650;color:#334155}.payment-history summary span{color:#64748b;background:#f1f5f9;border-radius:10px;padding:2px 7px;margin-left:5px}.payment-history .muted{font-size:.78rem;color:#64748b;line-height:1.6}.payment-row{display:flex;justify-content:space-between;gap:12px;margin-top:14px;padding-top:12px;border-top:1px solid #edf1f6}.payment-row>div{display:flex;flex-direction:column;gap:4px}.payment-row strong{font-size:.8rem}.payment-row small{font-size:.7rem;color:#64748b}.payment-values{text-align:right;align-items:flex-end}.payment-row.reversed{opacity:.65}.payment-row.reversed strong{text-decoration:line-through}.confirmation-panel{margin-top:18px;border:1px solid #bfdbfe;border-radius:12px;padding:15px;background:#eff6ff;color:#1e3a5f}.confirmation-panel.warning{border-color:#fed7aa;background:#fff7ed;color:#9a3412}.confirmation-panel h4{margin:0;font-size:.9rem}.confirmation-panel p{font-size:.78rem;line-height:1.6}.confirmation-panel>label{display:flex;flex-direction:column;gap:6px;font-size:.78rem}.confirmation-panel textarea{border:1px solid #cbd5e1;border-radius:8px;padding:9px;font:inherit;resize:vertical}.confirmation-panel .confirm-check{flex-direction:row;align-items:flex-start;margin:12px 0;line-height:1.5}.confirm-check input{width:17px;height:17px;margin-top:1px;accent-color:#2563eb}.confirmation-actions{display:flex;justify-content:flex-end;gap:8px}.secondary-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:18px}.cancel-area{display:flex;flex-wrap:wrap;gap:5px;margin-top:12px;align-items:center}.cancel-area button{color:#b45309}.cancel-area small{color:#64748b;font-size:.7rem;line-height:1.5}.inline-error{margin:12px 0;color:#a4420a;background:#fff7ed;border:1px solid #fed7aa;padding:10px 12px;border-radius:10px;font-size:.8rem;line-height:1.5}.inline-success{margin:12px 0;background:#ecfdf5;color:#047857;padding:10px 12px;border-radius:10px;font-size:.8rem}.print-status{display:flex;gap:9px;align-items:flex-start;margin-top:15px;padding:12px;background:#eff6ff;border-radius:10px;color:#1e3a5f;font-size:.78rem}.print-status>div{flex:1;min-width:0}.print-status svg{flex-shrink:0}.print-status p{margin:4px 0;line-height:1.5}.print-status small{font-size:.7rem}.erp-dialog__footer button{gap:7px}
@media(max-width:600px){.details-body{padding:15px!important}.order-metrics>div{padding:12px 9px}.order-metrics strong{font-size:.86rem}.order-metrics span{font-size:.67rem}.bag-icon{width:46px;height:46px;border-radius:13px}.order-identity h3{font-size:1rem}.section-heading{gap:6px}.section-heading button{font-size:.72rem}.reservation-details .erp-dialog__footer>.erp-button--primary{flex:1}.secondary-actions button{flex:1}.reserved-item{padding:10px;gap:8px}.confirmation-panel textarea{font-size:16px}}
</style>
