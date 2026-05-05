<template>
  <div class="ocr-overlay" @click.self="emit('close')">
    <div class="ocr-modal">
      <div class="ocr-header">
        <div class="ocr-header-left">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18" class="ocr-header-icon">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
          </svg>
          <h3>Ler Etiqueta com IA</h3>
        </div>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Brand selector (always visible) -->
      <div class="brand-bar">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14" class="brand-icon">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
        </svg>
        <input
          v-model="selectedBrand"
          type="text"
          class="brand-input"
          placeholder="Marca (opcional — melhora precisão)"
          list="brand-datalist"
        />
        <datalist id="brand-datalist">
          <option v-for="b in knownBrands" :key="b.brand" :value="b.brand">
            {{ b.brand }} ({{ b.count }} {{ b.count === 1 ? 'modelo' : 'modelos' }})
          </option>
        </datalist>
        <span v-if="selectedBrand && templateCount > 0" class="brand-trained-badge">
          {{ templateCount }} modelo{{ templateCount > 1 ? 's' : '' }} treinado{{ templateCount > 1 ? 's' : '' }}
        </span>
      </div>

      <div class="ocr-body">
        <!-- Camera phase -->
        <div v-if="phase === 'camera'" class="camera-wrap">
          <video ref="videoRef" autoplay playsinline class="camera-feed"></video>
          <div class="scan-frame">
            <div class="corner tl"></div><div class="corner tr"></div>
            <div class="corner bl"></div><div class="corner br"></div>
          </div>
          <p class="camera-hint">Enquadre a etiqueta dentro da moldura</p>
          <button @click="capture" class="capture-btn">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="22" height="22">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <circle cx="12" cy="13" r="3" stroke="currentColor" stroke-width="2" fill="none" />
            </svg>
            Capturar
          </button>
        </div>

        <!-- Processing phase -->
        <div v-if="phase === 'processing'" class="processing-wrap">
          <img v-if="capturedImageUrl" :src="capturedImageUrl" class="preview-img" alt="captura" />
          <div class="processing-status">
            <div class="ai-spinner">
              <div class="ai-dot"></div><div class="ai-dot"></div><div class="ai-dot"></div>
            </div>
            <div class="processing-text">
              <p class="processing-title">Analisando com IA{{ selectedBrand ? ` · ${selectedBrand}` : '' }}</p>
              <p class="processing-sub">{{ statusMsg }}</p>
            </div>
          </div>
        </div>

        <!-- Results phase -->
        <div v-if="phase === 'results'" class="results-wrap">
          <div class="results-top">
            <img v-if="capturedImageUrl" :src="capturedImageUrl" class="preview-thumb" alt="captura" />
            <div class="results-meta">
              <span class="results-brand-pill" v-if="selectedBrand">{{ selectedBrand }}</span>
              <span class="results-hint">Corrija os campos se necessário</span>
            </div>
          </div>

          <!-- Raw text (collapsible) -->
          <details class="raw-text-details" v-if="rawText">
            <summary>Texto detectado na etiqueta</summary>
            <pre class="raw-text">{{ rawText }}</pre>
          </details>

          <!-- Editable fields -->
          <div class="fields-grid">
            <div v-for="field in editableFields" :key="field.key" class="field-card" :class="{ detected: !!field.value }">
              <label class="field-label">{{ field.label }}</label>
              <input
                v-model="field.value"
                type="text"
                class="field-input"
                :placeholder="field.placeholder"
              />
              <div class="field-status">
                <span v-if="field.value" class="fstatus-ok">
                  <svg width="10" height="10" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/></svg>
                  detectado
                </span>
                <span v-else class="fstatus-empty">não detectado</span>
              </div>
            </div>
          </div>

          <div class="results-actions">
            <button @click="retake" class="btn btn-ghost">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Nova foto
            </button>
            <button @click="openSaveTemplate" class="btn btn-learn" title="Salvar este exemplo para treinar a IA">
              <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="14" height="14">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              Treinar IA
            </button>
            <button @click="applyFields" class="btn btn-primary" :disabled="!hasAnyField">
              Usar dados
            </button>
          </div>
        </div>

        <!-- Save template confirmation dialog -->
        <div v-if="phase === 'saving-template'" class="save-template-wrap">
          <img v-if="capturedImageUrl" :src="capturedImageUrl" class="preview-thumb" alt="captura" />

          <div class="save-template-form">
            <h4>Treinar IA com esta etiqueta</h4>
            <p class="save-hint">Salve este exemplo para que a IA aprenda o formato desta marca. Quanto mais exemplos, maior a precisão.</p>

            <div class="stf-group">
              <label>Marca *</label>
              <input v-model="saveForm.brand" type="text" class="stf-input" placeholder="Ex: Nike, Zara, Riachuelo..." list="brand-datalist" />
            </div>
            <div class="stf-group">
              <label>Notas para a IA (opcional)</label>
              <textarea v-model="saveForm.notes" class="stf-input stf-textarea" rows="2"
                placeholder="Ex: 'O modelo fica na 2ª linha'; 'Preços sempre em Guaranis'; 'Tamanho no canto inferior'" />
            </div>

            <div class="stf-fields-preview">
              <span v-for="f in editableFields.filter(f => f.value)" :key="f.key" class="stf-field-chip">
                <strong>{{ f.label }}:</strong> {{ f.value }}
              </span>
            </div>
          </div>

          <div class="results-actions">
            <button @click="phase = 'results'" class="btn btn-ghost">Voltar</button>
            <button @click="saveTemplate" class="btn btn-primary" :disabled="!saveForm.brand || savingTemplate">
              {{ savingTemplate ? 'Salvando...' : 'Salvar modelo' }}
            </button>
          </div>
        </div>

        <!-- Template saved confirmation -->
        <div v-if="phase === 'template-saved'" class="saved-wrap">
          <div class="saved-icon">
            <svg fill="none" viewBox="0 0 24 24" stroke="#10b981" width="36" height="36">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h4>Modelo salvo!</h4>
          <p>Próximas etiquetas de <strong>{{ saveForm.brand }}</strong> serão analisadas com mais precisão.</p>
          <div class="results-actions">
            <button @click="applyFields" class="btn btn-primary">Usar dados detectados</button>
          </div>
        </div>

        <!-- Camera error -->
        <div v-if="phase === 'error'" class="error-wrap">
          <svg fill="none" viewBox="0 0 24 24" stroke="#dc2626" width="32" height="32">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <p class="error-msg-big">{{ errorMsg }}</p>
          <button @click="emit('close')" class="btn btn-ghost">Fechar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, reactive, watch } from 'vue'
import { ocrAPI } from '@/services/api'

interface OcrResult {
  name?: string
  size?: string
  color?: string
  barcode?: string
  sale_price?: number
  currency?: string
}

const emit = defineEmits<{
  (e: 'result', data: OcrResult): void
  (e: 'close'): void
}>()

const videoRef = ref<HTMLVideoElement>()
const capturedImageUrl = ref('')
const phase = ref<'camera' | 'processing' | 'results' | 'saving-template' | 'template-saved' | 'error'>('camera')
const statusMsg = ref('Enviando imagem para análise...')
const rawText = ref('')
const errorMsg = ref('')
const selectedBrand = ref('')
const knownBrands = ref<Array<{ brand: string; count: number }>>([])
const savingTemplate = ref(false)

const saveForm = reactive({ brand: '', notes: '' })

let stream: MediaStream | null = null

interface EditableField {
  key: keyof OcrResult | 'brand'
  label: string
  placeholder: string
  value: string
}

const editableFields = reactive<EditableField[]>([
  { key: 'name',       label: 'Nome do produto', placeholder: 'Ex: Camiseta Polo Basic',   value: '' },
  { key: 'brand',      label: 'Marca',            placeholder: 'Ex: Nike',                  value: '' },
  { key: 'size',       label: 'Tamanho',           placeholder: 'M, G, 42...',               value: '' },
  { key: 'color',      label: 'Cor',               placeholder: 'Azul, Preto...',            value: '' },
  { key: 'barcode',    label: 'Código de barras',  placeholder: '7891234567890',             value: '' },
  { key: 'sale_price', label: 'Preço',             placeholder: '150000',                    value: '' },
])

const hasAnyField = computed(() => editableFields.some(f => f.value.trim()))

const templateCount = computed(() => {
  const b = knownBrands.value.find(k => k.brand.toLowerCase() === selectedBrand.value.toLowerCase())
  return b?.count ?? 0
})

// Sync brand input to brand field
watch(selectedBrand, (val) => {
  const f = editableFields.find(f => f.key === 'brand')
  if (f && !f.value) f.value = val
})

onMounted(async () => {
  // Load known brands
  try {
    knownBrands.value = await ocrAPI.getBrands()
  } catch {}

  // Start camera
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
    })
    if (videoRef.value) videoRef.value.srcObject = stream
  } catch {
    phase.value = 'error'
    errorMsg.value = 'Câmera não disponível. Verifique as permissões do navegador.'
  }
})

onUnmounted(() => {
  if (stream) stream.getTracks().forEach(t => t.stop())
})

function capture() {
  const video = videoRef.value
  if (!video || !video.videoWidth) return

  // Resize to max 1000px width — keep color for Claude Vision
  const MAX = 1000
  const scale = Math.min(MAX / video.videoWidth, 1)
  const w = Math.round(video.videoWidth * scale)
  const h = Math.round(video.videoHeight * scale)
  const canvas = document.createElement('canvas')
  canvas.width = w; canvas.height = h
  canvas.getContext('2d')!.drawImage(video, 0, 0, w, h)

  capturedImageUrl.value = canvas.toDataURL('image/jpeg', 0.85)
  if (stream) stream.getTracks().forEach(t => t.stop())
  phase.value = 'processing'

  runOcr(capturedImageUrl.value)
}

async function runOcr(imageBase64: string) {
  try {
    statusMsg.value = 'Reconhecendo texto e campos...'
    const data = await ocrAPI.parseLabel(imageBase64, selectedBrand.value || undefined)
    populateFields(data)
    phase.value = 'results'
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || 'Erro desconhecido'
    phase.value = 'error'
    errorMsg.value = `Erro ao analisar etiqueta: ${detail}`
  }
}

function populateFields(data: any) {
  rawText.value = data.texto_bruto || ''

  const map: Record<string, string> = {
    name:       data.nome       || '',
    brand:      data.marca      || selectedBrand.value || '',
    size:       data.tamanho    || '',
    color:      data.cor        || '',
    barcode:    data.codigo_barras || '',
    sale_price: data.preco != null ? String(data.preco) : '',
  }

  editableFields.forEach(f => {
    f.value = map[f.key] || ''
  })

  // Sync brand selector
  if (data.marca) selectedBrand.value = data.marca
}

function retake() {
  phase.value = 'camera'
  rawText.value = ''
  capturedImageUrl.value = ''
  editableFields.forEach(f => { f.value = '' })
  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    .then(s => {
      stream = s
      if (videoRef.value) videoRef.value.srcObject = s
    })
    .catch(() => { phase.value = 'error'; errorMsg.value = 'Câmera não disponível.' })
}

function openSaveTemplate() {
  saveForm.brand = selectedBrand.value || editableFields.find(f => f.key === 'brand')?.value || ''
  saveForm.notes = ''
  phase.value = 'saving-template'
}

async function saveTemplate() {
  if (!saveForm.brand) return
  savingTemplate.value = true
  try {
    const nameField   = editableFields.find(f => f.key === 'name')
    const sizeField   = editableFields.find(f => f.key === 'size')
    const colorField  = editableFields.find(f => f.key === 'color')
    const codeField   = editableFields.find(f => f.key === 'barcode')
    const priceField  = editableFields.find(f => f.key === 'sale_price')

    await ocrAPI.saveTemplate({
      brand:            saveForm.brand,
      notes:            saveForm.notes || undefined,
      sample_image:     capturedImageUrl.value,
      parsed_name:      nameField?.value   || undefined,
      parsed_size:      sizeField?.value   || undefined,
      parsed_color:     colorField?.value  || undefined,
      parsed_barcode:   codeField?.value   || undefined,
      parsed_price:     priceField?.value  || undefined,
      parsed_currency:  'PYG',
    })

    // Refresh brand list
    knownBrands.value = await ocrAPI.getBrands().catch(() => knownBrands.value)
    selectedBrand.value = saveForm.brand
    phase.value = 'template-saved'
  } catch (e: any) {
    alert('Erro ao salvar modelo: ' + (e?.response?.data?.detail || e?.message))
    phase.value = 'results'
  } finally {
    savingTemplate.value = false
  }
}

function applyFields() {
  const result: OcrResult = {}
  editableFields.forEach(f => {
    if (!f.value.trim()) return
    if (f.key === 'sale_price') {
      const n = parseFloat(f.value.replace(',', '.'))
      if (!isNaN(n)) result.sale_price = n
    } else if (f.key !== 'brand') {
      (result as any)[f.key] = f.value.trim()
    }
  })
  emit('result', result)
}
</script>

<style scoped>
.ocr-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.82); z-index: 600;
  display: flex; align-items: center; justify-content: center; padding: 1rem;
}
.ocr-modal {
  background: white; border-radius: 14px; width: 100%; max-width: 460px;
  max-height: 92vh; display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 24px 48px rgba(0,0,0,0.4);
}
.ocr-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.85rem 1rem; border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.ocr-header-left { display: flex; align-items: center; gap: 0.5rem; }
.ocr-header-icon { color: #6366f1; }
.ocr-header h3 { margin: 0; font-size: 0.95rem; font-weight: 600; color: #111827; }
.close-btn { background: none; border: none; cursor: pointer; color: #9ca3af; padding: 0.25rem; }
.close-btn:hover { color: #374151; }

/* Brand bar */
.brand-bar {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.5rem 0.75rem; background: #f8fafc; border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.brand-icon { color: #6b7280; flex-shrink: 0; }
.brand-input {
  flex: 1; border: 1px solid #d1d5db; border-radius: 6px; padding: 0.3rem 0.5rem;
  font-size: 0.82rem; outline: none; background: white;
}
.brand-input:focus { border-color: #6366f1; }
.brand-trained-badge {
  font-size: 0.65rem; font-weight: 700; background: #e0e7ff; color: #4338ca;
  border-radius: 99px; padding: 0.1rem 0.5rem; white-space: nowrap; flex-shrink: 0;
}

.ocr-body { flex: 1; overflow-y: auto; }

/* Camera */
.camera-wrap { position: relative; background: #000; }
.camera-feed { width: 100%; display: block; max-height: 280px; object-fit: cover; }
.scan-frame { position: absolute; top: 12%; left: 8%; right: 8%; bottom: 12%; pointer-events: none; }
.corner { position: absolute; width: 18px; height: 18px; border-color: #818cf8; border-style: solid; }
.tl { top: 0; left: 0; border-width: 3px 0 0 3px; }
.tr { top: 0; right: 0; border-width: 3px 3px 0 0; }
.bl { bottom: 0; left: 0; border-width: 0 0 3px 3px; }
.br { bottom: 0; right: 0; border-width: 0 3px 3px 0; }
.camera-hint { text-align: center; font-size: 0.72rem; color: #9ca3af; padding: 0.4rem; background: #000; margin: 0; }
.capture-btn {
  display: flex; align-items: center; gap: 0.5rem; justify-content: center;
  width: calc(100% - 2rem); margin: 0.65rem 1rem;
  padding: 0.7rem; background: #6366f1; color: white;
  border: none; border-radius: 8px; cursor: pointer; font-size: 0.9rem; font-weight: 600;
  transition: background 0.15s;
}
.capture-btn:hover { background: #4f46e5; }

/* Processing */
.processing-wrap { padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }
.preview-img { width: 100%; border-radius: 8px; display: block; max-height: 180px; object-fit: cover; }
.processing-status {
  display: flex; align-items: center; gap: 0.75rem;
  background: #f8f8ff; border: 1px solid #e0e7ff; border-radius: 8px; padding: 0.75rem 1rem;
}
.ai-spinner { display: flex; gap: 5px; align-items: center; }
.ai-dot {
  width: 8px; height: 8px; background: #6366f1; border-radius: 50%;
  animation: bounce 1.2s infinite ease-in-out;
}
.ai-dot:nth-child(2) { animation-delay: 0.2s; }
.ai-dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }
.processing-title { margin: 0; font-size: 0.85rem; font-weight: 600; color: #4338ca; }
.processing-sub { margin: 0; font-size: 0.75rem; color: #6b7280; }

/* Results */
.results-wrap { padding: 0.75rem; display: flex; flex-direction: column; gap: 0.75rem; }
.results-top { display: flex; align-items: center; gap: 0.75rem; }
.preview-thumb { width: 72px; height: 72px; object-fit: cover; border-radius: 6px; flex-shrink: 0; border: 1px solid #e5e7eb; }
.results-meta { display: flex; flex-direction: column; gap: 0.3rem; }
.results-brand-pill {
  display: inline-block; background: #e0e7ff; color: #4338ca;
  border-radius: 99px; padding: 0.15rem 0.6rem; font-size: 0.72rem; font-weight: 700;
}
.results-hint { font-size: 0.72rem; color: #9ca3af; }

.raw-text-details { font-size: 0.75rem; }
.raw-text-details summary { cursor: pointer; color: #6b7280; padding: 0.25rem 0; }
.raw-text {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px;
  padding: 0.5rem; font-size: 0.7rem; white-space: pre-wrap; max-height: 70px;
  overflow-y: auto; margin: 0.25rem 0 0;
}

.fields-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; }
.field-card {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 0.5rem 0.6rem;
  display: flex; flex-direction: column; gap: 0.2rem; transition: border-color 0.15s;
}
.field-card.detected { background: #f0fdf4; border-color: #bbf7d0; }
.field-label { font-size: 0.65rem; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: 0.03em; }
.field-input {
  border: none; background: transparent; font-size: 0.85rem; color: #111827;
  font-weight: 500; outline: none; padding: 0; width: 100%;
}
.field-input:focus { color: #4338ca; }
.field-status { display: flex; align-items: center; }
.fstatus-ok {
  display: flex; align-items: center; gap: 3px;
  font-size: 0.6rem; color: #16a34a; font-weight: 600;
}
.fstatus-empty { font-size: 0.6rem; color: #d1d5db; }

.results-actions { display: flex; gap: 0.5rem; justify-content: flex-end; padding-top: 0.25rem; }
.btn {
  display: flex; align-items: center; gap: 0.35rem;
  padding: 0.45rem 0.9rem; border-radius: 6px; font-size: 0.82rem;
  cursor: pointer; border: none; font-weight: 500; transition: all 0.15s;
}
.btn-primary { background: #6366f1; color: white; }
.btn-primary:hover:not(:disabled) { background: #4f46e5; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-ghost { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }
.btn-ghost:hover { background: #e5e7eb; }
.btn-learn { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.btn-learn:hover { background: #fde68a; }

/* Save template phase */
.save-template-wrap { padding: 0.85rem; display: flex; flex-direction: column; gap: 0.75rem; }
.save-template-form { display: flex; flex-direction: column; gap: 0.6rem; }
.save-template-form h4 { margin: 0; font-size: 0.9rem; font-weight: 600; color: #1f2937; }
.save-hint { margin: 0; font-size: 0.78rem; color: #6b7280; }
.stf-group { display: flex; flex-direction: column; gap: 0.2rem; }
.stf-group label { font-size: 0.72rem; font-weight: 600; color: #374151; }
.stf-input {
  padding: 0.45rem 0.6rem; border: 1px solid #d1d5db; border-radius: 6px;
  font-size: 0.85rem; outline: none; width: 100%; box-sizing: border-box;
}
.stf-input:focus { border-color: #6366f1; }
.stf-textarea { resize: vertical; min-height: 56px; font-family: inherit; }
.stf-fields-preview { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.stf-field-chip {
  font-size: 0.72rem; background: #f0fdf4; border: 1px solid #bbf7d0;
  border-radius: 6px; padding: 0.2rem 0.5rem; color: #166534;
}

/* Template saved */
.saved-wrap {
  padding: 2rem 1.5rem; display: flex; flex-direction: column; align-items: center; gap: 0.75rem; text-align: center;
}
.saved-icon { animation: pop 0.4s ease; }
@keyframes pop { 0% { transform: scale(0.5); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
.saved-wrap h4 { margin: 0; font-size: 1rem; font-weight: 700; color: #065f46; }
.saved-wrap p { margin: 0; font-size: 0.85rem; color: #374151; }

/* Error */
.error-wrap { padding: 2rem 1.5rem; display: flex; flex-direction: column; align-items: center; gap: 0.75rem; text-align: center; }
.error-msg-big { color: #dc2626; font-size: 0.85rem; }

@media (max-width: 500px) {
  .fields-grid { grid-template-columns: 1fr; }
}
</style>
