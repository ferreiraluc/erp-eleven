<template>
  <div v-if="isVisible" class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-container" @click.stop>
      <div class="modal-header">
        <h2 class="modal-title">
          {{ isEditing ? 'Editar Pedido' : 'Novo Pedido' }}
        </h2>
        <button @click="closeModal" class="modal-close">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <form @submit.prevent="handleSubmit" class="pedido-form">
          <!-- Pedido Section -->
          <div class="form-section">
            <h3 class="section-title">Informações do Pedido</h3>
            <div class="form-row">
              <div class="form-group required full-width">
                <label for="descricao">Descrição dos Itens</label>
                <textarea
                  id="descricao"
                  v-model="formData.descricao"
                  required
                  placeholder="Ex: 1 tênis Nike Air Max + 3 camisetas básicas"
                  rows="3"
                  class="form-textarea"
                ></textarea>
              </div>
            </div>
            <div class="form-row">
              <div class="form-group required">
                <label for="valor_total">Valor Total (R$)</label>
                <input
                  id="valor_total"
                  v-model="formData.valor_total"
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  placeholder="0,00"
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label for="status">Status</label>
                <select
                  id="status"
                  v-model="formData.status"
                  class="form-select"
                >
                  <option value="PENDENTE">Pendente</option>
                  <option value="PROCESSANDO">Processando</option>
                  <option value="ENVIADO">Enviado</option>
                  <option value="ENTREGUE">Entregue</option>
                  <option value="CANCELADO">Cancelado</option>
                </select>
              </div>
              <div class="form-group">
                <label for="codigo_rastreio">Código de Rastreio</label>
                <input
                  id="codigo_rastreio"
                  v-model="formData.codigo_rastreio"
                  type="text"
                  placeholder="BR123456789BR"
                  class="form-input"
                />
              </div>
            </div>
          </div>

          <!-- Cliente Section (Opcional) -->
          <div class="form-section">
            <h3 class="section-title">Dados do Cliente (Opcional)</h3>
            <div class="form-row">
              <div class="form-group">
                <label for="cliente_nome">Nome do Cliente</label>
                <input
                  id="cliente_nome"
                  v-model="formData.cliente_nome"
                  type="text"
                  placeholder="Nome completo do cliente"
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label for="cliente_telefone">Telefone</label>
                <input
                  id="cliente_telefone"
                  v-model="formData.cliente_telefone"
                  type="tel"
                  placeholder="(11) 99999-9999"
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label for="cliente_email">E-mail</label>
                <input
                  id="cliente_email"
                  v-model="formData.cliente_email"
                  type="email"
                  placeholder="cliente@email.com"
                  class="form-input"
                />
              </div>
            </div>
          </div>

          <!-- Endereço Section (Opcional) -->
          <div class="form-section">
            <h3 class="section-title">Endereço de Entrega (Opcional)</h3>
            <div class="form-row">
              <div class="form-group full-width">
                <label for="endereco_entrega">Endereço Completo</label>
                <textarea
                  id="endereco_entrega"
                  v-model="formData.endereco_entrega"
                  placeholder="Rua, número, bairro, cidade, estado, CEP"
                  rows="2"
                  class="form-textarea"
                ></textarea>
              </div>
            </div>
          </div>

          <!-- Tags Section -->
          <div class="form-section">
            <div class="section-header">
              <h3 class="section-title">Tags de Status</h3>
              <button
                type="button"
                @click="openTagManager"
                class="btn-secondary btn-small"
              >
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                </svg>
                Nova Tag
              </button>
            </div>

            <div v-if="tags.length > 0" class="tags-grid">
              <label
                v-for="tag in tags"
                :key="tag.id"
                class="tag-checkbox"
                :style="{
                  borderColor: selectedTags.includes(tag.id) ? tag.cor : '#e5e7eb',
                  backgroundColor: selectedTags.includes(tag.id) ? tag.cor + '10' : 'transparent'
                }"
              >
                <input
                  type="checkbox"
                  :value="tag.id"
                  v-model="selectedTags"
                  class="tag-input"
                />
                <span
                  class="tag-label"
                  :style="{ color: selectedTags.includes(tag.id) ? tag.cor : '#374151' }"
                >
                  {{ tag.nome }}
                </span>
                <span
                  class="tag-color"
                  :style="{ backgroundColor: tag.cor }"
                ></span>
              </label>
            </div>
            <p v-else class="no-tags">
              Nenhuma tag disponível.
              <button type="button" @click="createDefaultTags" class="link-button">
                Criar tags padrão
              </button>
            </p>
          </div>

        </form>
      </div>

      <div class="modal-footer">
        <button type="button" @click="closeModal" class="btn-secondary">
          Cancelar
        </button>
        <button
          type="button"
          @click="handleSubmit"
          :disabled="isSubmitting || !isFormValid"
          class="btn-primary"
        >
          <svg v-if="isSubmitting" class="loading-icon" fill="none" viewBox="0 0 24 24">
            <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          {{ isSubmitting ? 'Salvando...' : (isEditing ? 'Atualizar' : 'Criar Pedido') }}
        </button>
      </div>
    </div>

    <!-- Tag Manager Modal -->
    <TagManagerModal
      v-if="showTagManager"
      @close="closeTagManager"
      @tag-created="handleTagCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { pedidosAPI, tagsAPI, type Pedido, type PedidoCreate, type Tag } from '@/services/api'
import TagManagerModal from './TagManagerModal.vue'

interface Props {
  isVisible: boolean
  pedido?: Pedido | null
}

const props = withDefaults(defineProps<Props>(), {
  pedido: null
})

const emit = defineEmits<{
  close: []
  saved: [pedido: Pedido]
}>()

// State
const isSubmitting = ref(false)
const tags = ref<Tag[]>([])
const selectedTags = ref<string[]>([])
const showTagManager = ref(false)

// Form data
const formData = ref<PedidoCreate>({
  descricao: '',
  valor_total: 0,
  cliente_nome: '',
  cliente_telefone: '',
  cliente_email: '',
  endereco_entrega: '',
  status: 'PENDENTE',
  codigo_rastreio: ''
})


// Computed
const isEditing = computed(() => !!props.pedido)

const isFormValid = computed(() => {
  return !!(
    formData.value.descricao &&
    formData.value.valor_total > 0
  )
})

// Methods
const resetForm = () => {
  formData.value = {
    descricao: '',
    valor_total: 0,
    cliente_nome: '',
    cliente_telefone: '',
    cliente_email: '',
    endereco_entrega: '',
    status: 'PENDENTE',
    codigo_rastreio: ''
  }
  selectedTags.value = []
}

const loadFormData = () => {
  if (props.pedido) {
    formData.value = {
      descricao: props.pedido.descricao,
      valor_total: props.pedido.valor_total,
      cliente_nome: props.pedido.cliente_nome || '',
      cliente_telefone: props.pedido.cliente_telefone || '',
      cliente_email: props.pedido.cliente_email || '',
      endereco_entrega: props.pedido.endereco_entrega || '',
      status: props.pedido.status,
      codigo_rastreio: props.pedido.codigo_rastreio || ''
    }
    selectedTags.value = props.pedido.tags.map(tag => tag.id)
  } else {
    resetForm()
  }
}

const loadTags = async () => {
  try {
    tags.value = await tagsAPI.getAll()
  } catch (error) {
    console.error('Erro ao carregar tags:', error)
  }
}

const createDefaultTags = async () => {
  try {
    await tagsAPI.createDefaultTags()
    await loadTags()
  } catch (error) {
    console.error('Erro ao criar tags padrão:', error)
  }
}


const handleSubmit = async () => {
  if (!isFormValid.value || isSubmitting.value) return

  try {
    isSubmitting.value = true

    const submitData = {
      ...formData.value,
      tag_ids: selectedTags.value
    }

    let result: Pedido

    if (isEditing.value && props.pedido) {
      result = await pedidosAPI.update(props.pedido.id, submitData)
    } else {
      result = await pedidosAPI.create(submitData)
    }

    emit('saved', result)
    closeModal()
  } catch (error) {
    console.error('Erro ao salvar pedido:', error)
  } finally {
    isSubmitting.value = false
  }
}

const closeModal = () => {
  resetForm()
  emit('close')
}

const handleOverlayClick = () => {
  closeModal()
}

const openTagManager = () => {
  showTagManager.value = true
}

const closeTagManager = () => {
  showTagManager.value = false
}

const handleTagCreated = () => {
  loadTags()
}

// Watchers
watch(() => props.isVisible, (visible) => {
  if (visible) {
    loadFormData()
    loadTags()
  }
})

// Lifecycle
onMounted(() => {
  if (props.isVisible) {
    loadTags()
  }
})
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
  max-width: 800px;
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

.modal-title {
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
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 0.75rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.pedido-form {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.section-title {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 0.5rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 1rem;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.form-group.flex-2 {
  grid-column: span 2;
}

.form-group.full-width {
  grid-column: span 3;
}

.form-group.required label::after {
  content: ' *';
  color: #ef4444;
}

.form-group label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.form-input,
.form-select,
.form-textarea {
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.875rem;
  transition: border-color 0.2s;
}

.form-input:focus,
.form-select:focus,
.form-textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-textarea {
  resize: vertical;
  min-height: 80px;
}

.tags-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 0.75rem;
}

.tag-checkbox {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border: 2px solid;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-checkbox:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.tag-input {
  margin: 0;
  width: 1rem;
  height: 1rem;
}

.tag-label {
  flex: 1;
  font-size: 0.875rem;
  font-weight: 500;
}

.tag-color {
  width: 1rem;
  height: 1rem;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.1);
}

.no-tags {
  text-align: center;
  color: #6b7280;
  font-size: 0.875rem;
  padding: 2rem;
  border: 2px dashed #d1d5db;
  border-radius: 0.5rem;
}

.link-button {
  background: none;
  border: none;
  color: #2563eb;
  text-decoration: underline;
  cursor: pointer;
  font-size: inherit;
}

.link-button:hover {
  color: #1d4ed8;
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

.btn-primary:hover:not(:disabled) {
  background-color: #1d4ed8;
}

.btn-primary:disabled {
  background-color: #9ca3af;
  cursor: not-allowed;
}

.btn-secondary {
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

.btn-small {
  padding: 0.5rem 0.75rem;
  font-size: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.btn-small svg {
  width: 1rem;
  height: 1rem;
}

.loading-icon {
  width: 1rem;
  height: 1rem;
  animation: spin 1s linear infinite;
}

.spinner-track {
  opacity: 0.25;
}

.spinner-path {
  opacity: 0.75;
}

@keyframes spin {
  to { transform: rotate(360deg); }
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

  .form-row {
    grid-template-columns: 1fr;
  }

  .form-group.flex-2,
  .form-group.full-width {
    grid-column: span 1;
  }

  .tags-grid {
    grid-template-columns: 1fr;
  }

  .modal-footer {
    flex-direction: column;
  }
}
</style>