<template>
  <section class="entries-panel">
    <header><div><h2>{{ t('title') }}</h2><p>{{ t('description') }}</p></div><button class="erp-button erp-button--secondary erp-button--sm" :disabled="loading" @click="load()"><RefreshCw :size="15" />{{ t('reload') }}</button></header>
    <form class="entry-filters" @submit.prevent="offset=0; load()">
      <label>{{ t('currency') }}<select v-model="currency" @change="offset=0; load()"><option value="">{{ t('allCurrencies') }}</option><option v-for="code in result?.currencies || []" :key="code">{{ code }}</option></select></label>
      <label>{{ t('payment') }}<select v-model="paymentMethod" @change="offset=0; load()"><option value="">{{ t('allPayments') }}</option><option v-for="method in paymentOptions" :key="method.value" :value="method.value">{{ method.label }}</option></select></label>
      <label>{{ t('dateFrom') }}<input v-model="dateFrom" type="date" @change="offset=0; load()" /></label>
      <label>{{ t('dateTo') }}<input v-model="dateTo" type="date" @change="offset=0; load()" /></label>
      <label class="search">{{ t('weekFilter') }}<select :value="selectedWeek?.start || ''" @change="selectWeek"><option value="">{{ t('chooseWeek') }}</option><option v-for="week in result?.weeks || []" :key="week.start" :value="week.start">{{ formatDate(week.start) }} – {{ formatDate(week.end) }}</option></select></label>
      <label class="search">{{ t('search') }}<input v-model="search" type="search" :placeholder="t('searchHint')" maxlength="120" /></label>
      <div class="filter-actions"><button class="erp-button erp-button--secondary erp-button--sm" type="submit">{{ t('filter') }}</button><button class="erp-button erp-button--secondary erp-button--sm" v-if="currency || dateFrom || dateTo || paymentMethod || search" type="button" @click="clearFilters">{{ t('clear') }}</button></div>
      <p class="filter-help">{{ dateFrom || dateTo ? t('dateRangeHelp') : t('periodHelp') }}</p>
    </form>
    <p v-if="error" class="notice error" role="alert">{{ error }}</p>
    <p v-if="result?.coverage.needs_sync" class="notice">{{ t('needsSync') }}</p>
    <details v-if="result?.coverage.skipped_rows" class="notice"><summary>{{ t('skipped', { count: result.coverage.skipped_rows }) }}</summary><p>{{ t('skippedHelp') }}</p><ul><li v-for="issue in result.coverage.issues || []" :key="`${issue.filename}-${issue.sheet}`">{{ issue.filename }} · {{ issue.sheet }} · {{ issue.skipped_rows }}</li></ul></details>
    <p v-if="result?.coverage.undated_excluded" class="notice">{{ t('undatedExcluded', { count: result.coverage.undated_excluded }) }}</p>
    <p v-if="result?.coverage.period_excluded" class="notice">{{ t('periodExcluded', { count: result.coverage.period_excluded }) }}</p>
    <p v-if="result?.coverage.inferred_dates || result?.coverage.period_included" class="notice info">{{ t('calendarHelp') }}</p>
    <div v-if="result" :aria-busy="loading" :class="{ loading }">
      <div class="entry-metrics">
        <article><span>{{ t('entries') }}</span><strong>{{ result.summary.count.toLocaleString(locale) }}</strong><small>{{ t('entriesHelp') }}</small></article>
        <article><span>{{ t('dated') }}</span><strong>{{ result.summary.dated_count.toLocaleString(locale) }}</strong><small>{{ t('missingDate', { count: result.summary.undated_count }) }}</small></article>
        <article><span>{{ t('timed') }}</span><strong>{{ result.summary.timed_count.toLocaleString(locale) }}</strong><small>{{ t('timeHelp') }}</small></article>
        <article><span>{{ t('closing') }}</span><strong>{{ money(result.summary.official_total_usd, 'USD') }}</strong><small>{{ t('closingHelp') }}</small></article>
      </div>
      <p v-if="weeklyMachine" class="settlement-summary">{{ t('settlementHelp', { date: formatDate(selectedWeek!.settlement_date) }) }}</p>
      <div v-if="result.summary.currencies.length" class="currency-summary">
        <article v-for="item in result.summary.currencies" :key="item.currency"><span>{{ item.currency }}<template v-if="weeklyMachine"> · {{ t('weeklyNet') }}</template></span><strong>{{ money(weeklyMachine ? item.net : item.gross, item.currency) }}</strong><small>{{ weeklyMachine ? t('net') : t('gross') }} · {{ item.count }} {{ t('entries').toLowerCase() }}</small><p>{{ weeklyMachine ? t('gross') : t('net') }}: {{ money(weeklyMachine ? item.gross : item.net, item.currency) }}<small v-if="item.net_available < item.count">{{ t('netPartial', { count: item.net_available, total: item.count }) }}</small></p></article>
      </div>
      <section v-if="result.payments?.length" class="payment-summary" :aria-label="t('paymentSummary')">
        <h3>{{ t('paymentSummary') }}</h3><p>{{ t('paymentSummaryHelp') }}</p>
        <div class="payment-grid">
          <button v-for="group in result.payments" :key="group.payment_type" type="button" class="payment-card erp-control" :aria-pressed="paymentMethod === group.payment_type" @click="paymentMethod = paymentMethod === group.payment_type ? '' : group.payment_type; offset=0; load()">
            <span class="payment-heading"><b>{{ paymentLabel(group.payment_type, group.label) }}</b><small>{{ t('paymentCount', { count: group.count }) }}</small></span>
            <span v-for="item in group.currencies" :key="item.currency" class="payment-amount"><span>{{ item.currency }} · {{ t('gross') }}</span><strong>{{ money(item.gross, item.currency) }}</strong><small>{{ t('net') }}: {{ money(item.net, item.currency) }}</small><small v-if="item.net_available < item.count">{{ t('netPartial', { count: item.net_available, total: item.count }) }}</small></span>
          </button>
        </div>
      </section>
      <div class="entry-charts">
        <article class="chart-card"><h3>{{ t('intraday') }}</h3><p>{{ t('intradayHelp') }}</p>
          <div v-if="result.hourly.length" class="hourly" role="img" :aria-label="t('intraday')"><div v-for="hour in hours" :key="hour.hour" class="hour"><span class="bar-value">{{ hour.count || '' }}</span><div class="bar-track"><span :style="{height: `${hour.count / maxHour * 100}%`}" :title="`${hour.hour}:00 — ${hour.count} ${t('entries').toLowerCase()}`" /></div><small>{{ hour.hour.toString().padStart(2,'0') }}</small></div></div>
          <p v-else class="empty">{{ t('noTime') }}</p>
        </article>
        <article class="chart-card"><h3>{{ result.daily.length ? t('byDay') : t('byWeekday') }}</h3><p>{{ result.daily.length ? t('byDayHelp') : t('weekdayHelp') }}</p><div v-if="result.daily.length" class="daily-list"><button class="erp-control" v-for="item in result.daily.slice(-10).reverse()" :key="item.date" @click="dateFrom=item.date; dateTo=item.date; offset=0; load()"><span>{{ formatDate(item.date) }}</span><strong>{{ item.count }}</strong><small>{{ item.currencies.map(c => money(c.gross, c.currency)).join(' · ') }}</small></button></div><div v-else-if="result.weekdays.length" class="daily-list"><div v-for="item in result.weekdays" :key="item.day" class="weekday-row"><span>{{ t(`days.${item.day}`) }}</span><strong>{{ item.count }}</strong><small>{{ item.currencies.map(c => money(c.gross,c.currency)).join(' · ') }}</small></div></div><p v-else class="empty">{{ t('noDate') }}</p></article>
      </div>
      <div class="table-heading"><h3>{{ t('details') }}</h3><button class="erp-button erp-button--secondary erp-button--sm" :disabled="!result.items.length || loading" @click="exportPage"><Download :size="14" />{{ t('export') }}</button></div>
      <div class="table-wrap"><table><thead><tr><th>{{ t('date') }}</th><th>{{ t('seller') }}</th><th>{{ t('customer') }}</th><th>{{ t('payment') }}</th><th class="number">{{ t('gross') }}</th><th class="number">{{ t('net') }}</th><th>{{ t('source') }}</th></tr></thead><tbody><tr v-for="entry in result.items" :key="entry.id"><td>{{ entryDate(entry) }}<small v-if="entry.date_source === 'week_day'">{{ t('calendarDate') }}</small><small v-else-if="entry.date_source === 'week_period'">{{ t('calendarPeriod') }}</small><small>{{ entry.time || t('noRecordedTime') }}</small></td><td>{{ entry.seller }}</td><td>{{ entry.customer || '—' }}</td><td>{{ paymentLabel(entry.payment_type, entry.payment_method || '') }}</td><td class="number">{{ money(entry.gross,entry.currency) }}</td><td class="number">{{ money(entry.net,entry.currency) }}</td><td>{{ entry.source_cell }}<small>{{ entry.filename }} · {{ entry.month }}/{{ entry.year }}</small><small>{{ entry.week_label || t('unassignedWeek') }}<span v-if="entry.stale"> · {{ t('stale') }}</span></small></td></tr></tbody></table></div>
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
import { salesEntries, type EntriesResult, type SalesEntry } from '@/services/salesEntries'
import messages from './salesEntries.messages.json'
const props = defineProps<{ year?: number; month?: number; seller?: string; refreshedAt?: string | null }>()
const { t, locale } = useI18n({ useScope: 'local', messages })
const result = ref<EntriesResult | null>(null), error = ref(''), loading = ref(false)
const currency = ref(''), dateFrom = ref(''), dateTo = ref(''), paymentMethod = ref(''), search = ref(''), offset = ref(0)
let sequence = 0
const selectedWeek = computed(() => result.value?.weeks?.find(w => w.start === dateFrom.value && w.end === dateTo.value))
const weeklyMachine = computed(() => paymentMethod.value === 'maquina' && Boolean(selectedWeek.value))
function selectWeek(event: Event) {
  const week = result.value?.weeks?.find(w => w.start === (event.target as HTMLSelectElement).value)
  dateFrom.value = week?.start || ''; dateTo.value = week?.end || ''; offset.value = 0; load()
}
function paymentLabel(key: string, fallback: string) { return Object.hasOwn(messages.pt.paymentTypes, key) ? t(`paymentTypes.${key}`) : fallback }
const paymentOptions = computed(() => {
  const options = new Map(Object.keys(messages.pt.paymentTypes).map(value => [value, { value, label: paymentLabel(value, value) }]))
  for (const item of result.value?.payment_methods || []) options.set(item.value, { ...item, label: paymentLabel(item.value, item.label) })
  if (paymentMethod.value && !options.has(paymentMethod.value)) options.set(paymentMethod.value, { value: paymentMethod.value, label: paymentMethod.value })
  return [...options.values()]
})
const hours = computed(() => Array.from({ length: 24 }, (_, hour) => ({ hour, count: result.value?.hourly.find(r => r.hour === hour)?.count || 0 })))
const maxHour = computed(() => Math.max(1,...hours.value.map(h => h.count)))
const differences = computed(() => result.value?.reconciliation.filter(r => r.difference === null || Math.abs(r.difference) > .05) || [])
function money(value: number | null, code: string) { return value === null ? '—' : value.toLocaleString(locale.value,{style:'currency',currency:code,maximumFractionDigits:code==='PYG'?0:2}) }
function formatDate(value: string) { return new Date(`${value}T12:00:00`).toLocaleDateString(locale.value) }
function entryDate(entry: SalesEntry) {
  if (entry.date) return formatDate(entry.date)
  if (entry.period_start && entry.period_end) return `${formatDate(entry.period_start)} – ${formatDate(entry.period_end)}`
  return entry.day_group ? t(`days.${entry.day_group}`) : '—'
}
async function load() {
  const request = ++sequence
  if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) {
    error.value = t('invalidRange'); result.value = null; loading.value = false; return
  }
  loading.value = true; error.value = ''
  try {
    const next = await salesEntries.list({year:props.year || undefined,month:props.month || undefined,seller:props.seller || undefined,currency:currency.value || undefined,date_from:dateFrom.value || undefined,date_to:dateTo.value || undefined,payment_method:paymentMethod.value || undefined,search:search.value.trim() || undefined,offset:offset.value})
    if (request === sequence) result.value = next
  } catch { if (request === sequence) { result.value = null; error.value = t('error') } }
  finally { if (request === sequence) loading.value = false }
}
function clearFilters() { currency.value='';dateFrom.value='';dateTo.value='';paymentMethod.value='';search.value='';offset.value=0;load() }
function exportPage() {
  if (!result.value) return
  const cell = (value: unknown) => '"'+String(value??'').replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"'
  const rows = [[t('date'),t('time'),t('seller'),t('customer'),t('currency'),t('gross'),t('net'),t('payment'),t('source'),t('dateOrigin')],...result.value.items.map(r => [r.date || (r.period_start && r.period_end ? `${r.period_start} – ${r.period_end}` : ''),r.time,r.seller,r.customer,r.currency,r.gross,r.net,paymentLabel(r.payment_type,r.payment_method || ''),`${r.filename} — ${r.source_cell}`, r.date_source === 'week_day' ? t('calendarDate') : r.date_source === 'week_period' ? t('calendarPeriod') : r.date ? t('recordedDate') : ''])]
  const url = URL.createObjectURL(new Blob(['\uFEFF'+rows.map(r=>r.map(cell).join(';')).join('\r\n')],{type:'text/csv;charset=utf-8'}))
  const link=document.createElement('a');link.href=url;link.download='eleven-lancamentos.csv';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000)
}
watch(() => [props.year,props.month,props.seller], (_, previous) => {
  result.value=null;offset.value=0
  if (!previous || previous[0] !== props.year || previous[1] !== props.month) { dateFrom.value='';dateTo.value='' }
  load()
}, {immediate:true})
watch(() => props.refreshedAt, () => { offset.value=0;load() })
onBeforeUnmount(() => { sequence++ })
</script>

<style scoped>
.entries-panel{color:#172033}header,.table-heading,footer{display:flex;align-items:center;justify-content:space-between;gap:12px}h2{font-size:21px;letter-spacing:-.4px;margin:0 0 8px}h3{font-size:15px;margin:0 0 10px}p,small{color:#64748b;line-height:1.6}p{font-size:12px;margin:6px 0 14px}small{display:block;font-size:11px}button{display:inline-flex;align-items:center;justify-content:center;gap:6px;white-space:nowrap;background:white;border:1px solid #dce3ed;border-radius:8px;padding:9px 12px;color:#334155;font-size:12px;cursor:pointer}button:hover{background:#f1f5f9}button:disabled{opacity:.45;cursor:not-allowed}button:focus-visible,input:focus,select:focus{outline:2px solid #93c5fd;outline-offset:2px}.entry-filters{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;align-items:end;padding:18px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;margin:18px 0}.entry-filters label{display:flex;flex-direction:column;gap:7px;font-size:11px;color:#64748b;font-weight:600}.search{grid-column:span 2}.filter-actions{display:flex;gap:8px;grid-column:span 2}.filter-help{grid-column:1/-1;margin:0}input,select{border:1px solid #dce3ed;border-radius:8px;padding:9px;background:white;font:inherit;font-size:13px;min-width:0}.entry-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px}.entry-metrics article,.currency-summary article{border:1px solid #e2e8f0;border-radius:12px;background:white;padding:18px}.entry-metrics span,.currency-summary span{font-size:11px;color:#64748b}.entry-metrics strong,.currency-summary strong{font-size:25px;display:block;margin:12px 0 6px;font-variant-numeric:tabular-nums;letter-spacing:-.5px}.currency-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin-bottom:20px}.currency-summary article{border-top:3px solid #bfdbfe}.currency-summary strong{font-size:23px}.currency-summary p{margin-bottom:0}.entry-charts{display:grid;grid-template-columns:1.5fr 1fr;gap:18px;margin-bottom:24px}.chart-card{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:20px;min-width:0}.hourly{display:flex;gap:4px;height:190px;align-items:end;margin-top:20px}.hour{flex:1;min-width:0;text-align:center}.bar-track{height:140px;display:flex;align-items:end;border-bottom:1px solid #e2e8f0}.bar-track span{display:block;width:100%;background:#3b82f6;border-radius:3px 3px 0 0;min-height:0}.bar-value{font-size:9px;color:#475569;display:block;height:16px}.hour small{font-size:9px;margin-top:7px}.daily-list{display:grid;max-height:220px;overflow:auto}.daily-list button{display:grid;grid-template-columns:1fr auto;text-align:left;border:0;border-radius:0;border-bottom:1px solid #edf2f7;padding:9px 0}.daily-list small{grid-column:1/-1}.weekday-row{display:grid;grid-template-columns:1fr auto;gap:5px;padding:9px 0;border-bottom:1px solid #edf2f7;font-size:12px}.weekday-row small{grid-column:1/-1}.table-heading{margin:20px 0 10px}.table-wrap{overflow-x:auto;border:1px solid #e2e8f0;border-radius:10px;background:white}table{width:100%;border-collapse:collapse;font-size:12px;text-align:left}th{background:#f8fafc;padding:12px;color:#64748b;font-size:10px;text-transform:uppercase}td{padding:13px 12px;border-bottom:1px solid #edf2f7;vertical-align:top}td small{margin-top:5px}.number{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}.empty{padding:36px 15px;text-align:center}.notice{padding:13px;border:1px solid #fde68a;border-radius:8px;background:#fffbeb;color:#92400e}.notice.error{background:#fff1f2;border-color:#fecdd3;color:#9f1239}.loading{opacity:.65;pointer-events:none}footer{justify-content:end;margin:13px 0 24px;font-size:12px;color:#64748b}footer span{margin-right:auto}details{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:18px}summary{font-size:12px;color:#2563eb;cursor:pointer}details p{margin-top:12px}@media(max-width:1050px){.entry-metrics{grid-template-columns:repeat(2,1fr)}.entry-charts{grid-template-columns:1fr}.entry-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.entry-metrics strong{font-size:23px}}@media(max-width:620px){header{align-items:start;flex-wrap:wrap}.entry-filters{padding:12px;gap:10px}.entry-filters label{min-width:0}.entry-metrics{gap:9px}.entry-metrics article{padding:13px}.entry-metrics strong{font-size:20px}.chart-card{padding:14px}.hourly{gap:2px}.hour small{font-size:8px}.currency-summary{grid-template-columns:repeat(2,1fr)}.currency-summary article{padding:13px}.currency-summary strong{font-size:19px}}
.payment-summary{margin:0 0 24px}.payment-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}.payment-card{display:flex;flex-direction:column;align-items:stretch;justify-content:start;text-align:left;white-space:normal;padding:16px;min-width:0;border-radius:12px}.payment-card[aria-pressed=true]{background:#eff6ff;border-color:#93c5fd}.payment-heading{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px}.payment-heading b{font-size:13px}.payment-amount{display:block;border-top:1px solid #e2e8f0;padding-top:10px;margin-top:10px}.payment-amount>span{font-size:10px;color:#64748b}.payment-amount strong{display:block;font-size:20px;margin:5px 0;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}.payment-amount small{font-weight:400}@media(max-width:620px){.payment-grid{grid-template-columns:1fr 1fr;gap:9px}.payment-card{padding:12px}.payment-amount strong{font-size:18px}.entry-filters input,.entry-filters select{width:100%;box-sizing:border-box}}@media(max-width:360px){.payment-grid{grid-template-columns:1fr}}
.notice.info{background:#eff6ff;border-color:#bfdbfe;color:#1e40af}.notice summary{color:inherit}.notice li{font-size:12px;line-height:1.6}.settlement-summary{font-weight:600;color:#1e40af}
</style>
