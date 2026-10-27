<template>
  <Teleport to="body">
    <div v-if="open" class="product-link-backdrop erp-dialog-backdrop" @click.self="close">
      <section v-erp-dialog class="erp-dialog product-link-dialog" role="dialog" aria-modal="true" :aria-label="tr('Ficha do produto')">
        <header class="erp-dialog__header">
          <h2>{{ tr('Ficha do produto') }}</h2>
          <button data-dialog-close type="button" class="erp-button erp-button--secondary erp-button--icon" :aria-label="tr('Fechar')" @click="close">×</button>
        </header>
        <div class="erp-dialog__body">
          <p v-if="loading" role="status">{{ tr('Carregando produto...') }}</p>
          <div v-else-if="error" role="alert" class="product-link-error">
            <p>{{ tr(error) }}</p>
            <button v-if="validId" class="erp-button erp-button--secondary" @click="load">{{ tr('Tentar novamente') }}</button>
          </div>
          <template v-else-if="item">
            <h3>{{ item.name }}</h3>
            <p class="product-code">{{ item.inventory_code || item.sku_internal }}</p>
            <p v-if="!item.is_active" class="product-link-notice">{{ tr('Produto inativo') }}</p>
            <ProductGallery v-if="item.image_data || additional.length" :cover="item.image_data || ''" :additional="additional" expanded :loading="photosLoading" :load-error="photosError" @retry="loadPhotos" />
            <p v-else-if="photosLoading" role="status">{{ tr('Carregando fotos...') }}</p>
            <p v-else-if="photosError" role="alert">{{ tr('Não foi possível carregar as fotos.') }} <button class="erp-button erp-button--ghost erp-button--sm" @click="loadPhotos">{{ tr('Tentar novamente') }}</button></p>
            <p v-if="item.description" class="product-description">{{ item.description }}</p>
            <dl class="product-details">
              <div><dt>{{ tr('Marca') }}</dt><dd>{{ item.brand || '—' }}</dd></div>
              <div><dt>{{ tr('Categoria') }}</dt><dd>{{ item.category || '—' }}</dd></div>
              <div><dt>{{ tr('Tamanho') }}</dt><dd>{{ item.size || '—' }}</dd></div>
              <div><dt>{{ tr('Cor') }}</dt><dd>{{ item.color || '—' }}</dd></div>
              <div><dt>{{ tr('Preço de venda') }}</dt><dd>{{ price }}</dd></div>
              <div><dt>{{ tr('Código de barras') }}</dt><dd>{{ item.barcode || '—' }}</dd></div>
              <div><dt>{{ tr('Loja') }}</dt><dd>{{ displayStock(item.stock_loja) }}</dd></div>
              <div><dt>{{ tr('Depósito') }}</dt><dd>{{ displayStock(item.stock_deposito) }}</dd></div>
            </dl>
            <p v-if="!hasKnownStock(item)" class="product-link-notice">{{ tr('Há saldo desconhecido. Confira o estoque antes de movimentar.') }}</p>
          </template>
        </div>
        <footer class="erp-dialog__footer"><button class="erp-button erp-button--secondary" @click="close">{{ tr('Fechar') }}</button></footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { vErpDialog } from '@/directives/erpDialog'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import { displayStock, hasKnownStock } from '@/services/inventoryStock'
import ProductGallery from './ProductGallery.vue'
import { useInventoryI18n } from './i18n'

const route = useRoute(), router = useRouter(), auth = useAuthStore()
const { tr, numberLocale } = useInventoryI18n()
const item = ref<InventoryItem | null>(null), loading = ref(false), error = ref('')
const additional = ref<string[]>([]), photosLoading = ref(false), photosError = ref(false)
const requestedId = computed(() => typeof route.query.item_id === 'string' ? route.query.item_id : '')
const validId = computed(() => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(requestedId.value))
const open = computed(() => Object.hasOwn(route.query, 'item_id') && auth.isAuthenticated)
const identity = computed(() => JSON.stringify([auth.user?.id, auth.token, auth.userRole, auth.user?.sales_scope]))
const price = computed(() => {
  if (!item.value || !Number.isFinite(Number(item.value.sale_price)) || item.value.sale_price == null) return '—'
  const currency = item.value.sale_currency || item.value.currency || 'USD'
  return `${currency} ${Number(item.value.sale_price).toLocaleString(numberLocale(), { maximumFractionDigits: currency === 'PYG' ? 0 : 2 })}`
})
let generation = 0, photosGeneration = 0, controller: AbortController | undefined, photosController: AbortController | undefined

function reset() {
  generation++; photosGeneration++; controller?.abort(); photosController?.abort()
  item.value = null; additional.value = []; error.value = ''; loading.value = false; photosLoading.value = false; photosError.value = false
}
async function load() {
  reset()
  if (!open.value) return
  if (!validId.value) { error.value = 'O link do produto é inválido.'; return }
  const request = generation, id = requestedId.value, session = identity.value
  controller = new AbortController(); loading.value = true
  try {
    const result = await inventoryAPI.getItem(id, controller.signal)
    if (request !== generation || session !== identity.value || !open.value) return
    if (result.id.toLowerCase() !== id.toLowerCase()) throw new Error('unconfirmed_product')
    item.value = result
    void loadPhotos()
  } catch (cause) {
    if (request !== generation || session !== identity.value || !open.value) return
    const status = (cause as { response?: { status?: number } })?.response?.status
    error.value = status === 404 || status === 403 ? 'Este produto não está disponível para sua conta.' : 'Não foi possível carregar o produto. Tente novamente.'
  } finally { if (request === generation) loading.value = false }
}
async function loadPhotos() {
  if (!item.value || !open.value) return
  const request = ++photosGeneration, id = item.value.id, session = identity.value
  photosController?.abort(); photosController = new AbortController(); photosLoading.value = true; photosError.value = false
  try {
    const result = await inventoryAPI.getItemPhotos(id, photosController.signal)
    if (request === photosGeneration && session === identity.value && item.value?.id === id && open.value) additional.value = result.additional_images
  } catch {
    if (request === photosGeneration && session === identity.value && item.value?.id === id && open.value) photosError.value = true
  } finally { if (request === photosGeneration) photosLoading.value = false }
}
function close() {
  reset()
  const query = { ...route.query }; delete query.item_id
  void router.replace({ query })
}
watch([() => route.query.item_id, identity, open], () => { void load() }, { immediate: true, flush: 'sync' })
onUnmounted(reset)
</script>

<style scoped>
.product-link-backdrop{position:fixed;inset:0;z-index:12600;display:grid;place-items:center;padding:12px}
.product-link-dialog{width:min(680px,100%);max-height:calc(100dvh - 24px)}
.product-link-dialog h2{font-size:18px;margin:0}.product-link-dialog h3{font-size:20px;overflow-wrap:anywhere;margin:0 0 6px}
.product-code{font-size:12px;color:#64748b;overflow-wrap:anywhere}.product-description{white-space:pre-wrap;font-size:14px;line-height:1.6;overflow-wrap:anywhere}
.product-details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin:20px 0}.product-details dt{font-size:12px;color:#64748b}.product-details dd{margin:4px 0 0;font-size:14px;overflow-wrap:anywhere}
.product-link-error,.product-link-notice{padding:12px;border-radius:10px;background:#fff7ed;color:#9a3412;font-size:13px;line-height:1.5}
</style>
