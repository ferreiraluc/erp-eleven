<template>
  <div class="rastreamento-page">
    <!-- Header -->
    <header class="page-header">
      <div class="header-content">
        <div class="header-left">
          <button @click="$router.back()" class="back-button">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div class="header-info">
            <h1 class="page-title">Rastreamento de Encomendas</h1>
            <p class="page-subtitle">Gerencie e acompanhe todas as suas entregas</p>
          </div>
        </div>
        
        <div class="header-actions">
          
          <button @click="abrirModalCriacao" class="btn btn-primary">
            <svg class="btn-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Novo Rastreamento
          </button>
        </div>
      </div>
    </header>

    <!-- Stats Cards -->
    <div class="stats-section">
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon blue">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2M4 13h2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v4m-6 0h6" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Total</p>
            <p class="stat-value">{{ resumo?.total_rastreamentos || 0 }}</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon yellow">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Em Trânsito</p>
            <p class="stat-value">{{ resumo?.em_transito || 0 }}</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon green">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Entregues</p>
            <p class="stat-value">{{ resumo?.entregues || 0 }}</p>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon red">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="stat-content">
            <p class="stat-label">Pendentes</p>
            <p class="stat-value">{{ resumo?.pendentes || 0 }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Filtros e Busca -->
    <div class="filters-section">
      <div class="filters-content">
        <div class="search-box">
          <svg class="search-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input 
            v-model="filtros.busca"
            type="text" 
            placeholder="Buscar por código ou destinatário..."
            class="search-input"
            @input="aplicarFiltros"
          />
        </div>

        <div class="filter-select">
          <select v-model="filtros.status" @change="aplicarFiltros" class="status-select">
            <option value="">Todos os Status</option>
            <option value="PENDENTE">Pendente</option>
            <option value="EM_TRANSITO">Em Trânsito</option>
            <option value="ENTREGUE">Entregue</option>
            <option value="ERRO">Erro</option>
          </select>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="loading-section">
      <div class="loading-spinner">
        <svg class="spinner" fill="none" viewBox="0 0 24 24">
          <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      </div>
      <p>Carregando rastreamentos...</p>
    </div>

    <!-- Lista de Rastreamentos -->
    <div v-else class="rastreamentos-section">
      <div v-if="rastreamentosFiltrados.length === 0" class="empty-state">
        <svg class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2M4 13h2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v4m-6 0h6" />
        </svg>
        <h3>Nenhum rastreamento encontrado</h3>
        <p>Adicione um novo rastreamento para começar</p>
        <button @click="abrirModalCriacao" class="btn btn-primary">
          Adicionar Rastreamento
        </button>
      </div>

      <div v-else class="rastreamentos-list">
        <!-- Cabeçalho da lista -->
        <div class="list-header">
          <div class="header-codigo">Código</div>
          <div class="header-destinatario">Destinatário</div>
          <div class="header-descricao">Descrição</div>
          <div class="header-rastreio">Rastreio</div>
          <div class="header-status">Status</div>
          <div class="header-data">Data</div>
          <div class="header-actions">Ações</div>
        </div>

        <div 
          v-for="rastreamento in rastreamentosFiltrados" 
          :key="rastreamento.id"
          class="rastreamento-row"
        >
          <!-- Código e botão copiar -->
          <div class="row-codigo">
            <span class="codigo-text">{{ rastreamento.codigo_rastreio }}</span>
            <button 
              @click="copiarCodigo(rastreamento.codigo_rastreio)"
              class="copy-btn"
              title="Copiar Código"
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
          </div>

          <!-- Destinatário -->
          <div class="row-destinatario">
            {{ rastreamento.destinatario || '-' }}
          </div>

          <!-- Descrição -->
          <div class="row-descricao">
            {{ rastreamento.descricao || '-' }}
          </div>

          <!-- Botão Rastreio Correios -->
          <div class="row-rastreio">
            <button 
              @click="abrirRastreioCorreios(rastreamento.codigo_rastreio)"
              class="rastreio-btn"
              title="Rastrear nos Correios"
            >
              <svg width="16" height="16" viewBox="0 0 100 100" fill="none">
                <!-- Logo dos Correios -->
                <path d="M15 25 L35 45 L15 65 Z" fill="#FFC107"/>
                <path d="M35 15 L65 35 L45 55 L15 25 Z" fill="#FFC107"/>
                <path d="M45 55 L75 75 L45 85 Z" fill="#FF9800"/>
                <path d="M65 35 L85 15 L85 45 L65 65 Z" fill="#2196F3"/>
                <path d="M65 65 L85 45 L85 75 L65 85 Z" fill="#1976D2"/>
              </svg>
              <span>Correios</span>
            </button>
          </div>

          <!-- Status com edição inline -->
          <div class="row-status">
            <select 
              v-model="rastreamento.status"
              @change="atualizarStatus(rastreamento)"
              class="status-select-inline"
              :class="getStatusClass(rastreamento.status)"
            >
              <option value="PENDENTE">Pendente</option>
              <option value="EM_TRANSITO">Em Trânsito</option>
              <option value="ENTREGUE">Entregue</option>
              <option value="ERRO">Erro</option>
            </select>
          </div>

          <!-- Data criação -->
          <div class="row-data">
            {{ formatarData(rastreamento.created_at) }}
          </div>

          <!-- Ações -->
          <div class="row-actions">
            <button 
              @click="editarRastreamento(rastreamento)"
              class="action-btn"
              title="Editar"
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
            
            <button 
              @click="removerRastreamento(rastreamento)"
              class="action-btn delete"
              title="Excluir"
            >
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal de Criação/Edição -->
    <div v-if="showModal" class="modal-overlay" @click="fecharModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>{{ editandoRastreamento ? 'Editar' : 'Novo' }} Rastreamento</h2>
          <button @click="fecharModal" class="modal-close">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <div v-if="modalError" class="alert alert-error">
            {{ modalError }}
          </div>

          <div class="form-grid">
            <div class="form-group full-width">
              <label for="codigo">Código de Rastreamento *</label>
              <input 
                id="codigo"
                ref="codigoInput"
                type="text" 
                v-model="formData.codigo_rastreio"
                placeholder="BR123456789BR"
                class="form-input codigo-input"
                @input="formatarCodigo"
                :maxlength="13"
                required
              />
              <small class="input-hint">Digite apenas letras e números</small>
            </div>

            <div class="form-group">
              <label for="destinatario">Destinatário</label>
              <input 
                id="destinatario"
                type="text" 
                v-model="formData.destinatario"
                placeholder="Nome do destinatário"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="descricao">Descrição</label>
              <input 
                id="descricao"
                type="text" 
                v-model="formData.descricao"
                placeholder="Descrição do objeto"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="origem">Origem</label>
              <input 
                id="origem"
                type="text" 
                v-model="formData.origem"
                placeholder="Local de origem"
                class="form-input"
              />
            </div>

            <div class="form-group">
              <label for="destino">Destino</label>
              <input 
                id="destino"
                type="text" 
                v-model="formData.destino"
                placeholder="Local de destino"
                class="form-input"
              />
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="fecharModal" class="btn btn-secondary">
            Cancelar
          </button>
          
          <button 
            v-if="!editandoRastreamento"
            @click="consultarESalvar"
            :disabled="!formData.codigo_rastreio || salvando"
            class="btn btn-success"
          >
            <span v-if="salvando">Consultando...</span>
            <span v-else>Consultar e Salvar</span>
          </button>
          
          <button 
            @click="salvarRastreamento" 
            :disabled="!formData.codigo_rastreio || salvando" 
            class="btn btn-primary"
          >
            <span v-if="salvando">Salvando...</span>
            <span v-else>{{ editandoRastreamento ? 'Atualizar' : 'Salvar' }}</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRastreamentoStore } from '@/stores/rastreamento'
import type { Rastreamento, RastreamentoCreate } from '@/stores/rastreamento'

const rastreamentoStore = useRastreamentoStore()

// Estado da página
const loading = ref(false)
const showModal = ref(false)
const salvando = ref(false)
const modalError = ref<string | null>(null)
const editandoRastreamento = ref<Rastreamento | null>(null)
const codigoInput = ref<HTMLInputElement>()

// Dados do resumo
const resumo = ref(rastreamentoStore.resumoDashboard)

// Filtros
const filtros = ref({
  busca: '',
  status: ''
})

// Form data
const formData = ref<RastreamentoCreate>({
  codigo_rastreio: '',
  descricao: '',
  destinatario: '',
  origem: '',
  destino: '',
  pedido_id: undefined
})

// Computed
const rastreamentosFiltrados = computed(() => {
  let lista = rastreamentoStore.rastreamentosAtivos
  
  if (filtros.value.busca) {
    const busca = filtros.value.busca.toLowerCase()
    lista = lista.filter(r => 
      r.codigo_rastreio.toLowerCase().includes(busca) ||
      r.destinatario?.toLowerCase().includes(busca) ||
      r.descricao?.toLowerCase().includes(busca)
    )
  }
  
  if (filtros.value.status) {
    lista = lista.filter(r => r.status === filtros.value.status)
  }
  
  return lista
})

// Methods
async function carregarDados() {
  try {
    loading.value = true
    await Promise.all([
      rastreamentoStore.listarRastreamentos(),
      rastreamentoStore.obterResumoDashboard()
    ])
    resumo.value = rastreamentoStore.resumoDashboard
  } catch (error) {
    console.error('Erro ao carregar dados:', error)
  } finally {
    loading.value = false
  }
}

function aplicarFiltros() {
  // Os filtros são reativos através do computed
}

function abrirModalCriacao() {
  editandoRastreamento.value = null
  formData.value = {
    codigo_rastreio: '',
    descricao: '',
    destinatario: '',
    origem: '',
    destino: '',
    pedido_id: undefined
  }
  modalError.value = null
  showModal.value = true
  
  nextTick(() => {
    codigoInput.value?.focus()
  })
}

function editarRastreamento(rastreamento: Rastreamento) {
  editandoRastreamento.value = rastreamento
  formData.value = {
    codigo_rastreio: rastreamento.codigo_rastreio,
    descricao: rastreamento.descricao || '',
    destinatario: rastreamento.destinatario || '',
    origem: rastreamento.origem || '',
    destino: rastreamento.destino || '',
    pedido_id: rastreamento.pedido_id
  }
  modalError.value = null
  showModal.value = true
}

function fecharModal() {
  showModal.value = false
  editandoRastreamento.value = null
  modalError.value = null
}

function formatarCodigo(event: Event) {
  const input = event.target as HTMLInputElement
  let valor = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '')
  
  // Limitar a 13 caracteres (formato padrão dos Correios)
  if (valor.length > 13) {
    valor = valor.substring(0, 13)
  }
  
  formData.value.codigo_rastreio = valor
  input.value = valor
}

async function consultarESalvar() {
  if (!formData.value.codigo_rastreio) return
  
  try {
    salvando.value = true
    modalError.value = null
    
    await rastreamentoStore.consultarESalvarRastreamento({
      codigo: formData.value.codigo_rastreio,
      servico_id: '0001'
    })
    
    await carregarDados()
    fecharModal()
  } catch (error: any) {
    modalError.value = error.message || 'Erro ao consultar e salvar rastreamento'
  } finally {
    salvando.value = false
  }
}

async function salvarRastreamento() {
  if (!formData.value.codigo_rastreio) return
  
  try {
    salvando.value = true
    modalError.value = null
    
    if (editandoRastreamento.value) {
      await rastreamentoStore.atualizarRastreamento(
        editandoRastreamento.value.id,
        formData.value
      )
    } else {
      await rastreamentoStore.criarRastreamento(formData.value)
    }
    
    await carregarDados()
    fecharModal()
  } catch (error: any) {
    modalError.value = error.message || 'Erro ao salvar rastreamento'
  } finally {
    salvando.value = false
  }
}

async function consultarOnline(codigo: string) {
  try {
    loading.value = true
    await rastreamentoStore.consultarRastreamentoOnline({
      codigo,
      servico_id: '0001'
    })
    await carregarDados()
  } catch (error: any) {
    console.error('Erro ao consultar online:', error)
  } finally {
    loading.value = false
  }
}

async function removerRastreamento(rastreamento: Rastreamento) {
  if (!confirm(`Tem certeza que deseja remover o rastreamento ${rastreamento.codigo_rastreio}?`)) {
    return
  }
  
  try {
    await rastreamentoStore.removerRastreamento(rastreamento.id)
    await carregarDados()
  } catch (error: any) {
    console.error('Erro ao remover rastreamento:', error)
  }
}

async function atualizarTodos() {
  try {
    loading.value = true
    await rastreamentoStore.atualizarTodosRastreamentos()
    await carregarDados()
  } catch (error: any) {
    console.error('Erro ao atualizar rastreamentos:', error)
  } finally {
    loading.value = false
  }
}

function getStatusClass(status: string): string {
  return rastreamentoStore.getStatusColor(status)
}

function getStatusText(status: string): string {
  return rastreamentoStore.getStatusText(status)
}

function formatarData(data: string): string {
  return rastreamentoStore.formatarData(data)
}

// Novas funções para a lista
async function copiarCodigo(codigo: string) {
  try {
    await navigator.clipboard.writeText(codigo)
    // Você pode adicionar uma notificação aqui se quiser
    console.log('Código copiado:', codigo)
  } catch (error) {
    console.error('Erro ao copiar código:', error)
  }
}

function abrirRastreioCorreios(codigo: string) {
  const url = `https://rastreamento.correios.com.br/app/index.php?objetos=${codigo}`
  window.open(url, '_blank')
}

async function atualizarStatus(rastreamento: any) {
  try {
    await rastreamentoStore.atualizarRastreamento(rastreamento.id, {
      status: rastreamento.status
    })
    console.log('Status atualizado:', rastreamento.status)
    
    // Atualizar estatísticas automaticamente
    await rastreamentoStore.obterResumoDashboard()
    resumo.value = rastreamentoStore.resumoDashboard
  } catch (error: any) {
    console.error('Erro ao atualizar status:', error)
    // Reverter o status em caso de erro
    await carregarDados()
  }
}

// Lifecycle
onMounted(() => {
  carregarDados()
})
</script>

<style scoped>
.rastreamento-page {
  min-height: 100vh;
  background-color: #f9fafb;
}

/* Header */
.page-header {
  background-color: white;
  border-bottom: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.back-button {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.5rem;
  background-color: #f3f4f6;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.back-button:hover {
  background-color: #e5e7eb;
  color: #374151;
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
  font-size: 0.875rem;
  color: #6b7280;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

/* Stats Section */
.stats-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1.5rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
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

.stat-icon svg {
  width: 1.5rem;
  height: 1.5rem;
}

.stat-icon.blue {
  background-color: #dbeafe;
  color: #2563eb;
}

.stat-icon.yellow {
  background-color: #fef3c7;
  color: #d97706;
}

.stat-icon.green {
  background-color: #dcfce7;
  color: #16a34a;
}

.stat-icon.red {
  background-color: #fecaca;
  color: #dc2626;
}

.stat-label {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: #6b7280;
}

.stat-value {
  margin: 0;
  font-size: 2rem;
  font-weight: 700;
  color: #111827;
}

/* Filters */
.filters-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem 1.5rem;
}

.filters-content {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.search-box {
  flex: 1;
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

.search-input {
  width: 100%;
  padding: 0.75rem 0.75rem 0.75rem 2.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  background-color: white;
}

.search-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.status-select {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  background-color: white;
  min-width: 150px;
}

.status-select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

/* Loading */
.loading-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 3rem;
  color: #6b7280;
}

.loading-spinner {
  margin-bottom: 1rem;
}

.spinner {
  width: 2rem;
  height: 2rem;
  animation: spin 1s linear infinite;
}

.spinner-track {
  opacity: 0.25;
}

.spinner-path {
  opacity: 0.75;
}

/* Rastreamentos Grid */
.rastreamentos-section {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem 2rem;
}

.empty-state {
  text-align: center;
  padding: 3rem;
  color: #6b7280;
}

.empty-icon {
  width: 4rem;
  height: 4rem;
  margin: 0 auto 1rem;
  color: #9ca3af;
}

.empty-state h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #374151;
}

.empty-state p {
  margin: 0 0 1.5rem 0;
}

.rastreamentos-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 1.5rem;
}

.rastreamento-card {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  overflow: hidden;
  transition: all 0.2s;
}

.rastreamento-card:hover {
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  transform: translateY(-1px);
}

.card-header {
  padding: 1rem;
  border-bottom: 1px solid #f3f4f6;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.codigo-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.codigo {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
  font-family: monospace;
}

.status-badge {
  font-size: 0.75rem;
  font-weight: 500;
  padding: 0.25rem 0.5rem;
  border-radius: 0.375rem;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  gap: 0.5rem;
}

.action-btn {
  width: 2rem;
  height: 2rem;
  border-radius: 0.375rem;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f3f4f6;
  color: #6b7280;
  transition: all 0.2s;
}

.action-btn:hover {
  background-color: #e5e7eb;
  color: #374151;
}

.action-btn.delete:hover {
  background-color: #fecaca;
  color: #dc2626;
}

.action-btn svg {
  width: 1rem;
  height: 1rem;
}

.card-content {
  padding: 1rem;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.info-label {
  font-size: 0.75rem;
  font-weight: 500;
  color: #6b7280;
}

.info-value {
  font-size: 0.875rem;
  color: #111827;
}

/* Eventos */
.eventos-section {
  border-top: 1px solid #f3f4f6;
  padding-top: 1rem;
}

.eventos-title {
  margin: 0 0 0.75rem 0;
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}

.eventos-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.evento-item {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
}

.evento-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  background-color: #2563eb;
  margin-top: 0.375rem;
  flex-shrink: 0;
}

.evento-content {
  flex: 1;
}

.evento-situacao {
  margin: 0 0 0.25rem 0;
  font-size: 0.875rem;
  font-weight: 500;
  color: #111827;
}

.evento-detalhes {
  margin: 0 0 0.25rem 0;
  font-size: 0.75rem;
  color: #6b7280;
}

.evento-data {
  margin: 0;
  font-size: 0.75rem;
  color: #9ca3af;
}

/* Buttons */
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
  text-decoration: none;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
  width: 1rem;
  height: 1rem;
}

.btn-primary {
  background-color: #2563eb;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover:not(:disabled) {
  background-color: #e5e7eb;
}

.btn-success {
  background-color: #16a34a;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background-color: #15803d;
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
  padding: 1rem;
}

.modal-content {
  background-color: white;
  border-radius: 0.75rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
  flex: 1;
  overflow-y: auto;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  background-color: #f9fafb;
}

/* Form */
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-group.full-width {
  grid-column: 1 / -1;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.form-input {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  transition: border-color 0.2s;
}

.form-input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.codigo-input {
  font-family: monospace;
  font-weight: 600;
  text-transform: uppercase;
}

.input-hint {
  font-size: 0.75rem;
  color: #6b7280;
}

.alert {
  padding: 0.75rem;
  border-radius: 0.5rem;
  margin-bottom: 1rem;
  font-size: 0.875rem;
}

.alert-error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}

/* Status Colors */
.text-yellow-600.bg-yellow-100 {
  background-color: #fef3c7;
  color: #92400e;
}

.text-blue-600.bg-blue-100 {
  background-color: #dbeafe;
  color: #1e40af;
}

.text-green-600.bg-green-100 {
  background-color: #dcfce7;
  color: #166534;
}

.text-red-600.bg-red-100 {
  background-color: #fecaca;
  color: #991b1b;
}

.text-gray-600.bg-gray-100 {
  background-color: #f3f4f6;
  color: #4b5563;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Responsive */
@media (max-width: 768px) {
  .header-content {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }

  .header-actions {
    justify-content: space-between;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .filters-content {
    flex-direction: column;
    align-items: stretch;
  }

  .rastreamentos-grid {
    grid-template-columns: 1fr;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .modal-content {
    margin: 0.5rem;
    max-height: 95vh;
  }

  .rastreamentos-list {
    display: block;
  }

  .list-header {
    display: none;
  }

  .rastreamento-row {
    display: block;
    padding: 1rem;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    margin-bottom: 0.5rem;
  }

  .row-codigo,
  .row-destinatario,
  .row-descricao,
  .row-rastreio,
  .row-status,
  .row-data,
  .row-actions {
    margin-bottom: 0.5rem;
  }
}

/* Estilos da Lista */
.rastreamentos-list {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 1.5rem 2rem;
}

.list-header {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr 120px 120px 100px 120px;
  gap: 1rem;
  padding: 1rem;
  background-color: #f8fafc;
  border-radius: 0.5rem;
  margin-bottom: 0.5rem;
  font-weight: 600;
  font-size: 0.875rem;
  color: #374151;
  border: 1px solid #e2e8f0;
  align-items: center;
}

.list-header > div {
  display: flex;
  align-items: center;
}

.header-rastreio {
  justify-content: center;
}

.header-status {
  justify-content: center;
}

.header-data {
  justify-content: center;
}

.header-actions {
  justify-content: center;
}

.rastreamento-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.5fr 120px 120px 100px 120px;
  gap: 1rem;
  padding: 1rem;
  background-color: white;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  margin-bottom: 0.25rem;
  align-items: center;
  transition: all 0.2s;
}

.rastreamento-row:hover {
  border-color: #cbd5e1;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.row-codigo {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.codigo-text {
  font-family: monospace;
  font-weight: 600;
  font-size: 0.875rem;
  color: #111827;
}

.copy-btn {
  width: 1.5rem;
  height: 1.5rem;
  border: none;
  background: #f3f4f6;
  border-radius: 0.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.copy-btn:hover {
  background: #e5e7eb;
  color: #374151;
}

.row-destinatario,
.row-descricao {
  font-size: 0.875rem;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.row-status {
  display: flex;
  align-items: center;
}

.status-select-inline {
  width: 100%;
  padding: 0.375rem 0.5rem;
  border: 1px solid #d1d5db;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.status-select-inline:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

/* Status colors for select */
.status-select-inline.text-yellow-600 {
  background-color: #fef3c7;
  color: #92400e;
  border-color: #fbbf24;
}

.status-select-inline.text-blue-600 {
  background-color: #dbeafe;
  color: #1e40af;
  border-color: #60a5fa;
}

.status-select-inline.text-green-600 {
  background-color: #dcfce7;
  color: #166534;
  border-color: #4ade80;
}

.status-select-inline.text-red-600 {
  background-color: #fecaca;
  color: #991b1b;
  border-color: #f87171;
}

.row-data {
  font-size: 0.75rem;
  color: #6b7280;
  text-align: center;
}

.row-actions {
  display: flex;
  gap: 0.25rem;
  justify-content: center;
}

.action-btn {
  width: 1.75rem;
  height: 1.75rem;
  border: none;
  background: #f3f4f6;
  border-radius: 0.25rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #e5e7eb;
  color: #374151;
}

.action-btn.delete:hover {
  background: #fecaca;
  color: #dc2626;
}

.row-rastreio {
  display: flex;
  justify-content: center;
}

.rastreio-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.375rem 0.75rem;
  background: linear-gradient(135deg, #fbbf24 0%, #fbff00 100%);
  color: #1f2937;
  border: none;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  text-decoration: none;
  border: 1px solid #f59e0b;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.rastreio-btn:hover {
  background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 8px 0 rgba(245, 158, 11, 0.3);
  border-color: #d97706;
}

.rastreio-btn svg {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
}
</style>