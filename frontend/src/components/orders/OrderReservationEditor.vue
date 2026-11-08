<template>
  <Teleport to="body">
    <div class="erp-dialog-backdrop" @click.self="close">
      <section v-erp-dialog class="erp-dialog erp-dialog--xl reservation-editor" aria-labelledby="reservation-title">
        <header class="erp-dialog__header">
          <div><p class="eyebrow">{{ uiText('PEDIDOS · SEPARAÇÃO') }}</p><h2 id="reservation-title">{{ uiText(orderId ? 'Editar peças separadas' : 'Separar produtos') }}</h2></div>
          <button type="button" data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :aria-label="uiText('Fechar')" :disabled="saving || uncertain" @click="close">×</button>
        </header>
        <div v-if="loading" class="erp-dialog__body editor-loading" role="status">{{ uiText('Carregando pedido…') }}</div>
        <div v-else-if="loadError" class="erp-dialog__body" role="alert"><p>{{ loadError }}</p><button class="erp-button erp-button--secondary" @click="initialize">{{ uiText('Tentar novamente') }}</button></div>
        <template v-else>
          <nav class="erp-dialog__tabs editor-tabs" :aria-label="uiText('Etapas do pedido')">
            <button class="erp-control" :class="{ active: tab === 'products' }" @click="tab = 'products'">{{ uiText('Produtos') }}</button>
            <button class="erp-control" :class="{ active: tab === 'order' }" @click="tab = 'order'">{{ uiText('Separação') }} <span>{{ pieceCount }}</span></button>
          </nav>
          <div class="erp-dialog__body editor-body">
            <div class="editor-grid">
              <section class="catalog-panel" :class="{ 'mobile-hidden': tab !== 'products' }">
                <div class="catalog-search">
                  <input v-model="query" type="search" :placeholder="uiText('Produto, marca, tamanho ou código…')" :aria-label="uiText('Buscar produtos para separar')" :disabled="locked" @keydown.enter.prevent="addSingleResult" />
                  <button class="erp-button erp-button--primary erp-button--icon" :aria-label="uiText('Ler QR ou código de barras')" :disabled="locked" @click="scanner = true"><ScanLine :size="21" /></button>
                </div>
                <p class="panel-hint">{{ uiText(query.trim() ? 'Selecione o produto e o local de onde será separado.' : 'Produtos recentes · busque ou leia a etiqueta') }}</p>
                <p v-if="searching" role="status" class="panel-hint">{{ uiText('Consultando produtos e disponibilidade…') }}</p>
                <div v-else-if="searchError" role="alert" class="inline-error">{{ searchError }} <button class="erp-button erp-button--sm" @click="search">{{ uiText('Tentar novamente') }}</button></div>
                <p v-else-if="!products.length" class="panel-hint">{{ uiText('Nenhum produto encontrado. Tente o nome ou código interno.') }}</p>
                <div class="catalog-list">
                  <article v-for="item in products" :key="item.id" class="catalog-product">
                    <ProductThumbnail :item="item" :alt="item.name" class="product-photo" />
                    <div class="product-info"><strong>{{ item.name }}</strong><small>{{ [item.size, item.color].filter(Boolean).join(' · ') }}</small><small>{{ item.inventory_code || item.sku_internal }}</small>
                      <div class="catalog-bottom"><ErpSelect v-model="locations[item.id]" compact :label="uiText('Local para separar')" :disabled="locked"><option value="loja">{{ uiText('Loja') }} · {{ stockLabel(available(item.id, 'loja')) }}</option><option value="deposito">{{ uiText('Depósito') }} · {{ stockLabel(available(item.id, 'deposito')) }}</option></ErpSelect><span class="product-price">{{ saleUsd(catalogPriceGs(item), rate) }}</span></div>
                    </div>
                    <button class="erp-button erp-button--primary erp-button--icon add-product" :aria-label="uiText('Separar {0}', { 0: item.name })" :disabled="locked || !canAdd(item)" @click="add(item)">+</button>
                  </article>
                </div>
              </section>
              <section class="order-panel" :class="{ 'mobile-hidden': tab !== 'order' }">
                <PDVCustomerPicker v-model:customer-id="customerId" v-model:customer-name="customerName" required :disabled="locked || !!original?.payments.length" @busy="customerBusy = $event" />
                <p v-if="customerName && !customerId" class="inline-error">{{ uiText('Selecione um cliente cadastrado para manter a reserva e os pagamentos associados.') }}</p>
                <div class="selection-heading"><strong>{{ uiText('Peças a separar') }}</strong><span>{{ pieceCount }} {{ uiText('un') }}</span></div>
                <div v-if="!lines.length" class="empty-selection"><ShoppingBag :size="34" /><strong>{{ uiText('Monte a sacola do cliente') }}</strong><p>{{ uiText('Adicione os produtos. A reserva será feita ao confirmar.') }}</p></div>
                <article v-for="line in lines" :key="line.key" class="selected-line">
                  <ProductThumbnail :item="thumbnail(line)" :alt="line.item_name" class="selected-photo" />
                  <div class="selected-main"><strong>{{ line.item_name }}</strong><small>{{ [line.item_size, line.item_color, uiText(line.location === 'loja' ? 'Loja' : 'Depósito')].filter(Boolean).join(' · ') }}</small><small>{{ line.item_sku }}</small>
                    <div class="line-controls"><div class="quantity-control"><button class="erp-button erp-button--secondary erp-button--icon" :disabled="locked || line.quantity <= 1" :aria-label="uiText('Diminuir quantidade')" @click="line.quantity--; reviewed = false">−</button><input :value="line.quantity" type="number" inputmode="numeric" min="1" max="9999999" step="1" :disabled="locked" :aria-label="uiText('Quantidade de {0}', { 0: line.item_name })" @change="setQuantity(line, $event)" /><button class="erp-button erp-button--secondary erp-button--icon" :disabled="locked || refreshing === line.key" :aria-label="uiText('Aumentar quantidade')" @click="increase(line)">+</button></div><label class="price-input">U$ <input :value="usdPrice(line)" type="number" inputmode="decimal" min="0" step="0.01" :disabled="locked" :aria-label="uiText('Preço em dólares de {0}', { 0: line.item_name })" @change="setPrice(line, $event)" /></label></div>
                  </div>
                  <button class="erp-button erp-button--ghost erp-button--icon remove-line" :aria-label="uiText('Remover {0}', { 0: line.item_name })" :disabled="locked" @click="remove(line)">×</button>
                </article>
                <div class="order-settings"><label>{{ uiText('Observações / onde está separado') }}<textarea v-model="notes" rows="2" maxlength="2000" :disabled="locked" :placeholder="uiText('Ex.: sacola 3, prateleira do caixa')" /></label><label class="discount-input">{{ uiText('Desconto (U$)') }}<input :value="discountUsd" type="number" inputmode="decimal" min="0" step="0.01" :disabled="locked" @change="setDiscount" /></label></div>
                <div class="order-total"><span>{{ uiText('Total do pedido') }}</span><strong>{{ saleUsd(total, rate) }}</strong></div>
                <p class="panel-hint">{{ uiText('O pedido separado sai do saldo disponível. A venda e a baixa física acontecem na conclusão pelo PDV.') }}</p>
              </section>
            </div>
            <p v-if="notice" class="inline-notice" role="status">{{ notice }}</p>
            <p v-if="error" class="inline-error" role="alert">{{ error }}</p>
            <p v-if="!validRate" class="inline-error">{{ uiText('Não foi possível confirmar o câmbio. Atualize antes de reservar.') }} <button class="erp-button erp-button--sm" :disabled="locked" @click="reloadRates">{{ uiText('Atualizar câmbio') }}</button></p>
            <p v-if="uncertain" class="inline-error" role="alert">{{ uiText('A resposta não foi confirmada. Repita a mesma confirmação para recuperar o resultado, sem criar outra reserva.') }}</p>
          </div>
          <footer class="erp-dialog__footer editor-footer">
            <label class="review-checkbox"><input v-model="reviewed" type="checkbox" :disabled="locked" />{{ uiText('Conferi o cliente, as peças e os locais da separação.') }}</label>
            <div class="footer-actions"><button class="erp-button erp-button--secondary" :disabled="saving || uncertain" @click="close">{{ uiText('Cancelar') }}</button><button class="erp-button erp-button--primary" :disabled="saving || (!uncertain && !canSave)" @click="save">{{ uiText(saving ? 'Salvando…' : uncertain ? 'Repetir confirmação' : orderId ? 'Salvar separação' : 'Confirmar reserva') }}<span v-if="!saving && !uncertain"> · {{ saleUsd(total, rate) }}</span></button></div>
          </footer>
        </template>
      </section>
    </div>
    <BarcodeScanner v-if="scanner" @close="scanner = false" @barcode-detected="scan" />
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ScanLine, ShoppingBag } from 'lucide-vue-next'
import { vErpDialog } from '@/directives/erpDialog'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import ProductThumbnail from '@/components/inventory/ProductThumbnail.vue'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import PDVCustomerPicker from '@/components/pdv/PDVCustomerPicker.vue'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import { orderReservations, reservationError, type ReservationDetail, type ReservationItem, type ReservationSave } from '@/services/orderReservations'
import { paymentRate } from '@/services/pdvPayments'
import { saleUsd } from '@/services/saleUsd'
import { uiText } from '@/i18n/uiText'
import { useCurrencyStore } from '@/stores/currency'
import { useAuthStore } from '@/stores/auth'

type DraftLine = ReservationItem & { key: string }
type StockItem = InventoryItem & { available_loja?: number | null; available_deposito?: number | null }
const props = defineProps<{ orderId?: string }>()
const emit = defineEmits<{ close: []; saved: [value: ReservationDetail] }>()
const currency = useCurrencyStore(), auth = useAuthStore()
const loading = ref(true), loadError = ref(''), saving = ref(false), uncertain = ref(false), customerBusy = ref(false), reviewed = ref(false)
const original = ref<ReservationDetail | null>(null), customerId = ref<string | null>(null), customerName = ref<string | null>(null)
const lines = ref<DraftLine[]>([]), notes = ref(''), discount = ref(0), rate = ref(0), error = ref(''), notice = ref(''), refreshing = ref('')
const tab = ref<'products' | 'order'>('products'), scanner = ref(false), query = ref(''), products = ref<StockItem[]>([])
const catalog = ref<Record<string, StockItem>>({}), locations = ref<Record<string, 'loja' | 'deposito'>>({})
const searching = ref(false), searchError = ref('')
let generation = 0, controller: AbortController | undefined, timer: ReturnType<typeof setTimeout> | undefined, disposed = false
let pending: ReservationSave | null = null
const locked = computed(() => saving.value || uncertain.value)
const validRate = computed(() => Number.isFinite(rate.value) && rate.value > 0)
const pieceCount = computed(() => lines.value.reduce((sum, line) => sum + line.quantity, 0))
const subtotal = computed(() => Math.round(lines.value.reduce((sum, line) => sum + line.quantity * line.unit_price_gs, 0) * 100) / 100)
const total = computed(() => Math.round((subtotal.value - discount.value) * 100) / 100)
const discountUsd = computed(() => validRate.value ? Number((discount.value / rate.value).toFixed(2)) : 0)
const canSave = computed(() => !!customerId.value && !!lines.value.length && lines.value.length <= 200 && !customerBusy.value && reviewed.value && validRate.value && discount.value >= 0 && total.value >= 0 && total.value >= Number(original.value?.paid_gs || 0) && lines.value.every(line => Number.isInteger(line.quantity) && line.quantity > 0 && Number.isFinite(line.unit_price_gs) && line.unit_price_gs >= 0))
const storageKey = () => `eleven-order-reservation:${auth.user?.id || 'unknown'}:${props.orderId || 'new'}`
function storePending() { try { if (pending) sessionStorage.setItem(storageKey(), JSON.stringify({ payload: pending, customerName: customerName.value, lines: lines.value })); else sessionStorage.removeItem(storageKey()) } catch { /* Network retry still retains the key in this open editor. */ } }
function close() { if (!saving.value && !uncertain.value) emit('close') }
function stockLabel(value: number | null) { return value === null ? '—' : String(value) }
function ownReserved(id: string, location: string) { return original.value?.items.filter(line => line.item_id === id && line.location === location).reduce((sum, line) => sum + line.quantity, 0) || 0 }
function available(id: string, location: 'loja' | 'deposito', excludeKey?: string): number | null {
  const item = catalog.value[id]
  const source = original.value?.items.find(line => line.item_id === id)
  const base = item ? (location === 'loja' ? item.available_loja ?? item.stock_loja : item.available_deposito ?? item.stock_deposito)
    : (location === 'loja' ? source?.available_loja : source?.available_deposito) ?? null
  const own = ownReserved(id, location)
  // Until a fresh catalog row arrives, only the already-reserved quantity is known.
  if (base === null && !own) return null
  const selected = lines.value.filter(line => line.item_id === id && line.location === location && line.key !== excludeKey).reduce((sum, line) => sum + line.quantity, 0)
  return Math.max(0, Number(base || 0) + own - selected)
}
function remember(items: StockItem[]) {
  for (const item of items) {
    catalog.value[item.id] = item
    locations.value[item.id] ||= Number(item.available_loja ?? item.stock_loja) > 0 ? 'loja' : 'deposito'
  }
}
function catalogPriceGs(item: StockItem) {
  const native = Number(item.sale_price), conversion = paymentRate(item.sale_currency || 'PYG', { ...currency.exchangeRates, 'G$': rate.value })
  return Number.isFinite(native) && native >= 0 && conversion > 0 ? Math.round(native * conversion * 100) / 100 : NaN
}
function canAdd(item: StockItem) { return item.is_active && validRate.value && Number.isFinite(catalogPriceGs(item)) && (available(item.id, locations.value[item.id] || 'loja') || 0) >= 1 }
function add(item: StockItem) {
  if (locked.value || !canAdd(item)) return
  const location = locations.value[item.id] || 'loja', key = `${item.id}:${location}`, current = lines.value.find(line => line.key === key)
  if (current) current.quantity++
  else lines.value.push({ key, id: key, item_id: item.id, item_name: item.name, item_sku: item.inventory_code || item.sku_internal, item_size: item.size || null, item_color: item.color || null, location, quantity: 1, unit_price_gs: catalogPriceGs(item), total_gs: catalogPriceGs(item) })
  reviewed.value = false; error.value = ''; notice.value = uiText('{0} adicionado à separação.', { 0: item.name })
}
function addSingleResult() { if (!searching.value && products.value.length === 1) add(products.value[0]) }
function thumbnail(line: DraftLine) { return catalog.value[line.item_id] || { id: line.item_id, has_image: line.has_image ?? true, updated_at: line.updated_at || original.value?.reserved_at || '' } }
function remove(line: DraftLine) { lines.value = lines.value.filter(row => row.key !== line.key); reviewed.value = false }
function usdPrice(line: DraftLine) { return validRate.value ? Number((line.unit_price_gs / rate.value).toFixed(2)) : 0 }
function setQuantity(line: DraftLine, event: Event) {
  const input = event.target as HTMLInputElement, value = Number(input.value), allowed = available(line.item_id, line.location, line.key)
  if (!input.value.trim() || !Number.isInteger(value) || value < 1 || value > 9999999 || allowed === null || value > allowed) {
    error.value = uiText('Quantidade indisponível nesse local. Atualize o produto ou confira o estoque.'); input.value = String(line.quantity); return
  }
  line.quantity = value; reviewed.value = false; error.value = ''
}
async function increase(line: DraftLine) {
  if (locked.value || refreshing.value) return
  refreshing.value = line.key; error.value = ''
  try {
    if (!catalog.value[line.item_id]) remember([await inventoryAPI.getItemForSale(line.item_id)])
    if (disposed) return
    const allowed = available(line.item_id, line.location, line.key)
    if (allowed === null || line.quantity + 1 > allowed) { error.value = uiText('Não há mais unidades disponíveis nesse local.'); return }
    line.quantity++; reviewed.value = false
  } catch (caught) { if (!disposed) error.value = reservationError(caught) }
  finally { refreshing.value = '' }
}
function setPrice(line: DraftLine, event: Event) {
  const input = event.target as HTMLInputElement, value = Number(input.value)
  if (!input.value.trim() || !Number.isFinite(value) || value < 0 || value > 999999999 || !validRate.value) { input.value = String(usdPrice(line)); error.value = uiText('Informe um preço válido.'); return }
  line.unit_price_gs = Math.round(value * rate.value * 100) / 100; reviewed.value = false; error.value = ''
}
function setDiscount(event: Event) {
  const input = event.target as HTMLInputElement, value = Number(input.value), converted = Math.round(value * rate.value * 100) / 100
  if (!Number.isFinite(value) || value < 0 || converted > subtotal.value) { input.value = String(discountUsd.value); error.value = uiText('O desconto deve ficar entre zero e o subtotal.'); return }
  discount.value = converted; reviewed.value = false; error.value = ''
}
async function reloadRates() { if (original.value) return; if (await currency.loadCurrentRates()) rate.value = currency.exchangeRates['G$'] }
function invalidate() { generation++; controller?.abort(); clearTimeout(timer) }
async function search() {
  invalidate(); const run = generation; controller = new AbortController(); searching.value = true; searchError.value = ''
  try {
    const result = await inventoryAPI.getItems({ search: query.value.trim() || undefined, page_size: query.value.trim() ? 20 : 8, status: 'active', sort_by: query.value.trim() ? undefined : 'created_at', include_images: false }, controller.signal)
    if (disposed || run !== generation) return
    products.value = result.items; remember(result.items)
  } catch (caught) { if (!disposed && run === generation) { searchError.value = reservationError(caught); products.value = [] } }
  finally { if (!disposed && run === generation) searching.value = false }
}
watch(query, () => { invalidate(); products.value = []; searching.value = true; const run = generation; timer = setTimeout(() => { if (run === generation) void search() }, 280) })
watch([customerId, notes], () => { reviewed.value = false })
async function scan(code: string) {
  scanner.value = false; invalidate(); query.value = code; await Promise.resolve(); invalidate(); const run = generation; searching.value = true; searchError.value = ''
  try {
    const items = await inventoryAPI.getByBarcode(code, false)
    if (disposed || run !== generation) return
    products.value = items; remember(items)
    if (items.length === 1) add(items[0])
    else if (items.length > 1) notice.value = uiText('Este código pertence a mais de um produto. Escolha a variação correta.')
  } catch (caught) { if (!disposed && run === generation) searchError.value = reservationError(caught) }
  finally { if (!disposed && run === generation) searching.value = false }
}
async function initialize() {
  loading.value = true; loadError.value = ''
  try {
    if (props.orderId) {
      const value = await orderReservations.detail(props.orderId)
      if (disposed) return
      if (value.commerce_status !== 'reserved') throw new Error('closed')
      original.value = value; customerId.value = value.pdv_cliente_id; customerName.value = value.cliente_nome
      lines.value = value.items.map(item => ({ ...item, key: `${item.item_id}:${item.location}` })); notes.value = value.notas || ''; discount.value = value.desconto_gs; rate.value = value.usd_rate_gs; tab.value = 'order'
      void currency.loadCurrentRates()
    } else await reloadRates()
    if (disposed) return
    try {
      const saved = sessionStorage.getItem(storageKey())
      if (saved) {
        const record = JSON.parse(saved) as { payload: ReservationSave; customerName?: string; lines?: DraftLine[] }
        const value = record.payload
        if (value?.request_id && value.confirm === true && Array.isArray(value.items) && value.pdv_cliente_id) {
          pending = value; uncertain.value = true; customerId.value = value.pdv_cliente_id; customerName.value = record.customerName || null
          if (Array.isArray(record.lines)) lines.value = record.lines
          rate.value = value.usd_rate_gs; discount.value = value.desconto_gs; notes.value = value.notas || ''; tab.value = 'order'
          error.value = uiText('Há uma confirmação anterior sem resposta. Recupere o resultado antes de começar outra separação.')
        }
      }
    } catch { /* A malformed local draft is never submitted. */ }
    void search()
  } catch (caught) { if (!disposed) loadError.value = (caught as Error).message === 'closed' ? uiText('Este pedido não está mais reservado. Feche e atualize a listagem.') : reservationError(caught) }
  finally { if (!disposed) loading.value = false }
}
async function save() {
  if (saving.value || (!pending && !canSave.value)) return
  if (!pending) pending = { request_id: crypto.randomUUID(), confirm: true, expected_version: original.value?.commerce_version, pdv_cliente_id: customerId.value!, items: lines.value.map(line => ({ item_id: line.item_id, location: line.location, quantity: line.quantity, unit_price_gs: line.unit_price_gs })), usd_rate_gs: rate.value, desconto_gs: discount.value, notas: notes.value.trim() || undefined }
  storePending(); saving.value = true; error.value = ''
  try {
    const value = props.orderId ? await orderReservations.update(props.orderId, pending) : await orderReservations.create(pending)
    pending = null; storePending(); uncertain.value = false
    if (!disposed) emit('saved', value)
  } catch (caught) {
    const status = (caught as { response?: { status?: number } })?.response?.status
    uncertain.value = !status || status >= 500
    if (!uncertain.value) { pending = null; storePending() }
    if (!disposed) error.value = reservationError(caught)
  } finally { saving.value = false }
}
onMounted(initialize)
onBeforeUnmount(() => { disposed = true; invalidate() })
</script>

<style scoped>
.erp-dialog-backdrop{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;z-index:1000}.editor-tabs{display:none!important}.editor-footer{flex-direction:column!important}
.reservation-editor{width:min(1120px,calc(100vw - 32px));max-width:1120px}.eyebrow{margin:0 0 4px;color:#64748b;font-size:.65rem;font-weight:750;letter-spacing:.12em}.reservation-editor h2{font-size:1.15rem;margin:0}.editor-body{padding:0!important}.editor-grid{display:grid;grid-template-columns:1fr 1fr;min-height:420px}.catalog-panel{border-right:1px solid #e2e8f0;min-width:0;background:#f8fafc}.order-panel{min-width:0;padding-bottom:12px}.catalog-search{display:flex;gap:8px;padding:16px 16px 8px}.catalog-search input{min-width:0;flex:1;padding:12px;border:1px solid #dbe3ee;border-radius:12px;font-size:.9rem;background:#fff}.panel-hint{font-size:.76rem;color:#64748b;margin:8px 16px;line-height:1.55}.catalog-list{padding:0 12px 16px}.catalog-product{display:flex;gap:10px;padding:14px 0;border-bottom:1px solid #e2e8f0;align-items:center}.product-photo{width:64px;height:76px;object-fit:contain;background:white;border-radius:9px;flex-shrink:0}.product-info{min-width:0;flex:1;display:flex;flex-direction:column;gap:4px}.product-info strong{font-size:.84rem;overflow-wrap:anywhere;line-height:1.4}.product-info small,.selected-main small{font-size:.7rem;color:#64748b}.catalog-bottom{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:4px}.catalog-bottom :deep(.erp-select){max-width:160px}.product-price{font-weight:650;color:#2563eb;font-size:.78rem}.add-product{align-self:flex-end;font-size:1.3rem;min-width:38px!important;width:38px;height:38px;min-height:38px!important}.selection-heading{display:flex;justify-content:space-between;padding:15px 16px 8px;font-size:.83rem}.selection-heading span{color:#2563eb;background:#eff6ff;border-radius:12px;padding:3px 8px}.empty-selection{display:flex;flex-direction:column;align-items:center;text-align:center;color:#94a3b8;gap:10px;padding:40px 25px}.empty-selection strong{color:#475569;font-size:.9rem}.empty-selection p{font-size:.8rem;margin:0;line-height:1.5}.selected-line{display:flex;align-items:flex-start;padding:12px 14px;border-bottom:1px solid #edf1f6;gap:10px}.selected-photo{width:44px;height:56px;object-fit:contain;border-radius:8px;background:#f8fafc}.selected-main{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}.selected-main>strong{font-size:.81rem;line-height:1.4;overflow-wrap:anywhere}.line-controls{display:flex;gap:8px;flex-wrap:wrap;margin-top:7px}.quantity-control{display:flex;gap:3px}.quantity-control button{min-width:32px!important;width:32px;min-height:34px!important;height:34px;border-radius:8px}.quantity-control input{width:44px;text-align:center;border:1px solid #dbe3ee;border-radius:8px;font-size:.83rem;appearance:textfield}.quantity-control input::-webkit-inner-spin-button{appearance:none}.price-input{display:flex;align-items:center;gap:6px;border:1px solid #dbe3ee;border-radius:8px;padding:0 8px;color:#64748b;font-size:.75rem}.price-input input{width:68px;border:none;min-width:0;font-size:.83rem;background:transparent;outline:none}.remove-line{min-width:25px!important;width:25px;min-height:30px!important;height:30px;color:#94a3b8}.order-settings{display:flex;flex-direction:column;gap:12px;padding:16px}.order-settings label{display:flex;flex-direction:column;gap:6px;font-size:.75rem;color:#475569;font-weight:550}.order-settings textarea,.order-settings input{border:1px solid #dbe3ee;border-radius:9px;padding:9px;font:inherit;background:#fff}.order-settings .discount-input{flex-direction:row;align-items:center;justify-content:space-between}.discount-input input{width:100px;text-align:right}.order-total{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;margin:0 12px;background:#eff6ff;border-radius:12px;color:#1e3a5f;font-size:.85rem}.order-total strong{font-size:1.2rem;color:#1d4ed8}.editor-footer{display:flex;flex-direction:column;align-items:stretch!important;gap:10px}.review-checkbox{display:flex;align-items:flex-start;gap:8px;font-size:.78rem;color:#475569;line-height:1.5}.review-checkbox input{width:17px;height:17px;margin:1px 0;accent-color:#2563eb}.footer-actions{display:flex;gap:8px;justify-content:flex-end}.inline-error{margin:12px 16px;color:#a4420a;background:#fff7ed;border:1px solid #fed7aa;padding:10px 12px;border-radius:10px;font-size:.8rem;line-height:1.5}.inline-notice{margin:12px 16px;color:#166534;background:#f0fdf4;padding:10px 12px;border-radius:10px;font-size:.8rem}.editor-tabs{display:none}.editor-loading{padding:35px;color:#64748b;text-align:center}
@media(max-width:720px){.reservation-editor{width:calc(100vw - 16px)}.editor-tabs{display:flex!important;gap:8px;padding:8px 16px!important}.editor-tabs button{flex:1;border:0;background:#f1f5f9;color:#64748b;border-radius:10px;padding:10px;font-weight:600}.editor-tabs button.active{background:#eff6ff;color:#2563eb}.editor-tabs span{background:#dbeafe;border-radius:12px;padding:2px 7px;font-size:.75rem}.editor-grid{display:block;min-height:0}.catalog-panel{border-right:0}.mobile-hidden{display:none}.footer-actions>.erp-button--primary{flex:1}.footer-actions button{font-size:.8rem}.footer-actions span{display:none}.catalog-search input,.quantity-control input,.price-input input,.order-settings textarea,.order-settings input{font-size:16px}.product-photo{width:60px;height:68px}}
</style>
