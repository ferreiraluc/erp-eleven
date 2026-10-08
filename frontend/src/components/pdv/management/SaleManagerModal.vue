<template>
  <Teleport to="body"><div class="sale-overlay erp-dialog-backdrop" @keydown.esc.stop.prevent="close" @keydown.tab="trapFocus">
    <section v-erp-dialog ref="dialog" class="sale-dialog erp-dialog erp-dialog--lg" role="dialog" aria-modal="true" :aria-label="tr('Detalhes da venda')" tabindex="-1">
      <header class="erp-dialog__header"><div><h2>{{ operation ? operationText(operation) : tr('Detalhes da venda') }}</h2><small>#{{ saleId.slice(0,8) }}</small></div><button data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :aria-label="tr('Fechar')" :disabled="busy" @click="close">✕</button></header>
      <main class="erp-dialog__body">
        <p v-if="loading" role="status">{{ tr('Carregando venda...') }}</p>
        <div v-if="error" class="notice error" role="alert">{{ tr(error) }}<button v-if="!sale" class="erp-button erp-button--secondary erp-button--sm" @click="load">{{ tr('Tentar novamente') }}</button></div>
        <template v-if="sale && !loading">
          <div class="sale-identity"><div><strong>{{ sale.cliente_nome || tr('Cliente não informado') }}</strong><p>{{ saleDate(sale.created_at) }} · {{ sale.seller || tr('Vendedor não informado') }}</p></div><span class="status">{{ statusText(sale.status) }}</span></div>
          <p v-if="sale.deleted_at" class="notice">{{ tr('Venda excluída da listagem. O histórico está preservado.') }}</p>
          <template v-if="preview">
            <h3>{{ tr('Confira antes de confirmar') }}</h3>
            <div class="review-totals"><div><span>{{ tr('Total anterior') }}</span><strong>{{ gs(preview.before_total_gs) }}</strong></div><div><span>{{ tr('Valor após a operação') }}</span><strong>{{ gs(preview.after_total_gs) }}</strong></div><div v-if="operation !== 'edit'"><span>{{ tr('Estorno nesta operação') }}</span><strong>{{ gs(preview.refund_gs) }}</strong></div></div>
            <p v-if="operation !== 'edit'" class="notice">{{ tr('Abatimento do fiado') }}: <strong>{{ gs(preview.fiado_credit_gs) }}</strong><br />{{ tr('Valor a devolver fora do ERP') }}: <strong>{{ gs(preview.cash_refund_gs) }}</strong></p>
            <p v-if="operation !== 'edit'" class="hint">{{ tr(preview.payment_notice) }}</p>
            <template v-if="preview.correction">
              <p>{{ tr('Cliente') }}: <strong>{{ preview.correction.cliente_nome || tr('Não informado') }}</strong></p>
              <p>{{ tr('Vendedor') }}: <strong>{{ sellers.find(s=>s.id===preview?.correction?.vendedor_id)?.name || '—' }}</strong></p>
              <h3>{{ tr('Itens corrigidos') }}</h3><ul class="preview-list"><li v-for="(line,index) in preview.correction.items" :key="index"><strong>{{ line.item_name }}</strong><small>{{ [line.item_sku,line.item_size,line.item_color].filter(Boolean).join(' · ') }}</small><span>{{ qty(line.quantity) }} × {{ gs(line.unit_price_gs) }} · {{ tr('Desconto') }}: {{ gs(line.discount_gs) }}</span></li></ul>
              <h3>{{ tr('Pagamentos corrigidos') }}</h3><ul class="preview-list"><li v-for="(p,index) in preview.correction.payments" :key="index"><strong>{{ paymentText(p.method) }}</strong><span>{{ p.currency }} {{ amount(p.amount_original) }} → {{ gs(p.amount_gs) }}</span></li></ul>
            </template>
            <ul v-if="preview.returns.length" class="preview-list"><li v-for="r in preview.returns" :key="r.line_id"><strong>{{ r.name }}</strong><span>{{ qty(r.quantity) }} · {{ gs(r.refund_gs) }} · {{ tr(r.restock ? 'Com reposição ao estoque' : 'Sem reposição ao estoque') }}</span></li></ul>
            <h3>{{ tr('Efeito no estoque') }}</h3><p v-if="!preview.stock.length" class="hint">{{ tr('Nenhuma movimentação de estoque nesta operação.') }}</p>
            <ul class="preview-list"><li v-for="(s,index) in preview.stock" :key="index"><strong>{{ s.name }}</strong><span>{{ tr(s.location === 'loja' ? 'Loja' : 'Depósito') }}: {{ s.before }} → {{ s.after }} ({{ s.delta > 0 ? '+' : '' }}{{ s.delta }})</span></li></ul>
            <h3 v-if="preview.fiado.length">{{ tr('Efeito no fiado') }}</h3><ul class="preview-list"><li v-for="f in preview.fiado" :key="f.customer_id"><strong>{{ f.name }}</strong><span>{{ gs(f.before) }} → {{ gs(f.after) }}</span></li></ul>
            <p v-for="warning in preview.warnings" :key="warning" class="notice">{{ tr(warning) }}</p>
            <p><strong>{{ tr('Motivo') }}:</strong> {{ preview.reason }}</p>
            <label class="confirm-line"><input v-model="confirmed" type="checkbox" :disabled="busy" />{{ tr('Conferi os itens, os valores e os efeitos desta operação.') }}</label>
          </template>
          <template v-else-if="operation">
            <SaleEditForm v-if="operation === 'edit' && draft" v-model="draft" :sellers="sellers" />
            <template v-else-if="operation === 'return'">
              <p class="hint">{{ tr('Selecione as quantidades devolvidas. Os descontos da venda são distribuídos proporcionalmente.') }}</p>
              <article v-for="line in availableLines" :key="line.id" class="return-line"><strong>{{ line.item_name }}</strong><small>{{ [line.item_sku,line.item_size,line.item_color].filter(Boolean).join(' · ') }}</small><div class="return-controls"><label>{{ tr('Devolver') }}<input v-model.number="returnLines[line.id].quantity" type="number" :step="line.is_avulso ? '.001' : '1'" min="0" :max="Number(line.quantity)-Number(line.returned_quantity)" /></label><span>{{ tr('Disponível') }}: {{ Number(line.quantity)-Number(line.returned_quantity) }}</span><label class="check"><input v-model="returnLines[line.id].restock" type="checkbox" />{{ tr('Repor no estoque') }}</label></div><p v-if="line.product_deleted" class="notice">{{ tr('Produto excluído: use devolução sem reposição para preservar o catálogo.') }}</p></article>
            </template>
            <template v-else><p class="notice">{{ tr(operation === 'delete' ? 'A exclusão retira a venda da listagem e estorna o saldo restante, preservando todos os registros.' : 'O estorno integral devolve todas as peças restantes e registra a reversão do valor ainda não estornado.') }}</p><label v-if="['completed','partially_refunded'].includes(sale.status)" class="check"><input v-model="restock" type="checkbox" />{{ tr('Repor as peças restantes no estoque de origem') }}</label></template>
            <label class="reason">{{ tr('Motivo da alteração') }}<textarea v-model="reason" rows="3" maxlength="1000" :placeholder="tr('Descreva o que precisa ser corrigido ou devolvido')" /></label>
          </template>
          <template v-else>
            <div class="review-totals"><div><span>{{ tr('Total da venda') }}</span><strong>{{ gs(sale.total_gs) }}</strong></div><div><span>{{ tr('Estornado') }}</span><strong>{{ gs(sale.refunded_gs) }}</strong></div><div><span>{{ tr('Valor líquido') }}</span><strong>{{ gs(sale.status === 'cancelled' ? 0 : Number(sale.total_gs)-Number(sale.refunded_gs)) }}</strong></div></div>
            <p v-if="Number(sale.payment_difference_gs)" class="notice">{{ tr('Diferença entre pagamentos e total (pode incluir troco)') }}: {{ gs(sale.payment_difference_gs) }}</p>
            <nav class="detail-tabs"><button class="erp-control" :aria-pressed="tab==='items'" @click="tab='items'">{{ tr('Itens e pagamentos') }}</button><button v-if="sale.can_manage && auth.isOwner" class="erp-control" :aria-pressed="tab==='history'" @click="tab='history'">{{ tr('Histórico de alterações') }} ({{ sale.events.length }})</button></nav>
            <template v-if="tab==='items'">
              <ul class="preview-list"><li v-for="line in sale.items" :key="line.id"><strong>{{ line.item_name }}</strong><small>{{ [line.item_sku,line.item_size,line.item_color].filter(Boolean).join(' · ') }}</small><span>{{ qty(line.quantity) }} × {{ gs(line.unit_price_gs) }} · {{ tr(line.location==='loja' ? 'Loja' : 'Depósito') }}</span><span>{{ tr('Total do item') }}: {{ gs(line.total_gs) }}<template v-if="Number(line.discount_gs)"> · {{ tr('Desconto') }}: {{ gs(line.discount_gs) }}</template></span><span v-if="Number(line.returned_quantity)">{{ tr('Quantidade devolvida') }}: {{ qty(line.returned_quantity) }}</span></li></ul>
              <h3>{{ tr('Pagamentos') }}</h3><ul class="preview-list"><li v-for="p in sale.payments" :key="p.id"><strong>{{ paymentText(p.method) }}</strong><span>{{ p.currency }} {{ amount(p.amount_original) }} → {{ gs(p.amount_gs) }}</span><small v-if="p.reference">{{ p.reference }}</small></li></ul>
              <p v-if="sale.notas"><strong>{{ tr('Observações') }}:</strong> {{ sale.notas }}</p><p class="hint">{{ tr('Registrado por') }}: {{ sale.actor || '—' }} · {{ tr('Revisão') }} {{ sale.version }}</p><details><summary>{{ tr('Código completo da venda') }}</summary><code>{{ sale.id }}</code></details>
            </template>
            <template v-else>
              <p v-if="!sale.events.length" class="hint">{{ tr('Nenhuma revisão registrada. As alterações são acompanhadas a partir desta versão.') }}</p>
              <article v-for="event in sale.events" :key="event.id" class="event"><strong>{{ operationText(event.operation) }}</strong><p>{{ saleDate(event.at) }} · {{ event.actor || '—' }}</p><p>{{ event.reason }}</p><p>{{ tr('Total da venda') }}: {{ gs(event.before.total_gs) }} → {{ gs(event.after.total_gs) }} · {{ tr('Estorno') }}: {{ gs(event.effects.refund_gs) }}</p><details><summary>{{ tr('Ver itens antes e depois') }}</summary><h4>{{ tr('Antes') }}</h4><p v-for="line in event.before.items" :key="line.id">{{ qty(line.quantity) }} × {{ line.item_name }} · {{ gs(line.total_gs) }}</p><h4>{{ tr('Depois') }}</h4><p v-for="line in event.after.items" :key="line.id">{{ qty(line.quantity) }} × {{ line.item_name }} · {{ gs(line.total_gs) }} · {{ tr('Devolvidos') }}: {{ qty(line.returned_quantity || 0) }}</p></details></article>
            </template>
          </template>
        </template>
      </main>
      <footer class="erp-dialog__footer">
        <template v-if="preview"><button class="erp-button erp-button--secondary" :disabled="busy || uncertain" @click="preview=null; prepared=null; error=''">{{ tr('Voltar à edição') }}</button><button class="erp-button erp-button--danger" :disabled="busy || !confirmed" @click="commit">{{ tr(busy ? 'Processando...' : uncertain ? 'Tentar a mesma confirmação' : 'Confirmar operação') }}</button></template>
        <template v-else-if="operation"><button class="erp-button erp-button--secondary" :disabled="busy" @click="operation=null; error=''">{{ tr('Cancelar') }}</button><button class="erp-button erp-button--primary" :disabled="busy || reason.trim().length<5" @click="review">{{ tr(busy ? 'Conferindo...' : 'Revisar alterações') }}</button></template>
        <template v-else><button class="erp-button erp-button--secondary" @click="close">{{ tr('Fechar') }}</button><template v-if="sale?.can_manage && auth.isOwner && !sale.deleted_at"><button v-if="sale.status==='completed'" class="erp-button erp-button--primary" @click="start('edit')">{{ tr('Editar venda') }}</button><button v-if="availableLines.length && ['completed','partially_refunded'].includes(sale.status)" class="erp-button erp-button--secondary" @click="start('return')">{{ tr('Devolução parcial') }}</button><button v-if="['completed','partially_refunded'].includes(sale.status)" class="erp-button erp-button--danger" @click="start('cancel')">{{ tr('Estorno integral') }}</button><button class="erp-button erp-button--danger" @click="start('delete')">{{ tr('Excluir venda') }}</button></template></template>
      </footer>
    </section>
  </div></Teleport>
</template>
<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { pdvManagementAPI, saleError, type ManagedSale, type SaleOperation, type SaleCommand, type SalePreview, type SaleCommit } from '@/services/pdvManagement'
import type { PdvSaleCreate } from '@/services/api'
import SaleEditForm from './SaleEditForm.vue'
import { tr, gs, qty, amount, saleDate, statusText, operationText, paymentText } from './i18n'
const props=defineProps<{saleId:string;sellers:Array<{id:string;name:string}>}>()
const emit=defineEmits<{(e:'close'):void;(e:'changed'):void}>(),auth=useAuthStore()
const dialog=ref<HTMLElement>(),sale=ref<ManagedSale|null>(null),loading=ref(true),error=ref(''),tab=ref('items'),busy=ref(false)
const operation=ref<SaleOperation|null>(null),draft=ref<PdvSaleCreate>(),reason=ref(''),restock=ref(true)
const returnLines=ref<Record<string,{quantity:number;restock:boolean}>>({}),preview=ref<SalePreview|null>(null),prepared=ref<SaleCommit|null>(null),confirmed=ref(false),uncertain=ref(false)
let mounted=true,prior:HTMLElement|null=null,sequence=0
const availableLines=computed(()=>sale.value?.items.filter(l=>Number(l.quantity)>Number(l.returned_quantity)) || [])
async function load(){const current=++sequence;loading.value=true;sale.value=null;error.value='';try{const result=await pdvManagementAPI.detail(props.saleId);if(current===sequence)sale.value=result}catch(e){if(current===sequence)error.value=saleError(e)}finally{if(current===sequence)loading.value=false}}
function close(){if(!busy.value)emit('close')}
function start(action:SaleOperation){if(!sale.value || !auth.isOwner || busy.value || loading.value)return;operation.value=action;reason.value='';error.value='';preview.value=null;prepared.value=null;confirmed.value=false;uncertain.value=false;restock.value=true
  returnLines.value=Object.fromEntries(availableLines.value.map(l=>[l.id,{quantity:0,restock:!l.product_deleted}]))
  if(action==='edit'){const s=sale.value;draft.value=JSON.parse(JSON.stringify({vendedor_id:s.vendedor_id,cliente_id:s.cliente_id,cliente_nome:s.cliente_nome,items:s.items.map(l=>({...l,quantity:Number(l.quantity),unit_price_gs:Number(l.unit_price_gs),discount_gs:Number(l.discount_gs)})),payments:s.payments.map(p=>({...p,amount_original:Number(p.amount_original),exchange_rate:Number(p.exchange_rate),amount_gs:Number(p.amount_gs)})),desconto_gs:Number(s.desconto_gs),notas:s.notas}))}
}
async function review(){if(!operation.value || busy.value)return;busy.value=true;error.value=''
  const command:SaleCommand={operation:operation.value,reason:reason.value,restock:restock.value}
  if(operation.value==='edit')command.edit=draft.value
  if(operation.value==='return')command.lines=Object.entries(returnLines.value).filter(([,r])=>Number(r.quantity)>0).map(([line_id,r])=>({line_id,quantity:Number(r.quantity),restock:r.restock}))
  const frozen=JSON.parse(JSON.stringify(command)) as SaleCommand
  try{const result=await pdvManagementAPI.preview(props.saleId,frozen);if(mounted){preview.value=result;prepared.value={command:frozen,plan_token:result.plan_token,request_id:crypto.randomUUID(),confirm:true};confirmed.value=false;await nextTick();dialog.value?.focus()}}
  catch(e){if(mounted)error.value=saleError(e)}finally{if(mounted)busy.value=false}
}
async function commit(){if(!prepared.value || !confirmed.value || busy.value)return;busy.value=true;error.value=''
  try{const result=await pdvManagementAPI.commit(props.saleId,prepared.value);if(!result.ok || result.sale_id!==props.saleId)throw new Error('Unconfirmed');if(mounted){operation.value=null;preview.value=null;prepared.value=null;uncertain.value=false;emit('changed');await load()}}
  catch(e){if(mounted){error.value=saleError(e);const status=(e as {response?:{status?:number}})?.response?.status;uncertain.value=!status || status>=500;if(!uncertain.value){preview.value=null;prepared.value=null;confirmed.value=false}}}finally{if(mounted)busy.value=false}
}
function trapFocus(event:KeyboardEvent){const nodes=Array.from(dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select,textarea,summary,[tabindex="0"]')||[]).filter(e=>e.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(event.shiftKey && (document.activeElement===first || document.activeElement===dialog.value)){event.preventDefault();last?.focus()}else if(!event.shiftKey && (document.activeElement===last || document.activeElement===dialog.value)){event.preventDefault();first?.focus()}}
onMounted(async()=>{prior=document.activeElement as HTMLElement;await nextTick();dialog.value?.focus();load()})
onUnmounted(()=>{mounted=false;sequence++;prior?.focus()})
</script>
<style scoped>
.sale-overlay{position:fixed;inset:0;z-index:12500;background:#0f172a99;display:grid;place-items:center;padding:16px;color:#1e293b}.sale-dialog{width:min(900px,100%);max-height:94dvh;background:white;border-radius:16px;display:flex;flex-direction:column;box-shadow:0 20px 60px #0003}.sale-dialog>header,.sale-dialog>footer{padding:16px 20px;display:flex;justify-content:space-between;align-items:center;gap:10px;flex-shrink:0}.sale-dialog>header{border-bottom:1px solid #e2e8f0}h2{font-size:19px;margin:0 0 5px}header small,.hint{color:#64748b;font-size:12px}main{overflow:auto;padding:20px}footer{border-top:1px solid #e2e8f0;flex-wrap:wrap;justify-content:flex-end!important}footer button{font-size:12px;white-space:normal}.sale-identity{display:flex;justify-content:space-between;gap:12px;align-items:center}.sale-identity p{font-size:12px;color:#64748b}.status{font-size:11px;background:#f1f5f9;padding:6px 8px;border-radius:6px;white-space:nowrap}.review-totals{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:18px 0}.review-totals>div{display:grid;gap:8px;background:#f8fafc;border-radius:8px;padding:14px}.review-totals span{font-size:11px;color:#64748b}.review-totals strong{font-size:19px;overflow-wrap:anywhere}.notice{background:#fffbeb;border:1px solid #fde68a;color:#92400e;padding:12px;border-radius:8px;font-size:13px;line-height:1.6}.notice.error{background:#fef2f2;color:#b91c1c;border-color:#fecaca}.detail-tabs{display:flex;gap:8px;border-bottom:1px solid #e2e8f0;padding-bottom:12px}.detail-tabs button{padding:8px 10px;background:white;border:1px solid #cbd5e1;border-radius:8px;font-size:12px}.detail-tabs button[aria-pressed=true]{background:#eff6ff;color:#1d4ed8;border-color:#93c5fd}.preview-list{list-style:none;padding:0;display:grid;gap:10px}.preview-list li,.return-line,.event{padding:14px;border:1px solid #e2e8f0;border-radius:9px;display:grid;gap:7px;font-size:13px;overflow-wrap:anywhere}.preview-list small,.return-line small{font-size:11px;color:#64748b}.return-line,.event{margin:12px 0}.return-controls{display:flex;align-items:end;gap:16px;flex-wrap:wrap}.return-controls label:not(.check){max-width:110px}label{display:grid;gap:6px;font-size:13px}.check,.confirm-line{display:flex;align-items:center;gap:8px}.check input,.confirm-line input{width:auto;flex-shrink:0}.reason{margin-top:20px}.confirm-line{margin:20px 0;align-items:flex-start}input,textarea{padding:9px;border:1px solid #cbd5e1;border-radius:7px;min-width:0;width:100%;box-sizing:border-box;font:inherit}h3{font-size:16px;margin-top:22px}h4{margin:12px 0 6px}.event p{margin:2px 0;font-size:12px}.hint{line-height:1.6}details{font-size:12px;line-height:1.6}summary{cursor:pointer;color:#2563eb}code{overflow-wrap:anywhere}
@media(max-width:600px){.sale-overlay{padding:8px}.sale-dialog{max-height:calc(100dvh - 16px);border-radius:12px}.sale-dialog>header,.sale-dialog>footer{padding:12px}.sale-dialog>main{padding:12px}.review-totals{gap:6px}.review-totals>div{padding:10px}.review-totals strong{font-size:15px}.review-totals span{font-size:10px}.sale-identity{align-items:start}.sale-identity strong{font-size:14px}footer button{flex:1 1 auto}.check,input,textarea{font-size:16px}.check,.confirm-line{font-size:13px}.return-controls{gap:12px}.return-controls span{font-size:12px}}
</style>
