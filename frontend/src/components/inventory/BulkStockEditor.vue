<template>
  <section class="bulk-stock">
    <div class="stock-heading">
      <h3>{{ tr('Estoque por item') }}</h3>
      <ErpDropdown v-model="location" :options="locationOptions" :label="tr('Local do ajuste')" :disabled="disabled" />
    </div>
    <p class="stock-hint">{{ tr('Confira a quantidade final no local escolhido. O outro local é preservado.') }}</p>
    <div class="stock-bulk-controls">
      <div class="stock-field scope-field"><span>{{ tr('Aplicar quantidade a') }}</span><ErpDropdown v-model="target" :options="targetOptions" :label="tr('Aplicar quantidade a')" :disabled="disabled" /></div>
      <div class="stock-field"><span>{{ tr('Operação') }}</span><ErpDropdown v-model="operation" :options="operationOptions" :label="tr('Operação de quantidade')" :disabled="disabled" /></div>
      <div class="stock-field"><span>{{ tr('Quantidade') }}</span><StockQuantityInput v-model="amount" always-show-buttons :min="operation === 'set' ? 0 : -MAX_STOCK" :disabled="disabled || !eligibleItems.length" :aria-label="tr('Quantidade para aplicar')" @keydown.enter.stop.prevent="apply" /></div>
      <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="disabled || !canApply" @click="apply">{{ tr('Aplicar') }}</button>
    </div>
    <p v-if="applyError" role="alert" class="stock-error">{{ tr(applyError) }}</p>
    <p v-if="applied" role="status" class="stock-hint">{{ tr('Quantidade preparada em {count} itens. Salve para confirmar.', { count: applied }) }}</p>
    <div class="stock-rows">
      <div v-for="item in items" :key="item.id" class="stock-row" :class="{ modified: changed(item) }" :data-stock-item="item.id">
        <div class="stock-product">
          <div class="stock-badges"><span>{{ canonicalSize(item.size || '') || tr('Sem tamanho') }}</span><span>{{ item.color || tr('Sem cor') }}</span></div>
          <strong>{{ item.name }}</strong>
          <small>{{ tr('Loja') }}: {{ displayStock(item.stock_loja) }} · {{ tr('Depósito') }}: {{ displayStock(item.stock_deposito) }}</small>
        </div>
        <div class="stock-count">
          <span>{{ tr('Qtd. final') }} · {{ tr(location === 'loja' ? 'Loja' : 'Depósito') }}</span>
          <StockQuantityInput :model-value="modelValue[item.id]?.[location] ?? ''" always-show-buttons :disabled="disabled || !hasKnownStock(item)" :aria-label="tr('Quantidade {name}', { name: item.name })" :aria-invalid="hasKnownStock(item) && !validStockCount(modelValue[item.id]?.[location])" @update:model-value="update(item.id, $event)" @keydown.enter.stop.prevent />
          <small v-if="!hasKnownStock(item)">{{ tr('Revisar estoque') }}</small>
        </div>
      </div>
    </div>
    <div class="stock-summary" role="status">
      <strong>{{ tr('{count} produtos com saldo alterado', { count: changedStock(items, modelValue).length }) }}</strong>
      <span>{{ tr('Peças na seleção após salvar') }}: {{ totals }}</span>
      <span v-if="!validStockDraft(items, modelValue)" class="stock-error">{{ tr('Confira as quantidades: use inteiros a partir de zero, dentro do limite de estoque.') }}</span>
    </div>
  </section>
</template>

<script setup lang="ts">
import { colorKey } from '@/services/inventoryColors'
import { computed, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import StockQuantityInput from './StockQuantityInput.vue'
import type { InventoryItem } from '@/services/api'
import { canonicalSize } from '@/services/inventoryTaxonomy'
import { displayStock, hasKnownStock } from '@/services/inventoryStock'
import { changedStock, validStockCount, validStockDraft, MAX_STOCK, type StockDraft, type StockLocation } from '@/services/inventoryBulkStock'
import { useInventoryI18n } from './i18n'
const { tr, numberLocale } = useInventoryI18n()
const props = defineProps<{ items: InventoryItem[]; modelValue: StockDraft; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: StockDraft] }>()
const location = ref<StockLocation>('loja'), target = ref('all'), operation = ref('set'), amount = ref(0)
const applyError = ref(''), applied = ref(0)
const locationOptions = computed(() => [{ value: 'loja', label: tr('Loja') }, { value: 'deposito', label: tr('Depósito') }])
const operationOptions = computed(() => [{ value: 'set', label: tr('Definir quantidade') }, { value: 'add', label: tr('Somar ou retirar') }])
function identity(item: InventoryItem, field: 'color' | 'size') {
  return field === 'color' ? colorKey(item.color || '') : canonicalSize(item.size || '').toLowerCase()
}
const targetOptions = computed(() => {
  const result = [{ value: 'all', label: tr('Todos os selecionados') }]
  for (const field of ['color', 'size'] as const) {
    const labels = new Map(props.items.map(item => [identity(item, field), field === 'size' ? canonicalSize(item.size || '') : item.color || '']))
    for (const [key, label] of labels) result.push({ value: JSON.stringify([field, key]), label: `${tr(field === 'color' ? 'Cor' : 'Tamanho')}: ${label || tr(field === 'color' ? 'Sem cor' : 'Sem tamanho')}` })
  }
  return result
})
watch(targetOptions, options => { if (!options.some(option => option.value === target.value)) target.value = 'all' })
watch([target, operation, location, amount], () => { applied.value = 0; applyError.value = '' })
const eligibleItems = computed(() => {
  const filter = target.value === 'all' ? null : JSON.parse(target.value) as ['color' | 'size', string]
  return props.items.filter(item => hasKnownStock(item) && (!filter || identity(item, filter[0]) === filter[1]))
})
const canApply = computed(() => eligibleItems.value.length > 0 && Number.isInteger(amount.value) && Math.abs(amount.value) <= MAX_STOCK && (operation.value !== 'set' || amount.value >= 0))
function apply() {
  if (props.disabled || !canApply.value) return
  const next = { ...props.modelValue }
  for (const item of eligibleItems.value) {
    const current = next[item.id]
    const quantity = operation.value === 'set' ? amount.value : current[location.value] + amount.value
    const other = current[location.value === 'loja' ? 'deposito' : 'loja']
    if (!validStockCount(quantity) || quantity + other > MAX_STOCK) {
      applyError.value = 'A quantidade aplicada deixaria um saldo inválido. Nenhuma linha foi alterada.'
      return
    }
    next[item.id] = { ...current, [location.value]: quantity }
  }
  emit('update:modelValue', next)
  applyError.value = ''; applied.value = eligibleItems.value.length
}
function update(id: string, quantity: number) {
  if (props.disabled || !props.modelValue[id]) return
  emit('update:modelValue', { ...props.modelValue, [id]: { ...props.modelValue[id], [location.value]: quantity } })
}
function changed(item: InventoryItem) { return changedStock([item], props.modelValue).length > 0 }
const totals = computed(() => {
  if (props.items.some(item => !hasKnownStock(item)) || !validStockDraft(props.items, props.modelValue)) return '—'
  return props.items.reduce((sum, item) => sum + props.modelValue[item.id].loja + props.modelValue[item.id].deposito, 0).toLocaleString(numberLocale())
})
</script>

<style scoped>
.bulk-stock{display:flex;flex-direction:column;gap:12px}.stock-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.stock-heading h3{margin:0;font-size:15px;color:#1e293b}.stock-heading .erp-dropdown{width:150px}.stock-hint{margin:0;font-size:12px;line-height:1.5;color:#64748b}.stock-bulk-controls{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);align-items:end;gap:10px;padding:12px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px}.stock-bulk-controls .stock-field{display:flex;flex-direction:column;gap:5px;min-width:0;font-size:12px;color:#475569}.stock-bulk-controls>.erp-button{justify-self:end;min-height:40px}.stock-rows{border:1px solid #e2e8f0;border-radius:12px;overflow:hidden}.stock-row{display:grid;grid-template-columns:minmax(0,1fr) 148px;gap:12px;align-items:center;padding:12px;border-bottom:1px solid #e2e8f0}.stock-row:last-child{border-bottom:0}.stock-row:nth-child(even){background:#f8fafc}.stock-row.modified{background:#eff6ff}.stock-product{display:flex;flex-direction:column;min-width:0;gap:5px}.stock-product strong{font-size:13px;font-weight:500;overflow-wrap:anywhere}.stock-product small,.stock-count small{font-size:11px;color:#64748b}.stock-badges{display:flex;gap:5px;flex-wrap:wrap}.stock-badges span{border-radius:5px;background:#e0e7ff;color:#4338ca;padding:2px 6px;font-size:11px;font-weight:600;overflow-wrap:anywhere}.stock-badges span+span{background:#fce7f3;color:#9d174d}.stock-count{display:flex;flex-direction:column;gap:5px;min-width:0}.stock-count>span{font-size:11px;color:#64748b}.stock-summary{display:flex;flex-direction:column;gap:5px;padding:12px;background:#eff6ff;color:#1e3a8a;border-radius:10px;font-size:12px}.stock-error{color:#b91c1c;font-size:12px;margin:0}
@media(max-width:400px){.stock-row{grid-template-columns:minmax(0,1fr) 128px;gap:8px;padding:10px}.stock-bulk-controls{padding:10px;gap:8px}}
</style>
