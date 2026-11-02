<template>
  <main class="access-page">
    <ModuleHeader :title="$t('access.audit')">
      <button class="erp-button erp-button--secondary" :disabled="loading" @click="load">
        {{ $t("common.refresh") }}
      </button>
    </ModuleHeader>
    <p class="notice">{{ $t('access.auditNotice') }}</p><p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <details class="access-card audit-notifications" @toggle="notificationsOpen=($event.target as HTMLDetailsElement).open"><summary>{{ notificationText('admin') }}</summary><NotificationAdmin v-if="notificationsOpen" embedded /></details>
    <QualityPanel :run-id="typeof route.query.quality_run === 'string' ? route.query.quality_run : null" />
    <section class="access-card filters">
      <label>{{ $t('access.period') }}<ErpSelect :label="($t('access.period'))" v-model.number="days" @change="filter"><option :value="1">{{ $t('access.lastDay') }}</option><option :value="7">{{ $t('access.lastWeek') }}</option><option :value="30">{{ $t('access.lastMonth') }}</option><option :value="90">{{ $t('access.lastQuarter') }}</option></ErpSelect></label>
      <label>{{ $t('access.user') }}<ErpSelect :label="($t('access.user'))" v-model="userId" @change="filter"><option value="">{{ $t('access.allUsers') }}</option><option v-for="u in users" :key="u.id" :value="u.id">{{ u.nome }}</option></ErpSelect></label>
      <label>{{ $t('access.module') }}<ErpSelect :label="($t('access.module'))" v-model="module" @change="filter"><option value="">{{ $t('access.allModules') }}</option><option v-for="m in modules" :key="m" :value="m">{{ moduleName(m) }}</option></ErpSelect></label>
      <label>{{ $t('access.action') }}<ErpSelect :label="($t('access.action'))" v-model="action" @change="filter"><option value="">{{ $t('access.allActions') }}</option><option v-for="a in actions" :key="a" :value="a">{{ actionName(a) }}</option></ErpSelect></label>
    </section>
    <div v-if="loading&&!data" class="empty">{{ $t('common.loading') }}</div>
    <template v-if="data">
      <section class="metrics audit-metrics">
        <article class="access-card metric"><small>{{ at('operations') }}</small><strong>{{ data.total.toLocaleString(locale) }}</strong></article>
        <article class="access-card metric"><small>{{ $t('access.activeUsers') }}</small><strong>{{ data.users.length }}</strong></article>
      </section>
      <section class="access-card"><h2>{{ $t('access.activityByUser') }}</h2>
        <div v-if="!data.users.length" class="empty">{{ $t('access.noActivity') }}</div>
        <div class="table-wrap"><table><thead><tr><th>{{ $t('access.user') }}</th><th>{{ actionName('login') }}</th><th>{{ at('operations') }}</th><th>{{ $t('access.lastSeen') }}</th></tr></thead>
          <tbody><tr v-for="u in data.users" :key="u.id"><td><strong>{{ u.name }}</strong></td><td>{{ u.actions.login || 0 }}</td><td>{{ u.operations ?? mutationCount(u.actions) }}</td><td>{{ date(u.last_seen_at) }}</td></tr></tbody>
        </table></div>
      </section>
      <section class="access-card"><div class="access-head"><div><h2>{{ $t('access.history') }}</h2><small>{{ at('groupedHelp') }}</small></div><button class="erp-button erp-button--secondary" :disabled="!groups.length" @click="exportPage">{{ $t('access.exportPage') }}</button></div>
        <AuditOperationCard v-for="group in groups" :key="`${revision}:${group.key}`" :group="group" :filters="appliedFilters" />
        <div v-if="!groups.length" class="empty">{{ $t('access.noActivity') }}</div>
        <div class="actions"><span class="muted">{{ data.total ? data.offset+1 : 0 }}–{{ Math.min(data.offset+groups.length,data.total) }} / {{ data.total }}</span><button class="erp-button erp-button--secondary" :disabled="loading||offset===0" @click="offset=Math.max(0,offset-50);load()">{{ $t('access.previous') }}</button><button class="erp-button erp-button--secondary" :disabled="loading||offset+50>=data.total" @click="offset+=50;load()">{{ $t('access.next') }}</button></div>
      </section>
    </template>
  </main>
</template>
<script setup lang="ts">
import ErpSelect from '@/components/ui/ErpSelect.vue'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import { accessAPI, type AuditResult, type AuditGroup, type AuditFilters } from '@/services/access'
import AuditOperationCard from '@/components/access/AuditOperationCard.vue'
import { auditText, groupTitle, type AuditTextKey } from '@/services/auditPresentation'
import { formatDateTime } from '@/utils/datetime'
import type { User } from '@/services/api'
import NotificationAdmin from '@/components/notifications/NotificationAdmin.vue'
import QualityPanel from '@/components/notifications/QualityPanel.vue'
import { notificationText } from '@/services/notificationText'
const notificationsOpen=ref(false)
const route=useRoute()
const {t,te,locale}=useI18n()
const days=ref(7),userId=ref(''),module=ref(''),action=ref(''),offset=ref(0),loading=ref(false),error=ref(''),data=ref<AuditResult|null>(null),users=ref<User[]>([])
let requestId=0
const revision=ref(0),appliedFilters=ref<AuditFilters>({days:7})
const at=(key:AuditTextKey)=>auditText(key,locale.value)
const groups=computed<AuditGroup[]>(()=>data.value?.groups??data.value?.events.map(event=>({key:'event:'+event.id,kind:'operation',sale_id:null,sale_code:null,event_count:1,first_at:event.occurred_at,last_at:event.occurred_at,module:event.module,actor_name:event.actor_name,actor_count:1,samples:[event]}))??[])
const actions=['login','logout','login_failed','create','update','delete','bulk_update','bulk_delete','password_changed','password_reset','access_created','access_changed','item_permanently_deleted','item_catalog_deleted','pdv_edit','pdv_return','pdv_cancel','pdv_delete']
const modules=['dashboard','bi-vendas','enderecos','pedidos','inventory','rastreamento','vendas','pdv','fiado','vendors','exchange-rates','conta','usuarios','auditoria','assistente','clientes']
const moduleName=(m:string)=>te('access.modules.'+m)?t('access.modules.'+m):m
const actionName=(a:string)=>te('access.actionNames.'+a)?t('access.actionNames.'+a):a
const date=(s:string|null)=>s?formatDateTime(s):'—'
const mutationCount=(actions:Record<string,number>)=>Object.entries(actions).reduce((sum,[action,count])=>sum+(['login','login_failed','logout'].includes(action)?0:count),0)
async function load(){const id=++requestId;loading.value=true;error.value='';try{const filters={days:days.value,user_id:userId.value||undefined,module:module.value||undefined,action:action.value||undefined};const result=await accessAPI.audit({...filters,offset:offset.value,grouped:true});if(id===requestId){data.value=result;appliedFilters.value=filters;revision.value++}}catch{if(id===requestId){error.value=t('access.connectionError');offset.value=data.value?.offset??0}}finally{if(id===requestId)loading.value=false}}
function filter(){offset.value=0;load()}
function exportPage(){if(!data.value)return;const cell=(v:unknown)=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';const rows=[['when','user','action','module','identifier'].map(k=>t('access.'+k)),...groups.value.map(group=>[date(group.last_at),group.actor_name,groupTitle(group,locale.value,actionName),moduleName(group.module),group.sale_id||group.key])];const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='eleven-auditoria.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
onMounted(async()=>{await load();try{users.value=await accessAPI.users()}catch{error.value=t('access.connectionError')}})
</script>
<style scoped src="@/components/access/access.css"></style>
<style scoped>.audit-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.block{display:block;margin-top:4px}li{margin:6px 0}details{min-width:140px;max-width:340px}.audit-notifications{max-width:none;min-width:0}.audit-notifications>summary{font-size:16px;font-weight:700;color:#1d4ed8;cursor:pointer}.audit-notifications[open]>summary{margin-bottom:20px}</style>
