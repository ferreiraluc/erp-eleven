<template>
  <div class="inventory-grid-zoom" role="group" :aria-label="tr('Zoom dos produtos')">
    <label :for="inputId">{{ tr('Zoom') }}</label>
    <button type="button" class="zoom-step erp-control" :disabled="modelValue === 0"
      :aria-label="tr('Diminuir produtos')" @click="emit('update:modelValue', modelValue - 1)"><Minus aria-hidden="true" /></button>
    <input :id="inputId" type="range" min="0" max="2" step="1" :value="modelValue"
      :aria-label="tr('Zoom dos produtos')" :aria-valuetext="tr('{count} colunas', { count: 4 - modelValue })"
      @input="emit('update:modelValue', Number(($event.target as HTMLInputElement).value))" />
    <button type="button" class="zoom-step erp-control" :disabled="modelValue === 2"
      :aria-label="tr('Aumentar produtos')" @click="emit('update:modelValue', modelValue + 1)"><Plus aria-hidden="true" /></button>
    <output :for="inputId">{{ tr('{count} colunas', { count: 4 - modelValue }) }}</output>
  </div>
</template>
<script setup lang="ts">
import { Minus, Plus } from 'lucide-vue-next'
import { useId } from 'vue'
import { useInventoryI18n } from './i18n'
defineProps<{ modelValue: number }>()
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()
const { tr } = useInventoryI18n()
const inputId = `inventory-grid-zoom-${useId()}`
</script>
<style scoped>
.inventory-grid-zoom { display:none; }
@media(max-width:600px) {
  .inventory-grid-zoom { display:flex; align-items:center; gap:6px; padding:4px; color:#64748b; background:#fff; }
  label { font-size:.72rem; font-weight:600; }
  output { min-width:50px; text-align:right; font-size:.7rem; font-variant-numeric:tabular-nums; }
  input { flex:1; min-width:0; height:44px; padding:0; accent-color:#2563eb; cursor:pointer; touch-action:pan-y; }
  .zoom-step { display:flex; align-items:center; justify-content:center; flex:none; width:44px; height:44px; padding:0; border:1px solid #e2e8f0; border-radius:50%; background:#f8fafc; color:#475569; cursor:pointer; }
  .zoom-step svg { width:14px; height:14px; }
  input:focus-visible { outline:2px solid #2563eb; outline-offset:2px; border-radius:6px; }
}
</style>
