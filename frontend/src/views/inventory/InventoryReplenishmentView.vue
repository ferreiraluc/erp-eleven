<template>
  <div class="replenishment-view">
    <ModuleHeader :title="t('title')">
      <button
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="$router.push('/inventory')"
      >
        {{ t('inventory') }}
      </button>
      <button
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="$router.push('/inventory/labels')"
      >
        {{ t('labels') }}
      </button>
    </ModuleHeader>
    <main class="replenishment-main">
      <p class="intro">{{ t('intro') }}</p>
      <div class="device-strip" :class="{ warning: !device || deviceError }">
        <Printer :size="18" aria-hidden="true" />
        <div>
          <strong>{{ deviceError ? t('deviceError') : device?.name || t('deviceMissing') }}</strong>
          <small v-if="device">{{ t(deviceConnected ? 'deviceOnline' : 'deviceOffline') }}</small>
          <small>{{ t('deviceHint') }}</small>
        </div>
      </div>
      <p v-if="error" class="notice error" role="alert">{{ error }}</p>
      <div v-if="attempt || invalidPending" class="notice warning" role="alert">
        <p>{{ t(invalidPending ? 'invalidPending' : 'pending') }}</p>
        <button
          v-if="attempt"
          type="button"
          class="erp-button erp-button--primary erp-button--sm"
          :disabled="busy"
          @click="reviewOpen = true"
        >
          {{ t('recover') }}
        </button>
        <button
          type="button"
          class="erp-button erp-button--secondary erp-button--sm"
          @click="$router.push('/inventory/labels')"
        >
          {{ t('queue') }}
        </button>
      </div>
      <section v-if="lastBatch" class="result-panel" aria-live="polite">
        <div class="section-heading">
          <div>
            <h2>{{ t('success') }}</h2>
            <p>{{ t('resultSummary', { units: lastBatch.total }) }}</p>
          </div>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="queueLoading"
            @click="refreshQueue"
          >
            {{ t('refresh') }}
          </button>
        </div>
        <div class="result-jobs">
          <div v-for="job in lastBatch.jobs" :key="job.id" class="result-job">
            <div>
              <strong>{{ job.name }}</strong
              ><small
                >{{ [job.color, job.size, job.code].filter(Boolean).join(' · ') }} ·
                {{ job.copies }}</small
              >
              <small v-if="job.diagnostic_message">{{ job.diagnostic_message }}</small>
            </div>
            <span class="job-status" :class="job.status">{{ jobStatus(job.status) }}</span>
          </div>
        </div>
        <p v-if="queueError" role="alert" class="error-text">{{ t('queueError') }}</p>
        <p>{{ t('printHint') }}</p>
        <button
          type="button"
          class="erp-button erp-button--ghost erp-button--sm"
          @click="$router.push('/inventory/labels')"
        >
          {{ t('queue') }} <ArrowUpRight :size="16" aria-hidden="true" />
        </button>
      </section>
      <section class="catalog-panel">
        <form class="search-row" @submit.prevent="search">
          <label class="search-input"
            ><Search :size="18" aria-hidden="true" />
            <input
              v-model="query"
              type="search"
              :placeholder="t('placeholder')"
              :aria-label="t('search')"
              :disabled="locked || busy || reviewOpen"
            />
          </label>
          <button
            type="submit"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="locked || busy || reviewOpen"
          >
            {{ t('find') }}
          </button>
          <button
            type="button"
            class="erp-button erp-button--ghost erp-button--icon"
            :aria-label="t('refresh')"
            :title="t('refresh')"
            :disabled="loading || locked || busy || reviewOpen"
            @click="refresh"
          >
            <RefreshCw :size="18" />
          </button>
        </form>
        <div class="selection-toolbar">
          <span role="status">{{ loading ? t('loading') : t('count', { count: total }) }}</span>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="!eligible.length || controlsDisabled"
            @click="selectPage"
          >
            {{ t('selectPage') }}
          </button>
          <button
            v-if="selectedIds.length"
            type="button"
            class="erp-button erp-button--ghost erp-button--sm"
            :disabled="controlsDisabled"
            @click="selectedIds = []"
          >
            {{ t('clear') }}
          </button>
        </div>
        <p class="selection-hint">{{ t('selectionHint') }}</p>
        <p v-if="loadError" class="notice error" role="alert">{{ t('loadError') }}</p>
        <p v-else-if="!loading && !items.length" class="empty-message">{{ t('empty') }}</p>
        <div class="product-list" :aria-busy="loading">
          <article
            v-for="item in items"
            :key="item.id"
            class="product-row"
            :class="{ blocked: !canReplenish(item), selected: selectedIds.includes(item.id) }"
          >
            <input
              type="checkbox"
              class="product-check"
              :checked="selectedIds.includes(item.id)"
              :aria-label="t('select', { name: item.name })"
              :disabled="controlsDisabled || !canReplenish(item)"
              @change="selectItem(item, ($event.target as HTMLInputElement).checked)"
            />
            <ProductThumbnail :item="item" :alt="item.name" class="product-photo" />
            <div class="product-identity">
              <strong>{{ item.name }}</strong>
              <div class="product-tags">
                <span v-if="item.size">{{ item.size }}</span
                ><span v-if="item.color">{{ item.color }}</span
                ><small v-if="item.brand">{{ item.brand }}</small>
              </div>
              <small
                >{{ item.inventory_code || '—'
                }}<template v-if="item.location"> · {{ item.location }}</template></small
              >
              <div class="stock-line">
                <span>{{ t('store') }}: {{ item.stock_loja ?? '—' }}</span
                ><strong>{{ t('warehouse') }}: {{ item.stock_deposito ?? '—' }}</strong>
              </div>
              <template v-if="!canReplenish(item)"
                ><p class="blocked-reason">{{ item.blocked_reason || t('blocked') }}</p>
                <button
                  type="button"
                  class="erp-button erp-button--ghost erp-button--sm"
                  @click="$router.push({ path: '/inventory', query: { item_id: item.id } })"
                >
                  {{ t('checkStock') }}
                </button></template
              >
            </div>
            <div v-if="canReplenish(item)" class="product-actions">
              <StockQuantityInput
                v-model="quantities[item.id]"
                :min="1"
                :max="Math.min(100, item.stock_deposito!)"
                always-show-buttons
                :aria-label="t('quantity', { name: item.name })"
                :disabled="controlsDisabled"
              />
              <button
                type="button"
                class="erp-button erp-button--primary erp-button--sm"
                :disabled="controlsDisabled || !device || deviceError || !validQuantity(item)"
                @click="openReview([item])"
              >
                <PackageCheck :size="17" aria-hidden="true" />{{ t('restocked') }}
              </button>
            </div>
          </article>
        </div>
        <div class="pagination">
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || locked || busy || reviewOpen || page <= 1"
            @click="changePage(-1)"
          >
            {{ t('previous') }}
          </button>
          <span>{{ t('page', { page, pages }) }}</span>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || locked || busy || reviewOpen || page >= pages"
            @click="changePage(1)"
          >
            {{ t('next') }}
          </button>
        </div>
      </section>
      <div v-if="selectedIds.length && !reviewOpen" class="selection-footer">
        <div>
          <strong>{{ t('selected', { count: selectedIds.length }) }}</strong
          ><small>{{ t('totals', { products: selectedIds.length, units: selectedUnits }) }}</small>
        </div>
        <button
          type="button"
          class="erp-button erp-button--primary"
          :disabled="controlsDisabled || !device || deviceError"
          @click="openReview(selectedProducts)"
        >
          {{ t('restockSelected') }}
        </button>
      </div>
    </main>
    <Teleport to="body">
      <div
        v-if="reviewOpen"
        class="erp-dialog-backdrop replenishment-backdrop"
        @click.self="closeReview"
      >
        <section v-erp-dialog class="erp-dialog replenishment-dialog">
          <header class="erp-dialog__header">
            <h2>{{ t('review') }}</h2>
            <button
              data-dialog-close
              type="button"
              class="erp-button erp-button--ghost erp-button--icon"
              :aria-label="t('close')"
              :disabled="busy"
              @click="closeReview"
            >
              ×
            </button>
          </header>
          <div class="erp-dialog__body">
            <div class="review-summary">
              <strong>{{ t('direction') }}</strong
              ><span>{{ t('totals', { products: reviewRows.length, units: reviewUnits }) }}</span>
            </div>
            <p class="review-hint">{{ t(attempt ? 'original' : 'reviewHint') }}</p>
            <p v-if="error" class="notice error" role="alert">{{ error }}</p>
            <p v-if="attempt" class="notice warning" role="alert">{{ t('pending') }}</p>
            <div class="review-products">
              <div v-for="item in reviewRows" :key="item.id" class="review-product">
                <div>
                  <strong>{{ item.name }}</strong
                  ><small>{{
                    [item.color, item.size, item.inventory_code].filter(Boolean).join(' · ')
                  }}</small>
                </div>
                <strong>× {{ item.copies }}</strong>
              </div>
            </div>
            <template v-if="!attempt">
              <p v-if="layoutError" class="notice error" role="alert">{{ t('layoutError') }}</p>
              <ErpDropdown
                v-model="selectedLayoutId"
                :options="layoutOptions"
                :label="t('layout')"
                :disabled="busy || layoutError"
              />
              <ErpDropdown
                v-if="reviewRows.length > 1"
                v-model="previewItemId"
                :options="previewOptions"
                :label="t('previewProduct')"
                :disabled="busy"
              />
              <div class="label-preview">
                <img v-if="previewUrl" :src="previewUrl" :alt="t('previewAlt')" />
                <p v-else role="status">
                  {{ t(previewError ? 'previewError' : 'previewLoading') }}
                </p>
              </div>
              <button
                v-if="previewError || layoutError"
                type="button"
                class="erp-button erp-button--secondary erp-button--sm"
                :disabled="busy"
                @click="retryPreview"
              >
                {{ t('retryPreview') }}
              </button>
              <label class="confirmation-line"
                ><input
                  v-model="confirmed"
                  type="checkbox"
                  :disabled="busy || !previewUrl || layoutError"
                />{{ t('confirmed') }}</label
              >
            </template>
          </div>
          <footer class="erp-dialog__footer">
            <button
              type="button"
              class="erp-button erp-button--secondary"
              :disabled="busy"
              @click="closeReview"
            >
              {{ t('cancel') }}
            </button>
            <button
              type="button"
              class="erp-button erp-button--primary"
              :disabled="
                busy ||
                (!attempt && (!confirmed || !previewUrl || layoutError || !device || deviceError))
              "
              @click="submit"
            >
              <Printer :size="18" aria-hidden="true" />{{
                t(busy ? 'saving' : attempt ? 'recover' : 'confirm')
              }}
            </button>
          </footer>
        </section>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch, type WatchStopHandle } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowUpRight, PackageCheck, Printer, RefreshCw, Search } from 'lucide-vue-next'
import ModuleHeader from '@/components/ModuleHeader.vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import ProductThumbnail from '@/components/inventory/ProductThumbnail.vue'
import StockQuantityInput from '@/components/inventory/StockQuantityInput.vue'
import { replenishmentMessages } from '@/components/inventory/replenishmentMessages'
import { vErpDialog } from '@/directives/erpDialog'
import { useAuthStore } from '@/stores/auth'
import { productLabels, type LabelBatch, type LabelDevice } from '@/services/productLabels'
import { labelLayoutReference, type ProductLabelLayout } from '@/services/productLabelDesign'
import {
  inventoryReplenishment,
  canReplenish,
  replenishmentRequest,
  restoreReplenishmentRequest,
  type ReplenishmentProduct,
  type ReplenishmentRequest,
} from '@/services/inventoryReplenishment'

const { t } = useI18n({ useScope: 'local', messages: replenishmentMessages })
const auth = useAuthStore()
const items = ref<ReplenishmentProduct[]>([]),
  query = ref(''),
  appliedQuery = ref(''),
  page = ref(1),
  total = ref(0),
  pageSize = ref(40)
const quantities = ref<Record<string, number>>({}),
  selectedIds = ref<string[]>([])
const device = ref<LabelDevice | null>(null),
  deviceError = ref(false),
  loading = ref(false),
  loadError = ref(false),
  busy = ref(false),
  error = ref('')
const layouts = ref<ProductLabelLayout[]>([]),
  selectedLayoutId = ref('standard'),
  layoutError = ref(false)
const reviewOpen = ref(false),
  confirmed = ref(false),
  reviewRows = ref<(ReplenishmentProduct & { copies: number })[]>([])
const previewItemId = ref(''),
  previewUrl = ref(''),
  previewError = ref(false)
const attempt = ref<ReplenishmentRequest | null>(null),
  invalidPending = ref(false)
const lastBatch = ref<LabelBatch | null>(null),
  lastBatchId = ref(''),
  queueLoading = ref(false),
  queueError = ref(false)
const storageKey = computed(() => `eleven-replenishment-confirmation:${auth.user?.id || ''}`)
const resultKey = computed(() => `eleven-replenishment-result:${auth.user?.id || ''}`)
const layoutKey = computed(() => `eleven-label-layout:${auth.user?.id || ''}`)
const locked = computed(() => !!attempt.value || invalidPending.value)
const controlsDisabled = computed(
  () => locked.value || busy.value || loading.value || loadError.value || reviewOpen.value,
)
const eligible = computed(() => items.value.filter(canReplenish))
const selectedProducts = computed(() =>
  items.value.filter((item) => selectedIds.value.includes(item.id)),
)
const selectedUnits = computed(() =>
  selectedProducts.value.reduce((sum, item) => sum + (Number(quantities.value[item.id]) || 0), 0),
)
const reviewUnits = computed(() => reviewRows.value.reduce((sum, item) => sum + item.copies, 0))
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const activeLayout = computed(() =>
  layouts.value.find((layout) => layout.id === selectedLayoutId.value),
)
const layoutOptions = computed(() =>
  layouts.value.map((layout) => ({
    value: layout.id,
    label: layout.builtin ? t('standard') : layout.name,
  })),
)
const previewOptions = computed(() =>
  reviewRows.value.map((item) => ({
    value: item.id,
    label: [item.name, item.color, item.size].filter(Boolean).join(' · '),
  })),
)
const deviceConnected = computed(
  () =>
    !!device.value?.last_seen_at &&
    Date.now() - new Date(device.value.last_seen_at).getTime() < 120000,
)
let disposed = false,
  epoch = 0,
  listGeneration = 0,
  previewGeneration = 0,
  queueGeneration = 0,
  lastLoadedAt = 0
let listController: AbortController | undefined, stopUserWatch: WatchStopHandle | undefined
function current(ownerEpoch: number) {
  return !disposed && ownerEpoch === epoch
}

function validQuantity(item: ReplenishmentProduct) {
  const quantity = quantities.value[item.id]
  return (
    Number.isInteger(quantity) &&
    quantity >= 1 &&
    quantity <= Math.min(100, item.stock_deposito ?? 0)
  )
}
function selectItem(item: ReplenishmentProduct, checked: boolean) {
  if (controlsDisabled.value || !canReplenish(item)) return
  selectedIds.value = checked
    ? [...new Set([...selectedIds.value, item.id])]
    : selectedIds.value.filter((id) => id !== item.id)
}
function selectPage() {
  if (!controlsDisabled.value) selectedIds.value = eligible.value.map((item) => item.id)
}

async function loadCatalog() {
  const ownerEpoch = epoch,
    request = ++listGeneration
  listController?.abort()
  listController = new AbortController()
  loading.value = true
  loadError.value = false
  selectedIds.value = []
  try {
    const result = await inventoryReplenishment.list(
      appliedQuery.value,
      page.value,
      listController.signal,
    )
    if (!current(ownerEpoch) || request !== listGeneration) return
    // An operation may remove the last row of the last page.
    const finalPage = Math.max(1, Math.ceil(result.total / result.page_size))
    if (page.value > finalPage) {
      page.value = finalPage
      await loadCatalog()
      return
    }
    items.value = result.items
    total.value = result.total
    pageSize.value = result.page_size
    quantities.value = Object.fromEntries(result.items.map((item) => [item.id, 1]))
    lastLoadedAt = Date.now()
  } catch {
    if (current(ownerEpoch) && request === listGeneration) loadError.value = true
  } finally {
    if (current(ownerEpoch) && request === listGeneration) loading.value = false
  }
}
async function loadDevice() {
  const ownerEpoch = epoch
  try {
    const result = await productLabels.device()
    if (current(ownerEpoch)) {
      device.value = result.device
      deviceError.value = false
    }
  } catch {
    if (current(ownerEpoch)) deviceError.value = true
  }
}
async function loadLayouts() {
  const ownerEpoch = epoch
  try {
    const result = await productLabels.layouts()
    if (!current(ownerEpoch)) return
    layouts.value = result
    layoutError.value = !result.length
    if (!attempt.value && !result.some((layout) => layout.id === selectedLayoutId.value))
      selectedLayoutId.value = 'standard'
  } catch {
    if (current(ownerEpoch)) layoutError.value = true
  }
}
function search() {
  if (locked.value || busy.value || reviewOpen.value) return
  appliedQuery.value = query.value.trim()
  page.value = 1
  void loadCatalog()
}
function changePage(delta: number) {
  if (!loading.value && !locked.value && !busy.value && !reviewOpen.value) {
    page.value += delta
    void loadCatalog()
  }
}
function refresh() {
  if (loading.value || locked.value || busy.value || reviewOpen.value) return
  void Promise.allSettled([loadCatalog(), loadDevice(), loadLayouts()])
}
function onFocus() {
  if (
    document.visibilityState === 'visible' &&
    !selectedIds.value.length &&
    !Object.values(quantities.value).some((quantity) => quantity !== 1) &&
    Date.now() - lastLoadedAt > 30000
  )
    refresh()
}

function openReview(rows: ReplenishmentProduct[]) {
  if (controlsDisabled.value || !device.value || deviceError.value) return
  error.value = ''
  confirmed.value = false
  try {
    const selection = rows.map((item) => ({ ...item, copies: quantities.value[item.id] }))
    replenishmentRequest(selection, 'validation', activeLayout.value)
    reviewRows.value = selection
    previewItemId.value = selection[0].id
    reviewOpen.value = true
  } catch {
    error.value = t('limits')
  }
}
function clearPreview() {
  previewGeneration++
  if (previewUrl.value) URL.revokeObjectURL(previewUrl.value)
  previewUrl.value = ''
  previewError.value = false
}
function closeReview() {
  if (!busy.value) {
    reviewOpen.value = false
    confirmed.value = false
    clearPreview()
  }
}
async function loadPreview() {
  clearPreview()
  confirmed.value = false
  if (
    !reviewOpen.value ||
    attempt.value ||
    !previewItemId.value ||
    !activeLayout.value ||
    layoutError.value
  )
    return
  const request = previewGeneration,
    ownerEpoch = epoch
  try {
    const blob = await productLabels.preview(
      previewItemId.value,
      labelLayoutReference(activeLayout.value),
    )
    if (current(ownerEpoch) && request === previewGeneration && reviewOpen.value)
      previewUrl.value = URL.createObjectURL(blob)
  } catch {
    if (current(ownerEpoch) && request === previewGeneration) previewError.value = true
  }
}
async function retryPreview() {
  if (layoutError.value) await loadLayouts()
  await loadPreview()
}
watch(
  () => [
    reviewOpen.value,
    previewItemId.value,
    selectedLayoutId.value,
    activeLayout.value?.version,
    layoutError.value,
  ],
  () => {
    void loadPreview()
  },
)
watch(selectedLayoutId, (value) => {
  if (!attempt.value) {
    try {
      localStorage.setItem(layoutKey.value, value)
    } catch {
      /* Preference only. */
    }
  }
})

async function submit() {
  if (
    busy.value ||
    invalidPending.value ||
    (!attempt.value &&
      (!confirmed.value ||
        !previewUrl.value ||
        layoutError.value ||
        !activeLayout.value ||
        !device.value ||
        deviceError.value))
  )
    return
  const ownerEpoch = epoch,
    key = storageKey.value,
    successKey = resultKey.value
  busy.value = true
  error.value = ''
  if (!attempt.value) {
    try {
      const body = replenishmentRequest(reviewRows.value, crypto.randomUUID(), activeLayout.value)
      // The durable local copy must exist before the first network request.
      sessionStorage.setItem(key, JSON.stringify(body))
      attempt.value = body
    } catch {
      error.value = t('storageError')
      busy.value = false
      return
    }
  }
  const body = attempt.value!
  try {
    const result = await inventoryReplenishment.confirm(body)
    if (!current(ownerEpoch)) return
    // Commit the visible result before any secondary refresh can fail.
    lastBatch.value = result
    lastBatchId.value = result.id
    queueError.value = false
    try {
      sessionStorage.setItem(
        successKey,
        JSON.stringify({ id: result.id, request_key: result.request_key }),
      )
      sessionStorage.removeItem(key)
    } catch {
      /* Replaying the same request remains safe. */
    }
    attempt.value = null
    confirmed.value = false
    reviewOpen.value = false
    selectedIds.value = []
    clearPreview()
    await loadCatalog()
  } catch (cause) {
    if (!current(ownerEpoch)) return
    const response = (cause as { response?: { status?: number; data?: { detail?: unknown } } })
      .response
    if (response?.status === 409 || response?.status === 422) {
      try {
        sessionStorage.removeItem(key)
      } catch {
        /* Keep a blocking marker if storage cannot be cleared. */
      }
      attempt.value = null
      confirmed.value = false
      reviewOpen.value = false
      clearPreview()
      error.value = typeof response.data?.detail === 'string' ? response.data.detail : t('conflict')
      await loadCatalog()
      await loadLayouts()
    } else error.value = t('failure')
  } finally {
    if (current(ownerEpoch)) busy.value = false
  }
}

function jobStatus(status: string) {
  const key = (
    {
      pending: 'pendingStatus',
      claimed: 'claimed',
      submitted: 'submitted',
      uncertain: 'uncertain',
      failed: 'failed',
      cancelled: 'cancelled',
    } as Record<string, string>
  )[status]
  return key ? t(key) : status
}
async function refreshQueue() {
  if (!lastBatchId.value) return
  const ownerEpoch = epoch,
    request = ++queueGeneration
  queueLoading.value = true
  queueError.value = false
  try {
    const result = await productLabels.batch(lastBatchId.value)
    if (current(ownerEpoch) && request === queueGeneration) lastBatch.value = result
  } catch {
    if (current(ownerEpoch) && request === queueGeneration) queueError.value = true
  } finally {
    if (current(ownerEpoch) && request === queueGeneration) queueLoading.value = false
  }
}
async function initialize(userId: string | undefined) {
  epoch++
  listGeneration++
  queueGeneration++
  listController?.abort()
  clearPreview()
  items.value = []
  selectedIds.value = []
  quantities.value = {}
  reviewRows.value = []
  attempt.value = null
  invalidPending.value = false
  reviewOpen.value = false
  confirmed.value = false
  lastBatch.value = null
  lastBatchId.value = ''
  queueError.value = false
  queueLoading.value = false
  device.value = null
  deviceError.value = false
  layouts.value = []
  layoutError.value = false
  error.value = ''
  busy.value = false
  loading.value = false
  loadError.value = false
  query.value = ''
  appliedQuery.value = ''
  page.value = 1
  total.value = 0
  selectedLayoutId.value = 'standard'
  if (!userId) return
  try {
    const saved = sessionStorage.getItem(storageKey.value)
    if (saved) {
      attempt.value = restoreReplenishmentRequest(saved)
      reviewRows.value = attempt.value.items.map((item) => ({
        id: item.item_id,
        name: item.name,
        inventory_code: item.code,
        color: item.color,
        size: item.size,
        copies: item.copies,
        stock_loja: item.expected_stock_loja,
        stock_deposito: item.expected_stock_deposito,
        current_stock: item.expected_current_stock,
        sale_price: item.sale_price,
        sale_currency: item.sale_currency,
        group_key: null,
        brand: null,
        location: null,
        has_image: false,
        updated_at: '',
        blocked_reason: null,
      }))
      reviewOpen.value = true
    }
  } catch {
    invalidPending.value = true
  }
  try {
    selectedLayoutId.value =
      attempt.value?.layout_id || localStorage.getItem(layoutKey.value) || 'standard'
    const savedResult = JSON.parse(sessionStorage.getItem(resultKey.value) || 'null') as {
      id?: string
      request_key?: string
    } | null
    if (typeof savedResult?.id === 'string') {
      lastBatchId.value = savedResult.id
      // A successful response saved before a storage cleanup failure is conclusive.
      if (attempt.value?.request_key === savedResult.request_key) {
        attempt.value = null
        reviewOpen.value = false
        sessionStorage.removeItem(storageKey.value)
      }
      void refreshQueue()
    }
  } catch {
    /* A previous successful batch is optional. */
  }
  await Promise.allSettled([loadCatalog(), loadDevice(), loadLayouts()])
}
onMounted(() => {
  stopUserWatch = watch(
    () => auth.user?.id,
    (id) => {
      void initialize(id)
    },
    { immediate: true },
  )
  window.addEventListener('focus', onFocus)
  document.addEventListener('visibilitychange', onFocus)
})
onUnmounted(() => {
  disposed = true
  epoch++
  listController?.abort()
  stopUserWatch?.()
  clearPreview()
  window.removeEventListener('focus', onFocus)
  document.removeEventListener('visibilitychange', onFocus)
})
</script>

<style scoped>
.replenishment-view {
  min-height: 100dvh;
  background: #f6f8fb;
  color: #1e293b;
}
.replenishment-main {
  max-width: 1120px;
  margin: auto;
  padding: 0 16px 32px;
}
.intro,
.selection-hint,
.review-hint {
  font-size: 13px;
  line-height: 1.5;
  color: #64748b;
}
.device-strip {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px 15px;
  border: 1px solid #dbeafe;
  border-radius: 14px;
  background: #eff6ff;
  font-size: 13px;
}
.device-strip > svg {
  flex-shrink: 0;
}
.device-strip small {
  display: block;
  color: #64748b;
  margin-top: 3px;
}
.catalog-panel,
.result-panel {
  margin-top: 16px;
  padding: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  background: #fff;
}
.search-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.search-input {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid #cbd5e1;
  border-radius: 12px;
  padding: 9px 12px;
  color: #64748b;
}
.search-input input {
  width: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
  outline: 0;
  font-size: 16px;
  color: #1e293b;
}
.selection-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
  font-size: 13px;
}
.selection-toolbar > span {
  margin-right: auto;
}
.selection-hint {
  font-size: 12px;
  margin: 8px 0 14px;
}
.product-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.product-row {
  display: grid;
  grid-template-columns: 20px 76px minmax(0, 1fr) 160px;
  align-items: center;
  gap: 14px;
  padding: 14px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
}
.product-row.selected {
  border-color: #93c5fd;
  background: #f8fbff;
}
.product-row.blocked {
  background: #fffbeb;
}
.product-check {
  width: 18px;
  height: 18px;
  accent-color: #2563eb;
}
.product-photo {
  width: 76px;
  height: 80px;
  object-fit: contain;
  border: 1px solid #f1f5f9;
  border-radius: 10px;
  background: white;
}
.product-identity {
  min-width: 0;
}
.product-identity > strong {
  display: block;
  font-size: 14px;
  overflow-wrap: anywhere;
}
.product-identity > small {
  display: block;
  color: #64748b;
  font-size: 12px;
  overflow-wrap: anywhere;
  margin-top: 4px;
}
.product-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 5px;
  font-size: 12px;
}
.product-tags span {
  padding: 2px 6px;
  border-radius: 5px;
  background: #f1f5f9;
  color: #475569;
}
.product-tags small {
  color: #64748b;
}
.stock-line {
  display: flex;
  gap: 12px;
  font-size: 12px;
  margin-top: 7px;
  color: #64748b;
}
.stock-line strong {
  color: #047857;
}
.product-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.product-actions > button {
  justify-content: center;
}
.blocked-reason {
  font-size: 12px;
  line-height: 1.4;
  color: #92400e;
}
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 14px;
  margin-top: 20px;
  font-size: 12px;
}
.empty-message {
  padding: 28px 8px;
  text-align: center;
  color: #64748b;
}
.notice {
  padding: 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  margin: 12px 0;
}
.notice p {
  margin: 0 0 8px;
}
.notice button + button {
  margin-left: 6px;
}
.error {
  background: #fef2f2;
  color: #b91c1c;
  border: 1px solid #fecaca;
}
.warning {
  background: #fffbeb;
  color: #92400e;
  border-color: #fde68a;
}
.selection-footer {
  position: sticky;
  bottom: 10px;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  padding: 12px 16px;
  border: 1px solid #bfdbfe;
  border-radius: 15px;
  background: #eff6ff;
  box-shadow: 0 6px 20px #0f172a12;
}
.selection-footer strong {
  font-size: 13px;
}
.selection-footer small {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}
.section-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.section-heading h2 {
  font-size: 16px;
  line-height: 1.5;
  margin: 0;
  color: #047857;
}
.result-panel p {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.result-jobs {
  max-height: 240px;
  overflow: auto;
}
.result-job {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f1f5f9;
  font-size: 12px;
}
.result-job > div {
  min-width: 0;
}
.result-job strong {
  overflow-wrap: anywhere;
}
.result-job small {
  display: block;
  margin-top: 3px;
  color: #64748b;
}
.job-status {
  flex-shrink: 0;
  padding: 4px 8px;
  border-radius: 999px;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 11px;
}
.job-status.submitted {
  background: #ecfdf5;
  color: #047857;
}
.job-status.uncertain,
.job-status.failed {
  background: #fffbeb;
  color: #92400e;
}
.job-status.cancelled {
  background: #f1f5f9;
  color: #64748b;
}
.result-panel .error-text {
  color: #b91c1c;
}
.replenishment-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.review-summary {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 13px;
}
.review-summary > strong {
  color: #1d4ed8;
}
.review-hint {
  font-size: 12px;
}
.review-products {
  max-height: 180px;
  overflow: auto;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  margin: 12px 0;
}
.review-product {
  display: flex;
  gap: 12px;
  align-items: center;
  justify-content: space-between;
  padding: 9px 12px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 12px;
}
.review-product > div {
  min-width: 0;
}
.review-product strong {
  overflow-wrap: anywhere;
}
.review-product > strong {
  flex-shrink: 0;
}
.review-product small {
  display: block;
  color: #64748b;
  margin-top: 3px;
}
.replenishment-dialog :deep(.erp-dropdown) {
  margin-top: 10px;
}
.label-preview {
  min-height: 120px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #f8fafc;
  padding: 14px;
  margin: 12px 0;
}
.label-preview img {
  width: min(100%, 360px);
  height: auto;
  image-rendering: auto;
  background: white;
  box-shadow: 0 2px 8px #0f172a12;
}
.label-preview p {
  font-size: 13px;
  color: #64748b;
}
.confirmation-line {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 13px;
  line-height: 1.5;
  margin-top: 14px;
}
.confirmation-line input {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  accent-color: #2563eb;
  margin-top: 2px;
}
@media (max-width: 600px) {
  .replenishment-main {
    padding: 0 10px 20px;
  }
  .catalog-panel,
  .result-panel {
    padding: 12px;
  }
  .device-strip {
    align-items: flex-start;
    padding: 10px;
  }
  .product-row {
    grid-template-columns: 18px 60px minmax(0, 1fr);
    gap: 9px;
    padding: 10px;
  }
  .product-photo {
    width: 60px;
    height: 70px;
  }
  .product-actions {
    grid-column: 2 / 4;
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(90px, 1fr);
    align-items: center;
    gap: 10px;
  }
  .product-identity > strong {
    font-size: 13px;
  }
  .stock-line {
    gap: 8px;
  }
  .selection-footer {
    align-items: stretch;
    flex-direction: column;
    padding: 10px 12px;
  }
  .selection-footer > div {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .selection-footer small {
    margin: 0;
  }
  .selection-footer > button {
    justify-content: center;
  }
  .result-job {
    align-items: flex-start;
  }
  .job-status {
    max-width: 110px;
    white-space: normal;
    text-align: center;
  }
  .replenishment-dialog .erp-dialog__footer {
    display: grid;
    grid-template-columns: 1fr;
  }
  .replenishment-dialog .erp-dialog__footer > button {
    justify-content: center;
  }
  .replenishment-dialog .erp-dialog__footer > button:first-child {
    order: 2;
  }
}
</style>
