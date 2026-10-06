<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h2>{{ tr('Transferência em Lote') }}</h2>
        <button @click="emit('close')" class="close-btn erp-button erp-button--secondary erp-button--icon">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <p v-if="unknownStock" role="alert" class="stock-warning">{{ tr('Há itens com saldo não informado nesta seleção. Revise o estoque antes de transferir.') }}</p>
        <!-- Direction -->
        <div class="form-group">
          <label>{{ tr('Direção *') }}</label>
          <div class="dir-toggle">
            <button class="erp-control" type="button" :class="['dir-btn', { active: direction === 'deposito_to_loja' }]" @click="direction = 'deposito_to_loja'">
              {{ tr('Depósito → Loja') }}
            </button>
            <button class="erp-control" type="button" :class="['dir-btn', { active: direction === 'loja_to_deposito' }]" @click="direction = 'loja_to_deposito'">
              {{ tr('Loja → Depósito') }}
            </button>
          </div>
        </div>

        <!-- Items list -->
        <div class="items-section">
          <div class="items-header">
            <span class="items-title">{{ tr('Itens selecionados: {count}', { count: items.length }) }}</span>
            <button type="button" class="max-all-btn erp-button erp-button--secondary erp-button--sm" @click="setAllMax" :disabled="unknownStock">{{ tr('Máximo disponível') }}</button>
          </div>
          <div class="items-list">
            <div v-for="item in items" :key="item.id" class="transfer-row">
              <div class="row-info">
                <span class="row-name">{{ item.name }}</span>
                <span v-if="item.size" class="row-size">{{ item.size }}</span>
                <span class="row-stock" :class="sourceStock(item) === 0 ? 'stock-zero' : ''">
                  {{ direction === 'deposito_to_loja' ? tr('Dep.') : tr('Loja') }}: {{ displayStock(sourceStock(item)) }}
                  <span v-if="!hasKnownStock(item)"> · {{ tr('Revisar estoque') }}</span>
                </span>
              </div>
              <div class="row-qty">
                <button type="button" class="qty-btn erp-button erp-button--ghost erp-button--icon" @click="dec(item.id)" :disabled="!hasKnownStock(item) || (quantities[item.id] ?? 1) <= 0">−</button>
                <input
                  v-model.number="quantities[item.id]"
                  type="number"
                  min="0"
                  :max="sourceStock(item) ?? undefined"
                  :disabled="!hasKnownStock(item)"
                  class="qty-input"
                />
                <button type="button" class="qty-btn erp-button erp-button--ghost erp-button--icon" @click="inc(item.id, sourceStock(item))" :disabled="!canIncrease(item)">+</button>
              </div>
            </div>
          </div>
        </div>

        <div class="form-group">
          <label>{{ tr('Motivo') }}</label>
          <input v-model="reason" type="text" class="form-input" :placeholder="tr('Motivo da transferência...')" />
        </div>

        <div v-if="errorMsg" class="error-banner">{{ tr(errorMsg) }}</div>
      </div>

      <div class="modal-footer">
        <div class="footer-summary">
          {{ tr('Unidades a transferir: {count}', { count: totalQty }) }}
        </div>
        <button @click="emit('close')" class="btn btn-secondary erp-button erp-button--secondary">{{ tr('Cancelar') }}</button>
        <button @click="handleSubmit" class="btn btn-primary erp-button erp-button--primary" :disabled="saving || unknownStock || totalQty === 0">
          {{ saving ? tr('Transferindo...') : tr('Transferir') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useInventoryI18n } from '@/components/inventory/i18n'
const { tr } = useInventoryI18n()
import { ref, reactive, computed } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import { displayStock, hasKnownStock } from '@/services/inventoryStock'

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
const unknownStock = computed(() => props.items.some(item => !hasKnownStock(item)))

// Initialize quantities to 1 (or max if less) for each item
const quantities = reactive<Record<string, number>>(
  Object.fromEntries(props.items.map(item => {
    const source = sourceStockFor(item, direction.value)
    return [item.id, hasKnownStock(item) && source !== null ? Math.min(1, Math.max(0, source)) : 0]
  }))
)

function sourceStockFor(item: InventoryItem, dir: string): number | null {
  return dir === 'deposito_to_loja' ? item.stock_deposito : item.stock_loja
}

function sourceStock(item: InventoryItem): number | null {
  return sourceStockFor(item, direction.value)
}
function canIncrease(item: InventoryItem) {
  const source = sourceStock(item)
  return hasKnownStock(item) && source !== null && (quantities[item.id] ?? 0) < source
}

function dec(id: string) {
  const cur = quantities[id] ?? 0
  if (cur > 0) quantities[id] = cur - 1
}

function inc(id: string, max: number | null) {
  if (max === null) return
  const cur = quantities[id] ?? 0
  if (cur < max) quantities[id] = cur + 1
}

function setAllMax() {
  if (unknownStock.value) return
  for (const item of props.items) {
    const source = sourceStock(item)
    if (source !== null) quantities[item.id] = source
  }
}

const totalQty = computed(() => Object.values(quantities).reduce((s, v) => s + (v || 0), 0))

async function handleSubmit() {
  if (saving.value || unknownStock.value) return
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
.stock-warning { margin: 0; padding: .75rem; border-radius: 8px; background: #fffbeb; color: #92400e; font-size: .85rem; }
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
