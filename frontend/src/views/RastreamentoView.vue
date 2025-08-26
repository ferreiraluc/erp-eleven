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
        <!-- Cabeçalho da lista desktop -->
        <div class="list-header desktop-header">
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
          <!-- Layout Mobile: Card Dropdown -->
          <div class="mobile-dropdown-card">
            <!-- Cabeçalho sempre visível -->
            <div 
              class="mobile-card-header"
              @click="toggleCard(rastreamento.id)"
            >
              <div class="mobile-header-top">
                <div class="mobile-name-section">
                  <span class="mobile-name">{{ rastreamento.destinatario || 'Sem destinatário' }}</span>
                </div>
                <div class="mobile-expand-icon">
                  <svg 
                    width="20" 
                    height="20" 
                    fill="none" 
                    viewBox="0 0 24 24" 
                    stroke="currentColor"
                    :class="{ 'rotate-180': isCardExpanded(rastreamento.id) }"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>
              
              <div class="mobile-header-main">
                <div class="mobile-code-section">
                  <span class="mobile-code">{{ rastreamento.codigo_rastreio }}</span>
                  <button 
                    @click.stop="copiarCodigo(rastreamento.codigo_rastreio)"
                    class="mobile-copy-btn"
                    title="Copiar"
                  >
                    <svg width="14" height="14" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                  </button>
                </div>
                
                <button 
                  @click.stop="abrirRastreioCorreios(rastreamento.codigo_rastreio)"
                  class="mobile-correios-btn-compact"
                  title="Rastrear nos Correios"
                >
                  <svg width="16" height="16" viewBox="0 0 100 100" fill="none">
                    <path d="M15 25 L35 45 L15 65 Z" fill="#FFC107"/>
                    <path d="M35 15 L65 35 L45 55 L15 25 Z" fill="#FFC107"/>
                    <path d="M45 55 L75 75 L45 85 Z" fill="#FF9800"/>
                    <path d="M65 35 L85 15 L85 45 L65 65 Z" fill="#2196F3"/>
                    <path d="M65 65 L85 45 L85 75 L65 85 Z" fill="#1976D2"/>
                  </svg>
                  Correios
                </button>
              </div>
            </div>
            
            <!-- Conteúdo expansível -->
            <div 
              class="mobile-card-content"
              :class="{ 'expanded': isCardExpanded(rastreamento.id) }"
            >
              <div class="mobile-card-inner">
                <!-- Status -->
                <div class="mobile-content-row">
                  <span class="mobile-content-label">Status:</span>
                  <select 
                    v-model="rastreamento.status"
                    @change="atualizarStatus(rastreamento)"
                    class="mobile-status-select-expanded"
                    :class="getStatusClass(rastreamento.status)"
                  >
                    <option value="PENDENTE">Pendente</option>
                    <option value="EM_TRANSITO">Em Trânsito</option>
                    <option value="ENTREGUE">Entregue</option>
                    <option value="ERRO">Erro</option>
                  </select>
                </div>
                
                <!-- Detalhes -->
                <div class="mobile-content-row" v-if="rastreamento.destinatario">
                  <span class="mobile-content-label">Destinatário:</span>
                  <span class="mobile-content-value">{{ rastreamento.destinatario }}</span>
                </div>
                <div class="mobile-content-row" v-if="rastreamento.descricao">
                  <span class="mobile-content-label">Descrição:</span>
                  <span class="mobile-content-value">{{ rastreamento.descricao }}</span>
                </div>
                <div class="mobile-content-row">
                  <span class="mobile-content-label">Criado em:</span>
                  <span class="mobile-content-value mobile-date-value">{{ formatarData(rastreamento.created_at) }}</span>
                </div>
                
                <!-- Ações -->
                <div class="mobile-content-actions">
                  <button 
                    @click="editarRastreamento(rastreamento)"
                    class="mobile-action-btn-expanded edit"
                    title="Editar"
                  >
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                    Editar
                  </button>
                  <button 
                    @click="removerRastreamento(rastreamento)"
                    class="mobile-action-btn-expanded delete"
                    title="Excluir"
                  >
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                    Excluir
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Código e botão copiar (desktop) -->
          <div class="row-codigo desktop-only">
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

          <!-- Data criação (desktop) -->
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
const expandedCards = ref<Set<string>>(new Set())

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
  
  // Ordenação: entregues vão para o final, demais por data de criação (mais recentes primeiro)
  return lista.sort((a, b) => {
    // Se um é entregue e outro não, o entregue vai para baixo
    if (a.status === 'ENTREGUE' && b.status !== 'ENTREGUE') return 1
    if (a.status !== 'ENTREGUE' && b.status === 'ENTREGUE') return -1
    
    // Se ambos são entregues ou ambos não são, ordena por data de criação (mais recente primeiro)
    const dataA = new Date(a.created_at).getTime()
    const dataB = new Date(b.created_at).getTime()
    return dataB - dataA
  })
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

function getStatusClass(status: string): string {
  return rastreamentoStore.getStatusColor(status)
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

// Funções para controlar expansão dos cards
function toggleCard(cardId: string) {
  if (expandedCards.value.has(cardId)) {
    expandedCards.value.delete(cardId)
  } else {
    expandedCards.value.add(cardId)
  }
}

function isCardExpanded(cardId: string): boolean {
  return expandedCards.value.has(cardId)
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
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
  max-width: 600px;
}

.stat-card {
  background-color: white;
  border-radius: 0.75rem;
  padding: 1rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.stat-icon {
  width: 2.5rem;
  height: 2.5rem;
  border-radius: 0.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-icon svg {
  width: 1.25rem;
  height: 1.25rem;
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
  font-size: 1.5rem;
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

/* Desktop styles */
.mobile-dropdown-card {
  display: none;
}

/* Responsive */
@media (max-width: 768px) {
  .mobile-dropdown-card {
    display: block !important;
  }
  
  .desktop-header,
  .desktop-only {
    display: none !important;
  }


  /* Novo layout mobile - cards dropdown com largura quase total */
  .mobile-dropdown-card {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    margin: 0 0.125rem 16px 0.125rem;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    transition: all 0.2s ease;
    width: calc(100% - 0.25rem);
  }
  
  .mobile-dropdown-card:hover {
    border-color: #cbd5e1;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }
  
  /* Cabeçalho sempre visível com nome */
  .mobile-card-header {
    display: flex;
    flex-direction: column;
    padding: 16px;
    background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
    cursor: pointer;
    transition: all 0.2s;
    gap: 12px;
  }
  
  .mobile-card-header:hover {
    background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  }
  
  .mobile-header-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    width: 100%;
  }
  
  .mobile-name-section {
    flex: 1;
  }
  
  .mobile-name {
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
    line-height: 1.2;
  }
  
  .mobile-header-main {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
  }
  
  .mobile-code-section {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .mobile-code {
    font-family: 'SF Mono', 'Monaco', 'Consolas', monospace;
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
    background: white;
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid #cbd5e1;
    letter-spacing: 0.5px;
  }
  
  .mobile-copy-btn {
    width: 32px;
    height: 32px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: white;
    color: #64748b;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
  }
  
  .mobile-copy-btn:hover {
    background: #f1f5f9;
    border-color: #94a3b8;
    color: #475569;
  }
  
  .mobile-correios-btn-compact {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 12px;
    background: linear-gradient(135deg, #fbbf24 0%, #f59e0b 100%);
    color: #1f2937;
    border: 1px solid #d97706;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .mobile-correios-btn-compact:hover {
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(245, 158, 11, 0.3);
  }
  
  .mobile-expand-icon {
    color: #64748b;
    transition: all 0.3s ease;
  }
  
  .mobile-expand-icon svg {
    transition: transform 0.3s ease;
  }
  
  .mobile-expand-icon svg.rotate-180 {
    transform: rotate(180deg);
  }
  
  /* Conteúdo expansível */
  .mobile-card-content {
    max-height: 0;
    overflow: hidden;
    transition: all 0.3s ease;
    opacity: 0;
  }
  
  .mobile-card-content.expanded {
    max-height: 400px;
    opacity: 1;
  }
  
  .mobile-card-inner {
    padding: 16px;
    background: white;
    border-top: 1px solid #e5e7eb;
  }
  
  .mobile-content-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 8px 0;
    border-bottom: 1px solid #f1f5f9;
  }
  
  .mobile-content-row:last-child {
    border-bottom: none;
  }
  
  .mobile-content-label {
    font-size: 13px;
    font-weight: 500;
    color: #64748b;
    min-width: 80px;
    flex-shrink: 0;
  }
  
  .mobile-content-value {
    font-size: 14px;
    font-weight: 500;
    color: #1e293b;
    text-align: right;
    max-width: 60%;
    word-break: break-word;
  }
  
  .mobile-date-value {
    color: #64748b;
    font-size: 12px;
    font-weight: 400;
  }
  
  .mobile-status-select-expanded {
    padding: 8px 12px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 600;
    background: white;
    min-width: 100px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .mobile-status-select-expanded:focus {
    outline: none;
    border-color: #3b82f6;
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
  }
  
  /* Status colors for expanded select */
  .mobile-status-select-expanded.text-yellow-600 {
    background-color: #fef3c7;
    color: #92400e;
    border-color: #fbbf24;
  }
  
  .mobile-status-select-expanded.text-blue-600 {
    background-color: #dbeafe;
    color: #1e40af;
    border-color: #60a5fa;
  }
  
  .mobile-status-select-expanded.text-green-600 {
    background-color: #dcfce7;
    color: #166534;
    border-color: #4ade80;
  }
  
  .mobile-status-select-expanded.text-red-600 {
    background-color: #fecaca;
    color: #991b1b;
    border-color: #f87171;
  }
  
  .mobile-content-actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #f1f5f9;
  }
  
  .mobile-action-btn-expanded {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 12px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    background: white;
  }
  
  .mobile-action-btn-expanded.edit {
    color: #475569;
  }
  
  .mobile-action-btn-expanded.edit:hover {
    background: #f1f5f9;
    border-color: #94a3b8;
    color: #334155;
  }
  
  .mobile-action-btn-expanded.delete {
    color: #dc2626;
    border-color: #fca5a5;
  }
  
  .mobile-action-btn-expanded.delete:hover {
    background: #fef2f2;
    border-color: #f87171;
  }
  
  .header-content {
    flex-direction: row;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .header-left {
    flex: 1;
  }

  .header-actions {
    justify-content: flex-end;
    flex-shrink: 0;
  }

  .stats-grid {
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
  }
  
  .stat-card {
    padding: 0.75rem;
    gap: 0.5rem;
  }
  
  .stat-icon {
    width: 2rem;
    height: 2rem;
  }
  
  .stat-icon svg {
    width: 1rem;
    height: 1rem;
  }
  
  .stat-label {
    font-size: 0.75rem;
  }
  
  .stat-value {
    font-size: 1.25rem;
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
    padding: 0rem;
  }

  .list-header {
    display: none;
  }

  .rastreamento-row {
    display: flex ;
    flex-direction: column;
    padding: 0;
    border: 2px solid #e5e7eb;
    border-radius: 1rem;
    margin-bottom: 2rem;
    background: white;
    box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    position: relative;
    width: 100%;
    box-sizing: border-box;
    transition: all 0.3s;
    overflow: hidden;
  }

  .rastreamento-row:hover {
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    border-color: #9ca3af;
    transform: translateY(-2px);
  }

  /* Layout mobile: Código e botão na primeira linha */
  .row-codigo {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.75rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid #f3f4f6;
  }

  .row-codigo .codigo-text {
    font-size: 0.875rem;
    font-weight: 600;
    font-family: monospace;
  }

  .row-codigo .copy-btn {
    margin-left: 0.5rem;
  }




  /* Garantir que todos os elementos ficam dentro do card */
  .rastreamento-row * {
    max-width: 100%;
    box-sizing: border-box;
  }

  /* Esconder campos desktop no mobile */
  .row-destinatario,
  .row-descricao,
  .row-rastreio,
  .row-status,
  .row-data,
  .row-actions {
    display: none !important;
  }

}

/* Estilos da Lista */
.rastreamentos-list {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0rem 2rem;
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

/* Quebra a linha da listagem para 1 coluna e empilha os campos */
@media (max-width: 1100px) {
  .rastreamentos-list .list-header {
    display: none !important; /* some o cabeçalho em telas menores */
  }

  .rastreamento-row {
    display: grid;
    grid-template-columns: 1fr !important; /* vira 1 coluna */
    gap: 0.75rem;
  }

  /* Cada célula passa a ocupar a linha inteira, abaixo do bloco de código */
  .row-destinatario,
  .row-descricao,
  .row-rastreio,
  .row-status,
  .row-data,
  .row-actions {
    grid-column: 1 / -1 !important;
    justify-content: flex-start; /* evita centralização estranha herdada */
  }
}

/* Evita corte lateral do card */
.rastreamento-row {
  overflow: visible;            /* antes estava hidden */
}

/* Permite que cada célula encolha dentro da linha */
.rastreamento-row > * {
  min-width: 0;
}

/* Mobile: empilha e garante que o conteúdo quebre corretamente */
@media (max-width: 768px) {
  .mobile-main-row {
    display: grid !important;
    grid-template-columns: 1fr !important;
    align-items: stretch;
  }

  .rastreamento-row {
    display: flex;
    flex-direction: column;     /* tudo embaixo do bloco código+correios */
  }

  /* As linhas de info podem quebrar para a próxima linha */
  .mobile-info-row {
    flex-wrap: wrap;
    gap: 0.5rem 1rem;
  }

  /* O valor deve poder ocupar a linha inteira sem cortar */
  .mobile-value {
    max-width: 100%;
    word-break: break-word;
    overflow-wrap: anywhere;
  }

  /* O select de status não deve estourar a largura */
  .mobile-status-select {
    width: 100%;
    max-width: 260px;           /* ajuste fino opcional */
  }

  .mobile-rastreio-section,
  .row-rastreio {
    width: 100%;
    display: flex;
    justify-content: center; /* ou flex-start se quiser alinhado à esquerda */
    margin-top: 0.5rem;
  }

  .mobile-rastreio-btn-header,
  .rastreio-btn {
    width: 100%;        /* ocupa a linha toda */
    max-width: 100%;    /* evita estourar */
    justify-content: center;
    box-sizing: border-box;
  }
  
}

/* ===== Ajustes de TAMANHO: somente MOBILE ===== */
@media (max-width: 768px) {
  /* Header mais compacto */
  .page-header { border-bottom-width: 0; }
  .header-content {
    padding: 0.75rem 1rem;
    gap: 0.5rem;
  }
  .back-button {
    width: 2rem; height: 2rem; border-radius: 0.4rem;
  }
  .back-button svg { width: 1rem; height: 1rem; }

  .page-title {
    font-size: 1.125rem; /* antes 1.5rem */
    line-height: 1.2;
  }
  .page-subtitle {
    font-size: 0.75rem;   /* menor */
    color: #6b7280;
  }

  /* Botão "Novo Rastreamento" menor e no canto direito */
  .header-actions {
    justify-content: flex-end;
  }
  
  .header-actions .btn.btn-primary {
    padding: 0.4rem 0.75rem;
    font-size: 0.8rem;
    border-radius: 0.5rem;
    gap: 0.3rem;
    min-width: auto;
  }
  .header-actions .btn.btn-primary .btn-icon {
    width: 0.8rem; height: 0.8rem;
  }

  /* Cards de estatísticas com exata largura dos cards de rastreamento */
  .stats-section { padding: 0.75rem 0.125rem; }
  .stats-grid {
    grid-template-columns: 1fr 1fr;
    gap: 0.25rem;
    max-width: none;
    width: 100%;
  }
  .stat-card {
    padding: 1rem;
    border-radius: 0.75rem;
    gap: 0.75rem;
    margin: 0;
    width: 100%;
    box-sizing: border-box;
    min-height: 80px;
  }
  .stat-icon {
    width: 2.25rem; height: 2.25rem; border-radius: 0.5rem;
  }
  .stat-icon svg { width: 1.25rem; height: 1.25rem; }
  .stat-label { font-size: 0.8rem; margin-bottom: 0.25rem; font-weight: 500; }
  .stat-value { font-size: 1.5rem; font-weight: 700; }

  /* Filtros/Busca com exata largura dos cards */
  .filters-section { padding: 0 0.125rem 0.75rem; }
  .search-input {
    padding: 0.6rem 0.6rem 0.6rem 2.1rem;
    font-size: 0.85rem;
    border-radius: 0.5rem;
    width: 100%;
    margin: 0;
  }
  .search-icon { left: 0.6rem; }

  .status-select {
    padding: 0.6rem;
    font-size: 0.85rem;
    min-width: 0;
    width: 100%;
    margin: 0;
  }
  
  .search-box {
    width: 100%;
    margin: 0;
  }
  
  .filter-select {
    width: 100%;
    margin: 0;
  }

  /* Lista: "cards" de rastreamento com largura total */
  .rastreamentos-list { 
    padding: 0.01rem 0.01rem; 
    
  }
  .rastreamento-row {
    border-radius: 0.75rem;
    margin-bottom: 0.5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }

  /* Cabeçalho do card (código + botão Correios) menor */
  .mobile-main-row {
    padding: 0.85rem 0.9rem;
    border-radius: 0.75rem 0.75rem 0 0;
  }
  .mobile-codigo-section .codigo-text {
    padding: 0.5rem 0.75rem;
    font-size: 0.95rem;
  }
  .mobile-codigo-section .copy-btn {
    width: 2.1rem; height: 2.1rem; border-radius: 0.45rem;
  }
  .mobile-rastreio-btn-header {
    padding: 0.55rem 0.75rem;
    font-size: 0.85rem;
    min-width: 100px;
    border-radius: 0.6rem;
  }

  /* Blocos de info mais justos */
  .mobile-info-section { padding: 0.75rem 0.9rem; }
  .mobile-info-row {
    padding: 0.6rem 0.7rem;
    margin-bottom: 0.6rem;
    border-radius: 0.5rem;
  }
  .mobile-label {
    font-size: 0.75rem;
    min-width: 80px;
  }
  .mobile-value {
    font-size: 0.9rem;
  }
  .mobile-status-select {
    padding: 0.75rem;
    font-size: 0.85rem;
    max-width: 220px;
    border-radius: 0.5rem;
  }
  .mobile-date { font-size: 0.75rem; }

  /* Ações do card mais compactas */
  .mobile-actions {
    padding: 1rem;
    margin-top: 0.75rem;
    gap: 0.75rem;
    border-top-width: 1px;
  }
  .mobile-action-btn {
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    min-height: 42px;
    border-radius: 0.6rem;
    max-width: 120px;
  }
}

@media (max-width: 380px) {
  .page-title { font-size: 1rem; }
  .header-actions .btn.btn-primary { font-size: 0.8rem; padding: 0.45rem 0.7rem; }
  .stat-value { font-size: 0.95rem; }
}



</style>