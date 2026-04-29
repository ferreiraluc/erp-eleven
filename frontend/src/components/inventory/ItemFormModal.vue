<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h2>{{ isEdit ? 'Editar Item' : 'Novo Item' }}</h2>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Tabs -->
      <div class="tabs">
        <button @click="activeTab = 'basic'" :class="['tab', { active: activeTab === 'basic' }]">Básico</button>
        <button @click="activeTab = 'stock'" :class="['tab', { active: activeTab === 'stock' }]">Estoque</button>
      </div>

      <div class="modal-body">
        <!-- Basic Tab -->
        <div v-if="activeTab === 'basic'" class="tab-content">
          <div class="form-group">
            <label>Nome *</label>
            <input v-model="form.name" type="text" class="form-input" :class="{ error: errors.name }" placeholder="Nome do produto" />
            <span v-if="errors.name" class="error-msg">{{ errors.name }}</span>
          </div>

          <div class="form-group">
            <label>Descrição</label>
            <textarea v-model="form.description" class="form-input" rows="2" placeholder="Descrição opcional"></textarea>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Categoria</label>
              <div class="input-combo">
                <select v-if="!newCategory" v-model="form.category" class="form-input">
                  <option value="">Selecione...</option>
                  <option v-for="cat in categories" :key="cat" :value="cat">{{ cat }}</option>
                </select>
                <input v-if="newCategory" v-model="form.category" type="text" class="form-input" placeholder="Nova categoria" />
                <button @click="newCategory = !newCategory" class="combo-toggle" type="button">
                  {{ newCategory ? '↩' : '+' }}
                </button>
              </div>
            </div>
            <div class="form-group">
              <label>Tamanho</label>
              <input v-model="form.size" type="text" class="form-input" placeholder="P, M, G, GG..." />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Cor</label>
              <input v-model="form.color" type="text" class="form-input" placeholder="Vermelho, Azul..." />
            </div>
            <div class="form-group">
              <label>Unidade</label>
              <select v-model="form.unit" class="form-input">
                <option value="un">un</option>
                <option value="par">par</option>
                <option value="kg">kg</option>
                <option value="m">m</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Stock Tab -->
        <div v-if="activeTab === 'stock'" class="tab-content">
          <div class="form-group">
            <label>Localização</label>
            <input v-model="form.location" type="text" class="form-input" placeholder="Ex: A-12, Prateleira 3..." />
          </div>

          <div class="form-group">
            <label>Código de Barras</label>
            <div class="barcode-row">
              <input v-model="form.barcode" type="text" class="form-input" placeholder="EAN, QR, etc." />
              <button @click="showScanner = true" class="scan-btn" type="button" title="Escanear">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h4M4 12h4m12 0h.01M5 8H3a2 2 0 00-2 2v3a2 2 0 002 2h2" />
                </svg>
              </button>
            </div>
            <span v-if="barcodeDuplicateWarning" class="warn-msg">Este código já existe em outro item.</span>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Custo</label>
              <input v-model.number="form.cost_price" type="number" step="0.01" min="0" class="form-input" :class="{ error: errors.cost_price }" placeholder="0.00" />
              <span v-if="errors.cost_price" class="error-msg">{{ errors.cost_price }}</span>
            </div>
            <div class="form-group">
              <label>Preço de Venda</label>
              <input v-model.number="form.sale_price" type="number" step="0.01" min="0" class="form-input" placeholder="0.00" />
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Moeda</label>
              <select v-model="form.currency" class="form-input">
                <option value="PYG">G$ (Guarani)</option>
                <option value="BRL">R$ (Real)</option>
                <option value="USD">U$ (Dólar)</option>
                <option value="EUR">EUR (Euro)</option>
              </select>
            </div>
            <div class="form-group">
              <label>Fornecedor</label>
              <select v-model="form.supplier_id" class="form-input">
                <option value="">Nenhum</option>
                <option v-for="s in suppliers" :key="s.id" :value="s.id">{{ s.name }}</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Estoque Mínimo</label>
              <input v-model.number="form.min_stock" type="number" min="0" class="form-input" :class="{ error: errors.min_stock }" />
              <span v-if="errors.min_stock" class="error-msg">{{ errors.min_stock }}</span>
            </div>
            <div class="form-group">
              <label>Estoque Máximo</label>
              <input v-model.number="form.max_stock" type="number" min="0" class="form-input" />
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button @click="emit('close')" class="btn btn-secondary">Cancelar</button>
        <button @click="handleSubmit" class="btn btn-primary" :disabled="saving">
          {{ saving ? 'Salvando...' : (isEdit ? 'Atualizar' : 'Criar') }}
        </button>
      </div>
    </div>

    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import BarcodeScanner from './BarcodeScanner.vue'

const props = defineProps<{
  item?: InventoryItem | null
  suppliers?: Array<{ id: string; name: string }>
}>()

const emit = defineEmits<{
  (e: 'saved', item: InventoryItem): void
  (e: 'close'): void
}>()

const isEdit = computed(() => !!props.item)
const activeTab = ref('basic')
const showScanner = ref(false)
const saving = ref(false)
const newCategory = ref(false)
const barcodeDuplicateWarning = ref(false)

const categories = ['Camisetas', 'Calças', 'Vestidos', 'Acessórios', 'Calçados', 'Outros']

const form = reactive({
  name: '',
  description: '',
  category: '',
  size: '',
  color: '',
  unit: 'un',
  location: '',
  barcode: '',
  supplier_id: '',
  cost_price: 0,
  sale_price: 0,
  currency: 'PYG',
  min_stock: 0,
  max_stock: 0,
  is_active: true,
})

const errors = reactive<Record<string, string>>({})

onMounted(() => {
  if (props.item) {
    Object.assign(form, {
      name: props.item.name || '',
      description: props.item.description || '',
      category: props.item.category || '',
      size: props.item.size || '',
      color: props.item.color || '',
      unit: props.item.unit || 'un',
      location: props.item.location || '',
      barcode: props.item.barcode || '',
      supplier_id: props.item.supplier_id || '',
      cost_price: Number(props.item.cost_price) || 0,
      sale_price: Number(props.item.sale_price) || 0,
      currency: props.item.currency || 'PYG',
      min_stock: props.item.min_stock || 0,
      max_stock: props.item.max_stock || 0,
    })
  }
})

// Barcode duplicate check
let barcodeTimer: ReturnType<typeof setTimeout> | null = null
watch(() => form.barcode, (val) => {
  if (barcodeTimer) clearTimeout(barcodeTimer)
  barcodeDuplicateWarning.value = false
  if (!val) return
  barcodeTimer = setTimeout(async () => {
    try {
      const items = await inventoryAPI.getByBarcode(val)
      const others = items.filter((i: InventoryItem) => i.id !== props.item?.id)
      barcodeDuplicateWarning.value = others.length > 0
    } catch {}
  }, 500)
})

function validate() {
  Object.keys(errors).forEach(k => delete errors[k])
  if (!form.name || form.name.length < 2) errors.name = 'Nome deve ter ao menos 2 caracteres'
  if (form.cost_price < 0) errors.cost_price = 'Custo não pode ser negativo'
  if (form.min_stock > form.max_stock && form.max_stock > 0) errors.min_stock = 'Mínimo não pode ser maior que máximo'
  return Object.keys(errors).length === 0
}

async function handleSubmit() {
  if (!validate()) {
    if (errors.name) activeTab.value = 'basic'
    else activeTab.value = 'stock'
    return
  }
  saving.value = true
  try {
    const payload = { ...form, supplier_id: form.supplier_id || null }
    let result: InventoryItem
    if (isEdit.value && props.item) {
      result = await inventoryAPI.updateItem(props.item.id, payload)
    } else {
      result = await inventoryAPI.createItem(payload)
    }
    emit('saved', result)
  } catch (e: any) {
    errors.name = e.response?.data?.detail || 'Erro ao salvar'
  } finally {
    saving.value = false
  }
}

function onBarcodeDetected(code: string) {
  form.barcode = code
  showScanner.value = false
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 500;
  display: flex; align-items: center; justify-content: center; padding: 1rem;
}
.modal-container {
  background: white; border-radius: 12px; width: 100%; max-width: 520px;
  max-height: 90vh; display: flex; flex-direction: column; overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb;
}
.modal-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; }
.tabs { display: flex; border-bottom: 1px solid #e5e7eb; }
.tab { flex: 1; padding: 0.75rem; background: none; border: none; cursor: pointer; font-size: 0.9rem; color: #6b7280; border-bottom: 2px solid transparent; }
.tab.active { color: #3b82f6; border-bottom-color: #3b82f6; font-weight: 600; }
.modal-body { flex: 1; overflow-y: auto; padding: 1.25rem; }
.tab-content { display: flex; flex-direction: column; gap: 1rem; }
.form-group { display: flex; flex-direction: column; gap: 0.25rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.form-group label { font-size: 0.8rem; font-weight: 500; color: #374151; }
.form-input {
  padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 6px;
  font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box;
}
.form-input:focus { border-color: #3b82f6; }
.form-input.error { border-color: #ef4444; }
.error-msg { font-size: 0.75rem; color: #ef4444; }
.warn-msg { font-size: 0.75rem; color: #f59e0b; }
.input-combo { display: flex; gap: 0.5rem; }
.input-combo .form-input { flex: 1; }
.combo-toggle { padding: 0 0.75rem; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; font-size: 1rem; }
.barcode-row { display: flex; gap: 0.5rem; }
.barcode-row .form-input { flex: 1; }
.scan-btn { padding: 0.5rem 0.75rem; background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 6px; cursor: pointer; color: #374151; }
.modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 1rem 1.25rem; border-top: 1px solid #e5e7eb; }
.btn { padding: 0.5rem 1.25rem; border-radius: 6px; font-size: 0.9rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
</style>
