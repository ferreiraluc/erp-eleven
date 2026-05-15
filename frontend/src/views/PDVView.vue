<template>
  <div class="pdv-root">

    <!-- PDV Header -->
    <div class="pdv-header">
      <button class="pdv-back-btn" @click="router.push('/dashboard')">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        Dashboard
      </button>
      <span class="pdv-header-title">PDV</span>
      <div class="pdv-header-rates">
        <span>U$ {{ fmtRateShort(exchangeRates.usd) }}</span>
        <span>R$ {{ fmtRateShort(exchangeRates.brl) }}</span>
        <span>€ {{ fmtRateShort(exchangeRates.eur) }}</span>
      </div>
    </div>

    <!-- Mobile tab bar -->
    <div class="pdv-tab-bar mobile-only">
      <button :class="['pdv-tab', { active: mobileTab === 'products' }]" @click="mobileTab = 'products'">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        Produtos
      </button>
      <button :class="['pdv-tab', { active: mobileTab === 'cart' }]" @click="mobileTab = 'cart'">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
        Carrinho
        <span v-if="pdv.cartCount > 0" class="pdv-tab-badge">{{ pdv.cartCount }}</span>
      </button>
    </div>

    <!-- Main layout -->
    <div class="pdv-layout">

      <!-- LEFT: Product search panel -->
      <div class="pdv-panel-products" :class="{ 'mobile-hidden': mobileTab !== 'products' }">

        <!-- Search bar -->
        <div class="pdv-search-bar">
          <div class="pdv-search-input-wrap">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" class="pdv-search-icon"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <input
              ref="searchInput"
              v-model="searchQuery"
              type="text"
              placeholder="Buscar produto, SKU ou código de barras… (F2)"
              class="pdv-search-input"
              @keydown.enter="onSearchEnter"
              @input="onSearchInput"
            />
            <button v-if="searchQuery" class="pdv-search-clear" @click="clearSearch">×</button>
          </div>
          <button class="pdv-scan-btn" @click="showScanner = true" title="Escanear código">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h2M4 12v.01M12 8h.01M4 8h.01M20 8h.01M4 4h4M20 4h-4M4 20h4M20 20h-4"/></svg>
          </button>
        </div>

        <!-- Search results -->
        <div v-if="searchResults.length" class="pdv-results">
          <div
            v-for="item in searchResults"
            :key="item.id"
            class="pdv-result-row"
            @click="addToCart(item)"
          >
            <!-- Product thumbnail -->
            <div class="pdv-result-thumb">
              <img v-if="item.image_data" class="pdv-result-img" :src="imgSrc(item.image_data)" />
              <div v-else class="pdv-result-no-img">{{ item.name.charAt(0).toUpperCase() }}</div>
            </div>

            <div class="pdv-result-left">
              <div class="pdv-result-name">{{ item.name }}</div>
              <div class="pdv-result-meta">{{ [item.category, item.size, item.color].filter(Boolean).join(' · ') }}</div>
              <div class="pdv-result-sku">{{ item.sku_internal }}</div>
            </div>
            <div class="pdv-result-right">
              <div class="pdv-result-stock" :class="item.current_stock <= 0 ? 'stock-out' : item.current_stock < 3 ? 'stock-low' : 'stock-ok'">
                {{ item.current_stock }} un
              </div>
              <div class="pdv-result-price">
                <template v-if="isNativeCurrency(item.sale_currency)">
                  <span class="pdv-price-orig">{{ currencyLabel(item.sale_currency) }} {{ fmtNum(item.sale_price) }}</span>
                  <span class="pdv-price-gs">G$ {{ fmtNum(Math.round(item.sale_price * getRate(item.sale_currency))) }}</span>
                </template>
                <template v-else>
                  <span>{{ fmtGs(item.sale_price || 0) }}</span>
                </template>
              </div>
              <button class="pdv-result-add">+</button>
            </div>
          </div>
          <div v-if="searchQuery && !loadingSearch" class="pdv-result-avulso" @click="openAvulso()">
            <span>⚠</span> Produto não encontrado? Adicionar manualmente
          </div>
        </div>

        <!-- Placeholder when no search -->
        <div v-else-if="!searchQuery" class="pdv-search-hint">
          <div class="pdv-search-hint-icon">🔍</div>
          <p>Digite o nome, SKU ou escaneie o código de barras para adicionar produtos</p>
          <p class="pdv-shortcut-hint">Atalho: <kbd>F2</kbd> para focar a busca · <kbd>F5</kbd> para pagar</p>
        </div>

        <div v-else-if="loadingSearch" class="pdv-search-loading">Buscando…</div>

        <div v-else class="pdv-no-results">
          <p>Nenhum produto encontrado para "{{ searchQuery }}"</p>
          <button class="pdv-btn-avulso" @click="openAvulso(searchQuery)">
            + Adicionar como item avulso
          </button>
        </div>
      </div>

      <!-- RIGHT: Cart panel -->
      <div class="pdv-panel-cart" :class="{ 'mobile-hidden': mobileTab !== 'cart' }">

        <!-- Cart header -->
        <div class="pdv-cart-header">
          <span class="pdv-cart-title">Carrinho</span>
          <span class="pdv-cart-count">{{ pdv.cartCount }} item{{ pdv.cartCount !== 1 ? 's' : '' }}</span>
          <button v-if="pdv.cart.length" class="pdv-cart-clear" @click="confirmClear">🗑</button>
        </div>

        <!-- Client selector -->
        <div class="pdv-client-row">
          <input
            v-model="clienteNomeInput"
            type="text"
            placeholder="Cliente (opcional)"
            class="pdv-client-input"
            @input="pdv.clienteNome = clienteNomeInput"
          />
        </div>

        <!-- Cart items -->
        <div class="pdv-cart-items" v-if="pdv.cart.length">
          <div v-for="item in pdv.cart" :key="item.id" class="pdv-cart-item" :class="{ 'item-avulso': item.is_avulso }">
            <!-- Thumbnail -->
            <div class="pdv-ci-thumb">
              <img v-if="item.image_data" class="pdv-ci-img" :src="imgSrc(item.image_data)" />
              <div v-else class="pdv-ci-no-img">{{ item.item_name.charAt(0).toUpperCase() }}</div>
            </div>

            <div class="pdv-ci-body">
              <div class="pdv-ci-info">
                <div class="pdv-ci-name">
                  <span v-if="item.is_avulso" class="ci-avulso-badge">avulso</span>
                  {{ item.item_name }}
                </div>
                <div class="pdv-ci-meta">
                  <span v-if="item.item_size || item.item_color">{{ [item.item_size, item.item_color].filter(Boolean).join(' · ') }}</span>
                  <span v-if="isNativeCurrency(item.sale_currency)" class="ci-orig-price">
                    {{ currencyLabel(item.sale_currency) }} {{ fmtNum(item.original_price) }}
                  </span>
                </div>
              </div>

              <div class="pdv-ci-controls">
                <!-- Qty stepper -->
                <div class="pdv-qty-stepper">
                  <button class="qty-btn" @click="pdv.updateItemQty(item.id, item.quantity - 1)" :disabled="item.quantity <= 1">−</button>
                  <input
                    type="number" :value="item.quantity" min="1"
                    class="qty-input"
                    @change="pdv.updateItemQty(item.id, Number(($event.target as HTMLInputElement).value))"
                  />
                  <button class="qty-btn" @click="pdv.updateItemQty(item.id, item.quantity + 1)">+</button>
                </div>

                <!-- Price (inline editable, always in G$) -->
                <div class="pdv-ci-price-wrap">
                  <span class="pdv-ci-currency">G$</span>
                  <input
                    type="number" :value="item.unit_price_gs" min="0"
                    class="pdv-ci-price"
                    @change="pdv.updateItemPrice(item.id, Number(($event.target as HTMLInputElement).value))"
                    title="Editar preço em G$"
                  />
                </div>

                <!-- Line total -->
                <span class="pdv-ci-total">{{ fmtGs(item.quantity * item.unit_price_gs - item.discount_gs) }}</span>

                <!-- Remove -->
                <button class="pdv-ci-remove" @click="pdv.removeItem(item.id)" title="Remover">×</button>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="pdv-cart-empty">
          <div class="pdv-cart-empty-icon">🛒</div>
          <p>Carrinho vazio</p>
        </div>

        <!-- Totals -->
        <div class="pdv-totals" v-if="pdv.cart.length">
          <div class="pdv-total-row">
            <span>Subtotal</span>
            <span>{{ fmtGs(pdv.subtotal) }}</span>
          </div>
          <div v-if="pdv.discountGs > 0" class="pdv-total-row pdv-discount-row">
            <span>Desconto</span>
            <span>-{{ fmtGs(pdv.discountGs) }}</span>
          </div>
          <div class="pdv-total-row pdv-grand-total">
            <span>TOTAL</span>
            <span>{{ fmtGs(pdv.total) }}</span>
          </div>
        </div>

        <!-- Pay button -->
        <div class="pdv-pay-area">
          <button
            class="pdv-pay-btn"
            :disabled="!pdv.cart.length || pdv.loading"
            @click="openPayment"
          >
            <span v-if="pdv.loading">Processando…</span>
            <span v-else>💳 Pagar {{ pdv.cart.length ? fmtGs(pdv.total) : '' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Modals -->
    <BarcodeScanner
      v-if="showScanner"
      @barcode-detected="onBarcodeDetected"
      @close="showScanner = false"
    />

    <PDVAvulsoModal
      v-if="showAvulso"
      :scanned-code="avulsoCode"
      @add="onAvulsoAdd"
      @close="showAvulso = false"
    />

    <PDVPaymentModal
      v-if="showPayment"
      :total="pdv.total"
      :subtotal="pdv.subtotal"
      :discount="pdv.discountGs"
      :payments="pdv.payments"
      :loading="pdv.loading"
      :exchange-rates="exchangeRates"
      @confirm="onPaymentConfirm"
      @update:discount="pdv.discountGs = $event"
      @close="showPayment = false"
    />

    <PDVReceiptModal
      v-if="showReceipt && pdv.lastSale"
      :sale="pdv.lastSale"
      @close="showReceipt = false"
    />

    <!-- Toast -->
    <transition name="toast-fade">
      <div v-if="toast" class="pdv-toast" :class="`toast-${toast.type}`">{{ toast.msg }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { usePdvStore } from '@/stores/pdv'
import { inventoryAPI, exchangeRateAPI, type InventoryItem } from '@/services/api'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import PDVAvulsoModal from '@/components/pdv/PDVAvulsoModal.vue'
import PDVPaymentModal from '@/components/pdv/PDVPaymentModal.vue'
import PDVReceiptModal from '@/components/pdv/PDVReceiptModal.vue'
import type { CartPayment } from '@/stores/pdv'

const router = useRouter()
const pdv = usePdvStore()

const mobileTab = ref<'products' | 'cart'>('products')
const searchQuery = ref('')
const searchResults = ref<InventoryItem[]>([])
const loadingSearch = ref(false)
const showScanner = ref(false)
const showAvulso = ref(false)
const showPayment = ref(false)
const showReceipt = ref(false)
const avulsoCode = ref<string | null>(null)
const searchInput = ref<HTMLInputElement>()
const clienteNomeInput = ref('')
const exchangeRates = ref({ brl: 1150, usd: 6400, eur: 7200 })

interface Toast { msg: string; type: 'success' | 'error' }
const toast = ref<Toast | null>(null)
let toastTimer: ReturnType<typeof setTimeout>
let searchTimer: ReturnType<typeof setTimeout>

function showToast(msg: string, type: Toast['type'] = 'success') {
  clearTimeout(toastTimer)
  toast.value = { msg, type }
  toastTimer = setTimeout(() => { toast.value = null }, 2500)
}

// ── Currency helpers ───────────────────────────────────────────────────────────

function getRate(currency: string): number {
  const c = (currency || 'PYG').toUpperCase()
  if (c === 'USD') return exchangeRates.value.usd
  if (c === 'BRL') return exchangeRates.value.brl
  if (c === 'EUR') return exchangeRates.value.eur
  return 1
}

function isNativeCurrency(currency: string): boolean {
  const c = (currency || 'PYG').toUpperCase()
  return c !== 'PYG' && c !== 'GS' && c !== 'G$' && c !== ''
}

function currencyLabel(currency: string): string {
  const c = (currency || 'PYG').toUpperCase()
  const map: Record<string, string> = { USD: 'U$', BRL: 'R$', EUR: '€', PYG: 'G$', GS: 'G$' }
  return map[c] || c
}

function fmtGs(v: number) {
  return 'G$ ' + Math.round(v).toLocaleString('es-PY')
}
function fmtNum(v: number) {
  return v.toLocaleString('es-PY', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}
function fmtRateShort(v: number) {
  return (v / 1000).toLocaleString('es-PY', { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + 'k'
}

function imgSrc(data: string): string {
  if (!data) return ''
  if (data.startsWith('data:')) return data
  return `data:image/jpeg;base64,${data}`
}

// ── Search ────────────────────────────────────────────────────────────────────

function onSearchInput() {
  clearTimeout(searchTimer)
  if (!searchQuery.value.trim()) { searchResults.value = []; return }
  loadingSearch.value = true
  searchTimer = setTimeout(doSearch, 280)
}

async function doSearch() {
  try {
    const res = await inventoryAPI.getItems({ search: searchQuery.value, page_size: 20 })
    searchResults.value = res.items
  } catch {
    searchResults.value = []
  } finally {
    loadingSearch.value = false
  }
}

function onSearchEnter() {
  if (searchResults.value.length === 1) {
    addToCart(searchResults.value[0])
  }
}

function clearSearch() {
  searchQuery.value = ''
  searchResults.value = []
  searchInput.value?.focus()
}

// ── Cart actions ──────────────────────────────────────────────────────────────

function addToCart(item: InventoryItem) {
  const saleCurrency = item.sale_currency || 'PYG'
  const rate = getRate(saleCurrency)
  const priceGs = Math.round((item.sale_price || 0) * rate)

  pdv.addItem({
    item_id: item.id,
    item_name: item.name,
    item_sku: item.sku_internal || null,
    item_category: item.category || null,
    item_size: item.size || null,
    item_color: item.color || null,
    quantity: 1,
    unit_price_gs: priceGs,
    original_price_gs: priceGs,
    original_price: item.sale_price || 0,
    sale_currency: saleCurrency,
    image_data: item.image_data || null,
    discount_gs: 0,
    is_avulso: false,
    location: (item.stock_loja ?? 0) > 0 ? 'loja' : 'deposito',
  })
  showToast(`${item.name} adicionado`)
  clearSearch()
  mobileTab.value = 'cart'
}

function openAvulso(prefill?: string) {
  avulsoCode.value = prefill || null
  showAvulso.value = true
}

function onAvulsoAdd(item: any) {
  pdv.addItem(item)
  showAvulso.value = false
  showToast(`${item.item_name} adicionado`)
  mobileTab.value = 'cart'
}

function confirmClear() {
  if (confirm('Limpar o carrinho?')) pdv.clearCart()
}

// ── Barcode ───────────────────────────────────────────────────────────────────

async function onBarcodeDetected(code: string) {
  showScanner.value = false
  try {
    const results = await inventoryAPI.getByBarcode(code)
    if (results.length === 1) {
      addToCart(results[0])
    } else if (results.length > 1) {
      searchQuery.value = code
      searchResults.value = results
    } else {
      openAvulso(code)
    }
  } catch {
    openAvulso(code)
  }
}

// ── Payment ───────────────────────────────────────────────────────────────────

function openPayment() {
  showPayment.value = true
}

async function onPaymentConfirm(payments: CartPayment[], discount: number) {
  pdv.discountGs = discount
  pdv.payments.splice(0, pdv.payments.length, ...payments)
  showPayment.value = false
  try {
    await pdv.completeSale()
    showReceipt.value = true
    showToast('Venda concluída!', 'success')
  } catch (e: any) {
    showToast(e?.response?.data?.detail || 'Erro ao finalizar venda', 'error')
    showPayment.value = true
  }
}

// ── Keyboard shortcuts ────────────────────────────────────────────────────────

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'F2' || (e.key === '/' && !['INPUT', 'TEXTAREA'].includes((e.target as Element).tagName))) {
    e.preventDefault()
    searchInput.value?.focus()
    mobileTab.value = 'products'
  }
  if (e.key === 'F5') {
    e.preventDefault()
    if (pdv.cart.length) openPayment()
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  searchInput.value?.focus()
  try {
    const rates = await exchangeRateAPI.getCurrentRates()
    if (rates.usd_to_pyg) exchangeRates.value.usd = rates.usd_to_pyg
    if (rates.usd_to_pyg && rates.usd_to_brl && rates.usd_to_brl > 0) {
      exchangeRates.value.brl = Math.round(rates.usd_to_pyg / rates.usd_to_brl)
    }
    if (rates.eur_to_usd && rates.usd_to_pyg) {
      exchangeRates.value.eur = Math.round(rates.eur_to_usd * rates.usd_to_pyg)
    }
  } catch { /* keep defaults */ }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
/* ── Root ─────────────────────────────────────────────────────────────────── */
.pdv-root {
  display: flex; flex-direction: column;
  height: 100dvh; height: 100vh;
  background: #f3f4f6; overflow: hidden;
}

/* ── Header ───────────────────────────────────────────────────────────────── */
.pdv-header {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.5rem 0.875rem;
  background: #1f2937; color: white;
  flex-shrink: 0; min-height: 44px;
}
.pdv-back-btn {
  display: flex; align-items: center; gap: 0.3rem;
  background: rgba(255,255,255,0.1); border: none;
  color: #d1d5db; padding: 0.3rem 0.625rem;
  border-radius: 0.375rem; cursor: pointer; font-size: 0.8rem; font-weight: 600;
  transition: background 0.15s; white-space: nowrap;
}
.pdv-back-btn:hover { background: rgba(255,255,255,0.2); color: white; }
.pdv-header-title {
  font-size: 0.95rem; font-weight: 800; color: white;
  letter-spacing: 0.05em; flex: 1;
}
.pdv-header-rates {
  display: flex; gap: 0.75rem;
  font-size: 0.72rem; color: #9ca3af;
  font-family: monospace; white-space: nowrap;
}
.pdv-header-rates span { background: rgba(255,255,255,0.07); padding: 0.15rem 0.4rem; border-radius: 0.25rem; }

/* ── Mobile tabs ──────────────────────────────────────────────────────────── */
.pdv-tab-bar {
  display: flex; background: white;
  border-bottom: 2px solid #e5e7eb;
  flex-shrink: 0;
}
.pdv-tab {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 0.4rem;
  padding: 0.75rem 0.5rem; border: none; background: none;
  font-size: 0.85rem; font-weight: 600; color: #6b7280; cursor: pointer;
  position: relative; transition: color 0.15s;
}
.pdv-tab.active { color: #f97316; border-bottom: 2px solid #f97316; margin-bottom: -2px; }
.pdv-tab-badge {
  position: absolute; top: 6px; right: calc(50% - 28px);
  background: #f97316; color: white; border-radius: 9999px;
  font-size: 0.6rem; font-weight: 800; min-width: 16px; height: 16px;
  display: flex; align-items: center; justify-content: center; padding: 0 3px;
}
.mobile-only { display: none; }

/* ── Layout ───────────────────────────────────────────────────────────────── */
.pdv-layout {
  display: grid;
  grid-template-columns: 60fr 40fr;
  flex: 1; overflow: hidden; gap: 0;
}

/* ── Product panel ────────────────────────────────────────────────────────── */
.pdv-panel-products {
  display: flex; flex-direction: column; overflow: hidden;
  border-right: 1px solid #e5e7eb; background: white;
}

.pdv-search-bar {
  display: flex; gap: 0.5rem; padding: 0.75rem;
  border-bottom: 1px solid #f3f4f6; background: white; flex-shrink: 0;
}
.pdv-search-input-wrap {
  flex: 1; display: flex; align-items: center;
  border: 2px solid #e5e7eb; border-radius: 0.625rem; overflow: hidden;
  transition: border-color 0.15s; background: #f9fafb;
}
.pdv-search-input-wrap:focus-within { border-color: #f97316; background: white; }
.pdv-search-icon { width: 18px; height: 18px; color: #9ca3af; margin: 0 0.5rem; flex-shrink: 0; }
.pdv-search-input { flex: 1; border: none; outline: none; padding: 0.625rem 0.5rem 0.625rem 0; font-size: 0.9rem; background: transparent; }
.pdv-search-clear { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 0 0.5rem; font-size: 1.2rem; }
.pdv-scan-btn {
  width: 44px; height: 44px; border-radius: 0.625rem;
  border: 2px solid #e5e7eb; background: white; cursor: pointer; display: flex;
  align-items: center; justify-content: center; color: #374151; flex-shrink: 0;
}
.pdv-scan-btn:hover { border-color: #f97316; color: #f97316; }

.pdv-results { flex: 1; overflow-y: auto; }
.pdv-result-row {
  display: flex; align-items: center; gap: 0.625rem;
  padding: 0.5rem 0.75rem; border-bottom: 1px solid #f3f4f6;
  cursor: pointer; transition: background 0.1s;
}
.pdv-result-row:hover { background: #fff7ed; }

/* Thumbnail */
.pdv-result-thumb {
  width: 46px; height: 46px; border-radius: 0.375rem; overflow: hidden;
  flex-shrink: 0; background: #f3f4f6; border: 1px solid #e5e7eb;
}
.pdv-result-img { width: 100%; height: 100%; object-fit: cover; }
.pdv-result-no-img {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  font-size: 1.1rem; font-weight: 800; color: #9ca3af; background: #f3f4f6;
}

.pdv-result-left { flex: 1; min-width: 0; }
.pdv-result-name { font-weight: 600; font-size: 0.85rem; color: #111827; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pdv-result-meta { font-size: 0.72rem; color: #9ca3af; }
.pdv-result-sku { font-size: 0.65rem; color: #d1d5db; font-family: monospace; }
.pdv-result-right { display: flex; align-items: center; gap: 0.5rem; flex-shrink: 0; }
.pdv-result-stock { font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.375rem; border-radius: 0.3rem; }
.stock-ok  { background: #d1fae5; color: #065f46; }
.stock-low { background: #fef3c7; color: #92400e; }
.stock-out { background: #fee2e2; color: #991b1b; }
.pdv-result-price { text-align: right; }
.pdv-price-orig { display: block; font-size: 0.82rem; font-weight: 700; color: #1d4ed8; white-space: nowrap; }
.pdv-price-gs { display: block; font-size: 0.7rem; color: #6b7280; white-space: nowrap; }
.pdv-result-add {
  width: 28px; height: 28px; border-radius: 50%;
  border: none; background: #f97316; color: white;
  font-size: 1.1rem; cursor: pointer; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.pdv-result-avulso {
  padding: 0.75rem 0.875rem; font-size: 0.8rem; color: #d97706;
  border-top: 1px dashed #fcd34d; cursor: pointer; text-align: center;
}
.pdv-result-avulso:hover { background: #fffbeb; }

.pdv-search-hint { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; text-align: center; }
.pdv-search-hint-icon { font-size: 3rem; margin-bottom: 0.75rem; }
.pdv-search-hint p { color: #9ca3af; font-size: 0.88rem; margin: 0.25rem 0; }
.pdv-shortcut-hint { font-size: 0.75rem !important; color: #d1d5db !important; }
kbd { background: #f3f4f6; border: 1px solid #d1d5db; border-radius: 0.25rem; padding: 0.1rem 0.3rem; font-family: monospace; font-size: 0.75rem; }
.pdv-search-loading { padding: 1.5rem; text-align: center; color: #9ca3af; font-size: 0.85rem; }
.pdv-no-results { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 2rem; gap: 1rem; }
.pdv-no-results p { color: #9ca3af; font-size: 0.88rem; margin: 0; }
.pdv-btn-avulso { padding: 0.5rem 1.25rem; background: #fef3c7; color: #92400e; border: 1.5px solid #fcd34d; border-radius: 0.5rem; font-weight: 600; cursor: pointer; }

/* ── Cart panel ───────────────────────────────────────────────────────────── */
.pdv-panel-cart {
  display: flex; flex-direction: column; overflow: hidden; background: white;
}

.pdv-cart-header {
  display: flex; align-items: center; gap: 0.5rem;
  padding: 0.75rem 0.875rem; border-bottom: 1px solid #f3f4f6; flex-shrink: 0;
}
.pdv-cart-title { font-size: 0.95rem; font-weight: 700; color: #111827; }
.pdv-cart-count { font-size: 0.75rem; color: #9ca3af; flex: 1; }
.pdv-cart-clear { background: none; border: none; cursor: pointer; color: #dc2626; font-size: 1rem; padding: 0.2rem; }

.pdv-client-row { padding: 0.5rem 0.875rem; border-bottom: 1px solid #f3f4f6; flex-shrink: 0; }
.pdv-client-input {
  width: 100%; box-sizing: border-box;
  border: 1.5px solid #e5e7eb; border-radius: 0.4rem;
  padding: 0.35rem 0.6rem; font-size: 0.8rem; outline: none; color: #374151;
}
.pdv-client-input:focus { border-color: #f97316; }

.pdv-cart-items { flex: 1; overflow-y: auto; }
.pdv-cart-item {
  display: flex; gap: 0.5rem; padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #f3f4f6; align-items: flex-start;
}
.pdv-cart-item.item-avulso { background: #fffbeb; }

/* Cart thumbnail */
.pdv-ci-thumb {
  width: 40px; height: 40px; border-radius: 0.3rem; overflow: hidden;
  flex-shrink: 0; background: #f3f4f6; border: 1px solid #e5e7eb; margin-top: 2px;
}
.pdv-ci-img { width: 100%; height: 100%; object-fit: cover; }
.pdv-ci-no-img {
  width: 100%; height: 100%; display: flex; align-items: center; justify-content: center;
  font-size: 0.9rem; font-weight: 800; color: #9ca3af;
}

.pdv-ci-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.3rem; }
.pdv-ci-info { display: flex; flex-direction: column; }
.pdv-ci-name { font-size: 0.83rem; font-weight: 600; color: #111827; display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; }
.ci-avulso-badge { background: #fef3c7; color: #92400e; font-size: 0.6rem; font-weight: 700; padding: 0.1rem 0.3rem; border-radius: 0.2rem; }
.pdv-ci-meta { font-size: 0.68rem; color: #9ca3af; display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.ci-orig-price { background: #dbeafe; color: #1e40af; padding: 0.1rem 0.3rem; border-radius: 0.2rem; font-weight: 700; font-size: 0.68rem; }

.pdv-ci-controls { display: flex; align-items: center; gap: 0.4rem; flex-wrap: wrap; }

.pdv-qty-stepper { display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; }
.qty-btn { width: 26px; height: 26px; border: none; background: #f9fafb; cursor: pointer; font-size: 1rem; color: #374151; }
.qty-btn:hover:not(:disabled) { background: #f3f4f6; }
.qty-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.qty-input { width: 34px; border: none; outline: none; text-align: center; font-size: 0.85rem; font-weight: 600; padding: 0; height: 26px; }

.pdv-ci-price-wrap { display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; flex: 1; min-width: 90px; }
.pdv-ci-currency { padding: 0 0.3rem; font-size: 0.68rem; color: #9ca3af; background: #f9fafb; border-right: 1px solid #e5e7eb; white-space: nowrap; }
.pdv-ci-price { border: none; outline: none; flex: 1; padding: 0.25rem 0.3rem; font-size: 0.83rem; min-width: 0; }
.pdv-ci-price:focus { background: #fff7ed; }
.pdv-ci-total { font-size: 0.85rem; font-weight: 700; color: #111827; white-space: nowrap; margin-left: auto; }
.pdv-ci-remove { background: none; border: none; color: #dc2626; cursor: pointer; font-size: 1.1rem; padding: 0; }

.pdv-cart-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem; color: #9ca3af; }
.pdv-cart-empty-icon { font-size: 2.5rem; }
.pdv-cart-empty p { margin: 0; font-size: 0.88rem; }

.pdv-totals { padding: 0.625rem 0.875rem; border-top: 1px solid #f3f4f6; background: #f9fafb; flex-shrink: 0; }
.pdv-total-row { display: flex; justify-content: space-between; font-size: 0.85rem; color: #374151; padding: 0.15rem 0; }
.pdv-discount-row { color: #dc2626; }
.pdv-grand-total { font-size: 1rem; font-weight: 800; color: #111827; border-top: 1px solid #e5e7eb; margin-top: 0.25rem; padding-top: 0.375rem; }

.pdv-pay-area { padding: 0.75rem; flex-shrink: 0; border-top: 1px solid #f3f4f6; }
.pdv-pay-btn {
  width: 100%; padding: 0.875rem;
  background: linear-gradient(135deg, #f97316, #ea580c);
  color: white; border: none; border-radius: 0.75rem;
  font-size: 1rem; font-weight: 800; cursor: pointer;
  transition: opacity 0.15s; letter-spacing: 0.01em;
}
.pdv-pay-btn:hover:not(:disabled) { opacity: 0.9; }
.pdv-pay-btn:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Toast ────────────────────────────────────────────────────────────────── */
.pdv-toast {
  position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%);
  padding: 0.6rem 1.25rem; border-radius: 2rem; font-size: 0.85rem; font-weight: 600;
  z-index: 9999; pointer-events: none; white-space: nowrap; box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}
.toast-success { background: #111827; color: white; }
.toast-error   { background: #dc2626; color: white; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: all 0.25s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

/* ── Mobile ───────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .mobile-only { display: flex; }
  .pdv-layout { grid-template-columns: 1fr; }
  .pdv-panel-products, .pdv-panel-cart {
    height: calc(100dvh - 100px); height: calc(100vh - 100px);
  }
  .mobile-hidden { display: none !important; }
  .pdv-panel-products, .pdv-panel-cart { border-right: none; }
  .pdv-header-rates { display: none; }
  .pdv-header-title { font-size: 0.85rem; }
}
</style>
