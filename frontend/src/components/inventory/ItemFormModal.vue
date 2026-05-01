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
        <button @click="activeTab = 'photo'" :class="['tab', { active: activeTab === 'photo' }]">
          Foto
          <span v-if="form.image_data" class="tab-dot"></span>
        </button>
      </div>

      <div class="modal-body">
        <!-- ── Basic Tab ── -->
        <div v-if="activeTab === 'basic'" class="tab-content">
          <!-- OCR button -->
          <button @click="showOcr = true" class="ocr-btn" type="button">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Ler etiqueta com câmera (OCR)
          </button>

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
              <label>
                Unidade
                <span v-if="unitAutoSet" class="auto-tag">auto</span>
              </label>
              <select v-model="form.unit" class="form-input">
                <option value="un">un</option>
                <option value="par">par</option>
                <option value="kg">kg</option>
                <option value="m">m</option>
              </select>
            </div>
          </div>
        </div>

        <!-- ── Stock Tab ── -->
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
              <div class="price-with-currency">
                <select v-model="form.cost_currency" class="currency-select">
                  <option value="PYG">G$</option>
                  <option value="BRL">R$</option>
                  <option value="USD">U$</option>
                  <option value="EUR">€</option>
                </select>
                <input v-model.number="form.cost_price" type="number" step="0.01" min="0" class="form-input price-input" :class="{ error: errors.cost_price }" placeholder="0.00" />
              </div>
              <span v-if="errors.cost_price" class="error-msg">{{ errors.cost_price }}</span>
            </div>
            <div class="form-group">
              <label>Preço de Venda</label>
              <div class="price-with-currency">
                <select v-model="form.sale_currency" class="currency-select">
                  <option value="PYG">G$</option>
                  <option value="BRL">R$</option>
                  <option value="USD">U$</option>
                  <option value="EUR">€</option>
                </select>
                <input v-model.number="form.sale_price" type="number" step="0.01" min="0" class="form-input price-input" placeholder="0.00" />
              </div>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group" style="display:none"><!-- currency kept for compat -->
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

        <!-- ── Photo Tab ── -->
        <div v-if="activeTab === 'photo'" class="tab-content">
          <!-- Current image preview -->
          <div v-if="form.image_data" class="photo-preview">
            <img :src="form.image_data" alt="Foto do item" class="item-photo" />
            <button @click="form.image_data = ''" class="remove-photo">× Remover foto</button>
          </div>

          <div v-else class="photo-placeholder">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="40" height="40" class="photo-icon">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
            <p>Nenhuma foto adicionada</p>
          </div>

          <div class="photo-actions">
            <button @click="photoInputRef?.click()" class="btn btn-secondary" type="button">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
              </svg>
              Galeria
            </button>
            <button @click="showCameraPhoto = true" class="btn btn-secondary" type="button">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <circle cx="12" cy="13" r="3" stroke="currentColor" stroke-width="2" fill="none" />
              </svg>
              Câmera
            </button>
          </div>

          <input
            ref="photoInputRef"
            type="file"
            accept="image/*"
            class="hidden-input"
            @change="onPhotoFile"
          />

          <!-- Inline camera capture for photo -->
          <div v-if="showCameraPhoto" class="inline-camera">
            <video ref="photoVideoRef" autoplay playsinline class="inline-video"></video>
            <div class="inline-camera-btns">
              <button @click="capturePhoto" class="btn btn-primary" type="button">Capturar</button>
              <button @click="stopCameraPhoto" class="btn btn-secondary" type="button">Cancelar</button>
            </div>
          </div>

          <p class="photo-hint">A imagem é redimensionada para 400×400px e armazenada no banco de dados.</p>
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
    <OcrScanner v-if="showOcr" @result="onOcrResult" @close="showOcr = false" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, onMounted, onUnmounted } from 'vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import BarcodeScanner from './BarcodeScanner.vue'
import OcrScanner from './OcrScanner.vue'

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
const showOcr = ref(false)
const showCameraPhoto = ref(false)
const saving = ref(false)
const newCategory = ref(false)
const barcodeDuplicateWarning = ref(false)
const unitAutoSet = ref(false)
const photoInputRef = ref<HTMLInputElement>()
const photoVideoRef = ref<HTMLVideoElement>()
let photoStream: MediaStream | null = null

// Category → Unit mapping
const categoryUnitMap: Record<string, string> = {
  'Calçados': 'par',
  'Calcados': 'par',
}

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
  cost_currency: 'BRL',
  sale_currency: 'USD',
  min_stock: 0,
  max_stock: 0,
  is_active: true,
  image_data: '',
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
      cost_currency: (props.item as any).cost_currency || 'BRL',
      sale_currency: (props.item as any).sale_currency || 'USD',
      min_stock: props.item.min_stock || 0,
      max_stock: props.item.max_stock || 0,
      image_data: props.item.image_data || '',
    })
  }
})

onUnmounted(() => {
  if (photoStream) photoStream.getTracks().forEach(t => t.stop())
})

// Auto category → unit
watch(() => form.category, (cat) => {
  if (!cat) return
  const mapped = categoryUnitMap[cat]
  if (mapped && mapped !== form.unit) {
    form.unit = mapped
    unitAutoSet.value = true
    setTimeout(() => { unitAutoSet.value = false }, 2000)
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
      barcodeDuplicateWarning.value = items.filter((i: InventoryItem) => i.id !== props.item?.id).length > 0
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
    activeTab.value = errors.name ? 'basic' : 'stock'
    return
  }
  saving.value = true
  try {
    const payload = {
      ...form,
      supplier_id: form.supplier_id || null,
      image_data: form.image_data || null,
    }
    let result: InventoryItem
    if (isEdit.value && props.item) {
      result = await inventoryAPI.updateItem(props.item.id, payload)
    } else {
      result = await inventoryAPI.createItem(payload)
    }
    emit('saved', result)
  } catch (e: any) {
    errors.name = e.response?.data?.detail || 'Erro ao salvar'
    activeTab.value = 'basic'
  } finally {
    saving.value = false
  }
}

function onBarcodeDetected(code: string) {
  form.barcode = code
  showScanner.value = false
}

function onOcrResult(data: any) {
  showOcr.value = false
  if (data.name) form.name = data.name
  if (data.size) form.size = data.size
  if (data.color) form.color = data.color
  if (data.barcode) form.barcode = data.barcode
  if (data.sale_price) form.sale_price = data.sale_price
  if (data.currency) form.currency = data.currency
}

// Photo handling
function onPhotoFile(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  resizeAndStore(file)
}

function resizeAndStore(source: File | HTMLCanvasElement) {
  if (source instanceof File) {
    const reader = new FileReader()
    reader.onload = (ev) => {
      const img = new Image()
      img.onload = () => { storeResized(img) }
      img.src = ev.target?.result as string
    }
    reader.readAsDataURL(source)
  } else {
    // source is already a canvas
    form.image_data = source.toDataURL('image/jpeg', 0.82)
  }
}

function storeResized(img: HTMLImageElement) {
  const MAX = 400
  const scale = Math.min(MAX / img.width, MAX / img.height, 1)
  const w = Math.round(img.width * scale)
  const h = Math.round(img.height * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w; canvas.height = h
  canvas.getContext('2d')!.drawImage(img, 0, 0, w, h)
  form.image_data = canvas.toDataURL('image/jpeg', 0.82)
  activeTab.value = 'photo'
}

async function stopCameraPhoto() {
  if (photoStream) { photoStream.getTracks().forEach(t => t.stop()); photoStream = null }
  showCameraPhoto.value = false
}

watch(showCameraPhoto, async (val) => {
  if (!val) return
  try {
    photoStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    if (photoVideoRef.value) photoVideoRef.value.srcObject = photoStream
  } catch {
    showCameraPhoto.value = false
  }
})

function capturePhoto() {
  const video = photoVideoRef.value
  if (!video) return
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth; canvas.height = video.videoHeight
  canvas.getContext('2d')!.drawImage(video, 0, 0)
  stopCameraPhoto()
  storeResized(new Image())
  // Use canvas directly
  const MAX = 400
  const scale = Math.min(MAX / canvas.width, MAX / canvas.height, 1)
  const w = Math.round(canvas.width * scale)
  const h = Math.round(canvas.height * scale)
  const out = document.createElement('canvas')
  out.width = w; out.height = h
  out.getContext('2d')!.drawImage(canvas, 0, 0, w, h)
  form.image_data = out.toDataURL('image/jpeg', 0.82)
  activeTab.value = 'photo'
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 500; display: flex; align-items: center; justify-content: center; padding: 1rem; }
.modal-container { background: white; border-radius: 12px; width: 100%; max-width: 520px; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
.modal-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; }
.modal-header h2 { margin: 0; font-size: 1.1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; }
.tabs { display: flex; border-bottom: 1px solid #e5e7eb; }
.tab { flex: 1; padding: 0.75rem; background: none; border: none; cursor: pointer; font-size: 0.9rem; color: #6b7280; border-bottom: 2px solid transparent; position: relative; }
.tab.active { color: #3b82f6; border-bottom-color: #3b82f6; font-weight: 600; }
.tab-dot { width: 6px; height: 6px; background: #10b981; border-radius: 50%; display: inline-block; margin-left: 4px; vertical-align: middle; }
.modal-body { flex: 1; overflow-y: auto; padding: 1.25rem; }
.tab-content { display: flex; flex-direction: column; gap: 1rem; }
.ocr-btn {
  display: flex; align-items: center; gap: 0.5rem; width: 100%;
  padding: 0.6rem 0.75rem; background: #f0fdf4; border: 1px solid #bbf7d0;
  border-radius: 8px; cursor: pointer; color: #15803d; font-size: 0.85rem; font-weight: 500;
}
.ocr-btn:hover { background: #dcfce7; }
.form-group { display: flex; flex-direction: column; gap: 0.25rem; }
.form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
.form-group label { font-size: 0.8rem; font-weight: 500; color: #374151; display: flex; align-items: center; gap: 0.35rem; }
.auto-tag { font-size: 0.65rem; background: #dbeafe; color: #1d4ed8; border-radius: 4px; padding: 0.1rem 0.35rem; }
.form-input { padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 6px; font-size: 0.9rem; outline: none; width: 100%; box-sizing: border-box; }
.price-with-currency { display: flex; gap: 0; }
.currency-select { padding: 0.5rem 0.4rem; border: 1px solid #d1d5db; border-right: none; border-radius: 6px 0 0 6px; font-size: 0.8rem; font-weight: 600; color: #374151; background: #f9fafb; outline: none; cursor: pointer; flex-shrink: 0; }
.currency-select:focus { border-color: #3b82f6; }
.price-input { border-radius: 0 6px 6px 0 !important; }
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
/* Photo tab */
.photo-preview { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; }
.item-photo { width: 100%; max-height: 260px; object-fit: contain; border-radius: 8px; border: 1px solid #e5e7eb; }
.remove-photo { background: none; border: none; color: #ef4444; cursor: pointer; font-size: 0.85rem; }
.photo-placeholder { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2rem; color: #9ca3af; border: 2px dashed #e5e7eb; border-radius: 10px; }
.photo-icon { color: #d1d5db; }
.photo-actions { display: flex; gap: 0.75rem; }
.hidden-input { display: none; }
.inline-camera { margin-top: 0.75rem; border-radius: 8px; overflow: hidden; }
.inline-video { width: 100%; display: block; }
.inline-camera-btns { display: flex; gap: 0.5rem; padding: 0.75rem; background: #f9fafb; }
.photo-hint { font-size: 0.72rem; color: #9ca3af; }
.modal-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 1rem 1.25rem; border-top: 1px solid #e5e7eb; }
.btn { display: flex; align-items: center; gap: 0.4rem; padding: 0.5rem 1.25rem; border-radius: 6px; font-size: 0.9rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
</style>
