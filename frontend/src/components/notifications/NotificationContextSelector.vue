<template>
  <fieldset class="notification-context" :disabled="disabled">
    <legend>{{ n('context') }}</legend>
    <template v-if="!lockedSale">
      <label
        >{{ n('contextSearch')
        }}<input
          v-model="search"
          type="search"
          maxlength="100"
          :placeholder="n('contextSearchHelp')"
          autocomplete="off"
      /></label>
      <ErpDropdown
        v-if="options.length"
        :model-value="modelValue?.sale_id || ''"
        :options="options"
        :label="n('contextChooseSale')"
        :disabled="disabled"
        @update:model-value="chooseSale(String($event))"
      />
      <p v-if="searched && !results.length && !searching" class="context-hint">
        {{ n('contextNoResults') }}
      </p>
      <p v-if="hasMore" class="context-hint">{{ n('contextMoreResults') }}</p>
    </template>
    <p v-if="searching || loading" class="context-hint" role="status">{{ n('loading') }}</p>
    <p v-if="error" class="context-error" role="alert">{{ error }}</p>
    <div v-if="sale" class="context-summary">
      <strong>#{{ sale.code }}</strong
      ><span>{{ n('contextSeller') }}: {{ sale.seller_name || '—' }}</span>
      <button
        v-if="!lockedSale"
        type="button"
        class="erp-button erp-button--ghost erp-button--sm"
        @click="emit('update:modelValue', null)"
      >
        {{ n('contextClear') }}
      </button>
    </div>
    <template v-if="modelValue?.target === 'product'">
      <label
        >{{ n('contextProductSearch')
        }}<input v-model="productSearch" type="search" maxlength="100" autocomplete="off"
      /></label>
      <label
        >{{ n('contextChooseProduct')
        }}<ErpDropdown
          :model-value="modelValue.item_id || ''"
          :options="productOptions"
          :label="n('contextChooseProduct')"
          :disabled="disabled || productLoading"
          @update:model-value="chooseProduct(String($event))"
      /></label>
      <p class="context-hint">{{ n('contextProductHelp') }}</p>
      <p v-if="productLoading || productSearching" class="context-hint" role="status">
        {{ n('loading') }}
      </p>
      <p v-if="productError || referenceError" class="context-error" role="alert">
        {{ referenceError || productError }}
      </p>
    </template>
    <p v-if="sale?.items_truncated" class="context-hint">{{ n('contextItemsLimited') }}</p>
  </fieldset>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import {
  notificationsAPI,
  type NotificationContext,
  type NotificationProductReference,
  type NotificationSaleDetail,
  type NotificationSaleSummary,
} from '@/services/notifications'
import { inventoryAPI } from '@/services/api'
import { notificationText as n } from '@/services/notificationText'
const props = withDefaults(
  defineProps<{
    modelValue?: NotificationContext | null
    token: string | null
    initialSale?: NotificationSaleDetail | null
    lockedSale?: boolean
    disabled?: boolean
  }>(),
  { initialSale: null, lockedSale: false, disabled: false },
)
const emit = defineEmits<{
  'update:modelValue': [value: NotificationContext | null]
  loaded: [sale: NotificationSaleDetail | null]
  selected: [sale: NotificationSaleSummary]
  validity: [message: string]
}>()
const search = ref(''),
  results = ref<NotificationSaleSummary[]>([]),
  sale = ref<NotificationSaleDetail | null>(null)
const searching = ref(false),
  loading = ref(false),
  searched = ref(false),
  hasMore = ref(false),
  error = ref('')
let searchEpoch = 0,
  loadEpoch = 0,
  timer: ReturnType<typeof setTimeout> | undefined
let searchController: AbortController | undefined, loadController: AbortController | undefined
const productSearch = ref(''),
  productResults = ref<NotificationProductReference[]>([]),
  reference = ref<NotificationProductReference | null>(null)
const productLoading = ref(false),
  productSearching = ref(false),
  productError = ref('')
const referenceError = ref('')
let productEpoch = 0,
  referenceEpoch = 0,
  productTimer: ReturnType<typeof setTimeout> | undefined
let productController: AbortController | undefined, referenceController: AbortController | undefined
const options = computed(() => {
  const values = [...results.value]
  if (sale.value && !values.some((item) => item.id === sale.value!.id)) values.unshift(sale.value)
  return values.map((item) => ({
    value: item.id,
    label: `#${item.code}`,
    description: item.seller_name || '—',
  }))
})
const productOptions = computed(() => {
  const unique = new Map<
    string,
    { value: string; label: string; description: string; disabled: boolean }
  >()
  for (const item of sale.value?.items || []) {
    const value = item.item_id || `unlinked:${item.id}`
    if (unique.has(value)) continue
    unique.set(value, {
      value,
      label: item.item_name,
      description: [
        item.size,
        item.color,
        !item.item_id ? n('contextAvulso') : !item.product_available ? n('contextUnavailable') : '',
      ]
        .filter(Boolean)
        .join(' · '),
      disabled: !item.item_id || !item.product_available,
    })
  }
  const extras = [...productResults.value]
  if (reference.value && !extras.some((item) => item.id === reference.value!.id))
    extras.unshift(reference.value)
  for (const item of extras)
    unique.set(item.id, {
      value: item.id,
      label: item.name,
      description: [item.size, item.color, item.inventory_code].filter(Boolean).join(' · '),
      disabled: false,
    })
  return [...unique.values()]
})
watch(
  () => [props.modelValue?.target, props.modelValue?.item_id, props.token, sale.value] as const,
  async ([target, id, token]) => {
    const own = ++referenceEpoch
    referenceController?.abort()
    productLoading.value = false
    referenceError.value = ''
    reference.value = null
    if (target !== 'product' || !id || !token) return
    const linked = sale.value?.items.find((item) => item.item_id === id && item.product_available)
    const selected = productResults.value.find((item) => item.id === id)
    if (linked || selected) {
      reference.value = selected || {
        id,
        name: linked!.item_name,
        size: linked!.size,
        color: linked!.color,
        inventory_code: null,
      }
      return
    }
    productLoading.value = true
    referenceController = new AbortController()
    try {
      const result = await notificationsAPI.contextProduct(id, token, referenceController.signal)
      if (own === referenceEpoch && token === props.token) reference.value = result
    } catch {
      if (own === referenceEpoch) referenceError.value = n('contextProductNeeded')
    } finally {
      if (own === referenceEpoch) productLoading.value = false
    }
  },
  { immediate: true },
)
watch(
  [productSearch, () => props.token, () => props.modelValue?.target],
  ([value, token, target]) => {
    const own = ++productEpoch
    clearTimeout(productTimer)
    productController?.abort()
    productSearching.value = false
    productResults.value = []
    if (target !== 'product' || !token || value.trim().length < 2 || props.disabled) return
    productTimer = setTimeout(async () => {
      productSearching.value = true
      productController = new AbortController()
      productError.value = ''
      try {
        const response = await inventoryAPI.getItems(
          { search: value.trim(), page_size: 20, include_images: false, status: 'active' },
          productController.signal,
        )
        if (own !== productEpoch || token !== props.token) return
        productResults.value = response.items
          .filter((item) => item.is_active)
          .map((item) => ({
            id: item.id,
            name: item.name,
            inventory_code: item.inventory_code || null,
            size: item.size || null,
            color: item.color || null,
          }))
      } catch {
        if (own === productEpoch) productError.value = n('error')
      } finally {
        if (own === productEpoch) productSearching.value = false
      }
    }, 250)
  },
)
watch(
  () =>
    props.modelValue?.target === 'product' && props.modelValue.item_id
      ? referenceError.value || (productLoading.value ? n('loading') : '')
      : '',
  (value) => emit('validity', value),
  { immediate: true, flush: 'sync' },
)
watch(
  () => [props.modelValue?.sale_id, props.token, props.initialSale] as const,
  async ([id, token]) => {
    const own = ++loadEpoch
    loadController?.abort()
    sale.value = null
    emit('loaded', null)
    error.value = ''
    loading.value = false
    if (!id || !token) return
    if (props.initialSale?.id === id) {
      sale.value = props.initialSale
      emit('loaded', sale.value)
      return
    }
    loading.value = true
    loadController = new AbortController()
    try {
      const result = await notificationsAPI.contextSale(id, token, loadController.signal)
      if (own !== loadEpoch || token !== props.token || id !== props.modelValue?.sale_id) return
      sale.value = result
      emit('loaded', result)
    } catch {
      if (own === loadEpoch) error.value = n('error')
    } finally {
      if (own === loadEpoch) loading.value = false
    }
  },
  { immediate: true },
)
watch([search, () => props.token], ([value, token]) => {
  const own = ++searchEpoch
  clearTimeout(timer)
  searchController?.abort()
  searching.value = false
  searched.value = false
  hasMore.value = false
  results.value = []
  if (!token || value.trim().length < 2 || props.disabled || props.lockedSale) return
  timer = setTimeout(async () => {
    searching.value = true
    error.value = ''
    searchController = new AbortController()
    try {
      const response = await notificationsAPI.contextSales(
        value.trim(),
        token,
        searchController.signal,
      )
      if (own !== searchEpoch || token !== props.token) return
      results.value = response.items
      hasMore.value = response.has_more
      searched.value = true
    } catch {
      if (own === searchEpoch) error.value = n('error')
    } finally {
      if (own === searchEpoch) searching.value = false
    }
  }, 250)
})
function chooseSale(id: string) {
  const selected =
    results.value.find((item) => item.id === id) || (sale.value?.id === id ? sale.value : null)
  emit('update:modelValue', { sale_id: id, target: props.modelValue?.target || 'sale' })
  if (selected) emit('selected', selected)
}
function chooseProduct(id: string) {
  if (props.modelValue)
    emit('update:modelValue', { ...props.modelValue, target: 'product', item_id: id })
}
onBeforeUnmount(() => {
  searchEpoch++
  loadEpoch++
  productEpoch++
  referenceEpoch++
  clearTimeout(timer)
  clearTimeout(productTimer)
  searchController?.abort()
  loadController?.abort()
  productController?.abort()
  referenceController?.abort()
})
</script>
<style scoped>
.notification-context {
  display: grid;
  gap: 10px;
  min-width: 0;
  border: 1px solid #dbe4ef;
  border-radius: 12px;
  padding: 14px;
  background: #f8fafc;
}
.notification-context legend {
  padding: 0 5px;
  font-size: 13px;
  font-weight: 650;
  color: #475569;
}
.notification-context label {
  display: grid;
  gap: 7px;
  color: #475569;
  font-size: 13px;
  font-weight: 600;
}
.notification-context input {
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  padding: 11px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #0f172a;
  font: inherit;
  font-weight: 400;
}
.context-summary {
  display: flex;
  align-items: center;
  gap: 8px 14px;
  flex-wrap: wrap;
  font-size: 13px;
  color: #475569;
}
.context-summary strong {
  color: #1d4ed8;
}
.context-summary button {
  margin-left: auto;
}
.context-hint {
  margin: 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.context-error {
  margin: 0;
  font-size: 13px;
  color: #b91c1c;
}
</style>
