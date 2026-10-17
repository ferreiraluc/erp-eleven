<template>
  <section class="product-gallery" :aria-label="tr('Fotos do produto')" :aria-busy="busy || loading">
    <div class="gallery-heading"><strong>{{ tr('Fotos do produto') }}</strong><span>{{ photos.length }}/5</span></div>
    <p v-if="loading" role="status">{{ tr('Carregando fotos...') }}</p>
    <p v-if="loadError" role="alert">{{ tr('Não foi possível carregar as fotos. Tente novamente antes de salvar.') }}
      <button type="button" class="erp-button erp-button--secondary erp-button--sm" @click="emit('retry')">{{ tr('Tentar novamente') }}</button>
    </p>
    <img v-if="expanded && photos[selected]" class="gallery-main" :src="photos[selected]" :alt="tr('Foto {number} do produto', { number: selected + 1 })" />
    <div class="gallery-strip" role="group" :aria-label="tr('Escolher foto')">
      <button v-for="(photo, index) in photos" :key="index" type="button" class="gallery-thumb erp-control"
        :class="{ selected: selected === index }" :aria-pressed="selected === index"
        :aria-label="tr('Foto {number} do produto', { number: index + 1 })" @click="selected = index">
        <img v-if="previews.get(photo)" :src="previews.get(photo)" alt="" />
        <span v-else aria-hidden="true">{{ index + 1 }}</span>
        <small v-if="index === 0">{{ tr('Principal') }}</small>
      </button>
    </div>
    <template v-if="editable">
      <div v-if="photos.length" class="gallery-actions">
        <button v-if="selected > 0" type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="locked" @click="makeCover">{{ tr('Usar como principal') }}</button>
        <button type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="locked" @click="removeSelected">{{ tr('Remover foto') }} {{ selected + 1 }}</button>
      </div>
      <div class="gallery-actions">
        <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="locked || photos.length >= 5" @click="fileInput?.click()">＋ {{ tr('Adicionar fotos') }}</button>
        <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="locked || photos.length >= 5" @click="cameraInput?.click()">{{ tr('Câmera') }}</button>
        <span v-if="busy" role="status">{{ tr('Preparando fotos...') }}</span>
      </div>
      <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp" multiple hidden @change="addFiles" />
      <input ref="cameraInput" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden @change="addFiles" />
      <small>{{ tr('Até 5 fotos. A principal aparece nos cards; as outras ficam nesta galeria.') }}</small>
    </template>
    <p v-if="error" class="gallery-error" role="alert">{{ tr(error) }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { catalogForStorage } from '@/services/productPhoto'
import { galleryPreview, MAX_PRODUCT_PHOTOS, prepareGalleryFile } from '@/services/productGallery'
import { useInventoryI18n } from './i18n'
const props = withDefaults(defineProps<{ cover: string; additional: string[]; editable?: boolean; expanded?: boolean; loading?: boolean; loadError?: boolean }>(), { editable: false })
const emit = defineEmits<{ (e: 'update:cover', value: string): void; (e: 'update:additional', value: string[]): void; (e: 'busy', value: boolean): void; (e: 'retry'): void }>()
const { tr } = useInventoryI18n()
const photos = computed(() => [props.cover, ...props.additional].filter(Boolean))
const selected = ref(0), busy = ref(false), error = ref('')
const locked = computed(() => busy.value || props.loading || props.loadError)
const fileInput = ref<HTMLInputElement>(), cameraInput = ref<HTMLInputElement>()
const previews = ref(new Map<string, string>())
let disposed = false, generation = 0
onUnmounted(() => { disposed = true; generation++; emit('busy', false) })
watch(busy, value => emit('busy', value), { flush: 'sync' })
watch(photos, async values => {
  const request = ++generation
  selected.value = Math.min(selected.value, Math.max(0, values.length - 1))
  previews.value = new Map([...previews.value].filter(([source]) => values.includes(source)))
  for (const source of values) {
    if (previews.value.has(source)) continue
    try {
      const preview = await galleryPreview(source)
      if (disposed || request !== generation) return
      previews.value.set(source, preview)
    } catch { /* Legacy invalid photos keep a numbered placeholder. */ }
    if (disposed || request !== generation) return
  }
}, { immediate: true })
function apply(values: string[]) {
  emit('update:cover', values[0] || '')
  emit('update:additional', values.slice(1))
}
function removeSelected() {
  if (locked.value) return
  apply(photos.value.filter((_, index) => index !== selected.value))
}
async function makeCover() {
  if (locked.value || selected.value === 0) return
  busy.value = true; error.value = ''
  try {
    const values = [...photos.value]
    // Old primary photos may exceed the new gallery limit. Bound only the copy
    // becoming secondary, without rewriting other products or original files.
    values[0] = await catalogForStorage(values[0])
    const [cover] = values.splice(selected.value, 1)
    if (!disposed) { apply([cover, ...values]); selected.value = 0 }
  } catch { error.value = 'Não foi possível preparar a foto. Use JPEG, PNG ou WebP de até 15 MB.' }
  finally { busy.value = false }
}
async function addFiles(event: Event) {
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files || []); input.value = ''
  if (locked.value || !files.length) return
  const available = MAX_PRODUCT_PHOTOS - photos.value.length
  if (files.length > available) { error.value = 'Selecione apenas as fotos que cabem no limite de 5.'; return }
  busy.value = true; error.value = ''
  const values = [...photos.value]
  try {
    for (const file of files) {
      const photo = await prepareGalleryFile(file)
      if (disposed) return
      if (!values.includes(photo)) values.push(photo)
    }
    if (!disposed) apply(values)
  } catch { error.value = 'Não foi possível preparar a foto. Use JPEG, PNG ou WebP de até 15 MB.' }
  finally { busy.value = false }
}
</script>

<style scoped>
.product-gallery { min-width:0; border:1px solid #e2e8f0; border-radius:14px; padding:12px; margin:12px 0; }
.gallery-heading,.gallery-actions { display:flex; align-items:center; flex-wrap:wrap; gap:8px; }
.gallery-heading { justify-content:space-between; font-size:13px; margin-bottom:10px; }
.gallery-heading span,.product-gallery small { color:#64748b; font-size:11px; }
.gallery-strip { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:6px; }
.gallery-thumb { position:relative; min-width:0; padding:0; aspect-ratio:1; overflow:hidden; border:1px solid #e2e8f0; border-radius:10px; background:#f8fafc; color:#64748b; }
.gallery-thumb.selected { border:2px solid #2563eb; background:#eff6ff; }
.gallery-thumb img { width:100%; height:100%; object-fit:contain; }
.gallery-thumb small { position:absolute; bottom:0; left:0; right:0; background:#eff6ffeb; color:#1d4ed8; font-size:9px; }
.gallery-main { display:block; width:100%; height:min(48dvh,400px); object-fit:contain; margin-bottom:12px; }
.gallery-actions { margin:10px 0; }
.gallery-error { color:#b91c1c; font-size:12px; }
</style>
