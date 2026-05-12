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
                <label for="valor_total">Valor Total</label>
                <div class="valor-with-moeda">
                  <select
                    v-model="formData.moeda"
                    class="moeda-select"
                    title="Moeda"
                  >
                    <option value="G$">G$</option>
                    <option value="R$">R$</option>
                    <option value="U$">U$</option>
                  </select>
                  <input
                    id="valor_total"
                    v-model="formData.valor_total"
                    type="number"
                    step="0.01"
                    min="0"
                    required
                    placeholder="0,00"
                    class="form-input valor-input"
                  />
                </div>
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
              <div class="form-group rastreio-group">
                <label>Rastreamento</label>
                <!-- Modo autocomplete (padrão) -->
                <div v-if="!rastreioManual" style="position:relative;">
                  <input
                    v-model="rastreioSearch"
                    type="text"
                    placeholder="Buscar rastreio cadastrado..."
                    class="form-input"
                    @input="onRastreioSearchInput"
                    @focus="onRastreioFocus"
                    @blur="setTimeout(() => showRastreioSuggestions = false, 180)"
                  />
                  <button v-if="selectedRastreio" type="button" @click="clearRastreio" class="rastreio-clear-btn">✕</button>
                  <!-- Dropdown de sugestões -->
                  <div v-if="showRastreioSuggestions" class="rastreio-list">
                    <button
                      v-for="r in rastreioFiltered"
                      :key="r.id"
                      type="button"
                      class="rastreio-item"
                      @mousedown.prevent="selectRastreio(r)"
                    >
                      <span class="rastreio-name">{{ r.destinatario || 'Sem destinatário' }}</span>
                      <div class="rastreio-meta">
                        <span class="rastreio-code">{{ r.codigo_rastreio }}</span>
                        <span v-if="r.numero_pedido" class="rastreio-pedido-badge">#{{ r.numero_pedido }}</span>
                        <span class="rastreio-status-dot" :style="{ background: rastreioStatusColor(r.status) }"></span>
                        <span class="rastreio-status-text">{{ rastreioStatusLabel(r.status) }}</span>
                      </div>
                    </button>
                    <div v-if="!rastreioFiltered.length" class="rastreio-empty">Nenhum resultado</div>
                  </div>
                </div>
                <!-- Modo manual: campo texto livre -->
                <input
                  v-else
                  v-model="formData.codigo_rastreio"
                  type="text"
                  placeholder="BR123456789BR"
                  class="form-input"
                />
                <!-- Confirmação de seleção -->
                <p v-if="selectedRastreio && !rastreioManual" class="rastreio-ok">
                  ✓ {{ selectedRastreio.codigo_rastreio }}
                  <span class="rastreio-status-dot" :style="{ background: rastreioStatusColor(selectedRastreio.status) }"></span>
                  {{ rastreioStatusLabel(selectedRastreio.status) }}
                </p>
                <!-- Toggle entre modos -->
                <button type="button" @click="rastreioManual = !rastreioManual; clearRastreio()" class="rastreio-toggle">
                  {{ rastreioManual ? '← Buscar rastreamentos cadastrados' : 'Digitar código manualmente' }}
                </button>
                <!-- Ver Rastreamento (apenas no modo edição) -->
                <div v-if="isEditing" class="ver-rastreio-row">
                  <button
                    v-if="selectedRastreio || (rastreioManual && formData.codigo_rastreio)"
                    type="button"
                    class="btn-ver-rastreio"
                    @click="verRastreamento"
                  >
                    <svg width="13" height="13" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                    Ver Rastreamento
                  </button>
                  <p v-else class="rastreio-nao-vinculado">
                    Nenhum rastreamento vinculado a este pedido.
                  </p>
                </div>
              </div>
            </div>
          </div>

          <!-- Cliente Section (Opcional) -->
          <div class="form-section">
            <h3 class="section-title">Dados do Cliente (Opcional)</h3>

            <!-- Autocomplete para vincular cliente existente -->
            <div class="cliente-autocomplete" style="margin-bottom:.75rem;">
              <label style="font-size:.78rem;font-weight:600;color:#374151;display:block;margin-bottom:.3rem;">Vincular cliente cadastrado</label>
              <div style="position:relative;">
                <input
                  v-model="clienteSearch"
                  type="text"
                  placeholder="Buscar por nome, telefone ou CPF..."
                  class="form-input"
                  @input="onClienteSearchInput"
                  @blur="setTimeout(() => showSuggestions = false, 200)"
                  style="width:100%;box-sizing:border-box;"
                />
                <button v-if="selectedCliente" type="button" @click="clearCliente" style="position:absolute;right:.5rem;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:#9ca3af;font-size:.8rem;">✕ Desvincular</button>
                <div v-if="showSuggestions" class="suggestion-list">
                  <button
                    v-for="c in clienteSuggestions"
                    :key="c.id"
                    type="button"
                    class="suggestion-item"
                    @mousedown.prevent="selectCliente(c)"
                  >
                    <span class="sug-name">{{ c.nome }}</span>
                    <span class="sug-detail">{{ [c.telefone, c.cpf].filter(Boolean).join(' · ') }}</span>
                  </button>
                </div>
              </div>
              <p v-if="selectedCliente" style="font-size:.72rem;color:#10b981;margin:.3rem 0 0;">
                ✓ Vinculado: {{ selectedCliente.nome }} — campos preenchidos automaticamente
              </p>
            </div>

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

          <!-- Anexos Section -->
          <div class="form-section">
            <h3 class="section-title">Fotos e Anexos</h3>
            <AnexosCarousel
              :anexos="anexos"
              :editable="true"
              :uploading="uploadingAnexo"
              :error-msg="uploadError"
              @delete="handleDeleteAnexo"
              @upload="handleUploadFiles"
            />
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
import { useRouter } from 'vue-router'
import { pedidosAPI, pedidoAnexosAPI, tagsAPI, clientesAPI, rastreamentosAPI, type Pedido, type PedidoCreate, type PedidoAnexo, type Tag, type Cliente, type RastreamentoSimple } from '@/services/api'
import TagManagerModal from './TagManagerModal.vue'
import AnexosCarousel from './AnexosCarousel.vue'

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

// Anexos
const anexos = ref<PedidoAnexo[]>([])
const pendingUploads = ref<{ file: File; base64: string }[]>([])
const uploadingAnexo = ref(false)
const uploadError = ref('')

// Cliente autocomplete
const clienteSearch = ref('')
const clienteSuggestions = ref<Cliente[]>([])
const selectedCliente = ref<Cliente | null>(null)
const showSuggestions = ref(false)
let clienteSearchTimer: ReturnType<typeof setTimeout> | null = null

async function onClienteSearchInput() {
  if (clienteSearch.value.length < 2) { clienteSuggestions.value = []; showSuggestions.value = false; return }
  if (clienteSearchTimer) clearTimeout(clienteSearchTimer)
  clienteSearchTimer = setTimeout(async () => {
    clienteSuggestions.value = await clientesAPI.search(clienteSearch.value, 8)
    showSuggestions.value = clienteSuggestions.value.length > 0
  }, 250)
}

function selectCliente(c: Cliente) {
  selectedCliente.value = c
  clienteSearch.value = c.nome
  showSuggestions.value = false
  formData.value.cliente_id = c.id
  formData.value.cliente_nome = c.nome
  formData.value.cliente_telefone = c.telefone || ''
  formData.value.cliente_email = c.email || ''
  formData.value.endereco_entrega = c.endereco || ''
}

function clearCliente() {
  selectedCliente.value = null
  clienteSearch.value = ''
  formData.value.cliente_id = undefined
}

// Rastreamento autocomplete
const rastreioSearch = ref('')
const rastreioList = ref<RastreamentoSimple[]>([])
const rastreioFiltered = ref<RastreamentoSimple[]>([])
const selectedRastreio = ref<RastreamentoSimple | null>(null)
const showRastreioSuggestions = ref(false)
const rastreioManual = ref(false)  // fallback: let user type a code manually

async function loadRastreios() {
  try { rastreioList.value = await rastreamentosAPI.list({ limit: 200 }) } catch { rastreioList.value = [] }
}

function onRastreioFocus() {
  if (!rastreioSearch.value) {
    rastreioFiltered.value = rastreioList.value.slice(0, 8)
    showRastreioSuggestions.value = rastreioFiltered.value.length > 0
  } else {
    onRastreioSearchInput()
  }
}

function onRastreioSearchInput() {
  const term = rastreioSearch.value.toLowerCase()
  if (!term) {
    rastreioFiltered.value = rastreioList.value.slice(0, 8)
    showRastreioSuggestions.value = rastreioFiltered.value.length > 0
    return
  }
  rastreioFiltered.value = rastreioList.value.filter(r =>
    r.codigo_rastreio.toLowerCase().includes(term) ||
    (r.destinatario || '').toLowerCase().includes(term) ||
    (r.descricao || '').toLowerCase().includes(term)
  ).slice(0, 8)
  showRastreioSuggestions.value = rastreioFiltered.value.length > 0
}

function selectRastreio(r: RastreamentoSimple) {
  selectedRastreio.value = r
  formData.value.codigo_rastreio = r.codigo_rastreio
  rastreioSearch.value = r.codigo_rastreio
  showRastreioSuggestions.value = false
}

function clearRastreio() {
  selectedRastreio.value = null
  formData.value.codigo_rastreio = ''
  rastreioSearch.value = ''
}

function rastreioStatusLabel(s: string) {
  const m: Record<string, string> = { PENDENTE: 'Pendente', EM_TRANSITO: 'Em trânsito', ENTREGUE: 'Entregue', ERRO: 'Erro', NAO_ENCONTRADO: 'Não encontrado' }
  return m[s] || s
}

function rastreioStatusColor(s: string) {
  const m: Record<string, string> = { PENDENTE: '#f59e0b', EM_TRANSITO: '#3b82f6', ENTREGUE: '#10b981', ERRO: '#ef4444', NAO_ENCONTRADO: '#6b7280' }
  return m[s] || '#9ca3af'
}

// Form data
const formData = ref<PedidoCreate>({
  descricao: '',
  valor_total: 0,
  moeda: 'G$',
  cliente_nome: '',
  cliente_telefone: '',
  cliente_email: '',
  endereco_entrega: '',
  status: 'PENDENTE',
  codigo_rastreio: ''
})


// Computed
const router = useRouter()
const isEditing = computed(() => !!props.pedido)

function verRastreamento() {
  const code = selectedRastreio.value?.codigo_rastreio || formData.value.codigo_rastreio
  if (code) {
    router.push({ path: '/rastreamento', query: { search: code } })
    closeModal()
  }
}

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
    moeda: 'G$',
    cliente_id: undefined,
    cliente_nome: '',
    cliente_telefone: '',
    cliente_email: '',
    endereco_entrega: '',
    status: 'PENDENTE',
    codigo_rastreio: ''
  }
  selectedTags.value = []
  selectedCliente.value = null
  clienteSearch.value = ''
  selectedRastreio.value = null
  rastreioSearch.value = ''
  rastreioManual.value = false
  anexos.value = []
  pendingUploads.value = []
  uploadError.value = ''
}

const loadFormData = () => {
  if (props.pedido) {
    formData.value = {
      descricao: props.pedido.descricao,
      valor_total: props.pedido.valor_total,
      moeda: props.pedido.moeda || 'G$',
      cliente_id: props.pedido.cliente_id || undefined,
      cliente_nome: props.pedido.cliente_nome || '',
      cliente_telefone: props.pedido.cliente_telefone || '',
      cliente_email: props.pedido.cliente_email || '',
      endereco_entrega: props.pedido.endereco_entrega || '',
      status: props.pedido.status,
      codigo_rastreio: props.pedido.codigo_rastreio || ''
    }
    selectedTags.value = props.pedido.tags.map(tag => tag.id)
    if (props.pedido.cliente) {
      selectedCliente.value = props.pedido.cliente as Cliente
      clienteSearch.value = props.pedido.cliente.nome
    } else {
      selectedCliente.value = null
      clienteSearch.value = ''
    }
    // Restore rastreio selection
    if (props.pedido.codigo_rastreio) {
      rastreioSearch.value = props.pedido.codigo_rastreio
      const found = rastreioList.value.find(r => r.codigo_rastreio === props.pedido!.codigo_rastreio)
      selectedRastreio.value = found || null
      if (!found) rastreioManual.value = true
    } else {
      selectedRastreio.value = null
      rastreioSearch.value = ''
      rastreioManual.value = false
    }
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
      // Upload any files that were added before the pedido was saved
      for (const p of pendingUploads.value) {
        try {
          await pedidoAnexosAPI.upload(result.id, {
            nome_arquivo: p.file.name,
            tipo_arquivo: p.file.type,
            tamanho: p.file.size,
            dados: p.base64,
          })
        } catch { /* best-effort */ }
      }
    }

    emit('saved', result)
    closeModal()
  } catch (error) {
    console.error('Erro ao salvar pedido:', error)
  } finally {
    isSubmitting.value = false
  }
}

async function loadAnexos() {
  if (!props.pedido) { anexos.value = []; return }
  try {
    anexos.value = await pedidoAnexosAPI.getAnexos(props.pedido.id)
  } catch {
    anexos.value = []
  }
}

async function handleUploadFiles(files: File[]) {
  uploadError.value = ''
  for (const file of files) {
    if (anexos.value.length >= 10) { uploadError.value = 'Limite de 10 anexos atingido.'; break }
    if (file.size > 5 * 1024 * 1024) { uploadError.value = `"${file.name}" excede 5 MB.`; continue }

    uploadingAnexo.value = true
    try {
      const base64 = await fileToBase64(file)
      // If pedido already saved, upload immediately; otherwise queue for post-save
      if (props.pedido) {
        const novo = await pedidoAnexosAPI.upload(props.pedido.id, {
          nome_arquivo: file.name,
          tipo_arquivo: file.type,
          tamanho: file.size,
          dados: base64,
        })
        anexos.value = [...anexos.value, novo]
      } else {
        // Pending uploads stored locally until pedido is created
        pendingUploads.value.push({ file, base64 })
        // Add a preview object
        anexos.value = [...anexos.value, {
          id: `pending-${Date.now()}-${file.name}`,
          pedido_id: '',
          nome_arquivo: file.name,
          tipo_arquivo: file.type,
          tamanho: file.size,
          dados: base64,
          created_at: new Date().toISOString(),
        }]
      }
    } catch (e: any) {
      uploadError.value = e?.response?.data?.detail || `Erro ao enviar "${file.name}".`
    } finally {
      uploadingAnexo.value = false
    }
  }
}

async function handleDeleteAnexo(anexo: PedidoAnexo) {
  if (anexo.id.startsWith('pending-')) {
    // Remove from pending list
    pendingUploads.value = pendingUploads.value.filter(p => p.file.name !== anexo.nome_arquivo)
    anexos.value = anexos.value.filter(a => a.id !== anexo.id)
    return
  }
  try {
    await pedidoAnexosAPI.delete(props.pedido!.id, anexo.id)
    anexos.value = anexos.value.filter(a => a.id !== anexo.id)
  } catch {
    uploadError.value = 'Erro ao remover anexo.'
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      // strip "data:image/jpeg;base64," prefix
      resolve(result.split(',')[1])
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
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
watch(() => props.isVisible, async (visible) => {
  if (visible) {
    await loadRastreios()
    loadFormData()
    loadTags()
    loadAnexos()
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

/* Rastreamento autocomplete */
.rastreio-group { position: relative; }
.rastreio-clear-btn {
  position: absolute; right: .5rem; top: 50%; transform: translateY(-50%);
  background: none; border: none; cursor: pointer; color: #9ca3af; font-size: .8rem;
}
.rastreio-list {
  position: absolute; top: calc(100% + 3px); left: 0; right: 0;
  background: white; border: 1px solid #e5e7eb; border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0,0,0,.1); z-index: 200;
  max-height: 240px; overflow-y: auto;
}
.rastreio-item {
  display: flex; flex-direction: column; align-items: flex-start; gap: .15rem;
  width: 100%; text-align: left; padding: .5rem .85rem;
  background: none; border: none; cursor: pointer; border-bottom: 1px solid #f3f4f6;
}
.rastreio-item:last-child { border-bottom: none; }
.rastreio-item:hover { background: #f9fafb; }
.rastreio-name { font-size: .82rem; font-weight: 700; color: #111827; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.rastreio-meta { display: flex; align-items: center; gap: .35rem; }
.rastreio-code { font-size: .72rem; font-weight: 600; color: #6b7280; font-family: monospace; }
.rastreio-pedido-badge { font-size: .65rem; font-weight: 700; background: #dbeafe; color: #1d4ed8; padding: .08rem .35rem; border-radius: 4px; }
.rastreio-status-dot { width: .45rem; height: .45rem; border-radius: 50%; flex-shrink: 0; display: inline-block; }
.rastreio-status-text { font-size: .7rem; color: #9ca3af; }
.rastreio-empty { padding: .75rem; font-size: .8rem; color: #9ca3af; text-align: center; }
.rastreio-ok {
  margin: .3rem 0 0; font-size: .72rem; color: #10b981;
  display: flex; align-items: center; gap: .3rem;
}
.rastreio-toggle {
  background: none; border: none; cursor: pointer; font-size: .72rem;
  color: #6b7280; text-decoration: underline; padding: 0; margin-top: .25rem;
}
.rastreio-toggle:hover { color: #374151; }
.ver-rastreio-row { margin-top: 0.5rem; }
.btn-ver-rastreio {
  display: inline-flex; align-items: center; gap: 0.35rem;
  padding: 0.35rem 0.7rem; background: #eff6ff; color: #2563eb;
  border: 1px solid #bfdbfe; border-radius: 6px; font-size: 0.78rem;
  font-weight: 600; cursor: pointer; transition: background 0.15s;
}
.btn-ver-rastreio:hover { background: #dbeafe; }
.rastreio-nao-vinculado { font-size: 0.75rem; color: #9ca3af; margin: 0.25rem 0 0; font-style: italic; }

/* Valor + moeda combo */
.valor-with-moeda {
  display: flex;
  gap: 0;
}

.moeda-select {
  padding: 0.75rem 0.5rem;
  border: 1px solid #d1d5db;
  border-right: none;
  border-radius: 0.5rem 0 0 0.5rem;
  font-size: 0.875rem;
  font-weight: 600;
  background-color: #f9fafb;
  color: #374151;
  cursor: pointer;
  width: 4.5rem;
  flex-shrink: 0;
  transition: border-color 0.2s;
}

.moeda-select:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
  z-index: 1;
  position: relative;
}

.valor-input {
  border-radius: 0 0.5rem 0.5rem 0 !important;
  flex: 1;
}

/* Cliente autocomplete */
.suggestion-list {
  position: absolute;
  top: calc(100% + 3px);
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 6px 18px rgba(0,0,0,.1);
  z-index: 200;
  max-height: 220px;
  overflow-y: auto;
}
.suggestion-item {
  display: flex;
  flex-direction: column;
  gap: .1rem;
  width: 100%;
  text-align: left;
  padding: .5rem .85rem;
  background: none;
  border: none;
  cursor: pointer;
  border-bottom: 1px solid #f3f4f6;
}
.suggestion-item:last-child { border-bottom: none; }
.suggestion-item:hover { background: #f9fafb; }
.sug-name { font-size: .85rem; font-weight: 600; color: #111827; }
.sug-detail { font-size: .73rem; color: #6b7280; }
</style>