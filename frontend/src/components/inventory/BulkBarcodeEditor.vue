<template>
  <component :is="embedded ? 'div' : 'details'" class="bulk-barcodes" :class="{ embedded }">
    <summary v-if="!embedded">{{ tr('Códigos de barras em lote') }}</summary>
    <p>{{ tr('Leia ou digite por item, ou prepare códigos usando a base e o tamanho. Confira antes de salvar.') }}</p>
    <div class="barcode-controls">
      <label v-if="!embedded">{{ tr('Aplicar códigos a') }}<ErpDropdown v-model="scope" :options="scopeChoices" :label="tr('Aplicar códigos a')" /></label>
      <label>{{ tr('Formato') }}<ErpDropdown v-model="mode" :options="[{ value: 'size', label: tr('Código base + tamanho') }, { value: 'same', label: tr('Mesmo código base') }]" :label="tr('Formato do código')" /></label>
    </div>
    <label>{{ tr('Código base') }}<input v-model="base" :aria-label="tr('Código base')" type="text" maxlength="200" autocomplete="off" @keydown.enter.prevent="prepare" /></label>
    <label class="check"><input v-model="onlyEmpty" type="checkbox" />{{ tr('Preencher somente códigos vazios') }}</label>
    <p>{{ tr('Base + tamanho é um código interno; não é um novo EAN do fabricante.') }}</p>
    <button class="erp-button erp-button--secondary erp-button--sm" type="button" :disabled="disabled || !base.trim()" @click="prepare">{{ tr('Conferir códigos') }}</button>
    <div v-if="preview.length" class="barcode-preview">
      <p>{{ tr('{count} códigos preparados para conferir.', { count: preview.length }) }}</p>
      <ul v-if="!embedded"><li v-for="row in preview" :key="row.item.id"><span>{{ row.item.name }} · {{ row.item.size }}</span><code>{{ row.before || '—' }} → {{ row.after }}</code></li></ul>
      <code v-else>{{ preview[0].before || '—' }} → {{ preview[0].after }}</code>
      <button class="erp-button erp-button--secondary erp-button--sm" type="button" :disabled="disabled" @click="apply">{{ tr('Aplicar códigos à prévia') }}</button>
    </div>
    <p v-if="error" class="barcode-error" role="alert">{{ tr(error) }}</p>
    <div class="barcode-reader">
      <label>{{ tr('Item para leitura') }}<ErpDropdown v-model="readingId" :options="readingOptions" :label="tr('Item para leitura')" /></label>
      <div class="barcode-input-row">
        <input :value="modelValue[readingId] || ''" :aria-label="tr('Código do item em leitura')" type="text" maxlength="200" autocomplete="off" @input="write(($event.target as HTMLInputElement).value)" @keydown.enter.prevent="next" />
        <button class="erp-button erp-button--secondary erp-button--icon" type="button" :disabled="disabled || !readingId" :aria-label="tr('Ler código com câmera')" @click="scanner = true"><Camera :size="18" /></button>
        <button class="erp-button erp-button--secondary erp-button--sm" type="button" :disabled="disabled || !readingId" @click="next">{{ tr('Próximo') }}</button>
      </div>
      <p>{{ tr('Enter avança para o próximo item. Zeros à esquerda são preservados.') }}</p>
    </div>
    <p v-if="repeated.length" role="status" class="barcode-warning">{{ tr('{count} códigos aparecem em mais de um selecionado. Eles continuam separados por produto.', { count: repeated.length }) }}</p>
    <p v-if="readMessage" role="status">{{ tr(readMessage) }}</p>
    <Teleport to="body"><BarcodeScanner v-if="scanner" @barcode-detected="scanned" @close="scanner = false" /></Teleport>
  </component>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Camera } from 'lucide-vue-next'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import BarcodeScanner from './BarcodeScanner.vue'
import type { InventoryItem } from '@/services/api'
import { inScope, scopeOptions } from '@/services/inventoryBulkDetails'
import { barcodePreview, repeatedBarcodes } from '@/services/inventoryBulkBarcodes'
import { useInventoryI18n } from './i18n'
const { tr } = useInventoryI18n()
const props = defineProps<{ items: InventoryItem[]; modelValue: Record<string, string>; disabled?: boolean; embedded?: boolean; selectedScope?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: Record<string, string>] }>()
const base = ref(''), mode = ref('size'), scope = ref('all'), onlyEmpty = ref(true), error = ref(''), readMessage = ref('')
const readingId = ref(props.items[0]?.id || ''), scanner = ref(false)
const preview = ref<ReturnType<typeof barcodePreview>>([])
const scopeChoices = computed(() => [{ value: 'all', label: tr('Todos os selecionados') }, ...scopeOptions(props.items).map(o => ({ ...o, label: `${tr(o.kind)}: ${o.label}` }))])
const targets = computed(() => props.items.filter(item => inScope(item, props.selectedScope ?? scope.value)))
const readingOptions = computed(() => props.items.map(item => ({ value: item.id, label: item.name, description: `${item.inventory_code || item.sku_internal} · ${item.size || ''} · ${item.color || ''}` })))
const repeated = computed(() => repeatedBarcodes(props.items, props.modelValue))
watch([base, mode, scope, onlyEmpty, () => props.selectedScope, () => props.items], () => { preview.value = []; error.value = '' }, { deep: true })
function prepare() {
  if (props.disabled) return
  try { preview.value = barcodePreview(targets.value, props.modelValue, base.value, mode.value === 'size', onlyEmpty.value); error.value = preview.value.length ? '' : 'Nenhum código precisa ser alterado nesta seleção.' }
  catch (e) { preview.value = []; error.value = (e as Error).message }
}
function apply() {
  if (props.disabled) return
  // A manual edit after review must not be overwritten by an old prepared list.
  if (preview.value.some(row => (props.modelValue[row.item.id] || '') !== row.before)) { preview.value = []; error.value = 'Os códigos mudaram. Confira a prévia novamente.'; return }
  const next = { ...props.modelValue }
  for (const row of preview.value) next[row.item.id] = row.after
  emit('update:modelValue', next); preview.value = []
}
function write(value: string) { if (!props.disabled && readingId.value) emit('update:modelValue', { ...props.modelValue, [readingId.value]: value }) }
function next() {
  const index = props.items.findIndex(item => item.id === readingId.value)
  if (index >= 0 && index < props.items.length - 1) { readingId.value = props.items[index + 1].id; readMessage.value = '' }
  else readMessage.value = 'Último item da seleção. Confira os códigos e salve.'
}
function scanned(value: string) { write(value.trim()); scanner.value = false; readMessage.value = 'Código lido. Confira e avance para o próximo item.' }
</script>
<style scoped>
.bulk-barcodes.embedded{padding:0;border:0}
.bulk-barcodes{padding:12px;border:1px solid #dbe3ef;border-radius:12px}.bulk-barcodes summary{cursor:pointer;font-size:14px;font-weight:600}.bulk-barcodes p{font-size:12px;color:#64748b;margin:10px 0}.bulk-barcodes label{display:flex;flex-direction:column;gap:4px;font-size:12px;min-width:0;margin:8px 0}.barcode-controls{display:grid;grid-template-columns:1fr 1fr;gap:10px}.bulk-barcodes input[type=text]{width:100%;min-width:0;box-sizing:border-box;padding:8px 10px;border:1px solid #cbd5e1;border-radius:8px;font:inherit;font-size:14px}.bulk-barcodes .check{flex-direction:row;align-items:center}.barcode-input-row{display:flex;gap:6px}.barcode-input-row input{flex:1;width:0}.barcode-reader{border-top:1px solid #e2e8f0;padding-top:8px;margin-top:12px}.barcode-preview{margin-top:10px;background:#f8fafc;padding:8px;border-radius:8px}.barcode-preview ul{list-style:none;padding:0;max-height:180px;overflow:auto}.barcode-preview li{display:flex;flex-direction:column;gap:3px;padding:4px 0;font-size:12px}.barcode-preview code{overflow-wrap:anywhere}.barcode-error{color:#b91c1c!important}.barcode-warning{background:#fffbeb;color:#92400e!important;padding:8px;border-radius:8px}
</style>
