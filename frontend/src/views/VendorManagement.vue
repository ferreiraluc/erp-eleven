<template>
  <div class="vendor-management">
    <!-- Header -->
    <div class="page-header">
      <div class="header-content">
        <div class="header-title">
          <button @click="goBack" class="back-button">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1>Gerenciar Vendedores</h1>
            <p class="subtitle">Cadastre, edite e gerencie seus vendedores</p>
          </div>
        </div>
        <button @click="openCreateModal" class="create-button">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          Novo Vendedor
        </button>
      </div>
    </div>

    <!-- Content -->
    <div class="page-content">
      <!-- Stats Cards -->
      <div class="stats-row">
        <div class="stat-card">
          <div class="stat-icon active">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ activeVendors }}</span>
            <span class="stat-label">Vendedores Ativos</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon inactive">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728" />
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ inactiveVendors }}</span>
            <span class="stat-label">Vendedores Inativos</span>
          </div>
        </div>
        
        <div class="stat-card">
          <div class="stat-icon total">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
          </div>
          <div class="stat-info">
            <span class="stat-value">{{ totalVendors }}</span>
            <span class="stat-label">Total de Vendedores</span>
          </div>
        </div>
      </div>

      <!-- Filters -->
      <div class="filters-section">
        <div class="filters-group">
          <button 
            @click="setFilter('all')" 
            :class="['filter-button', { active: currentFilter === 'all' }]"
          >
            Todos ({{ totalVendors }})
          </button>
          <button 
            @click="setFilter('active')" 
            :class="['filter-button', { active: currentFilter === 'active' }]"
          >
            Ativos ({{ activeVendors }})
          </button>
          <button 
            @click="setFilter('inactive')" 
            :class="['filter-button', { active: currentFilter === 'inactive' }]"
          >
            Inativos ({{ inactiveVendors }})
          </button>
        </div>
        
        <div class="search-group">
          <div class="search-input">
            <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input 
              v-model="searchQuery"
              type="text"
              placeholder="Pesquisar vendedor..."
            />
          </div>
        </div>
      </div>

      <!-- Vendors Table -->
      <div class="table-section">
        <div v-if="isLoading" class="loading-state">
          <div class="loading-spinner"></div>
          <p>Carregando vendedores...</p>
        </div>
        
        <div v-else-if="filteredVendors.length === 0" class="empty-state">
          <svg class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
          <h3>Nenhum vendedor encontrado</h3>
          <p>{{ currentFilter === 'all' ? 'Cadastre seu primeiro vendedor' : 'Nenhum vendedor corresponde aos filtros aplicados' }}</p>
          <button v-if="currentFilter === 'all'" @click="openCreateModal" class="create-button">
            Cadastrar Vendedor
          </button>
        </div>
        
        <div v-else class="table-container">
          <table class="vendors-table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Taxa de Comissão</th>
                <th>Meta Semanal</th>
                <th>Telefone</th>
                <th>Status</th>
                <th>Criado em</th>
                <th class="actions-column">Ações</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="vendor in filteredVendors" :key="vendor.id" class="vendor-row">
                <td>
                  <div class="vendor-name">
                    <div class="vendor-avatar">
                      {{ vendor.nome.charAt(0).toUpperCase() }}
                    </div>
                    <span>{{ vendor.nome }}</span>
                  </div>
                </td>
                <td>
                  <span class="commission-rate">{{ vendor.taxa_comissao }}%</span>
                </td>
                <td>
                  <span class="weekly-goal">G$ {{ formatCurrency(vendor.meta_semanal) }}</span>
                </td>
                <td>
                  <span class="phone">{{ vendor.telefone || '-' }}</span>
                </td>
                <td>
                  <span :class="['status-badge', vendor.ativo ? 'active' : 'inactive']">
                    {{ vendor.ativo ? 'Ativo' : 'Inativo' }}
                  </span>
                </td>
                <td>
                  <span class="created-date">{{ formatDate(vendor.created_at) }}</span>
                </td>
                <td class="actions-column">
                  <div class="action-buttons">
                    <button @click="editVendor(vendor)" class="action-button edit">
                      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <button 
                      @click="toggleVendorStatus(vendor)" 
                      :class="['action-button', vendor.ativo ? 'deactivate' : 'activate']"
                    >
                      <svg v-if="vendor.ativo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728" />
                      </svg>
                      <svg v-else fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Create/Edit Modal -->
    <div v-if="showModal" class="modal-overlay" @click="closeModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>{{ isEditing ? 'Editar Vendedor' : 'Novo Vendedor' }}</h2>
          <button @click="closeModal" class="modal-close">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <form @submit.prevent="submitForm" class="modal-body">
          <div v-if="formError" class="form-error">
            {{ formError }}
          </div>

          <div class="form-group">
            <label for="nome">Nome *</label>
            <input 
              id="nome"
              v-model="form.nome"
              type="text"
              required
              placeholder="Digite o nome do vendedor"
            />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="taxa_comissao">Taxa de Comissão (%)</label>
              <input 
                id="taxa_comissao"
                v-model="form.taxa_comissao"
                type="number"
                step="0.01"
                min="0"
                max="100"
                placeholder="10.00"
              />
            </div>

            <div class="form-group">
              <label for="meta_semanal">Meta Semanal (G$)</label>
              <input 
                id="meta_semanal"
                v-model="form.meta_semanal"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
              />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label for="telefone">Telefone</label>
              <input 
                id="telefone"
                v-model="form.telefone"
                type="text"
                placeholder="+595 xxx xxx xxx"
              />
            </div>

            <div class="form-group">
              <label for="conta_bancaria">Conta Bancária</label>
              <input 
                id="conta_bancaria"
                v-model="form.conta_bancaria"
                type="text"
                placeholder="Número da conta"
              />
            </div>
          </div>

          <div class="form-group">
            <ColorPicker 
              v-model="form.cor_calendario"
              label="Cor do Calendário"
            />
          </div>

          <div class="form-group">
            <label class="checkbox-label">
              <input 
                v-model="form.ativo"
                type="checkbox"
              />
              <span class="checkmark"></span>
              Vendedor ativo
            </label>
          </div>

          <div class="modal-footer">
            <button type="button" @click="closeModal" class="button secondary">
              Cancelar
            </button>
            <button type="submit" :disabled="isSubmitting" class="button primary">
              <span v-if="isSubmitting">{{ isEditing ? 'Salvando...' : 'Criando...' }}</span>
              <span v-else>{{ isEditing ? 'Salvar' : 'Criar Vendedor' }}</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import ColorPicker from '@/components/ColorPicker.vue'
import { vendorsAPI, type VendorResponse, type VendorCreate } from '@/services/api'

const router = useRouter()

// Reactive data
const vendors = ref<VendorResponse[]>([])
const isLoading = ref(false)
const showModal = ref(false)
const isEditing = ref(false)
const isSubmitting = ref(false)
const currentFilter = ref<'all' | 'active' | 'inactive'>('all')
const searchQuery = ref('')
const formError = ref('')

// Form data
const form = ref<VendorCreate & { id?: string }>({
  nome: '',
  taxa_comissao: 10,
  meta_semanal: 0,
  conta_bancaria: '',
  telefone: '',
  cor_calendario: '#3B82F6',
  ativo: true
})

// Computed properties
const activeVendors = computed(() => vendors.value.filter(v => v.ativo).length)
const inactiveVendors = computed(() => vendors.value.filter(v => !v.ativo).length)
const totalVendors = computed(() => vendors.value.length)

const filteredVendors = computed(() => {
  let filtered = vendors.value

  // Filter by status
  if (currentFilter.value === 'active') {
    filtered = filtered.filter(v => v.ativo)
  } else if (currentFilter.value === 'inactive') {
    filtered = filtered.filter(v => !v.ativo)
  }

  // Filter by search query
  if (searchQuery.value.trim()) {
    const query = searchQuery.value.toLowerCase()
    filtered = filtered.filter(v => 
      v.nome.toLowerCase().includes(query) ||
      v.telefone?.toLowerCase().includes(query)
    )
  }

  return filtered
})

// Methods
const loadVendors = async () => {
  try {
    isLoading.value = true
    vendors.value = await vendorsAPI.getAll()
  } catch (error) {
    console.error('Error loading vendors:', error)
  } finally {
    isLoading.value = false
  }
}

const setFilter = (filter: 'all' | 'active' | 'inactive') => {
  currentFilter.value = filter
}

const openCreateModal = () => {
  isEditing.value = false
  form.value = {
    nome: '',
    taxa_comissao: 10,
    meta_semanal: 0,
    conta_bancaria: '',
    telefone: '',
    cor_calendario: '#3B82F6',
    ativo: true
  }
  formError.value = ''
  showModal.value = true
}

const editVendor = (vendor: VendorResponse) => {
  isEditing.value = true
  form.value = {
    id: vendor.id,
    nome: vendor.nome,
    taxa_comissao: vendor.taxa_comissao,
    meta_semanal: vendor.meta_semanal,
    conta_bancaria: vendor.conta_bancaria || '',
    telefone: vendor.telefone || '',
    cor_calendario: vendor.cor_calendario || '#3B82F6',
    ativo: vendor.ativo
  }
  formError.value = ''
  showModal.value = true
}

const closeModal = () => {
  showModal.value = false
  formError.value = ''
}

const submitForm = async () => {
  try {
    isSubmitting.value = true
    formError.value = ''

    const vendorData = {
      nome: form.value.nome.trim(),
      taxa_comissao: form.value.taxa_comissao || 10,
      meta_semanal: form.value.meta_semanal || 0,
      conta_bancaria: form.value.conta_bancaria?.trim() || undefined,
      telefone: form.value.telefone?.trim() || undefined,
      cor_calendario: form.value.cor_calendario || '#3B82F6',
      ativo: form.value.ativo
    }

    if (isEditing.value && form.value.id) {
      await vendorsAPI.update(form.value.id, vendorData)
    } else {
      await vendorsAPI.create(vendorData)
    }

    await loadVendors()
    closeModal()
  } catch (error: any) {
    formError.value = error.response?.data?.detail || 'Erro ao salvar vendedor'
  } finally {
    isSubmitting.value = false
  }
}

const toggleVendorStatus = async (vendor: VendorResponse) => {
  try {
    await vendorsAPI.update(vendor.id, { ativo: !vendor.ativo })
    await loadVendors()
  } catch (error) {
    console.error('Error toggling vendor status:', error)
  }
}

const formatCurrency = (value: number) => {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('pt-BR')
}

const goBack = () => {
  router.go(-1)
}

// Lifecycle
onMounted(() => {
  loadVendors()
})
</script>

<style scoped>
.vendor-management {
  min-height: 100vh;
  background-color: #f9fafb;
}

/* Header */
.page-header {
  background-color: white;
  border-bottom: 1px solid #e5e7eb;
  padding: 1.5rem 2rem;
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 1200px;
  margin: 0 auto;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-button {
  background: none;
  border: none;
  padding: 0.5rem;
  border-radius: 0.5rem;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
}

.back-button:hover {
  background-color: #f3f4f6;
  color: #374151;
}

.back-button svg {
  width: 1.5rem;
  height: 1.5rem;
}

.header-title h1 {
  margin: 0;
  font-size: 1.875rem;
  font-weight: 700;
  color: #111827;
}

.subtitle {
  margin: 0.25rem 0 0 0;
  color: #6b7280;
  font-size: 0.875rem;
}

.create-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  background-color: #16a34a;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.create-button:hover {
  background-color: #15803d;
}

.create-button svg {
  width: 1.25rem;
  height: 1.25rem;
}

/* Content */
.page-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

/* Stats */
.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  background-color: white;
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  gap: 1rem;
}

.stat-icon {
  width: 3rem;
  height: 3rem;
  border-radius: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon.active {
  background-color: #dcfce7;
  color: #16a34a;
}

.stat-icon.inactive {
  background-color: #fee2e2;
  color: #dc2626;
}

.stat-icon.total {
  background-color: #dbeafe;
  color: #2563eb;
}

.stat-icon svg {
  width: 1.5rem;
  height: 1.5rem;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 1.875rem;
  font-weight: 700;
  color: #111827;
  line-height: 1;
}

.stat-label {
  font-size: 0.875rem;
  color: #6b7280;
  margin-top: 0.25rem;
}

/* Filters */
.filters-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  gap: 1rem;
  flex-wrap: wrap;
}

.filters-group {
  display: flex;
  gap: 0.5rem;
}

.filter-button {
  padding: 0.75rem 1rem;
  border: 1px solid #d1d5db;
  background-color: white;
  border-radius: 0.5rem;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
  transition: all 0.2s;
}

.filter-button:hover {
  background-color: #f9fafb;
}

.filter-button.active {
  background-color: #2563eb;
  color: white;
  border-color: #2563eb;
}

.search-group {
  flex-shrink: 0;
}

.search-input {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 0.75rem;
  top: 50%;
  transform: translateY(-50%);
  width: 1.25rem;
  height: 1.25rem;
  color: #9ca3af;
}

.search-input input {
  padding: 0.75rem 0.75rem 0.75rem 2.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  width: 250px;
  font-size: 0.875rem;
}

.search-input input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* Table */
.table-section {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  overflow: hidden;
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
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

.empty-state {
  text-align: center;
  padding: 3rem;
}

.empty-icon {
  width: 4rem;
  height: 4rem;
  color: #9ca3af;
  margin: 0 auto 1rem;
}

.empty-state h3 {
  margin: 0 0 0.5rem 0;
  color: #111827;
  font-size: 1.125rem;
  font-weight: 600;
}

.empty-state p {
  margin: 0 0 1.5rem 0;
  color: #6b7280;
  font-size: 0.875rem;
}

.table-container {
  overflow-x: auto;
}

.vendors-table {
  width: 100%;
  border-collapse: collapse;
}

.vendors-table th {
  background-color: #f9fafb;
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  font-size: 0.875rem;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
}

.vendors-table td {
  padding: 1rem;
  border-bottom: 1px solid #f3f4f6;
  font-size: 0.875rem;
}

.vendor-row:hover {
  background-color: #f9fafb;
}

.vendor-name {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.vendor-avatar {
  width: 2.5rem;
  height: 2.5rem;
  background-color: #2563eb;
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.875rem;
}

.commission-rate {
  font-weight: 600;
  color: #059669;
}

.weekly-goal {
  font-weight: 600;
  color: #374151;
}

.phone {
  color: #6b7280;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.75rem;
  font-weight: 500;
}

.status-badge.active {
  background-color: #dcfce7;
  color: #166534;
}

.status-badge.inactive {
  background-color: #fee2e2;
  color: #991b1b;
}

.created-date {
  color: #6b7280;
}

.actions-column {
  width: 120px;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.action-button {
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

.action-button svg {
  width: 1rem;
  height: 1rem;
}

.action-button.edit {
  background-color: #dbeafe;
  color: #2563eb;
}

.action-button.edit:hover {
  background-color: #bfdbfe;
}

.action-button.activate {
  background-color: #dcfce7;
  color: #16a34a;
}

.action-button.activate:hover {
  background-color: #bbf7d0;
}

.action-button.deactivate {
  background-color: #fee2e2;
  color: #dc2626;
}

.action-button.deactivate:hover {
  background-color: #fecaca;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  margin: 1rem;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h2 {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.modal-close {
  width: 2rem;
  height: 2rem;
  border-radius: 0.375rem;
  background: none;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.modal-close:hover {
  background-color: #f3f4f6;
  color: #374151;
}

.modal-close svg {
  width: 1.25rem;
  height: 1.25rem;
}

.modal-body {
  padding: 1.5rem;
  max-height: 60vh;
  overflow-y: auto;
}

.form-error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  padding: 0.75rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.form-group {
  margin-bottom: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
  margin-bottom: 0.5rem;
}

.form-group input {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  transition: border-color 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
  margin: 0;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  background-color: #f9fafb;
}

.button {
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.button.secondary {
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.button.secondary:hover {
  background-color: #e5e7eb;
}

.button.primary {
  background-color: #2563eb;
  color: white;
}

.button.primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.button.primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 768px) {
  .page-header {
    padding: 1rem;
  }

  .page-content {
    padding: 1rem;
  }

  .header-content {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }

  .stats-row {
    grid-template-columns: 1fr;
    gap: 1rem;
  }

  .filters-section {
    flex-direction: column;
    align-items: stretch;
  }

  .search-input input {
    width: 100%;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  .modal-content {
    margin: 0.5rem;
  }

  .table-container {
    font-size: 0.75rem;
  }

  .vendors-table th,
  .vendors-table td {
    padding: 0.75rem 0.5rem;
  }
}
</style>