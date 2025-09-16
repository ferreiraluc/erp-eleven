<template>
  <div class="vendas-view">
    <!-- Header -->
    <div class="page-header">
      <div class="header-content">
        <div class="title-section">
          <h1>💰 Vendas</h1>
          <p class="subtitle">Gerencie e visualize todas as vendas do sistema</p>
        </div>
        <div class="action-buttons">
          <button @click="showImportModal = true" class="btn-primary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
            </svg>
            Importar Vendas
          </button>
          <button @click="showAddModal = true" class="btn-secondary">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6"/>
            </svg>
            Nova Venda
          </button>
        </div>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon success">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.total_vendas || 0 }}</div>
          <div class="stat-label">Total de Vendas</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon warning">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ formatCurrency(stats.valor_total || 0) }}</div>
          <div class="stat-label">Valor Total</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon info">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8 7V3a2 2 0 012-2h4a2 2 0 012 2v4m-6 4h6m0 0a2 2 0 002 2v6a2 2 0 01-2 2H8a2 2 0 01-2-2v-6a2 2 0 012-2z"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.vendas_hoje || 0 }}</div>
          <div class="stat-label">Vendas Hoje</div>
        </div>
      </div>

      <div class="stat-card">
        <div class="stat-icon primary">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"/>
          </svg>
        </div>
        <div class="stat-content">
          <div class="stat-value">{{ stats.vendedores_ativos || 0 }}</div>
          <div class="stat-label">Vendedores Ativos</div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filters-section">
      <div class="filters-grid">
        <div class="filter-group">
          <label>🔍 Buscar</label>
          <input 
            v-model="filters.search" 
            type="text" 
            placeholder="Vendedor, produto, etc..."
            class="filter-input"
          >
        </div>
        
        <div class="filter-group">
          <label>👤 Vendedor</label>
          <select v-model="filters.vendedor" class="filter-select">
            <option value="">Todos os vendedores</option>
            <option v-for="vendedor in vendedores" :key="vendedor.id" :value="vendedor.id">
              {{ vendedor.nome }}
            </option>
          </select>
        </div>

        <div class="filter-group">
          <label>💰 Moeda</label>
          <select v-model="filters.moeda" class="filter-select">
            <option value="">Todas as moedas</option>
            <option value="G$">G$ (Guaranis)</option>
            <option value="R$">R$ (Reais)</option>
            <option value="U$">U$ (Dólares)</option>
            <option value="EUR">EUR (Euros)</option>
          </select>
        </div>

        <div class="filter-group">
          <label>📅 Período</label>
          <select v-model="filters.periodo" class="filter-select">
            <option value="">Todos os períodos</option>
            <option value="hoje">Hoje</option>
            <option value="semana">Esta semana</option>
            <option value="mes">Este mês</option>
            <option value="ano">Este ano</option>
          </select>
        </div>

        <div class="filter-actions">
          <button @click="applyFilters" class="btn-primary">Filtrar</button>
          <button @click="clearFilters" class="btn-ghost">Limpar</button>
        </div>
      </div>
    </div>

    <!-- Sales Table -->
    <div class="table-section">
      <div class="table-header">
        <h2>📊 Lista de Vendas</h2>
        <div class="table-actions">
          <button @click="exportVendas" class="btn-ghost">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 10v6m0 0l-3-3m3 3l3-3M3 17V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v10a2 2 0 01-2 2H5a2 2 0 01-2-2z"/>
            </svg>
            Exportar
          </button>
        </div>
      </div>

      <div class="table-container">
        <table class="sales-table" v-if="filteredVendas.length > 0">
          <thead>
            <tr>
              <th @click="sortBy('data_venda')" class="sortable">
                📅 Data
                <span v-if="sortField === 'data_venda'" class="sort-indicator">
                  {{ sortDirection === 'asc' ? '↑' : '↓' }}
                </span>
              </th>
              <th @click="sortBy('vendedor_nome')" class="sortable">
                👤 Vendedor
                <span v-if="sortField === 'vendedor_nome'" class="sort-indicator">
                  {{ sortDirection === 'asc' ? '↑' : '↓' }}
                </span>
              </th>
              <th @click="sortBy('valor_bruto')" class="sortable">
                💰 Valor
                <span v-if="sortField === 'valor_bruto'" class="sort-indicator">
                  {{ sortDirection === 'asc' ? '↑' : '↓' }}
                </span>
              </th>
              <th>🏦 Moeda</th>
              <th>💳 Pagamento</th>
              <th>📦 Produto</th>
              <th class="actions-column">Ações</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="venda in paginatedVendas" :key="venda.id" class="table-row">
              <td>{{ formatDate(venda.data_venda) }}</td>
              <td>
                <div class="vendedor-cell">
                  <div class="vendedor-avatar">{{ venda.vendedor_nome.charAt(0) }}</div>
                  <span>{{ venda.vendedor_nome }}</span>
                </div>
              </td>
              <td class="valor-cell">{{ formatCurrency(venda.valor_bruto) }}</td>
              <td>
                <span class="moeda-tag" :class="getMoedaClass(venda.moeda)">
                  {{ venda.moeda }}
                </span>
              </td>
              <td>
                <span class="pagamento-tag">{{ formatPaymentMethod(venda.metodo_pagamento) }}</span>
              </td>
              <td>
                <span class="produto-desc">{{ venda.descricao_produto || 'N/A' }}</span>
              </td>
              <td class="actions-cell">
                <button @click="editVenda(venda)" class="btn-action edit">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                  </svg>
                </button>
                <button @click="deleteVenda(venda)" class="btn-action delete">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                  </svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Empty State -->
        <div v-else class="empty-state">
          <div class="empty-icon">📊</div>
          <h3>Nenhuma venda encontrada</h3>
          <p>{{ hasFilters ? 'Tente ajustar os filtros' : 'Comece importando ou criando uma nova venda' }}</p>
          <button @click="hasFilters ? clearFilters() : showImportModal = true" class="btn-primary">
            {{ hasFilters ? 'Limpar Filtros' : 'Importar Vendas' }}
          </button>
        </div>
      </div>

      <!-- Pagination -->
      <div v-if="filteredVendas.length > 0" class="pagination">
        <div class="pagination-info">
          Mostrando {{ startIndex + 1 }}-{{ endIndex }} de {{ filteredVendas.length }} vendas
        </div>
        <div class="pagination-controls">
          <button 
            @click="currentPage--" 
            :disabled="currentPage === 1" 
            class="btn-pagination"
          >
            ← Anterior
          </button>
          
          <span class="page-info">{{ currentPage }} de {{ totalPages }}</span>
          
          <button 
            @click="currentPage++" 
            :disabled="currentPage === totalPages" 
            class="btn-pagination"
          >
            Próxima →
          </button>
        </div>
      </div>
    </div>

    <!-- Import Modal -->
    <div v-if="showImportModal" class="modal-overlay" @click="showImportModal = false">
      <div class="modal" @click.stop>
        <VendasImportCard />
        <div class="modal-actions">
          <button @click="showImportModal = false" class="btn-secondary">Fechar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { salesAPI, vendorsAPI } from '@/services/api'
import VendasImportCard from '@/components/VendasImportCard.vue'

// Estado reativo
const vendas = ref([])
const vendedores = ref([])
const stats = ref({})
const loading = ref(false)
const showImportModal = ref(false)
const showAddModal = ref(false)

// Filtros
const filters = ref({
  search: '',
  vendedor: '',
  moeda: '',
  periodo: ''
})

// Ordenação
const sortField = ref('data_venda')
const sortDirection = ref('desc')

// Paginação
const currentPage = ref(1)
const itemsPerPage = 20

// Computed properties
const hasFilters = computed(() => {
  return filters.value.search || filters.value.vendedor || filters.value.moeda || filters.value.periodo
})

const filteredVendas = computed(() => {
  let result = [...vendas.value]

  // Filtro por busca
  if (filters.value.search) {
    const searchTerm = filters.value.search.toLowerCase()
    result = result.filter(venda =>
      venda.vendedor_nome?.toLowerCase().includes(searchTerm) ||
      venda.descricao_produto?.toLowerCase().includes(searchTerm)
    )
  }

  // Filtro por vendedor
  if (filters.value.vendedor) {
    result = result.filter(venda => venda.vendedor_id === filters.value.vendedor)
  }

  // Filtro por moeda
  if (filters.value.moeda) {
    result = result.filter(venda => venda.moeda === filters.value.moeda)
  }

  // Filtro por período
  if (filters.value.periodo) {
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    
    result = result.filter(venda => {
      const vendaDate = new Date(venda.data_venda)
      
      switch (filters.value.periodo) {
        case 'hoje':
          return vendaDate >= today
        case 'semana':
          const weekStart = new Date(today)
          weekStart.setDate(today.getDate() - 7)
          return vendaDate >= weekStart
        case 'mes':
          return vendaDate.getMonth() === now.getMonth() && vendaDate.getFullYear() === now.getFullYear()
        case 'ano':
          return vendaDate.getFullYear() === now.getFullYear()
        default:
          return true
      }
    })
  }

  // Ordenação
  result.sort((a, b) => {
    const aVal = a[sortField.value]
    const bVal = b[sortField.value]
    
    if (sortDirection.value === 'asc') {
      return aVal < bVal ? -1 : aVal > bVal ? 1 : 0
    } else {
      return aVal > bVal ? -1 : aVal < bVal ? 1 : 0
    }
  })

  return result
})

const totalPages = computed(() => Math.ceil(filteredVendas.value.length / itemsPerPage))
const startIndex = computed(() => (currentPage.value - 1) * itemsPerPage)
const endIndex = computed(() => Math.min(startIndex.value + itemsPerPage, filteredVendas.value.length))

const paginatedVendas = computed(() => 
  filteredVendas.value.slice(startIndex.value, endIndex.value)
)

// Métodos
const loadVendas = async () => {
  try {
    loading.value = true
    const response = await salesAPI.getAll()
    vendas.value = response || []
    updateStats()
  } catch (error) {
    console.error('Erro ao carregar vendas:', error)
  } finally {
    loading.value = false
  }
}

const loadVendedores = async () => {
  try {
    const response = await vendorsAPI.getAll()
    vendedores.value = response || []
  } catch (error) {
    console.error('Erro ao carregar vendedores:', error)
  }
}

const updateStats = () => {
  const today = new Date()
  const todayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate())
  
  stats.value = {
    total_vendas: vendas.value.length,
    valor_total: vendas.value.reduce((sum, venda) => sum + parseFloat(venda.valor_bruto || 0), 0),
    vendas_hoje: vendas.value.filter(venda => new Date(venda.data_venda) >= todayStart).length,
    vendedores_ativos: new Set(vendas.value.map(venda => venda.vendedor_id)).size
  }
}

const sortBy = (field: string) => {
  if (sortField.value === field) {
    sortDirection.value = sortDirection.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDirection.value = 'asc'
  }
}

const applyFilters = () => {
  currentPage.value = 1
}

const clearFilters = () => {
  filters.value = {
    search: '',
    vendedor: '',
    moeda: '',
    periodo: ''
  }
  currentPage.value = 1
}

const editVenda = (venda: any) => {
  // TODO: Implementar edição de venda
  console.log('Editar venda:', venda)
}

const deleteVenda = async (venda: any) => {
  if (confirm('Tem certeza que deseja excluir esta venda?')) {
    try {
      // TODO: Implementar exclusão de venda
      console.log('Excluir venda:', venda)
      await loadVendas()
    } catch (error) {
      console.error('Erro ao excluir venda:', error)
    }
  }
}

const exportVendas = () => {
  // TODO: Implementar exportação
  console.log('Exportar vendas')
}

// Formatação
const formatDate = (dateStr: string) => {
  return new Date(dateStr).toLocaleDateString('pt-BR')
}

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('pt-BR', { 
    minimumFractionDigits: 2,
    maximumFractionDigits: 2 
  }).format(value)
}

const formatPaymentMethod = (method: string) => {
  const methods = {
    'PIX_POWER': 'PIX Power',
    'PIX_THAIS': 'PIX Thais',
    'PIX_MERCADO_PAGO': 'PIX MP',
    'CREDITO': 'Crédito',
    'DEBITO': 'Débito',
    'PY_TRANSFER_SUDAMERIS': 'Transfer Sudameris',
    'PY_TRANSFER_INTERFISA': 'Transfer Interfisa'
  }
  return methods[method] || method
}

const getMoedaClass = (moeda: string) => {
  const classes = {
    'G$': 'moeda-guarani',
    'R$': 'moeda-real',
    'U$': 'moeda-dollar',
    'EUR': 'moeda-euro'
  }
  return classes[moeda] || ''
}

// Lifecycle
onMounted(() => {
  loadVendas()
  loadVendedores()
})
</script>

<style scoped>
.vendas-view {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

/* Page Header */
.page-header {
  margin-bottom: 2rem;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 2rem;
}

.title-section h1 {
  font-size: 2rem;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 0.5rem;
}

.subtitle {
  color: #6b7280;
  font-size: 1rem;
  margin: 0;
}

.action-buttons {
  display: flex;
  gap: 1rem;
}

/* Buttons */
.btn-primary, .btn-secondary, .btn-ghost {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  font-size: 0.875rem;
}

.btn-primary {
  background: #1f2937;
  color: white;
}

.btn-primary:hover {
  background: #374151;
}

.btn-secondary {
  background: #f3f4f6;
  color: #1f2937;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

.btn-ghost {
  background: transparent;
  color: #6b7280;
}

.btn-ghost:hover {
  color: #374151;
  background: #f9fafb;
}

.btn-primary svg, .btn-secondary svg, .btn-ghost svg {
  width: 1rem;
  height: 1rem;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  display: flex;
  align-items: center;
  gap: 1rem;
}

.stat-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg {
  width: 1.5rem;
  height: 1.5rem;
}

.stat-icon.success {
  background: #dcfce7;
  color: #16a34a;
}

.stat-icon.warning {
  background: #fef3c7;
  color: #d97706;
}

.stat-icon.info {
  background: #dbeafe;
  color: #2563eb;
}

.stat-icon.primary {
  background: #f3e8ff;
  color: #7c3aed;
}

.stat-value {
  font-size: 1.875rem;
  font-weight: 700;
  color: #1f2937;
  line-height: 1;
}

.stat-label {
  color: #6b7280;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}

/* Filters */
.filters-section {
  background: white;
  border-radius: 12px;
  padding: 1.5rem;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  margin-bottom: 2rem;
}

.filters-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  align-items: end;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.filter-group label {
  font-weight: 500;
  color: #374151;
  font-size: 0.875rem;
}

.filter-input, .filter-select {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 0.875rem;
  transition: border-color 0.2s;
}

.filter-input:focus, .filter-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
}

/* Table */
.table-section {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  overflow: hidden;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.table-header h2 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}

.table-container {
  overflow-x: auto;
}

.sales-table {
  width: 100%;
  border-collapse: collapse;
}

.sales-table th,
.sales-table td {
  padding: 1rem;
  text-align: left;
  border-bottom: 1px solid #f3f4f6;
}

.sales-table th {
  background: #f9fafb;
  font-weight: 600;
  color: #374151;
  font-size: 0.875rem;
}

.sales-table th.sortable {
  cursor: pointer;
  user-select: none;
  position: relative;
}

.sales-table th.sortable:hover {
  background: #f3f4f6;
}

.sort-indicator {
  margin-left: 0.5rem;
  font-size: 0.75rem;
}

.table-row:hover {
  background: #f9fafb;
}

.vendedor-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.vendedor-avatar {
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
}

.valor-cell {
  font-weight: 600;
  color: #059669;
}

.moeda-tag {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 500;
}

.moeda-guarani {
  background: #dcfce7;
  color: #16a34a;
}

.moeda-real {
  background: #dbeafe;
  color: #2563eb;
}

.moeda-dollar {
  background: #fef3c7;
  color: #d97706;
}

.moeda-euro {
  background: #f3e8ff;
  color: #7c3aed;
}

.pagamento-tag {
  padding: 0.25rem 0.75rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 500;
  background: #f3f4f6;
  color: #374151;
}

.produto-desc {
  color: #6b7280;
  font-size: 0.875rem;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions-cell {
  display: flex;
  gap: 0.5rem;
}

.btn-action {
  padding: 0.5rem;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.btn-action svg {
  width: 1rem;
  height: 1rem;
}

.btn-action.edit {
  background: #dbeafe;
  color: #2563eb;
}

.btn-action.edit:hover {
  background: #bfdbfe;
}

.btn-action.delete {
  background: #fee2e2;
  color: #dc2626;
}

.btn-action.delete:hover {
  background: #fecaca;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 4rem 2rem;
}

.empty-icon {
  font-size: 4rem;
  margin-bottom: 1rem;
}

.empty-state h3 {
  font-size: 1.25rem;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 0.5rem;
}

.empty-state p {
  color: #6b7280;
  margin: 0 0 2rem;
}

/* Pagination */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
}

.pagination-info {
  color: #6b7280;
  font-size: 0.875rem;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.btn-pagination {
  padding: 0.5rem 1rem;
  border: 1px solid #d1d5db;
  background: white;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 0.875rem;
}

.btn-pagination:hover:not(:disabled) {
  background: #f9fafb;
}

.btn-pagination:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-info {
  font-size: 0.875rem;
  color: #374151;
  font-weight: 500;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
  padding: 1rem;
}

.modal {
  background: white;
  border-radius: 12px;
  width: 100%;
  max-width: 800px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-actions {
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  display: flex;
  justify-content: flex-end;
}

/* Responsive */
@media (max-width: 768px) {
  .vendas-view {
    padding: 1rem;
  }

  .header-content {
    flex-direction: column;
    align-items: stretch;
  }

  .action-buttons {
    justify-content: stretch;
  }

  .action-buttons > * {
    flex: 1;
  }

  .stats-grid {
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  }

  .filters-grid {
    grid-template-columns: 1fr;
  }

  .table-header {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }

  .pagination {
    flex-direction: column;
    gap: 1rem;
  }
}
</style>