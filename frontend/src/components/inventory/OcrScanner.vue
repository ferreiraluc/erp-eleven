<template>
  <div class="ocr-overlay" @click.self="emit('close')">
    <div class="ocr-modal">
      <div class="ocr-header">
        <h3>Ler Etiqueta (OCR)</h3>
        <button @click="emit('close')" class="close-btn">
          <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="ocr-body">
        <!-- Camera preview -->
        <div v-if="phase === 'camera'" class="camera-wrap">
          <video ref="videoRef" autoplay playsinline class="camera-feed"></video>
          <div class="scan-frame">
            <div class="corner tl"></div><div class="corner tr"></div>
            <div class="corner bl"></div><div class="corner br"></div>
          </div>
          <p class="camera-hint">Enquadre a etiqueta dentro da moldura</p>
          <button @click="capture" class="capture-btn">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="24" height="24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
              <circle cx="12" cy="13" r="3" stroke="currentColor" stroke-width="2" fill="none" />
            </svg>
            Capturar
          </button>
        </div>

        <!-- Processing -->
        <div v-if="phase === 'processing'" class="processing-wrap">
          <img v-if="capturedImageUrl" :src="capturedImageUrl" class="preview-canvas" alt="captura" />
          <div class="processing-status">
            <div class="spinner"></div>
            <p>{{ statusMsg }}</p>
          </div>
        </div>

        <!-- Results -->
        <div v-if="phase === 'results'" class="results-wrap">
          <img v-if="capturedImageUrl" :src="capturedImageUrl" class="preview-canvas-small" alt="captura" />

          <div class="raw-text-box">
            <label>Texto detectado:</label>
            <pre class="raw-text">{{ rawText }}</pre>
          </div>

          <div class="fields-list">
            <div v-for="field in suggestedFields" :key="field.key" class="field-row" :class="{ detected: field.value }">
              <div class="field-info">
                <span class="field-label">{{ field.label }}</span>
                <span v-if="field.value" class="field-value">{{ field.value }}</span>
                <span v-else class="field-empty">não detectado</span>
              </div>
              <label class="field-check">
                <input type="checkbox" v-model="field.accepted" :disabled="!field.value" />
              </label>
            </div>
          </div>

          <div class="results-actions">
            <button @click="retake" class="btn btn-secondary">Repetir</button>
            <button @click="applyFields" class="btn btn-primary" :disabled="!hasAnyAccepted">
              Usar dados selecionados
            </button>
          </div>
        </div>

        <!-- Camera error -->
        <div v-if="phase === 'error'" class="error-wrap">
          <p class="error-msg-big">{{ errorMsg }}</p>
          <button @click="emit('close')" class="btn btn-secondary">Fechar</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, reactive } from 'vue'

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
const phase = ref<'camera' | 'processing' | 'results' | 'error'>('camera')
const statusMsg = ref('Preparando OCR...')
const rawText = ref('')
const errorMsg = ref('')

let stream: MediaStream | null = null

interface SuggestedField {
  key: keyof OcrResult
  label: string
  value: string
  accepted: boolean
}

const suggestedFields = reactive<SuggestedField[]>([
  { key: 'name', label: 'Nome', value: '', accepted: true },
  { key: 'size', label: 'Tamanho', value: '', accepted: true },
  { key: 'color', label: 'Cor', value: '', accepted: true },
  { key: 'barcode', label: 'Código de barras', value: '', accepted: true },
  { key: 'sale_price', label: 'Preço', value: '', accepted: true },
])

const hasAnyAccepted = computed(() =>
  suggestedFields.some(f => f.accepted && f.value)
)

onMounted(async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } }
    })
    if (videoRef.value) {
      videoRef.value.srcObject = stream
    }
  } catch (e: any) {
    phase.value = 'error'
    errorMsg.value = 'Câmera não disponível. Verifique as permissões.'
  }
})

onUnmounted(() => {
  if (stream) stream.getTracks().forEach(t => t.stop())
})

function capture() {
  const video = videoRef.value
  if (!video || !video.videoWidth) return

  // Create offscreen canvas — never depends on DOM ref
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  const ctx = canvas.getContext('2d')!
  ctx.drawImage(video, 0, 0)

  // Preprocess: grayscale threshold — good contrast for white labels on dark backgrounds
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
  const d = imageData.data
  for (let i = 0; i < d.length; i += 4) {
    const gray = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2]
    const val = gray > 128 ? 255 : 0
    d[i] = d[i + 1] = d[i + 2] = val
  }
  ctx.putImageData(imageData, 0, 0)

  capturedImageUrl.value = canvas.toDataURL('image/jpeg', 0.9)
  if (stream) stream.getTracks().forEach(t => t.stop())
  phase.value = 'processing'

  runOcr(canvas)
}

async function runOcr(canvas: HTMLCanvasElement) {
  try {
    statusMsg.value = 'Carregando OCR (primeira vez pode demorar)...'
    const { createWorker } = await import('tesseract.js')
    const worker = await createWorker('por+eng')

    statusMsg.value = 'Reconhecendo texto...'
    const { data } = await worker.recognize(canvas)
    await worker.terminate()

    rawText.value = data.text
    parseText(data.text)
    phase.value = 'results'
  } catch (e: any) {
    phase.value = 'error'
    errorMsg.value = 'Erro no OCR: ' + (e?.message || 'desconhecido')
  }
}

function parseText(text: string) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean)

  // Barcode: 8–13 digit sequence
  const barcodeMatch = text.match(/\b(\d{8,13})\b/)
  setField('barcode', barcodeMatch ? barcodeMatch[1] : '')

  // Size: clothing sizes (PT)
  const sizeMatch = text.match(/\b(PP|P|M|GG|G|XGG|XG|2XL|XL|XS|[3-5][0-9])\b/i)
  setField('size', sizeMatch ? sizeMatch[1].toUpperCase() : '')

  // Price: currency + number
  const priceMatch = text.match(/(?:U\$|USD|R\$|BRL|G\$|PYG|€|EUR)[\s]*([\d.,]+)/i)
  if (priceMatch) {
    setField('sale_price', priceMatch[1].replace(',', '.'))
  } else {
    const loosePrice = text.match(/\b(\d{1,6}[.,]\d{2})\b/)
    setField('sale_price', loosePrice ? loosePrice[1].replace(',', '.') : '')
  }

  // Color: common PT colors
  const colors = ['preto', 'preta', 'branco', 'branca', 'azul', 'vermelho', 'vermelha',
    'verde', 'amarelo', 'amarela', 'rosa', 'cinza', 'marrom', 'laranja', 'roxo', 'roxa',
    'bege', 'nude', 'creme', 'vinho', 'caramelo']
  const lowerText = text.toLowerCase()
  const foundColor = colors.find(c => lowerText.includes(c))
  setField('color', foundColor ? foundColor.charAt(0).toUpperCase() + foundColor.slice(1) : '')

  // Name: longest line that isn't purely a number/size/price
  const nameCandidate = lines
    .filter(l => l.length > 3 && !/^\d+$/.test(l))
    .filter(l => !barcodeMatch || !l.includes(barcodeMatch[1]))
    .sort((a, b) => b.length - a.length)[0] || ''
  setField('name', nameCandidate)
}

function setField(key: keyof OcrResult, value: string) {
  const f = suggestedFields.find(f => f.key === key)
  if (f) {
    f.value = value
    f.accepted = !!value
  }
}

function retake() {
  phase.value = 'camera'
  rawText.value = ''
  capturedImageUrl.value = ''
  suggestedFields.forEach(f => { f.value = ''; f.accepted = true })
  // Re-open camera
  navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    .then(s => {
      stream = s
      if (videoRef.value) videoRef.value.srcObject = s
    })
    .catch(() => { phase.value = 'error'; errorMsg.value = 'Câmera não disponível.' })
}

function applyFields() {
  const result: OcrResult = {}
  suggestedFields.forEach(f => {
    if (f.accepted && f.value) {
      if (f.key === 'sale_price') {
        (result as any)[f.key] = parseFloat(f.value)
      } else {
        (result as any)[f.key] = f.value
      }
    }
  })
  emit('result', result)
}
</script>

<style scoped>
.ocr-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 600;
  display: flex; align-items: center; justify-content: center; padding: 1rem;
}
.ocr-modal {
  background: white; border-radius: 12px; width: 100%; max-width: 460px;
  max-height: 92vh; display: flex; flex-direction: column; overflow: hidden;
}
.ocr-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; flex-shrink: 0;
}
.ocr-header h3 { margin: 0; font-size: 1rem; font-weight: 600; }
.close-btn { background: none; border: none; cursor: pointer; color: #6b7280; }
.ocr-body { flex: 1; overflow-y: auto; }

/* Camera phase */
.camera-wrap { position: relative; background: #000; }
.camera-feed { width: 100%; display: block; max-height: 300px; object-fit: cover; }
.scan-frame {
  position: absolute; top: 15%; left: 10%; right: 10%; bottom: 15%;
  pointer-events: none;
}
.corner {
  position: absolute; width: 20px; height: 20px;
  border-color: #3b82f6; border-style: solid;
}
.tl { top: 0; left: 0; border-width: 3px 0 0 3px; }
.tr { top: 0; right: 0; border-width: 3px 3px 0 0; }
.bl { bottom: 0; left: 0; border-width: 0 0 3px 3px; }
.br { bottom: 0; right: 0; border-width: 0 3px 3px 0; }
.camera-hint { text-align: center; font-size: 0.75rem; color: #9ca3af; padding: 0.5rem; background: #000; margin: 0; }
.capture-btn {
  display: flex; align-items: center; gap: 0.5rem; justify-content: center;
  width: calc(100% - 2rem); margin: 0.75rem 1rem;
  padding: 0.75rem; background: #3b82f6; color: white;
  border: none; border-radius: 8px; cursor: pointer; font-size: 0.95rem; font-weight: 600;
}

/* Processing phase */
.processing-wrap { padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }
.preview-canvas { width: 100%; border-radius: 8px; display: block; }
.processing-status { display: flex; align-items: center; gap: 0.75rem; justify-content: center; padding: 1rem; }
.spinner { width: 24px; height: 24px; border: 3px solid #e5e7eb; border-top-color: #3b82f6; border-radius: 50%; animation: spin 0.8s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Results phase */
.results-wrap { padding: 1rem; display: flex; flex-direction: column; gap: 1rem; }
.preview-canvas-small { width: 100%; max-height: 140px; object-fit: cover; border-radius: 8px; display: block; }
.raw-text-box label { font-size: 0.75rem; font-weight: 600; color: #6b7280; display: block; margin-bottom: 0.25rem; }
.raw-text { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 6px; padding: 0.5rem; font-size: 0.75rem; white-space: pre-wrap; max-height: 80px; overflow-y: auto; margin: 0; }
.fields-list { display: flex; flex-direction: column; gap: 0.5rem; }
.field-row {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.6rem 0.75rem; border-radius: 8px; background: #f3f4f6; border: 1px solid #e5e7eb;
}
.field-row.detected { background: #f0fdf4; border-color: #bbf7d0; }
.field-info { display: flex; flex-direction: column; gap: 0.1rem; }
.field-label { font-size: 0.7rem; color: #6b7280; font-weight: 500; }
.field-value { font-size: 0.9rem; color: #111827; font-weight: 600; }
.field-empty { font-size: 0.8rem; color: #9ca3af; }
.field-check input { width: 18px; height: 18px; cursor: pointer; }
.results-actions { display: flex; gap: 0.75rem; justify-content: flex-end; padding-top: 0.25rem; }
.btn { padding: 0.5rem 1.25rem; border-radius: 6px; font-size: 0.875rem; cursor: pointer; border: none; font-weight: 500; }
.btn-primary { background: #3b82f6; color: white; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-secondary { background: #f3f4f6; color: #374151; border: 1px solid #d1d5db; }

/* Error */
.error-wrap { padding: 2rem 1.5rem; display: flex; flex-direction: column; align-items: center; gap: 1rem; }
.error-msg-big { color: #dc2626; text-align: center; font-size: 0.9rem; }
</style>
