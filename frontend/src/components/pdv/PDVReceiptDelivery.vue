<template>
  <section class="receipt-delivery no-print" aria-live="polite">
    <p v-if="loading">{{ uiText('Consultando impressora do caixa…') }}</p>
    <template v-else-if="state?.printer || state?.job">
      <strong>{{ state.printer?.name || uiText('Ticket da venda') }}</strong>
      <p>{{ uiText(statusText) }}</p>
      <small v-if="state.job?.diagnostic_message">{{ state.job.diagnostic_message }}</small>
      <div class="delivery-actions">
        <button v-if="!state.job" type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="busy" @click="send()">{{ uiText('Imprimir no caixa') }}</button>
        <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="busy" @click="refresh">{{ uiText('Atualizar estado') }}</button>
        <button v-if="state.job && !['pending','claimed'].includes(state.job.status) && !confirmCopy" type="button" class="erp-button erp-button--secondary erp-button--sm" @click="confirmCopy=true">{{ uiText('Outra cópia') }}</button>
      </div>
      <div v-if="confirmCopy">
        <p>{{ uiText('Confira o papel e a fila do Windows. Confirmar envia uma nova cópia, mesmo que a anterior já tenha saído.') }}</p>
        <button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="busy" @click="send(true)">{{ uiText('Confirmar nova cópia') }}</button>
        <button type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="busy" @click="confirmCopy=false">{{ uiText('Cancelar') }}</button>
      </div>
    </template>
    <p v-else-if="!error">{{ uiText('Impressora do caixa não ativada. Use a impressão neste aparelho ou configure os tickets no PDV.') }}</p>
    <p v-if="error" role="alert">{{ error }} <button type="button" class="erp-button erp-button--sm" :disabled="busy" @click="refresh">{{ uiText('Tentar novamente') }}</button></p>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { uiText } from '@/i18n/uiText'
import { pdvReceipts, type ReceiptState } from '@/services/pdvReceipts'
import { saleError } from '@/services/pdvManagement'
const props=defineProps<{saleId:string}>()
const state=ref<ReceiptState | null>(null), loading=ref(true), busy=ref(false), error=ref(''), confirmCopy=ref(false)
let copyKey: string | undefined
const statusText=computed(()=>({pending:'Na fila do caixa. Mantenha o agente conectado.',claimed:'O agente está processando o ticket.',submitted:'Enviado à impressora. Confira a saída do papel.',uncertain:'Envio incerto. Confira a fila antes de pedir outra cópia.',failed:'Falha no envio do ticket.',expired:'O ticket expirou sem ser recolhido.',cancelled:'Impressão cancelada.'}[state.value?.job?.status || ''] || 'Pronto para enviar ao caixa.'))
async function refresh(){ if(busy.value)return; busy.value=true;error.value='';try{state.value=await pdvReceipts.state(props.saleId)}catch(e){error.value=saleError(e)}finally{busy.value=false;loading.value=false} }
async function send(copy=false){ if(busy.value)return;busy.value=true;error.value=''; if(copy) copyKey ||= crypto.randomUUID();try{state.value=await pdvReceipts.print(props.saleId,copy?copyKey:undefined);confirmCopy.value=false;copyKey=undefined}catch(e){error.value=saleError(e)}finally{busy.value=false} }
onMounted(refresh)
</script>
<style scoped>
.receipt-delivery{padding:.8rem 1rem;background:#eff6ff;color:#1e3a5f;font-size:.85rem}.receipt-delivery p{margin:.4rem 0}.delivery-actions{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.5rem}
</style>
