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
          <div class="form-row">
            <div class="form-group full-width">
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

        <!-- Endereço -->
        <div class="form-section">
          <h3 class="section-title">Endereço</h3>
          <div class="form-row">
            <div class="form-group full-width">
              <label>Rua / Logradouro</label>
              <input v-model="form.endereco_rua" type="text" placeholder="Rua das Flores, 123" class="form-input" />
            </div>
            <div class="form-group">
              <label>Bairro</label>
              <input v-model="form.endereco_bairro" type="text" placeholder="Centro" class="form-input" />
            </div>
            <div class="form-group">
              <label>Cidade</label>
              <input v-model="form.endereco_cidade" type="text" placeholder="São Paulo" class="form-input" />
            </div>
            <div class="form-group half">
              <label>UF</label>
              <input v-model="form.endereco_uf" type="text" placeholder="SP" maxlength="2" class="form-input" style="text-transform:uppercase" />
            </div>
            <div class="form-group half">
              <label>CEP</label>
              <input v-model="form.endereco_cep" type="text" placeholder="00000-000" maxlength="9" class="form-input" />
            </div>
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
  nome: '', telefone: '', email: '', cpf: '',
  endereco_rua: '', endereco_bairro: '', endereco_cidade: '', endereco_uf: '', endereco_cep: '',
  ativo: true,
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
      endereco_rua: props.cliente.endereco_rua || '',
      endereco_bairro: props.cliente.endereco_bairro || '',
      endereco_cidade: props.cliente.endereco_cidade || '',
      endereco_uf: props.cliente.endereco_uf || '',
      endereco_cep: props.cliente.endereco_cep || '',
      ativo: props.cliente.ativo,
    } : emptyForm()
  }
})

async function handleSubmit() {
  if (submitting.value) return
  submitting.value = true
  errorMsg.value = ''
  try {
    const payload: ClienteCreate = {
      ...form.value,
      endereco_uf: form.value.endereco_uf?.toUpperCase(),
    }
    // Remove empty strings → undefined
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
.modal-box { background: white; border-radius: 12px; width: 100%; max-width: 560px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,.2); }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 1.25rem 1.5rem; border-bottom: 1px solid #e5e7eb; }
.modal-title { font-size: 1.1rem; font-weight: 700; color: #111827; margin: 0; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; padding: .25rem; }
.modal-body { overflow-y: auto; padding: 1.25rem 1.5rem; flex: 1; }
.form-section { margin-bottom: 1.25rem; }
.section-title { font-size: .8rem; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: .05em; margin: 0 0 .75rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }
.form-group { display: flex; flex-direction: column; gap: .3rem; }
.form-group.full-width { grid-column: 1 / -1; }
.form-group.half { }
label { font-size: .78rem; font-weight: 600; color: #374151; }
.form-input { padding: .5rem .75rem; border: 1px solid #d1d5db; border-radius: 7px; font-size: .875rem; outline: none; transition: border-color .15s; }
.form-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.15); }
.modal-footer { display: flex; justify-content: flex-end; gap: .75rem; padding-top: 1rem; border-top: 1px solid #f3f4f6; margin-top: .5rem; }
.btn { display: flex; align-items: center; gap: .4rem; padding: .5rem 1.1rem; border-radius: 8px; font-size: .875rem; cursor: pointer; border: none; font-weight: 600; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: .5; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; }
.error-msg { color: #dc2626; font-size: .8rem; margin: .5rem 0; }
@media (max-width: 480px) { .form-row { grid-template-columns: 1fr; } }
</style>
