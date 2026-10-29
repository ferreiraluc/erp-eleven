<template>
  <section class="bulk-photos" :class="{ embedded }" :aria-busy="busy">
    <h3 v-if="!embedded">{{ tr('Fotos por cor') }}</h3>
    <p>{{ tr(operation === 'add' ? 'Adicione uma foto à galeria dos itens escolhidos, com até 5 fotos por produto. Se não houver foto principal, a nova foto será a principal.' : 'Troque a foto principal dos itens escolhidos. As fotos adicionais da galeria são preservadas.') }}</p>
    <div class="photo-controls">
      <div v-if="!embedded" class="photo-target">
        <span>{{ tr('Aplicar foto a') }}</span>
        <ErpDropdown v-model="target" :options="options" :label="tr('Aplicar foto a')" :disabled="locked" />
      </div>
      <div class="photo-target"><span>{{ tr('Operação da foto') }}</span><ErpDropdown v-model="operation" :options="[{ value: 'replace', label: tr('Substituir foto principal') }, { value: 'add', label: tr('Adicionar à galeria') }]" :label="tr('Operação da foto')" :disabled="locked" /></div>
      <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="locked || !targets.length" @click="fileInput?.click()">{{ tr('Enviar foto') }}</button>
      <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="locked || !targets.length" @click="cameraInput?.click()">{{ tr('Câmera') }}</button>
      <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="locked || !targets.length" @click="editPhoto()">{{ tr('Editar foto') }}</button>
    </div>
    <div v-if="sources.length" class="photo-reference">
      <ErpDropdown v-if="sources.length > 1" v-model="sourceId" :options="sources" :label="tr('Foto de referência')" :disabled="locked" />
      <p>{{ tr('Foto de referência: {name}. A imagem editada será aplicada ao grupo escolhido.', { name: sourceName }) }}</p>
    </div>
    <input ref="fileInput" data-bulk-photo-file type="file" accept="image/jpeg,image/png,image/webp" hidden @change="prepare" />
    <input ref="cameraInput" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" hidden @change="prepare" />
    <p class="photo-target-count">{{ tr('{count} itens receberão a foto enviada.', { count: targets.length }) }}</p>
    <p v-if="busy" role="status">{{ tr('Preparando fotos...') }}</p>
    <p v-if="error" role="alert" class="photo-error">{{ tr(error) }}</p>
    <div v-if="groups.length" class="photo-drafts">
      <article v-for="group in groups" :key="group.item_ids[0]" class="photo-draft">
        <img :src="modelValue[group.item_ids[0]].preview" :alt="tr('Nova foto principal')" />
        <div class="photo-summary">
          <strong>{{ group.colors }}</strong>
          <span>{{ tr('{count} itens selecionados', { count: group.item_ids.length }) }}</span>
          <span>{{ tr(group.operation === 'add' ? 'Adicionar à galeria' : 'Substituir foto principal') }}</span>
          <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="locked" :aria-label="tr('Editar foto de {color}', { color: group.colors })" @click="editPhoto(group.item_ids, group.operation === 'add' ? 'add' : 'replace')">{{ tr('Editar foto') }}</button>
          <details v-if="!embedded"><summary>{{ tr('Conferir itens') }}</summary>
            <ul><li v-for="item in group.items" :key="item.id">{{ item.name }} · {{ item.size || tr('Sem tamanho') }}</li></ul>
          </details>
        </div>
        <button type="button" class="erp-button erp-button--ghost erp-button--icon" :disabled="locked" :aria-label="tr('Desfazer foto de {color}', { color: group.colors })" @click="undo(group.item_ids)">×</button>
      </article>
      <p role="status">{{ tr('{count} itens com foto preparada. Clique em Salvar para concluir.', { count: changedCount }) }}</p>
    </div>
    <ProductPhotoAssistant
      v-if="editor"
      photo-only
      :initial-image="editor.image"
      :apply-hint="tr('A foto será preparada para {count} itens. Clique em Salvar no editar massivo para concluir.', { count: editor.ids.length })"
      @close="editor = null"
      @result="applyEditedPhoto"
    />
  </section>
</template>

<script setup lang="ts">
import { colorKey, uniqueColors } from '@/services/inventoryColors'
import { computed, onUnmounted, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import ProductPhotoAssistant from './ProductPhotoAssistant.vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import type { ProductPhotoResult } from '@/services/productPhoto'
import { inScope } from '@/services/inventoryBulkDetails'
import { galleryPreview, prepareGalleryFile } from '@/services/productGallery'
import { MAX_BATCH_PHOTOS, photoAssignments, type PhotoDraft } from '@/services/inventoryBulkPhotos'
import { useInventoryI18n } from './i18n'
const { tr } = useInventoryI18n()
const props = defineProps<{ items: InventoryItem[]; modelValue: PhotoDraft; disabled?: boolean; embedded?: boolean; selectedScope?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: PhotoDraft]; busy: [value: boolean] }>()
const target = ref('all'), busy = ref(false), error = ref('')
const operation = ref<'replace' | 'add'>('replace')
type PhotoOperation = 'replace' | 'add'
const sourceId = ref('')
const editor = ref<{ ids: string[]; operation: PhotoOperation; image: string } | null>(null)
const fileInput = ref<HTMLInputElement>(), cameraInput = ref<HTMLInputElement>()
const working = computed(() => busy.value || !!editor.value)
const locked = computed(() => props.disabled || working.value)
const controller = new AbortController()
let disposed = false
watch(working, value => emit('busy', value), { flush: 'sync' })
onUnmounted(() => { disposed = true; controller.abort(); emit('busy', false) })
const options = computed(() => {
  const colors = new Map<string, { label: string; count: number }>()
  for (const item of props.items) {
    const key = colorKey(item.color || '')
    const group = colors.get(key) || { label: item.color?.trim() || tr('Sem cor'), count: 0 }
    group.count++; colors.set(key, group)
  }
  return [{ value: 'all', label: tr('Todos os selecionados'), description: tr('{count} itens selecionados', { count: props.items.length }) },
    ...[...colors].map(([key, color]) => ({ value: `color:${key}`, label: color.label, description: tr('{count} itens selecionados', { count: color.count }) }))]
})
watch(options, values => { if (!values.some(option => option.value === target.value)) target.value = 'all' })
const targets = computed(() => props.items.filter(item => inScope(item, props.selectedScope ?? target.value)))
const sources = computed(() => targets.value.filter(item => props.modelValue[item.id] || item.has_image || item.image_data).map(item => ({
  value: item.id, label: item.name, description: [item.color, item.size].filter(Boolean).join(' · '),
})))
watch(sources, values => {
  if (!values.some(source => source.value === sourceId.value)) sourceId.value = values[0]?.value || ''
}, { immediate: true })
const sourceName = computed(() => sources.value.find(source => source.value === sourceId.value)?.label || '')
const groups = computed(() => photoAssignments(props.modelValue, props.items.map(item => item.id)).map(group => {
  const ids = new Set(group.item_ids)
  const items = props.items.filter(item => ids.has(item.id))
  return { ...group, items, colors: uniqueColors(items.map(item => item.color || tr('Sem cor'))).join(' · ') }
}))
const changedCount = computed(() => groups.value.reduce((total, group) => total + group.item_ids.length, 0))
function undo(ids: string[]) {
  if (locked.value) return
  const next = { ...props.modelValue }
  ids.forEach(id => delete next[id])
  emit('update:modelValue', next); error.value = ''
}
async function editPhoto(groupIds?: string[], groupOperation?: PhotoOperation) {
  if (locked.value) return
  // Freeze recipients and operation before loading an original or opening the nested editor.
  const ids = groupIds ? [...groupIds] : targets.value.map(item => item.id)
  if (!ids.length) return
  const selectedOperation = groupOperation ?? operation.value
  const id = groupIds?.[0] ?? sourceId.value
  busy.value = true; error.value = ''
  try {
    let image = props.modelValue[id]?.image || ''
    if (!image && id) {
      // Listing images can be thumbnails. Only the explicit detail request provides the editable original.
      const item = await inventoryAPI.getItem(id, controller.signal)
      if (!item.image_data) throw new Error('missing_image')
      image = item.image_data
    }
    if (!disposed) editor.value = { ids, operation: selectedOperation, image }
  } catch {
    if (!disposed) error.value = 'Não foi possível carregar a foto original. Tente novamente ou envie outra foto.'
  } finally { if (!disposed) busy.value = false }
}
async function stagePhoto(image: string, ids: string[], selectedOperation: PhotoOperation) {
  const preview = await galleryPreview(image)
  if (disposed) return false
  const next = { ...props.modelValue }
  const photo = { image, preview, operation: selectedOperation }
  ids.forEach(id => { next[id] = photo })
  if (photoAssignments(next, props.items.map(item => item.id)).length > MAX_BATCH_PHOTOS) {
    error.value = 'Prepare até 20 fotos diferentes por edição. Salve este lote antes de continuar.'
    return false
  }
  emit('update:modelValue', next)
  return true
}
async function applyEditedPhoto(result: ProductPhotoResult) {
  const session = editor.value
  if (!session || busy.value) return
  // Unmount the editor to release its worker/images; the prepared draft still needs the batch Save.
  busy.value = true; editor.value = null; error.value = ''
  try {
    await stagePhoto(result.image_data, session.ids, session.operation)
  } catch {
    if (!disposed) error.value = 'Não foi possível preparar a foto. Use JPEG, PNG ou WebP de até 15 MB.'
  } finally { if (!disposed) busy.value = false }
}
async function prepare(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]; input.value = ''
  if (locked.value || !file || !targets.value.length) return
  // Snapshot membership before asynchronous decoding; later color edits never move a photo to another product.
  const ids = targets.value.map(item => item.id)
  const selectedOperation = operation.value
  busy.value = true; error.value = ''
  try {
    const image = await prepareGalleryFile(file)
    if (disposed) return
    await stagePhoto(image, ids, selectedOperation)
  } catch {
    if (!disposed) error.value = 'Não foi possível preparar a foto. Use JPEG, PNG ou WebP de até 15 MB.'
  } finally { busy.value = false }
}
</script>

<style scoped>
.bulk-photos{min-width:0;display:flex;flex-direction:column;gap:10px;padding:14px;border:1px solid #dbe3ef;border-radius:14px;background:#f8fafc}
.bulk-photos.embedded{padding:0;border:0;background:transparent}
h3,p{margin:0}h3{font-size:14px;color:#334155}p,.photo-target>span{font-size:12px;color:#64748b;line-height:1.5}
.photo-controls{display:flex;align-items:end;gap:8px;flex-wrap:wrap}.photo-target{flex:1 1 180px;min-width:0;display:grid;gap:5px}
.photo-reference{display:grid;gap:6px;min-width:0}.photo-summary>button{justify-self:start}
.photo-drafts{display:grid;gap:10px}.photo-draft{display:flex;align-items:start;gap:10px;background:white;border:1px solid #e2e8f0;border-radius:12px;padding:10px;min-width:0}
.photo-draft>img{width:64px;height:64px;object-fit:contain;border-radius:8px;background:#f8fafc;flex-shrink:0}.photo-summary{min-width:0;flex:1;display:grid;gap:4px;font-size:12px;overflow-wrap:anywhere}.photo-summary>span{color:#64748b}
summary{cursor:pointer;color:#2563eb;padding:5px 0}ul{padding-left:16px;margin:4px 0;max-height:150px;overflow:auto}.photo-error{color:#b91c1c}
@media(pointer:coarse){.photo-controls button,.photo-draft>button{min-height:44px;min-width:44px}}
@media(max-width:400px){.photo-target{flex-basis:100%}.bulk-photos{padding:10px}.photo-draft>img{width:56px;height:56px}}
</style>
