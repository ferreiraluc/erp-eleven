<template>
  <div class="clientes-view">
    <ModuleHeader :title="uiText('Clientes')">
      <button v-if="auth.isOwner" type="button" class="erp-button erp-button--secondary" :aria-pressed="selectionMode" @click="toggleSelectionMode">{{ mergeText(selectionMode ? 'finish' : 'select') }}</button>
      <button @click="openCreate" class="btn btn-primary erp-button erp-button--primary">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        {{ uiText(`Novo cliente`) }}
      </button>
    </ModuleHeader>

    <!-- Search -->
    <div class="search-section">
      <div class="search-box">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" class="search-icon">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input v-model="searchQuery" type="text" maxlength="200" :placeholder="uiText(`Buscar por nome, telefone, CPF, e-mail...`)" class="search-input" />
      </div>
      <div class="filter-row">
        <button v-for="filter in statusFilters" :key="filter.value" class="erp-control" :class="['chip', { active: statusFilter === filter.value }]" :aria-pressed="statusFilter === filter.value" @click="statusFilter = filter.value">
          {{ uiText(filter.label) }}
        </button>
        <div class="customer-sort"><ErpSelect v-model="sort" :label="customerText('sort')"><option value="nome">{{ customerText('name') }}</option><option value="ultima_compra">{{ customerText('latestPurchase') }}</option><option value="ultima_impressao">{{ customerText('latestPrint') }}</option></ErpSelect></div>
        <span v-if="!loading && !loadError" class="total-count">{{ total === 1 ? uiText('{0} cliente',{0:total}) : uiText('{0} clientes',{0:total}) }}</span>
      </div>
      <div v-if="selectionMode && auth.isOwner" class="customer-selection" role="region" :aria-label="mergeText('selected', { count: selectedCustomers.length })">
        <div><strong>{{ mergeText('selected', { count: selectedCustomers.length }) }}</strong><p>{{ mergeText('selectionHelp') }}</p></div>
        <div class="customer-selection-actions"><button type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="!selectedCustomers.length" @click="selectedById = {}">{{ mergeText('clear') }}</button><button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="selectedCustomers.length < 2" @click="showMerge = true">{{ mergeText('merge') }}</button></div>
        <p v-if="selectedCustomers.length >= selectionLimit" class="customer-selection-limit" role="status">{{ mergeText('limit') }}</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading-state" role="status">
      <div class="spinner"></div>
      <p>{{ uiText(`Carregando...`) }}</p>
    </div>

    <div v-else-if="loadError" class="empty-state" role="alert">
      <p>{{ uiText('Não foi possível carregar os clientes.') }}</p>
      <button @click="loadPage(page)" class="erp-button erp-button--secondary">{{ uiText('Tentar novamente') }}</button>
    </div>

    <!-- Empty -->
    <div v-else-if="clientes.length === 0" class="empty-state">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="48" height="48">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
      <p>{{ uiText(`Nenhum cliente encontrado`) }}</p>
      <button v-if="searchQuery.trim() || statusFilter !== 'active'" @click="clearFilters" class="erp-button erp-button--secondary" style="margin-top:1rem">{{ uiText('Limpar Filtros') }}</button>
      <button v-else @click="openCreate" class="btn btn-primary erp-button erp-button--primary" style="margin-top:1rem">{{ uiText(`Novo cliente`) }}</button>
    </div>

    <div v-else class="clientes-list">
      <CustomerActivityCard
        v-for="c in clientes" :key="c.id" :customer="c" :expanded="expandedId === c.id"
        :selectable="selectionMode && auth.isOwner" :selected="selectionMode && !!selectedById[c.id]" :selection-disabled="selectedCustomers.length >= selectionLimit"
        @toggle="toggleHistory(c.id)" @edit="openEdit(c)" @deactivate="confirmDelete(c)"
        @select="toggleSelected(c)"
      >
        <CustomerLogisticsPanel v-if="expandedId === c.id" :customer="c" @changed="refreshActivity" />
      </CustomerActivityCard>
    </div>

    <nav v-if="!loadError && totalPages > 1" class="customer-pagination" :aria-label="uiText('Página')">
      <button @click="changePage(page - 1)" class="erp-button erp-button--secondary" :disabled="loading || page === 1">{{ uiText('Anterior') }}</button>
      <span>{{ uiText('Página') }} {{ page }} {{ uiText('de') }} {{ totalPages }}</span>
      <button @click="changePage(page + 1)" class="erp-button erp-button--secondary" :disabled="loading || page >= totalPages">{{ uiText('Próxima') }}</button>
    </nav>

    <CustomerMergeSelectionModal v-if="showMerge && auth.isOwner" :customers="selectedCustomers" @close="showMerge = false" @changed="onMerged" />

    <!-- Form Modal -->
    <ClienteFormModal
      :is-visible="showForm"
      :cliente="editingCliente"
      @close="showForm = false; editingCliente = null"
      @saved="onSaved"
    />

    <!-- Toast -->
    <transition name="toast">
      <div v-if="toast" :class="['toast', 'toast-' + toast.type]">{{ toast.message }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import ModuleHeader from '@/components/ModuleHeader.vue'
import CustomerMergeSelectionModal from '@/components/clientes/CustomerMergeSelectionModal.vue'
import { useAuthStore } from '@/stores/auth'
import { uiText } from '@/i18n/uiText'
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { clientesAPI, type Cliente } from '@/services/api'
import ClienteFormModal from '@/components/clientes/ClienteFormModal.vue'
import CustomerLogisticsPanel from '@/components/logistics/CustomerLogisticsPanel.vue'
import CustomerActivityCard from '@/components/clientes/CustomerActivityCard.vue'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { useI18n } from 'vue-i18n'
import { customerMessages } from '@/components/clientes/customerMessages'
import { customerMergeMessages } from '@/components/clientes/customerMergeMessages'
import type { CustomerSort, CustomerWithActivity } from '@/services/customerLogistics'
const { t: customerText } = useI18n({ useScope: 'local', messages: { pt: { ...customerMessages.pt, ...customerMergeMessages.pt }, es: { ...customerMessages.es, ...customerMergeMessages.es }, en: { ...customerMessages.en, ...customerMergeMessages.en } } })
const mergeText = customerText
const auth = useAuthStore()
const selectionMode = ref(false), showMerge = ref(false)
const selectedById = ref<Record<string, Cliente>>({})
const selectedCustomers = computed(() => Object.values(selectedById.value))
const selectionLimit = 20

type CustomerStatusFilter = 'active' | 'inactive' | 'all'
const clientes = ref<CustomerWithActivity[]>([])
const sort = ref<CustomerSort>('nome')
const loading = ref(true), loadError = ref(false), total = ref(0)
const searchQuery = ref('')
const statusFilter = ref<CustomerStatusFilter>('active')
const statusFilters = [{ value: 'active', label: 'Ativos' }, { value: 'inactive', label: 'Inativos' }, { value: 'all', label: 'Todos' }] as const
const showForm = ref(false)
const editingCliente = ref<Cliente | null>(null)
const toast = ref<{ message: string; type: string } | null>(null)
const page = ref(1)
const pageSize = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
let requestVersion = 0

// Histórico por cliente
const expandedId = ref<string | null>(null)
function toggleHistory(id: string) {
  expandedId.value = expandedId.value === id ? null : id
}

let searchTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, () => {
  requestVersion++
  loading.value = true; loadError.value = false; expandedId.value = null
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => reload(), 300)
}, { flush: 'sync' })
watch([statusFilter, sort], () => reload(), { flush: 'sync' })
watch(() => auth.token, () => {
  requestVersion++
  if (searchTimer) { clearTimeout(searchTimer); searchTimer = null }
  clientes.value = []; total.value = 0; expandedId.value = null
  showForm.value = false; editingCliente.value = null; showMerge.value = false
  selectedById.value = {}; selectionMode.value = false
  loadError.value = false
  if (auth.token) void loadPage(1)
  else loading.value = false
}, { flush: 'sync' })
watch(() => auth.isOwner, owner => {
  if (!owner) { selectedById.value = {}; selectionMode.value = false; showMerge.value = false }
}, { flush: 'sync' })

function toggleSelectionMode() { selectionMode.value = !selectionMode.value }
function toggleSelected(customer: Cliente) {
  if (!auth.isOwner || !selectionMode.value) return
  const selected = { ...selectedById.value }
  if (selected[customer.id]) delete selected[customer.id]
  else if (selectedCustomers.value.length < selectionLimit) selected[customer.id] = customer
  selectedById.value = selected
}
async function onMerged(targetId: string, sourceIds: string[]) {
  const token = auth.token
  showMerge.value = false
  const selected = { ...selectedById.value }
  sourceIds.forEach(id => { delete selected[id] })
  selectedById.value = selected
  expandedId.value = targetId
  await loadPage(page.value)
  if (token === auth.token) showToast(mergeText('success'), 'success')
}

function reload() {
  expandedId.value = null
  return loadPage(1)
}

async function loadPage(targetPage: number, background = false) {
  if (searchTimer) { clearTimeout(searchTimer); searchTimer = null }
  const version = ++requestVersion, token = auth.token
  page.value = targetPage
  if (!background) loading.value = true
  loadError.value = false
  try {
    const result = await clientesAPI.getPage({
      page: targetPage, page_size: pageSize,
      search: searchQuery.value.trim() || undefined,
      sort: sort.value, ativo: statusFilter.value !== 'inactive', include_inactive: statusFilter.value === 'all',
    })
    if (version !== requestVersion || token !== auth.token) return
    total.value = result.total
    if (targetPage > totalPages.value) {
      await loadPage(totalPages.value)
      return
    }
    clientes.value = result.items
    for (const customer of result.items) {
      if (selectedById.value[customer.id]) selectedById.value[customer.id] = customer
    }
    if (expandedId.value && !clientes.value.some(customer => customer.id === expandedId.value)) expandedId.value = null
  } catch {
    if (version !== requestVersion || token !== auth.token) return
    loadError.value = true; clientes.value = []
  } finally { if (version === requestVersion) loading.value = false }
}

function refreshActivity() {
  // Keep the expanded, independently paginated history mounted while its summary refreshes.
  void loadPage(page.value, true)
}

function clearFilters() {
  searchQuery.value = ''
  if (statusFilter.value !== 'active') statusFilter.value = 'active'
  else reload()
}

function changePage(targetPage: number) {
  if (loading.value || targetPage < 1 || targetPage > totalPages.value) return
  expandedId.value = null
  void loadPage(targetPage)
}

function openCreate() {
  editingCliente.value = null
  showForm.value = true
}

function openEdit(c: Cliente) {
  editingCliente.value = c
  showForm.value = true
}

function onSaved() {
  void loadPage(editingCliente.value ? page.value : 1)
  showToast(editingCliente.value ? uiText(`Cliente atualizado.`) : uiText(`Cliente criado.`), 'success')
}

async function confirmDelete(c: Cliente) {
  if (!confirm(uiText(`Inativar cliente "{0}"?`,{0:c.nome}))) return
  const token = auth.token
  try {
    await clientesAPI.delete(c.id)
    if (token !== auth.token) return
    await loadPage(page.value)
    showToast(uiText(`Cliente inativado.`), 'success')
  } catch {
    if (token === auth.token) showToast(uiText(`Erro ao inativar cliente.`), 'error')
  }
}

function showToast(message: string, type: string) {
  toast.value = { message, type }
  setTimeout(() => toast.value = null, 3000)
}

onMounted(() => reload())
onUnmounted(() => { requestVersion++; if (searchTimer) clearTimeout(searchTimer) })
</script>

<style scoped>
.clientes-view { min-height: 100vh; background: #f9fafb; }
.clientes-view > .erp-module-header { position: sticky; top: 0; z-index: 10; }
.btn { display: flex; align-items: center; gap: .4rem; padding: .45rem .9rem; border-radius: 8px; font-size: .875rem; cursor: pointer; border: none; font-weight: 600; }
.btn-primary { background: #3b82f6; color: white; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }

.search-section { padding: 1.2rem 1rem 1rem; max-width: 1040px; margin: 0 auto; }
.search-box { position: relative; margin-bottom: .6rem; }
.search-icon { position: absolute; left: .75rem; top: 50%; transform: translateY(-50%); color: #9ca3af; width: 1rem; height: 1rem; }
.search-input { width: 100%; padding: .6rem .75rem .6rem 2.25rem; border: 1px solid #d1d5db; border-radius: 8px; font-size: .875rem; outline: none; box-sizing: border-box; }
.filter-row { display: flex; flex-wrap: wrap; align-items: center; gap: .6rem; }
.chip { padding: .25rem .75rem; border-radius: 20px; font-size: .78rem; font-weight: 600; cursor: pointer; border: 1px solid #d1d5db; background: white; color: #6b7280; }
.chip.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.total-count { font-size: .76rem; color: #64748b; white-space: nowrap; }

.loading-state, .empty-state { display: flex; flex-direction: column; align-items: center; gap: .75rem; padding: 3rem 1rem; color: #9ca3af; }
.spinner { width: 32px; height: 32px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin .7s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

.clientes-list { padding: .3rem 1rem 2rem; max-width: 1040px; margin: 0 auto; display: flex; flex-direction: column; gap: .85rem; }
.customer-sort { width: 210px; margin-left: auto; max-width: 100%; }
.customer-selection { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .7rem; margin-top: .9rem; padding: .8rem; background: #eff6ff; border: 1px solid #c7dbf8; border-radius: 12px; }
.customer-selection strong { color: #1d4ed8; font-size: .8rem; }
.customer-selection p { margin: .25rem 0 0; color: #64748b; font-size: .73rem; line-height: 1.5; }
.customer-selection-actions { display: flex; gap: .4rem; flex-wrap: wrap; }
.customer-selection .customer-selection-limit { width: 100%; color: #92400e; }
/* ─── Misc ─────────────────────────────────────────── */
.customer-pagination { display: flex; align-items: center; justify-content: center; gap: 1rem; padding: 0 1rem 2rem; color: #6b7280; font-size: .8rem; }

.toast { position: fixed; bottom: 1.5rem; right: 1.5rem; padding: .7rem 1.2rem; border-radius: 8px; font-size: .85rem; font-weight: 600; z-index: 9999; box-shadow: 0 4px 12px rgba(0,0,0,.15); }
.toast-success { background: #10b981; color: white; }
.toast-error { background: #ef4444; color: white; }
.toast-enter-active, .toast-leave-active { transition: all .25s; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }

@media (max-width: 600px) {
  .btn { padding: .35rem .65rem; font-size: .75rem; }
  .customer-sort { width: 100%; order: 2; }
  .total-count { margin-left: auto; }
  .clientes-list { padding-left: .7rem; padding-right: .7rem; }
}
</style>
