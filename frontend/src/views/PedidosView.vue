<template>
  <div class="pedidos-view">
    <!-- Header -->
    <ModuleHeader :title="$tr('Pedidos')">
      <button @click="openReservationEditor()" class="btn btn-primary erp-button erp-button--primary">
        <svg class="btn-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        {{ $tr("Separar produtos") }}
      </button>
      <button @click="openCreateModal" class="erp-button erp-button--ghost legacy-create">{{ $tr('Pedido sem reserva') }}</button>
      <button v-if="auth.isOwner" class="erp-button erp-button--ghost legacy-create" @click="showArchive = true">{{ $tr('Arquivar anteriores') }}</button>
    </ModuleHeader>

    <div class="reservation-intro"><ShoppingBag :size="19" /><p><strong>{{ $tr('Cada peça no lugar certo.') }}</strong> {{ $tr('Separe para um cliente, acompanhe os pagamentos e conclua a venda pelo PDV.') }}</p></div>

    <!-- Filters and Controls -->
    <div class="filters-section">
      <div class="filters-row">
        <!-- Search -->
        <div class="search-box">
          <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            v-model="searchQuery"
            type="text"
            :placeholder='$tr("Buscar por número, cliente ou cidade...")'
            class="search-input"
          />
        </div>

        <!-- Status Filter -->
        <div class="filter-group">
          <label class="filter-label">{{ $tr('Separação') }}</label>
          <ErpSelect :label="$tr('Separação')" v-model="commerceFilter" class="filter-select">
            <option value="">{{ $tr('Todos os pedidos') }}</option>
            <option value="reserved">{{ $tr('Separados') }}</option>
            <option value="conditional">{{ $tr('Condicionais pendentes') }}</option>
            <option value="returned">{{ $tr('Condicionais devolvidas') }}</option>
            <option value="completed">{{ $tr('Vendas concluídas') }}</option>
            <option value="cancelled">{{ $tr('Reservas canceladas') }}</option>
            <option value="legacy">{{ $tr('Sem reserva de estoque') }}</option>
          </ErpSelect>
        </div>
        <div class="filter-group">
          <label class="filter-label">{{ $tr("Status") }}</label>
          <ErpSelect :label="($tr('Status'))" v-model="statusFilter" class="filter-select">
            <option value="">{{ $tr("Todos") }}</option>
            <option value="PENDENTE">{{ $tr("Pendente") }}</option>
            <option value="PROCESSANDO">{{ $tr("Processando") }}</option>
            <option value="ENVIADO">{{ $tr("Enviado") }}</option>
            <option value="ENTREGUE">{{ $tr("Entregue") }}</option>
            <option value="CANCELADO">{{ $tr("Cancelado") }}</option>
          </ErpSelect>
        </div>

        <div class="filter-group">
          <label class="filter-label">{{ $tr('Listagem') }}</label>
          <ErpSelect :label="$tr('Listagem')" v-model="listing" class="filter-select">
            <option value="current">{{ $tr('Pedidos atuais') }}</option><option value="archived">{{ $tr('Arquivo de pedidos') }}</option><option value="all">{{ $tr('Atuais e arquivados') }}</option>
          </ErpSelect>
        </div>
        <!-- Tag Filter -->
        <div class="filter-group">
          <label class="filter-label">{{ $tr("Tag") }}</label>
          <ErpSelect :label="($tr('Tag'))" v-model="tagFilter" class="filter-select">
            <option value="">{{ $tr("Todas") }}</option>
            <option v-for="tag in tags" :key="tag.id" :value="tag.id">
              {{ tag.nome }}
            </option>
          </ErpSelect>
        </div>

        <!-- View Toggle -->
        <div class="view-toggle">
          <button class="erp-control"
            @click="viewMode = 'list'"
            :class="['toggle-btn', { active: viewMode === 'list' }]"
          >
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            {{ $tr("Lista") }}
          </button>
          <button class="erp-control"
            @click="viewMode = 'cards'"
            :class="['toggle-btn', { active: viewMode === 'cards' }]"
          >
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            {{ $tr("Cards") }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="linkedOrderError" class="empty-state" role="alert">
      <p>{{ $tr("Não foi possível abrir o pedido solicitado.") }}</p>
      <button type="button" class="erp-button erp-button--secondary" @click="loadLinkedOrder">
        {{ $tr("Tentar novamente") }}
      </button>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>{{ $tr("Carregando pedidos...") }}</p>
    </div>

    <!-- No Results -->
    <div v-else-if="loadError" class="empty-state" role="alert">
      <p>{{ $tr("Não foi possível carregar os pedidos.") }}</p>
      <button type="button" class="erp-button erp-button--secondary" @click="loadPedidos">
        {{ $tr("Tentar novamente") }}
      </button>
    </div>
    <div v-else-if="pedidos.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0H4m16 0l-2-2m0 0l-2 2m2-2v4" />
        </svg>
      </div>
      <h3>{{ $tr("Nenhum pedido encontrado") }}</h3>
      <p>{{ $tr("Não há pedidos que correspondam aos filtros selecionados") }}</p>
      <button @click="clearFilters" class="btn btn-secondary erp-button erp-button--secondary">
        {{ $tr("Limpar Filtros") }}
      </button>
    </div>

    <!-- Pedidos List -->
    <div v-else class="pedidos-container">
      <!-- List View -->
      <div v-if="viewMode === 'list'" class="pedidos-list">
        <div class="list-header">
          <div class="col col-number">{{ $tr("Número") }}</div>
          <div class="col col-cliente">{{ $tr("Cliente") }}</div>
          <div class="col col-status">{{ $tr("Status") }}</div>
          <div class="col col-tags">{{ $tr("Tags") }}</div>
          <div class="col col-data">{{ $tr("Data") }}</div>
          <div class="col col-actions">{{ $tr("Ações") }}</div>
        </div>

        <div
          v-for="pedido in pedidos"
          :key="pedido.id"
          class="list-item"
          @click="openDetailsModal(pedido)"
        >
          <div class="col col-number">
            <span class="number-badge">{{ pedido.numero_pedido }}</span>
          </div>
          <div class="col col-cliente">
            <div class="cliente-info">
              <span class="cliente-nome">{{ pedido.cliente_nome }}</span>
              <span class="pedido-descricao-lista">{{ pedido.descricao }}</span>
              <span class="cliente-cidade" v-if="pedido.endereco_entrega">{{ pedido.endereco_entrega }}</span>
            </div>
          </div>
          <div class="col col-status">
            <span :class="['status-badge', pedido.commerce_status ? `commerce-${pedido.commerce_status}` : getStatusClass(pedido.status)]">
              {{ pedido.commerce_status ? reservationStatusLabel(pedido.commerce_status, Number(pedido.paid_gs || 0), Math.max(0, Number(pedido.total_gs || 0) - Number(pedido.paid_gs || 0))) : getStatusLabel(pedido.status) }}
            </span>
          </div>
          <div class="col col-tags">
            <div class="tags-container">
              <span
                v-for="tag in pedido.tags"
                :key="tag.id"
                class="tag-badge"
                :style="{ backgroundColor: tag.cor, color: getContrastColor(tag.cor) }"
              >
                {{ tag.nome }}
              </span>
            </div>
          </div>
          <div class="col col-data">
            {{ formatDate(pedido.created_at) }}
          </div>
          <div class="col col-actions">
            <button
              @click.stop="openEditModal(pedido)"
              class="action-btn edit-btn erp-button erp-button--ghost erp-button--icon"
              :title='$tr("Editar")'
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              @click.stop="createRastreamento(pedido)"
              class="action-btn track-btn erp-button erp-button--ghost erp-button--icon"
              :title='$tr("Rastreamento")'
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      <!-- Cards View -->
      <div v-else class="pedidos-cards">
        <template v-for="pedido in pedidos" :key="pedido.id">
          <ReservationCard v-if="pedido.commerce_status" :pedido="pedido" @view="openDetailsModal" />
          <PedidoCard v-else :pedido="pedido" @edit="openEditModal" @view="openDetailsModal" @track="createRastreamento" />
        </template>
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="pagination">
        <button
          @click="previousPage"
          :disabled="currentPage === 1"
          class="pagination-btn erp-button erp-button--secondary erp-button--sm"
        >
          {{ $tr("Anterior") }}
        </button>

        <span class="pagination-info">
          {{ $tr("Página") }} {{ currentPage }} {{ $tr("de") }} {{ totalPages }}
        </span>

        <button
          @click="nextPage"
          :disabled="currentPage === totalPages"
          class="pagination-btn erp-button erp-button--secondary erp-button--sm"
        >
          {{ $tr("Próxima") }}
        </button>
      </div>
    </div>

    <OrderArchiveDialog v-if="showArchive && auth.isOwner" @close="showArchive = false" @archived="onArchived" />
    <!-- Modals -->
    <PedidoModal
      :is-visible="showCreateModal"
      :pedido="editingPedido"
      @close="closeModals"
      @saved="handlePedidoSaved"
    />

    <PedidoDetailsModal
      v-if="showDetailsModal && selectedPedido"
      :pedido="selectedPedido"
      @close="closeDetailsModal"
      @edit="openLogisticsEdit"
      @updated="selectedPedido = $event; handlePedidoSaved()"
    />
    <OrderReservationEditor v-if="showReservationEditor" :order-id="reservationEditingId || undefined" @close="closeReservationEditor" @saved="onReservationSaved" />
    <OrderReservationDetails v-if="reservationDetailsId" :key="reservationDetailsId" :order-id="reservationDetailsId" @close="reservationDetailsId = null" @edit="openReservationEditor" @updated="onReservationUpdated" @logistics="openReservationLogistics" />
  </div>
</template>

<script setup lang="ts">
import { formatDate as businessDate } from '@/utils/datetime'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { ShoppingBag } from 'lucide-vue-next'
import { uiText } from '@/i18n/uiText'
import { ref, onMounted, onBeforeUnmount, computed, watch, defineAsyncComponent } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import PedidoCard from '@/components/PedidoCard.vue'
import PedidoModal from '@/components/PedidoModal.vue'
import PedidoDetailsModal from '@/components/PedidoDetailsModal.vue'
import { pedidosAPI, tagsAPI, type Pedido, type Tag } from '@/services/api'
import ReservationCard from '@/components/orders/ReservationCard.vue'
import { reservationStatusLabel, type ReservationDetail } from '@/services/orderReservations'
const OrderReservationEditor = defineAsyncComponent(() => import('@/components/orders/OrderReservationEditor.vue'))
const OrderReservationDetails = defineAsyncComponent(() => import('@/components/orders/OrderReservationDetails.vue'))

import { useAuthStore } from '@/stores/auth'
const OrderArchiveDialog = defineAsyncComponent(() => import('@/components/orders/OrderArchiveDialog.vue'))
const auth = useAuthStore(), showArchive = ref(false), listing = ref<'current' | 'archived' | 'all'>('current')
function onArchived() { showArchive.value = false; listing.value = 'current'; currentPage.value = 1; void loadPedidos() }

import { orderTrackingLocation } from '@/services/orderNavigation'

// State
const router = useRouter()
const route = useRoute()
const pedidos = ref<Pedido[]>([])
const tags = ref<Tag[]>([])
const isLoading = ref(true)
const loadError = ref(false)
const linkedOrderError = ref(false)
let linkedRequest = 0
const totalItems = ref(0)
let requestVersion = 0
let searchTimer: ReturnType<typeof setTimeout> | undefined
const searchQuery = ref(typeof route.query.q === 'string' ? route.query.q : '')
const statusFilter = ref('')
const tagFilter = ref('')
const commerceFilter = ref('')
const viewMode = ref<'list' | 'cards'>('cards')
const currentPage = ref(1)
const itemsPerPage = 20

// Modal state
const showCreateModal = ref(false)
const showDetailsModal = ref(false)
const editingPedido = ref<Pedido | null>(null)
const selectedPedido = ref<Pedido | null>(null)
const showReservationEditor = ref(false)
const reservationEditingId = ref<string | null>(null)
const reservationDetailsId = ref<string | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(totalItems.value / itemsPerPage)))

const loadPedidos = async () => {
  clearTimeout(searchTimer)
  const version = ++requestVersion
  isLoading.value = true
  loadError.value = false
  try {
    const result = await pedidosAPI.getPage({
      page: currentPage.value,
      page_size: itemsPerPage,
      search: searchQuery.value.trim() || undefined,
      status: statusFilter.value || undefined,
      tag_id: tagFilter.value || undefined,
      commerce_status: commerceFilter.value || undefined,
      listing: listing.value,
    })
    if (version !== requestVersion) return
    totalItems.value = result.total
    if (currentPage.value > totalPages.value) {
      currentPage.value = totalPages.value
      await loadPedidos()
      return
    }
    pedidos.value = result.items
  } catch {
    if (version !== requestVersion) return
    loadError.value = true
    pedidos.value = []
  } finally {
    if (version === requestVersion) isLoading.value = false
  }
}

const loadTags = async () => {
  try {
    tags.value = await tagsAPI.getAll()
  } catch (error) {
    console.error('Erro ao carregar tags:', error)
    tags.value = []
  }
}

const formatDate = (dateString: string) => {
  return businessDate(dateString)
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    'PENDENTE': uiText(`Pendente`),
    'PROCESSANDO': uiText(`Processando`),
    'ENVIADO': uiText(`Enviado`),
    'ENTREGUE': uiText(`Entregue`),
    'CANCELADO': uiText(`Cancelado`)
  }
  return labels[status] || status
}

const getStatusClass = (status: string) => {
  const classes: Record<string, string> = {
    'PENDENTE': 'status-pending',
    'PROCESSANDO': 'status-processing',
    'ENVIADO': 'status-shipped',
    'ENTREGUE': 'status-delivered',
    'CANCELADO': 'status-cancelled'
  }
  return classes[status] || 'status-default'
}

const getContrastColor = (backgroundColor: string) => {
  // Simple contrast calculation
  const hex = backgroundColor.replace('#', '')
  const r = parseInt(hex.substr(0, 2), 16)
  const g = parseInt(hex.substr(2, 2), 16)
  const b = parseInt(hex.substr(4, 2), 16)
  const brightness = (r * 299 + g * 587 + b * 114) / 1000
  return brightness > 128 ? '#000000' : '#ffffff'
}

const clearFilters = () => {
  searchQuery.value = ''
  statusFilter.value = ''
  tagFilter.value = ''
  commerceFilter.value = ''
  listing.value = 'current'
}

const openCreateModal = () => {
  editingPedido.value = null
  showCreateModal.value = true
}

const openEditModal = (pedido: Pedido) => {
  if (pedido.commerce_status) { if (pedido.commerce_status === 'reserved' && !pedido.archived_at) openReservationEditor(pedido.id); else reservationDetailsId.value = pedido.id; return }
  showDetailsModal.value = false
  selectedPedido.value = null
  editingPedido.value = pedido
  showCreateModal.value = true
}
const openLogisticsEdit = (pedido: Pedido) => {
  showDetailsModal.value = false; selectedPedido.value = null
  editingPedido.value = pedido; showCreateModal.value = true
}

const openDetailsModal = (pedido: Pedido) => {
  ++linkedRequest
  linkedOrderError.value = false
  if (pedido.commerce_status) { reservationDetailsId.value = pedido.id; return }
  selectedPedido.value = pedido
  showDetailsModal.value = true
}

const closeModals = () => {
  showCreateModal.value = false
  editingPedido.value = null
}

const closeDetailsModal = () => {
  ++linkedRequest
  showDetailsModal.value = false
  selectedPedido.value = null
}

const handlePedidoSaved = async () => {
  // Refresh the list
  await loadPedidos()
}

function openReservationEditor(id?: string) {
  showDetailsModal.value = false; selectedPedido.value = null; reservationDetailsId.value = null
  reservationEditingId.value = id || null; showReservationEditor.value = true
}
function closeReservationEditor() { showReservationEditor.value = false; reservationEditingId.value = null }
async function onReservationSaved(value: ReservationDetail) {
  closeReservationEditor(); reservationDetailsId.value = value.id; await loadPedidos()
}
async function onReservationUpdated() { await loadPedidos() }
async function openReservationLogistics(id: string) {
  const request = ++linkedRequest
  try {
    const pedido = await pedidosAPI.getById(id)
    if (request !== linkedRequest) return
    reservationDetailsId.value = null; selectedPedido.value = pedido; showDetailsModal.value = true
  } catch { if (request === linkedRequest) linkedOrderError.value = true }
}

const createRastreamento = (pedido: Pedido) => router.push(orderTrackingLocation(pedido))

const previousPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
    void loadPedidos()
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    void loadPedidos()
  }
}

// Watchers
watch([statusFilter, tagFilter, commerceFilter, listing], () => {
  currentPage.value = 1
  loadPedidos()
})

watch(searchQuery, () => {
  currentPage.value = 1
  ++requestVersion // Invalidate in-flight results while waiting for debounce.
  isLoading.value = true
  clearTimeout(searchTimer)
  searchTimer = setTimeout(loadPedidos, 300)
})

onBeforeUnmount(() => { ++requestVersion; ++linkedRequest; clearTimeout(searchTimer) })

async function loadLinkedOrder() {
  const request = ++linkedRequest
  linkedOrderError.value = false
  const id = route.query.pedido_id
  if (typeof id !== 'string' || !id) return
  try {
    const pedido = pedidos.value.find(p => p.id === id) || await pedidosAPI.getById(id)
    if (request === linkedRequest) openDetailsModal(pedido)
  } catch {
    if (request === linkedRequest) linkedOrderError.value = true
  }
}
watch(() => route.query.pedido_id, loadLinkedOrder, { immediate: true })
watch(() => route.query.q, value => { if (typeof value === 'string') searchQuery.value = value })
onMounted(() => { void loadPedidos(); void loadTags() })
</script>

<style scoped>
.pedidos-view {
  padding: 1.5rem;
  background-color: #f9fafb;
  min-height: 100vh;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn-primary {
  background-color: #2563eb;
  color: white;
}

.btn-primary:hover {
  background-color: #1d4ed8;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover {
  background-color: #e5e7eb;
}

.btn-icon {
  width: 1rem;
  height: 1rem;
}

.filters-section {
  background-color: white;
  border-radius: 0.75rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.filters-row {
  display: flex;
  gap: 1rem;
  align-items: end;
  flex-wrap: wrap;
}

.search-box {
  position: relative;
  flex: 1;
  min-width: 300px;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  width: 1rem;
  height: 1rem;
  color: #6b7280;
}

.search-input {
  width: 100%;
  padding: 0.75rem 0.75rem 0.75rem 2.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
}

.search-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.filter-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: #374151;
}

.filter-select {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  min-width: 120px;
}

.filter-select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.view-toggle {
  display: flex;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  overflow: hidden;
}

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  background-color: white;
  border: none;
  cursor: pointer;
  font-size: 0.875rem;
  color: #6b7280;
  transition: all 0.2s;
}

.toggle-btn svg {
  width: 1rem;
  height: 1rem;
}

.toggle-btn.active {
  background-color: #2563eb;
  color: white;
}

.toggle-btn:hover:not(.active) {
  background-color: #f3f4f6;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
}

.loading-spinner {
  width: 2rem;
  height: 2rem;
  border: 2px solid #e5e7eb;
  border-top: 2px solid #2563eb;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 1rem;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  text-align: center;
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.empty-icon svg {
  width: 3rem;
  height: 3rem;
  color: #9ca3af;
  margin-bottom: 1rem;
}

.empty-state h3 {
  margin: 0 0 0.5rem 0;
  color: #374151;
  font-size: 1.125rem;
}

.empty-state p {
  margin: 0 0 1.5rem 0;
  color: #6b7280;
}

.pedidos-container {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

/* List View Styles */
.pedidos-list {
  width: 100%;
}

.list-header {
  display: grid;
  grid-template-columns: 120px 1fr 120px 200px 100px 100px;
  gap: 1rem;
  padding: 1rem 1.5rem;
  background-color: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
  font-size: 0.75rem;
  font-weight: 600;
  color: #374151;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.list-item {
  display: grid;
  grid-template-columns: 120px 1fr 120px 200px 100px 100px;
  gap: 1rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid #f3f4f6;
  cursor: pointer;
  transition: background-color 0.2s;
}

.list-item:hover {
  background-color: #f9fafb;
}

.list-item:last-child {
  border-bottom: none;
}

.col {
  display: flex;
  align-items: center;
}

.number-badge {
  padding: 0.25rem 0.5rem;
  background-color: #eff6ff;
  color: #2563eb;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 600;
}

.cliente-info {
  display: flex;
  flex-direction: column;
}

.cliente-nome {
  font-weight: 500;
  color: #111827;
}

.pedido-descricao-lista {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 400;
}

.cliente-cidade {
  font-size: 0.75rem;
  color: #6b7280;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-pending {
  background-color: #fef3c7;
  color: #92400e;
}

.status-processing {
  background-color: #dbeafe;
  color: #1e40af;
}

.status-shipped {
  background-color: #fed7aa;
  color: #c2410c;
}

.status-delivered {
  background-color: #dcfce7;
  color: #166534;
}

.status-cancelled {
  background-color: #fee2e2;
  color: #dc2626;
}

.tags-container {
  display: flex;
  gap: 0.25rem;
  flex-wrap: wrap;
}

.tag-badge {
  padding: 0.125rem 0.5rem;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
}

.col-actions {
  gap: 0.5rem;
}

.action-btn {
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 0.375rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.action-btn svg {
  width: 1rem;
  height: 1rem;
}

.edit-btn {
  background-color: #eff6ff;
  color: #2563eb;
}

.edit-btn:hover {
  background-color: #dbeafe;
}

.track-btn {
  background-color: #f0fdf4;
  color: #16a34a;
}

.track-btn:hover {
  background-color: #dcfce7;
}

/* Cards View Styles */
.pedidos-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  padding: 1.5rem;
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 1rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
}

.pagination-btn {
  padding: 0.5rem 1rem;
  background-color: white;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  cursor: pointer;
  font-size: 0.875rem;
  transition: all 0.2s;
}

.pagination-btn:hover:not(:disabled) {
  background-color: #f3f4f6;
}

.pagination-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pagination-info {
  font-size: 0.875rem;
  color: #6b7280;
}

/* Responsive */
@media (max-width: 1024px) {
  .list-header,
  .list-item {
    grid-template-columns: 100px 1fr 100px 150px 80px;
    font-size: 0.75rem;
  }

  .col-data {
    display: none;
  }
}

@media (max-width: 768px) {
  .pedidos-view {
    padding: 1rem;
  }

  .filters-row {
    flex-direction: column;
    align-items: stretch;
  }

  .search-box {
    min-width: unset;
  }

  .view-toggle {
    align-self: center;
  }

  .list-header,
  .list-item {
    grid-template-columns: 1fr 100px 60px;
    gap: 0.5rem;
    padding: 0.75rem;
  }

  .col-status,
  .col-tags {
    display: none;
  }

  .pedidos-cards {
    grid-template-columns: 1fr;
    padding: 1rem;
  }
}
.reservation-intro{display:flex;gap:9px;align-items:center;padding:0 0 18px;color:#64748b;font-size:.8rem;line-height:1.6}.reservation-intro>svg{flex-shrink:0;color:#3b82f6}.reservation-intro p{margin:0}.reservation-intro strong{color:#334155}.filters-section{border:1px solid #e2e8f0;border-radius:16px;box-shadow:none;padding:16px;margin-bottom:16px}.filters-row{gap:12px}.search-input{box-sizing:border-box;border-color:#dbe3ee;border-radius:11px}.filter-select{padding:0;border:0;background:transparent}.filter-label{color:#64748b}.pedidos-container{background:transparent;box-shadow:none;overflow:visible}.pedidos-list{background:white;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden}.pedidos-cards{padding:0;gap:16px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));align-items:start}.view-toggle{border-color:#e2e8f0;border-radius:11px}.toggle-btn{padding:10px}.toggle-btn.active{background:#eff6ff;color:#2563eb}.commerce-reserved{color:#9a3412;background:#fff7ed}.commerce-completed{color:#047857;background:#ecfdf5}.commerce-cancelled{color:#64748b;background:#f1f5f9}.pagination{border:0;padding-top:22px}.legacy-create{font-size:.76rem;color:#64748b}
@media(max-width:768px){.pedidos-view{padding:12px}.filters-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.search-box{grid-column:1/-1}.search-input{font-size:16px}.view-toggle{align-self:end;justify-self:end}.filter-group{min-width:0}.filter-select{min-width:0}.pedidos-cards{grid-template-columns:1fr;padding:0;gap:12px}.reservation-intro{font-size:.73rem;padding:4px 2px 14px}.reservation-intro strong{display:block}.filters-section{padding:13px}.legacy-create{padding:8px!important;font-size:.68rem}.filter-label{font-size:.69rem}}
</style>
