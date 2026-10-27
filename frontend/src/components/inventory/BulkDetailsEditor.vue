<template>
  <section class="bulk-details">
    <h3>{{ tr('Dados do produto em lote') }}</h3>
    <p class="hint">
      {{ tr('Escolha o campo, aplique ao grupo desejado e confira cada item antes de salvar.') }}
    </p>
    <div class="batch-controls">
      <label
        >{{ tr('Campo para editar')
        }}<ErpDropdown
          v-model="field"
          :options="fieldOptions"
          :label="tr('Campo para editar')"
          :disabled="disabled"
      /></label>
      <label
        >{{ tr('Aplicar dados a')
        }}<ErpDropdown
          v-model="scope"
          :options="scopeChoices"
          :label="tr('Aplicar dados a')"
          :disabled="disabled"
      /></label>
      <label v-if="simpleField && !['cost', 'sale'].includes(field)"
        >{{ tr('Operação')
        }}<ErpDropdown
          v-model="operation"
          :options="operations"
          :label="tr('Operação dos dados')"
          :disabled="disabled"
      /></label>
    </div>
    <p v-if="field === 'group_key'" class="hint">
      {{
        tr(
          'Use o mesmo nome para reunir tamanhos e cores da mesma família. Limpar remove o vínculo, sem excluir produtos.',
        )
      }}
    </p>
    <p v-if="moneyField || field === 'currency'" class="hint">
      {{ tr('A moeda identifica os valores cadastrados; trocar a moeda não converte os preços.') }}
    </p>
    <div v-if="moneyField" class="money-controls">
      <label
        >{{ tr('Moeda')
        }}<ErpDropdown
          v-model="moneyCurrency"
          :options="moneyOptions"
          :placeholder="tr('Manter moeda de cada item')"
          :label="tr('Moeda para aplicar')"
          :disabled="disabled"
      /></label>
      <label
        >{{ tr('Preço')
        }}<BulkDetailInput :field="moneyField" v-model="value" :label="tr('Preço para aplicar')"
      /></label>
      <p class="hint">{{ tr('Preço em branco mantém o valor de cada item.') }}</p>
    </div>
    <BulkCategoryInput
      v-else-if="field === 'category' && operation !== 'clear'"
      :model-value="String(value ?? '')"
      :categories="allCategories"
      :label="tr('Categoria para aplicar')"
      @update:model-value="value = $event"
    />
    <BulkDetailInput
      v-else-if="simpleField && operation !== 'clear'"
      :field="simpleField"
      v-model="value"
      :brands="brands"
      :colors="previewItems.map((item) => item.color || '')"
      :categories="allCategories"
      :suppliers="suppliers"
      :label="tr('Valor para aplicar')"
    />
    <div v-if="field === 'stock'" class="stock-controls">
      <label
        >{{ tr('Operação')
        }}<ErpDropdown
          v-model="stockOperation"
          :options="[
            { value: 'keep', label: tr('Manter quantidade') },
            { value: 'set', label: tr('Definir quantidade') },
            { value: 'add', label: tr('Somar ou retirar') },
          ]"
          :label="tr('Operação de quantidade')"
      /></label>
      <label v-if="stockOperation !== 'keep'"
        >{{ tr('Quantidade')
        }}<StockQuantityInput
          v-model="amount"
          always-show-buttons
          :min="stockOperation === 'set' ? 0 : -MAX_STOCK"
          :aria-label="tr('Quantidade para aplicar')"
          :disabled="disabled || !targets.some(hasKnownStock)"
          @keydown.enter.stop.prevent="prepare"
      /></label>
      <label
        >{{ tr('Estoque Mínimo')
        }}<BulkDetailInput field="min_stock" v-model="minimum" :label="tr('Mínimo para aplicar')"
      /></label>
      <label
        >{{ tr('Estoque Máximo')
        }}<BulkDetailInput field="max_stock" v-model="maximum" :label="tr('Máximo para aplicar')"
      /></label>
      <p class="hint wide">
        {{ tr('Limites em branco mantêm os valores atuais. Máximo zero significa sem limite.') }}
      </p>
      <label class="wide"
        >{{ tr('Motivo do ajuste (opcional)')
        }}<input v-model="stockReason" :aria-label="tr('Motivo do ajuste (opcional)')"
      /></label>
    </div>
    <div v-if="field === 'name_replace'" class="name-controls">
      <p class="hint wide">
        {{
          tr('Substitua uma palavra ou trecho. O restante do nome e os tamanhos são preservados.')
        }}
      </p>
      <label
        >{{ tr('Localizar no nome')
        }}<input v-model="nameFind" :aria-label="tr('Localizar no nome')" placeholder="Biss"
      /></label>
      <label
        >{{ tr('Substituir por')
        }}<input v-model="nameReplacement" :aria-label="tr('Substituir por')" placeholder="Boss"
      /></label>
      <p class="hint wide">
        {{ tr('{count} nomes serão alterados', { count: namePreview.length }) }}
      </p>
    </div>
    <!-- Keep asynchronous photo preparation and barcode scans alive when switching fields. -->
    <BulkBarcodeEditor
      v-show="field === 'barcode'"
      embedded
      :selected-scope="scope"
      :items="previewItems"
      v-model="barcodes"
      :disabled="disabled"
    />
    <BulkPhotoEditor
      v-show="field === 'photo'"
      embedded
      :selected-scope="scope"
      :items="previewItems"
      :model-value="photos"
      :disabled="disabled"
      @update:model-value="emit('update:photos', $event)"
      @busy="emit('busy', $event)"
    />
    <p v-if="supplierError && field === 'supplier_id'" class="error" role="alert">
      {{ tr('Não foi possível carregar fornecedores.') }}
      <button
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="loadSuppliers"
      >
        {{ tr('Tentar novamente') }}
      </button>
    </p>
    <button
      v-if="!['barcode', 'photo'].includes(field)"
      type="button"
      class="erp-button erp-button--secondary erp-button--sm prepare-button"
      :disabled="disabled || !canPrepare"
      @click="prepare"
    >
      {{ tr('Preparar alteração · {count}', { count: targets.length }) }}
    </button>
    <p v-if="error" role="alert" class="error">{{ tr(error) }}</p>
    <p v-if="prepared" role="status" class="hint">
      {{ tr('Alterações preparadas. Confira os itens e salve para concluir.') }}
    </p>

    <div class="review-heading">
      <h3>
        {{ tr('Conferir itens') }} <small>· {{ items.length }}</small>
      </h3>
      <label
        >{{ tr('Local do ajuste')
        }}<ErpDropdown
          v-model="location"
          :options="[
            { value: 'loja', label: tr('Loja') },
            { value: 'deposito', label: tr('Depósito') },
          ]"
          :label="tr('Local do ajuste')"
          :disabled="disabled"
      /></label>
    </div>
    <p class="hint">
      {{
        tr(
          'A quantidade pode ser ajustada em cada linha. O outro local é preservado. Trocar o campo conserva todas as alterações preparadas.',
        )
      }}
    </p>
    <div class="product-rows">
      <article
        v-for="item in items"
        :key="item.id"
        class="product-row"
        :class="{ modified: isChanged(item) }"
        :data-detail-item="item.id"
        :data-stock-item="item.id"
      >
        <div class="product-summary">
          <img
            v-if="photos[item.id]"
            :src="photos[item.id].preview"
            class="card-thumb"
            :alt="
              tr(photos[item.id].operation === 'add' ? 'Foto a adicionar' : 'Nova foto principal')
            "
          />
          <ProductThumbnail
            v-else-if="item.image_data || item.has_image"
            :item="item"
            class="card-thumb"
          />
          <div class="product-info">
            <div class="badges">
              <span>{{
                canonicalSize(String(itemValue(item, 'size') || '')) || tr('Sem tamanho')
              }}</span
              ><span>{{ itemValue(item, 'color') || tr('Sem cor') }}</span
              ><small v-if="isChanged(item)">{{ tr('Alterado') }}</small>
            </div>
            <BulkDetailInput
              v-if="field === 'name_replace'"
              field="name"
              :model-value="itemValue(item, 'name')"
              :label="tr('Nome de {name}', { name: item.name })"
              @update:model-value="write(item, 'name', $event)"
            />
            <strong v-else>{{ itemValue(item, 'name') }}</strong>
            <p v-if="field !== 'description'" class="product-description">
              {{ itemValue(item, 'description') || tr('Sem descrição') }}
            </p>
            <small
              >{{ item.inventory_code || item.sku_internal }} · {{ tr('Loja') }}:
              {{ displayStock(stock[item.id]?.loja ?? item.stock_loja) }} · {{ tr('Depósito') }}:
              {{ displayStock(stock[item.id]?.deposito ?? item.stock_deposito) }}</small
            >
            <small v-if="photos[item.id]">{{
              tr(photos[item.id].operation === 'add' ? 'Foto a adicionar' : 'Nova foto principal')
            }}</small>
            <small v-if="changedFields(item).length" class="change-summary"
              >{{ tr('Alterações') }}: {{ changedFields(item).join(' · ') }}</small
            >
          </div>
        </div>
        <div class="stock-count">
          <span>{{ tr('Qtd. final') }} · {{ tr(location === 'loja' ? 'Loja' : 'Depósito') }}</span>
          <StockQuantityInput
            :model-value="stock[item.id]?.[location] ?? ''"
            always-show-buttons
            :disabled="disabled || !hasKnownStock(item)"
            :aria-label="tr('Quantidade {name}', { name: item.name })"
            :aria-invalid="hasKnownStock(item) && !validStockCount(stock[item.id]?.[location])"
            @update:model-value="updateQuantity(item.id, $event)"
            @keydown.enter.stop.prevent
          />
          <small v-if="!hasKnownStock(item)">{{ tr('Revisar estoque') }}</small>
        </div>
        <div v-if="moneyField" class="row-editor money-controls">
          <label
            >{{ tr('Moeda')
            }}<BulkDetailInput
              :field="moneyCurrencyField"
              :model-value="itemValue(item, moneyCurrencyField)"
              :label="tr('Moeda de {name}', { name: item.name })"
              @update:model-value="write(item, moneyCurrencyField, $event)"
          /></label>
          <label
            >{{ tr('Preço')
            }}<BulkDetailInput
              :field="moneyField"
              :model-value="itemValue(item, moneyField)"
              :label="tr('Preço de {name}', { name: item.name })"
              @update:model-value="write(item, moneyField, $event)"
          /></label>
        </div>
        <div v-else-if="field === 'stock'" class="row-editor stock-limits">
          <label
            >{{ tr('Estoque Mínimo')
            }}<BulkDetailInput
              field="min_stock"
              :model-value="itemValue(item, 'min_stock')"
              :label="tr('Mínimo de {name}', { name: item.name })"
              @update:model-value="write(item, 'min_stock', $event)"
          /></label>
          <label
            >{{ tr('Estoque Máximo')
            }}<BulkDetailInput
              field="max_stock"
              :model-value="itemValue(item, 'max_stock')"
              :label="tr('Máximo de {name}', { name: item.name })"
              @update:model-value="write(item, 'max_stock', $event)"
          /></label>
        </div>
        <BulkCategoryInput
          v-else-if="field === 'category'"
          class="row-editor"
          :model-value="String(itemValue(item, 'category') ?? '')"
          :categories="allCategories"
          :label="item.name"
          @update:model-value="write(item, 'category', $event)"
        />
        <label v-else-if="simpleField" class="row-editor"
          >{{ tr(definition?.label || '')
          }}<BulkDetailInput
            :field="simpleField"
            :model-value="itemValue(item, simpleField)"
            :brands="brands"
            :colors="previewItems.map((item) => item.color || '')"
            :categories="allCategories"
            :suppliers="suppliers"
            :label="
              tr('{field} de {name}', { field: tr(definition?.label || ''), name: item.name })
            "
            @update:model-value="write(item, simpleField!, $event)"
        /></label>
      </article>
    </div>
    <div class="stock-summary" role="status">
      <strong>{{ tr('{count} produtos com alterações', { count: changedCount }) }}</strong>
      <span>{{ tr('Peças na seleção após salvar') }}: {{ totals }}</span>
      <span v-if="validationError" class="error">{{ tr(validationError) }}</span>
    </div>
  </section>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import BulkDetailInput from './BulkDetailInput.vue'
import BulkCategoryInput from './BulkCategoryInput.vue'
import BulkBarcodeEditor from './BulkBarcodeEditor.vue'
import BulkPhotoEditor from './BulkPhotoEditor.vue'
import StockQuantityInput from './StockQuantityInput.vue'
import ProductThumbnail from './ProductThumbnail.vue'
import { inventoryAPI, type InventoryItem, type InventorySupplier } from '@/services/api'
import {
  detailFields,
  detailValue,
  setDetail,
  scopeOptions,
  inScope,
  detailsError,
  type DetailDraft,
  type DetailKey,
  type DetailValue,
} from '@/services/inventoryBulkDetails'
import { type PhotoDraft } from '@/services/inventoryBulkPhotos'
import {
  changedStock,
  validStockCount,
  validStockDraft,
  MAX_STOCK,
  type StockDraft,
  type StockLocation,
} from '@/services/inventoryBulkStock'
import { displayStock, hasKnownStock } from '@/services/inventoryStock'
import { canonicalSize } from '@/services/inventoryTaxonomy'
import { replaceProductName } from '@/services/inventoryNameReplace'
import { useInventoryI18n } from './i18n'
const { tr, numberLocale } = useInventoryI18n()
const props = defineProps<{
  items: InventoryItem[]
  modelValue: DetailDraft
  stock: StockDraft
  photos: PhotoDraft
  reason: string
  disabled?: boolean
  brands?: string[]
  categories?: string[]
}>()
const emit = defineEmits<{
  'update:modelValue': [value: DetailDraft]
  'update:stock': [value: StockDraft]
  'update:photos': [value: PhotoDraft]
  'update:reason': [value: string]
  busy: [value: boolean]
}>()
type EditorField = DetailKey | 'cost' | 'sale' | 'stock' | 'photo' | 'name_replace'
const field = ref<EditorField>('description'),
  scope = ref('all'),
  operation = ref('replace'),
  value = ref<DetailValue>('')
const moneyCurrency = ref(''),
  minimum = ref<DetailValue>(''),
  maximum = ref<DetailValue>('')
const amount = ref(0),
  stockOperation = ref('keep'),
  location = ref<StockLocation>('loja')
const nameFind = ref(''),
  nameReplacement = ref(''),
  error = ref(''),
  prepared = ref(false)
const suppliers = ref<InventorySupplier[]>([]),
  supplierError = ref(false),
  suppliersLoaded = ref(false)
const stockReason = computed({ get: () => props.reason, set: (v) => emit('update:reason', v) })
const hiddenFields = new Set([
  'name',
  'cost_price',
  'sale_price',
  'cost_currency',
  'sale_currency',
  'min_stock',
  'max_stock',
  'barcode',
])
const fieldOptions = computed(() => [
  ...detailFields
    .filter((f) => !hiddenFields.has(f.key))
    .map((f) => ({
      value: f.key,
      label: tr(f.key === 'category' ? 'Categoria e subcategoria' : f.label),
    })),
  { value: 'cost', label: tr('Moeda e preço de custo') },
  { value: 'sale', label: tr('Moeda e preço de venda') },
  { value: 'stock', label: tr('Estoque: quantidade, mínimo e máximo') },
  { value: 'barcode', label: tr('Códigos de barras em lote') },
  { value: 'photo', label: tr('Fotos por cor') },
  { value: 'name_replace', label: tr('Corrigir nomes com substituição') },
])
const definition = computed(() => detailFields.find((f) => f.key === field.value))
const simpleField = computed(() => definition.value?.key)
const moneyField = computed(() =>
  field.value === 'cost' ? 'cost_price' : field.value === 'sale' ? 'sale_price' : undefined,
)
const moneyCurrencyField = computed(() =>
  field.value === 'cost' ? 'cost_currency' : 'sale_currency',
)
const moneyOptions = computed(() => [
  { value: '', label: tr('Manter moeda de cada item') },
  ...['USD', 'BRL', 'PYG', 'EUR'].map((value) => ({ value, label: value })),
])
const previewItems = computed(() =>
  props.items.map((item) => ({ ...item, ...props.modelValue[item.id] }) as InventoryItem),
)
const allCategories = computed(() => [
  ...new Set(
    [...(props.categories || []), ...props.items.map((i) => i.category || '')].filter(Boolean),
  ),
])
const scopeChoices = computed(() => [
  { value: 'all', label: tr('Todos os selecionados') },
  ...scopeOptions(previewItems.value).map((o) => ({ ...o, label: `${tr(o.kind)}: ${o.label}` })),
])
const targets = computed(() =>
  props.items.filter((_, index) => inScope(previewItems.value[index], scope.value)),
)
const operations = computed(() => [
  { value: 'replace', label: tr('Substituir') },
  ...(field.value === 'description' ? [{ value: 'append', label: tr('Adicionar ao final') }] : []),
  ...(definition.value && 'clear' in definition.value
    ? [{ value: 'clear', label: tr('Limpar campo') }]
    : []),
])
const barcodes = computed({
  get: () =>
    Object.fromEntries(
      props.items.map((item) => [item.id, String(itemValue(item, 'barcode') || '')]),
    ),
  set: (values) => {
    let next = props.modelValue
    for (const item of props.items)
      if (item.id in values) next = setDetail(next, item, 'barcode', values[item.id])
    emit('update:modelValue', next)
  },
})
const namePreview = computed(() =>
  targets.value.flatMap((item) => {
    const before = String(itemValue(item, 'name')),
      after = replaceProductName(before, nameFind.value, nameReplacement.value)
    return before !== after ? [{ item, after }] : []
  }),
)
watch(field, () => {
  operation.value = 'replace'
  value.value =
    field.value === 'is_active'
      ? true
      : field.value === 'currency'
        ? 'USD'
        : field.value === 'supplier_id'
          ? null
          : ''
  moneyCurrency.value = ''
  error.value = ''
  prepared.value = false
  if (field.value === 'supplier_id' && !suppliersLoaded.value) void loadSuppliers()
})
watch(scopeChoices, (options) => {
  if (!options.some((o) => o.value === scope.value)) scope.value = 'all'
})
async function loadSuppliers() {
  supplierError.value = false
  try {
    suppliers.value = await inventoryAPI.getSuppliers()
    suppliersLoaded.value = true
  } catch {
    supplierError.value = true
  }
}
function itemValue(item: InventoryItem, key: DetailKey) {
  return detailValue(item, key, props.modelValue)
}
function write(item: InventoryItem, key: DetailKey, v: DetailValue) {
  if (!props.disabled) emit('update:modelValue', setDetail(props.modelValue, item, key, v))
}
function updateQuantity(id: string, quantity: number) {
  if (!props.disabled && props.stock[id])
    emit('update:stock', {
      ...props.stock,
      [id]: { ...props.stock[id], [location.value]: quantity },
    })
}
const canPrepare = computed(
  () =>
    targets.value.length > 0 &&
    (field.value === 'name_replace'
      ? namePreview.value.length > 0
      : moneyField.value
        ? value.value !== '' || moneyCurrency.value !== ''
        : field.value === 'stock'
          ? stockOperation.value !== 'keep' || minimum.value !== '' || maximum.value !== ''
          : field.value === 'supplier_id'
            ? !supplierError.value && suppliersLoaded.value
            : true),
)
function prepare() {
  if (props.disabled || !canPrepare.value) return
  let next = props.modelValue
  const quantities = { ...props.stock }
  error.value = ''
  prepared.value = false
  if (field.value === 'stock') {
    for (const item of targets.value) {
      if (hasKnownStock(item) && stockOperation.value !== 'keep') {
        const current = quantities[item.id]
        const quantity =
          stockOperation.value === 'set' ? amount.value : current[location.value] + amount.value
        const other = current[location.value === 'loja' ? 'deposito' : 'loja']
        if (!validStockCount(quantity) || quantity + other > MAX_STOCK) {
          error.value =
            'A quantidade aplicada deixaria um saldo inválido. Nenhuma linha foi alterada.'
          return
        }
        quantities[item.id] = { ...current, [location.value]: quantity }
      }
      if (minimum.value !== '') next = setDetail(next, item, 'min_stock', minimum.value)
      if (maximum.value !== '') next = setDetail(next, item, 'max_stock', maximum.value)
    }
  } else if (field.value === 'name_replace') {
    for (const row of namePreview.value) next = setDetail(next, row.item, 'name', row.after)
  } else
    for (const item of targets.value) {
      if (moneyField.value) {
        if (value.value !== '') next = setDetail(next, item, moneyField.value, value.value)
        if (moneyCurrency.value)
          next = setDetail(next, item, moneyCurrencyField.value, moneyCurrency.value)
      } else if (simpleField.value) {
        let v =
          operation.value === 'clear' ? (field.value === 'supplier_id' ? null : '') : value.value
        if (operation.value === 'append')
          v = [itemValue(item, simpleField.value), v].filter(Boolean).join('\n')
        next = setDetail(next, item, simpleField.value, v)
      }
    }
  error.value = detailsError(next, props.items)
  if (error.value) return
  emit('update:modelValue', next)
  if (field.value === 'stock') emit('update:stock', quantities)
  if (field.value === 'name_replace') {
    nameFind.value = ''
    nameReplacement.value = ''
  }
  prepared.value = true
}
function changedFields(item: InventoryItem) {
  return Object.keys(props.modelValue[item.id] || {}).map((key) =>
    tr(detailFields.find((f) => f.key === key)!.label),
  )
}
function isChanged(item: InventoryItem) {
  return (
    !!props.modelValue[item.id] ||
    !!props.photos[item.id] ||
    changedStock([item], props.stock).length > 0
  )
}
const changedCount = computed(() => props.items.filter(isChanged).length)
const validationError = computed(
  () =>
    detailsError(props.modelValue, props.items) ||
    (!validStockDraft(props.items, props.stock)
      ? 'Confira as quantidades: use inteiros a partir de zero, dentro do limite de estoque.'
      : ''),
)
const totals = computed(() =>
  props.items.some((i) => !hasKnownStock(i)) || !validStockDraft(props.items, props.stock)
    ? '—'
    : props.items
        .reduce((sum, i) => sum + props.stock[i.id].loja + props.stock[i.id].deposito, 0)
        .toLocaleString(numberLocale()),
)
</script>
<style scoped>
.bulk-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}
h3,
p {
  margin: 0;
}
h3 {
  font-size: 15px;
  color: #1e293b;
}
h3 small {
  font-weight: 400;
  color: #64748b;
}
.hint {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.batch-controls,
.stock-controls,
.name-controls,
.money-controls,
.stock-limits {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  min-width: 0;
}
.batch-controls > label:first-child,
.wide,
.money-controls > .hint {
  grid-column: 1/-1;
}
label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 12px;
  color: #475569;
  min-width: 0;
}
.prepare-button {
  align-self: start;
}
.review-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-top: 1px solid #e2e8f0;
  padding-top: 16px;
  margin-top: 4px;
}
.review-heading > label {
  width: 160px;
  flex-shrink: 0;
}
.product-rows {
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  overflow: hidden;
}
.product-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 148px;
  gap: 12px;
  align-items: center;
  padding: 14px;
  border-bottom: 1px solid #e2e8f0;
}
.product-row:last-child {
  border-bottom: 0;
}
.product-row:nth-child(even) {
  background: #f8fafc;
}
.product-row.modified {
  background: #eff6ff;
}
.product-summary {
  display: flex;
  align-items: start;
  gap: 10px;
  min-width: 0;
}
.card-thumb {
  width: 52px;
  height: 60px;
  object-fit: contain;
  border-radius: 8px;
  background: white;
  flex-shrink: 0;
}
.product-info {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.product-info strong {
  font-size: 13px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.product-description {
  font-size: 12px;
  line-height: 1.4;
  color: #475569;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.product-info small,
.stock-count small {
  font-size: 11px;
  line-height: 1.4;
  color: #64748b;
  overflow-wrap: anywhere;
}
.badges {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 5px;
}
.badges > span {
  border-radius: 5px;
  padding: 2px 6px;
  background: #e0e7ff;
  color: #4338ca;
  font-size: 11px;
  font-weight: 600;
  overflow-wrap: anywhere;
}
.badges > span + span {
  background: #fce7f3;
  color: #9d174d;
}
.badges > small,
.product-info .change-summary {
  color: #1d4ed8;
}
.stock-count {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.stock-count > span {
  font-size: 11px;
  color: #64748b;
}
.row-editor {
  grid-column: 1/-1;
}
.stock-summary {
  display: grid;
  gap: 5px;
  border-radius: 10px;
  padding: 12px;
  background: #eff6ff;
  color: #1e3a8a;
  font-size: 12px;
}
.error {
  color: #b91c1c;
  font-size: 12px;
  line-height: 1.5;
}
input {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  border: 1px solid #cbd5e1;
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
  font-size: 14px;
  color: #0f172a;
  background: white;
}
@media (max-width: 480px) {
  .stock-controls,
  .name-controls {
    grid-template-columns: 1fr;
  }
  .product-row {
    grid-template-columns: minmax(0, 1fr) 128px;
    padding: 10px;
    gap: 10px;
  }
  .product-summary {
    grid-column: 1/-1;
  }
  .stock-count {
    grid-column: 2;
    grid-row: 2;
  }
  .row-editor {
    grid-column: 1/-1;
  }
  .product-row > .row-editor {
    grid-row: auto;
  }
  .product-info strong {
    font-size: 14px;
  }
  .card-thumb {
    width: 48px;
    height: 56px;
  }
  .review-heading {
    align-items: end;
  }
  .review-heading > label {
    width: 145px;
  }
}
</style>
