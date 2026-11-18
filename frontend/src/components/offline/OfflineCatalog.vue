<template>
  <section class="offline-catalog" aria-labelledby="offline-catalog-title">
    <div class="offline-catalog__content">
      <header class="offline-catalog__header">
        <div>
          <span class="offline-catalog__brand">ELEVEN</span>
          <h1 id="offline-catalog-title">{{ text('title') }}</h1>
          <p v-if="userName" class="offline-catalog__user">{{ userName }}</p>
        </div>
        <div class="offline-catalog__actions">
          <button class="erp-button erp-button--secondary erp-button--sm" :disabled="loading" @click="emit('retry')">
            <RefreshCw :size="16" :class="{ spinning: loading }" aria-hidden="true" />
            {{ text(loading ? 'connecting' : 'connect') }}
          </button>
          <button class="erp-button erp-button--ghost erp-button--icon" :aria-label="text('logout')" @click="emit('logout')">
            <LogOut :size="19" aria-hidden="true" />
          </button>
        </div>
      </header>

      <section class="offline-catalog__notice" aria-live="polite">
        <WifiOff :size="19" aria-hidden="true" />
        <div>
          <strong>{{ text('offline') }}</strong>
          <p>{{ text('snapshotWarning') }}</p>
          <p class="offline-catalog__sync">{{ text('savedAt') }}: <time v-if="syncedAt" :datetime="new Date(syncedAt).toISOString()">{{ dateText(syncedAt) }}</time><span v-else>{{ text('notSaved') }}</span></p>
        </div>
      </section>

      <form class="offline-catalog__search" role="search" @submit.prevent="searchNow(true)">
        <label class="offline-catalog__query">
          <Search :size="20" aria-hidden="true" />
          <span class="sr-only">{{ text('searchLabel') }}</span>
          <input v-model="query" data-testid="offline-query" type="search" :placeholder="text('searchPlaceholder')" maxlength="160" autocomplete="off" />
        </label>
        <button type="button" class="erp-button erp-button--primary erp-button--icon" :aria-label="text('scan')" @click="showScanner = true">
          <ScanLine :size="21" aria-hidden="true" />
        </button>
        <button type="button" class="erp-button erp-button--secondary erp-button--icon" :aria-label="text('filters')" :aria-expanded="showFilters" aria-controls="offline-catalog-filters" @click="showFilters = !showFilters">
          <SlidersHorizontal :size="20" aria-hidden="true" />
          <span v-if="filterCount" class="offline-catalog__filter-count">{{ filterCount }}</span>
        </button>
      </form>

      <section v-if="showFilters" id="offline-catalog-filters" class="offline-catalog__filters" :aria-label="text('filters')">
        <label>{{ text('brand') }}<ErpSelect v-model="filters.brand" :label="text('brand')"><option value="">{{ text('all') }}</option><option v-for="value in facets.brands" :key="value" :value="value">{{ value }}</option></ErpSelect></label>
        <label>{{ text('category') }}<ErpSelect v-model="filters.category" :label="text('category')"><option value="">{{ text('all') }}</option><option value="__uncategorized__">{{ text('uncategorized') }}</option><option v-for="value in facets.categories" :key="value" :value="value">{{ value }}</option></ErpSelect></label>
        <label>{{ text('color') }}<ErpSelect v-model="filters.color" :label="text('color')"><option value="">{{ text('all') }}</option><option v-for="value in facets.colors" :key="value" :value="value">{{ value }}</option></ErpSelect></label>
        <label>{{ text('size') }}<ErpSelect v-model="filters.size" :label="text('size')"><option value="">{{ text('all') }}</option><option v-for="value in facets.sizes" :key="value" :value="value">{{ value }}</option></ErpSelect></label>
        <label>{{ text('status') }}<ErpSelect v-model="filters.status" :label="text('status')"><option value="">{{ text('all') }}</option><option value="active">{{ text('active') }}</option><option value="inactive">{{ text('inactive') }}</option><option value="out">{{ text('out') }}</option><option value="low">{{ text('low') }}</option><option value="excess">{{ text('excess') }}</option></ErpSelect></label>
        <label>{{ text('location') }}<ErpSelect v-model="filters.location_stock" :label="text('location')"><option value="">{{ text('all') }}</option><option value="loja">{{ text('store') }}</option><option value="deposito">{{ text('warehouse') }}</option></ErpSelect></label>
        <button type="button" class="erp-button erp-button--ghost erp-button--sm" :disabled="!filterCount && !query" @click="clearSearch">{{ text('clear') }}</button>
        <small v-if="facetsFailed">{{ text('filtersUnavailable') }}</small>
      </section>

      <div class="offline-catalog__results" role="status" aria-live="polite">
        <span v-if="searching">{{ text('searching') }}</span>
        <span v-else-if="!searchFailed">{{ total.toLocaleString(uiLocale()) }} {{ text('products') }}</span>
        <span>{{ text('readOnly') }}</span>
      </div>

      <div v-if="searchFailed" class="offline-catalog__empty" role="alert">
        <Package :size="32" aria-hidden="true" /><h2>{{ text('loadFailed') }}</h2><p>{{ text('tryConnection') }}</p>
        <button class="erp-button erp-button--secondary" @click="searchNow()">{{ text('retryLocal') }}</button>
      </div>
      <div v-else-if="!searching && !items.length" class="offline-catalog__empty">
        <Package :size="32" aria-hidden="true" />
        <h2>{{ text(syncedAt ? 'noResults' : 'noSnapshot') }}</h2>
        <p>{{ text(syncedAt ? 'changeSearch' : 'prepareOnline') }}</p>
        <button v-if="query || filterCount" class="erp-button erp-button--secondary" @click="clearSearch">{{ text('clear') }}</button>
      </div>

      <section v-else class="offline-catalog__grid" :aria-busy="searching" :aria-label="text('products')">
        <article v-for="item in items" :key="item.id" class="offline-product" :data-product-id="item.id">
          <button class="offline-product__photo" :aria-label="`${text('details')}: ${item.name}`" :aria-expanded="expandedId === item.id" :aria-controls="`offline-details-${item.id}`" @click="toggleDetails(item.id)">
            <img v-if="thumbnails[item.id]" :src="thumbnails[item.id]!" :alt="item.name" loading="lazy" decoding="async" @error="thumbnails[item.id] = null" />
            <Package v-else :size="32" aria-hidden="true" />
            <span v-if="!item.is_active" class="offline-product__inactive">{{ text('inactive') }}</span>
          </button>
          <div class="offline-product__body">
            <p class="offline-product__code">{{ item.inventory_code || item.sku_internal }}</p>
            <h2>{{ item.name }}</h2>
            <p class="offline-product__variant">{{ [item.color, item.size].filter(Boolean).join(' · ') || item.brand || '—' }}</p>
            <strong class="offline-product__price">{{ priceText(item) }}</strong>
            <p v-if="!item.stock_confirmed" class="offline-product__unconfirmed">{{ text('unconfirmed') }}</p>
            <p class="offline-product__stock" :aria-label="`${text('store')}: ${stockText(item, 'stock_loja')}; ${text('warehouse')}: ${stockText(item, 'stock_deposito')}`"><span :class="{ 'negative-stock': item.stock_confirmed && Number(item.stock_loja) < 0 }">{{ stockText(item, 'stock_loja') }} L</span><span aria-hidden="true">|</span><span :class="{ 'negative-stock': item.stock_confirmed && Number(item.stock_deposito) < 0 }">{{ stockText(item, 'stock_deposito') }} D</span></p>
            <p class="offline-product__availability">{{ text('available') }}: {{ stockText(item, 'available_stock') }}<br />{{ text('reserved') }}: {{ reservedTotal(item) }}</p>
            <button class="erp-button erp-button--ghost erp-button--sm offline-product__details-toggle" :aria-expanded="expandedId === item.id" :aria-controls="`offline-details-${item.id}`" @click="toggleDetails(item.id)">{{ text('details') }}<ChevronDown :size="17" :class="{ rotated: expandedId === item.id }" aria-hidden="true" /></button>
          </div>
          <div v-if="expandedId === item.id" :id="`offline-details-${item.id}`" class="offline-product__details">
            <img v-if="thumbnails[item.id]" :src="thumbnails[item.id]!" :alt="item.name" decoding="async" @error="thumbnails[item.id] = null" />
            <p v-if="thumbnails[item.id]" class="offline-product__thumbnail-note">{{ text('savedThumbnail') }}</p>
            <dl><template v-for="entry in details(item)" :key="entry.label"><dt>{{ entry.label }}</dt><dd>{{ entry.value }}</dd></template></dl>
            <p v-if="item.description" class="offline-product__description">{{ item.description }}</p>
            <table class="offline-product__balances"><caption>{{ text('savedBalances') }}</caption><thead><tr><th scope="col"></th><th scope="col">{{ text('store') }}</th><th scope="col">{{ text('warehouse') }}</th></tr></thead><tbody>
              <tr><th scope="row">{{ text('physical') }}</th><td>{{ stockText(item, 'stock_loja') }}</td><td>{{ stockText(item, 'stock_deposito') }}</td></tr>
              <tr><th scope="row">{{ text('reserved') }}</th><td>{{ stockText(item, 'reserved_loja') }}</td><td>{{ stockText(item, 'reserved_deposito') }}</td></tr>
              <tr><th scope="row">{{ text('available') }}</th><td>{{ stockText(item, 'available_loja') }}</td><td>{{ stockText(item, 'available_deposito') }}</td></tr>
            </tbody></table>
          </div>
        </article>
      </section>

      <nav v-if="total > pageSize" class="offline-catalog__pagination" :aria-label="text('pagination')">
        <button class="erp-button erp-button--secondary erp-button--icon" :aria-label="text('previous')" :disabled="searching || offset === 0" @click="changePage(-1)"><ChevronLeft :size="20" aria-hidden="true" /></button>
        <span>{{ Math.floor(offset / pageSize) + 1 }} / {{ Math.ceil(total / pageSize) }}</span>
        <button class="erp-button erp-button--secondary erp-button--icon" :aria-label="text('next')" :disabled="searching || offset + pageSize >= total" @click="changePage(1)"><ChevronRight :size="20" aria-hidden="true" /></button>
      </nav>
    </div>
    <BarcodeScanner v-if="showScanner" @barcode-detected="onCode" @close="showScanner = false" />
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ChevronDown, ChevronLeft, ChevronRight, LogOut, Package, RefreshCw, ScanLine, Search, SlidersHorizontal, WifiOff } from 'lucide-vue-next'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { uiLocale } from '@/i18n/uiText'
import { getOfflineCatalogFacets, loadOfflineThumbnail, offlineCatalogState, searchOfflineCatalog, type OfflineCatalogItem } from '@/services/offlineCatalog'

withDefaults(defineProps<{ userName: string; loading?: boolean }>(), { loading: false })
const emit = defineEmits<{ retry: []; logout: [] }>()
const messages = {
  title: ['Estoque salvo', 'Inventario guardado', 'Saved inventory'], offline: ['Consulta offline', 'Consulta sin conexión', 'Offline browsing'],
  snapshotWarning: ['Preços e quantidades são da última cópia. Podem ter mudado na loja.', 'Precios y cantidades corresponden a la última copia. Pueden haber cambiado en la tienda.', 'Prices and quantities come from the last saved copy. They may have changed at the store.'],
  savedAt: ['Cópia salva em', 'Copia guardada el', 'Copy saved on'], notSaved: ['Ainda não disponível', 'Aún no disponible', 'Not available yet'],
  connect: ['Conectar', 'Conectar', 'Reconnect'], connecting: ['Conectando…', 'Conectando…', 'Connecting…'], logout: ['Sair', 'Cerrar sesión', 'Sign out'],
  searchLabel: ['Buscar produtos salvos', 'Buscar productos guardados', 'Search saved products'], searchPlaceholder: ['Nome, código, descrição…', 'Nombre, código, descripción…', 'Name, code, description…'],
  scan: ['Ler QR ou código de barras', 'Leer QR o código de barras', 'Scan QR or barcode'], filters: ['Filtros', 'Filtros', 'Filters'],
  brand: ['Marca', 'Marca', 'Brand'], category: ['Categoria', 'Categoría', 'Category'], color: ['Cor', 'Color', 'Color'], size: ['Tamanho', 'Talla', 'Size'], all: ['Todos', 'Todos', 'All'],
  uncategorized: ['Sem categoria', 'Sin categoría', 'Uncategorized'], status: ['Situação', 'Estado', 'Status'], active: ['Ativos', 'Activos', 'Active'], inactive: ['Inativo', 'Inactivo', 'Inactive'],
  out: ['Sem estoque', 'Sin existencias', 'Out of stock'], low: ['Estoque baixo', 'Existencias bajas', 'Low stock'], excess: ['Estoque em excesso', 'Exceso de existencias', 'Overstock'],
  location: ['Estoque no local', 'Existencias por ubicación', 'Stock by location'], store: ['Loja', 'Tienda', 'Store'], warehouse: ['Depósito', 'Depósito', 'Warehouse'],
  clear: ['Limpar busca e filtros', 'Limpiar búsqueda y filtros', 'Clear search and filters'], filtersUnavailable: ['Algumas opções não puderam ser lidas. A busca por texto continua disponível.', 'No se pudieron leer algunas opciones. La búsqueda de texto sigue disponible.', 'Some options could not be read. Text search is still available.'],
  searching: ['Buscando neste aparelho…', 'Buscando en este dispositivo…', 'Searching this device…'], products: ['produtos', 'productos', 'products'], readOnly: ['Somente consulta', 'Solo consulta', 'Read only'],
  loadFailed: ['Não foi possível ler a cópia local', 'No se pudo leer la copia local', 'Could not read the local copy'], tryConnection: ['Tente novamente ou conecte o aparelho para recuperar o catálogo.', 'Intenta de nuevo o conecta el dispositivo para recuperar el catálogo.', 'Try again or reconnect this device to recover the catalog.'], retryLocal: ['Tentar novamente', 'Intentar de nuevo', 'Try again'],
  noResults: ['Nenhum produto nesta busca', 'Ningún producto en esta búsqueda', 'No products match this search'], changeSearch: ['Confira o código, tente outra palavra ou limpe os filtros.', 'Revisa el código, prueba otra palabra o limpia los filtros.', 'Check the code, try another word or clear the filters.'],
  noSnapshot: ['Nenhum catálogo salvo neste aparelho', 'No hay catálogo guardado en este dispositivo', 'No catalog saved on this device'], prepareOnline: ['Conecte-se ao ERP para preparar a consulta offline.', 'Conéctate al ERP para preparar la consulta sin conexión.', 'Connect to the ERP to prepare offline browsing.'],
  details: ['Detalhes', 'Detalles', 'Details'], unconfirmed: ['Saldo não confirmado na cópia', 'Saldo no confirmado en la copia', 'Stock unconfirmed in this copy'], available: ['Disponível', 'Disponible', 'Available'], reserved: ['Reservado', 'Reservado', 'Reserved'],
  savedThumbnail: ['Miniatura salva neste aparelho', 'Miniatura guardada en este dispositivo', 'Thumbnail saved on this device'], savedBalances: ['Quantidades na última cópia', 'Cantidades en la última copia', 'Quantities in the last copy'], physical: ['Físico', 'Físico', 'Physical'],
  barcode: ['Código de barras', 'Código de barras', 'Barcode'], unit: ['Unidade', 'Unidad', 'Unit'], group: ['Grade', 'Grupo', 'Variant group'],
  pagination: ['Páginas de produtos', 'Páginas de productos', 'Product pages'], previous: ['Página anterior', 'Página anterior', 'Previous page'], next: ['Próxima página', 'Página siguiente', 'Next page'],
} as const
function text(key: keyof typeof messages) { return messages[key][uiLocale().startsWith('es') ? 1 : uiLocale().startsWith('en') ? 2 : 0] }
const query = ref(''), showScanner = ref(false), showFilters = ref(false), expandedId = ref<string | null>(null)
const filters = reactive({ brand: '', category: '', color: '', size: '', status: '', location_stock: '' })
const facets = ref({ brands: [] as string[], categories: [] as string[], colors: [] as string[], sizes: [] as string[] })
const facetsFailed = ref(false), searching = ref(false), searchFailed = ref(false)
const items = ref<OfflineCatalogItem[]>([]), total = ref(0), offset = ref(0), thumbnails = ref<Record<string, string | null>>({})
const pageSize = 50, syncedAt = computed(() => Number.isFinite(offlineCatalogState.syncedAt) && offlineCatalogState.syncedAt > 0 ? offlineCatalogState.syncedAt : 0)
const filterCount = computed(() => Object.values(filters).filter(Boolean).length)
let requestVersion = 0, facetVersion = 0, alive = true, searchTimer: ReturnType<typeof setTimeout> | undefined

function dateText(value: number) { return new Date(value).toLocaleString(uiLocale(), { timeZone: 'America/Sao_Paulo', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }) }
function numberText(value: unknown) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString(uiLocale()) : '—' }
type StockField = 'stock_loja' | 'stock_deposito' | 'available_loja' | 'available_deposito' | 'available_stock' | 'reserved_loja' | 'reserved_deposito'
function stockText(item: OfflineCatalogItem, field: StockField) { return item.stock_confirmed ? numberText(item[field]) : '—' }
function reservedTotal(item: OfflineCatalogItem) { return item.stock_confirmed && typeof item.reserved_loja === 'number' && typeof item.reserved_deposito === 'number' ? numberText(item.reserved_loja + item.reserved_deposito) : '—' }
function priceText(item: OfflineCatalogItem) {
  if (item.sale_price == null || !item.sale_currency) return '—'
  const amount = Number(item.sale_price)
  if (!Number.isFinite(amount)) return '—'
  const code = item.sale_currency.toUpperCase()
  if (!['USD', 'PYG', 'BRL', 'EUR'].includes(code)) return `${item.sale_currency} ${amount.toLocaleString(uiLocale())}`
  return new Intl.NumberFormat(uiLocale(), { style: 'currency', currency: code, maximumFractionDigits: code === 'PYG' ? 0 : 2 }).format(amount)
}
function details(item: OfflineCatalogItem) {
  return (['brand', 'category', 'color', 'size', 'unit', 'barcode'] as const).map(key => ({ label: text(key), value: item[key] || '—' }))
    .concat(item.group_key ? [{ label: text('group'), value: item.group_key }] : [])
}
function toggleDetails(id: string) { expandedId.value = expandedId.value === id ? null : id }
async function loadPhotos(rows: OfflineCatalogItem[], run: number) {
  const remaining = rows.filter(item => item.has_image)
  await Promise.all(Array.from({ length: Math.min(4, remaining.length) }, async () => {
    while (remaining.length && alive && run === requestVersion) {
      const item = remaining.shift()!
      try {
        const photo = await loadOfflineThumbnail(item.id, item.updated_at)
        if (alive && run === requestVersion && photo && /^data:image\/(?:jpeg|png|webp);base64,/i.test(photo)) thumbnails.value[item.id] = photo
      } catch { /* A missing thumbnail never blocks a local product search. */ }
    }
  }))
}
async function searchNow(reset = false) {
  if (!alive) return
  if (searchTimer) { clearTimeout(searchTimer); searchTimer = undefined }
  if (reset) offset.value = 0
  const run = ++requestVersion
  searching.value = true; searchFailed.value = false; expandedId.value = null
  try {
    const response = await searchOfflineCatalog(query.value.trim(), { ...filters }, { limit: pageSize, offset: offset.value })
    if (!alive || run !== requestVersion) return
    items.value = response.items; total.value = response.total; thumbnails.value = {}
    void loadPhotos(response.items, run)
  } catch {
    if (alive && run === requestVersion) { searchFailed.value = true; items.value = []; total.value = 0; thumbnails.value = {} }
  } finally { if (alive && run === requestVersion) searching.value = false }
}
function scheduleSearch() {
  // Invalidate a previous result immediately, even during the debounce window.
  requestVersion++; searching.value = true; offset.value = 0
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { void searchNow() }, 180)
}
watch([query, () => ({ ...filters })], scheduleSearch, { deep: true })
async function clearSearch() { query.value = ''; for (const key of Object.keys(filters) as (keyof typeof filters)[]) filters[key] = ''; await nextTick(); if (alive) void searchNow(true) }
function changePage(direction: number) { if (searching.value) return; offset.value = Math.max(0, offset.value + direction * pageSize); void searchNow() }
async function onCode(code: string) {
  if (!alive) return
  showScanner.value = false; query.value = code.trim()
  for (const key of Object.keys(filters) as (keyof typeof filters)[]) filters[key] = ''
  await nextTick()
  if (alive) void searchNow(true)
}
async function loadFacets() {
  const run = ++facetVersion
  try { const value = await getOfflineCatalogFacets(); if (alive && run === facetVersion) { facets.value = value; facetsFailed.value = false } }
  catch { if (alive && run === facetVersion) facetsFailed.value = true }
}
watch(() => [offlineCatalogState.syncedAt, offlineCatalogState.count, offlineCatalogState.loading], (current, previous) => {
  if (!current[2] && (current[0] !== previous[0] || current[1] !== previous[1] || previous[2])) {
    void searchNow(true); void loadFacets()
  }
})
onMounted(() => {
  void searchNow()
  void loadFacets()
})
onBeforeUnmount(() => { alive = false; requestVersion++; if (searchTimer) clearTimeout(searchTimer); thumbnails.value = {} })
</script>

<style scoped>
.offline-catalog{min-height:100dvh;background:#f7f9fc;color:#172033;padding:calc(14px + env(safe-area-inset-top,0px)) 14px calc(24px + env(safe-area-inset-bottom,0px))}.offline-catalog__content{max-width:1180px;margin:auto}.offline-catalog__header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px}.offline-catalog__brand{font-weight:800;font-size:12px;letter-spacing:.2em;color:#2563eb}.offline-catalog h1{font-size:23px;margin:3px 0;line-height:1.2}.offline-catalog__user{font-size:12px;color:#64748b;margin:4px 0 0}.offline-catalog__actions{display:flex;align-items:center;gap:7px}.offline-catalog__notice{display:flex;gap:10px;padding:13px 14px;background:#fff8eb;border:1px solid #f0ddba;border-radius:15px;color:#7c5b24;font-size:12px}.offline-catalog__notice>svg{flex-shrink:0;margin-top:2px}.offline-catalog__notice p{margin:4px 0 0;line-height:1.45}.offline-catalog__notice strong{font-size:13px}.offline-catalog__sync{font-size:11px}.offline-catalog__search{display:flex;gap:8px;margin:16px 0 10px}.offline-catalog__query{min-width:0;flex:1;display:flex;align-items:center;gap:9px;background:white;border:1px solid #dbe2ed;border-radius:12px;padding:0 11px;color:#64748b}.offline-catalog__query input{min-width:0;width:100%;border:0;background:none;outline:none;height:44px;font-size:16px;color:#172033}.offline-catalog__query:focus-within{outline:2px solid #93b4ff;outline-offset:1px}.offline-catalog__search>.erp-button{position:relative;min-width:46px;min-height:46px;flex-shrink:0;border-radius:12px}.offline-catalog__filter-count{position:absolute;top:-5px;right:-4px;min-width:17px;height:17px;padding:0 4px;display:grid;place-items:center;border-radius:99px;background:#2563eb;color:white;font-size:10px}.offline-catalog__filters{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;background:#fff;border:1px solid #e2e8f0;border-radius:15px;padding:14px;margin-bottom:12px}.offline-catalog__filters>label{min-width:0;display:grid;gap:6px;color:#64748b;font-size:12px}.offline-catalog__filters>button,.offline-catalog__filters>small{grid-column:1/-1;justify-self:start}.offline-catalog__results{display:flex;justify-content:space-between;gap:12px;margin:12px 2px;font-size:12px;color:#64748b;min-height:18px}.offline-catalog__grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;align-items:start}.offline-product{overflow:hidden;background:#fff;border:1px solid #e0e6ef;border-radius:16px;box-shadow:0 2px 5px #0f172a03;min-width:0}.offline-product__photo{position:relative;width:100%;height:140px;border:0;background:#f0f3f8;color:#9aa8bb;display:grid;place-items:center;cursor:pointer}.offline-product__photo img{height:100%;width:100%;object-fit:contain}.offline-product__inactive{position:absolute;top:8px;left:8px;padding:3px 7px;background:#e2e8f0;color:#475569;border-radius:6px;font-size:10px}.offline-product__body{padding:11px 12px 9px}.offline-product__code{color:#7b8799;font-size:10px;letter-spacing:.03em;overflow-wrap:anywhere;margin:0 0 5px}.offline-product h2{font-size:13px;line-height:1.35;margin:0;font-weight:650;overflow-wrap:anywhere;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden;min-height:35px}.offline-product__variant{font-size:11px;color:#64748b;margin:6px 0;overflow-wrap:anywhere;min-height:15px}.offline-product__price{display:block;font-size:14px;font-weight:650;color:#1d4ed8;margin:8px 0}.offline-product__stock{display:flex;gap:7px;align-items:center;margin:9px 0 4px;font-size:15px;font-weight:650}.offline-product__stock>span:nth-child(2){font-weight:400;color:#cad3e0}.offline-product__availability{font-size:11px;color:#64748b;line-height:1.6;margin:0}.offline-product__unconfirmed{font-size:11px;color:#a15b16;margin:7px 0}.offline-product__details-toggle{display:flex;justify-content:space-between;width:100%;padding:6px 0;margin-top:7px;font-size:12px;min-height:34px}.negative-stock{color:#b42318}.rotated{transform:rotate(180deg)}.offline-product__details{border-top:1px solid #eef1f6;padding:12px;background:#fbfcfe}.offline-product__details>img{display:block;width:100%;max-height:300px;object-fit:contain;border-radius:8px}.offline-product__thumbnail-note{color:#7b8799;font-size:10px;margin:6px 0 12px}.offline-product__details dl{display:grid;grid-template-columns:auto minmax(0,1fr);gap:7px 9px;font-size:11px;margin:0}.offline-product__details dt{color:#64748b}.offline-product__details dd{margin:0;overflow-wrap:anywhere}.offline-product__description{font-size:12px;line-height:1.5;white-space:pre-line;overflow-wrap:anywhere}.offline-product__balances{width:100%;border-collapse:collapse;font-size:10px;margin-top:12px}.offline-product__balances caption{text-align:left;color:#64748b;font-size:10px;margin-bottom:7px}.offline-product__balances th{font-weight:500;text-align:left;color:#64748b}.offline-product__balances td{text-align:center;font-variant-numeric:tabular-nums}.offline-product__balances td,.offline-product__balances th{padding:5px 2px;border-bottom:1px solid #eef1f6}.offline-catalog__empty{text-align:center;color:#64748b;padding:40px 20px;background:white;border:1px dashed #d7dfeb;border-radius:16px}.offline-catalog__empty h2{font-size:17px;color:#334155}.offline-catalog__empty p{font-size:13px;line-height:1.5;max-width:420px;margin:10px auto 18px}.offline-catalog__pagination{display:flex;justify-content:center;align-items:center;gap:22px;padding:22px 0 4px;font-size:13px;color:#64748b}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}.spinning{animation:offline-spin 1.2s linear infinite}@keyframes offline-spin{to{transform:rotate(360deg)}}@media(min-width:760px){.offline-catalog{padding-left:24px;padding-right:24px}.offline-catalog__grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}.offline-catalog__filters{grid-template-columns:repeat(3,minmax(0,1fr))}.offline-product__photo{height:170px}.offline-product h2{font-size:15px}.offline-product__code,.offline-product__availability,.offline-product__variant{font-size:12px}.offline-product__body{padding:14px}.offline-product__details dl,.offline-product__balances{font-size:12px}}@media(min-width:1100px){.offline-catalog__grid{grid-template-columns:repeat(4,minmax(0,1fr))}.offline-catalog__filters{grid-template-columns:repeat(6,minmax(0,1fr))}}@media(max-width:359px){.offline-catalog{padding-left:10px;padding-right:10px}.offline-catalog__grid{grid-template-columns:1fr}.offline-catalog h1{font-size:20px}.offline-catalog__header{gap:6px}.offline-catalog__actions{gap:3px}}@media(prefers-reduced-motion:reduce){.spinning{animation:none}}
</style>
