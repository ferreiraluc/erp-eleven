<template>
  <div class="category-pair">
    <label
      >{{ tr('Categoria')
      }}<ErpDropdown
        :model-value="parts[0]"
        :options="roots"
        editable
        :label="`${label} · ${tr('Categoria')}`"
        @update:model-value="setRoot(String($event ?? ''))"
    /></label>
    <label
      >{{ tr('Subcategoria')
      }}<ErpDropdown
        :model-value="parts[1]"
        :options="children"
        editable
        :disabled="!parts[0]"
        :label="`${label} · ${tr('Subcategoria')}`"
        @update:model-value="update(String($event ?? ''))"
    /></label>
  </div>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import { useInventoryI18n } from './i18n'
const { tr } = useInventoryI18n()
const props = defineProps<{ modelValue: string; categories: string[]; label: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
function split(value: string) {
  const [root = '', ...rest] = value.split('>').map((part) => part.trim())
  return [root, rest.join(' > ')]
}
const parts = computed(() => split(props.modelValue))
const roots = computed(() =>
  [...new Set(props.categories.map((value) => split(value)[0]).filter(Boolean))].map((value) => ({
    value,
    label: value,
  })),
)
const children = computed(() =>
  [
    ...new Set(
      props.categories
        .filter((value) => split(value)[0] === parts.value[0])
        .map((value) => split(value)[1])
        .filter(Boolean),
    ),
  ].map((value) => ({ value, label: value })),
)
function setRoot(root: string) {
  emit('update:modelValue', root.trim())
}
function update(child: string) {
  emit('update:modelValue', [parts.value[0], child.trim()].filter(Boolean).join(' > '))
}
</script>
<style scoped>
.category-pair {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}
label {
  display: grid;
  gap: 5px;
  min-width: 0;
  font-size: 12px;
  color: #475569;
}
@media (max-width: 480px) {
  .category-pair {
    grid-template-columns: 1fr;
  }
}
</style>
