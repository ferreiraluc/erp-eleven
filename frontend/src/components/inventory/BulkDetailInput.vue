<template>
  <textarea v-if="definition.kind === 'text'" :value="String(modelValue ?? '')" :aria-label="label" rows="2" @input="update(($event.target as HTMLTextAreaElement).value)" />
  <ErpDropdown v-else-if="options" :model-value="selectValue" :options="options" :label="label" :editable="['brand', 'category'].includes(definition.kind)" @update:model-value="updateSelection" />
  <input v-else :value="String(modelValue ?? '')" :aria-label="label" :type="definition.kind === 'number' ? 'number' : 'text'" :min="definition.kind === 'number' ? 0 : undefined" :step="definition.kind === 'number' ? 1 : undefined" :maxlength="'max' in definition ? definition.max : undefined" @input="update(($event.target as HTMLInputElement).value)" />
</template>
<script setup lang="ts">
import { computed } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import { detailFields, type DetailKey, type DetailValue } from '@/services/inventoryBulkDetails'
import type { InventorySupplier } from '@/services/api'
import { useInventoryI18n } from './i18n'
const { tr } = useInventoryI18n()
const props = defineProps<{ field: DetailKey; modelValue: DetailValue; label: string; brands?: string[]; categories?: string[]; suppliers?: InventorySupplier[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: DetailValue] }>()
const definition = computed(() => detailFields.find(f => f.key === props.field)!)
const selectValue = computed(() => props.field === 'is_active' ? String(props.modelValue) : String(props.modelValue ?? ''))
const options = computed(() => {
  switch (definition.value.kind) {
    case 'brand': return (props.brands || []).map(value => ({ value, label: value }))
    case 'category': return (props.categories || []).map(value => ({ value, label: value }))
    case 'supplier': return [{ value: '', label: tr('Nenhum') }, ...(props.suppliers || []).map(s => ({ value: s.id, label: s.name }))]
    case 'status': return [{ value: 'true', label: tr('Ativo') }, { value: 'false', label: tr('Inativo') }]
    case 'currency': return [{ value: 'USD', label: 'U$', icon: '🇺🇸' }, { value: 'BRL', label: 'R$', icon: '🇧🇷' }, { value: 'PYG', label: 'G$', icon: '🇵🇾' }, { value: 'EUR', label: 'EUR', icon: '🇪🇺' }]
    default: return undefined
  }
})
function update(value: string) { emit('update:modelValue', definition.value.kind === 'number' && value !== '' ? Number(value) : value) }
function updateSelection(value: string | number | null) {
  emit('update:modelValue', props.field === 'is_active' ? value === 'true' : props.field === 'supplier_id' ? value || null : String(value ?? ''))
}
</script>
<style scoped>
input,textarea{width:100%;min-width:0;box-sizing:border-box;border:1px solid #cbd5e1;border-radius:8px;padding:8px 10px;font:inherit;font-size:14px;background:white;color:#0f172a}textarea{resize:vertical;min-height:64px}input:focus,textarea:focus{outline:2px solid #93c5fd;outline-offset:1px}
</style>
