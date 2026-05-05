<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h2>Movimentação de Estoque</h2>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <div v-if="item" class="item-info">
          <span class="item-name">{{ item.name }}</span>
          <div class="item-stock-row">
            <span class="item-stock">Loja: <strong>{{ item.stock_loja ?? item.current_stock }}</strong></span>
            <span class="item-stock-sep">·</span>
            <span class="item-stock">Depósito: <strong>{{ item.stock_deposito ?? 0 }}</strong></span>
          </div>
        </div>

        <div class="form-group">
          <label>Tipo de Movimentação *</label>
          <div class="movement-type-grid">
            <button
              v-for="t in movementTypes"
              :key="t.value"
              @click="form.movement_type = t.value"
              :class="['type-btn', { active: form.movement_type === t.value }, t.color]"
              type="button"
            >
              {{ t.label }}
            </button>
          </div>
        </div>

        <!-- Location selector (entry / exit) -->
        <div v-if="form.movement_type === 'entry' || form.movement_type === 'exit'" class="form-group">
          <label>Local *</label>
          <div class="loc-toggle">
            <button type="button" :class="['loc-btn', { active: form.location === 'loja' }]" @click="form.location = 'loja'">Loja</button>
            <button type="button" :class="['loc-btn', { active: form.location === 'deposito' }]" @click="form.location = 'deposito'">Depósito</button>
          </div>
        </div>

        <!-- Transfer direction -->
        <div v-if="form.movement_type === 'transfer'" class="form-group">
          <label>Direção *</label>
          <div class="loc-toggle">
            <button type="button" :class="['loc-btn loc-btn-wide', { active: form.location_from === 'deposito' }]" @click="form.location_from = 'deposito'; form.location_to = 'loja'">Depósito → Loja</button>
            <button type="button" :class="['loc-btn loc-btn-wide', { active: form.location_from === 'loja' }]" @click="form.location_from = 'loja'; form.location_to = 'deposito'">Loja → Depósito</button>
          </div>
        </div>

        <!-- Batch mode toggle (only for entry) -->
        <div v-if="form.movement_type === 'entry'" class="form-group">
          <label class="checkbox-label">
            <input type="checkbox" v-model="batchMode" />
            Entrada em lote
          </label>
        </div>

        <!-- Single mode -->
        <template v-if="!batchMode">
          <div class="form-row">
            <div class="form-group">
              <label>Quantidade *</label>
              <input v-model.number="form.quantity" type="number" min="1" class="form-input" :class="{ error: errors.quantity }" />
              <span v-if="errors.quantity" class="error-msg">{{ errors.quantity }}</span>
            </div>
            <div class="form-group" v-if="form.movement_type === 'entry'">
              <label>Custo Unitário</label>
              <input v-model.number="form.unit_cost" type="number" step="0.01" min="0" class="form-input" />
            </div>
          </div>

          <div class="form-group">
            <label :class="{ required: form.movement_type === 'adjustment' }">Motivo</label>
            <input v-model="form.reason" type="text" class="form-input" :class="{ error: errors.reason }" placeholder="Motivo da movimentação..." />
            <span v-if="errors.reason" class="error-msg">{{ errors.reason }}</span>
          </div>

          <div class="form-group">
            <label>Observações</label>
            <textarea v-model="form.notes" class="form-input" rows="2" placeholder="Notas adicionais..."></textarea>
          </div>
        </template>

        <!-- Batch mode -->
        <template v-if="batchMode">
          <div class="batch-list">
            <div v-for="(line, idx) in batchLines" :key="idx" class="batch-line">
              <input v-model="line.item_id" type="text" class="form-input" placeholder="ID do item" />
              <input v-model.number="line.quantity" type="number" min="1" class="form-input small" placeholder="Qtd" />
              <input v-model.number="line.unit_cost" type="number" step="0.01" min="0" class="form-input small" placeholder="Custo" />
              <button @click="batchLines.splice(idx, 1)" class="remove-btn" type="button">×</button>
            </div>
            <button @click="batchLines.push({ item_id: '', quantity: 1, unit_cost: 0 })" class="add-line-btn" type="button">
              + Adicionar linha
            </button>
          </div>
          <div class="form-group">
            <label>Motivo</label>
            <input v-model="form.reason" type="text" class="form-input" placeholder="Motivo da entrada..." />
          </div>
        </template>
      </div>

      <div class="modal-footer">
        <button @click="emit('close')" class="btn btn-secondary">Cancelar</button>
        <button @click="handleSubmit" class="btn btn-primary" :disabled="saving">
          {{ saving ? 'Salvando...' : 'Registrar' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'

const props = defineProps<{
  item?: InventoryItem | null
}>()

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'close'): void
}>()

const saving = ref(false)
const batchMode = ref(false)

const movementTypes = [
  { value: 'entry', label: 'Entrada', color: 'green' },
  { value: 'exit', label: 'Saída', color: 'red' },
  { value: 'adjustment', label: 'Ajuste', color: 'yellow' },
  { value: 'transfer', label: 'Transferência', color: 'blue' },
]

const form = reactive({
  movement_type: 'entry',
  quantity: 1,
  reason: '',
  unit_cost: undefined as number | undefined,
  location: 'loja' as 'loja' | 'deposito',
  location_from: 'deposito',
  location_to: 'loja',
  notes: '',
})

const errors = reactive<Record<string, string>>({})
const batchLines = ref([{ item_id: '', quantity: 1, unit_cost: 0 }])

function validate() {
  Object.keys(errors).forEach(k => delete errors[k])
  if (!batchMode.value) {
    if (!form.quantity || form.quantity < 1) errors.quantity = 'Quantidade deve ser ao menos 1'
    if (form.movement_type === 'adjustment' && !form.reason) errors.reason = 'Motivo obrigatório para ajuste'
  }
  return Object.keys(errors).length === 0
}

async function handleSubmit() {
  if (!validate()) return
  saving.value = true
  try {
    if (batchMode.value) {
      await inventoryAPI.createBatchMovement({
        items: batchLines.value.filter(l => l.item_id && l.quantity > 0),
        reason: form.reason,
      })
    } else {
      await inventoryAPI.createMovement({
        item_id: props.item!.id,
        movement_type: form.movement_type,
        quantity: form.quantity,
        reason: form.reason || undefined,
        unit_cost: form.movement_type === 'entry' ? form.unit_cost : undefined,
        location: (form.movement_type === 'entry' || form.movement_type === 'exit') ? form.location : undefined,
        location_from: form.movement_type === 'transfer' ? form.location_from : undefined,
        location_to: form.movement_type === 'transfer' ? form.location_to : undefined,
        notes: form.notes || undefined,
      })
    }
    emit('saved')
  } catch (e: any) {
    errors.quantity = e.response?.data?.detail || 'Erro ao registrar'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 500; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal-container { background: white; border-radius: 12px; width: 100%; max-width: 480px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; }
.modal-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; }
.modal-body { flex: 1; overflow-y: auto; padding: 1.25rem; display: flex; flex-direction: column; gap: 1rem; }
.item-info { background: #f9fafb; border-radius: 8px; padding: 0.75rem; display: flex; justify-content: space-between; align-items: center; }
.item-name { font-weight: 600; color: #111827; }
.item-stock { font-size: 0.85rem; color: #6b7280; }
.form-group { display: flex; flex-direction: column; gap: 0.25rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.form-group label { font-size: 0.8rem; font-weight: 500; color: #374151; }
.form-group label.required::after { content: ' *'; color: #ef4444; }
.form-input { padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box; }
.form-input:focus { border-color: #3b82f6; }
.form-input.error { border-color: #ef4444; }
.form-input.small { padding: 0.5rem; }
.error-msg { font-size: 0.75rem; color: #ef4444; }
.movement-type-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
.type-btn { padding: 0.6rem; border: 2px solid #e5e7eb; border-radius: 8px; cursor: pointer; background: white; font-size: 0.85rem; font-weight: 500; transition: all 0.15s; }
.type-btn.active.green { background: #dcfce7; border-color: #16a34a; color: #15803d; }
.type-btn.active.red { background: #fee2e2; border-color: #dc2626; color: #dc2626; }
.type-btn.active.yellow { background: #fef9c3; border-color: #ca8a04; color: #a16207; }
.type-btn.active.blue { background: #dbeafe; border-color: #2563eb; color: #1d4ed8; }
.checkbox-label { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; cursor: pointer; }
.batch-list { display: flex; flex-direction: column; gap: 0.5rem; }
.batch-line { display: flex; gap: 0.5rem; align-items: center; }
.remove-btn { padding: 0.4rem 0.6rem; background: #fee2e2; border: none; border-radius: 6px; cursor: pointer; color: #dc2626; font-size: 1rem; }
.add-line-btn { padding: 0.5rem; background: #f3f4f6; border: 1px dashed #d1d5db; border-radius: 6px; cursor: pointer; color: #374151; font-size: 0.85rem; }
.modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 1rem 1.25rem; border-top: 1px solid #e5e7eb; }
.btn { padding: 0.5rem 1.25rem; border-radius: 6px; font-size: 0.9rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
.item-stock-row { display: flex; align-items: center; gap: 0.5rem; }
.item-stock-sep { color: #d1d5db; }
.loc-toggle { display: flex; gap: 0.5rem; }
.loc-btn { flex: 1; padding: 0.5rem; border: 2px solid #e5e7eb; border-radius: 8px; cursor: pointer; background: white; font-size: 0.85rem; font-weight: 500; transition: all 0.15s; }
.loc-btn.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.loc-btn-wide { font-size: 0.8rem; }
</style>
