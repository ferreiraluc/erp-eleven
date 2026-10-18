<template>
  <div class="filter-chips" :aria-label="tr('Filtros de estoque')">
    <button v-for="chip in statusChips" :key="chip.value" type="button" class="chip desktop-status erp-control"
      :class="{ active: status === chip.value, 'chip-inactive': chip.value === 'inactive' }"
      :aria-pressed="status === chip.value" @click="emit('status', chip.value)">
      {{ tr(chip.label) }}<span v-if="chip.count !== undefined" class="chip-count">{{ chip.count }}</span>
    </button>

    <ErpSelect class="mobile-only filter-dropdown" compact pill :value="status" :class="{ active: !!status }" :label="tr('Status do estoque')"
      :display-label="tr(statusChips.find(chip => chip.value === status)?.label || 'Todos')" @change="emit('status', $event)">
      <option v-for="chip in statusChips" :key="chip.value" :value="chip.value">{{ tr(chip.label) }}{{ chip.count !== undefined ? ` (${chip.count})` : '' }}</option>
    </ErpSelect>
    <ErpSelect v-if="brands.length" class="filter-dropdown" compact pill searchable :value="brand" :class="{ active: !!brand }" :label="tr('Marca')"
      :display-label="brand || tr('Marca')" @change="emit('brand', $event)">
      <option value="">{{ tr('Todas as marcas') }}</option>
      <option v-for="item in brands" :key="item" :value="item">{{ item }}</option>
    </ErpSelect>
    <ErpSelect v-if="categories.length" class="filter-dropdown" compact pill searchable :value="category" :class="{ active: !!category }" :label="tr('Categoria')"
      :display-label="category ? formatCategory(category) : tr('Categoria')" @change="emit('category', $event)">
      <option value="">{{ tr('Todas as categorias') }}</option>
      <option v-for="item in categories" :key="item" :value="item">{{ formatCategory(item) }}</option>
    </ErpSelect>

    <button type="button" class="chip chip-loc desktop-location erp-control" :class="{ active: location === 'loja' }" :aria-pressed="location === 'loja'" @click="emit('location', 'loja')">
      {{ tr('Loja') }}<span v-if="counts?.loja_count !== undefined" class="chip-count">{{ counts.loja_count }}</span>
    </button>
    <button type="button" class="chip chip-loc desktop-location erp-control" :class="{ active: location === 'deposito' }" :aria-pressed="location === 'deposito'" @click="emit('location', 'deposito')">
      {{ tr('Depósito') }}<span v-if="counts?.deposito_count !== undefined" class="chip-count">{{ counts.deposito_count }}</span>
    </button>
    <ErpSelect class="mobile-only filter-dropdown" compact pill :value="location" :class="{ active: !!location }" :label="tr('Local do estoque')"
      :display-label="tr(location === 'loja' ? 'Loja' : location === 'deposito' ? 'Depósito' : 'Local')" @change="emit('location', $event as 'loja' | 'deposito' | '')">
      <option value="">{{ tr('Local') }}</option>
      <option value="loja">{{ tr('Loja') }} ({{ counts?.loja_count || 0 }})</option>
      <option value="deposito">{{ tr('Depósito') }} ({{ counts?.deposito_count || 0 }})</option>
    </ErpSelect>
    <ErpSelect class="filter-dropdown" compact pill :value="sortBy || ''" :class="{ active: sortBy === 'created_at' }" :label="tr('Ordenação dos produtos')"
      :display-label="tr(sortBy === 'created_at' ? 'Mais recentes' : 'Ordem padrão')" @change="emit('sort', $event)">
      <option value="">{{ tr('Ordem padrão') }}</option>
      <option value="created_at">{{ tr('Adicionados mais recentemente') }}</option>
    </ErpSelect>
    <button type="button" class="chip mobile-only erp-control" :class="{ active: ungroupedOnly }" :aria-pressed="!!ungroupedOnly" @click="emit('toggle-ungrouped')">{{ tr('Sem grade') }}</button>
    <button v-if="hasGroups" type="button" class="chip erp-control" :class="{ active: groupMode }" :aria-pressed="groupMode" @click="emit('toggle-groups')">
      {{ tr('Ver grades') }}<span v-if="counts?.group_count" class="chip-count">{{ counts.group_count }}</span><span v-if="groupMode" aria-hidden="true">✓</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { useInventoryI18n } from '@/components/inventory/i18n'

interface StatusChip { value: string; label: string; count?: number }
interface InventoryCounts { loja_count?: number; deposito_count?: number; group_count?: number }

defineProps<{
  statusChips: StatusChip[]
  status: string
  brands: string[]
  brand: string
  categories: string[]
  category: string
  location: string
  sortBy?: string
  hasGroups: boolean
  groupMode: boolean
  ungroupedOnly?: boolean
  counts?: InventoryCounts | null
}>()
const emit = defineEmits<{
  sort: [value: string]
  status: [value: string]
  brand: [value: string]
  category: [value: string]
  location: [value: 'loja' | 'deposito' | '']
  'toggle-ungrouped': []
  'toggle-groups': []
}>()
const { tr } = useInventoryI18n()
function formatCategory(value: string) { return value ? value.replace('>', ' › ') : '' }
</script>

<style scoped>
.filter-chips{display:flex;gap:.375rem;flex-wrap:wrap;margin-bottom:.5rem}.chip{padding:.375rem .75rem;border-radius:20px;background:#f8fafc;border:1px solid #e5e7eb;font-size:.8rem;cursor:pointer;color:#374151;display:flex;align-items:center;gap:.25rem}.chip.active{background:#eaf1ff;border-color:#93b4ee;color:#1d4ed8;box-shadow:inset 0 1px 0 #ffffff,0 1px 3px #2563eb12}.chip-inactive.active{background:#fee2e2;border-color:#ef4444;color:#b91c1c}.chip-count{background:#bfdbfe;color:#1e40af;border-radius:10px;padding:0 5px;font-size:.7rem;min-width:16px;text-align:center}.chip.active .chip-count{background:var(--color-brand-600);color:#fff}.chip-inactive.active .chip-count{background:#b91c1c}
.filter-chips>.filter-dropdown{width:auto;max-width:220px;min-width:100px}
.filter-dropdown :deep(.erp-dropdown__value){justify-content:center}
.filter-dropdown.active :deep(.erp-dropdown__control){background:#eaf1ff;border-color:#93b4ee;color:#1d4ed8}
.mobile-only{display:none}
@media(max-width:600px){
.filter-chips{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-bottom:6px}
.desktop-status,.desktop-location{display:none}.mobile-only{display:block}
.filter-chips>.filter-dropdown{width:100%;min-width:0;max-width:100%}
.chip{min-width:0;min-height:32px;padding:4px 7px;border-radius:999px;font-size:.72rem;justify-content:center;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chip-count{font-size:.65rem;min-width:0}
}
</style>
