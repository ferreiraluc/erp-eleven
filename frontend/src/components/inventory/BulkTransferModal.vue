<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h2>Transferência em Lote</h2>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <!-- Direction -->
        <div class="form-group">
          <label>Direção *</label>
          <div class="dir-toggle">
            <button type="button" :class="['dir-btn', { active: direction === 'deposito_to_loja' }]" @click="direction = 'deposito_to_loja'">
              Depósito → Loja
            </button>
            <button type="button" :class="['dir-btn', { active: direction === 'loja_to_deposito' }]" @click="direction = 'loja_to_deposito'">
              Loja → Depósito
            </button>
          </div>
        </div>

        <!-- Items list -->
        <div class="items-section">
          <div class="items-header">
            <span class="items-title">{{ items.length }} ite{{ items.length !== 1 ? 'ns' : 'm' }} selecionado{{ items.length !== 1 ? 's' : '' }}</span>
            <button type="button" class="max-all-btn" @click="setAllMax">Máximo disponível</button>
          </div>
          <div class="items-list">
            <div v-for="item in items" :key="item.id" class="transfer-row">
              <div class="row-info">
                <span class="row-name">{{ item.name }}</span>
                <span v-if="item.size" class="row-size">{{ item.size }}</span>
                <span class="row-stock" :class="sourceStock(item) === 0 ? 'stock-zero' : ''">
                  {{ direction === 'deposito_to_loja' ? 'Dep.' : 'Loja' }}: {{ sourceStock(item) }}
                </span>
              </div>
              <div class="row-qty">
                <button type="button" class="qty-btn" @click="dec(item.id)" :disabled="(quantities[item.id] ?? 1) <= 0">−</button>
                <input
                  v-model.number="quantities[item.id]"
                  type="number"
                  min="0"
                  :max="sourceStock(item)"
                  class="qty-input"
                />
                <button type="button" class="qty-btn" @click="inc(item.id, sourceStock(item))" :disabled="(quantities[item.id] ?? 0) >= sourceStock(item)">+</button>
              </div>
            </div>
          </div>
        </div>

        <div class="form-group">
          <label>Motivo</label>
          <input v-model="reason" type="text" class="form-input" placeholder="Motivo da transferência..." />
        </div>

        <div v-if="errorMsg" class="error-banner">{{ errorMsg }}</div>
      </div>

      <div class="modal-footer">
        <div class="footer-summary">
          {{ totalQty }} unidad{{ totalQty !== 1 ? 'es' : 'e' }} a transferir
        </div>
        <button @click="emit('close')" class="btn btn-secondary">Cancelar</button>
        <button @click="handleSubmit" class="btn btn-primary" :disabled="saving || totalQty === 0">
          {{ saving ? 'Transferindo...' : 'Transferir' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'

const props = defineProps<{
  items: InventoryItem[]
}>()

const emit = defineEmits<{
  (e: 'saved'): void
  (e: 'close'): void
}>()

const direction = ref<'deposito_to_loja' | 'loja_to_deposito'>('deposito_to_loja')
const reason = ref('')
const saving = ref(false)
const errorMsg = ref('')

// Initialize quantities to 1 (or max if less) for each item
const quantities = reactive<Record<string, number>>(
  Object.fromEntries(props.items.map(i => [i.id, Math.min(1, sourceStockFor(i, direction.value))]))
)

function sourceStockFor(item: InventoryItem, dir: string): number {
  return dir === 'deposito_to_loja' ? (item.stock_deposito ?? 0) : (item.stock_loja ?? item.current_stock ?? 0)
}

function sourceStock(item: InventoryItem): number {
  return sourceStockFor(item, direction.value)
}

function dec(id: string) {
  const cur = quantities[id] ?? 0
  if (cur > 0) quantities[id] = cur - 1
}

function inc(id: string, max: number) {
  const cur = quantities[id] ?? 0
  if (cur < max) quantities[id] = cur + 1
}

function setAllMax() {
  for (const item of props.items) {
    quantities[item.id] = sourceStock(item)
  }
}

const totalQty = computed(() => Object.values(quantities).reduce((s, v) => s + (v || 0), 0))

async function handleSubmit() {
  errorMsg.value = ''
  const payload = props.items
    .map(i => ({ item_id: i.id, quantity: quantities[i.id] ?? 0 }))
    .filter(x => x.quantity > 0)

  if (payload.length === 0) {
    errorMsg.value = 'Nenhuma quantidade definida.'
    return
  }

  saving.value = true
  try {
    await inventoryAPI.transferBulk({
      items: payload,
      direction: direction.value,
      reason: reason.value || undefined,
    })
    emit('saved')
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Erro ao transferir'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 600; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal-container { background: white; border-radius: 12px; width: 100%; max-width: 520px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; }
.modal-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; }
.modal-body { flex: 1; overflow-y: auto; padding: 1.25rem; display: flex; flex-direction: column; gap: 1rem; }
.form-group { display: flex; flex-direction: column; gap: 0.25rem; }
.form-group label { font-size: 0.8rem; font-weight: 500; color: #374151; }
.form-input { padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box; }
.form-input:focus { border-color: #3b82f6; }
.dir-toggle { display: flex; gap: 0.5rem; }
.dir-btn { flex: 1; padding: 0.6rem; border: 2px solid #e5e7eb; border-radius: 8px; cursor: pointer; background: white; font-size: 0.85rem; font-weight: 500; transition: all 0.15s; }
.dir-btn.active { background: #dbeafe; border-color: #3b82f6; color: #1d4ed8; }
.items-section { display: flex; flex-direction: column; gap: 0.5rem; }
.items-header { display: flex; align-items: center; justify-content: space-between; }
.items-title { font-size: 0.8rem; font-weight: 500; color: #374151; }
.max-all-btn { font-size: 0.75rem; color: #3b82f6; background: none; border: none; cursor: pointer; text-decoration: underline; padding: 0; }
.items-list { display: flex; flex-direction: column; gap: 0.5rem; max-height: 300px; overflow-y: auto; }
.transfer-row { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.6rem 0.75rem; }
.row-info { display: flex; align-items: center; gap: 0.4rem; flex: 1; min-width: 0; flex-wrap: wrap; }
.row-name { font-size: 0.85rem; font-weight: 500; color: #111827; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 140px; }
.row-size { font-size: 0.75rem; background: #e5e7eb; color: #374151; padding: 0.1rem 0.35rem; border-radius: 4px; white-space: nowrap; }
.row-stock { font-size: 0.75rem; color: #6b7280; white-space: nowrap; }
.row-stock.stock-zero { color: #ef4444; }
.row-qty { display: flex; align-items: center; gap: 0.25rem; flex-shrink: 0; }
.qty-btn { width: 28px; height: 28px; border: 1px solid #d1d5db; border-radius: 6px; background: white; cursor: pointer; font-size: 1rem; display: flex; align-items: center; justify-content: center; }
.qty-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.qty-input { width: 52px; text-align: center; padding: 0.35rem 0.25rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; }
.error-banner { background: #fee2e2; color: #dc2626; padding: 0.75rem; border-radius: 8px; font-size: 0.85rem; }
.modal-footer { display: flex; align-items: center; justify-content: flex-end; gap: 0.75rem; padding: 1rem 1.25rem; border-top: 1px solid #e5e7eb; }
.footer-summary { flex: 1; font-size: 0.8rem; color: #6b7280; }
.btn { padding: 0.5rem 1.25rem; border-radius: 6px; font-size: 0.9rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
@media (max-width: 600px) {
  .modal-overlay { align-items: flex-end; padding: 0; }
  .modal-container { border-radius: 14px 14px 0 0; max-height: 88vh; }
  .row-name { max-width: 100px; }
}
</style>
