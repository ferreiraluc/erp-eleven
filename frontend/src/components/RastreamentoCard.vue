<template>
  <div class="action-card rastreamento-card" @click="navigateToRastreamento" style="cursor: pointer;">
    <div class="card-header">
      <h3 class="card-title">Rastreamento</h3>
      <div class="card-actions">
        <button 
          v-if="canManageRastreamento"
          @click.stop="openRastreamentoModal"
          class="edit-rate-btn"
          title="Adicionar Rastreamento"
        >
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
        </button>
        <div class="card-icon">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </div>
      </div>
    </div>
    
    <div v-if="isLoading" class="rastreamento-content loading">
      <div class="tracking-loading">
        <svg class="loading-spinner" fill="none" viewBox="0 0 24 24">
          <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        <p>Carregando rastreamentos...</p>
      </div>
    </div>
    
    <div v-else class="rastreamento-content">
      <div class="rastreamento-stats">
        <div class="stat-item">
          <span class="stat-label">Total</span>
          <span class="stat-value">{{ resumo?.total_rastreamentos || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Em Trânsito</span>
          <span class="stat-value em-transito">{{ resumo?.em_transito || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Entregues</span>
          <span class="stat-value entregue">{{ resumo?.entregues || 0 }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Pendentes</span>
          <span class="stat-value pendente">{{ resumo?.pendentes || 0 }}</span>
        </div>
      </div>
      
      <div v-if="resumo?.rastreamentos_recentes?.length" class="rastreamentos-recentes">
        <h4 class="recentes-title">Últimos Rastreamentos</h4>
        <div class="rastreamentos-list">
          <div
            v-for="rastreamento in resumo.rastreamentos_recentes"
            :key="rastreamento.id"
            class="rastreamento-item"
          >
            <div class="rastreamento-info">
              <p class="rastreamento-codigo">{{ rastreamento.codigo_rastreio }}</p>
              <p class="rastreamento-cliente">{{ rastreamento.destinatario || 'Sem destinatário' }}</p>
            </div>
            <div class="rastreamento-status">
              <button
                @click.stop="copiarCodigo(rastreamento.codigo_rastreio)"
                class="copy-btn"
                title="Copiar código"
              >
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
              <span 
                class="status-badge"
                :class="getStatusClass(rastreamento.status)"
              >
                {{ getStatusText(rastreamento.status) }}
              </span>
            </div>
          </div>
        </div>
      </div>
      
      <div v-else class="empty-rastreamentos">
        <svg class="empty-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2M4 13h2m0 0V9a2 2 0 012-2h2a2 2 0 012 2v4m-6 0h6" />
        </svg>
        <p class="empty-text">Nenhum rastreamento</p>
      </div>
    </div>
  </div>

  <!-- Modal para Adicionar Rastreamento -->
  <div v-if="showModal" class="modal-overlay" @click="closeModal">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h2>Novo Rastreamento</h2>
        <button @click="closeModal" class="modal-close">
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
            <label for="codigo_rastreio">Código de Rastreamento *</label>
            <input 
              id="codigo_rastreio"
              type="text" 
              v-model="novoRastreamento.codigo_rastreio"
              @input="formatarCodigo"
              placeholder="BR123456789BR"
              class="form-input"
              required
              maxlength="13"
            />
          </div>

          <div class="form-group">
            <label for="destinatario">Destinatário</label>
            <input 
              id="destinatario"
              type="text" 
              v-model="novoRastreamento.destinatario"
              placeholder="Nome do destinatário"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label for="descricao">Descrição</label>
            <input 
              id="descricao"
              type="text" 
              v-model="novoRastreamento.descricao"
              placeholder="Descrição do objeto"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label for="origem">Origem</label>
            <input 
              id="origem"
              type="text" 
              v-model="novoRastreamento.origem"
              placeholder="Local de origem"
              class="form-input"
            />
          </div>

          <div class="form-group">
            <label for="destino">Destino</label>
            <input 
              id="destino"
              type="text" 
              v-model="novoRastreamento.destino"
              placeholder="Local de destino"
              class="form-input"
            />
          </div>
        </div>

        <div class="form-actions">
          <button 
            @click="consultarECriar"
            :disabled="!novoRastreamento.codigo_rastreio || isCreating"
            class="btn btn-consultar"
          >
            <span v-if="isCreating">Consultando...</span>
            <span v-else>Consultar e Adicionar</span>
          </button>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="closeModal" class="btn btn-secondary">
          Cancelar
        </button>
        <button 
          @click="criarRastreamento" 
          :disabled="!novoRastreamento.codigo_rastreio || isCreating" 
          class="btn btn-primary"
        >
          <span v-if="isCreating">Criando...</span>
          <span v-else>Criar Rastreamento</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRastreamentoStore } from '@/stores/rastreamento'
import { useAuthStore } from '@/stores/auth'
import type { RastreamentoResumo, RastreamentoCreate } from '@/stores/rastreamento'

const router = useRouter()
const rastreamentoStore = useRastreamentoStore()
const authStore = useAuthStore()

const isLoading = ref(false)
const showModal = ref(false)
const isCreating = ref(false)
const modalError = ref<string | null>(null)
const resumo = ref<RastreamentoResumo | null>(null)

const novoRastreamento = ref<RastreamentoCreate>({
  codigo_rastreio: '',
  descricao: '',
  destinatario: '',
  origem: '',
  destino: '',
  pedido_id: undefined
})

// Check if user can manage rastreamento
const canManageRastreamento = computed(() => {
  return authStore.user && ['ADMIN', 'GERENTE', 'OPERACIONAL'].includes(authStore.user.role)
})

const navigateToRastreamento = () => {
  router.push('/rastreamento')
}

const openRastreamentoModal = () => {
  if (!canManageRastreamento.value) return
  showModal.value = true
  modalError.value = null
  resetForm()
}

const closeModal = () => {
  showModal.value = false
  modalError.value = null
  resetForm()
}

const resetForm = () => {
  novoRastreamento.value = {
    codigo_rastreio: '',
    descricao: '',
    destinatario: '',
    origem: '',
    destino: '',
    pedido_id: undefined
  }
}

const loadResumo = async () => {
  try {
    isLoading.value = true
    resumo.value = await rastreamentoStore.obterResumoDashboard()
  } catch (error: any) {
    console.error('Erro ao carregar resumo de rastreamentos:', error)
  } finally {
    isLoading.value = false
  }
}

const criarRastreamento = async () => {
  if (!novoRastreamento.value.codigo_rastreio) return
  
  try {
    isCreating.value = true
    modalError.value = null
    
    await rastreamentoStore.criarRastreamento(novoRastreamento.value)
    
    // Recarregar resumo
    await loadResumo()
    
    closeModal()
  } catch (error: any) {
    modalError.value = error.message || 'Erro ao criar rastreamento'
  } finally {
    isCreating.value = false
  }
}

const consultarECriar = async () => {
  if (!novoRastreamento.value.codigo_rastreio) return
  
  try {
    isCreating.value = true
    modalError.value = null
    
    await rastreamentoStore.consultarESalvarRastreamento({
      codigo: novoRastreamento.value.codigo_rastreio,
      servico_id: '0001'
    })
    
    // Recarregar resumo
    await loadResumo()
    
    closeModal()
  } catch (error: any) {
    modalError.value = error.message || 'Erro ao consultar e criar rastreamento'
  } finally {
    isCreating.value = false
  }
}

const getStatusClass = (status: string): string => {
  switch (status) {
    case 'PENDENTE':
      return 'status-pendente'
    case 'EM_TRANSITO':
      return 'status-em-transito'
    case 'ENTREGUE':
      return 'status-entregue'
    case 'ERRO':
    case 'NAO_ENCONTRADO':
      return 'status-erro'
    default:
      return 'status-pendente'
  }
}

const getStatusText = (status: string): string => {
  switch (status) {
    case 'PENDENTE':
      return 'Pendente'
    case 'EM_TRANSITO':
      return 'Em Trânsito'
    case 'ENTREGUE':
      return 'Entregue'
    case 'ERRO':
      return 'Erro'
    case 'NAO_ENCONTRADO':
      return 'Não Encontrado'
    default:
      return status
  }
}

const formatarCodigo = (event: Event) => {
  const input = event.target as HTMLInputElement
  let valor = input.value.toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (valor.length > 13) {
    valor = valor.substring(0, 13)
  }
  novoRastreamento.value.codigo_rastreio = valor
}

const copiarCodigo = async (codigo: string) => {
  try {
    await navigator.clipboard.writeText(codigo)
    console.log('Código copiado:', codigo)
  } catch (error) {
    console.error('Erro ao copiar código:', error)
  }
}

onMounted(() => {
  loadResumo()
})
</script>

<style scoped>
.rastreamento-card {
  border-radius: 0.75rem;
  transition: all 0.2s ease-in-out;
  background-color: white;
  border: 1px solid #e5e7eb;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.rastreamento-card:hover {
  border-color: #2563eb;
  box-shadow: 0 4px 12px -4px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1rem 0.5rem 1rem;
}

.card-title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.edit-rate-btn {
  width: 1.5rem;
  height: 1.5rem;
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

.edit-rate-btn:hover {
  background-color: #f3f4f6;
  color: #374151;
}

.edit-rate-btn svg {
  width: 0.875rem;
  height: 0.875rem;
}

.card-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
}

.card-icon svg {
  width: 1rem;
  height: 1rem;
}

.rastreamento-content {
  padding: 0 1rem 1rem 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  min-height: 200px;
  max-height: 260px;
}

.rastreamento-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
  padding: 0.75rem;
  background-color: #f8fafc;
  border-radius: 0.5rem;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.stat-label {
  font-size: 0.625rem;
  color: #6b7280;
  margin-bottom: 0.125rem;
  line-height: 1.2;
}

.stat-value {
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
  line-height: 1;
}

.stat-value.em-transito {
  color: #2563eb;
}

.stat-value.entregue {
  color: #16a34a;
}

.stat-value.pendente {
  color: #d97706;
}

.tracking-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem 0;
}

.tracking-loading .loading-spinner {
  width: 1.5rem;
  height: 1.5rem;
  color: #2563eb;
  animation: spin 1s linear infinite;
}

.tracking-loading p {
  font-size: 0.875rem;
  color: #6b7280;
  margin: 0;
}

.rastreamentos-recentes {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.recentes-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: #374151;
  margin: 0 0 0.5rem 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.rastreamentos-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
  overflow-y: auto;
  max-height: 160px;
  padding-right: 0.25rem;
}

.rastreamentos-list::-webkit-scrollbar {
  width: 3px;
}

.rastreamentos-list::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 1.5px;
}

.rastreamentos-list::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 1.5px;
}

.rastreamentos-list::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.rastreamento-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem;
  background-color: white;
  border: 1px solid #e2e8f0;
  border-radius: 0.375rem;
  transition: all 0.15s ease;
}

.rastreamento-item:hover {
  border-color: #cbd5e1;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
}

.rastreamento-info {
  flex: 1;
  min-width: 0;
}

.rastreamento-codigo {
  font-size: 0.625rem;
  font-weight: 600;
  color: #111827;
  margin: 0 0 0.125rem 0;
  font-family: monospace;
  letter-spacing: 0.025em;
}

.rastreamento-cliente {
  font-size: 0.575rem;
  color: #64748b;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rastreamento-status {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

.copy-btn {
  width: 1rem;
  height: 1rem;
  border: none;
  background: none;
  cursor: pointer;
  color: #6b7280;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.25rem;
  padding: 0.125rem;
}

.copy-btn:hover {
  background-color: #f3f4f6;
  color: #374151;
}

.copy-btn svg {
  width: 0.75rem;
  height: 0.75rem;
}

.status-badge {
  font-size: 0.5rem;
  font-weight: 600;
  padding: 0.125rem 0.25rem;
  border-radius: 0.25rem;
  white-space: nowrap;
  text-transform: uppercase;
  letter-spacing: 0.025em;
}

.status-pendente {
  background-color: #f59e0b;
  color: white;
}

.status-em-transito {
  background-color: #3b82f6;
  color: white;
}

.status-entregue {
  background-color: #10b981;
  color: white;
}

.status-erro {
  background-color: #ef4444;
  color: white;
}

.empty-rastreamentos {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem 1rem;
  color: #9ca3af;
  text-align: center;
}

.empty-icon {
  width: 1.5rem;
  height: 1.5rem;
  opacity: 0.5;
}

.empty-text {
  font-size: 0.675rem;
  margin: 0;
  opacity: 0.8;
}

/* Modal Styles */
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

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  background-color: #f9fafb;
}

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

.form-actions {
  margin-top: 1rem;
  display: flex;
  justify-content: center;
}

.btn {
  padding: 0.75rem 1.5rem;
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

.btn-primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn-primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
}

.btn-secondary:hover {
  background-color: #e5e7eb;
}

.btn-consultar {
  background-color: #16a34a;
  color: white;
}

.btn-consultar:hover:not(:disabled) {
  background-color: #15803d;
}

.btn-consultar:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
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

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}


@media (max-width: 768px) {
  .rastreamento-stats {
    grid-template-columns: 1fr 1fr;
    gap: 0.5rem;
  }
  
  .stat-item {
    padding: 0.5rem;
  }
  
  .stat-value {
    font-size: 1rem;
  }
  
  .form-grid {
    grid-template-columns: 1fr;
  }
  
  .modal-content {
    margin: 0.5rem;
    max-height: 95vh;
  }
  
  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem;
  }
}
</style>