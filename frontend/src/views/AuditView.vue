<template>
  <main class="access-page">
    <header class="access-head"><div><h1>{{ $t('access.audit') }}</h1><p>{{ $t('access.auditSubtitle') }}</p></div><button class="erp-button erp-button--secondary" :disabled="loading" @click="load">{{ $t('common.refresh') }}</button></header>
    <p class="notice">{{ $t('access.timeNotice') }}</p><p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <section class="access-card filters">
      <label>{{ $t('access.period') }}<select v-model.number="days" @change="filter"><option :value="1">{{ $t('access.lastDay') }}</option><option :value="7">{{ $t('access.lastWeek') }}</option><option :value="30">{{ $t('access.lastMonth') }}</option><option :value="90">{{ $t('access.lastQuarter') }}</option></select></label>
      <label>{{ $t('access.user') }}<select v-model="userId" @change="filter"><option value="">{{ $t('access.allUsers') }}</option><option v-for="u in users" :key="u.id" :value="u.id">{{ u.nome }}</option></select></label>
      <label>{{ $t('access.module') }}<select v-model="module" @change="filter"><option value="">{{ $t('access.allModules') }}</option><option v-for="m in modules" :key="m" :value="m">{{ moduleName(m) }}</option></select></label>
      <label>{{ $t('access.action') }}<select v-model="action" @change="filter"><option value="">{{ $t('access.allActions') }}</option><option v-for="a in actions" :key="a" :value="a">{{ actionName(a) }}</option></select></label>
    </section>
    <div v-if="loading&&!data" class="empty">{{ $t('common.loading') }}</div>
    <template v-if="data">
      <section class="metrics"><article class="access-card metric"><small>{{ $t('access.events') }}</small><strong>{{ data.total.toLocaleString(locale) }}</strong></article><article class="access-card metric"><small>{{ $t('access.activeUsers') }}</small><strong>{{ data.users.length }}</strong></article><article class="access-card metric"><small>{{ $t('access.activeTime') }}</small><strong>{{ duration(data.active_seconds) }}</strong></article></section>
      <div class="two-columns"><section class="access-card"><h2>{{ $t('access.timeByModule') }}</h2><div v-if="!data.modules.length" class="empty">{{ $t('access.noActivity') }}</div><div class="bars"><div v-for="m in sortedModules" :key="m.module"><div class="bar-label"><span>{{ moduleName(m.module) }}</span><strong>{{ duration(m.active_seconds) }}</strong></div><div class="track"><span :style="{width:100*m.active_seconds/Math.max(1,sortedModules[0]?.active_seconds||1)+'%'}" /></div></div></div></section>
      <section class="access-card"><h2>{{ $t('access.activityByUser') }}</h2><div v-if="!data.users.length" class="empty">{{ $t('access.noActivity') }}</div><div class="table-wrap"><table><thead><tr><th>{{ $t('access.user') }}</th><th>{{ $t('access.activeTime') }}</th><th>{{ $t('access.mutations') }}</th><th>{{ $t('access.lastSeen') }}</th></tr></thead><tbody><tr v-for="u in data.users" :key="u.id"><td><strong>{{ u.name }}</strong></td><td>{{ duration(u.active_seconds) }}</td><td>{{ (u.actions.create||0)+(u.actions.update||0)+(u.actions.delete||0)+(u.actions.bulk_update||0)+(u.actions.bulk_delete||0) }}</td><td>{{ date(u.last_seen_at) }}</td></tr></tbody></table></div></section></div>
      <section class="access-card"><div class="access-head"><div><h2>{{ $t('access.history') }}</h2><small>{{ $t('access.historyHelp') }}</small></div><button class="erp-button erp-button--secondary" :disabled="!data.events.length" @click="exportPage">{{ $t('access.exportPage') }}</button></div>
        <div class="table-wrap"><table><thead><tr><th>{{ $t('access.when') }}</th><th>{{ $t('access.user') }}</th><th>{{ $t('access.action') }}</th><th>{{ $t('access.module') }}</th><th>{{ $t('access.result') }}</th><th>{{ $t('access.details') }}</th></tr></thead><tbody><tr v-for="e in data.events" :key="e.id"><td>{{ date(e.occurred_at) }}</td><td><strong>{{ e.actor_name }}</strong><small class="block">{{ e.source }}</small></td><td><span class="badge">{{ actionName(e.action) }}</span></td><td>{{ moduleName(e.module) }}</td><td>{{ e.status_code || $t('access.committed') }}</td><td><details><summary>{{ $t('access.details') }}</summary><p><code>{{ e.method }} {{ e.route || e.entity }}<br/>{{ e.entity_id }}</code></p><ul><li v-for="(value,key) in e.changes" :key="key"><strong>{{ key }}</strong>: {{ change(value) }}</li></ul><small>{{ $t('access.reference') }}: {{ e.request_id || e.id }}</small></details></td></tr></tbody></table><div v-if="!data.events.length" class="empty">{{ $t('access.noActivity') }}</div></div>
        <div class="actions"><span class="muted">{{ data.total ? offset+1 : 0 }}–{{ Math.min(offset+data.events.length,data.total) }} / {{ data.total }}</span><button class="erp-button erp-button--secondary" :disabled="loading||offset===0" @click="offset=Math.max(0,offset-50);load()">{{ $t('access.previous') }}</button><button class="erp-button erp-button--secondary" :disabled="loading||offset+50>=data.total" @click="offset+=50;load()">{{ $t('access.next') }}</button></div>
      </section>
    </template>
  </main>
</template>
<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { accessAPI, type AuditResult } from '@/services/access'
import type { User } from '@/services/api'
const {t,te,locale}=useI18n()
const days=ref(7),userId=ref(''),module=ref(''),action=ref(''),offset=ref(0),loading=ref(false),error=ref(''),data=ref<AuditResult|null>(null),users=ref<User[]>([])
let requestId=0
const actions=['login','logout','login_failed','create','update','delete','bulk_update','bulk_delete','password_changed','password_reset','access_created','access_changed','read','request']
const modules=['dashboard','bi-vendas','enderecos','pedidos','inventory','rastreamento','vendas','pdv','fiado','vendors','exchange-rates','conta','usuarios','auditoria','assistente','clientes']
const sortedModules=computed(()=>[...(data.value?.modules||[])].sort((a,b)=>b.active_seconds-a.active_seconds))
const moduleName=(m:string)=>te('access.modules.'+m)?t('access.modules.'+m):m
const actionName=(a:string)=>te('access.actionNames.'+a)?t('access.actionNames.'+a):a
const date=(s:string|null)=>s?new Date(s).toLocaleString(locale.value):'—'
const duration=(seconds:number)=>seconds<60?`${Math.floor(seconds)}s`:seconds<3600?`${Math.floor(seconds/60)}min ${Math.floor(seconds%60)}s`:`${Math.floor(seconds/3600)}h ${Math.floor(seconds%3600/60)}min`
function change(value:unknown){if(value&&typeof value==='object'&&'changed' in value)return t('access.fieldChanged');if(value&&typeof value==='object'&&'before' in value&&'after' in value)return `${value.before??'—'} → ${value.after??'—'}`;return String(value)}
async function load(){const id=++requestId;loading.value=true;error.value='';try{const result=await accessAPI.audit({days:days.value,user_id:userId.value||undefined,module:module.value||undefined,action:action.value||undefined,offset:offset.value});if(id===requestId)data.value=result}catch{if(id===requestId)error.value=t('access.connectionError')}finally{if(id===requestId)loading.value=false}}
function filter(){offset.value=0;load()}
function exportPage(){if(!data.value)return;const cell=(v:unknown)=>'"'+String(v??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';const rows=[['when','user','channel','action','module','result','object','identifier'].map(k=>t('access.'+k)),...data.value.events.map(e=>[e.occurred_at,e.actor_name,e.source,actionName(e.action),moduleName(e.module),e.status_code,e.entity,e.entity_id])];const url=URL.createObjectURL(new Blob(['\uFEFF'+rows.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='eleven-auditoria.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
onMounted(async()=>{await load();try{users.value=await accessAPI.users()}catch{error.value=t('access.connectionError')}})
</script>
<style scoped src="@/components/access/access.css"></style>
<style scoped>.block{display:block;margin-top:4px}li{margin:6px 0}details{min-width:140px;max-width:340px}</style>
