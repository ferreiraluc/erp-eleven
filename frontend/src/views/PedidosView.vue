<template>
  <div class="pedidos-view">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="header-left">
          <div class="header-top">
            <button @click="$router.back()" class="back-button">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <h1 class="page-title">Pedidos</h1>
          </div>
          <p class="page-subtitle">Gerencie todos os pedidos da loja</p>
        </div>
        <div class="header-right">
          <button @click="openCreateModal" class="btn btn-primary">
            <svg class="btn-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Novo Pedido
          </button>
        </div>
      </div>
    </header>

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
            placeholder="Buscar por número, cliente ou cidade..."
            class="search-input"
          />
        </div>

        <!-- Status Filter -->
        <div class="filter-group">
          <label class="filter-label">Status</label>
          <select v-model="statusFilter" class="filter-select">
            <option value="">Todos</option>
            <option value="PENDENTE">Pendente</option>
            <option value="PROCESSANDO">Processando</option>
            <option value="ENVIADO">Enviado</option>
            <option value="ENTREGUE">Entregue</option>
            <option value="CANCELADO">Cancelado</option>
          </select>
        </div>

        <!-- Tag Filter -->
        <div class="filter-group">
          <label class="filter-label">Tag</label>
          <select v-model="tagFilter" class="filter-select">
            <option value="">Todas</option>
            <option v-for="tag in tags" :key="tag.id" :value="tag.id">
              {{ tag.nome }}
            </option>
          </select>
        </div>

        <!-- View Toggle -->
        <div class="view-toggle">
          <button
            @click="viewMode = 'list'"
            :class="['toggle-btn', { active: viewMode === 'list' }]"
          >
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16" />
            </svg>
            Lista
          </button>
          <button
            @click="viewMode = 'cards'"
            :class="['toggle-btn', { active: viewMode === 'cards' }]"
          >
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
            </svg>
            Cards
          </button>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="loading-container">
      <div class="loading-spinner"></div>
      <p>Carregando pedidos...</p>
    </div>

    <!-- No Results -->
    <div v-else-if="filteredPedidos.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0H4m16 0l-2-2m0 0l-2 2m2-2v4" />
        </svg>
      </div>
      <h3>Nenhum pedido encontrado</h3>
      <p>Não há pedidos que correspondam aos filtros selecionados</p>
      <button @click="clearFilters" class="btn btn-secondary">
        Limpar Filtros
      </button>
    </div>

    <!-- Pedidos List -->
    <div v-else class="pedidos-container">
      <!-- List View -->
      <div v-if="viewMode === 'list'" class="pedidos-list">
        <div class="list-header">
          <div class="col col-number">Número</div>
          <div class="col col-cliente">Cliente</div>
          <div class="col col-status">Status</div>
          <div class="col col-tags">Tags</div>
          <div class="col col-data">Data</div>
          <div class="col col-actions">Ações</div>
        </div>

        <div
          v-for="pedido in filteredPedidos"
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
              <span class="cliente-cidade" v-if="pedido.endereco_cidade">{{ pedido.endereco_cidade }}, {{ pedido.endereco_uf }}</span>
            </div>
          </div>
          <div class="col col-status">
            <span :class="['status-badge', getStatusClass(pedido.status)]">
              {{ getStatusLabel(pedido.status) }}
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
              class="action-btn edit-btn"
              title="Editar"
            >
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            <button
              @click.stop="createRastreamento(pedido)"
              class="action-btn track-btn"
              title="Rastreamento"
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
        <PedidoCard
          v-for="pedido in filteredPedidos"
          :key="pedido.id"
          :pedido="pedido"
          @edit="openEditModal"
          @view="openDetailsModal"
          @track="createRastreamento"
        />
      </div>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="pagination">
        <button
          @click="previousPage"
          :disabled="currentPage === 1"
          class="pagination-btn"
        >
          Anterior
        </button>

        <span class="pagination-info">
          Página {{ currentPage }} de {{ totalPages }}
        </span>

        <button
          @click="nextPage"
          :disabled="currentPage === totalPages"
          class="pagination-btn"
        >
          Próxima
        </button>
      </div>
    </div>

    <!-- Modals -->
    <PedidoModal
      :is-visible="showCreateModal"
      :pedido="editingPedido"
      @close="closeModals"
      @saved="handlePedidoSaved"
    />

    <PedidoDetailsModal
      v-if="showDetailsModal"
      :pedido="selectedPedido"
      @close="closeDetailsModal"
      @edit="openEditModal"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import PedidoCard from '@/components/PedidoCard.vue'
import PedidoModal from '@/components/PedidoModal.vue'
import PedidoDetailsModal from '@/components/PedidoDetailsModal.vue'
import { pedidosAPI, tagsAPI, type Pedido, type Tag } from '@/services/api'

// State
const router = useRouter()
const pedidos = ref<Pedido[]>([])
const tags = ref<Tag[]>([])
const isLoading = ref(true)
const searchQuery = ref('')
const statusFilter = ref('')
const tagFilter = ref('')
const viewMode = ref<'list' | 'cards'>('list')
const currentPage = ref(1)
const itemsPerPage = 20

// Modal state
const showCreateModal = ref(false)
const showDetailsModal = ref(false)
const editingPedido = ref<Pedido | null>(null)
const selectedPedido = ref<Pedido | null>(null)

// Computed
const filteredPedidos = computed(() => {
  let filtered = pedidos.value

  // Search filter
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(pedido =>
      pedido.numero_pedido.toLowerCase().includes(query) ||
      pedido.cliente_nome.toLowerCase().includes(query) ||
      pedido.endereco_cidade.toLowerCase().includes(query)
    )
  }

  // Status filter
  if (statusFilter.value) {
    filtered = filtered.filter(pedido => pedido.status === statusFilter.value)
  }

  // Tag filter
  if (tagFilter.value) {
    filtered = filtered.filter(pedido =>
      pedido.tags.some(tag => tag.id === tagFilter.value)
    )
  }

  return filtered
})

const totalPages = computed(() => Math.ceil(filteredPedidos.value.length / itemsPerPage))

// Methods
const loadPedidos = async () => {
  try {
    isLoading.value = true

    const params: any = {}

    if (statusFilter.value) params.status = statusFilter.value
    if (tagFilter.value) params.tag_id = tagFilter.value

    pedidos.value = await pedidosAPI.getAll(params)
  } catch (error) {
    console.error('Erro ao carregar pedidos:', error)
    pedidos.value = []
  } finally {
    isLoading.value = false
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
  return new Date(dateString).toLocaleDateString('pt-BR')
}

const getStatusLabel = (status: string) => {
  const labels: Record<string, string> = {
    'PENDENTE': 'Pendente',
    'PROCESSANDO': 'Processando',
    'ENVIADO': 'Enviado',
    'ENTREGUE': 'Entregue',
    'CANCELADO': 'Cancelado'
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
}

const openCreateModal = () => {
  editingPedido.value = null
  showCreateModal.value = true
}

const openEditModal = (pedido: Pedido) => {
  editingPedido.value = pedido
  showCreateModal.value = true
}

const openDetailsModal = (pedido: Pedido) => {
  selectedPedido.value = pedido
  showDetailsModal.value = true
}

const closeModals = () => {
  showCreateModal.value = false
  editingPedido.value = null
}

const closeDetailsModal = () => {
  showDetailsModal.value = false
  selectedPedido.value = null
}

const handlePedidoSaved = async (pedido: Pedido) => {
  // Refresh the list
  await loadPedidos()
}

const createRastreamento = async (pedido: Pedido) => {
  if (!pedido.codigo_rastreio) {
    // Se não tem código de rastreio, vai para página de rastreamentos para criar novo
    router.push({
      name: 'rastreamento',
      query: { pedido_id: pedido.id }
    })
    return
  }

  try {
    // Verificar se já existe rastreamento para este código
    const resultado = await pedidosAPI.verificarRastreamento(pedido.codigo_rastreio)

    if (resultado.exists && resultado.rastreamento_id) {
      // Se existe, navegar diretamente para o rastreamento existente
      router.push({
        name: 'rastreamento-detalhes',
        params: { id: resultado.rastreamento_id }
      })
    } else {
      // Se não existe, criar novo rastreamento
      router.push({
        name: 'rastreamento',
        query: {
          pedido_id: pedido.id,
          codigo_rastreio: pedido.codigo_rastreio
        }
      })
    }
  } catch (error) {
    console.error('Erro ao verificar rastreamento:', error)
    // Em caso de erro, ir para página de rastreamentos
    router.push({
      name: 'rastreamento',
      query: { pedido_id: pedido.id }
    })
  }
}

const previousPage = () => {
  if (currentPage.value > 1) {
    currentPage.value--
  }
}

const nextPage = () => {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
  }
}

// Watchers
watch([statusFilter, tagFilter], () => {
  currentPage.value = 1
  loadPedidos()
})

watch(searchQuery, () => {
  currentPage.value = 1
})

// Lifecycle
onMounted(async () => {
  await Promise.all([loadPedidos(), loadTags()])
})
</script>

<style scoped>
.pedidos-view {
  padding: 1.5rem;
  background-color: #f9fafb;
  min-height: 100vh;
}

.page-header {
  background-color: white;
  border-radius: 0.75rem;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-top {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.5rem;
  height: 2.5rem;
  background-color: #f3f4f6;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s;
}

.back-button:hover {
  background-color: #e5e7eb;
  border-color: #9ca3af;
}

.back-button svg {
  width: 1.25rem;
  height: 1.25rem;
}

.page-title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 600;
  color: #111827;
}

.page-subtitle {
  margin: 0;
  color: #6b7280;
  font-size: 0.875rem;
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
</style>