<template>
  <Teleport to="body" :disabled="!quick">
  <div v-if="isVisible" class="modal-overlay erp-dialog-backdrop" @click.self="close">
    <div v-erp-dialog class="modal-box erp-dialog" :class="{ 'erp-dialog--sm': quick }">
      <div class="modal-header erp-dialog__header">
        <h2 class="modal-title">{{ isEditing ? uiText(`Editar Cliente`) : uiText(`Novo Cliente`) }}</h2>
        <button data-dialog-close :aria-label="uiText('Fechar')" class="close-btn erp-button erp-button--secondary erp-button--icon" @click="close" :disabled="submitting">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="modal-body erp-dialog__form">

        <!-- Dados básicos -->
        <div class="erp-dialog__body"><div class="form-section">
          <h3 class="section-title">{{ uiText(`Dados do Cliente`) }}</h3>
          <fieldset :disabled="submitting" class="form-grid">
            <div class="form-group span-2">
              <label for="customer-form-name">{{ uiText(`Nome *`) }}</label>
              <input id="customer-form-name" v-model="form.nome" type="text" :placeholder="uiText(`Nome completo`)" class="form-input" required />
            </div>
            <div class="form-group">
              <label for="customer-form-phone">{{ uiText(`Telefone`) }}</label>
              <input id="customer-form-phone" v-model="form.telefone" type="tel" placeholder="(11) 99999-9999" class="form-input" />
            </div>
            <div v-if="!quick" class="form-group">
              <label>{{ uiText(`E-mail`) }}</label>
              <input v-model="form.email" type="email" placeholder="cliente@email.com" class="form-input" />
            </div>
          </fieldset>
        </div>

        <section class="form-section document-section">
          <h3 class="section-title">{{ documentText('title') }}</h3>
          <fieldset :disabled="submitting" class="document-list">
            <div v-if="legacyDocument" class="legacy-document">
              <span>{{ documentText('previous') }}: {{ legacyDocument }}</span>
              <ErpSelect v-model="legacyType" :label="documentText('type')" :disabled="submitting"><option value="">{{ documentText('unspecified') }}</option><option v-for="type in documentTypes" :key="type" :value="type">{{ type }} · {{ countryFor(type) }}</option></ErpSelect>
              <p class="field-hint">{{ documentText('legacyHelp') }}</p>
              <button type="button" class="erp-button erp-button--ghost erp-button--sm" @click="legacyDocument = ''; legacyType = ''">{{ documentText('remove') }}</button>
            </div>
            <div v-for="(document, index) in documents" :key="index" class="document-row">
              <ErpSelect v-model="document.tipo" :label="documentText('type')" :disabled="submitting" @change="updateDocumentType(document)"><option v-for="type in documentTypes" :key="type" :value="type">{{ type }} · {{ countryFor(type) }}</option></ErpSelect>
              <label><span class="sr-only">{{ documentText('number') }}</span><input v-model="document.numero" class="form-input" type="text" maxlength="40" :placeholder="documentText('number')" :aria-label="documentText('number')" /></label>
              <label v-if="document.tipo === 'RG'" class="document-issuer"><span class="sr-only">{{ documentText('issuer') }}</span><input v-model="document.emissor" class="form-input" type="text" maxlength="40" :placeholder="documentText('issuer')" :aria-label="documentText('issuer')" /></label>
              <button type="button" class="erp-button erp-button--ghost erp-button--icon" :aria-label="documentText('remove')" @click="documents.splice(index, 1)">×</button>
            </div>
            <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="documents.length + (legacyDocument ? 1 : 0) >= 10" @click="documents.push({ tipo: 'CPF', pais: 'BR', numero: '' })">+ {{ documentText('add') }}</button>
          </fieldset>
        </section>

        <!-- Endereço livre -->
        <details class="form-section" :open="!quick">
          <summary class="section-title">{{ uiText(`Endereço`) }}</summary>
          <div class="form-group">
            <label>{{ uiText(`Endereço completo`) }}</label>
            <textarea
              v-model="form.endereco"
              class="form-textarea"
              rows="4"
              :placeholder="uiText(`Cole ou digite o endereço completo aqui`) + '\n' + uiText(`Ex: Rua das Flores, 123, Bairro Centro, São Paulo - SP, CEP 01310-100`)"
            ></textarea>
            <span class="field-hint">{{ uiText(`Campo livre — cole o endereço como preferir.`) }}</span>
          </div>
        </details>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p></div>

        <div class="modal-footer erp-dialog__footer">
          <button type="button" class="btn btn-secondary erp-button erp-button--secondary" @click="close" :disabled="submitting">{{ uiText(`Cancelar`) }}</button>
          <button type="submit" class="btn btn-primary erp-button erp-button--primary" :disabled="submitting || !form.nome.trim()">
            {{ submitting ? uiText(`Salvando...`) : (isEditing ? uiText(`Salvar alterações`) : uiText(`Criar cliente`)) }}
          </button>
        </div>
      </form>
    </div>
  </div>
  </Teleport>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { uiText } from '@/i18n/uiText'
import { ref, watch, computed, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { customerDocumentMessages } from './customerDocumentMessages'
import { clientesAPI, type Cliente, type ClienteCreate, type ClienteDocumento } from '@/services/api'

interface Props {
  isVisible: boolean
  cliente?: Cliente | null
  quick?: boolean
  initialName?: string
}
const props = withDefaults(defineProps<Props>(), { cliente: null, quick: false, initialName: '' })
const emit = defineEmits<{ close: []; saved: [c: Cliente] }>()
const { t: documentText } = useI18n({ useScope: 'local', messages: customerDocumentMessages })
const auth = useAuthStore()
const documentTypes = ['CPF', 'CNPJ', 'RG', 'CI', 'RUC'] as const
const documents = ref<ClienteDocumento[]>([])
const originalLegacyRow = ref<ClienteDocumento | null>(null)
const legacyDocument = ref(''), legacyType = ref<ClienteDocumento['tipo'] | ''>('')
const countryFor = (type: ClienteDocumento['tipo']): 'BR' | 'PY' => type === 'CI' || type === 'RUC' ? 'PY' : 'BR'
function updateDocumentType(document: ClienteDocumento) {
  document.pais = countryFor(document.tipo)
  if (document.tipo !== 'RG') delete document.emissor
}
let generation = 0

const isEditing = computed(() => !!props.cliente)
const submitting = ref(false)
const errorMsg = ref('')

const emptyForm = (): ClienteCreate => ({
  nome: '', telefone: '', email: '', cpf: '', endereco: '', ativo: true,
})

const form = ref<ClienteCreate>(emptyForm())

watch(() => props.isVisible, (v) => {
  if (v) {
    generation++
    errorMsg.value = ''
    form.value = props.cliente ? {
      nome: props.cliente.nome,
      telefone: props.cliente.telefone || '',
      email: props.cliente.email || '',
      cpf: props.cliente.cpf || '',
      endereco: props.cliente.endereco || '',
      ativo: props.cliente.ativo,
    } : { ...emptyForm(), nome: props.initialName }
    documents.value = (props.cliente?.documentos || []).map(document => ({ ...document }))
    originalLegacyRow.value = null
    legacyDocument.value = ''; legacyType.value = ''
    const legacy = props.cliente?.cpf?.trim() || ''
    const normalized = legacy.replace(/\D/g, '')
    if (legacy && !documents.value.some(document => document.numero.replace(/\D/g, '') === normalized && (document.tipo === 'CPF' || document.tipo === 'CNPJ'))) {
      if (normalized.length === 11 || normalized.length === 14) documents.value.push({ tipo: normalized.length === 11 ? 'CPF' : 'CNPJ', pais: 'BR', numero: legacy })
      else legacyDocument.value = legacy
    }
    if (legacy) originalLegacyRow.value = documents.value.find(document => document.numero.replace(/\D/g, '') === normalized && (document.tipo === 'CPF' || document.tipo === 'CNPJ')) || null
  }
}, { immediate: true })
watch(() => auth.token, () => { generation++; submitting.value = false; errorMsg.value = ''; emit('close') }, { flush: 'sync' })
onBeforeUnmount(() => { generation++ })

function close() { if (!submitting.value) emit('close') }

async function handleSubmit() {
  if (submitting.value) return
  if (documents.value.some(document => !document.numero.trim())) { errorMsg.value = documentText('invalid'); return }
  const current = ++generation, token = auth.token
  submitting.value = true
  errorMsg.value = ''
  try {
    const allDocuments: ClienteDocumento[] = documents.value.map(document => ({ tipo: document.tipo, pais: countryFor(document.tipo), numero: document.numero.trim(), ...(document.tipo === 'RG' && document.emissor?.trim() ? { emissor: document.emissor.trim() } : {}) }))
    if (legacyDocument.value && legacyType.value) allDocuments.push({ tipo: legacyType.value, pais: countryFor(legacyType.value), numero: legacyDocument.value })
    // An alias may retain the unique legacy CPF. Documents added to the primary
    // record must not silently move that CPF into its legacy column on contact edits.
    const original = originalLegacyRow.value
    const legacy = isEditing.value
      ? original
        ? documents.value.includes(original) && (original.tipo === 'CPF' || original.tipo === 'CNPJ') ? original.numero.trim() : null
        : legacyDocument.value || null
      : allDocuments.find(document => document.tipo === 'CPF' || document.tipo === 'CNPJ')?.numero || (!legacyType.value && legacyDocument.value) || null
    const payload: ClienteCreate = { ...form.value, documentos: allDocuments, cpf: legacy }
    // Remove strings vazias → undefined
    Object.keys(payload).forEach(k => {
      const key = k as keyof ClienteCreate
      if (payload[key] === '') delete payload[key]
    })
    let result: Cliente
    if (isEditing.value && props.cliente) {
      result = await clientesAPI.update(props.cliente.id, payload)
    } else {
      result = await clientesAPI.create(payload)
    }
    if (current === generation && token === auth.token) { emit('saved', result); emit('close') }
  } catch (e: any) {
    if (current !== generation || token !== auth.token) return
    const detail = e.response?.data?.detail
    errorMsg.value = Array.isArray(detail)
      ? detail.map((d: any) => d.msg || String(d)).join('; ')
      : (typeof detail === 'string' ? detail : e.message || uiText(`Erro ao salvar cliente.`))
  } finally {
    if (current === generation) submitting.value = false
  }
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; z-index: 1000; padding: 1rem; }
.modal-box { background: white; border-radius: 12px; width: 100%; max-width: 520px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,.2); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 1.1rem 1.4rem; border-bottom: 1px solid #e5e7eb; flex-shrink: 0; }
.modal-title { font-size: 1.05rem; font-weight: 700; color: #111827; margin: 0; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; padding: .25rem; }
.modal-body { overflow-y: auto; padding: 1.25rem 1.4rem; flex: 1; }

.form-section { margin-bottom: 1.25rem; }
.section-title { font-size: .75rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin: 0 0 .75rem; }

.form-grid { border: 0; padding: 0; margin: 0; min-width: 0; display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; }
.form-group { display: flex; flex-direction: column; gap: .28rem; }
.form-group.span-2 { grid-column: 1 / -1; }
.document-list { border: 0; margin: 0; padding: 0; min-width: 0; display: grid; gap: .6rem; }
.document-row { display: grid; grid-template-columns: 135px minmax(0, 1fr) 32px; gap: .4rem; align-items: center; }
.document-row > label { min-width: 0; }
.document-row input { width: 100%; box-sizing: border-box; }
.document-row .document-issuer { grid-column: 1 / 3; grid-row: 2; }
.document-row > button { grid-column: 3; grid-row: 1; }
.legacy-document { border: 1px solid #e2e8f0; border-radius: 8px; padding: .7rem; display: grid; gap: .5rem; color: #64748b; font-size: .78rem; overflow-wrap: anywhere; }
.document-list > button { justify-self: start; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; border: 0; }

label { font-size: .78rem; font-weight: 600; color: #374151; }
.form-input { padding: .5rem .75rem; border: 1px solid #d1d5db; border-radius: 7px; font-size: .875rem; outline: none; transition: border-color .15s; }
.form-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.15); }

.form-textarea {
  padding: .6rem .75rem;
  border: 1px solid #d1d5db;
  border-radius: 7px;
  font-size: .875rem;
  outline: none;
  resize: vertical;
  min-height: 90px;
  font-family: inherit;
  line-height: 1.5;
  transition: border-color .15s;
  width: 100%;
  box-sizing: border-box;
}
.form-textarea:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.15); }
.field-hint { font-size: .72rem; color: #9ca3af; }

.modal-footer { display: flex; justify-content: flex-end; gap: .75rem; padding-top: 1rem; border-top: 1px solid #f3f4f6; margin-top: .25rem; flex-shrink: 0; }
.btn { display: flex; align-items: center; gap: .4rem; padding: .5rem 1.1rem; border-radius: 8px; font-size: .875rem; cursor: pointer; border: none; font-weight: 600; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.error-msg { color: #dc2626; font-size: .8rem; margin: .5rem 0 0; }

@media (max-width: 480px) {
  .form-grid { grid-template-columns: 1fr; }
  .form-group.span-2 { grid-column: 1; }
}
</style>
