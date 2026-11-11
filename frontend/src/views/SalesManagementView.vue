<template>
  <div class="sales-manager">
    <ModuleHeader :title="tr('Vendas')">
      <button class="erp-button erp-button--secondary" :disabled="loading" @click="load">{{ tr('Atualizar') }}</button>
      <button class="erp-button erp-button--primary" @click="router.push('/pdv')">+ {{ tr('Nova Venda') }}</button>
    </ModuleHeader>
    <main>
      <p class="scope-note">{{ tr('Vendas registradas no PDV. Os resultados das planilhas continuam na Visão de vendas.') }}</p>
      <p v-if="auth.ownSales" class="scope-note">{{ tr('Você está consultando apenas suas vendas.') }}</p>
      <div v-if="data && !loading && !error" class="sale-summary">
        <article><span>{{ tr('Vendas no período') }}</span><strong>{{ data.total }}</strong></article>
        <article><span>{{ tr('Valor líquido no ERP') }}</span><strong>{{ usd(data.summary.usd_unavailable ? null : data.summary.net_usd) }}</strong></article>
        <article class="summary-secondary"><span>{{ tr('Devoluções registradas') }}</span><strong>{{ usd(data.summary.usd_unavailable ? null : data.summary.refunded_usd) }}</strong></article>
        <article class="summary-secondary"><span>{{ tr('Canceladas') }}</span><strong>{{ data.summary.cancelled }}</strong></article>
      </div>
      <p v-if="data?.summary.usd_unavailable" class="scope-note">{{ tr('Cotação histórica indisponível') }} · {{ data.summary.usd_unavailable }}</p>
      <div ref="filterRoot" class="filter-disclosure" @keydown.esc.stop.prevent="closeFilters(true)">
        <div class="filter-toolbar">
          <button ref="filterTrigger" type="button" class="filter-trigger erp-control" :class="{ 'is-open': filtersOpen, 'has-filters': activeFilters.length }"
            :id="filterTriggerId" :aria-expanded="filtersOpen" :aria-controls="filterPanelId"
            @click="filtersOpen ? closeFilters() : openFilters()" @keydown.down.prevent="openFilters(true)">
            <Search aria-hidden="true" /><span>{{ tr('Buscar e filtrar') }}</span>
            <span v-if="activeFilters.length" class="filter-count">{{ activeFilters.length }}</span>
            <ChevronDown class="filter-chevron" aria-hidden="true" />
          </button>
          <button type="button" class="erp-button erp-button--secondary scan-ticket" @click="openScanner"><ScanLine aria-hidden="true" />{{ tr('Ler ticket') }}</button>
        </div>
        <form v-if="filtersOpen" ref="filterPanel" :id="filterPanelId" class="sales-filters" :style="filterPosition" role="region" :aria-labelledby="filterTriggerId" @submit.prevent="applyFilters">
          <div class="filter-panel-title"><strong>{{ tr('Buscar e filtrar') }}</strong><button type="button" class="filter-close erp-control" :aria-label="tr('Fechar filtros')" @click="closeFilters(true)"><X aria-hidden="true" /></button></div>
          <label class="search-field" :for="`${filterPanelId}-search`">{{ tr('Buscar') }}<input ref="searchInput" :id="`${filterPanelId}-search`" v-model="filters.q" type="search" :placeholder="tr('Cliente, produto, SKU ou código da venda')" maxlength="150" /></label>
          <label>{{ tr('De') }}<input v-model="filters.date_from" type="date" /></label>
          <label>{{ tr('Até') }}<input v-model="filters.date_to" type="date" /></label>
          <label>{{ tr('Situação') }}<ErpSelect :label="tr('Situação')" v-model="filters.status"><option value="">{{ tr('Todas') }}</option><option v-for="status in statuses" :key="status" :value="status">{{ statusText(status) }}</option></ErpSelect></label>
          <label v-if="!auth.ownSales">{{ tr('Vendedor') }}<ErpSelect :label="tr('Vendedor')" v-model="filters.seller_id"><option value="">{{ tr('Todos') }}</option><option v-for="s in sellers" :key="s.id" :value="s.id">{{ s.name }}</option></ErpSelect></label>
          <label>{{ tr('Pagamento') }}<ErpSelect :label="tr('Pagamento')" v-model="filters.payment"><option value="">{{ tr('Todos') }}</option><option v-for="method in allPaymentFilters" :key="method" :value="method">{{ paymentText(method) }}</option></ErpSelect></label>
          <label v-if="auth.isOwner">{{ tr('Listagem') }}<ErpSelect :label="tr('Listagem')" v-model="filters.deleted"><option :value="false">{{ tr('Vendas visíveis') }}</option><option :value="true">{{ tr('Histórico de excluídas') }}</option></ErpSelect></label>
          <div class="filter-actions"><button class="erp-button erp-button--primary" :disabled="loading" type="submit">{{ tr('Filtrar') }}</button><button type="button" class="erp-button erp-button--secondary" @click="clear">{{ tr('Limpar') }}</button></div>
        </form>
      </div>
      <div v-if="activeFilters.length" class="active-filters" :aria-label="tr('Filtros aplicados')">
        <button v-for="filter in activeFilters" :key="filter.key" type="button" class="filter-chip erp-control" :aria-label="`${tr('Remover filtro')}: ${filter.label}`" @click="removeFilter(filter.key)"><span>{{ filter.label }}</span><X aria-hidden="true" /></button>
        <button v-if="activeFilters.length > 1" type="button" class="erp-button erp-button--ghost erp-button--sm" @click="clear">{{ tr('Limpar filtros') }}</button>
      </div>
      <p v-if="optionsError" role="alert" class="scope-note">{{ tr('Não foi possível carregar os vendedores.') }} <button class="erp-button erp-button--ghost erp-button--sm" @click="loadOptions">{{ tr('Tentar novamente') }}</button></p>
      <p v-if="loading" class="state-box" role="status">{{ tr('Carregando vendas...') }}</p>
      <div v-else-if="error" class="state-box" role="alert"><p>{{ tr(error) }}</p><button class="erp-button erp-button--secondary" @click="load">{{ tr('Tentar novamente') }}</button></div>
      <section v-else-if="data" class="sales-results" :aria-label="tr('Vendas')">
        <div class="result-toolbar"><span>{{ data.total }} {{ tr('vendas encontradas') }}</span><button v-if="data.items.length" class="erp-button erp-button--ghost erp-button--sm" @click="exportPage">{{ tr('Exportar página') }}</button></div>
        <div v-if="!data.items.length" class="state-box"><p>{{ tr('Nenhuma venda encontrada neste filtro.') }}</p><button class="erp-button erp-button--secondary" @click="clear">{{ tr('Limpar filtros') }}</button></div>
        <div v-else class="sales-table-wrap">
          <table>
            <thead><tr><th>{{ tr('Venda') }}</th><th>{{ tr('Cliente e vendedor') }}</th><th>{{ tr('Pagamento') }}</th><th>{{ tr('Situação') }}</th><th>{{ tr('Valor líquido') }}</th><th><span class="sr-only">{{ tr('Ações') }}</span></th></tr></thead>
            <tbody><tr v-for="sale in data.items" :key="sale.id" class="sale-row">
              <td class="sale-identity"><div><strong class="sale-date">{{ saleDate(sale.created_at) }}</strong><small>#{{ sale.ticket_code || sale.id.replaceAll('-', '').slice(0, 10).toUpperCase() }} · {{ sale.items_count }} {{ tr('itens') }}</small></div><div v-if="sale.products?.some(p => p.preview)" class="sold-previews"><ProductThumbnail v-for="(product,index) in sale.products.filter(p => p.preview)" :key="index" :item="product.preview!" :title="product.name" class="sold-preview" /></div></td>
              <td class="sale-customer"><strong>{{ sale.cliente_nome || tr('Cliente não informado') }}</strong><small><UserRound aria-hidden="true" />{{ sale.seller || '—' }}</small></td>
              <td class="sale-payment"><span class="sr-only">{{ tr('Pagamento') }}: </span>{{ sale.payment_methods.map(paymentText).join(' · ') || '—' }}</td>
              <td class="sale-status"><span class="status" :class="sale.status">{{ statusText(sale.status) }}</span></td>
              <td class="sale-value"><span class="sr-only">{{ tr('Valor líquido') }}: </span><strong>{{ usd(sale.net_usd) }}</strong><small v-if="Number(sale.refunded_gs)">{{ tr('Estorno') }}: {{ usd(sale.refunded_usd) }}</small></td>
              <td class="sale-action-cell"><div class="sale-actions"><button class="erp-button erp-button--secondary erp-button--sm" @click="openSale(sale.id)">{{ tr('Ver venda') }}<ChevronRight aria-hidden="true" /></button><button v-if="auth.isOwner && !sale.deleted_at" class="erp-button erp-button--ghost erp-button--sm" @click="notificationSaleId = sale.id">{{ tr('Notificar vendedor') }}</button></div></td>
            </tr></tbody>
          </table>
        </div>
        <footer v-if="data.total > data.page_size" class="pagination"><button class="erp-button erp-button--secondary" :disabled="page === 1" @click="page--; load()">{{ tr('Anterior') }}</button><span>{{ page }} / {{ Math.ceil(data.total / data.page_size) }}</span><button class="erp-button erp-button--secondary" :disabled="page * data.page_size >= data.total" @click="page++; load()">{{ tr('Próxima') }}</button></footer>
      </section>
    </main>
    <BarcodeScanner v-if="showScanner" @barcode-detected="findTicket" @close="showScanner=false" />
    <SaleManagerModal v-if="selected" :key="selected" :sale-id="selected" :sellers="sellers" @close="closeSale" @changed="load" />
    <SaleNotificationModal v-if="notificationSaleId && auth.isOwner" :sale-id="notificationSaleId" @close="notificationSaleId = ''" @sent="notificationSaleId = ''" />
  </div>
</template>
<script setup lang="ts">
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { computed, nextTick, onMounted, onUnmounted, ref, useId, watch } from 'vue'
import { ChevronDown, ChevronRight, Search, ScanLine, UserRound, X } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ModuleHeader from '@/components/ModuleHeader.vue'
import ProductThumbnail from '@/components/inventory/ProductThumbnail.vue'
import SaleManagerModal from '@/components/pdv/management/SaleManagerModal.vue'
import SaleNotificationModal from '@/components/notifications/SaleNotificationModal.vue'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import { pdvManagementAPI, saleError, type SaleListing } from '@/services/pdvManagement'
import { allPaymentFilters } from '@/services/pdvPayments'
import { usd } from '@/services/saleUsd'
import { tr, saleDate, statusText, paymentText } from '@/components/pdv/management/i18n'
const auth = useAuthStore(), router = useRouter(), route = useRoute()
const blank = () => ({ q: '', date_from: '', date_to: '', status: '', seller_id: '', payment: '', deleted: false })
type FilterKey = keyof ReturnType<typeof blank>
const filters = ref(blank()), page = ref(1), loading = ref(false), error = ref(''), selected = ref('')
const appliedFilters = ref(blank()), filtersOpen = ref(false)
const filterRoot = ref<HTMLElement>(), filterTrigger = ref<HTMLButtonElement>(), searchInput = ref<HTMLInputElement>()
const filterPanel = ref<HTMLFormElement>(), filterPosition = ref<Record<string, string>>({})
const filterPanelId = `sales-filters-${useId()}`, filterTriggerId = `${filterPanelId}-trigger`
const data = ref<SaleListing | null>(null), sellers = ref<Array<{ id: string; name: string }>>([])
const optionsError = ref(false), showScanner = ref(false)
const notificationSaleId = ref('')
watch(() => auth.isOwner, owner => { if (!owner) notificationSaleId.value = '' })
const activeFilters = computed(() => {
  const f = appliedFilters.value
  const labels: Partial<Record<FilterKey, string>> = {
    q: f.q && `${tr('Buscar')}: ${f.q}`,
    date_from: f.date_from && `${tr('De')}: ${f.date_from.split('-').reverse().join('/')}`,
    date_to: f.date_to && `${tr('Até')}: ${f.date_to.split('-').reverse().join('/')}`,
    status: f.status && statusText(f.status),
    seller_id: f.seller_id && `${tr('Vendedor')}: ${sellers.value.find(s => s.id === f.seller_id)?.name || '—'}`,
    payment: f.payment && paymentText(f.payment),
    deleted: f.deleted ? tr('Histórico de excluídas') : '',
  }
  return (Object.entries(labels) as Array<[FilterKey, string]>).filter(([, label]) => label).map(([key, label]) => ({ key, label }))
})
async function openFilters(focusSearch = false) {
  filtersOpen.value = true
  await nextTick()
  placeFilters()
  if (focusSearch) searchInput.value?.focus({ preventScroll: true })
}
function closeFilters(restoreFocus = false) {
  filtersOpen.value = false
  if (restoreFocus) filterTrigger.value?.focus({ preventScroll: true })
}
function onOutside(event: PointerEvent) {
  // Selectors render their option list in body; choosing an option must not dismiss its form.
  if (!(event.target instanceof Element) || event.target.closest('.erp-dropdown__menu')) return
  if (!filterRoot.value?.contains(event.target)) closeFilters()
}
function onFocusIn(event: FocusEvent) {
  if (!filtersOpen.value || !(event.target instanceof Element) || event.target.closest('.erp-dropdown__menu')) return
  if (event.target !== filterTrigger.value && !filterPanel.value?.contains(event.target)) closeFilters()
}
function placeFilters() {
  const panel = filterPanel.value, anchor = filterTrigger.value?.getBoundingClientRect()
  if (!filtersOpen.value || !panel || !anchor) return
  const viewport = window.visualViewport
  const left = viewport?.offsetLeft ?? 0, top = viewport?.offsetTop ?? 0
  const width = viewport?.width ?? window.innerWidth, height = viewport?.height ?? window.innerHeight
  const panelWidth = Math.min(680, Math.max(0, width - 24))
  const maxHeight = Math.min(620, Math.max(0, height - 24))
  // Measure at the actual width before clamping the panel to the visible viewport.
  panel.style.width = `${panelWidth}px`
  const panelHeight = Math.min(panel.scrollHeight + 2, maxHeight)
  filterPosition.value = {
    width: `${panelWidth}px`, maxHeight: `${maxHeight}px`,
    left: `${Math.max(left + 12, Math.min(anchor.left, left + width - panelWidth - 12))}px`,
    top: `${Math.max(top + 12, Math.min(anchor.bottom + 8, top + height - panelHeight - 12))}px`,
  }
}
let filterLayoutFrame = 0
function queueFilterLayout() {
  if (!filtersOpen.value || filterLayoutFrame) return
  filterLayoutFrame = window.requestAnimationFrame(() => { filterLayoutFrame = 0; placeFilters() })
}
function applyFilters() {
  appliedFilters.value = { ...filters.value, q: filters.value.q.trim() }
  filters.value = { ...appliedFilters.value }; page.value = 1
  closeFilters(true); void load()
}
function removeFilter(key: FilterKey) {
  appliedFilters.value = { ...appliedFilters.value, [key]: blank()[key] }
  filters.value = { ...filters.value, [key]: blank()[key] }
  page.value = 1; void load()
}
function openScanner() { closeFilters(); showScanner.value = true }
function findTicket(code: string) { showScanner.value = false; filters.value = { ...blank(), q: code.trim() }; applyFilters() }
const statuses = ['completed', 'partially_refunded', 'refunded', 'cancelled']
let sequence = 0, mounted = true
watch(() => route.query.sale_id, value => {
  selected.value = typeof value === 'string' && value.trim().length <= 128 ? value.trim() : ''
}, { immediate: true })
function openSale(id: string) { void router.push({ query: { ...route.query, sale_id: id } }) }
function closeSale() {
  selected.value = ''
  const query = { ...route.query }; delete query.sale_id
  void router.replace({ query })
}
async function load() { const current = ++sequence; loading.value = true; error.value = ''
  try { const result = await pdvManagementAPI.list(Object.fromEntries(Object.entries({ ...appliedFilters.value, page: page.value }).filter(([,v]) => v !== ''))); if (current === sequence) data.value = result }
  catch (e) { if (current === sequence) error.value = saleError(e) } finally { if (current === sequence) loading.value = false }
}
function clear() { filters.value = blank(); applyFilters() }
function exportPage() {
  if (!data.value) return
  const safe = (value: unknown) => '"' + String(value ?? '').replace(/^\s*[=+@-]/, "'$&").replaceAll('"', '""') + '"'
  const lines = [[tr('Venda'),tr('Data'),tr('Cliente'),tr('Vendedor'),tr('Situação'),'Total USD','Estorno USD'], ...data.value.items.map(s => [s.id,saleDate(s.created_at),s.cliente_nome,s.seller,statusText(s.status),s.total_usd,s.refunded_usd])]
  const url = URL.createObjectURL(new Blob(['\ufeff' + lines.map(row => row.map(safe).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = `vendas-pagina-${page.value}.csv`; a.click(); URL.revokeObjectURL(url)
}
async function loadOptions() { optionsError.value = false; try { const result = await pdvManagementAPI.options(); if (mounted) sellers.value = result.sellers } catch { if (mounted) optionsError.value = true } }
onMounted(() => {
  load(); loadOptions()
  document.addEventListener('pointerdown', onOutside)
  document.addEventListener('focusin', onFocusIn)
  window.addEventListener('resize', queueFilterLayout)
  window.addEventListener('scroll', queueFilterLayout, true)
  window.visualViewport?.addEventListener('resize', queueFilterLayout)
  window.visualViewport?.addEventListener('scroll', queueFilterLayout)
})
onUnmounted(() => {
  sequence++; mounted = false
  document.removeEventListener('pointerdown', onOutside)
  document.removeEventListener('focusin', onFocusIn)
  window.removeEventListener('resize', queueFilterLayout)
  window.removeEventListener('scroll', queueFilterLayout, true)
  window.visualViewport?.removeEventListener('resize', queueFilterLayout)
  window.visualViewport?.removeEventListener('scroll', queueFilterLayout)
  if (filterLayoutFrame) window.cancelAnimationFrame(filterLayoutFrame)
})
</script>
<style scoped>
.sales-manager { min-height:100vh; background:#f8fafc; color:#1e293b; }
.sales-manager > main { max-width:1440px; margin:auto; padding:0 24px 32px; }
.scope-note { margin:8px 0; font-size:12px; color:#64748b; line-height:1.45; }
.sale-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:14px 0; }
.sale-summary article { min-width:0; background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding:12px 14px; display:grid; gap:4px; }
.sale-summary span { font-size:12px; color:#64748b; }
.sale-summary strong { font-size:20px; color:#1d4ed8; overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }
.filter-disclosure { position:relative; margin-bottom:12px; z-index:2; }
.filter-toolbar { display:flex; align-items:center; gap:8px; }
.filter-trigger { display:flex; align-items:center; gap:8px; min-height:44px; padding:10px 14px; border:1px solid #cbd5e1; border-radius:12px; background:#fff; color:#475569; cursor:pointer; font:inherit; font-size:14px; }
.filter-trigger.is-open,.filter-trigger.has-filters { border-color:#93c5fd; color:#1d4ed8; background:#eff6ff; }
.filter-trigger svg,.filter-close svg,.filter-chip svg { width:17px; height:17px; flex:none; }
.filter-chevron { margin-left:12px; transition:transform .15s ease; }
.is-open .filter-chevron { transform:rotate(180deg); }
.filter-count { display:inline-flex; align-items:center; justify-content:center; min-width:22px; height:22px; padding:0 4px; border-radius:999px; color:#1d4ed8; background:#dbeafe; font-size:12px; font-weight:700; }
.sales-filters { position:fixed; z-index:50; width:min(680px,calc(100vw - 24px)); box-sizing:border-box; max-height:min(620px,calc(100dvh - 24px)); overflow-y:auto; overscroll-behavior:contain; display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; padding:16px; background:#fff; border:1px solid #cbd5e1; border-radius:16px; box-shadow:0 16px 40px #0f172a20; }
.filter-panel-title { grid-column:1/-1; display:flex; align-items:center; justify-content:space-between; gap:8px; font-size:14px; }
.filter-close { display:flex; align-items:center; justify-content:center; min-width:44px; min-height:44px; border:1px solid #e2e8f0; border-radius:10px; background:#f8fafc; color:#64748b; cursor:pointer; }
.sales-filters label { display:grid; gap:6px; min-width:0; font-size:12px; font-weight:600; }
.sales-filters input { width:100%; min-width:0; min-height:44px; box-sizing:border-box; font:inherit; font-size:16px; padding:10px; border:1px solid #cbd5e1; border-radius:10px; background:#fff; color:#334155; }
.sales-filters :deep(.erp-dropdown__control) { min-height:44px; }
.search-field { grid-column:1/-1; }
.filter-actions { grid-column:1/-1; display:flex; gap:8px; padding:10px 0 0; position:sticky; bottom:-16px; margin-bottom:-16px; padding-bottom:16px; background:#fff; border-top:1px solid #f1f5f9; z-index:1; }
.filter-actions > button { flex:1; }
:is(#app,body) .filter-actions > button { min-height:44px; }
.active-filters { display:flex; flex-wrap:wrap; gap:6px; margin:0 0 12px; }
.filter-chip { display:inline-flex; align-items:center; gap:6px; max-width:100%; min-height:36px; padding:6px 9px; border:1px solid #bfdbfe; border-radius:999px; background:#eff6ff; color:#1d4ed8; cursor:pointer; font:inherit; font-size:12px; text-align:left; }
.filter-chip span { overflow-wrap:anywhere; min-width:0; }
.filter-chip svg { width:14px; height:14px; }
.sales-results { background:#fff; border:1px solid #e2e8f0; border-radius:12px; overflow:hidden; }
.result-toolbar,.pagination { display:flex; justify-content:space-between; align-items:center; gap:10px; padding:12px 16px; font-size:12px; color:#64748b; }
.sales-table-wrap { overflow:auto; }
table { width:100%; border-collapse:collapse; text-align:left; }
th { font-size:11px; text-transform:uppercase; background:#f8fafc; color:#64748b; padding:12px; }
td { padding:12px; border-top:1px solid #e2e8f0; font-size:13px; vertical-align:middle; }
td strong,td small { display:block; }
td small { margin-top:3px; font-size:11px; color:#64748b; line-height:1.4; }
.sale-customer small { display:flex; align-items:center; gap:4px; }
.sale-customer svg { width:13px; height:13px; flex:none; }
.sale-value strong { white-space:nowrap; font-variant-numeric:tabular-nums; }
.sold-previews { display:flex; gap:4px; margin-top:6px; flex-wrap:wrap; }
.sold-preview { width:34px; height:34px; object-fit:contain; border:1px solid #e2e8f0; border-radius:6px; background:#fff; }
.sale-actions { display:flex; flex-wrap:wrap; gap:4px; }
.status { display:inline-block; padding:4px 7px; border-radius:6px; background:#f1f5f9; font-size:11px; font-weight:600; line-height:1.35; }
.completed { background:#dcfce7; color:#166534; }
.partially_refunded { background:#fef3c7; color:#92400e; }
.cancelled,.refunded { background:#fee2e2; color:#991b1b; }
.state-box { text-align:center; padding:32px 16px; color:#64748b; }
.sr-only { position:absolute; width:1px; height:1px; padding:0; overflow:hidden; clip:rect(0,0,0,0); white-space:nowrap; border:0; }
@media(max-width:1199px) {
  .sales-manager > main { padding-inline:16px; }
  .sales-results { border:0; border-radius:0; background:transparent; overflow:visible; }
  .result-toolbar { padding:0 0 10px; min-height:40px; }
  .sales-table-wrap { overflow:visible; }
  table { display:block; }
  thead { display:none; }
  tbody { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
  .sale-row { display:grid; grid-template-columns:minmax(0,1fr) auto; grid-template-areas:"customer value" "identity identity" "status payment" "actions actions"; gap:8px 10px; min-width:0; align-content:start; padding:14px; background:#fff; border:1px solid #dbe2ea; border-radius:14px; box-shadow:0 1px 2px #0f172a05; }
  td { border:0; padding:0; min-width:0; overflow-wrap:anywhere; }
  .sale-customer { grid-area:customer; }
  .sale-customer > strong { font-size:14px; line-height:1.3; }
  .sale-customer small { margin-top:3px; }
  .sale-value { grid-area:value; text-align:right; max-width:165px; }
  .sale-value > strong { font-size:16px; color:#1d4ed8; }
  .sale-value small { max-width:155px; }
  .sale-identity { grid-area:identity; display:flex; align-items:center; justify-content:space-between; gap:8px; }
  .sale-date { font-size:11px; color:#64748b; font-weight:500; }
  .sold-previews { flex-shrink:0; margin-top:0; max-width:45%; }
  .sold-preview { width:30px; height:30px; }
  .sale-status { grid-area:status; align-self:center; }
  .sale-payment { grid-area:payment; align-self:center; text-align:right; font-size:11px; color:#64748b; max-width:160px; }
  .sale-action-cell { grid-area:actions; border-top:1px solid #f1f5f9; padding-top:7px; }
  .sale-actions { align-items:center; justify-content:space-between; }
  :is(#app,body) .sale-actions > .erp-button { min-height:44px; }
  .pagination { padding:16px 0; }
}
@media(max-width:767px) {
  .sales-manager > main { padding:0 12px 24px; }
  .sale-summary { grid-template-columns:repeat(2,minmax(0,1fr)); gap:7px; margin:12px 0; }
  .sale-summary article { padding:10px 12px; }
  .sale-summary strong { font-size:18px; }
  .sale-summary .summary-secondary { display:flex; align-items:center; justify-content:space-between; gap:6px; border:0; background:transparent; padding:2px; }
  .summary-secondary span { font-size:11px; }
  .summary-secondary strong { color:#475569; font-size:12px; flex-shrink:0; white-space:nowrap; }
  .filter-trigger { flex:1; min-width:0; padding:10px; gap:6px; font-size:13px; }
  .filter-chevron { margin-left:auto; }
  :is(#app,body) .scan-ticket { min-height:44px; padding-inline:10px; font-size:12px; gap:5px; }
  .sales-filters { gap:12px; padding:12px; }
  .filter-actions { bottom:-12px; margin-bottom:-12px; padding-bottom:12px; }
  :is(#app,body) .filter-actions > button,.filter-close,.filter-chip { min-height:44px; }
  tbody { grid-template-columns:minmax(0,1fr); gap:12px; }
  .sale-row { padding:12px; gap:7px 8px; }
  .scope-note { font-size:11px; }
}
@media(max-width:359px) {
  .sale-row { grid-template-columns:minmax(0,1fr) minmax(0,.85fr); }
  .sale-value > strong { white-space:normal; overflow-wrap:anywhere; }
  .scan-ticket svg { display:none; }
}
@media(prefers-reduced-motion:reduce) { .filter-chevron { transition:none; } }
</style>
