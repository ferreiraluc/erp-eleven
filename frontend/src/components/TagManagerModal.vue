<template>
  <div class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-container" @click.stop>
      <div class="modal-header">
        <h2 class="modal-title">Gerenciar Tags</h2>
        <button @click="$emit('close')" class="modal-close">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <!-- Create New Tag Form -->
        <div class="create-tag-section">
          <h3 class="section-title">Criar Nova Tag</h3>
          <form @submit.prevent="createTag" class="tag-form">
            <div class="form-row">
              <div class="form-group">
                <label for="nome">Nome da Tag</label>
                <input
                  id="nome"
                  v-model="newTag.nome"
                  type="text"
                  required
                  placeholder="Ex: Separado, Pago, Enviado..."
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label for="cor">Cor</label>
                <div class="color-input-container">
                  <input
                    id="cor"
                    v-model="newTag.cor"
                    type="color"
                    class="color-input"
                  />
                  <input
                    v-model="newTag.cor"
                    type="text"
                    placeholder="#FF0000"
                    class="form-input color-text"
                  />
                </div>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group flex-2">
                <label for="descricao">Descrição (opcional)</label>
                <input
                  id="descricao"
                  v-model="newTag.descricao"
                  type="text"
                  placeholder="Descrição da tag..."
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label for="ordem">Ordem</label>
                <input
                  id="ordem"
                  v-model="newTag.ordem"
                  type="number"
                  min="1"
                  max="100"
                  placeholder="10"
                  class="form-input"
                />
              </div>
            </div>

            <div class="form-actions">
              <button
                type="submit"
                :disabled="!newTag.nome || isCreating"
                class="btn-primary"
              >
                <svg v-if="isCreating" class="loading-icon" fill="none" viewBox="0 0 24 24">
                  <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                {{ isCreating ? 'Criando...' : 'Criar Tag' }}
              </button>
            </div>

            <!-- Preview -->
            <div v-if="newTag.nome" class="tag-preview">
              <span class="preview-label">Preview:</span>
              <span
                class="tag-badge preview"
                :style="{
                  backgroundColor: newTag.cor + '20',
                  borderColor: newTag.cor,
                  color: newTag.cor
                }"
              >
                {{ newTag.nome }}
              </span>
            </div>
          </form>
        </div>

        <!-- Existing Tags List -->
        <div class="tags-list-section">
          <h3 class="section-title">Tags Existentes</h3>

          <div v-if="isLoading" class="loading-container">
            <div class="loading-spinner"></div>
            <p>Carregando tags...</p>
          </div>

          <div v-else-if="tags.length === 0" class="empty-state">
            <p>Nenhuma tag encontrada.</p>
          </div>

          <div v-else class="tags-grid">
            <div
              v-for="tag in tags"
              :key="tag.id"
              class="tag-item"
              :class="{ inactive: !tag.ativo }"
            >
              <div class="tag-info">
                <span
                  class="tag-badge"
                  :style="{
                    backgroundColor: tag.cor + '20',
                    borderColor: tag.cor,
                    color: tag.cor
                  }"
                >
                  {{ tag.nome }}
                </span>
                <div class="tag-details">
                  <span class="tag-description">{{ tag.descricao || 'Sem descrição' }}</span>
                  <span class="tag-order">Ordem: {{ tag.ordem }}</span>
                </div>
              </div>

              <div class="tag-actions">
                <button
                  @click="editTag(tag)"
                  class="action-btn edit-btn"
                  title="Editar tag"
                >
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </button>
                <button
                  @click="toggleTagStatus(tag)"
                  :class="['action-btn', tag.ativo ? 'deactivate-btn' : 'activate-btn']"
                  :title="tag.ativo ? 'Desativar tag' : 'Ativar tag'"
                >
                  <svg v-if="tag.ativo" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.878 9.878L3 3m6.878 6.878L12 12m-3-3l6.364 6.364M21 21l-3-3m0 0a10.05 10.05 0 01-8.098-2.879m4.616-4.616a3 3 0 00-4.243-4.243m0 0a9.968 9.968 0 00-1.563 3.029M12 12l-3-3" />
                  </svg>
                  <svg v-else fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                </button>
                <button
                  @click="deleteTag(tag)"
                  class="action-btn delete-btn"
                  title="Excluir tag"
                >
                  <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="createDefaultTags" class="btn-secondary">
          Criar Tags Padrão
        </button>
        <button @click="$emit('close')" class="btn-primary">
          Fechar
        </button>
      </div>
    </div>

    <!-- Edit Tag Modal -->
    <div v-if="editingTag" class="modal-overlay edit-overlay" @click="cancelEdit">
      <div class="modal-container edit-modal" @click.stop>
        <div class="modal-header">
          <h3 class="modal-title">Editar Tag</h3>
          <button @click="cancelEdit" class="modal-close">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="modal-body">
          <form @submit.prevent="updateTag" class="tag-form">
            <div class="form-row">
              <div class="form-group">
                <label for="edit-nome">Nome da Tag</label>
                <input
                  id="edit-nome"
                  v-model="editForm.nome"
                  type="text"
                  required
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label for="edit-cor">Cor</label>
                <div class="color-input-container">
                  <input
                    id="edit-cor"
                    v-model="editForm.cor"
                    type="color"
                    class="color-input"
                  />
                  <input
                    v-model="editForm.cor"
                    type="text"
                    class="form-input color-text"
                  />
                </div>
              </div>
            </div>

            <div class="form-row">
              <div class="form-group flex-2">
                <label for="edit-descricao">Descrição</label>
                <input
                  id="edit-descricao"
                  v-model="editForm.descricao"
                  type="text"
                  class="form-input"
                />
              </div>
              <div class="form-group">
                <label for="edit-ordem">Ordem</label>
                <input
                  id="edit-ordem"
                  v-model="editForm.ordem"
                  type="number"
                  min="1"
                  max="100"
                  class="form-input"
                />
              </div>
            </div>

            <!-- Preview -->
            <div class="tag-preview">
              <span class="preview-label">Preview:</span>
              <span
                class="tag-badge preview"
                :style="{
                  backgroundColor: editForm.cor + '20',
                  borderColor: editForm.cor,
                  color: editForm.cor
                }"
              >
                {{ editForm.nome }}
              </span>
            </div>
          </form>
        </div>

        <div class="modal-footer">
          <button @click="cancelEdit" class="btn-secondary">
            Cancelar
          </button>
          <button
            @click="updateTag"
            :disabled="!editForm.nome || isUpdating"
            class="btn-primary"
          >
            <svg v-if="isUpdating" class="loading-icon" fill="none" viewBox="0 0 24 24">
              <circle class="spinner-track" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="spinner-path" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isUpdating ? 'Salvando...' : 'Salvar' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { tagsAPI, type Tag, type TagCreate } from '@/services/api'

defineEmits<{
  close: []
  tagCreated: []
}>()

// State
const tags = ref<Tag[]>([])
const isLoading = ref(true)
const isCreating = ref(false)
const isUpdating = ref(false)
const editingTag = ref<Tag | null>(null)

// Forms
const newTag = ref<TagCreate>({
  nome: '',
  cor: '#6366F1',
  descricao: '',
  ordem: '50'
})

const editForm = ref<TagCreate>({
  nome: '',
  cor: '#6366F1',
  descricao: '',
  ordem: '50'
})

// Methods
const loadTags = async () => {
  try {
    isLoading.value = true
    tags.value = await tagsAPI.getAll(0, 100, false) // Include inactive tags
  } catch (error) {
    console.error('Erro ao carregar tags:', error)
  } finally {
    isLoading.value = false
  }
}

const createTag = async () => {
  if (!newTag.value.nome || isCreating.value) return

  try {
    isCreating.value = true
    await tagsAPI.create(newTag.value)

    // Reset form
    newTag.value = {
      nome: '',
      cor: '#6366F1',
      descricao: '',
      ordem: '50'
    }

    // Reload tags
    await loadTags()
  } catch (error) {
    console.error('Erro ao criar tag:', error)
  } finally {
    isCreating.value = false
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

const editTag = (tag: Tag) => {
  editingTag.value = tag
  editForm.value = {
    nome: tag.nome,
    cor: tag.cor,
    descricao: tag.descricao || '',
    ordem: tag.ordem
  }
}

const cancelEdit = () => {
  editingTag.value = null
  editForm.value = {
    nome: '',
    cor: '#6366F1',
    descricao: '',
    ordem: '50'
  }
}

const updateTag = async () => {
  if (!editingTag.value || !editForm.value.nome || isUpdating.value) return

  try {
    isUpdating.value = true
    await tagsAPI.update(editingTag.value.id, editForm.value)
    await loadTags()
    cancelEdit()
  } catch (error) {
    console.error('Erro ao atualizar tag:', error)
  } finally {
    isUpdating.value = false
  }
}

const toggleTagStatus = async (tag: Tag) => {
  try {
    await tagsAPI.update(tag.id, { ativo: !tag.ativo })
    await loadTags()
  } catch (error) {
    console.error('Erro ao alterar status da tag:', error)
  }
}

const deleteTag = async (tag: Tag) => {
  if (!confirm(`Tem certeza que deseja excluir a tag "${tag.nome}"?`)) return

  try {
    await tagsAPI.delete(tag.id)
    await loadTags()
  } catch (error) {
    console.error('Erro ao excluir tag:', error)
  }
}

const handleOverlayClick = () => {
  // Only close if not editing a tag
  if (!editingTag.value) {
    // Don't auto-close, let user click close button
  }
}

// Lifecycle
onMounted(loadTags)
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
  z-index: 1001;
  padding: 1rem;
}

.edit-overlay {
  z-index: 1002;
}

.modal-container {
  background: white;
  border-radius: 0.75rem;
  box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
  max-width: 600px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.edit-modal {
  max-width: 500px;
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
  justify-content: space-between;
  gap: 0.75rem;
  padding: 1.5rem;
  border-top: 1px solid #e5e7eb;
  flex-shrink: 0;
}

.create-tag-section,
.tags-list-section {
  margin-bottom: 2rem;
}

.section-title {
  margin: 0 0 1rem 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: #111827;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 0.5rem;
}

.tag-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
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

.color-input-container {
  display: flex;
  gap: 0.5rem;
}

.color-input {
  width: 3rem;
  height: 3rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  cursor: pointer;
  padding: 0;
  background: none;
}

.color-text {
  flex: 1;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.tag-preview {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem;
  background-color: #f9fafb;
  border-radius: 0.5rem;
}

.preview-label {
  font-size: 0.875rem;
  font-weight: 500;
  color: #374151;
}

.tag-badge {
  padding: 0.25rem 0.75rem;
  border-radius: 0.5rem;
  font-size: 0.75rem;
  font-weight: 500;
  border: 1px solid;
}

.tag-badge.preview {
  font-size: 0.875rem;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 2rem;
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

.empty-state {
  text-align: center;
  padding: 2rem;
  color: #6b7280;
}

.tags-grid {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.tag-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  transition: all 0.2s;
}

.tag-item:hover {
  border-color: #d1d5db;
  background-color: #f9fafb;
}

.tag-item.inactive {
  opacity: 0.5;
}

.tag-info {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
}

.tag-details {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.tag-description {
  font-size: 0.875rem;
  color: #6b7280;
}

.tag-order {
  font-size: 0.75rem;
  color: #9ca3af;
}

.tag-actions {
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

.activate-btn {
  background-color: #f0fdf4;
  color: #16a34a;
}

.activate-btn:hover {
  background-color: #dcfce7;
}

.deactivate-btn {
  background-color: #fef3c7;
  color: #d97706;
}

.deactivate-btn:hover {
  background-color: #fde68a;
}

.delete-btn {
  background-color: #fef2f2;
  color: #dc2626;
}

.delete-btn:hover {
  background-color: #fee2e2;
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

  .form-group.flex-2 {
    grid-column: span 1;
  }

  .modal-footer {
    flex-direction: column;
  }

  .tag-item {
    flex-direction: column;
    gap: 1rem;
    align-items: stretch;
  }

  .tag-actions {
    justify-content: center;
  }
}
</style>