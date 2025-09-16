<template>
  <div class="pedido-card" @click="$emit('view', pedido)">
    <!-- Header -->
    <div class="card-header">
      <div class="header-left">
        <span class="numero-pedido">{{ pedido.numero_pedido }}</span>
        <span :class="['status-badge', getStatusClass(pedido.status)]">
          {{ getStatusLabel(pedido.status) }}
        </span>
      </div>
      <div class="header-right">
        <button
          @click.stop="$emit('edit', pedido)"
          class="action-btn edit-btn"
          title="Editar pedido"
        >
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Pedido Info -->
    <div class="pedido-section">
      <div class="pedido-info">
        <h3 class="pedido-descricao">{{ pedido.descricao }}</h3>
        <div class="pedido-details">
          <div class="detail-item">
            <svg class="detail-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1" />
            </svg>
            <span class="valor-total">R$ {{ formatCurrency(pedido.valor_total) }}</span>
          </div>
          <div v-if="pedido.cliente_nome" class="detail-item">
            <svg class="detail-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            <span>{{ pedido.cliente_nome }}</span>
          </div>
          <div v-if="pedido.cliente_telefone" class="detail-item">
            <svg class="detail-icon" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21L6.16 10.81a11.058 11.058 0 004.999 4.999l1.433-3.064a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            <span>{{ formatPhone(pedido.cliente_telefone) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Tags -->
    <div v-if="pedido.tags && pedido.tags.length > 0" class="tags-section">
      <div class="tags-container">
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

    <!-- Progress Info -->
    <div class="progress-section">
      <div class="date-info">
        <span class="date-label">Criado em:</span>
        <span class="date-value">{{ formatDate(pedido.created_at) }}</span>
      </div>

      <!-- Rastreamento Button -->
      <button
        v-if="pedido.codigo_rastreio"
        @click.stop="$emit('track', pedido)"
        class="track-btn has-tracking"
        title="Ver rastreamento"
      >
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        Rastreado
      </button>
      <button
        v-else
        @click.stop="$emit('track', pedido)"
        class="track-btn no-tracking"
        title="Criar rastreamento"
      >
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
        Rastrear
      </button>
    </div>

    <!-- Footer -->
    <div class="card-footer">
      <div class="footer-left">
        <span class="last-update">
          Atualizado: {{ formatDate(pedido.updated_at) }}
        </span>
      </div>
      <div class="footer-right">
        <button
          @click.stop="$emit('view', pedido)"
          class="view-btn"
        >
          Ver detalhes
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Tag {
  id: string
  nome: string
  cor: string
  ordem: string
}

interface Pedido {
  id: string
  numero_pedido: string
  descricao: string
  valor_total: number
  cliente_nome?: string
  cliente_telefone?: string
  cliente_email?: string
  endereco_entrega?: string
  status: string
  codigo_rastreio?: string
  created_at: string
  updated_at: string
  tags: Tag[]
}

interface Props {
  pedido: Pedido
}

defineProps<Props>()

defineEmits<{
  edit: [pedido: Pedido]
  view: [pedido: Pedido]
  track: [pedido: Pedido]
}>()

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric'
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
  return new Intl.NumberFormat('pt-BR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
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
</script>

<style scoped>
.pedido-card {
  background: white;
  border-radius: 0.75rem;
  padding: 1.5rem;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
  border: 1px solid #e5e7eb;
  cursor: pointer;
  transition: all 0.2s ease;
  height: fit-content;
}

.pedido-card:hover {
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  border-color: #d1d5db;
  transform: translateY(-1px);
}

/* Header */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #f3f4f6;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.numero-pedido {
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
  background-color: #eff6ff;
  color: #2563eb;
  padding: 0.25rem 0.75rem;
  border-radius: 0.5rem;
  width: fit-content;
}

.status-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 9999px;
  font-size: 0.75rem;
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

.header-right {
  display: flex;
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

/* Pedido Section */
.pedido-section {
  margin-bottom: 1rem;
}

.pedido-descricao {
  margin: 0 0 0.5rem 0;
  font-size: 1rem;
  font-weight: 600;
  color: #111827;
  line-height: 1.4;
}

.pedido-details {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.valor-total {
  font-weight: 600;
  color: #059669;
}

.detail-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: #6b7280;
}

.detail-icon {
  width: 1rem;
  height: 1rem;
  color: #9ca3af;
  flex-shrink: 0;
}

/* Tags Section */
.tags-section {
  margin-bottom: 1rem;
}

.tags-container {
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

/* Progress Section */
.progress-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #f3f4f6;
}

.date-info {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.date-label {
  font-size: 0.75rem;
  color: #6b7280;
}

.date-value {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.track-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: none;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.track-btn svg {
  width: 1rem;
  height: 1rem;
}

.track-btn.has-tracking {
  background-color: #dcfce7;
  color: #166534;
}

.track-btn.has-tracking:hover {
  background-color: #bbf7d0;
}

.track-btn.no-tracking {
  background-color: #fef3c7;
  color: #92400e;
}

.track-btn.no-tracking:hover {
  background-color: #fde68a;
}

/* Footer */
.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.last-update {
  font-size: 0.75rem;
  color: #9ca3af;
}

.view-btn {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.75rem;
  background-color: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 0.375rem;
  font-size: 0.75rem;
  font-weight: 500;
  color: #374151;
  cursor: pointer;
  transition: all 0.2s;
}

.view-btn:hover {
  background-color: #f3f4f6;
  border-color: #d1d5db;
}

.view-btn svg {
  width: 0.875rem;
  height: 0.875rem;
}

/* Responsive */
@media (max-width: 640px) {
  .pedido-card {
    padding: 1rem;
  }

  .numero-pedido {
    font-size: 1rem;
  }

  .pedido-descricao {
    font-size: 0.875rem;
  }

  .progress-section {
    flex-direction: column;
    gap: 0.75rem;
    align-items: stretch;
  }

  .track-btn {
    justify-content: center;
  }

  .card-footer {
    flex-direction: column;
    gap: 0.75rem;
    align-items: stretch;
  }

  .view-btn {
    justify-content: center;
  }
}
</style>