<template>
  <section class="vendor-activity" :aria-label="`${vendor.nome} · ${t('activity')}`">
    <header><div><h2>{{ vendor.nome }} · {{ t('activity') }}</h2><small v-if="data?.seller">{{ data.seller }}</small></div><button class="erp-button erp-button--secondary erp-button--sm" @click="$emit('close')">{{ t('close') }}</button></header>
    <form class="filters" @submit.prevent="load"><label>{{ t('year') }}<select v-model.number="year" @change="load"><option v-for="y in years" :key="y" :value="y">{{ y }}</option></select></label><label>{{ t('month') }}<select v-model.number="month" @change="load"><option :value="0">{{ t('all') }}</option><option v-for="m in 12" :key="m" :value="m">{{ monthLabel(m) }}</option></select></label></form>
    <p v-if="loading" role="status">{{ t('loading') }}</p><p v-if="error" role="alert">{{ t('error') }} <button class="erp-button erp-button--secondary erp-button--sm" @click="load">{{ t('retry') }}</button></p>
    <template v-if="data && !loading && !error">
      <p class="note">{{ t('source') }}<span v-if="data.last_synced_at"> {{ t('synced') }}: {{ date(data.last_synced_at) }}</span></p>
      <p v-if="!data.sales_access" class="note">{{ t('restricted') }}</p><p v-else-if="!data.sales" class="note">{{ t('unmapped') }}</p>
      <div class="metrics"><article v-if="data.sales"><small>{{ t('total') }}</small><strong>{{ amount(data.sales.selected.total_usd) }}</strong><small v-if="data.sales.selected.partial">{{ t('partial') }}</small></article><article v-if="data.sales"><small>{{ t('best') }}</small><strong>{{ amount(data.sales.weeks[0]?.total_usd) }}</strong><small v-if="data.sales.weeks[0]">{{ monthLabel(data.sales.weeks[0].month) }} · {{ data.sales.weeks[0].label }}</small></article><article><small>{{ t('calendar') }}</small><strong>{{ data.days_off.length }}</strong></article></div>
      <template v-if="data.sales">
        <div class="currencies"><span v-for="c in data.sales.currencies" :key="c.currency">{{ c.currency }} <strong>{{ amount(c.value) }}</strong></span></div>
        <h3>{{ t('monthly') }}</h3><div class="table-scroll"><table><thead><tr><th>{{ t('month') }}</th><th>US$</th><th>{{ t('synced') }}</th></tr></thead><tbody><tr v-for="m in months" :key="m.source_id"><td>{{ monthLabel(m.month) }} / {{ m.year }}<small v-if="m.partial">{{ t('partial') }}</small></td><td>{{ amount(m.total_usd) }}</td><td>{{ m.synced_at ? date(m.synced_at) : '—' }}</td></tr><tr v-if="!months.length"><td colspan="3">{{ t('empty') }}</td></tr></tbody></table></div>
        <RouterLink class="erp-button erp-button--secondary erp-button--sm" :to="{path:'/bi-vendas',query:{seller:data.seller || '',year,month:month || undefined}}">{{ t('open') }}</RouterLink>
      </template>
      <h3>{{ t('days') }}</h3><div class="table-scroll"><table><thead><tr><th>{{ t('date') }}</th><th>{{ t('type') }}</th><th>{{ t('period') }}</th><th>{{ t('reason') }}</th></tr></thead><tbody><tr v-for="day in data.days_off" :key="day.id"><td>{{ date(day.date+'T12:00:00') }}<small>{{ t(day.approved?'approved':'pending') }}</small></td><td>{{ t(day.type) }}</td><td>{{ t(day.period) }}</td><td>{{ day.reason || '—' }}</td></tr><tr v-if="!data.days_off.length"><td colspan="4">{{ t('empty') }}</td></tr></tbody></table></div>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import api, { type VendorResponse } from '@/services/api'
import type { Overview } from '@/services/salesBi'
import { vendorActivityMessages } from './messages'
const props=defineProps<{vendor:VendorResponse}>()
defineEmits<{close:[]}>()
const {t,locale}=useI18n({useScope:'local',messages:vendorActivityMessages})
interface Activity {seller:string|null;sales_access:boolean;sales:Overview|null;last_synced_at:string|null;days_off:{id:string;date:string;type:string;period:string;approved:boolean;reason:string|null}[]}
const data=ref<Activity|null>(null),year=ref(new Date().getFullYear()),month=ref(0),loading=ref(false),error=ref(false)
let sequence=0
const years=computed(()=>[...new Set([new Date().getFullYear(),year.value,...(data.value?.sales?.years || [])])].sort((a,b)=>b-a))
const months=computed(()=>data.value?.sales?.months.filter(m=>m.year===year.value && (!month.value || m.month===month.value)).reverse() || [])
const amount=(v:number|null|undefined)=>v==null?'—':v.toLocaleString(locale.value,{minimumFractionDigits:2,maximumFractionDigits:2})
const date=(v:string)=>new Date(v).toLocaleDateString(locale.value)
const monthLabel=(m:number)=>new Date(2026,m-1,1).toLocaleDateString(locale.value,{month:'long'})
async function load(){const seq=++sequence;loading.value=true;error.value=false;try{const r=await api.get<Activity>(`/api/vendedores/${props.vendor.id}/atividade`,{params:{ano:year.value,mes:month.value || undefined}});if(seq===sequence)data.value=r.data}catch{if(seq===sequence){error.value=true;data.value=null}}finally{if(seq===sequence)loading.value=false}}
watch(()=>props.vendor.id,()=>{data.value=null;void load()},{immediate:true})
onUnmounted(()=>{sequence++})
</script>
<style scoped>
.vendor-activity{background:white;border:1px solid #dbe5f3;border-radius:16px;padding:24px;margin:24px 0;color:#1e293b;min-width:0}header,.filters,.currencies{display:flex;align-items:center;gap:16px;flex-wrap:wrap}header{justify-content:space-between}h2{font-size:18px;margin:0}h3{font-size:15px;margin:24px 0 12px}small,.note{color:#64748b;font-size:12px;line-height:1.6}small{display:block}.note span{display:block;margin-top:4px}.filters{margin:20px 0}.filters label{font-size:12px;font-weight:600;display:grid;gap:6px}select{border:1px solid #cbd5e1;background:white;color:#334155;border-radius:8px;padding:9px;min-width:110px;max-width:100%}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0}.metrics article{background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px}.metrics strong{font-size:26px;display:block;margin-top:8px}.currencies{font-size:13px}.currencies span{padding:10px;background:#eff6ff;border-radius:8px}.table-scroll{overflow-x:auto;margin:12px 0}table{width:100%;border-collapse:collapse;text-align:left;font-size:13px}th,td{padding:12px;border-bottom:1px solid #e2e8f0}th{background:#f8fafc;color:#64748b;font-weight:600}@media(max-width:600px){.vendor-activity{padding:16px}.metrics{grid-template-columns:1fr}.filters{gap:10px}}
</style>
