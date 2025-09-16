<template>
  <div class="modal-overlay" @click="$emit('close')">
    <div class="modal-container" @click.stop>
      <div class="modal-header">
        <div class="header-info">
          <h2 class="modal-title">Detalhes do Pedido</h2>
          <span class="pedido-number">{{ pedido.numero_pedido }}</span>
        </div>
        <div class="header-actions">
          <button @click="$emit('edit', pedido)" class="edit-btn">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Editar
          </button>
          <button @click="$emit('close')" class="modal-close">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div class="modal-body">
        <!-- Status and Tags -->
        <div class="status-section">
          <div class="status-info">
            <span :class="['status-badge', getStatusClass(pedido.status)]">
              {{ getStatusLabel(pedido.status) }}
            </span>
            <div v-if="pedido.tags && pedido.tags.length > 0" class="tags-display">
              <span
                v-for="tag in pedido.tags"
                :key="tag.id"
                class="tag-badge"
                :style="{
                  backgroundColor: tag.cor + '20',
                  borderColor: tag.cor,
                  color: tag.cor
                }"
              >
                {{ tag.nome }}
              </span>
            </div>
          </div>
          <div class="dates-info">
            <div class="date-item">
              <span class="date-label">Criado:</span>
              <span class="date-value">{{ formatDate(pedido.created_at) }}</span>
            </div>
            <div class="date-item">
              <span class="date-label">Atualizado:</span>
              <span class="date-value">{{ formatDate(pedido.updated_at) }}</span>
            </div>
          </div>
        </div>

        <!-- Descrição do Pedido -->
        <div class="info-section">
          <h3 class="section-title">Descrição do Pedido</h3>
          <div class="description-display">
            <p class="description-text">{{ pedido.descricao }}</p>
            <div class="valor-info">
              <span class="valor-label">Valor Total:</span>
              <span class="valor-value">R$ {{ formatCurrency(pedido.valor_total) }}</span>
            </div>
          </div>
        </div>

        <!-- Cliente Info (Opcional) -->
        <div v-if="pedido.cliente_nome || pedido.cliente_telefone || pedido.cliente_email" class="info-section">
          <h3 class="section-title">Dados do Cliente</h3>
          <div class="info-grid">
            <div v-if="pedido.cliente_nome" class="info-item">
              <span class="info-label">Nome:</span>
              <span class="info-value">{{ pedido.cliente_nome }}</span>
            </div>
            <div v-if="pedido.cliente_telefone" class="info-item">
              <span class="info-label">Telefone:</span>
              <span class="info-value">{{ formatPhone(pedido.cliente_telefone) }}</span>
            </div>
            <div v-if="pedido.cliente_email" class="info-item">
              <span class="info-label">E-mail:</span>
              <span class="info-value">{{ pedido.cliente_email }}</span>
            </div>
          </div>
        </div>

        <!-- Endereço (Opcional) -->
        <div v-if="pedido.endereco_entrega" class="info-section">
          <h3 class="section-title">Endereço de Entrega</h3>
          <div class="address-display">
            <div class="address-line">{{ pedido.endereco_entrega }}</div>
          </div>
        </div>

        <!-- Rastreamento -->
        <div v-if="pedido.codigo_rastreio" class="info-section">
          <h3 class="section-title">Rastreamento</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">Código de Rastreio:</span>
              <span class="info-value tracking-code">{{ pedido.codigo_rastreio }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="createRastreamento" class="btn-secondary">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {{ pedido.codigo_rastreio ? 'Ver Rastreamento' : 'Criar Rastreamento' }}
        </button>
        <button @click="$emit('edit', pedido)" class="btn-primary">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
          Editar Pedido
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import type { Pedido } from '@/services/api'

interface Props {
  pedido: Pedido
}

const props = defineProps<Props>()

defineEmits<{
  close: []
  edit: [pedido: Pedido]
}>()

const router = useRouter()

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

const formatPhone = (phone: string) => {
  // Format Brazilian phone number
  if (phone.length === 11) {
    return phone.replace(/(\d{2})(\d{5})(\d{4})/, '($1) $2-$3')
  } else if (phone.length === 10) {
    return phone.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2-$3')
  }
  return phone
}

const formatCurrency = (value: number) => {
  return value.toLocaleString('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
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


const createRastreamento = () => {
  router.push({
    name: 'rastreamento',
    query: { pedido_id: props.pedido.id }
  })
}
</script>

<style scoped>
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

.modal-container {
  background: white;
  border-radius: 0.75rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.modal-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  color: #111827;
}

.pedido-number {
  font-size: 0.875rem;
  color: #6b7280;
  font-weight: 500;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.edit-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  background-color: #eff6ff;
  color: #2563eb;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.edit-btn:hover {
  background-color: #dbeafe;
}

.edit-btn svg {
  width: 1rem;
  height: 1rem;
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
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.status-section {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  padding: 1rem;
  background-color: #f9fafb;
  border-radius: 0.5rem;
}

.status-info {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.status-badge {
  padding: 0.5rem 1rem;
  border-radius: 9999px;
  font-size: 0.875rem;
  font-weight: 500;
  width: fit-content;
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

.tags-display {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.tag-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  border: 1px solid;
}

.dates-info {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  text-align: right;
}

.date-item {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.date-label {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
}

.date-value {
  font-size: 0.875rem;
  color: #374151;
}

.info-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 0.5rem;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.info-label {
  font-size: 0.75rem;
  color: #6b7280;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.info-value {
  font-size: 0.875rem;
  color: #111827;
  font-weight: 500;
}

.tracking-code {
  font-family: 'Courier New', monospace;
  background-color: #f3f4f6;
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  font-size: 0.75rem;
}

.address-display {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 1rem;
  background-color: #f9fafb;
  border-radius: 0.5rem;
  border-left: 3px solid #2563eb;
}

.address-line {
  font-size: 0.875rem;
  color: #374151;
  line-height: 1.4;
}

.observation-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.observation-label {
  font-size: 0.875rem;
  font-weight: 600;
  color: #374151;
}

.observation-text {
  margin: 0;
  font-size: 0.875rem;
  color: #6b7280;
  line-height: 1.5;
  padding: 0.75rem;
  background-color: #f9fafb;
  border-radius: 0.5rem;
  border-left: 3px solid #d1d5db;
}

.description-display {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background-color: #f9fafb;
  border-radius: 0.5rem;
  border-left: 3px solid #2563eb;
}

.description-text {
  margin: 0;
  font-size: 1rem;
  color: #374151;
  line-height: 1.5;
  font-weight: 500;
}

.valor-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem;
  background-color: white;
  border-radius: 0.5rem;
  border: 1px solid #e5e7eb;
}

.valor-label {
  font-size: 0.875rem;
  color: #6b7280;
  font-weight: 500;
}

.valor-value {
  font-size: 1.25rem;
  color: #059669;
  font-weight: 700;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background-color: #2563eb;
  color: white;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-primary:hover {
  background-color: #1d4ed8;
}

.btn-primary svg {
  width: 1rem;
  height: 1rem;
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background-color: #f3f4f6;
  color: #374151;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background-color: #e5e7eb;
}

.btn-secondary svg {
  width: 1rem;
  height: 1rem;
}

/* Responsive */
@media (max-width: 768px) {
  .modal-overlay {
    padding: 0.5rem;
  }

  .modal-container {
    max-height: 95vh;
  }

  .modal-header,
  .modal-body,
  .modal-footer {
    padding: 1rem;
  }

  .status-section {
    flex-direction: column;
    gap: 1rem;
  }

  .dates-info {
    text-align: left;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .modal-footer {
    flex-direction: column;
  }

  .header-actions {
    flex-direction: column;
  }
}
</style>