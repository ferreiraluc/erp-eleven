<template>
  <div v-if="isVisible" class="modal-overlay" @click.self="$emit('close')">
    <div class="modal-box">
      <div class="modal-header">
        <h2 class="modal-title">{{ isEditing ? 'Editar Cliente' : 'Novo Cliente' }}</h2>
        <button class="close-btn" @click="$emit('close')">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="modal-body">

        <!-- Dados básicos -->
        <div class="form-section">
          <h3 class="section-title">Dados do Cliente</h3>
          <div class="form-grid">
            <div class="form-group span-2">
              <label>Nome *</label>
              <input v-model="form.nome" type="text" placeholder="Nome completo" class="form-input" required />
            </div>
            <div class="form-group">
              <label>Telefone</label>
              <input v-model="form.telefone" type="tel" placeholder="(11) 99999-9999" class="form-input" />
            </div>
            <div class="form-group">
              <label>E-mail</label>
              <input v-model="form.email" type="email" placeholder="cliente@email.com" class="form-input" />
            </div>
            <div class="form-group">
              <label>CPF</label>
              <input v-model="form.cpf" type="text" placeholder="000.000.000-00" class="form-input" maxlength="14" />
            </div>
          </div>
        </div>

        <!-- Endereço livre -->
        <div class="form-section">
          <h3 class="section-title">Endereço</h3>
          <div class="form-group">
            <label>Endereço completo</label>
            <textarea
              v-model="form.endereco"
              class="form-textarea"
              rows="4"
              placeholder="Cole ou digite o endereço completo aqui&#10;Ex: Rua das Flores, 123, Bairro Centro, São Paulo - SP, CEP 01310-100"
            ></textarea>
            <span class="field-hint">Campo livre — cole o endereço como preferir.</span>
          </div>
        </div>

        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>

        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" @click="$emit('close')">Cancelar</button>
          <button type="submit" class="btn btn-primary" :disabled="submitting || !form.nome.trim()">
            {{ submitting ? 'Salvando...' : (isEditing ? 'Salvar alterações' : 'Criar cliente') }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { clientesAPI, type Cliente, type ClienteCreate } from '@/services/api'

interface Props {
  isVisible: boolean
  cliente?: Cliente | null
}
const props = withDefaults(defineProps<Props>(), { cliente: null })
const emit = defineEmits<{ close: []; saved: [c: Cliente] }>()

const isEditing = computed(() => !!props.cliente)
const submitting = ref(false)
const errorMsg = ref('')

const emptyForm = (): ClienteCreate => ({
  nome: '', telefone: '', email: '', cpf: '', endereco: '', ativo: true,
})

const form = ref<ClienteCreate>(emptyForm())

watch(() => props.isVisible, (v) => {
  if (v) {
    errorMsg.value = ''
    form.value = props.cliente ? {
      nome: props.cliente.nome,
      telefone: props.cliente.telefone || '',
      email: props.cliente.email || '',
      cpf: props.cliente.cpf || '',
      endereco: props.cliente.endereco || '',
      ativo: props.cliente.ativo,
    } : emptyForm()
  }
})

async function handleSubmit() {
  if (submitting.value) return
  submitting.value = true
  errorMsg.value = ''
  try {
    const payload: ClienteCreate = { ...form.value }
    // Remove strings vazias → undefined
    Object.keys(payload).forEach(k => {
      const key = k as keyof ClienteCreate
      if (payload[key] === '') (payload as any)[key] = undefined
    })
    let result: Cliente
    if (isEditing.value && props.cliente) {
      result = await clientesAPI.update(props.cliente.id, payload)
    } else {
      result = await clientesAPI.create(payload)
    }
    emit('saved', result)
    emit('close')
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Erro ao salvar cliente.'
  } finally {
    submitting.value = false
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

.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: .7rem; }
.form-group { display: flex; flex-direction: column; gap: .28rem; }
.form-group.span-2 { grid-column: 1 / -1; }

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
