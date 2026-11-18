<template>
  <section class="receipt-delivery no-print" aria-live="polite">
    <p v-if="loading">{{ uiText(available ? 'Consultando impressora do caixa…' : 'Conecte-se e atualize o estado antes de solicitar uma impressão.') }}</p>
    <template v-else-if="state?.printer || state?.job">
      <strong>{{ state.printer?.name || uiText('Ticket da venda') }}</strong>
      <p>{{ uiText(statusText) }}</p>
      <small v-if="state.job?.diagnostic_message">{{ state.job.diagnostic_message }}</small>
      <div class="delivery-actions">
        <button v-if="!state.job" type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="!canSendOriginal" @click="send()">{{ uiText('Imprimir no caixa') }}</button>
        <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="busy || !available || blocked" @click="refresh">{{ uiText('Atualizar estado') }}</button>
        <button v-if="state.job && !confirmCopy" type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="!canCopy" :aria-describedby="inQueue || !available || !stateVerified ? hintId : undefined" @click="confirmCopy=true">{{ uiText(copyKey ? 'Retomar solicitação anterior' : 'Outra cópia') }}</button>
      </div>
      <p v-if="state.job && inQueue" :id="hintId" class="delivery-hint">{{ uiText('Para evitar impressões duplicadas, aguarde o ticket sair da fila antes de pedir outra cópia. O estado é atualizado automaticamente.') }}</p>
      <p v-else-if="!available || !stateVerified" :id="hintId" class="delivery-hint">{{ uiText('Conecte-se e atualize o estado antes de solicitar uma impressão.') }}</p>
      <div v-if="confirmCopy">
        <p>{{ uiText(copyKey ? 'A resposta da tentativa anterior não chegou. Retome a mesma solicitação: se já foi aceita, não imprime outra cópia. Se ainda não foi aceita, poderá imprimir. Confira o papel antes de continuar.' : 'Confira o papel e a fila da impressora. Confirmar envia uma nova cópia, mesmo que a anterior já tenha saído.') }}</p>
        <button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="!canCopy" @click="send(true)">{{ uiText(copyKey ? 'Retomar solicitação anterior' : 'Confirmar nova cópia') }}</button>
        <button type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy" @click="confirmCopy=false">{{ uiText('Cancelar') }}</button>
      </div>
    </template>
    <p v-else-if="!error">{{ uiText('Impressora do caixa não ativada. Use a impressão neste aparelho ou configure os tickets em Configurações.') }}</p>
    <p v-if="error" role="alert">{{ error }} <button v-if="!blocked" type="button" class="erp-button erp-button--sm" :disabled="busy || !available" @click="refresh">{{ uiText('Tentar novamente') }}</button></p>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { uiText } from '@/i18n/uiText'
import { pdvReceipts, type ReceiptState } from '@/services/pdvReceipts'
import { saleError } from '@/services/pdvManagement'
import { storedToken } from '@/services/sessionStorage'
const props=defineProps<{saleId:string}>()
const state=ref<ReceiptState | null>(null), loading=ref(true), busy=ref(false), error=ref(''), confirmCopy=ref(false)
const stateVerified=ref(false), blocked=ref(false)
const available=ref(!document.hidden && navigator.onLine)
const ownerToken=storedToken()
const hintId=`receipt-copy-${useId()}`
const terminalStatuses=new Set(['submitted','uncertain','failed','expired','cancelled'])
const inQueue=computed(()=>!!state.value?.job && !terminalStatuses.has(state.value.job.status))
const canCopy=computed(()=>!!state.value?.job && !inQueue.value && stateVerified.value && available.value && !busy.value && !blocked.value)
const canSendOriginal=computed(()=>!!state.value?.printer && !state.value.job && stateVerified.value && available.value && !busy.value && !blocked.value)
let mounted=false, generation=0, failures=0, sessionEnded=false
let pollTimer: ReturnType<typeof setTimeout> | undefined
const copyKey=ref<string>()
const statusText=computed(()=>({pending:'Na fila do caixa. Mantenha o agente conectado.',claimed:'O agente está processando o ticket.',submitted:'Enviado à impressora. Confira a saída do papel.',uncertain:'Envio incerto. Confira a fila antes de pedir outra cópia.',failed:'Falha no envio do ticket.',expired:'O ticket expirou sem ser recolhido.',cancelled:'Impressão cancelada.'}[state.value?.job?.status || ''] || (state.value?.job ? 'Aguardando confirmação do estado do ticket.' : 'Pronto para enviar ao caixa.')))
function stopPolling() { clearTimeout(pollTimer); pollTimer=undefined }
function invalidateSession() {
  if (sessionEnded) return
  sessionEnded=true
  generation++; stopPolling(); blocked.value=true; state.value=null; stateVerified.value=false
  confirmCopy.value=false; copyKey.value=undefined; busy.value=false; loading.value=false
  error.value=uiText('Reabra o ticket após entrar novamente no sistema.')
}
function sessionMatches() {
  if (sessionEnded) return false
  if (storedToken() === ownerToken) return true
  invalidateSession(); return false
}
function current(request: number, saleId: string) {
  return mounted && request === generation && saleId === props.saleId && sessionMatches()
}
function needsRefresh() { return !stateVerified.value || inQueue.value }
function scheduleRefresh() {
  stopPolling()
  if (!mounted || blocked.value || !available.value || !sessionMatches() || !needsRefresh()) return
  // GET only. Recover transport errors progressively without replaying a print.
  pollTimer=setTimeout(()=>{ pollTimer=undefined; void refresh() }, Math.min(30000, 3000 * 2 ** Math.min(failures,4)))
}
function applyState(result: ReceiptState) {
  state.value=result; stateVerified.value=true; failures=0; error.value=''
  if (inQueue.value) confirmCopy.value=false
}
function requestFailed(cause: unknown) {
  stateVerified.value=false; failures++; error.value=saleError(cause)
  const status=(cause as {response?:{status?:number}})?.response?.status
  if (status === 401 || status === 403 || status === 404) {
    blocked.value=true; state.value=null; confirmCopy.value=false; copyKey.value=undefined
  }
}
async function refresh() {
  if (!mounted || busy.value || blocked.value || !available.value || !sessionMatches()) return
  stopPolling(); busy.value=true; error.value=''
  const request=generation, saleId=props.saleId
  try {
    const result=await pdvReceipts.state(saleId)
    if (current(request,saleId)) applyState(result)
  } catch (cause) {
    if (current(request,saleId)) requestFailed(cause)
  } finally {
    if (current(request,saleId)) { busy.value=false; loading.value=false; scheduleRefresh() }
  }
}
async function send(copy=false) {
  if (!mounted || !sessionMatches() || (copy ? !canCopy.value || !confirmCopy.value : !canSendOriginal.value)) return
  stopPolling(); busy.value=true; error.value=''
  const request=generation, saleId=props.saleId
  if(copy) copyKey.value ||= crypto.randomUUID()
  try {
    const result=await pdvReceipts.print(saleId,copy?copyKey.value:undefined)
    if (current(request,saleId)) { applyState(result); confirmCopy.value=false; copyKey.value=undefined }
  } catch (cause) {
    if (current(request,saleId)) requestFailed(cause)
    // Keep the key across a lost response, cancel/reopen and status refreshes.
  } finally {
    if (current(request,saleId)) { busy.value=false; scheduleRefresh() }
  }
}
function visibilityOrConnectionChanged() {
  available.value=!document.hidden && navigator.onLine
  stopPolling()
  if (!mounted || !sessionMatches()) return
  if (!available.value) stateVerified.value=false
  else if (needsRefresh()) void refresh()
}
function sessionChanged() { if (mounted) sessionMatches() }
watch(()=>props.saleId, ()=>{
  generation++; stopPolling(); state.value=null; stateVerified.value=false; failures=0
  copyKey.value=undefined; confirmCopy.value=false; busy.value=false; error.value=''; loading.value=true
  if (!mounted) return
  if (!sessionMatches()) { loading.value=false; error.value=uiText('Reabra o ticket após entrar novamente no sistema.'); return }
  blocked.value=false; void refresh()
}, {flush:'sync'})
onMounted(()=>{
  mounted=true
  document.addEventListener('visibilitychange',visibilityOrConnectionChanged)
  window.addEventListener('online',visibilityOrConnectionChanged)
  window.addEventListener('offline',visibilityOrConnectionChanged)
  window.addEventListener('focus',visibilityOrConnectionChanged)
  window.addEventListener('erp:native-app-active',visibilityOrConnectionChanged)
  window.addEventListener('storage',sessionChanged)
  window.addEventListener('erp:session-cleared',sessionChanged)
  window.addEventListener('erp:session-expired',invalidateSession)
  window.addEventListener('erp:password-required',invalidateSession)
  void refresh()
})
onUnmounted(()=>{
  mounted=false; generation++; stopPolling(); copyKey.value=undefined
  document.removeEventListener('visibilitychange',visibilityOrConnectionChanged)
  window.removeEventListener('online',visibilityOrConnectionChanged)
  window.removeEventListener('offline',visibilityOrConnectionChanged)
  window.removeEventListener('focus',visibilityOrConnectionChanged)
  window.removeEventListener('erp:native-app-active',visibilityOrConnectionChanged)
  window.removeEventListener('storage',sessionChanged)
  window.removeEventListener('erp:session-cleared',sessionChanged)
  window.removeEventListener('erp:session-expired',invalidateSession)
  window.removeEventListener('erp:password-required',invalidateSession)
})
</script>
<style scoped>
.receipt-delivery{padding:.8rem 1rem;background:#eff6ff;color:#1e3a5f;font-size:.85rem}.receipt-delivery p{margin:.4rem 0}.delivery-actions{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem}.delivery-hint{font-size:.78rem;line-height:1.4}
</style>
