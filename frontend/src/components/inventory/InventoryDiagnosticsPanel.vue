<template>
  <section id="inventory-diagnostics" class="diagnostics-panel" aria-labelledby="diagnostics-title">
    <header class="diagnostics-header">
      <div>
        <h2 id="diagnostics-title">{{ t('title') }}</h2>
        <p>{{ t('subtitle') }}</p>
        <small v-if="checkedAt">{{ t('checkedAt', { date: checkedAt }) }}</small>
      </div>
      <div class="diagnostics-actions">
        <button type="button" class="diag-button" :disabled="loading" @click="load()">{{ t('refresh') }}</button>
        <button type="button" class="diag-button close-button" :aria-label="t('close')" @click="emit('close')">×</button>
      </div>
    </header>

    <template v-if="data">
      <div class="diagnostics-summary">
        <div class="summary-card"><span>{{ t('active') }}</span><strong>{{ number(data.total_active_items) }}</strong></div>
        <div class="summary-card" :class="{ 'summary-alert': data.affected_items > 0 }"><span>{{ t('affected') }}</span><strong>{{ number(data.affected_items) }}</strong></div>
        <div v-for="key in issueKeys" :key="key" class="summary-card">
          <span>{{ t(key) }}</span><strong>{{ number(data.counts[key]) }}</strong>
          <small v-if="key === 'duplicate_barcode'">{{ t('duplicates', { count: number(data.counts.duplicate_barcode_groups) }) }}</small>
        </div>
      </div>
      <p class="diagnostics-hint">{{ t('countsHint') }}</p>
    </template>

    <p class="review-notice">{{ t('reviewHint') }}</p>
    <form class="diagnostics-filters" @submit.prevent="applyFilters()">
      <label class="search-field">
        <span>{{ t('searchLabel') }}</span>
        <input v-model="searchDraft" type="search" maxlength="150" :placeholder="t('searchPlaceholder')" />
      </label>
      <label>
        <span>{{ t('issue') }}</span>
        <select v-model="issue" @change="applyFilters()">
          <option value="all">{{ t('all') }}</option>
          <option v-for="key in issueKeys" :key="key" :value="key">{{ t(key) }}</option>
        </select>
      </label>
      <label>
        <span>{{ t('pageSize') }}</span>
        <select v-model.number="pageSize" @change="applyFilters()">
          <option v-for="size in [25, 50, 100]" :key="size" :value="size">{{ size }}</option>
        </select>
      </label>
      <button class="diag-button primary" type="submit">{{ t('search') }}</button>
      <button v-if="issue !== 'all' || query || searchDraft" class="diag-button" type="button" @click="clearFilters()">{{ t('clear') }}</button>
    </form>

    <p v-if="loading" class="diagnostics-state" role="status">{{ t('loading') }}</p>
    <div v-else-if="loadError" class="diagnostics-error" role="alert">
      <span>{{ t('error') }}</span><button type="button" class="diag-button" @click="load()">{{ t('retry') }}</button>
    </div>
    <template v-else-if="data">
      <p v-if="openError" class="diagnostics-error" role="alert">{{ t(openError) }}</p>
      <p v-if="!data.items.length" class="diagnostics-state" role="status">{{ t(data.affected_items === 0 ? 'clearAll' : 'empty') }}</p>
      <div v-else class="diagnostics-table-wrap" tabindex="0" :aria-label="t('title')">
        <table class="diagnostics-table">
          <thead><tr>
            <th scope="col">{{ t('product') }}</th><th scope="col">{{ t('barcode') }}</th>
            <th scope="col">{{ t('total') }}</th><th scope="col">{{ t('store') }}</th><th scope="col">{{ t('warehouse') }}</th>
            <th scope="col">{{ t('expected') }}</th><th scope="col">{{ t('delta') }}</th><th scope="col">{{ t('alerts') }}</th><th scope="col">{{ t('action') }}</th>
          </tr></thead>
          <tbody><tr v-for="item in data.items" :key="item.id" :data-item-id="item.id">
            <th scope="row" class="diagnostic-product"><strong>{{ item.name }}</strong><code>{{ item.sku_internal }}</code><small>{{ [item.brand, item.size, item.color].filter(Boolean).join(' · ') }}</small></th>
            <td class="diagnostic-code">
              <code v-if="item.barcode">{{ item.barcode }}</code><span v-else>{{ t('absent') }}</span>
              <small v-if="item.normalized_barcode && item.normalized_barcode !== item.barcode">{{ t('normalized', { code: item.normalized_barcode }) }}</small>
              <small v-if="item.duplicate_count >= 2">{{ t('shared', { count: number(item.duplicate_count) }) }}</small>
            </td>
            <td v-for="key in stockKeys" :key="key" class="stock-value" :class="{ negative: item[key] !== null && item[key]! < 0 }" :title="item[key] === null ? t('absent') : undefined">{{ number(item[key]) }}</td>
            <td class="stock-value" :class="{ difference: item.delta !== null && item.delta !== 0 }" :title="item.delta === null ? t('absent') : undefined">{{ number(item.delta, true) }}</td>
            <td><div class="diagnostic-issues"><span v-for="alert in item.issues" :key="alert" class="issue-badge" :class="{ severe: alert === 'negative_stock' }">{{ t(isKnownIssue(alert) ? alert : 'other') }}</span></div></td>
            <td><button class="diag-button open-product" type="button" :disabled="!!openingId" @click="emit('open-item', item.id)">{{ t(openingId === item.id ? 'opening' : 'openItem') }}</button></td>
          </tr></tbody>
        </table>
      </div>
      <footer class="diagnostics-pagination">
        <span>{{ t('results', { count: number(data.total_items) }) }}</span>
        <nav :aria-label="t('page', { page: data.page, pages })">
          <button type="button" class="diag-button" :disabled="data.page <= 1" @click="load(data.page - 1)">{{ t('previous') }}</button>
          <span>{{ t('page', { page: data.page, pages }) }}</span>
          <button type="button" class="diag-button" :disabled="data.page >= pages" @click="load(data.page + 1)">{{ t('next') }}</button>
        </nav>
      </footer>
    </template>
    <p class="diagnostics-hint">{{ t('deltaHint') }}</p>
    <p class="diagnostics-hint">{{ t('manualHint') }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { inventoryDiagnosticsAPI, type InventoryDiagnostics, type InventoryIssue, type InventoryIssueFilter } from '@/services/inventoryDiagnostics'
import { diagnosticsMessages } from './diagnosticsMessages'

const props = withDefaults(defineProps<{ revision?: number; openingId?: string | null; openError?: 'openError' | 'inactive' | null }>(), { revision: 0, openingId: null, openError: null })
const emit = defineEmits<{ (event: 'close'): void; (event: 'open-item', id: string): void }>()
const { t, locale } = useI18n({ useScope: 'local', messages: diagnosticsMessages })
const issueKeys: InventoryIssue[] = ['stock_mismatch', 'negative_stock', 'missing_stock', 'duplicate_barcode']
const stockKeys = ['current_stock', 'stock_loja', 'stock_deposito', 'expected_stock'] as const
const issue = ref<InventoryIssueFilter>('all'), searchDraft = ref(''), query = ref('')
const page = ref(1), pageSize = ref(25), data = ref<InventoryDiagnostics | null>(null)
const loading = ref(false), loadError = ref(false)
let generation = 0, controller: AbortController | null = null

const displayLocale = computed(() => locale.value === 'es' ? 'es-PY' : locale.value === 'en' ? 'en-US' : 'pt-BR')
const pages = computed(() => data.value ? Math.max(1, Math.ceil(data.value.total_items / data.value.page_size)) : 1)
const checkedAt = computed(() => {
  if (!data.value) return ''
  const date = new Date(data.value.checked_at)
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(displayLocale.value, {
    timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
})
function number(value: number | null, signed = false) {
  if (value === null || !Number.isFinite(value)) return '—'
  return value.toLocaleString(displayLocale.value, { signDisplay: signed ? 'exceptZero' : 'auto' })
}
function isKnownIssue(value: string): value is InventoryIssue { return issueKeys.includes(value as InventoryIssue) }

async function load(targetPage = page.value) {
  const request = ++generation
  controller?.abort()
  controller = new AbortController()
  page.value = targetPage
  loading.value = true
  loadError.value = false
  data.value = null // Never show old rows under a newly selected filter.
  try {
    const result = await inventoryDiagnosticsAPI.get({ issue: issue.value, q: query.value, page: targetPage, page_size: pageSize.value }, controller.signal)
    if (request !== generation) return
    const lastPage = Math.max(1, Math.ceil(result.total_items / result.page_size))
    if (targetPage > lastPage) {
      // A manual correction may have removed the last item on this page.
      await load(lastPage)
      return
    }
    data.value = result
    page.value = result.page
  } catch {
    if (request === generation) loadError.value = true
  } finally {
    if (request === generation) loading.value = false
  }
}
function applyFilters() {
  query.value = searchDraft.value.trim().slice(0, 150)
  searchDraft.value = query.value
  load(1)
}
function clearFilters() {
  searchDraft.value = ''; query.value = ''; issue.value = 'all'
  load(1)
}
watch(() => props.revision, () => load())
onMounted(() => load())
onUnmounted(() => { generation++; controller?.abort() })
</script>

<style scoped>
.diagnostics-panel { margin: 1rem; padding: 1.25rem; border: 1px solid #dbe3ef; border-radius: 12px; background: white; color: #1f2937; box-shadow: 0 2px 8px #0f172a06; }
.diagnostics-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; margin-bottom: 1rem; }
.diagnostics-header h2 { margin: 0; font-size: 1.05rem; color: #111827; }
.diagnostics-header p { font-size: .85rem; color: #6b7280; margin: .35rem 0; }
.diagnostics-header small { color: #6b7280; font-size: .75rem; }
.diagnostics-actions { display: flex; align-items: center; gap: .5rem; }
.diag-button { border: 1px solid #d1d5db; border-radius: 7px; padding: .5rem .7rem; color: #374151; background: white; font-size: .8rem; cursor: pointer; white-space: nowrap; }
.diag-button:hover:not(:disabled) { background: #f3f4f6; border-color: #9ca3af; }
.diag-button:focus-visible, input:focus-visible, select:focus-visible, .diagnostics-table-wrap:focus-visible { outline: 2px solid #3b82f6; outline-offset: 2px; }
.diag-button:disabled { opacity: .45; cursor: not-allowed; }
.diag-button.primary { background: #2563eb; border-color: #2563eb; color: white; }
.diag-button.primary:hover { background: #1d4ed8; }
.close-button { font-size: 1.3rem; line-height: 1; padding: .42rem .6rem; }
.diagnostics-summary { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: .6rem; }
.summary-card { padding: .75rem; background: #f8fafc; border: 1px solid #e5e7eb; border-radius: 8px; display: flex; flex-direction: column; gap: .3rem; }
.summary-card span { font-size: .73rem; color: #4b5563; }
.summary-card strong { font-size: 1.35rem; }
.summary-card small { font-size: .68rem; color: #6b7280; }
.summary-alert { background: #fffbeb; border-color: #fde68a; color: #92400e; }
.diagnostics-hint { font-size: .74rem; line-height: 1.5; color: #6b7280; margin: .6rem 0 0; }
.review-notice { font-size: .8rem; line-height: 1.5; color: #475569; background: #eff6ff; padding: .7rem .85rem; border-radius: 8px; margin: 1rem 0; }
.diagnostics-filters { display: flex; flex-wrap: wrap; align-items: flex-end; gap: .6rem; margin-bottom: 1rem; }
.diagnostics-filters label { display: flex; flex-direction: column; gap: .35rem; font-size: .75rem; color: #4b5563; }
.search-field { flex: 1; min-width: 200px; }
.diagnostics-filters input, .diagnostics-filters select { border: 1px solid #d1d5db; border-radius: 7px; padding: .5rem .65rem; font-size: .8rem; background: white; min-height: 34px; }
.diagnostics-state { padding: 1.75rem 1rem; text-align: center; color: #6b7280; font-size: .85rem; background: #f9fafb; border-radius: 8px; }
.diagnostics-error { color: #b91c1c; background: #fef2f2; padding: .75rem; border-radius: 8px; font-size: .8rem; display: flex; align-items: center; gap: .75rem; }
.diagnostics-table-wrap { overflow-x: auto; border: 1px solid #e5e7eb; border-radius: 8px; }
.diagnostics-table { width: 100%; border-collapse: collapse; text-align: left; font-size: .8rem; }
.diagnostics-table th, .diagnostics-table td { padding: .8rem .65rem; border-bottom: 1px solid #e5e7eb; vertical-align: middle; }
.diagnostics-table thead th { background: #f9fafb; color: #6b7280; font-weight: 500; font-size: .7rem; white-space: nowrap; }
.diagnostics-table tr:last-child td, .diagnostics-table tr:last-child th { border-bottom: 0; }
.diagnostic-product { min-width: 160px; font-weight: 400; }
.diagnostic-product strong { display: block; margin-bottom: .3rem; overflow-wrap: anywhere; }
.diagnostic-product code { font-size: .7rem; color: #64748b; }
.diagnostic-product small, .diagnostic-code small { display: block; margin-top: .3rem; color: #64748b; font-size: .68rem; overflow-wrap: anywhere; }
.diagnostic-code { min-width: 130px; max-width: 200px; overflow-wrap: anywhere; }
.stock-value { text-align: right; font-variant-numeric: tabular-nums; }
.negative { color: #b91c1c; font-weight: 600; }
.difference { color: #b45309; font-weight: 600; }
.diagnostic-issues { display: flex; flex-wrap: wrap; gap: .3rem; min-width: 120px; }
.issue-badge { background: #fef3c7; color: #92400e; border-radius: 5px; padding: .2rem .4rem; font-size: .68rem; }
.issue-badge.severe { background: #fee2e2; color: #b91c1c; }
.diagnostics-pagination, .diagnostics-pagination nav { display: flex; align-items: center; gap: .6rem; }
.diagnostics-pagination { justify-content: space-between; flex-wrap: wrap; margin-top: .85rem; font-size: .76rem; color: #6b7280; }
@media (max-width: 1050px) { .diagnostics-summary { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 600px) {
  .diagnostics-panel { margin: .75rem; padding: .85rem; }
  .diagnostics-header { flex-wrap: wrap; gap: .6rem; }
  .diagnostics-header h2 { font-size: 1rem; }
  .diagnostics-actions { width: 100%; justify-content: space-between; }
  .diagnostics-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .search-field { flex-basis: 100%; }
  .diagnostics-pagination nav { flex-wrap: wrap; }
}
</style>
