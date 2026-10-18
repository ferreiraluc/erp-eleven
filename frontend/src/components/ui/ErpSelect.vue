<template>
  <ErpDropdown
    v-bind="$attrs"
    :model-value="modelValue !== undefined ? modelValue : value"
    :options="readOptions()"
    :label="label || ($attrs['aria-label'] as string | undefined)"
    :disabled="disabled"
    :required="required"
    :id="id"
    :placeholder="placeholder"
    @update:model-value="choose"
  />
</template>
<script setup lang="ts" generic="T extends DropdownValue">
import { useSlots } from 'vue'
import ErpDropdown from './ErpDropdown.vue'
import { slotOptions, type DropdownValue, type DropdownOption } from './dropdownOptions'
defineOptions({ inheritAttrs: false })
const props = defineProps<{
  modelValue?: T
  value?: T
  modelModifiers?: { number?: boolean; trim?: boolean }
  label?: string
  placeholder?: string
  id?: string
  disabled?: boolean
  required?: boolean
}>()
const emit = defineEmits<{ 'update:modelValue': [value: T]; change: [value: T] }>()
const slots = useSlots()
// Evaluate in render, so asynchronously loaded/translatable slot options update.
function readOptions() {
  return slotOptions(slots.default?.() || []) as DropdownOption<T>[]
}
function choose(raw: T | undefined) {
  let value = raw
  if (typeof value === 'string' && props.modelModifiers?.trim) value = value.trim() as T
  if (
    typeof value === 'string' &&
    props.modelModifiers?.number &&
    value !== '' &&
    Number.isFinite(Number(value))
  )
    value = Number(value) as T
  emit('update:modelValue', value as T)
  emit('change', value as T)
}
</script>
