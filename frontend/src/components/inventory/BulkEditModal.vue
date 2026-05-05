<template>
  <div class="modal-overlay" @click.self="emit('close')">
    <div class="modal-container">
      <div class="modal-header">
        <h2>Editar Massivo <span class="item-count">({{ items.length }} itens)</span></h2>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <!-- ── Shared fields ── -->
        <section class="section">
          <h3 class="section-title">Campos compartilhados</h3>
          <p class="section-hint">Deixe em branco para não alterar. Aplica a todos os itens selecionados.</p>

          <!-- Image -->
          <div class="form-group">
            <label>Imagem (aplicar a todos)</label>
            <div class="image-area">
              <div v-if="sharedImage" class="image-preview">
                <img :src="sharedImage" alt="Preview" />
                <button @click="sharedImage = ''" class="remove-img-btn" type="button">×</button>
              </div>
              <div v-else class="image-placeholder" @click="triggerFileInput">
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="32" height="32"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" /></svg>
                <span>Clique para selecionar</span>
              </div>
              <input ref="fileInputRef" type="file" accept="image/*" class="hidden-input" @change="onImageFile" />
            </div>
          </div>

          <!-- Brand + Category -->
          <div class="form-row">
            <div class="form-group">
              <label>Marca</label>
              <input v-model="sharedBrand" type="text" class="form-input" placeholder="Vazio = não alterar" :list="'bulk-brand-list'" />
              <datalist id="bulk-brand-list">
                <option v-for="b in distinctBrands" :key="b" :value="b" />
              </datalist>
            </div>
            <div class="form-group">
              <label>Categoria</label>
              <input v-model="sharedCategory" type="text" class="form-input" placeholder="Vazio = não alterar" :list="'bulk-cat-list'" />
              <datalist id="bulk-cat-list">
                <option v-for="c in distinctCategories" :key="c" :value="c" />
              </datalist>
            </div>
          </div>

          <!-- Shared prices -->
          <div class="form-row">
            <div class="form-group">
              <label>Preço de custo</label>
              <input v-model="sharedCostPrice" type="number" min="0" step="any" class="form-input" placeholder="Vazio = não alterar" />
            </div>
            <div class="form-group">
              <label>Preço de venda</label>
              <input v-model="sharedSalePrice" type="number" min="0" step="any" class="form-input" placeholder="Vazio = não alterar" />
            </div>
          </div>

          <!-- Shared stock adjustment -->
          <div class="stock-adjust-block">
            <div class="stock-adjust-header">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
              </svg>
              <span>Ajuste de estoque compartilhado</span>
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>Quantidade <span class="label-hint">(+ entrada / − saída)</span></label>
                <input
                  v-model.number="sharedStockDelta"
                  type="number"
                  class="form-input"
                  :class="{ 'input-entry': sharedStockDelta > 0, 'input-exit': sharedStockDelta < 0 }"
                  placeholder="Ex: +5 ou -3"
                />
              </div>
              <div class="form-group">
                <label>
                  Motivo
                  <span v-if="sharedStockDelta && sharedStockDelta !== 0" class="required-mark">*</span>
                </label>
                <input
                  v-model="sharedStockReason"
                  type="text"
                  class="form-input"
                  :class="{ error: stockErrors.shared }"
                  placeholder="Motivo obrigatório"
                />
                <span v-if="stockErrors.shared" class="error-msg">{{ stockErrors.shared }}</span>
              </div>
            </div>
            <p class="stock-adjust-hint">
              Itens com ajuste individual abaixo têm prioridade sobre este valor.
            </p>
          </div>
        </section>

        <!-- ── Per-item fields ── -->
        <section class="section">
          <h3 class="section-title">Campos por item</h3>
          <p class="section-hint">Os campos de texto mostram o valor atual — edite apenas o que precisa alterar.</p>
          <div class="items-list">
            <div v-for="item in items" :key="item.id" class="item-card">
              <!-- Item header -->
              <div class="item-card-header">
                <img v-if="sharedImage || item.image_data" :src="sharedImage || item.image_data" class="card-thumb" alt="" />
                <div v-else class="card-thumb-placeholder"></div>
                <div class="card-header-info">
                  <span class="card-original-name">{{ item.name }}</span>
                  <span class="card-stock-badge">Estoque: {{ item.current_stock }}</span>
                </div>
              </div>

              <!-- Text fields (pre-populated) -->
              <div class="item-fields">
                <div class="field-group field-group-wide">
                  <label>Nome</label>
                  <input
                    v-model="itemNames[item.id]"
                    type="text"
                    class="field-input"
                    :class="{ modified: itemNames[item.id] !== item.name }"
                  />
                </div>
                <div class="field-group">
                  <label>Cor</label>
                  <input
                    v-model="itemColors[item.id]"
                    type="text"
                    class="field-input"
                    :class="{ modified: itemColors[item.id] !== (item.color || '') }"
                  />
                </div>
                <div class="field-group">
                  <label>Tamanho</label>
                  <input
                    v-model="itemSizes[item.id]"
                    type="text"
                    class="field-input"
                    :placeholder="item.size || ''"
                  />
                </div>
                <div class="field-group field-group-wide">
                  <label>Código de barras</label>
                  <input
                    v-model="itemBarcodes[item.id]"
                    type="text"
                    class="field-input"
                    :class="{ modified: itemBarcodes[item.id] !== (item.barcode || '') }"
                  />
                </div>

                <!-- Per-item prices -->
                <div class="field-group">
                  <label>Custo <span class="label-current">atual: {{ formatPrice(item.cost_price) }}</span></label>
                  <input
                    v-model="itemCostPrices[item.id]"
                    type="number"
                    min="0"
                    step="any"
                    class="field-input"
                    placeholder="Vazio = não alterar"
                  />
                </div>
                <div class="field-group">
                  <label>Venda <span class="label-current">atual: {{ formatPrice(item.sale_price) }}</span></label>
                  <input
                    v-model="itemSalePrices[item.id]"
                    type="number"
                    min="0"
                    step="any"
                    class="field-input"
                    placeholder="Vazio = não alterar"
                  />
                </div>

                <!-- Per-item stock -->
                <div class="field-group">
                  <label>Δ Estoque <span class="label-hint">(+ / −)</span></label>
                  <input
                    v-model.number="itemStockDeltas[item.id]"
                    type="number"
                    class="field-input"
                    :class="{ 'input-entry': itemStockDeltas[item.id] > 0, 'input-exit': itemStockDeltas[item.id] < 0 }"
                    placeholder="Ex: +2 ou -1"
                  />
                </div>
                <div class="field-group">
                  <label>
                    Motivo
                    <span v-if="itemStockDeltas[item.id] && itemStockDeltas[item.id] !== 0" class="required-mark">*</span>
                  </label>
                  <input
                    v-model="itemStockReasons[item.id]"
                    type="text"
                    class="field-input"
                    :class="{ error: stockErrors[item.id] }"
                    placeholder="Motivo do ajuste"
                  />
                  <span v-if="stockErrors[item.id]" class="error-msg">{{ stockErrors[item.id] }}</span>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div class="modal-footer">
        <button @click="emit('close')" class="btn btn-secondary" :disabled="saving">Cancelar</button>
        <button @click="save" class="btn btn-primary" :disabled="saving || !hasChanges">
          <span v-if="saving">Salvando...</span>
          <span v-else>Salvar {{ items.length }} itens</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'

const props = defineProps<{
  items: InventoryItem[]
  distinctBrands?: string[]
  distinctCategories?: string[]
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

const sharedImage = ref('')
const sharedBrand = ref('')
const sharedCategory = ref('')
const sharedCostPrice = ref<string>('')
const sharedSalePrice = ref<string>('')
const sharedStockDelta = ref<number>(0)
const sharedStockReason = ref('')
const saving = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const stockErrors = reactive<Record<string, string>>({})

// Per-item maps — pre-populated with current values for text fields
const itemNames     = reactive<Record<string, string>>(Object.fromEntries(props.items.map(i => [i.id, i.name])))
const itemColors    = reactive<Record<string, string>>(Object.fromEntries(props.items.map(i => [i.id, i.color || ''])))
const itemSizes     = reactive<Record<string, string>>({})
const itemBarcodes  = reactive<Record<string, string>>(Object.fromEntries(props.items.map(i => [i.id, i.barcode || ''])))
const itemCostPrices  = reactive<Record<string, string>>({})
const itemSalePrices  = reactive<Record<string, string>>({})
const itemStockDeltas = reactive<Record<string, number>>({})
const itemStockReasons = reactive<Record<string, string>>({})

function formatPrice(val: any): string {
  if (val === null || val === undefined || val === '' || val === 0) return '—'
  return Number(val).toLocaleString('pt-BR')
}

const hasChanges = computed(() => {
  if (sharedImage.value || sharedBrand.value || sharedCategory.value) return true
  if (sharedCostPrice.value !== '' || sharedSalePrice.value !== '') return true
  if (sharedStockDelta.value && sharedStockDelta.value !== 0) return true
  return props.items.some(item => {
    if (itemNames[item.id] !== item.name) return true
    if (itemColors[item.id] !== (item.color || '')) return true
    if (itemSizes[item.id]) return true
    if (itemBarcodes[item.id] !== (item.barcode || '')) return true
    if (itemCostPrices[item.id] !== '' && itemCostPrices[item.id] !== undefined) return true
    if (itemSalePrices[item.id] !== '' && itemSalePrices[item.id] !== undefined) return true
    if (itemStockDeltas[item.id] && itemStockDeltas[item.id] !== 0) return true
    return false
  })
})

function triggerFileInput() {
  fileInputRef.value?.click()
}

function onImageFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (ev) => {
    const img = new Image()
    img.onload = () => {
      const MAX = 400
      const scale = Math.min(MAX / img.width, MAX / img.height, 1)
      const w = Math.round(img.width * scale)
      const h = Math.round(img.height * scale)
      const canvas = document.createElement('canvas')
      canvas.width = w; canvas.height = h
      canvas.getContext('2d')!.drawImage(img, 0, 0, w, h)
      sharedImage.value = canvas.toDataURL('image/jpeg', 0.82)
    }
    img.src = ev.target?.result as string
  }
  reader.readAsDataURL(file)
  input.value = ''
}

function validateStock(): boolean {
  // Clear previous errors
  Object.keys(stockErrors).forEach(k => delete stockErrors[k])

  let valid = true
  if (sharedStockDelta.value && sharedStockDelta.value !== 0 && !sharedStockReason.value.trim()) {
    stockErrors.shared = 'Informe o motivo do ajuste'
    valid = false
  }
  for (const item of props.items) {
    const delta = itemStockDeltas[item.id]
    if (delta && delta !== 0 && !itemStockReasons[item.id]?.trim()) {
      stockErrors[item.id] = 'Informe o motivo'
      valid = false
    }
  }
  return valid
}

async function save() {
  if (!hasChanges.value || saving.value) return
  if (!validateStock()) return

  saving.value = true
  try {
    const perItems: Array<{
      id: string; size?: string; name?: string; color?: string; barcode?: string
      cost_price?: number; sale_price?: number; stock_delta?: number; stock_reason?: string
    }> = []

    for (const item of props.items) {
      const entry: typeof perItems[0] = { id: item.id }
      let changed = false

      if (itemSizes[item.id])                               { entry.size    = itemSizes[item.id];    changed = true }
      if (itemNames[item.id] !== item.name)                  { entry.name    = itemNames[item.id];    changed = true }
      if (itemColors[item.id] !== (item.color || ''))        { entry.color   = itemColors[item.id];   changed = true }
      if (itemBarcodes[item.id] !== (item.barcode || ''))    { entry.barcode = itemBarcodes[item.id]; changed = true }

      const cp = itemCostPrices[item.id]
      const sp = itemSalePrices[item.id]
      if (cp !== '' && cp !== undefined)  { entry.cost_price = Number(cp); changed = true }
      if (sp !== '' && sp !== undefined)  { entry.sale_price = Number(sp); changed = true }

      const delta = itemStockDeltas[item.id]
      if (delta && delta !== 0) {
        entry.stock_delta  = delta
        entry.stock_reason = itemStockReasons[item.id] || ''
        changed = true
      }

      if (changed) perItems.push(entry)
    }

    await inventoryAPI.batchEdit({
      item_ids:    props.items.map(i => i.id),
      brand:       sharedBrand.value    || undefined,
      category:    sharedCategory.value || undefined,
      image_data:  sharedImage.value    || undefined,
      cost_price:  sharedCostPrice.value !== '' ? Number(sharedCostPrice.value) : undefined,
      sale_price:  sharedSalePrice.value !== '' ? Number(sharedSalePrice.value) : undefined,
      stock_delta:  (sharedStockDelta.value && sharedStockDelta.value !== 0) ? sharedStockDelta.value : undefined,
      stock_reason: sharedStockReason.value || undefined,
      sizes: perItems.length ? perItems : undefined,
    })

    emit('saved')
  } catch (e: any) {
    console.error('Bulk edit error:', e.response?.status, e.response?.data, e.message)
    const detail = e.response?.data?.detail
    const msg = typeof detail === 'string'
      ? detail
      : Array.isArray(detail)
        ? detail.map((d: any) => d.msg || d.loc?.join('.') || JSON.stringify(d)).join('\n')
        : e.message || 'Erro ao salvar'
    alert(msg)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 2500; padding: 1rem;
}
.modal-container {
  background: white; border-radius: 12px; width: 100%;
  max-width: 620px; max-height: 92vh;
  display: flex; flex-direction: column; overflow: hidden;
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.modal-header h2 { font-size: 1rem; font-weight: 700; color: #111827; margin: 0; }
.item-count { font-weight: 400; color: #6b7280; font-size: 0.875rem; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; padding: 0.25rem; }
.modal-body { overflow-y: auto; padding: 1rem 1.25rem; flex: 1; display: flex; flex-direction: column; gap: 1.25rem; }
.section { display: flex; flex-direction: column; gap: 0.6rem; }
.section-title { font-size: 0.875rem; font-weight: 600; color: #374151; margin: 0; }
.section-hint { font-size: 0.72rem; color: #9ca3af; margin: 0; }
.form-group { display: flex; flex-direction: column; gap: 0.3rem; flex: 1; }
.form-group label { font-size: 0.78rem; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 0.3rem; }
.form-row { display: flex; gap: 0.75rem; }
.form-input { padding: 0.42rem 0.7rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; }
.form-input:focus { outline: none; border-color: #3b82f6; }
.form-input.error { border-color: #ef4444; }

/* Labels helpers */
.label-hint { font-size: 0.68rem; font-weight: 400; color: #9ca3af; }
.label-current { font-size: 0.65rem; font-weight: 400; color: #9ca3af; }
.required-mark { color: #ef4444; font-size: 0.75rem; }
.error-msg { font-size: 0.72rem; color: #ef4444; }

/* Stock inputs colors */
.input-entry { border-color: #86efac !important; background: #f0fdf4; color: #15803d; }
.input-exit  { border-color: #fca5a5 !important; background: #fff5f5; color: #b91c1c; }

/* Stock adjust block */
.stock-adjust-block {
  background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px;
  padding: 0.75rem; display: flex; flex-direction: column; gap: 0.5rem;
}
.stock-adjust-header {
  display: flex; align-items: center; gap: 0.4rem;
  font-size: 0.78rem; font-weight: 600; color: #475569;
}
.stock-adjust-hint { font-size: 0.68rem; color: #94a3b8; margin: 0; }

/* Image */
.image-area { }
.image-preview { position: relative; display: inline-block; }
.image-preview img { width: 72px; height: 72px; object-fit: cover; border-radius: 8px; border: 1px solid #e5e7eb; }
.remove-img-btn { position: absolute; top: -6px; right: -6px; width: 18px; height: 18px; border-radius: 50%; background: #ef4444; color: white; border: none; cursor: pointer; font-size: 0.75rem; display: flex; align-items: center; justify-content: center; }
.image-placeholder { width: 72px; height: 72px; border: 2px dashed #d1d5db; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.2rem; cursor: pointer; color: #9ca3af; font-size: 0.58rem; text-align: center; }
.image-placeholder:hover { border-color: #3b82f6; color: #3b82f6; }
.hidden-input { display: none; }

/* Per-item list */
.items-list { display: flex; flex-direction: column; gap: 0.6rem; max-height: 420px; overflow-y: auto; }
.item-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.6rem 0.75rem; background: #fafafa; display: flex; flex-direction: column; gap: 0.5rem; }
.item-card-header { display: flex; align-items: center; gap: 0.5rem; }
.card-thumb { width: 28px; height: 28px; object-fit: cover; border-radius: 4px; flex-shrink: 0; }
.card-thumb-placeholder { width: 28px; height: 28px; background: #e5e7eb; border-radius: 4px; flex-shrink: 0; }
.card-header-info { display: flex; align-items: center; gap: 0.5rem; min-width: 0; flex: 1; }
.card-original-name { font-size: 0.78rem; font-weight: 600; color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; }
.card-stock-badge { font-size: 0.68rem; color: #64748b; background: #f1f5f9; border-radius: 4px; padding: 0.1rem 0.4rem; white-space: nowrap; flex-shrink: 0; }

/* Fields grid inside card */
.item-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem 0.6rem; }
.field-group { display: flex; flex-direction: column; gap: 0.15rem; }
.field-group-wide { grid-column: 1 / -1; }
.field-group label { font-size: 0.68rem; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.03em; display: flex; align-items: center; gap: 0.25rem; }
.field-input { padding: 0.3rem 0.5rem; border: 1px solid #e5e7eb; border-radius: 5px; font-size: 0.82rem; background: white; }
.field-input:focus { outline: none; border-color: #3b82f6; background: #eff6ff; }
.field-input.modified { border-color: #f59e0b; background: #fffbeb; }

/* Footer */
.modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 0.875rem 1.25rem; border-top: 1px solid #e5e7eb; flex-shrink: 0; }
.btn { padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.875rem; font-weight: 500; cursor: pointer; border: none; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { background: #93c5fd; cursor: not-allowed; }
.btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 600px) {
  .modal-container { max-height: 96vh; }
  .form-row { flex-direction: column; gap: 0.5rem; }
  .item-fields { grid-template-columns: 1fr 1fr; }
  .items-list { max-height: none; }
}
</style>
