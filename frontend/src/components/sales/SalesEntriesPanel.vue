<template>
  <section class="entries-panel">
    <header><div><h2>{{ t('title') }}</h2><p>{{ t('description') }}</p></div><button class="erp-button erp-button--secondary erp-button--sm" :disabled="loading" @click="load()"><RefreshCw :size="15" />{{ t('reload') }}</button></header>
    <form class="entry-filters" @submit.prevent="offset=0; load()">
      <label>{{ t('currency') }}<select v-model="currency" @change="offset=0; load()"><option value="">{{ t('allCurrencies') }}</option><option v-for="code in result?.currencies || []" :key="code">{{ code }}</option></select></label>
      <label>{{ t('date') }}<input v-model="day" type="date" @change="offset=0; load()" /></label>
      <label class="search">{{ t('search') }}<input v-model="search" type="search" :placeholder="t('searchHint')" maxlength="120" /></label>
      <button class="erp-button erp-button--secondary erp-button--sm" type="submit">{{ t('filter') }}</button><button class="erp-button erp-button--secondary erp-button--sm" v-if="currency || day || search" type="button" @click="clearFilters">{{ t('clear') }}</button>
    </form>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="result?.coverage.needs_sync" class="notice">{{ t('needsSync') }}</p>
    <p v-if="result?.coverage.skipped_rows" class="notice">{{ t('skipped', { count: result.coverage.skipped_rows }) }}</p>
    <div v-if="result" :aria-busy="loading" :class="{ loading }">
      <div class="entry-metrics">
        <article><span>{{ t('entries') }}</span><strong>{{ result.summary.count.toLocaleString(locale) }}</strong><small>{{ t('entriesHelp') }}</small></article>
        <article><span>{{ t('dated') }}</span><strong>{{ result.summary.dated_count.toLocaleString(locale) }}</strong><small>{{ t('missingDate', { count: result.summary.undated_count }) }}</small></article>
        <article><span>{{ t('timed') }}</span><strong>{{ result.summary.timed_count.toLocaleString(locale) }}</strong><small>{{ t('timeHelp') }}</small></article>
        <article><span>{{ t('closing') }}</span><strong>{{ money(result.summary.official_total_usd, 'USD') }}</strong><small>{{ t('closingHelp') }}</small></article>
      </div>
      <div v-if="result.summary.currencies.length" class="currency-summary">
        <article v-for="item in result.summary.currencies" :key="item.currency"><span>{{ item.currency }}</span><strong>{{ money(item.gross, item.currency) }}</strong><small>{{ t('gross') }} · {{ item.count }} {{ t('entries').toLowerCase() }}</small><p>{{ t('net') }}: {{ money(item.net, item.currency) }}<small v-if="item.net_available < item.count">{{ t('netPartial', { count: item.net_available, total: item.count }) }}</small></p></article>
      </div>
      <div class="entry-charts">
        <article class="chart-card"><h3>{{ t('intraday') }}</h3><p>{{ t('intradayHelp') }}</p>
          <div v-if="result.hourly.length" class="hourly" role="img" :aria-label="t('intraday')"><div v-for="hour in hours" :key="hour.hour" class="hour"><span class="bar-value">{{ hour.count || '' }}</span><div class="bar-track"><span :style="{height: `${hour.count / maxHour * 100}%`}" :title="`${hour.hour}:00 — ${hour.count} ${t('entries').toLowerCase()}`" /></div><small>{{ hour.hour.toString().padStart(2,'0') }}</small></div></div>
          <p v-else class="empty">{{ t('noTime') }}</p>
        </article>
        <article class="chart-card"><h3>{{ result.daily.length ? t('byDay') : t('byWeekday') }}</h3><p>{{ result.daily.length ? t('byDayHelp') : t('weekdayHelp') }}</p><div v-if="result.daily.length" class="daily-list"><button class="erp-control" v-for="item in result.daily.slice(-10).reverse()" :key="item.date" @click="day=item.date; offset=0; load()"><span>{{ formatDate(item.date) }}</span><strong>{{ item.count }}</strong><small>{{ item.currencies.map(c => money(c.gross, c.currency)).join(' · ') }}</small></button></div><div v-else-if="result.weekdays.length" class="daily-list"><div v-for="item in result.weekdays" :key="item.day" class="weekday-row"><span>{{ t(`days.${item.day}`) }}</span><strong>{{ item.count }}</strong><small>{{ item.currencies.map(c => money(c.gross,c.currency)).join(' · ') }}</small></div></div><p v-else class="empty">{{ t('noDate') }}</p></article>
      </div>
      <div class="table-heading"><h3>{{ t('details') }}</h3><button class="erp-button erp-button--secondary erp-button--sm" :disabled="!result.items.length || loading" @click="exportPage"><Download :size="14" />{{ t('export') }}</button></div>
      <div class="table-wrap"><table><thead><tr><th>{{ t('date') }}</th><th>{{ t('seller') }}</th><th>{{ t('customer') }}</th><th>{{ t('payment') }}</th><th class="number">{{ t('gross') }}</th><th class="number">{{ t('net') }}</th><th>{{ t('source') }}</th></tr></thead><tbody><tr v-for="entry in result.items" :key="entry.id"><td>{{ entry.date ? formatDate(entry.date) : entry.day_group ? t(`days.${entry.day_group}`) : '—' }}<small>{{ entry.time || t('noRecordedTime') }}</small></td><td>{{ entry.seller }}</td><td>{{ entry.customer || '—' }}</td><td>{{ entry.payment_method || '—' }}</td><td class="number">{{ money(entry.gross,entry.currency) }}</td><td class="number">{{ money(entry.net,entry.currency) }}</td><td>{{ entry.source_cell }}<small>{{ entry.filename }} · {{ entry.month }}/{{ entry.year }}</small><small>{{ entry.week_label || t('unassignedWeek') }}<span v-if="entry.stale"> · {{ t('stale') }}</span></small></td></tr></tbody></table></div>
      <p v-if="!result.items.length" class="empty">{{ t('empty') }}</p>
      <footer><span>{{ result.total ? offset + 1 : 0 }}–{{ Math.min(offset + result.limit,result.total) }} / {{ result.total.toLocaleString(locale) }}</span><button class="erp-button erp-button--secondary erp-button--sm" :disabled="offset===0 || loading" @click="offset=Math.max(0,offset-result.limit); load()">{{ t('previous') }}</button><button class="erp-button erp-button--secondary erp-button--sm" :disabled="offset+result.limit>=result.total || loading" @click="offset+=result.limit; load()">{{ t('next') }}</button></footer>
      <details v-if="differences.length"><summary>{{ t('reconciliation') }}</summary><p>{{ t('reconciliationHelp') }}</p><div class="table-wrap"><table><thead><tr><th>{{ t('period') }}</th><th>{{ t('currency') }}</th><th class="number">{{ t('savedSummary') }}</th><th class="number">{{ t('observedNet') }}</th><th class="number">{{ t('difference') }}</th></tr></thead><tbody><tr v-for="item in differences" :key="`${item.year}-${item.month}-${item.currency}`"><td>{{ item.month }}/{{ item.year }}</td><td>{{ item.currency }}</td><td class="number">{{ money(item.published,item.currency) }}</td><td class="number">{{ money(item.observed_net,item.currency) }}</td><td class="number">{{ money(item.difference,item.currency) }}</td></tr></tbody></table></div></details>
    </div>
    <p v-else-if="loading" class="empty" role="status">{{ t('loading') }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Download, RefreshCw } from 'lucide-vue-next'
import { salesEntries, type EntriesResult } from '@/services/salesEntries'
import messages from './salesEntries.messages.json'
const props = defineProps<{ year?: number; month?: number; seller?: string; refreshedAt?: string | null }>()
const { t, locale } = useI18n({ useScope: 'local', messages })
const result = ref<EntriesResult | null>(null), error = ref(''), loading = ref(false)
const currency = ref(''), day = ref(''), search = ref(''), offset = ref(0)
let sequence = 0
const hours = computed(() => Array.from({ length: 24 }, (_, hour) => ({ hour, count: result.value?.hourly.find(r => r.hour === hour)?.count || 0 })))
const maxHour = computed(() => Math.max(1,...hours.value.map(h => h.count)))
const differences = computed(() => result.value?.reconciliation.filter(r => r.difference === null || Math.abs(r.difference) > .05) || [])
function money(value: number | null, code: string) { return value === null ? '—' : value.toLocaleString(locale.value,{style:'currency',currency:code,maximumFractionDigits:code==='PYG'?0:2}) }
function formatDate(value: string) { return new Date(`${value}T12:00:00`).toLocaleDateString(locale.value) }
async function load() {
  const request = ++sequence
  loading.value = true; error.value = ''
  try {
    const next = await salesEntries.list({year:props.year || undefined,month:props.month || undefined,seller:props.seller || undefined,currency:currency.value || undefined,day:day.value || undefined,search:search.value.trim() || undefined,offset:offset.value})
    if (request === sequence) result.value = next
  } catch { if (request === sequence) { result.value = null; error.value = t('error') } }
  finally { if (request === sequence) loading.value = false }
}
function clearFilters() { currency.value='';day.value='';search.value='';offset.value=0;load() }
function exportPage() {
  if (!result.value) return
  const cell = (value: unknown) => '"'+String(value??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"'
  const rows = [[t('date'),t('time'),t('seller'),t('customer'),t('currency'),t('gross'),t('net'),t('payment'),t('source')],...result.value.items.map(r => [r.date,r.time,r.seller,r.customer,r.currency,r.gross,r.net,r.payment_method,`${r.filename} — ${r.source_cell}`])]
  const url = URL.createObjectURL(new Blob(['\uFEFF'+rows.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}))
  const link=document.createElement('a');link.href=url;link.download='eleven-lancamentos.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
watch(() => [props.year,props.month,props.seller], () => { result.value=null;offset.value=0;day.value='';load() }, {immediate:true})
watch(() => props.refreshedAt, () => { offset.value=0;load() })
onBeforeUnmount(() => { sequence++ })
</script>

<style scoped>
.entries-panel{color:#172033}header,.table-heading,footer{display:flex;align-items:center;justify-content:space-between;gap:12px}h2{font-size:21px;letter-spacing:-.4px;margin:0 0 8px}h3{font-size:15px;margin:0 0 10px}p,small{color:#64748b;line-height:1.6}p{font-size:12px;margin:6px 0 14px}small{display:block;font-size:11px}button{display:inline-flex;align-items:center;justify-content:center;gap:6px;white-space:nowrap;background:white;border:1px solid #dce3ed;border-radius:8px;padding:9px 12px;color:#334155;font-size:12px;cursor:pointer}button:hover{background:#f1f5f9}button:disabled{opacity:.45;cursor:not-allowed}button:focus-visible,input:focus,select:focus{outline:2px solid #93c5fd;outline-offset:2px}.entry-filters{display:flex;gap:12px;align-items:end;padding:18px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin:18px 0}.entry-filters label{display:flex;flex-direction:column;gap:7px;font-size:11px;color:#64748b;font-weight:600}.search{flex:1}input,select{border:1px solid #dce3ed;border-radius:8px;padding:9px;background:white;font:inherit;font-size:13px;min-width:0}.entry-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}.entry-metrics article,.currency-summary article{border:1px solid #e2e8f0;border-radius:12px;background:white;padding:18px}.entry-metrics span,.currency-summary span{font-size:11px;color:#64748b}.entry-metrics strong,.currency-summary strong{font-size:25px;display:block;margin:12px 0 6px;font-variant-numeric:tabular-nums;letter-spacing:-.5px}.currency-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:20px}.currency-summary article{border-top:3px solid #bfdbfe}.currency-summary strong{font-size:23px}.currency-summary p{margin-bottom:0}.entry-charts{display:grid;grid-template-columns:1.5fr 1fr;gap:18px;margin-bottom:24px}.chart-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px;min-width:0}.hourly{display:flex;gap:4px;height:190px;align-items:end;margin-top:20px}.hour{flex:1;min-width:0;text-align:center}.bar-track{height:140px;display:flex;align-items:end;border-bottom:1px solid #e2e8f0}.bar-track span{display:block;width:100%;background:#3b82f6;border-radius:3px 3px 0 0;min-height:0}.bar-value{font-size:9px;color:#475569;display:block;height:16px}.hour small{font-size:9px;margin-top:7px}.daily-list{display:grid;max-height:220px;overflow:auto}.daily-list button{display:grid;grid-template-columns:1fr auto;text-align:left;border:0;border-radius:0;border-bottom:1px solid #edf2f7;padding:9px 0}.daily-list small{grid-column:1/-1}.weekday-row{display:grid;grid-template-columns:1fr auto;gap:5px;padding:9px 0;border-bottom:1px solid #edf2f7;font-size:12px}.weekday-row small{grid-column:1/-1}.table-heading{margin:20px 0 10px}.table-wrap{overflow-x:auto;border:1px solid #e2e8f0;border-radius:10px;background:white}table{width:100%;border-collapse:collapse;font-size:12px;text-align:left}th{background:#f8fafc;padding:12px;color:#64748b;font-size:10px;text-transform:uppercase}td{padding:13px 12px;border-bottom:1px solid #edf2f7;vertical-align:top}td small{margin-top:5px}.number{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.empty{padding:36px 15px;text-align:center}.notice{padding:13px;border:1px solid #fde68a;border-radius:8px;background:#fffbeb;color:#92400e}.notice.error{background:#fff1f2;border-color:#fecdd3;color:#9f1239}.loading{opacity:.65;pointer-events:none}footer{justify-content:end;margin:13px 0 24px;font-size:12px;color:#64748b}footer span{margin-right:auto}details{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px}summary{font-size:12px;color:#2563eb;cursor:pointer}details p{margin-top:12px}@media(max-width:1050px){.entry-metrics{grid-template-columns:repeat(2,1fr)}.entry-charts{grid-template-columns:1fr}.entry-filters{flex-wrap:wrap}.search{min-width:180px}.entry-metrics strong{font-size:23px}}@media(max-width:620px){header{align-items:start;flex-wrap:wrap}.entry-filters{padding:12px;gap:10px}.entry-filters label{flex:1;min-width:120px}.entry-metrics{gap:9px}.entry-metrics article{padding:13px}.entry-metrics strong{font-size:20px}.chart-card{padding:14px}.hourly{gap:2px}.hour small{font-size:8px}.currency-summary{grid-template-columns:repeat(2,1fr)}.currency-summary article{padding:13px}.currency-summary strong{font-size:19px}}
</style>
