<template>
  <div class="ocr-overlay" @click.self="emit('close')">
    <div class="ocr-modal" role="dialog" aria-modal="true" :aria-label="t('title')">
      <div class="ocr-header"><h3>{{ t('title') }}</h3><button class="close-btn" :aria-label="t('close')" @click="emit('close')">×</button></div>
      <div class="brand-bar"><input v-model="selectedBrand" class="brand-input" :placeholder="t('brandHint')" :aria-label="t('brandHint')" list="brand-datalist" maxlength="100" :disabled="phase === 'processing'" /><datalist id="brand-datalist"><option v-for="brand in knownBrands" :key="brand.brand" :value="brand.brand" /></datalist><span v-if="templateCount" class="brand-trained-badge">{{ t('examples', { count: templateCount }) }}</span></div>
      <div class="ocr-body">
        <p class="ocr-notice">{{ t('transient') }}</p>
        <div v-if="phase === 'camera'" class="camera-wrap">
          <video ref="videoRef" autoplay playsinline muted class="camera-feed" />
          <p class="camera-hint">{{ t('frame') }}</p><button class="capture-btn" @click="capture">{{ t('capture') }}</button>
        </div>
        <div v-if="phase === 'camera' || phase === 'error'" class="ocr-file-picker">
          <label class="btn btn-ghost">{{ t('upload') }}<input type="file" accept="image/jpeg,image/png,image/webp" @change="chooseFile" /></label><small>{{ t('formats') }}</small>
        </div>
        <div v-if="phase === 'processing'" class="processing-wrap"><img :src="capturedImageUrl" class="preview-img" alt="" /><p class="processing-title" role="status">{{ t('processing') }}</p></div>
        <div v-if="phase === 'results'" class="results-wrap">
          <div class="results-top"><img :src="capturedImageUrl" class="preview-thumb" alt="" /><p class="results-hint">{{ t('reviewHint') }}</p></div>
          <ul v-if="warningKeys.length" class="ocr-warnings"><li v-for="key in warningKeys" :key="key">{{ t(key) }}</li></ul>
          <div v-if="reading && reading.matches_total" class="ocr-matches"><p>{{ t('matches', { count: reading.matches_total }) }}</p><ul><li v-for="match in reading.matches" :key="match.id">{{ match.name }} · {{ match.sku_internal }}</li></ul></div>
          <details v-if="reading?.texto_bruto" class="raw-text-details"><summary>{{ t('raw') }}</summary><pre class="raw-text">{{ reading.texto_bruto }}</pre></details>
          <div class="fields-grid">
            <div v-for="field in fields" :key="field.key" class="field-card" :class="{ detected: !!values[field.key] }">
              <label class="field-label" :for="`ocr-${field.key}`">{{ t(field.key) }}</label><input :id="`ocr-${field.key}`" v-model="values[field.key]" class="field-input" :inputmode="field.key === 'sale_price' ? 'decimal' : 'text'" :maxlength="field.key === 'name' ? 200 : field.key === 'brand' ? 100 : 50" />
              <span class="field-status">{{ !values[field.key] ? t('empty') : values[field.key] === originals[field.key] ? t('detected') : t('edited') }}</span>
              <small v-if="reading?.evidencias[field.source]" class="ocr-evidence">{{ reading.evidencias[field.source] }}</small>
            </div>
            <div class="field-card"><label class="field-label" for="ocr-currency">{{ t('currency') }}</label><select id="ocr-currency" v-model="currency" class="field-input"><option value="">{{ t('unknown') }}</option><option v-for="code in currencies" :key="code" :value="code">{{ code }}</option></select></div>
          </div>
          <label class="ocr-review"><input v-model="reviewed" type="checkbox" />{{ t('reviewed') }}</label><p class="ocr-next">{{ t('next') }}</p>
          <p v-if="formError" class="error-msg-big" role="alert">{{ t(formError) }}</p>
          <p v-if="exampleSaved" class="ocr-success" role="status">{{ t('saved') }}</p>
          <div class="results-actions"><button class="btn btn-ghost" @click="retake">{{ t('retake') }}</button><button class="btn btn-learn" :disabled="!reviewed || !hasAnyField" @click="openSaveTemplate">{{ t('saveExample') }}</button><button class="btn btn-primary" :disabled="!reviewed || !hasAnyField" @click="applyFields">{{ t('use') }}</button></div>
        </div>
        <div v-if="phase === 'saving-template'" class="save-template-wrap">
          <h4>{{ t('exampleTitle') }}</h4><p class="save-hint">{{ t('exampleHint') }}</p><img :src="capturedImageUrl" class="preview-thumb" alt="" />
          <div class="stf-group"><label for="ocr-example-brand">{{ t('brand') }} *</label><input id="ocr-example-brand" v-model="saveForm.brand" maxlength="100" class="stf-input" /></div>
          <div class="stf-group"><label for="ocr-example-notes">{{ t('notes') }}</label><textarea id="ocr-example-notes" v-model="saveForm.notes" maxlength="1500" class="stf-input stf-textarea" /></div>
          <p v-if="formError" class="error-msg-big" role="alert">{{ t(formError) }}</p><div class="results-actions"><button class="btn btn-ghost" :disabled="savingTemplate" @click="phase = 'results'">{{ t('back') }}</button><button class="btn btn-primary" :disabled="savingTemplate || !saveForm.brand.trim()" @click="saveTemplate">{{ t('save') }}</button></div>
        </div>
        <div v-if="phase === 'error'" class="error-wrap"><p class="error-msg-big" role="alert">{{ t(errorKey) }}</p><button class="btn btn-ghost" @click="retake">{{ t('camera') }}</button></div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import { isAxiosError } from 'axios'
import { ocrAPI } from '@/services/api'
import type { OcrAppliedFields, OcrParsedLabel, OcrCurrency } from '@/services/ocr'
import { ocrMessages } from './ocrMessages'
const { t } = useI18n({ useScope: 'local', messages: ocrMessages })
const emit = defineEmits<{ result: [data: OcrAppliedFields]; close: [] }>()
const videoRef = ref<HTMLVideoElement>()
const phase = ref<'camera' | 'processing' | 'results' | 'saving-template' | 'error'>('camera')
const capturedImageUrl = ref(''), selectedBrand = ref(''), errorKey = ref('cameraFailed'), formError = ref('')
const reading = ref<OcrParsedLabel | null>(null), reviewed = ref(false), savingTemplate = ref(false), exampleSaved = ref(false)
const knownBrands = ref<Array<{ brand: string; count: number }>>([])
const currencies: OcrCurrency[] = ['PYG', 'BRL', 'USD', 'EUR']
const currency = ref<OcrCurrency | ''>('')
const fields = [
  { key: 'name', source: 'nome' }, { key: 'brand', source: 'marca' }, { key: 'size', source: 'tamanho' },
  { key: 'color', source: 'cor' }, { key: 'barcode', source: 'codigo_barras' }, { key: 'sale_price', source: 'preco' },
] as const
const values = reactive({ name: '', brand: '', size: '', color: '', barcode: '', sale_price: '' })
const originals = reactive({ ...values })
const saveForm = reactive({ brand: '', notes: '' })
const hasAnyField = computed(() => Object.values(values).some(value => value.trim()))
const templateCount = computed(() => knownBrands.value.find(brand => brand.brand.toLowerCase() === selectedBrand.value.toLowerCase())?.count || 0)
const warningKeys = computed(() => [...new Set((reading.value?.avisos || []).filter(key => key !== 'barcode_exists').map(key => key.startsWith('unverified_') ? 'unverified' : key))])
let stream: MediaStream | null = null, controller: AbortController | null = null
let disposed = false, cameraRequest = 0
watch([values, currency], () => { reviewed.value = false; formError.value = '' }, { deep: true })
function stopCamera() { cameraRequest++; stream?.getTracks().forEach(track => track.stop()); stream = null }
async function startCamera() {
  const request = ++cameraRequest
  try {
    const camera = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 1600 }, height: { ideal: 1200 } } })
    if (disposed || request !== cameraRequest) { camera.getTracks().forEach(track => track.stop()); return }
    stream = camera; await nextTick(); if (videoRef.value) videoRef.value.srcObject = camera
  } catch { if (!disposed && request === cameraRequest) { errorKey.value = 'cameraFailed'; phase.value = 'error' } }
}
function capture() {
  const video = videoRef.value
  if (!video?.videoWidth) return
  const scale = Math.min(1600 / Math.max(video.videoWidth, video.videoHeight), 1)
  const canvas = document.createElement('canvas'); canvas.width = Math.round(video.videoWidth * scale); canvas.height = Math.round(video.videoHeight * scale)
  canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
  void runOcr(canvas.toDataURL('image/jpeg', .9))
}
async function chooseFile(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]; input.value = ''
  if (!file) return
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) { stopCamera(); errorKey.value = 'invalidFile'; phase.value = 'error'; return }
  const reader = new FileReader()
  reader.onload = () => { if (!disposed && typeof reader.result === 'string') void runOcr(reader.result) }
  reader.onerror = () => { if (!disposed) { errorKey.value = 'invalidFile'; phase.value = 'error' } }
  reader.readAsDataURL(file)
}
async function runOcr(image: string) {
  stopCamera(); controller?.abort(); const request = new AbortController(); controller = request
  capturedImageUrl.value = image; phase.value = 'processing'; reading.value = null; reviewed.value = false; exampleSaved.value = false
  try {
    const result = await ocrAPI.parseLabel(image, selectedBrand.value || undefined, request.signal)
    if (disposed || request !== controller) return
    reading.value = result
    for (const field of fields) values[field.key] = result[field.source] == null ? '' : String(result[field.source])
    Object.assign(originals, values); currency.value = result.moeda || ''; phase.value = 'results'
  } catch (error) {
    if (disposed || request !== controller) return
    errorKey.value = isAxiosError(error) && error.response?.status === 503 ? 'unavailable' : 'readingFailed'; phase.value = 'error'
  }
}
function retake() { stopCamera(); controller?.abort(); controller = null; capturedImageUrl.value = ''; reading.value = null; reviewed.value = false; phase.value = 'camera'; void startCamera() }
function reviewedResult(): OcrAppliedFields | null {
  if (!reviewed.value) return null
  const result: OcrAppliedFields = {}
  for (const key of ['name', 'brand', 'size', 'color', 'barcode'] as const) if (values[key].trim()) result[key] = values[key].trim()
  if (values.sale_price.trim()) {
    const number = values.sale_price.trim().replace(',', '.')
    if (!/^\d+(?:\.\d{1,2})?$/.test(number) || !currency.value || Number(number) > 1_000_000_000) { formError.value = 'invalidPrice'; return null }
    result.sale_price = Number(number); result.currency = currency.value
  }
  return result
}
function applyFields() { const result = reviewedResult(); if (result) emit('result', result) }
function openSaveTemplate() { if (!reviewedResult()) return; saveForm.brand = values.brand || selectedBrand.value; saveForm.notes = ''; formError.value = ''; phase.value = 'saving-template' }
async function saveTemplate() {
  const result = reviewedResult(); if (!result || !saveForm.brand.trim() || savingTemplate.value) return
  savingTemplate.value = true; formError.value = ''
  try {
    await ocrAPI.saveTemplate({ brand: saveForm.brand.trim(), notes: saveForm.notes || undefined, sample_image: capturedImageUrl.value, parsed_name: result.name, parsed_size: result.size, parsed_color: result.color, parsed_barcode: result.barcode, parsed_price: result.sale_price == null ? undefined : String(result.sale_price), parsed_currency: result.currency })
    if (disposed) return
    exampleSaved.value = true; phase.value = 'results'; knownBrands.value = await ocrAPI.getBrands().catch(() => knownBrands.value)
  } catch { formError.value = 'saveFailed' }
  finally { savingTemplate.value = false }
}
onMounted(() => { void ocrAPI.getBrands().then(brands => { if (!disposed) knownBrands.value = brands }).catch(() => undefined); void startCamera() })
onUnmounted(() => { disposed = true; stopCamera(); controller?.abort(); capturedImageUrl.value = ''; reading.value = null })
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
.ocr-notice, .ocr-next { font-size: .76rem; color: #64748b; padding: .7rem 1rem; margin: 0; line-height: 1.5; }
.ocr-file-picker { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 1rem; color: #64748b; }
.ocr-file-picker input { max-width: 200px; font-size: .7rem; margin-left: .5rem; }
.ocr-review { display: flex; align-items: flex-start; gap: .5rem; padding: .7rem 0; font-size: .8rem; color: #334155; }
.ocr-review input { margin-top: .15rem; }
.ocr-warnings, .ocr-matches { padding: .8rem 1rem .8rem 1.7rem; background: #fffbeb; color: #92400e; border-radius: 8px; font-size: .78rem; line-height: 1.6; }
.ocr-evidence { display: block; color: #64748b; font-size: .68rem; margin-top: .3rem; overflow-wrap: anywhere; }
.ocr-success { color: #15803d; font-size: .8rem; }
button:disabled { opacity: .5; cursor: not-allowed; }
</style>
