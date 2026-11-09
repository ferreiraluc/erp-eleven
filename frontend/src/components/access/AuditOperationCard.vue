<template>
  <article class="audit-operation">
    <details @toggle="toggle" :key="group.key">
      <summary>
        <span class="operation-heading"><strong>{{ title }}</strong><small>{{ group.actor_count > 1 ? at('actors',{count:group.actor_count}) : group.actor_name }} · {{ date(group.last_at) }}</small></span>
        <span v-if="group.event_count > 1" class="record-count">{{ at('records',{count:group.event_count}) }}</span>
      </summary>
      <div class="operation-content">
        <p v-if="group.sale_code" class="sale-reference">{{ at('ticket') }} #{{ group.sale_code }}</p>
        <router-link v-if="group.sale_id" class="erp-button erp-button--secondary erp-button--sm" :to="{path:'/vendas-pdv',query:{sale_id:group.sale_id}}">{{ at('openSale') }}</router-link>
        <p v-if="error" class="operation-error" role="alert">{{ error }}</p>
        <ol class="event-list" :class="{ 'event-list--single': total === 1 }">
          <li v-for="event in events" :key="event.id">
            <strong v-if="total > 1">{{ eventSummary(event,locale,actionName) }}</strong>
            <p v-if="productLabel(event)">{{ productLabel(event) }}</p>
            <p v-if="stockBalanceText(event,locale)" class="stock-balances">{{ stockBalanceText(event,locale) }}</p>
            <small v-if="total > 1">{{ event.actor_name }} · {{ date(event.occurred_at) }}</small>
            <details class="event-details"><summary>{{ $t('access.details') }}</summary>
              <ul v-if="Object.keys(fields(event)).length"><li v-for="(value,key) in fields(event)" :key="key"><strong>{{ auditFieldName(String(key),locale) }}</strong>: {{ change(value) }}</li></ul>
              <details class="technical-details"><summary>{{ at('technical') }}</summary>
                <p>{{ at('entity') }}: {{ auditEntityName(event.entity,locale) }} <code v-if="event.entity">({{ event.entity }})</code></p>
                <p v-if="event.entity_id">{{ at('identifier') }}: <code>{{ event.entity_id }}</code></p>
                <p>{{ at('channel') }}: {{ event.source }}</p>
                <p>{{ $t('access.reference') }}: <code>{{ event.request_id || event.id }}</code></p>
                <ul><li v-for="(value,key) in fields(event,true)" :key="key"><code>{{ key }}</code>: {{ change(value) }}</li></ul>
              </details>
            </details>
          </li>
        </ol>
        <p v-if="loading" role="status">{{ $t('common.loading') }}</p>
        <button v-if="error || events.length < total" type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="loading" @click="load">{{ error ? $t('common.refresh') : at('more') }}</button>
      </div>
    </details>
    <div v-if="!opened && summaries.length" class="operation-preview">
      <small v-if="group.event_count > 1">{{ at('examples') }}</small>
      <ul><li v-for="(entry,index) in summaries" :key="index">{{ entry }}</li></ul>
    </div>
  </article>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { accessAPI, type AuditEvent, type AuditFilters, type AuditGroup } from '@/services/access'
import { auditText, auditFieldName, auditEntityName, eventSummary, groupTitle, productLabel, stockBalanceText, type AuditTextKey } from '@/services/auditPresentation'
import { formatDateTime } from '@/utils/datetime'
const props=defineProps<{group:AuditGroup;filters:AuditFilters}>()
const {locale,t,te}=useI18n()
const at=(key:AuditTextKey,params:Record<string,string|number>={})=>auditText(key,locale.value,params)
const actionName=(value:string)=>te('access.actionNames.'+value)?t('access.actionNames.'+value):value
const date=(value:string)=>formatDateTime(value)
const title=computed(()=>groupTitle(props.group,locale.value,actionName))
const opened=ref(false)
const events=ref<AuditEvent[]>([]),total=ref(props.group.event_count),loading=ref(false),error=ref('')
let alive=true,started=false
const summaries=computed(()=>{
  if(props.group.event_count===1) { const label=props.group.samples[0]?productLabel(props.group.samples[0]):'';return label?[label]:[] }
  const samples=props.group.kind==='sale'?props.group.samples.filter(e=>e.entity!=='pdv_sales'):props.group.samples
  const movements=samples.filter(e=>e.entity==='stock_movements')
  return [...new Set((movements.length?movements:samples).map(e=>[eventSummary(e,locale.value,actionName),productLabel(e)].filter(Boolean).join(' · ')))].slice(0,3)
})
function toggle(event:Event) { if(event.target!==event.currentTarget)return;opened.value=(event.target as HTMLDetailsElement).open;if(opened.value&&!started) { started=true;void load() } }
async function load(){if(loading.value)return;loading.value=true;error.value='';try{
  const result=await accessAPI.auditGroup({...props.filters,key:props.group.key,offset:events.value.length})
  if(alive){events.value.push(...result.events.filter(e=>!events.value.some(old=>old.id===e.id)));total.value=result.total}
}catch{if(alive)error.value=t('access.connectionError')}finally{if(alive)loading.value=false}}
const technicalKeys=new Set(['id','created_at','updated_at','created_by','deleted_by','version','request_id','event_id','preview_hash','destination_ids'])
function fields(event:AuditEvent,technical=false){return Object.fromEntries(Object.entries(event.changes).filter(([key])=>key!=='_context'&&technicalKeys.has(key)===technical&&!(event.entity==='inventory_grade_links'&&key==='after')))}
function change(value:unknown){if(value&&typeof value==='object'&&'changed' in value)return t('access.fieldChanged');if(value&&typeof value==='object'&&'before' in value&&'after' in value)return `${value.before??'—'} → ${value.after??'—'}`;return typeof value==='object'?JSON.stringify(value):String(value)}
onBeforeUnmount(()=>{alive=false})
</script>
<style scoped>
.audit-operation{border:1px solid #dbe3ed;border-radius:14px;margin:12px 0;background:#fff;overflow:hidden}
.audit-operation>details>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px;cursor:pointer;list-style:none}
.audit-operation>details>summary::after{content:'⌄';color:#64748b}.audit-operation>details[open]>summary::after{transform:rotate(180deg)}
.operation-heading{display:flex;flex-direction:column;gap:5px;min-width:0;flex:1}.operation-heading strong{font-size:16px;overflow-wrap:anywhere}.operation-heading small{color:#64748b;font-size:12px}
.record-count{color:#475569;background:#f1f5f9;border-radius:999px;padding:4px 8px;font-size:12px;white-space:nowrap}
.operation-preview{margin:0;padding:0 16px 14px;color:#475569;font-size:13px}.operation-preview>small{color:#64748b;font-size:11px}.operation-preview ul{margin:0;padding-left:18px}.operation-preview li{margin:5px 0;overflow-wrap:anywhere}
.sale-reference{font-size:13px;color:#64748b;margin:0 0 12px}.operation-content{border-top:1px solid #e2e8f0;padding:16px}.event-list{padding:0;list-style:none;margin:14px 0}.event-list>li{padding:12px 0;border-bottom:1px solid #edf1f5}.event-list--single{margin:0}.event-list--single>li{padding:0;border-bottom:0}.event-list>li>p{font-size:13px;margin:4px 0}.event-list small{color:#64748b;font-size:12px}.event-details{margin-top:8px;font-size:13px}.event-details>summary{cursor:pointer;color:#1d4ed8}.event-details code{overflow-wrap:anywhere}.event-details ul{padding-left:18px}.technical-details{margin-top:12px;color:#64748b}.technical-details>summary{cursor:pointer}.technical-details p{margin:8px 0;overflow-wrap:anywhere}.event-details li{overflow-wrap:anywhere}.operation-error{color:#b91c1c}
@media(max-width:600px){.audit-operation>details>summary{padding:12px;gap:8px;flex-wrap:wrap}.operation-heading{flex-basis:70%}.record-count{font-size:11px}.operation-content{padding:12px}.operation-preview{padding-left:12px;padding-right:12px}}
</style>
