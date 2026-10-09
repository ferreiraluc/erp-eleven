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
        <article><span>{{ tr('Valor líquido no ERP') }}</span><strong>{{ gs(data.summary.net_gs) }}</strong></article>
        <article><span>{{ tr('Devoluções registradas') }}</span><strong>{{ gs(data.summary.refunded_gs) }}</strong></article>
        <article><span>{{ tr('Canceladas') }}</span><strong>{{ data.summary.cancelled }}</strong></article>
      </div>
      <form class="sales-filters" @submit.prevent="page = 1; load()">
        <label class="search-field">{{ tr('Buscar') }}<input v-model="filters.q" :placeholder="tr('Cliente, produto, SKU ou código da venda')" maxlength="150" /></label>
        <label>{{ tr('De') }}<input v-model="filters.date_from" type="date" /></label>
        <label>{{ tr('Até') }}<input v-model="filters.date_to" type="date" /></label>
        <label>{{ tr('Situação') }}<select v-model="filters.status"><option value="">{{ tr('Todas') }}</option><option v-for="status in statuses" :key="status" :value="status">{{ statusText(status) }}</option></select></label>
        <label v-if="!auth.ownSales">{{ tr('Vendedor') }}<select v-model="filters.seller_id"><option value="">{{ tr('Todos') }}</option><option v-for="s in sellers" :key="s.id" :value="s.id">{{ s.name }}</option></select></label>
        <label>{{ tr('Pagamento') }}<select v-model="filters.payment"><option value="">{{ tr('Todos') }}</option><option v-for="method in allPaymentFilters" :key="method" :value="method">{{ paymentText(method) }}</option></select></label>
        <label v-if="auth.isOwner">{{ tr('Listagem') }}<select v-model="filters.deleted"><option :value="false">{{ tr('Vendas visíveis') }}</option><option :value="true">{{ tr('Histórico de excluídas') }}</option></select></label>
        <div class="filter-actions"><button class="erp-button erp-button--primary" :disabled="loading">{{ tr('Filtrar') }}</button><button type="button" class="erp-button erp-button--secondary" @click="clear">{{ tr('Limpar') }}</button></div>
      </form>
      <p v-if="optionsError" role="alert" class="scope-note">{{ tr('Não foi possível carregar os vendedores.') }} <button class="erp-button erp-button--ghost erp-button--sm" @click="loadOptions">{{ tr('Tentar novamente') }}</button></p>
      <p v-if="loading" class="state-box" role="status">{{ tr('Carregando vendas...') }}</p>
      <div v-else-if="error" class="state-box" role="alert"><p>{{ tr(error) }}</p><button class="erp-button erp-button--secondary" @click="load">{{ tr('Tentar novamente') }}</button></div>
      <section v-else-if="data" class="sales-results" :aria-label="tr('Vendas')">
        <div class="result-toolbar"><span>{{ data.total }} {{ tr('vendas encontradas') }}</span><button v-if="data.items.length" class="erp-button erp-button--ghost erp-button--sm" @click="exportPage">{{ tr('Exportar página') }}</button></div>
        <div v-if="!data.items.length" class="state-box"><p>{{ tr('Nenhuma venda encontrada neste filtro.') }}</p><button class="erp-button erp-button--secondary" @click="clear">{{ tr('Limpar filtros') }}</button></div>
        <div v-else class="sales-table-wrap"><table><thead><tr><th>{{ tr('Venda') }}</th><th>{{ tr('Cliente e vendedor') }}</th><th>{{ tr('Pagamento') }}</th><th>{{ tr('Situação') }}</th><th>{{ tr('Valor líquido') }}</th><th><span class="sr-only">{{ tr('Ações') }}</span></th></tr></thead>
          <tbody><tr v-for="sale in data.items" :key="sale.id">
            <td :data-label="tr('Venda')"><strong>{{ saleDate(sale.created_at) }}</strong><small>#{{ sale.id.slice(0, 8) }} · {{ sale.items_count }} {{ tr('itens') }}</small></td>
            <td :data-label="tr('Cliente e vendedor')"><strong>{{ sale.cliente_nome || tr('Cliente não informado') }}</strong><small>{{ sale.seller || '—' }}</small></td>
            <td :data-label="tr('Pagamento')">{{ sale.payment_methods.map(paymentText).join(' · ') || '—' }}</td>
            <td :data-label="tr('Situação')"><span class="status" :class="sale.status">{{ statusText(sale.status) }}</span></td>
            <td :data-label="tr('Valor líquido')"><strong>{{ gs(sale.status === 'cancelled' ? 0 : Number(sale.total_gs) - Number(sale.refunded_gs)) }}</strong><small v-if="Number(sale.refunded_gs)">{{ tr('Estorno') }}: {{ gs(sale.refunded_gs) }}</small></td>
            <td><button class="erp-button erp-button--secondary erp-button--sm" @click="selected = sale.id">{{ tr('Ver venda') }}</button></td>
          </tr></tbody></table></div>
        <footer v-if="data.total > data.page_size" class="pagination"><button class="erp-button erp-button--secondary" :disabled="page === 1" @click="page--; load()">{{ tr('Anterior') }}</button><span>{{ page }} / {{ Math.ceil(data.total / data.page_size) }}</span><button class="erp-button erp-button--secondary" :disabled="page * data.page_size >= data.total" @click="page++; load()">{{ tr('Próxima') }}</button></footer>
      </section>
    </main>
    <SaleManagerModal v-if="selected" :sale-id="selected" :sellers="sellers" @close="selected = ''" @changed="load" />
  </div>
</template>
<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ModuleHeader from '@/components/ModuleHeader.vue'
import SaleManagerModal from '@/components/pdv/management/SaleManagerModal.vue'
import { pdvManagementAPI, saleError, type SaleListing } from '@/services/pdvManagement'
import { allPaymentFilters } from '@/services/pdvPayments'
import { tr, gs, saleDate, statusText, paymentText } from '@/components/pdv/management/i18n'
const auth = useAuthStore(), router = useRouter()
const blank = () => ({ q: '', date_from: '', date_to: '', status: '', seller_id: '', payment: '', deleted: false })
const filters = ref(blank()), page = ref(1), loading = ref(false), error = ref(''), selected = ref('')
const data = ref<SaleListing | null>(null), sellers = ref<Array<{ id: string; name: string }>>([])
const optionsError = ref(false)
const statuses = ['completed', 'partially_refunded', 'refunded', 'cancelled']
let sequence = 0, mounted = true
async function load() { const current = ++sequence; loading.value = true; error.value = ''
  try { const result = await pdvManagementAPI.list(Object.fromEntries(Object.entries({ ...filters.value, page: page.value }).filter(([,v]) => v !== ''))); if (current === sequence) data.value = result }
  catch (e) { if (current === sequence) error.value = saleError(e) } finally { if (current === sequence) loading.value = false }
}
function clear() { filters.value = blank(); page.value = 1; load() }
function exportPage() {
  if (!data.value) return
  const safe = (value: unknown) => '"' + String(value ?? '').replace(/^\s*[=+@-]/, "'$&").replaceAll('"', '""') + '"'
  const lines = [[tr('Venda'),tr('Data'),tr('Cliente'),tr('Vendedor'),tr('Situação'),'Total G$','Estorno G$'], ...data.value.items.map(s => [s.id,saleDate(s.created_at),s.cliente_nome,s.seller,statusText(s.status),s.total_gs,s.refunded_gs])]
  const url = URL.createObjectURL(new Blob(['\ufeff' + lines.map(row => row.map(safe).join(';')).join('\r\n')], { type: 'text/csv;charset=utf-8' }))
  const a = document.createElement('a'); a.href = url; a.download = `vendas-pagina-${page.value}.csv`; a.click(); URL.revokeObjectURL(url)
}
async function loadOptions() { optionsError.value = false; try { const result = await pdvManagementAPI.options(); if (mounted) sellers.value = result.sellers } catch { if (mounted) optionsError.value = true } }
onMounted(() => { load(); loadOptions() })
onUnmounted(() => { sequence++; mounted = false })
</script>
<style scoped>
.sales-manager{min-height:100vh;background:#f8fafc;color:#1e293b}.sales-manager>main{max-width:1440px;margin:auto;padding:0 24px 32px}.scope-note{font-size:13px;color:#64748b;line-height:1.5}.sale-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:18px 0}.sale-summary article{background:white;border:1px solid #e2e8f0;border-radius:12px;padding:18px;display:grid;gap:10px}.sale-summary span{font-size:12px;color:#64748b}.sale-summary strong{font-size:22px;color:#1d4ed8;overflow-wrap:anywhere}.sales-filters{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;background:white;border:1px solid #e2e8f0;border-radius:12px;padding:18px;margin-bottom:20px}label{display:grid;gap:6px;font-size:12px;font-weight:600}input,select{width:100%;min-width:0;box-sizing:border-box;font-size:14px;padding:9px;border:1px solid #cbd5e1;border-radius:8px;background:white;color:#334155}.search-field{grid-column:span 2}.filter-actions{display:flex;align-items:end;gap:8px}.sales-results{background:white;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}.result-toolbar,.pagination{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:16px;font-size:13px}.sales-table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;text-align:left}th{font-size:11px;text-transform:uppercase;background:#f8fafc;color:#64748b;padding:12px}td{padding:16px 12px;border-top:1px solid #e2e8f0;font-size:13px}td strong,td small{display:block}td small{margin-top:5px;font-size:11px;color:#64748b}.status{display:inline-block;padding:5px 8px;border-radius:6px;background:#f1f5f9;font-size:11px;font-weight:600}.completed{background:#dcfce7;color:#166534}.partially_refunded{background:#fef3c7;color:#92400e}.cancelled,.refunded{background:#fee2e2;color:#991b1b}.state-box{text-align:center;padding:40px 16px;color:#64748b}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}
@media(max-width:900px){.sales-filters{grid-template-columns:repeat(2,minmax(0,1fr))}.sale-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.sale-summary strong{font-size:18px}}
@media(max-width:600px){.sales-manager>main{padding:0 12px 24px}.sale-summary{gap:8px}.sale-summary article{padding:12px}.sales-filters{gap:10px;padding:12px}input,select{font-size:16px}.sales-table-wrap{overflow:visible}table,tbody,tr,td{display:block}thead{display:none}tr{padding:12px;border-top:1px solid #e2e8f0}td{border:0;padding:6px 0;display:flex;align-items:center;justify-content:space-between;gap:12px;text-align:right;flex-wrap:wrap}td:before{content:attr(data-label);color:#64748b;font-size:11px;text-align:left}td small{flex-basis:100%;margin:0}td:last-child{justify-content:flex-end}.sale-summary strong{font-size:17px}.scope-note{font-size:12px}}
</style>
