<template>
  <div ref="root" class="filter-chips" :aria-label="tr('Filtros de estoque')">
    <button v-for="chip in statusChips" :key="chip.value" type="button" class="chip erp-control"
      :class="{ active: status === chip.value, 'chip-inactive': chip.value === 'inactive' }"
      :aria-pressed="status === chip.value" @click="emit('status', chip.value)">
      {{ tr(chip.label) }}<span v-if="chip.count !== undefined" class="chip-count">{{ chip.count }}</span>
    </button>

    <div v-if="brands.length" class="chip-dd-wrap">
      <button type="button" class="chip erp-control" :class="{ active: !!brand }" :aria-expanded="open === 'brand'" @click.stop="toggle('brand')">
        {{ brand || tr('Marca') }} <span class="chip-caret" aria-hidden="true">▾</span>
      </button>
      <div v-if="open === 'brand'" class="chip-dropdown">
        <div class="chip-dd-search-wrap"><input v-model="brandSearch" class="chip-dd-search" :aria-label="tr('Buscar marca...')" :placeholder="tr('Buscar marca...')" type="search" autocomplete="off" /></div>
        <button type="button" class="chip-dd-opt erp-control" :class="{ active: !brand }" @click="choose('brand', '')">{{ tr('Todas as marcas') }}</button>
        <button v-for="item in filteredBrands" :key="item" type="button" class="chip-dd-opt erp-control" :class="{ active: brand === item }" @click="choose('brand', item)">{{ item }}</button>
      </div>
    </div>

    <div v-if="categories.length" class="chip-dd-wrap">
      <button type="button" class="chip erp-control" :class="{ active: !!category }" :aria-expanded="open === 'category'" @click.stop="toggle('category')">
        {{ category ? formatCategory(category) : tr('Categoria') }} <span class="chip-caret" aria-hidden="true">▾</span>
      </button>
      <div v-if="open === 'category'" class="chip-dropdown">
        <div class="chip-dd-search-wrap"><input v-model="categorySearch" class="chip-dd-search" :aria-label="tr('Buscar categoria...')" :placeholder="tr('Buscar categoria...')" type="search" autocomplete="off" /></div>
        <button type="button" class="chip-dd-opt erp-control" :class="{ active: !category }" @click="choose('category', '')">{{ tr('Todas as categorias') }}</button>
        <button v-for="item in filteredCategories" :key="item" type="button" class="chip-dd-opt erp-control" :class="{ active: category === item }" @click="choose('category', item)">{{ formatCategory(item) }}</button>
      </div>
    </div>

    <button type="button" class="chip chip-loc erp-control" :class="{ active: location === 'loja' }" :aria-pressed="location === 'loja'" @click="emit('location', 'loja')">
      {{ tr('Loja') }}<span v-if="counts?.loja_count !== undefined" class="chip-count">{{ counts.loja_count }}</span>
    </button>
    <button type="button" class="chip chip-loc erp-control" :class="{ active: location === 'deposito' }" :aria-pressed="location === 'deposito'" @click="emit('location', 'deposito')">
      {{ tr('Depósito') }}<span v-if="counts?.deposito_count !== undefined" class="chip-count">{{ counts.deposito_count }}</span>
    </button>
    <button v-if="hasGroups" type="button" class="chip erp-control" :class="{ active: groupMode }" :aria-pressed="groupMode" @click="emit('toggle-groups')">
      {{ tr('Ver grades') }}<span v-if="counts?.group_count" class="chip-count">{{ counts.group_count }}</span><span v-if="groupMode" aria-hidden="true">✓</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useInventoryI18n } from '@/components/inventory/i18n'
import { taxonomyKey } from '@/services/inventoryTaxonomy'

type FilterKey = 'brand' | 'category'
interface StatusChip { value: string; label: string; count?: number }
interface InventoryCounts { loja_count?: number; deposito_count?: number; group_count?: number }

const props = defineProps<{
  statusChips: StatusChip[]
  status: string
  brands: string[]
  brand: string
  categories: string[]
  category: string
  location: string
  hasGroups: boolean
  groupMode: boolean
  counts?: InventoryCounts | null
}>()
const emit = defineEmits<{
  status: [value: string]
  brand: [value: string]
  category: [value: string]
  location: [value: 'loja' | 'deposito']
  'toggle-groups': []
}>()
const { tr } = useInventoryI18n()
const root = ref<HTMLElement | null>(null)
const open = ref<FilterKey | null>(null)
const brandSearch = ref('')
const categorySearch = ref('')
const filteredBrands = computed(() => brandSearch.value.trim() ? props.brands.filter(item => taxonomyKey(item).includes(taxonomyKey(brandSearch.value))) : props.brands)
const filteredCategories = computed(() => categorySearch.value.trim() ? props.categories.filter(item => taxonomyKey(item).includes(taxonomyKey(categorySearch.value))) : props.categories)

function formatCategory(value: string) { return value ? value.replace('>', ' › ') : '' }
function close() { open.value = null; brandSearch.value = ''; categorySearch.value = '' }
function toggle(key: FilterKey) {
  if (open.value === key) close()
  else open.value = key
}
function choose(key: FilterKey, value: string) {
  if (key === 'brand') emit('brand', value)
  else emit('category', value)
  close()
}
function onDocumentClick(event: MouseEvent) { if (root.value && !root.value.contains(event.target as Node)) close() }
onMounted(() => document.addEventListener('click', onDocumentClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocumentClick))
</script>

<style scoped>
.filter-chips{display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:.5rem}.chip{padding:.375rem .75rem;border-radius:20px;background:#f3f4f6;border:1px solid #e5e7eb;font-size:.8rem;cursor:pointer;color:#374151;display:flex;align-items:center;gap:.25rem}.chip.active{background:var(--color-brand-100);border-color:var(--color-brand-600);color:var(--color-brand-700)}.chip-inactive.active{background:#fee2e2;border-color:#ef4444;color:#b91c1c}.chip-count{background:#bfdbfe;color:#1e40af;border-radius:10px;padding:0 5px;font-size:.7rem;min-width:16px;text-align:center}.chip.active .chip-count{background:var(--color-brand-600);color:#fff}.chip-inactive.active .chip-count{background:#b91c1c}.chip-dd-wrap{position:relative}.chip-caret{font-size:.6rem;margin-left:.2rem}.chip-dropdown{position:absolute;top:calc(100% + 4px);left:0;z-index:200;background:#fff;border:1px solid var(--color-border);border-radius:var(--radius-md);box-shadow:0 4px 16px rgb(15 23 42 / 12%);min-width:180px;max-height:240px;overflow-y:auto}.chip-dd-search-wrap{padding:.35rem .5rem;border-bottom:1px solid #f3f4f6;position:sticky;top:0;background:#fff;z-index:1}.chip-dd-search{width:100%;font-size:.78rem;border:1px solid var(--color-border);border-radius:var(--radius-sm);padding:.35rem .5rem;box-sizing:border-box;color:#374151}.chip-dd-opt{display:block;width:100%;text-align:left;padding:.45rem .85rem;font-size:.82rem;color:#374151;background:none;border:none;cursor:pointer}.chip-dd-opt:hover{background:#f8fafc}.chip-dd-opt.active{background:var(--color-brand-100);color:var(--color-brand-700);font-weight:600}
@media(max-width:600px){.chip-dropdown{position:static;width:min(260px,calc(100vw - 3rem));max-height:220px;margin-top:.35rem}}
</style>
