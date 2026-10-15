<template>
  <div class="stock-stepper">
    <button type="button" class="stock-step" :aria-label="uiText('Diminuir quantidade')" :disabled="disabled || (Number.isFinite(Number(modelValue)) && Number(modelValue) <= min)" @click="step(-1)">−</button>
    <input v-bind="$attrs" :value="Number.isNaN(modelValue) ? '' : modelValue" type="number" inputmode="numeric" step="1" :min="Number.isFinite(min) ? min : undefined" :max="max" :disabled="disabled" @input="input" />
    <button type="button" class="stock-step" :aria-label="uiText('Aumentar quantidade')" :disabled="disabled || Number(modelValue) >= max" @click="step(1)">+</button>
  </div>
</template>
<script setup lang="ts">
import { uiText } from '@/i18n/uiText'
defineOptions({ inheritAttrs: false })
const props = withDefaults(defineProps<{ modelValue?: number | string; min?: number; max?: number; disabled?: boolean }>(), { min: 0, max: 2147483647, disabled: false })
const emit = defineEmits<{ 'update:modelValue': [value: number] }>()
function input(event: Event) { emit('update:modelValue', (event.target as HTMLInputElement).valueAsNumber) }
function step(delta: number) {
  if (props.disabled) return
  // Do not focus the textbox: a button tap must not open the mobile keyboard.
  const current = Number(props.modelValue)
  emit('update:modelValue', Math.max(props.min, Math.min(props.max, (Number.isFinite(current) ? Math.trunc(current) : 0) + delta)))
}
</script>
<style scoped>
.stock-stepper{display:flex;align-items:stretch;min-width:0;width:100%;gap:3px}.stock-stepper input{flex:1 1 0;min-width:0;width:100%;box-sizing:border-box;min-height:40px;padding:8px 10px;border:1px solid #d1d5db;border-radius:8px;background:white;font-size:14px}.stock-stepper input.error,.stock-stepper input[aria-invalid=true]{border-color:#dc2626}.stock-stepper input:disabled{opacity:.5}.stock-step{display:none}
@media(max-width:767px),(hover:none) and (pointer:coarse){.stock-stepper .stock-step{display:flex;align-items:center;justify-content:center;flex:0 0 32px;min-width:32px;min-height:40px;padding:0;border:1px solid #cbd5e1;border-radius:9px;background:#f8fafc;color:#334155;font-size:20px;line-height:1;touch-action:manipulation}.stock-step:disabled{opacity:.4}.stock-stepper input{font-size:16px;text-align:center;padding-inline:4px!important}}
</style>
