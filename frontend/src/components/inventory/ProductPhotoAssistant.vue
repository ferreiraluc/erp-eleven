<template>
  <Teleport to="body">
    <div v-show="open" class="photo-overlay erp-dialog-backdrop" @keydown.esc.stop="close" @keydown.tab="trapFocus">
      <section v-erp-dialog ref="dialog" class="photo-dialog erp-dialog erp-dialog--media" role="dialog" aria-modal="true" aria-labelledby="product-photo-title" tabindex="-1">
        <header class="erp-dialog__header"><div><h2 id="product-photo-title">{{ t('title') }}</h2><p>{{ t('intro') }}</p></div>
          <button data-dialog-close type="button" class="erp-button erp-button--ghost erp-button--icon" :aria-label="t('close')" :disabled="busy === 'generating'" @click="close">✕</button>
        </header>
        <div ref="photoBody" class="photo-body erp-dialog__body">
          <div class="photo-actions">
            <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="!!busy" @click="fileInput?.click()">{{ t('choose') }}</button>
            <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="!!busy" @click="cameraInput?.click()">{{ t('camera') }}</button>
            <input ref="fileInput" hidden type="file" accept="image/jpeg,image/png,image/webp" @change="upload" />
            <input ref="cameraInput" hidden type="file" accept="image/jpeg,image/png,image/webp" capture="environment" @change="upload" />
            <small>{{ t('formats') }}</small>
          </div>
          <p v-if="busy" class="photo-status" role="status" aria-live="polite">{{ t(busy) }}</p>
          <p v-if="error" class="photo-error" role="alert">{{ t(error) }}</p>
          <section class="photo-tools" :aria-label="t('generate')">
            <p v-if="!original" class="photo-hint">{{ t('chooseForHanger') }}</p>
            <div class="photo-actions">
              <button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="!original || !!busy || editAttempted || !editingAvailable" @click="confirmPaid = true">{{ t('generate') }}</button>
              <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="!original || !!busy || !!cutout" @click="removeBackground">{{ t('remove') }}</button>
            </div>
            <div v-if="confirmPaid" class="photo-paid">
              <p>{{ t('paid') }}</p><p v-if="model === 'gpt-image-1-mini'">{{ t('miniCost') }}</p>
              <div class="photo-actions"><button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="!!busy || !editingAvailable" @click="generate">{{ t('paidConfirm') }}</button>
              <button type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="!!busy" @click="confirmPaid = false">{{ t('back') }}</button></div>
            </div>
            <p v-if="original && !editingAvailable" class="photo-hint">{{ t('edit_unavailable') }}</p>
          </section>
          <div v-if="original" class="photo-workspace">
            <div class="photo-preview">
              <div class="photo-comparison">
                <figure><img :src="original" :alt="t('original')" /><figcaption>{{ t('original') }}</figcaption></figure>
                <figure><img :src="selectedImage" :alt="t(selected)" /><figcaption>{{ t(selected) }}</figcaption></figure>
              </div>
              <div class="photo-options" role="group" :aria-label="t('choose')">
                <button v-for="option in options" :key="option" type="button" class="erp-control" :aria-pressed="selected === option" :disabled="!!busy" @click="selected = option">{{ t(option) }}</button>
              </div>
              <p v-if="hanger" class="photo-hint">{{ t('generatedWarning') }}</p>
              <p v-if="cost !== null" class="photo-hint">{{ t('cost', { amount: cost.toFixed(5) }) }}</p>
              <a :href="selectedImage" download="eleven-produto.jpg" class="photo-download">{{ t('download') }}</a>
            </div>
            <div class="photo-fields">
              <button type="button" class="erp-button erp-button--primary erp-button--sm" :disabled="!!busy || analyzed" @click="analyze">{{ t('analyze') }}</button>
              <p class="photo-hint">{{ t('reviewHint') }}</p>
              <p v-if="noProduct" class="photo-hint" role="status">{{ t('noProduct') }}</p>
              <label v-for="field in fieldNames" :key="field">{{ t(field) }}
                <input v-model="fields[field]" :name="'photo-' + field" :maxlength="field === 'name' ? 200 : field === 'description' ? 1000 : field === 'color' || field === 'size' ? 50 : 100" :disabled="!!busy" />
                <small v-if="(field === 'brand' && brandEvidence) || (field === 'size' && sizeEvidence)">{{ t('evidence') }}: {{ field === 'brand' ? brandEvidence : sizeEvidence }}</small>
              </label>
              <p class="photo-hint">{{ t('manual') }}</p>
            </div>
          </div>
        </div>
        <footer class="erp-dialog__footer" v-if="original"><label v-if="!draft" class="photo-reviewed"><input v-model="reviewed" type="checkbox" :disabled="!!busy" />{{ t('reviewed') }}</label>
          <p>{{ t(draft ? 'draftNext' : 'next') }}</p><button type="button" class="erp-button erp-button--primary" :disabled="(!draft && (!reviewed || !fields.name.trim())) || !!busy" @click="apply">{{ t(draft ? 'draftUse' : 'use') }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { productPhotoMessages } from './productPhotoMessages'
import { analyzePhoto, catalogForStorage, cutoutPhoto, generateCatalog, photoError, photoStatus, preparePhoto,
  type ProductPhotoFields, type ProductPhotoResult } from '@/services/productPhoto'
const { t } = useI18n({ useScope: 'local', messages: productPhotoMessages })
const props = withDefaults(defineProps<{ draft?: boolean; open?: boolean; startWithHanger?: boolean; initialImage?: string }>(), { draft: false, open: true, startWithHanger: false })
const emit = defineEmits<{ (event: 'close'): void; (event: 'result', value: ProductPhotoResult): void }>()
const fieldNames: (keyof ProductPhotoFields)[] = ['name', 'brand', 'category', 'color', 'size', 'description']
const blank = (): ProductPhotoFields => ({ name: '', brand: '', category: '', color: '', size: '', description: '' })
const fields = reactive(blank())
const fileInput = ref<HTMLInputElement>(), cameraInput = ref<HTMLInputElement>(), dialog = ref<HTMLElement>()
const photoBody = ref<HTMLElement>()
const original = ref(''), cutout = ref(''), hanger = ref('')
const selected = ref<'original' | 'cutout' | 'hanger'>('original')
const selectedImage = computed(() => selected.value === 'cutout' ? cutout.value : selected.value === 'hanger' ? hanger.value : original.value)
const options = computed(() => (['original', ...(cutout.value ? ['cutout'] : []), ...(hanger.value ? ['hanger'] : [])]) as ('original' | 'cutout' | 'hanger')[])
const reviewed = ref(false), analyzed = ref(false), noProduct = ref(false), confirmPaid = ref(false), editAttempted = ref(false)
const busy = ref(''), error = ref(''), editingAvailable = ref(false), model = ref(''), cost = ref<number | null>(null)
const brandEvidence = ref(''), sizeEvidence = ref('')
const controller = new AbortController()
let alive = true
let priorFocus: HTMLElement | null = null
let appliedImage = ''
let seededImage: string | undefined
function seedImage() {
  const image = props.initialImage || ''
  if (props.initialImage === undefined || image === seededImage || busy.value) return
  seededImage = image
  if (image && (image === appliedImage || image === original.value)) return
  original.value = image; cutout.value = ''; hanger.value = ''; selected.value = 'original'
  Object.assign(fields, blank()); analyzed.value = false; reviewed.value = false; noProduct.value = false
  confirmPaid.value = false; editAttempted.value = false; cost.value = null; error.value = ''
  brandEvidence.value = ''; sizeEvidence.value = ''
}
watch([() => props.open, () => props.initialImage], () => { if (props.open) seedImage() }, { immediate: true })
watch(() => props.open, async open => {
  if (open) { priorFocus = document.activeElement as HTMLElement; await nextTick(); if (photoBody.value) photoBody.value.scrollTop = 0; dialog.value?.focus() }
  else priorFocus?.focus()
})
watch([fields, selected], () => { reviewed.value = false }, { deep: true, flush: 'sync' })
watch([() => props.open, () => props.startWithHanger, original, editingAvailable], () => {
  // The shortcut opens the cost confirmation; only its explicit button calls the paid API.
  if (props.open && props.startWithHanger && original.value && editingAvailable.value && !editAttempted.value) confirmPaid.value = true
})
onMounted(async () => {
  priorFocus = document.activeElement as HTMLElement
  dialog.value?.focus()
  try { const status = await photoStatus(); if (alive) { editingAvailable.value = status.editing_available; model.value = status.model } } catch { /* Original and free cutout remain available. */ }
})
onUnmounted(() => { alive = false; controller.abort(); priorFocus?.focus() })
function close() { if (busy.value !== 'generating') emit('close') }
function trapFocus(event: KeyboardEvent) {
  const elements = dialog.value?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled):not([hidden]), a[href], [tabindex="0"]')
  if (!elements?.length) return
  const first = elements[0], last = elements[elements.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.value)) { event.preventDefault(); last.focus() }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
}
async function upload(event: Event) {
  const input = event.target as HTMLInputElement, file = input.files?.[0]
  input.value = ''
  if (!file || busy.value) return
  busy.value = 'preparing'; error.value = ''
  try {
    const image = await preparePhoto(file)
    if (!alive) return
    original.value = image; cutout.value = ''; hanger.value = ''; selected.value = 'original'
    Object.assign(fields, blank()); analyzed.value = false; reviewed.value = false; noProduct.value = false
    confirmPaid.value = false; editAttempted.value = false; cost.value = null; brandEvidence.value = ''; sizeEvidence.value = ''
  } catch { if (alive) error.value = 'invalid_image' } finally { if (alive) busy.value = '' }
}
async function analyze() {
  if (busy.value || analyzed.value || !original.value) return
  busy.value = 'analyzing'; error.value = ''; reviewed.value = false
  try {
    const result = await analyzePhoto(original.value, controller.signal)
    if (!alive) return
    for (const field of fieldNames) if (result[field]) fields[field] = result[field]
    noProduct.value = !result.single_product; brandEvidence.value = result.brand_evidence; sizeEvidence.value = result.size_evidence
    analyzed.value = true
  } catch (e) { if (alive) error.value = photoError(e) } finally { if (alive) busy.value = '' }
}
async function removeBackground() {
  if (busy.value || cutout.value || !original.value) return
  busy.value = 'removing'; error.value = ''; reviewed.value = false
  try { const result = await cutoutPhoto(original.value, controller.signal); if (alive) { cutout.value = result; selected.value = 'cutout' } }
  catch { if (alive) error.value = 'cutout_failed' } finally { if (alive) busy.value = '' }
}
async function generate() {
  if (busy.value || editAttempted.value || !confirmPaid.value || !original.value || !editingAvailable.value) return
  busy.value = 'generating'; error.value = ''; reviewed.value = false; editAttempted.value = true; confirmPaid.value = false
  try {
    const result = await generateCatalog(original.value, controller.signal)
    if (alive) { hanger.value = result.image; selected.value = 'hanger'; cost.value = result.estimated_cost_usd }
  } catch (e) { if (alive) error.value = photoError(e) } finally { if (alive) busy.value = '' }
}
async function apply() {
  if (busy.value || (!props.draft && (!reviewed.value || !fields.name.trim()))) return
  busy.value = 'preparing'; error.value = ''
  try {
    const image_data = await catalogForStorage(selectedImage.value)
    if (alive) { appliedImage = image_data; emit('result', { ...fields, name: fields.name.trim(), image_data, ...(props.draft && selected.value !== 'original' ? { original_image: original.value } : {}) }) }
  } catch { if (alive) error.value = 'invalid_image' } finally { if (alive) busy.value = '' }
}
</script>

<style scoped>
.photo-overlay{position:fixed;inset:0;background:#0f172a99;z-index:12000;display:flex;align-items:center;justify-content:center;padding:20px}
.photo-dialog{width:min(960px,100%);max-height:92dvh;background:#fff;border-radius:18px;display:flex;flex-direction:column;overflow:hidden;color:#1e293b;box-shadow:0 20px 70px #0f172a40}
.photo-tools{margin-top:16px}.photo-dialog>header,.photo-dialog>footer{flex-shrink:0}.photo-body{overscroll-behavior:contain}.photo-tools .erp-button{max-width:100%;white-space:normal;height:auto}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;padding:20px 24px;border-bottom:1px solid #e2e8f0}h2{font-size:21px;margin:0 0 6px}p{margin:0;font-size:13px;line-height:1.5;color:#64748b}.photo-body{overflow:auto;padding:20px 24px;min-height:0}.photo-actions{display:flex;align-items:center;flex-wrap:wrap;gap:8px}small{font-size:11px;color:#64748b}.photo-workspace{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:24px;margin-top:20px}.photo-comparison{display:grid;grid-template-columns:1fr 1fr;gap:10px}figure{margin:0;min-width:0}figure img{width:100%;aspect-ratio:1;object-fit:contain;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc}figcaption{text-align:center;font-size:12px;margin-top:6px;color:#64748b}.photo-options{display:flex;flex-wrap:wrap;gap:6px;margin:16px 0}.photo-options button{font-size:12px;padding:7px 10px;border:1px solid #dbe3ef;border-radius:8px;background:white;color:#475569}.photo-options button[aria-pressed=true]{background:#eff6ff;border-color:#3b82f6;color:#1d4ed8}.photo-fields{display:flex;flex-direction:column;gap:12px}.photo-fields>button{align-self:flex-start}.photo-fields label{display:flex;flex-direction:column;gap:5px;font-size:12px;font-weight:600}.photo-fields input{border:1px solid #cbd5e1;border-radius:8px;padding:9px 10px;min-width:0;font-size:14px;color:#1e293b;background:white}.photo-fields input:focus{outline:2px solid #93c5fd;outline-offset:1px}.photo-hint{font-size:12px;margin:10px 0}.photo-paid,.photo-status{background:#eff6ff;padding:12px;border-radius:10px;margin-top:12px}.photo-paid p{margin-bottom:10px;color:#334155}.photo-error{margin-top:12px;background:#fff1f2;color:#9f1239;padding:10px;border-radius:8px}.photo-download{font-size:12px;color:#2563eb;display:inline-block;margin-top:12px}footer{padding:16px 24px;border-top:1px solid #e2e8f0;background:#f8fafc}footer p{font-size:11px;margin:8px 0 12px}.photo-reviewed{display:flex;align-items:flex-start;gap:8px;font-size:13px}.photo-reviewed input{accent-color:#2563eb;margin-top:3px}
@media(max-width:600px){.photo-overlay{padding:8px}.photo-dialog{max-height:96dvh;border-radius:14px}header,.photo-body,footer{padding:14px}h2{font-size:18px}.photo-workspace{grid-template-columns:1fr;gap:18px}.photo-comparison img{max-height:210px}.photo-actions small{width:100%}.photo-fields input{font-size:16px}footer .erp-button{width:100%}}
</style>
