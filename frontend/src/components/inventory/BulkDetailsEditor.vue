<template>
  <section class="bulk-details">
    <h3>{{ tr('Dados do produto em lote') }}</h3>
    <p>{{ tr('Escolha o campo, aplique ao grupo desejado e confira cada item antes de salvar.') }}</p>
    <div class="detail-controls">
      <label>{{ tr('Campo para editar') }}<ErpDropdown v-model="field" :options="fieldOptions" :label="tr('Campo para editar')" /></label>
      <label>{{ tr('Aplicar dados a') }}<ErpDropdown v-model="scope" :options="targetOptions" :label="tr('Aplicar dados a')" /></label>
      <label>{{ tr('Operação') }}<ErpDropdown v-model="operation" :options="operations" :label="tr('Operação dos dados')" /></label>
    </div>
    <p v-if="field === 'group_key'">{{ tr('A mesma família reúne os produtos em Ver grades. Limpar desvincula apenas os selecionados.') }}</p>
    <p v-if="field === 'cost_currency' || field === 'sale_currency' || field === 'currency'">{{ tr('A moeda identifica os valores cadastrados; trocar a moeda não converte os preços.') }}</p>
    <BulkDetailInput v-if="operation !== 'clear'" v-model="value" :field="field" :label="tr('Valor para aplicar')" :brands="brands" :categories="categories" :suppliers="suppliers" />
    <p v-if="supplierError" role="alert">{{ tr('Não foi possível carregar os fornecedores.') }} <button class="erp-button erp-button--secondary erp-button--sm" type="button" @click="loadSuppliers">{{ tr('Tentar novamente') }}</button></p>
    <button type="button" class="erp-button erp-button--secondary erp-button--sm apply-details" :disabled="disabled || !targets.length || (field === 'supplier_id' && supplierError)" @click="apply">{{ tr('Preparar alteração') }} · {{ targets.length }}</button>
    <p v-if="error" role="alert" class="detail-error">{{ tr(error) }}</p>
    <details class="detail-review" :open="Object.keys(modelValue).length > 0">
      <summary>{{ tr('Conferir e editar por item') }} · {{ items.length }}</summary>
      <div class="detail-rows">
        <label v-for="item in items" :key="item.id" :data-detail-item="item.id">
          <span>{{ item.name }} <small>{{ item.inventory_code || item.sku_internal }} · {{ item.size }} · {{ item.color }}</small></span>
          <BulkDetailInput :model-value="detailValue(item, field, modelValue)" :field="field" :label="`${tr(definition.label)} · ${item.name}`" :brands="brands" :categories="categories" :suppliers="suppliers" @update:model-value="set(item, $event)" />
        </label>
      </div>
    </details>
    <p v-if="Object.keys(modelValue).length" role="status">{{ tr('{count} itens com dados preparados.', { count: Object.keys(modelValue).length }) }}</p>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import BulkDetailInput from './BulkDetailInput.vue'
import { inventoryAPI, type InventoryItem, type InventorySupplier } from '@/services/api'
import { detailFields, detailValue, detailsError, setDetail, scopeOptions, inScope, type DetailDraft, type DetailKey, type DetailValue } from '@/services/inventoryBulkDetails'
import { useInventoryI18n } from './i18n'
const { tr } = useInventoryI18n()
const props = defineProps<{ items: InventoryItem[]; modelValue: DetailDraft; disabled?: boolean; brands?: string[]; categories?: string[] }>()
const emit = defineEmits<{ 'update:modelValue': [value: DetailDraft] }>()
const field = ref<DetailKey>('description'), scope = ref('all'), operation = ref('replace'), value = ref<DetailValue>(''), error = ref('')
const suppliers = ref<InventorySupplier[]>([]), supplierError = ref(false)
async function loadSuppliers() {
  try { suppliers.value = await inventoryAPI.getSuppliers(); supplierError.value = false }
  catch { supplierError.value = true }
}
const definition = computed(() => detailFields.find(f => f.key === field.value)!)
const fieldOptions = computed(() => detailFields.map(f => ({ value: f.key, label: tr(f.label) })))
const targetOptions = computed(() => [{ value: 'all', label: tr('Todos os selecionados') }, ...scopeOptions(props.items).map(o => ({ ...o, label: `${tr(o.kind)}: ${o.label}` }))])
const targets = computed(() => props.items.filter(item => inScope(item, scope.value)))
const operations = computed(() => [{ value: 'replace', label: tr('Substituir') },
  ...(field.value === 'description' ? [{ value: 'append', label: tr('Acrescentar ao final') }] : []),
  ...('clear' in definition.value ? [{ value: 'clear', label: tr('Limpar campo') }] : [])])
watch(field, () => {
  operation.value = 'replace'; error.value = ''
  value.value = definition.value.kind === 'status' ? true : definition.value.kind === 'currency' ? 'USD' : definition.value.kind === 'number' ? 0 : ''
  if (field.value === 'supplier_id') void loadSuppliers()
})
function set(item: InventoryItem, next: DetailValue) {
  if (!props.disabled) emit('update:modelValue', setDetail(props.modelValue, item, field.value, next))
}
function apply() {
  if (props.disabled) return
  let next = props.modelValue
  for (const item of targets.value) {
    const after = operation.value === 'clear' ? (['supplier_id', 'group_key'].includes(field.value) ? null : '')
      : operation.value === 'append' ? [detailValue(item, field.value, next), String(value.value ?? '').trim()].filter(Boolean).join('\n') : value.value
    next = setDetail(next, item, field.value, after)
  }
  error.value = detailsError(next)
  if (!error.value) emit('update:modelValue', next)
}
</script>
<style scoped>
.bulk-details{display:flex;flex-direction:column;gap:10px;padding:12px;border:1px solid #dbe3ef;border-radius:12px}.bulk-details h3{margin:0;font-size:14px}.bulk-details p{margin:0;font-size:12px;color:#64748b}.detail-controls{display:grid;grid-template-columns:1fr 1fr;gap:10px}.detail-controls label{min-width:0;font-size:12px;display:flex;flex-direction:column;gap:4px}.detail-controls label:first-child{grid-column:1/-1}.apply-details{align-self:flex-start}.detail-review summary{font-size:13px;cursor:pointer;padding:8px 0}.detail-rows{display:flex;flex-direction:column;gap:12px;max-height:260px;overflow:auto}.detail-rows label{display:flex;flex-direction:column;gap:5px;font-size:13px}.detail-rows small{display:block;color:#64748b;font-size:11px;overflow-wrap:anywhere}.detail-error{color:#b91c1c!important}
</style>
