<template>
  <div class="usage-history">
    <p class="intro"><strong>{{ address.label }}</strong><br/>Endereços A4 e etiquetas aparecem juntos, com a data e o responsável por cada utilização.</p>
    <div class="usage-metrics">
      <div><strong>{{ result.summary.address_prints }}</strong><span>Endereços A4 impressos</span></div>
      <div><strong>{{ result.summary.labels }}</strong><span>Etiquetas emitidas</span></div>
      <div><strong>{{ result.summary.completed_prints }}</strong><span>Total enviado à impressora</span></div>
    </div>
    <p class="usage-note">O total inclui {{ result.summary.address_prints }} endereço(s) A4 e {{ result.summary.label_prints }} etiqueta(s). Conta somente envios confirmados pelo agente; cancelamentos, falhas e trabalhos na fila não entram no total. A saída física do papel depende da impressora.<br/><strong v-if="result.summary.last_printed_at">Última impressão: {{ date(result.summary.last_printed_at) }}</strong></p>
    <div class="usage-toolbar">
      <label>Mostrar <select v-model="kind" @change="offset=0;load()"><option value="all">Todas as utilizações</option><option value="frete">Cotações e etiquetas</option><option value="impressao">Impressões</option></select></label>
      <button :disabled="loading" @click="load">Atualizar</button>
    </div>
    <p v-if="error" role="alert" class="usage-error">{{ error }}</p>
    <p v-if="loading" role="status" class="usage-empty">Carregando histórico…</p>
    <div v-else class="usage-table">
      <table><thead><tr><th>Data / responsável</th><th>Utilização</th><th>Situação</th><th>Detalhes</th></tr></thead><tbody>
        <tr v-for="entry in result.items" :key="entry.kind+entry.id">
          <td>{{ date(entry.finished_at || entry.created_at) }}<small>{{ entry.user }}</small><small v-if="entry.finished_at">Solicitada em {{ date(entry.created_at) }}</small></td>
          <td><strong>{{ entry.kind==='frete'?'Frete SuperFrete':entry.source==='superfrete'?'Impressão de etiqueta':'Endereço A4 · modelo simples' }}</strong><small>{{ entry.environment==='sandbox'?'Ambiente de testes':entry.source==='bot'?'Solicitada pelo bot':entry.source==='erp'?'Solicitada pelo ERP':'' }}</small></td>
          <td><span class="usage-badge">{{ entry.kind==='impressao' && entry.status==='pending'?'Na fila de impressão':states[entry.status] || entry.status }}</span><small v-if="entry.price">{{ money(entry.price) }}</small><code v-if="entry.tracking">{{ entry.tracking }}</code></td>
          <td><details><summary>{{ entry.recipient || 'Ver endereço utilizado' }}</summary><p>{{ entry.address_text || 'Sem detalhes de rua informados.' }}</p></details><button @click="entry.kind==='frete'?$emit('freight',entry.id):$emit('print',entry.id)">{{ entry.kind==='frete'?'Abrir frete':'Ver PDF' }}</button></td>
        </tr>
        <tr v-if="!result.items.length"><td colspan="4" class="usage-empty">{{ kind==='all'?'Nenhuma utilização registrada. O histórico aparecerá ao cotar um frete ou enviar uma impressão.':'Nenhuma utilização deste tipo.' }}</td></tr>
      </tbody></table>
    </div>
    <footer><span>{{ result.total }} {{ result.total===1?'registro':'registros' }}<small>{{ result.summary.prints }} solicitações de impressão · {{ result.summary.quotes }} cotações</small><small v-if="result.summary.last_used_at">Última utilização: {{ date(result.summary.last_used_at) }}</small></span><div><button :disabled="offset===0 || loading" @click="offset-=30;load()">Anterior</button><button :disabled="offset+30>=result.total || loading" @click="offset+=30;load()">Próxima</button></div></footer>
  </div>
</template>

<script setup lang="ts">
import { onMounted,ref,onUnmounted } from 'vue'
import api from '@/services/api'
import type { SavedAddress, AddressUsage } from './types'
const props=defineProps<{address:SavedAddress}>()
defineEmits<{freight:[id:string];print:[id:string]}>()
const result=ref<AddressUsage>({total:0,summary:{total:0,quotes:0,labels:0,prints:0,completed_prints:0,address_prints:0,label_prints:0,last_used_at:null,last_printed_at:null},items:[]})
const kind=ref('all'),offset=ref(0),loading=ref(false),error=ref('')
let sequence=0
async function load(){const current=++sequence;loading.value=true;error.value='';try{const {data}=await api.get('/api/address-manager/addresses/'+props.address.id+'/usage',{params:{offset:offset.value,kind:kind.value}});if(current===sequence)result.value=data}catch{if(current===sequence)error.value='Não foi possível carregar o histórico. Tente atualizar.'}finally{if(current===sequence)loading.value=false}}
const date=(v:string)=>new Date(v).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})
const money=(v:string)=>Number(v).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})
const states:Record<string,string>={quoted:'Cotação realizada',creating:'Criando frete',pending:'Aguardando pagamento',paying:'Pagamento em andamento',released:'Etiqueta emitida',posted:'Postado',delivered:'Entregue',cancelled:'Cancelado',uncertain:'Conferência necessária',claimed:'Retirada pelo agente',submitted:'Enviada à impressora',failed:'Falha',expired:'Expirada'}
onMounted(load)
onUnmounted(()=>{sequence++})
</script>

<style scoped>
.usage-note{color:#64748b;font-size:12px;line-height:1.6;margin:12px 0}.usage-note strong{display:block;margin-top:6px;color:#475569}
.intro{color:#64748b;font-size:13px;line-height:1.6;margin:18px 0}.intro strong{color:#172033;font-size:16px}.usage-metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}.usage-metrics>div{border:1px solid #e2e8f0;background:#f8fafc;border-radius:12px;padding:16px}.usage-metrics strong{display:block;font-size:25px;color:#172033}.usage-metrics span,small{display:block;color:#64748b;font-size:12px;margin-top:5px}.usage-toolbar,footer,footer>div{display:flex;align-items:center;justify-content:space-between;gap:10px}.usage-toolbar{margin:18px 0}.usage-toolbar label{font-size:12px;color:#475569;display:flex;gap:10px;align-items:center}select,button{border:1px solid #cbd5e1;border-radius:8px;padding:9px 11px;background:white;color:#334155;font:inherit;font-size:12px}button{font-weight:600;cursor:pointer}button:hover{background:#f1f5f9}button:disabled{opacity:.5;cursor:not-allowed}.usage-table{overflow-x:auto}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}th{background:#f8fafc;color:#64748b;font-size:11px;text-transform:uppercase;padding:12px}td{padding:15px 12px;border-bottom:1px solid #edf1f5;vertical-align:top}details{margin-bottom:10px}summary{cursor:pointer;color:#2563eb}details p{max-width:250px;line-height:1.5;font-size:12px;color:#64748b;overflow-wrap:anywhere}.usage-badge{display:inline-block;padding:5px 8px;border-radius:6px;background:#eff6ff;color:#1d4ed8;font-size:11px}.usage-empty{text-align:center;color:#64748b;padding:30px 12px}.usage-error{background:#fff1f2;color:#9f1239;padding:12px;border-radius:8px}code{display:block;font-size:12px;margin-top:8px}footer{margin-top:20px;color:#64748b;font-size:12px}@media(max-width:600px){.usage-metrics{gap:6px}.usage-metrics>div{padding:11px}.usage-metrics span{font-size:11px}.usage-toolbar label{display:block}select{display:block;margin-top:5px}}
</style>
