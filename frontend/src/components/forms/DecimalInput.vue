<template>
  <input ref="input" type="text" inputmode="decimal" autocomplete="off" :value="draft"
    @input="onInput" @focus="onFocus" @blur="focused = false" />
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { uiLocale } from '@/i18n/uiText'
const props = defineProps<{ modelValue: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: number | null] }>()
const input = ref<HTMLInputElement>(), focused = ref(false), draft = ref('')
let emitted: number | null = null
function format(value: number | null) {
  return value === null || !Number.isFinite(value) ? '' : value.toLocaleString(uiLocale(), { useGrouping: false, maximumFractionDigits: 6 })
}
watch(() => props.modelValue, value => {
  // Preserve the caret and partially typed decimals ("5,"), but accept external changes.
  if (!focused.value || value !== emitted) draft.value = format(value)
}, { immediate: true })
function onInput(event: Event) {
  draft.value = (event.target as HTMLInputElement).value
  let normalized = draft.value.trim().replace(/\s/g, '')
  if (normalized.includes(',') && normalized.includes('.')) {
    const decimal = normalized.lastIndexOf(',') > normalized.lastIndexOf('.') ? ',' : '.'
    normalized = normalized.split(decimal === ',' ? '.' : ',').join('').replace(',', '.')
  } else normalized = normalized.replace(',', '.')
  emitted = /^(?:\d+(?:\.\d*)?|\.\d+)$/.test(normalized) && Number.isFinite(Number(normalized)) ? Number(normalized) : null
  emit('update:modelValue', emitted)
}
function onFocus() {
  focused.value = true
  if (props.modelValue === 0) draft.value = ''
  else input.value?.select()
}
defineExpose({ focus: () => input.value?.focus() })
</script>
