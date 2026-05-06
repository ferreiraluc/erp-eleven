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
        <div class="rstat rstat-total">
          <span class="rstat-num">{{ resumo?.total_rastreamentos || 0 }}</span>
          <span class="rstat-lbl">Total</span>
        </div>
        <div class="rstat rstat-transito">
          <span class="rstat-num">{{ resumo?.em_transito || 0 }}</span>
          <span class="rstat-lbl">Trânsito</span>
        </div>
        <div class="rstat rstat-entregue">
          <span class="rstat-num">{{ resumo?.entregues || 0 }}</span>
          <span class="rstat-lbl">Entregues</span>
        </div>
        <div class="rstat rstat-pendente">
          <span class="rstat-num">{{ resumo?.pendentes || 0 }}</span>
          <span class="rstat-lbl">Pendentes</span>
        </div>
      </div>
      
      <div v-if="resumo?.rastreamentos_recentes?.length" class="rastreamentos-recentes">
        <h4 class="recentes-title">Últimos Rastreamentos</h4>
        <div class="rastreamentos-list">
          <div
            v-for="rastreamento in resumo.rastreamentos_recentes"
            :key="rastreamento.id"
            class="track-card"
            :class="`track-${getStatusClass(rastreamento.status)}`"
          >
            <!-- Accent strip (left border via class) -->

            <!-- Top row: destinatário + status badge -->
            <div class="track-top">
              <span class="track-name">{{ rastreamento.destinatario || 'Sem destinatário' }}</span>
              <span class="track-badge" :class="getStatusClass(rastreamento.status)">
                {{ getStatusText(rastreamento.status) }}
              </span>
            </div>

            <!-- Code row: código monospace + serviço + botão copiar -->
            <div class="track-code-row">
              <span class="track-code">{{ rastreamento.codigo_rastreio }}</span>
              <span v-if="getBadgeText(rastreamento.rastreio_info)" class="track-service">
                {{ getBadgeText(rastreamento.rastreio_info) }}
              </span>
              <button
                @click.stop="copiarCodigo(rastreamento.codigo_rastreio)"
                class="track-copy"
                title="Copiar código"
              >
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              </button>
            </div>

            <!-- Last event -->
            <div v-if="rastreamento.historico_eventos?.length" class="track-event">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" class="track-event-icon">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"/>
              </svg>
              <span class="track-event-text">{{ rastreamento.historico_eventos[0]?.situacao }}</span>
            </div>

            <!-- Delivery estimate -->
            <div v-if="rastreamento.rastreio_info?.data_prevista" class="track-estimate">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" class="track-estimate-icon">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/>
              </svg>
              <span>Prev. {{ rastreamento.rastreio_info.data_prevista }}</span>
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

const getBadgeText = (info: any): string => {
  if (!info) return ''
  const tipo = info.tipo_servico || ''
  const match = tipo.match(/\(([^)]+)\)/)
  if (match) return match[1]
  return info.categoria || info.sigla || ''
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
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
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
  flex: 1;
  overflow: hidden;
}

.rastreamento-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.375rem;
}

.rstat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.5rem 0.25rem;
  border-radius: 0.5rem;
  gap: 0.125rem;
}

.rstat-num {
  font-size: 1.25rem;
  font-weight: 800;
  line-height: 1;
}

.rstat-lbl {
  font-size: 0.58rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  line-height: 1.2;
  text-align: center;
}

.rstat-total   { background: #f3f4f6; }
.rstat-total   .rstat-num { color: #111827; }
.rstat-total   .rstat-lbl { color: #6b7280; }

.rstat-transito { background: #dbeafe; }
.rstat-transito .rstat-num { color: #1d4ed8; }
.rstat-transito .rstat-lbl { color: #3b82f6; }

.rstat-entregue { background: #d1fae5; }
.rstat-entregue .rstat-num { color: #065f46; }
.rstat-entregue .rstat-lbl { color: #10b981; }

.rstat-pendente { background: #fef3c7; }
.rstat-pendente .rstat-num { color: #b45309; }
.rstat-pendente .rstat-lbl { color: #d97706; }

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
  min-height: 0;
}

.recentes-title {
  font-size: 0.65rem;
  font-weight: 700;
  color: #9ca3af;
  margin: 0 0 0.5rem;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.rastreamentos-list {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding-right: 0.25rem;
}

.rastreamentos-list::-webkit-scrollbar { width: 3px; }
.rastreamentos-list::-webkit-scrollbar-track { background: #f1f5f9; border-radius: 2px; }
.rastreamentos-list::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 2px; }
.rastreamentos-list::-webkit-scrollbar-thumb:hover { background: #94a3b8; }

/* ── Track card ──────────────────────────────────────────── */
.track-card {
  position: relative;
  background: white;
  border: 1px solid #e5e7eb;
  border-left-width: 3px;
  border-radius: 0.5rem;
  padding: 0.5rem 0.625rem 0.45rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  transition: box-shadow 0.15s, transform 0.15s;
}
.track-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  transform: translateY(-1px);
}

/* Status accent colors */
.track-card.status-pendente    { border-left-color: #f59e0b; background: #fffdf5; }
.track-card.status-em-transito { border-left-color: #3b82f6; background: #f8fbff; }
.track-card.status-entregue    { border-left-color: #10b981; background: #f5fdf8; }
.track-card.status-erro        { border-left-color: #ef4444; background: #fff8f8; }

/* Top row */
.track-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.track-name {
  font-size: 0.8rem;
  font-weight: 700;
  color: #111827;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.track-badge {
  font-size: 0.6rem;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: 99px;
  white-space: nowrap;
  flex-shrink: 0;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.track-badge.status-pendente    { background: #fef3c7; color: #b45309; }
.track-badge.status-em-transito { background: #dbeafe; color: #1d4ed8; }
.track-badge.status-entregue    { background: #d1fae5; color: #065f46; }
.track-badge.status-erro        { background: #fee2e2; color: #b91c1c; }

/* Code row */
.track-code-row {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.track-code {
  font-family: 'SF Mono', 'Fira Mono', monospace;
  font-size: 0.7rem;
  font-weight: 600;
  color: #374151;
  letter-spacing: 0.04em;
  flex: 1;
  min-width: 0;
}

.track-service {
  font-size: 0.55rem;
  font-weight: 800;
  background: #e0e7ff;
  color: #3730a3;
  padding: 0.1rem 0.35rem;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  flex-shrink: 0;
}

.track-copy {
  width: 1.375rem;
  height: 1.375rem;
  border: none;
  background: #f3f4f6;
  cursor: pointer;
  color: #9ca3af;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.25rem;
  flex-shrink: 0;
  transition: background 0.15s, color 0.15s;
}
.track-copy:hover { background: #e5e7eb; color: #374151; }
.track-copy svg { width: 0.7rem; height: 0.7rem; }

/* Last event */
.track-event {
  display: flex;
  align-items: flex-start;
  gap: 0.25rem;
  margin-top: 0.05rem;
}
.track-event-icon {
  width: 0.7rem;
  height: 0.7rem;
  color: #6b7280;
  flex-shrink: 0;
  margin-top: 0.05rem;
}
.track-event-text {
  font-size: 0.7rem;
  color: #4b5563;
  line-height: 1.3;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* Delivery estimate */
.track-estimate {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}
.track-estimate-icon {
  width: 0.65rem;
  height: 0.65rem;
  color: #9ca3af;
  flex-shrink: 0;
}
.track-estimate {
  font-size: 0.65rem;
  color: #9ca3af;
}

/* Status badge (old — kept for backwards compat, unused in new card) */
.status-pendente    { }
.status-em-transito { }
.status-entregue    { }
.status-erro        { }

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