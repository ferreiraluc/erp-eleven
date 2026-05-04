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
          <p class="section-hint">Deixe em branco para não alterar nesses itens.</p>

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

          <!-- Brand + Category in a row -->
          <div class="form-row">
            <div class="form-group">
              <label>Marca</label>
              <input v-model="sharedBrand" type="text" class="form-input" placeholder="Ex: Nike (vazio = não alterar)" :list="'bulk-brand-list'" />
              <datalist id="bulk-brand-list">
                <option v-for="b in distinctBrands" :key="b" :value="b" />
              </datalist>
            </div>
            <div class="form-group">
              <label>Categoria</label>
              <input v-model="sharedCategory" type="text" class="form-input" placeholder="Ex: Camisetas (vazio = não alterar)" :list="'bulk-cat-list'" />
              <datalist id="bulk-cat-list">
                <option v-for="c in distinctCategories" :key="c" :value="c" />
              </datalist>
            </div>
          </div>
        </section>

        <!-- ── Per-item fields ── -->
        <section class="section">
          <h3 class="section-title">Campos por item</h3>
          <p class="section-hint">Deixe em branco para manter o valor atual de cada item.</p>
          <div class="items-list">
            <div v-for="item in items" :key="item.id" class="item-card">
              <!-- Item header -->
              <div class="item-card-header">
                <img v-if="sharedImage || item.image_data" :src="sharedImage || item.image_data" class="card-thumb" alt="" />
                <div v-else class="card-thumb-placeholder"></div>
                <span class="card-original-name">{{ item.name }}</span>
              </div>
              <!-- Editable fields grid -->
              <div class="item-fields">
                <div class="field-group">
                  <label>Nome</label>
                  <input
                    v-model="itemNames[item.id]"
                    type="text"
                    class="field-input"
                    :placeholder="item.name"
                  />
                </div>
                <div class="field-group">
                  <label>Cor</label>
                  <input
                    v-model="itemColors[item.id]"
                    type="text"
                    class="field-input"
                    :placeholder="item.color || 'Cor'"
                  />
                </div>
                <div class="field-group">
                  <label>Tamanho</label>
                  <input
                    v-model="itemSizes[item.id]"
                    type="text"
                    class="field-input"
                    :placeholder="item.size || 'Tam'"
                  />
                </div>
                <div class="field-group field-group-wide">
                  <label>Código de barras</label>
                  <input
                    v-model="itemBarcodes[item.id]"
                    type="text"
                    class="field-input"
                    :placeholder="item.barcode || 'Código de barras'"
                  />
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
const saving = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

// Per-item field maps (empty = keep as-is)
const itemNames = reactive<Record<string, string>>({})
const itemColors = reactive<Record<string, string>>({})
const itemSizes = reactive<Record<string, string>>({})
const itemBarcodes = reactive<Record<string, string>>({})

const hasChanges = computed(() => {
  if (sharedImage.value || sharedBrand.value || sharedCategory.value) return true
  return props.items.some(item =>
    itemNames[item.id] || itemColors[item.id] ||
    itemSizes[item.id] || itemBarcodes[item.id]
  )
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

async function save() {
  if (!hasChanges.value || saving.value) return
  saving.value = true
  try {
    const perItems: Array<{ id: string; size?: string; name?: string; color?: string; barcode?: string }> = []
    for (const item of props.items) {
      const entry: { id: string; size?: string; name?: string; color?: string; barcode?: string } = { id: item.id }
      let hasEntry = false
      if (itemSizes[item.id])    { entry.size    = itemSizes[item.id];    hasEntry = true }
      if (itemNames[item.id])    { entry.name    = itemNames[item.id];    hasEntry = true }
      if (itemColors[item.id])   { entry.color   = itemColors[item.id];   hasEntry = true }
      if (itemBarcodes[item.id]) { entry.barcode = itemBarcodes[item.id]; hasEntry = true }
      if (hasEntry) perItems.push(entry)
    }

    await inventoryAPI.batchEdit({
      item_ids: props.items.map(i => i.id),
      brand:      sharedBrand.value    || undefined,
      category:   sharedCategory.value || undefined,
      image_data: sharedImage.value    || undefined,
      sizes: perItems.length ? perItems : undefined,
    })

    emit('saved')
  } catch (e: any) {
    alert(e.response?.data?.detail || 'Erro ao salvar')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; padding: 1rem;
}
.modal-container {
  background: white; border-radius: 12px; width: 100%;
  max-width: 600px; max-height: 92vh;
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
.form-group label { font-size: 0.78rem; font-weight: 500; color: #374151; }
.form-row { display: flex; gap: 0.75rem; }
.form-input { padding: 0.42rem 0.7rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.85rem; }
.form-input:focus { outline: none; border-color: #3b82f6; }

/* Image */
.image-area { }
.image-preview { position: relative; display: inline-block; }
.image-preview img { width: 72px; height: 72px; object-fit: cover; border-radius: 8px; border: 1px solid #e5e7eb; }
.remove-img-btn { position: absolute; top: -6px; right: -6px; width: 18px; height: 18px; border-radius: 50%; background: #ef4444; color: white; border: none; cursor: pointer; font-size: 0.75rem; display: flex; align-items: center; justify-content: center; }
.image-placeholder { width: 72px; height: 72px; border: 2px dashed #d1d5db; border-radius: 8px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.2rem; cursor: pointer; color: #9ca3af; font-size: 0.58rem; text-align: center; }
.image-placeholder:hover { border-color: #3b82f6; color: #3b82f6; }
.hidden-input { display: none; }

/* Per-item list */
.items-list { display: flex; flex-direction: column; gap: 0.6rem; max-height: 340px; overflow-y: auto; }
.item-card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.6rem 0.75rem; background: #fafafa; display: flex; flex-direction: column; gap: 0.5rem; }
.item-card-header { display: flex; align-items: center; gap: 0.5rem; }
.card-thumb { width: 28px; height: 28px; object-fit: cover; border-radius: 4px; flex-shrink: 0; }
.card-thumb-placeholder { width: 28px; height: 28px; background: #e5e7eb; border-radius: 4px; flex-shrink: 0; }
.card-original-name { font-size: 0.78rem; font-weight: 600; color: #374151; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* Fields grid inside card */
.item-fields { display: grid; grid-template-columns: 1fr 1fr; gap: 0.4rem 0.6rem; }
.field-group { display: flex; flex-direction: column; gap: 0.15rem; }
.field-group-wide { grid-column: 1 / -1; }
.field-group label { font-size: 0.68rem; font-weight: 500; color: #6b7280; text-transform: uppercase; letter-spacing: 0.03em; }
.field-input { padding: 0.3rem 0.5rem; border: 1px solid #e5e7eb; border-radius: 5px; font-size: 0.82rem; background: white; }
.field-input:focus { outline: none; border-color: #3b82f6; background: #eff6ff; }

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
}
</style>
