<template>
  <div class="pdv-root">

    <!-- PDV Header -->
    <div class="pdv-header">
      <button class="pdv-back-btn" @click="router.push('/dashboard')">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="16" height="16"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
        Dashboard
      </button>
      <span class="pdv-header-title">PDV</span>

      <!-- Exchange rate button (same as dashboard) -->
      <button class="pdv-rate-btn" @click="openRateModal" :title="canEditRates ? 'Editar taxas de câmbio' : 'Taxas de câmbio'">
        <span class="pdv-rate-pill">🇺🇸 U$→G$ {{ rateUsd.toLocaleString('es-PY') }}</span>
        <span class="pdv-rate-pill">🇧🇷 U$→R$ {{ currencyStore.exchangeRates['R$'].toFixed(2) }}</span>
        <svg v-if="canEditRates" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="13" height="13" class="pdv-rate-edit-icon"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/></svg>
      </button>
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
        <div class="pdv-search-bar">
          <div class="pdv-search-input-wrap">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" class="pdv-search-icon"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <input ref="searchInput" v-model="searchQuery" type="text"
              placeholder="Buscar produto, SKU ou código de barras… (F2)"
              class="pdv-search-input" @keydown.enter="onSearchEnter" @input="onSearchInput" />
            <button v-if="searchQuery" class="pdv-search-clear" @click="clearSearch">×</button>
          </div>
          <button class="pdv-scan-btn" @click="showScanner = true" title="Escanear código">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v1m6 11h2m-6 0h-2v4m0-11v3m0 0h.01M12 12h4.01M16 20h2M4 12v.01M12 8h.01M4 8h.01M20 8h.01M4 4h4M20 4h-4M4 20h4M20 20h-4"/></svg>
          </button>
        </div>

        <div v-if="searchResults.length" class="pdv-results">
          <div v-for="item in searchResults" :key="item.id" class="pdv-result-row" @click="addToCart(item)">
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
                  <span class="pdv-price-gs">≈ G$ {{ fmtNum(Math.round(item.sale_price * getRate(item.sale_currency))) }}</span>
                </template>
                <template v-else>
                  <span class="pdv-price-orig">{{ fmtGs(item.sale_price || 0) }}</span>
                </template>
              </div>
              <button class="pdv-result-add">+</button>
            </div>
          </div>
          <div v-if="searchQuery && !loadingSearch" class="pdv-result-avulso" @click="openAvulso()">
            <span>⚠</span> Produto não encontrado? Adicionar manualmente
          </div>
        </div>

        <div v-else-if="!searchQuery" class="pdv-search-hint">
          <div class="pdv-search-hint-icon">🔍</div>
          <p>Digite o nome, SKU ou escaneie o código de barras para adicionar produtos</p>
          <p class="pdv-shortcut-hint">Atalho: <kbd>F2</kbd> busca · <kbd>F5</kbd> pagar · <kbd>Esc</kbd> voltar</p>
        </div>
        <div v-else-if="loadingSearch" class="pdv-search-loading">Buscando…</div>
        <div v-else class="pdv-no-results">
          <p>Nenhum produto encontrado para "{{ searchQuery }}"</p>
          <button class="pdv-btn-avulso" @click="openAvulso(searchQuery)">+ Adicionar como item avulso</button>
        </div>
      </div>

      <!-- RIGHT: Cart + Payment (unified panel) -->
      <div class="pdv-panel-cart" :class="{ 'mobile-hidden': mobileTab !== 'cart' }">

        <!-- Fixed header -->
        <div class="pdv-cart-header">
          <span class="pdv-cart-title">Carrinho</span>
          <span class="pdv-cart-count">{{ pdv.cartCount }} item{{ pdv.cartCount !== 1 ? 's' : '' }}</span>
          <button v-if="pdv.cart.length" class="pdv-cart-clear" @click="confirmClear">🗑</button>
        </div>

        <!-- Scrollable body -->
        <div class="pdv-cart-scroll">

          <!-- Client -->
          <div class="pdv-client-row">
            <input v-model="clienteNomeInput" type="text" placeholder="Cliente (opcional)"
              class="pdv-client-input" @input="pdv.clienteNome = clienteNomeInput" />
          </div>

          <!-- Cart items -->
          <div v-if="pdv.cart.length" class="pdv-cart-items">
            <div v-for="item in pdv.cart" :key="item.id" class="pdv-cart-item" :class="{ 'item-avulso': item.is_avulso }">
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
                    <span v-if="isNativeCurrency(item.sale_currency)" class="ci-gs-equiv">≈ {{ fmtGs(item.unit_price_gs) }}</span>
                  </div>
                </div>
                <div class="pdv-ci-controls">
                  <div class="pdv-qty-stepper">
                    <button class="qty-btn" @click="pdv.updateItemQty(item.id, item.quantity - 1)" :disabled="item.quantity <= 1">−</button>
                    <input type="number" :value="item.quantity" min="1" class="qty-input"
                      @change="pdv.updateItemQty(item.id, Number(($event.target as HTMLInputElement).value))" />
                    <button class="qty-btn" @click="pdv.updateItemQty(item.id, item.quantity + 1)">+</button>
                  </div>
                  <div class="pdv-ci-price-wrap">
                    <span class="pdv-ci-currency">{{ currencyLabel(item.sale_currency) }}</span>
                    <input type="number" :value="item.original_price" min="0" class="pdv-ci-price"
                      @change="pdv.updateItemOriginalPrice(item.id, Number(($event.target as HTMLInputElement).value), getRate(item.sale_currency))" />
                  </div>
                  <span class="pdv-ci-total">{{ fmtGs(item.quantity * item.unit_price_gs - item.discount_gs) }}</span>
                  <button class="pdv-ci-remove" @click="pdv.removeItem(item.id)">×</button>
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
            <div class="pdv-total-row"><span>Subtotal</span><span>{{ fmtGs(pdv.subtotal) }}</span></div>
            <div v-if="pdv.discountGs > 0" class="pdv-total-row pdv-discount-row">
              <span>Desconto</span><span>-{{ fmtGs(pdv.discountGs) }}</span>
            </div>
            <div class="pdv-total-row pdv-grand-total">
              <span>TOTAL</span><span>{{ fmtGs(pdv.total) }}</span>
            </div>
            <div class="pdv-total-usd">≈ U$ {{ fmtNum(pdv.total / rateUsd) }}</div>
          </div>

          <!-- ── Payment section ── -->
          <div class="pdv-payment-section" v-if="pdv.cart.length">

            <div class="pdv-payment-divider">💳 Pagamento</div>

            <!-- Discount -->
            <div class="pay-discount-row">
              <span class="pay-discount-label">Desconto (G$)</span>
              <div class="pay-discount-input-wrap">
                <span class="pay-currency-prefix">G$</span>
                <input v-model.number="pdv.discountGs" type="number" min="0" class="pay-discount-input" placeholder="0" />
              </div>
            </div>

            <!-- Payments added -->
            <div class="pay-entries-inline">
              <div v-for="p in localPayments" :key="p.id" class="pay-entry">
                <div class="pay-entry-method">
                  <span class="pay-method-badge" :class="`method-${p.method}`">{{ methodLabel(p.method) }}</span>
                  <span v-if="p.reference" class="pay-entry-ref">{{ p.reference }}</span>
                </div>
                <div class="pay-entry-amounts">
                  <span v-if="p.currency !== 'GS'" class="pay-orig-amount">{{ p.currency }} {{ fmtNum(p.amount_original) }}</span>
                  <span class="pay-gs-amount">{{ fmtGs(p.amount_gs) }}</span>
                </div>
                <button class="pay-entry-remove" @click="removePayment(p.id)">×</button>
              </div>
              <div v-if="!localPayments.length" class="pay-empty">Nenhum pagamento adicionado</div>
            </div>

            <!-- Add payment form -->
            <div class="pay-add-section">
              <div class="pay-add-row">
                <select v-model="newMethod" class="pay-select">
                  <option v-for="m in PAYMENT_METHODS" :key="m.value" :value="m.value">{{ m.label }}</option>
                </select>
                <select v-model="newCurrency" class="pay-select pay-select-sm">
                  <option value="USD">U$</option>
                  <option value="GS">G$</option>
                  <option value="BRL">R$</option>
                  <option value="EUR">€</option>
                </select>
              </div>
              <div class="pay-add-row">
                <div class="pay-input-wrap">
                  <span class="pay-currency-prefix">{{ currencySymbol }}</span>
                  <input v-model.number="newAmount" ref="amountInput" type="number" min="0"
                    class="pay-amount-input"
                    :placeholder="payRemaining > 0 ? fmtNum(remainingInCurrency) : '0'"
                    @keydown.enter="addPayment" />
                </div>
                <button class="pay-btn-total" @click="fillTotal" title="Preencher valor restante">Total</button>
                <input v-if="showReference" v-model="newReference" type="text" class="pay-ref-input" :placeholder="referencePlaceholder" />
                <button class="pay-btn-add" @click="addPayment" :disabled="!newAmount">+ Add</button>
              </div>
              <div v-if="newCurrency !== 'GS'" class="pay-rate-row">
                <span>Taxa:</span>
                <input v-model.number="newRate" type="number" min="0" step="0.01" class="pay-rate-input" />
                <span>{{ newCurrency }}/G$</span>
                <span class="pay-converted">= {{ fmtGs(newAmount * newRate) }}</span>
              </div>
            </div>

            <!-- Payment summary -->
            <div class="pay-summary-inline">
              <div class="pay-sum-row">
                <span>Pago</span>
                <span :class="payTotalPaid >= pdv.total ? 'pay-ok' : 'pay-short'">{{ fmtGs(payTotalPaid) }}</span>
              </div>
              <div v-if="payTroco > 0" class="pay-sum-row pay-troco-row">
                <span>Troco</span><span class="pay-troco">{{ fmtGs(payTroco) }}</span>
              </div>
              <div v-if="payRemaining > 0" class="pay-sum-row pay-remaining-row">
                <span>Faltando</span><span class="pay-remaining">{{ fmtGs(payRemaining) }}</span>
              </div>
            </div>

          </div>

        </div><!-- end pdv-cart-scroll -->

        <!-- Sticky confirm button -->
        <div class="pdv-pay-area">
          <button class="pay-confirm-btn"
            :disabled="!canConfirmPayment || pdv.loading || !pdv.cart.length"
            @click="confirmPayment">
            <span v-if="pdv.loading">Processando…</span>
            <span v-else-if="!pdv.cart.length">Carrinho vazio</span>
            <span v-else-if="payRemaining > 0">Faltando {{ fmtGs(payRemaining) }}</span>
            <span v-else>✓ Confirmar e imprimir</span>
          </button>
        </div>

      </div>
    </div>

    <!-- Modals -->
    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />
    <PDVAvulsoModal v-if="showAvulso" :scanned-code="avulsoCode" @add="onAvulsoAdd" @close="showAvulso = false" />
    <PDVReceiptModal v-if="showReceipt && pdv.lastSale" :sale="pdv.lastSale" @close="showReceipt = false" />

    <!-- Exchange Rate Modal (same as dashboard) -->
    <div v-if="showRateModal" class="er-overlay" @click.self="showRateModal = false">
      <div class="er-modal">
        <div class="er-header">
          <h2>Taxas de Câmbio</h2>
          <button class="er-close" @click="showRateModal = false">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
          </button>
        </div>
        <div class="er-body">
          <div v-if="rateError" class="er-error">{{ rateError }}</div>
          <div class="er-form">
            <div class="er-group">
              <label>USD → Guarani (G$)</label>
              <input type="number" step="1" v-model.number="editingRates.usd_to_pyg" placeholder="6400" class="er-input" :disabled="!canEditRates" />
            </div>
            <div class="er-group">
              <label>USD → Real (R$)</label>
              <input type="number" step="0.01" v-model.number="editingRates.usd_to_brl" placeholder="5.85" class="er-input" :disabled="!canEditRates" />
            </div>
            <div class="er-group">
              <label>EUR → USD ($)</label>
              <input type="number" step="0.001" v-model.number="editingRates.eur_to_usd" placeholder="1.085" class="er-input" :disabled="!canEditRates" />
            </div>
            <div class="er-group">
              <label>EUR → Real (R$)</label>
              <input type="number" step="0.01" v-model.number="editingRates.eur_to_brl" placeholder="6.20" class="er-input" :disabled="!canEditRates" />
            </div>
          </div>
        </div>
        <div class="er-footer">
          <button class="er-btn-cancel" @click="showRateModal = false">Cancelar</button>
          <button v-if="canEditRates" class="er-btn-save" @click="saveRates" :disabled="savingRates">
            <span v-if="savingRates">Salvando…</span>
            <span v-else>Salvar Taxas</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Toast -->
    <transition name="toast-fade">
      <div v-if="toast" class="pdv-toast" :class="`toast-${toast.type}`">{{ toast.msg }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { usePdvStore } from '@/stores/pdv'
import { useAuthStore } from '@/stores/auth'
import { useCurrencyStore } from '@/stores/currency'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import PDVAvulsoModal from '@/components/pdv/PDVAvulsoModal.vue'
import PDVReceiptModal from '@/components/pdv/PDVReceiptModal.vue'
import type { CartPayment } from '@/stores/pdv'

const router = useRouter()
const pdv = usePdvStore()
const authStore = useAuthStore()
const currencyStore = useCurrencyStore()

// ── Panel / tab state ─────────────────────────────────────────────────────────
const mobileTab = ref<'products' | 'cart'>('products')

// ── Search ────────────────────────────────────────────────────────────────────
const searchQuery = ref('')
const searchResults = ref<InventoryItem[]>([])
const loadingSearch = ref(false)
const showScanner = ref(false)
const showAvulso = ref(false)
const showReceipt = ref(false)
const avulsoCode = ref<string | null>(null)
const searchInput = ref<HTMLInputElement>()
const clienteNomeInput = ref('')

// ── Exchange rates (from shared currency store) ───────────────────────────────
// G$ per 1 USD
const rateUsd = computed(() => currencyStore.exchangeRates['G$'])
// G$ per 1 BRL
const rateBrl = computed(() =>
  currencyStore.exchangeRates['R$'] > 0
    ? Math.round(currencyStore.exchangeRates['G$'] / currencyStore.exchangeRates['R$'])
    : 1150
)
// G$ per 1 EUR  (store['EUR'] = EUR per USD, so G$/EUR = G$/USD / EUR/USD)
const rateEur = computed(() =>
  currencyStore.exchangeRates['EUR'] > 0
    ? Math.round(currencyStore.exchangeRates['G$'] / currencyStore.exchangeRates['EUR'])
    : 7900
)

// ── Exchange rate modal ───────────────────────────────────────────────────────
const showRateModal = ref(false)
const savingRates = ref(false)
const rateError = ref<string | null>(null)
const editingRates = ref({ usd_to_pyg: 0, usd_to_brl: 0, eur_to_usd: 0, eur_to_brl: 0 })

const canEditRates = computed(() =>
  !!authStore.user && ['ADMIN', 'GERENTE'].includes(authStore.user.role)
)

function openRateModal() {
  const rates = currencyStore.exchangeRates
  // rates['EUR'] = EUR per USD (e.g. 0.92), so eur_to_usd = 1 / rates['EUR']
  const eurPerUsd = rates['EUR'] > 0 ? rates['EUR'] : 0.92
  const eurToUsd = 1 / eurPerUsd
  editingRates.value = {
    usd_to_pyg: rates['G$'],
    usd_to_brl: rates['R$'],
    eur_to_usd: Math.round(eurToUsd * 10000) / 10000,
    eur_to_brl: Math.round(rates['R$'] / eurPerUsd * 100) / 100,
  }
  rateError.value = null
  showRateModal.value = true
}

async function saveRates() {
  if (!canEditRates.value) return
  try {
    savingRates.value = true
    rateError.value = null
    await currencyStore.updateRatesAPI({
      usd_to_pyg: editingRates.value.usd_to_pyg || undefined,
      usd_to_brl: editingRates.value.usd_to_brl || undefined,
      eur_to_usd: editingRates.value.eur_to_usd || undefined,
      eur_to_brl: editingRates.value.eur_to_brl || undefined,
    })
    showRateModal.value = false
    showToast('Taxas atualizadas', 'success')
  } catch (e: any) {
    rateError.value = e?.response?.data?.detail || e?.message || 'Erro ao salvar taxas'
  } finally {
    savingRates.value = false
  }
}

// ── Payment state ────────────────────────────────────────────────────────────
const localPayments = ref<CartPayment[]>([])
const newMethod = ref('cash_usd')
const newCurrency = ref('USD')
const newAmount = ref<number>(0)
const newRate = ref(0)
const newReference = ref('')
const amountInput = ref<HTMLInputElement>()

const PAYMENT_METHODS = [
  { value: 'cash_usd',     label: '💵 Dinheiro U$' },
  { value: 'cash_gs',      label: '💵 Dinheiro G$' },
  { value: 'cash_brl',     label: '💵 Dinheiro R$' },
  { value: 'cash_eur',     label: '💵 Dinheiro €' },
  { value: 'card',         label: '💳 Cartão' },
  { value: 'pix',          label: '📱 PIX' },
  { value: 'mercadopago',  label: '🛒 MercadoPago' },
  { value: 'transfer_br',  label: '🏦 Transf. Brasil' },
  { value: 'transfer_py',  label: '🏦 Transf. Paraguai' },
  { value: 'pix_cambista', label: '🔄 PIX Cambista' },
  { value: 'qr_py',        label: '📲 QR Paraguai' },
  { value: 'tigo_money',   label: '📲 Tigo Money' },
  { value: 'fiado',        label: '📒 Fiado' },
]

function methodCurrency(m: string) {
  if (['cash_brl', 'pix', 'transfer_br', 'pix_cambista', 'mercadopago'].includes(m)) return 'BRL'
  if (m === 'cash_gs' || m === 'transfer_py' || m === 'qr_py' || m === 'tigo_money') return 'GS'
  if (m === 'cash_eur') return 'EUR'
  return 'USD' // cash_usd, card default to USD
}
function defaultRate(c: string) {
  if (c === 'BRL') return rateBrl.value
  if (c === 'USD') return rateUsd.value
  if (c === 'EUR') return rateEur.value
  return 1
}
function methodLabel(m: string) {
  return PAYMENT_METHODS.find(x => x.value === m)?.label.replace(/^\S+\s/, '') || m
}

watch(newMethod, (m) => {
  newCurrency.value = methodCurrency(m)
  newRate.value = defaultRate(newCurrency.value)
  newReference.value = ''
})
watch(newCurrency, (c) => { newRate.value = defaultRate(c) })
watch(() => pdv.cart.length, (len) => { if (len === 0) resetPayment() })

const currencySymbol = computed(() => ({ GS: 'G$', BRL: 'R$', USD: 'U$', EUR: '€' }[newCurrency.value] ?? newCurrency.value))
const showReference = computed(() => ['card', 'pix', 'transfer_br', 'transfer_py', 'pix_cambista', 'mercadopago'].includes(newMethod.value))
const referencePlaceholder = computed(() => {
  if (newMethod.value === 'card') return 'Últimos 4 dígitos'
  if (['pix', 'pix_cambista', 'mercadopago'].includes(newMethod.value)) return 'Chave / ref.'
  return 'Referência'
})

const payTotalPaid = computed(() => localPayments.value.reduce((s, p) => s + p.amount_gs, 0))
const payRemaining = computed(() => Math.max(0, pdv.total - payTotalPaid.value))
const payTroco = computed(() => Math.max(0, payTotalPaid.value - pdv.total))
const remainingInCurrency = computed(() =>
  newCurrency.value === 'GS' ? payRemaining.value : payRemaining.value / (newRate.value || 1)
)
const canConfirmPayment = computed(() => payTotalPaid.value >= pdv.total && localPayments.value.length > 0)

function fillTotal() {
  newAmount.value = Math.ceil(remainingInCurrency.value * 100) / 100
  nextTick(() => amountInput.value?.focus())
}

function addPayment() {
  if (!newAmount.value || newAmount.value <= 0) return
  const rate = newCurrency.value === 'GS' ? 1 : newRate.value
  const amountGs = newCurrency.value === 'GS' ? newAmount.value : newAmount.value * rate
  localPayments.value.push({
    id: crypto.randomUUID(),
    method: newMethod.value,
    currency: newCurrency.value,
    amount_original: newAmount.value,
    exchange_rate: rate,
    amount_gs: Math.round(amountGs),
    cambista_id: null,
    reference: newReference.value || null,
    label: methodLabel(newMethod.value),
  })
  newAmount.value = 0
  newReference.value = ''
  nextTick(() => amountInput.value?.focus())
}

function removePayment(id: string) {
  localPayments.value = localPayments.value.filter(p => p.id !== id)
}

// ── Toast ─────────────────────────────────────────────────────────────────────
interface Toast { msg: string; type: 'success' | 'error' }
const toast = ref<Toast | null>(null)
let toastTimer: ReturnType<typeof setTimeout>
let searchTimer: ReturnType<typeof setTimeout>

function showToast(msg: string, type: Toast['type'] = 'success') {
  clearTimeout(toastTimer)
  toast.value = { msg, type }
  toastTimer = setTimeout(() => { toast.value = null }, 2500)
}

// ── Currency helpers ──────────────────────────────────────────────────────────
function getRate(currency: string): number {
  const c = (currency || 'PYG').toUpperCase()
  if (c === 'USD') return rateUsd.value
  if (c === 'BRL') return rateBrl.value
  if (c === 'EUR') return rateEur.value
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
function fmtGs(v: number) { return 'G$ ' + Math.round(v).toLocaleString('es-PY') }
function fmtNum(v: number) { return v.toLocaleString('es-PY', { minimumFractionDigits: 0, maximumFractionDigits: 2 }) }
function imgSrc(data: string): string {
  return data.startsWith('data:') ? data : `data:image/jpeg;base64,${data}`
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
  } catch { searchResults.value = [] }
  finally { loadingSearch.value = false }
}
function onSearchEnter() {
  if (searchResults.value.length === 1) addToCart(searchResults.value[0])
}
function clearSearch() {
  searchQuery.value = ''
  searchResults.value = []
  searchInput.value?.focus()
}

// ── Cart ──────────────────────────────────────────────────────────────────────
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
function openAvulso(prefill?: string) { avulsoCode.value = prefill || null; showAvulso.value = true }
function onAvulsoAdd(item: any) {
  pdv.addItem(item)
  showAvulso.value = false
  showToast(`${item.item_name} adicionado`)
  mobileTab.value = 'cart'
}
function confirmClear() { if (confirm('Limpar o carrinho?')) pdv.clearCart() }

// ── Barcode ───────────────────────────────────────────────────────────────────
async function onBarcodeDetected(code: string) {
  showScanner.value = false
  try {
    const results = await inventoryAPI.getByBarcode(code)
    if (results.length === 1) addToCart(results[0])
    else if (results.length > 1) { searchQuery.value = code; searchResults.value = results }
    else openAvulso(code)
  } catch { openAvulso(code) }
}

// ── Payment ───────────────────────────────────────────────────────────────────
function resetPayment() {
  localPayments.value = []
  newAmount.value = 0
  newReference.value = ''
}

async function confirmPayment() {
  pdv.payments.splice(0, pdv.payments.length, ...localPayments.value)
  try {
    await pdv.completeSale()
    resetPayment()
    showReceipt.value = true
    showToast('Venda concluída!', 'success')
  } catch (e: any) {
    showToast(e?.response?.data?.detail || 'Erro ao finalizar venda', 'error')
  }
}

// ── Keyboard ──────────────────────────────────────────────────────────────────
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'F2' || (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as Element).tagName))) {
    e.preventDefault(); searchInput.value?.focus(); mobileTab.value = 'products'
  }
  if (e.key === 'F5') { e.preventDefault(); nextTick(() => amountInput.value?.focus()); mobileTab.value = 'cart' }
  if (e.key === 'Escape') { if (showRateModal.value) showRateModal.value = false }
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  searchInput.value?.focus()
  // Initialise newRate from the shared currency store (no API call needed)
  newRate.value = defaultRate(newCurrency.value)
})
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
/* ── Root ─────────────────────────────────────────────────────────────────── */
.pdv-root { display: flex; flex-direction: column; height: 100dvh; height: 100vh; background: #f3f4f6; overflow: hidden; }

/* ── Header ───────────────────────────────────────────────────────────────── */
.pdv-header { display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem 0.875rem; background: #1f2937; color: white; flex-shrink: 0; min-height: 44px; }
.pdv-back-btn { display: flex; align-items: center; gap: 0.3rem; background: rgba(255,255,255,0.1); border: none; color: #d1d5db; padding: 0.3rem 0.625rem; border-radius: 0.375rem; cursor: pointer; font-size: 0.8rem; font-weight: 600; transition: background 0.15s; white-space: nowrap; }
.pdv-back-btn:hover { background: rgba(255,255,255,0.2); color: white; }
.pdv-header-title { font-size: 0.95rem; font-weight: 800; color: white; letter-spacing: 0.05em; }

/* Exchange rate button */
.pdv-rate-btn { margin-left: auto; display: flex; align-items: center; gap: 0.4rem; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15); border-radius: 0.5rem; padding: 0.3rem 0.6rem; cursor: pointer; transition: background 0.15s; }
.pdv-rate-btn:hover { background: rgba(255,255,255,0.15); }
.pdv-rate-pill { font-size: 0.72rem; color: #d1d5db; font-family: monospace; white-space: nowrap; }
.pdv-rate-edit-icon { color: #9ca3af; flex-shrink: 0; }

/* ── Mobile tabs ──────────────────────────────────────────────────────────── */
.pdv-tab-bar { display: flex; background: white; border-bottom: 2px solid #e5e7eb; flex-shrink: 0; }
.pdv-tab { flex: 1; display: flex; align-items: center; justify-content: center; gap: 0.4rem; padding: 0.75rem 0.5rem; border: none; background: none; font-size: 0.85rem; font-weight: 600; color: #6b7280; cursor: pointer; position: relative; transition: color 0.15s; }
.pdv-tab.active { color: #f97316; border-bottom: 2px solid #f97316; margin-bottom: -2px; }
.pdv-tab-badge { position: absolute; top: 6px; right: calc(50% - 28px); background: #f97316; color: white; border-radius: 9999px; font-size: 0.6rem; font-weight: 800; min-width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; padding: 0 3px; }
.mobile-only { display: none; }

/* ── Layout ───────────────────────────────────────────────────────────────── */
.pdv-layout { display: grid; grid-template-columns: 60fr 40fr; flex: 1; overflow: hidden; }

/* ── Products panel ───────────────────────────────────────────────────────── */
.pdv-panel-products { display: flex; flex-direction: column; overflow: hidden; border-right: 1px solid #e5e7eb; background: white; }
.pdv-search-bar { display: flex; gap: 0.5rem; padding: 0.75rem; border-bottom: 1px solid #f3f4f6; background: white; flex-shrink: 0; }
.pdv-search-input-wrap { flex: 1; display: flex; align-items: center; border: 2px solid #e5e7eb; border-radius: 0.625rem; overflow: hidden; transition: border-color 0.15s; background: #f9fafb; }
.pdv-search-input-wrap:focus-within { border-color: #f97316; background: white; }
.pdv-search-icon { width: 18px; height: 18px; color: #9ca3af; margin: 0 0.5rem; flex-shrink: 0; }
.pdv-search-input { flex: 1; border: none; outline: none; padding: 0.625rem 0.5rem 0.625rem 0; font-size: 0.9rem; background: transparent; }
.pdv-search-clear { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 0 0.5rem; font-size: 1.2rem; }
.pdv-scan-btn { width: 44px; height: 44px; border-radius: 0.625rem; border: 2px solid #e5e7eb; background: white; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #374151; flex-shrink: 0; }
.pdv-scan-btn:hover { border-color: #f97316; color: #f97316; }

.pdv-results { flex: 1; overflow-y: auto; }
.pdv-result-row { display: flex; align-items: center; gap: 0.625rem; padding: 0.5rem 0.75rem; border-bottom: 1px solid #f3f4f6; cursor: pointer; transition: background 0.1s; }
.pdv-result-row:hover { background: #fff7ed; }
.pdv-result-thumb { width: 46px; height: 46px; border-radius: 0.375rem; overflow: hidden; flex-shrink: 0; background: #f3f4f6; border: 1px solid #e5e7eb; }
.pdv-result-img { width: 100%; height: 100%; object-fit: cover; }
.pdv-result-no-img { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; font-weight: 800; color: #9ca3af; }
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
.pdv-price-gs { display: block; font-size: 0.68rem; color: #9ca3af; white-space: nowrap; }
.pdv-result-add { width: 28px; height: 28px; border-radius: 50%; border: none; background: #f97316; color: white; font-size: 1.1rem; cursor: pointer; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.pdv-result-avulso { padding: 0.75rem; font-size: 0.8rem; color: #d97706; border-top: 1px dashed #fcd34d; cursor: pointer; text-align: center; }
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

/* ── Cart panel (unified) ─────────────────────────────────────────────────── */
.pdv-panel-cart { display: flex; flex-direction: column; overflow: hidden; background: white; }
.pdv-cart-header { display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 0.875rem; border-bottom: 2px solid #f3f4f6; flex-shrink: 0; }
.pdv-cart-title { font-size: 0.95rem; font-weight: 700; color: #111827; }
.pdv-cart-count { font-size: 0.75rem; color: #9ca3af; flex: 1; }
.pdv-cart-clear { background: none; border: none; cursor: pointer; color: #dc2626; font-size: 1rem; padding: 0.2rem; }

/* Scrollable body */
.pdv-cart-scroll { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }

.pdv-client-row { padding: 0.5rem 0.875rem; border-bottom: 1px solid #f3f4f6; flex-shrink: 0; }
.pdv-client-input { width: 100%; box-sizing: border-box; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.35rem 0.6rem; font-size: 0.8rem; outline: none; color: #374151; }
.pdv-client-input:focus { border-color: #f97316; }

.pdv-cart-items { }
.pdv-cart-item { display: flex; gap: 0.5rem; padding: 0.5rem 0.75rem; border-bottom: 1px solid #f3f4f6; align-items: flex-start; }
.pdv-cart-item.item-avulso { background: #fffbeb; }
.pdv-ci-thumb { width: 40px; height: 40px; border-radius: 0.3rem; overflow: hidden; flex-shrink: 0; background: #f3f4f6; border: 1px solid #e5e7eb; margin-top: 2px; }
.pdv-ci-img { width: 100%; height: 100%; object-fit: cover; }
.pdv-ci-no-img { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 0.9rem; font-weight: 800; color: #9ca3af; }
.pdv-ci-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 0.3rem; }
.pdv-ci-info { display: flex; flex-direction: column; }
.pdv-ci-name { font-size: 0.83rem; font-weight: 600; color: #111827; display: flex; align-items: center; gap: 0.3rem; flex-wrap: wrap; }
.ci-avulso-badge { background: #fef3c7; color: #92400e; font-size: 0.6rem; font-weight: 700; padding: 0.1rem 0.3rem; border-radius: 0.2rem; }
.pdv-ci-meta { font-size: 0.68rem; color: #9ca3af; display: flex; gap: 0.4rem; align-items: center; flex-wrap: wrap; }
.ci-gs-equiv { color: #6b7280; font-style: italic; }
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
.pdv-cart-empty { padding: 2rem 1rem; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; color: #9ca3af; }
.pdv-cart-empty-icon { font-size: 2.5rem; }
.pdv-cart-empty p { margin: 0; font-size: 0.88rem; }

.pdv-totals { padding: 0.5rem 0.875rem; background: #f9fafb; border-top: 2px solid #f3f4f6; }
.pdv-total-row { display: flex; justify-content: space-between; font-size: 0.85rem; color: #374151; padding: 0.12rem 0; }
.pdv-discount-row { color: #dc2626; }
.pdv-grand-total { font-size: 1rem; font-weight: 800; color: #111827; border-top: 1px solid #e5e7eb; margin-top: 0.2rem; padding-top: 0.3rem; }
.pdv-total-usd { font-size: 0.7rem; color: #9ca3af; text-align: right; margin-top: 0.1rem; }

/* ── Payment section (inline below cart) ──────────────────────────────────── */
.pdv-payment-section { border-top: 2px solid #e5e7eb; margin-top: auto; }
.pdv-payment-divider { padding: 0.5rem 0.875rem; font-size: 0.78rem; font-weight: 700; color: #374151; background: #f9fafb; border-bottom: 1px solid #f3f4f6; letter-spacing: 0.03em; }

.pay-discount-row { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.875rem; border-bottom: 1px solid #f3f4f6; background: #fff7ed; }
.pay-discount-label { font-size: 0.72rem; font-weight: 600; color: #92400e; white-space: nowrap; }
.pay-discount-input-wrap { display: flex; align-items: center; border: 1.5px solid #fed7aa; border-radius: 0.35rem; overflow: hidden; background: white; }
.pay-currency-prefix { padding: 0.2rem 0.3rem; font-size: 0.7rem; color: #9ca3af; background: #f9fafb; border-right: 1px solid #e5e7eb; }
.pay-discount-input { border: none; outline: none; width: 80px; padding: 0.2rem 0.35rem; font-size: 0.85rem; }

.pay-entries-inline { padding: 0.375rem 0.875rem; }
.pay-entry { display: flex; align-items: center; gap: 0.4rem; padding: 0.3rem 0.4rem; border-radius: 0.4rem; margin-bottom: 0.25rem; background: #f9fafb; }
.pay-entry-method { flex: 1; display: flex; align-items: center; gap: 0.35rem; min-width: 0; }
.pay-method-badge { font-size: 0.68rem; font-weight: 700; padding: 0.1rem 0.3rem; border-radius: 0.25rem; background: #e5e7eb; color: #374151; white-space: nowrap; }
.method-cash_gs  { background: #d1fae5; color: #065f46; }
.method-cash_brl { background: #dbeafe; color: #1e40af; }
.method-cash_usd { background: #fef9c3; color: #713f12; }
.method-cash_eur { background: #ede9fe; color: #4c1d95; }
.method-card     { background: #f0fdf4; color: #166534; }
.method-pix      { background: #ecfdf5; color: #065f46; }
.method-fiado    { background: #fef3c7; color: #92400e; }
.pay-entry-ref { font-size: 0.65rem; color: #9ca3af; overflow: hidden; text-overflow: ellipsis; max-width: 55px; }
.pay-entry-amounts { display: flex; flex-direction: column; align-items: flex-end; }
.pay-orig-amount { font-size: 0.65rem; color: #9ca3af; }
.pay-gs-amount { font-size: 0.8rem; font-weight: 700; color: #111827; }
.pay-entry-remove { background: none; border: none; color: #dc2626; cursor: pointer; font-size: 1.1rem; padding: 0; flex-shrink: 0; }
.pay-empty { font-size: 0.75rem; color: #d1d5db; text-align: center; padding: 0.4rem 0; }

.pay-add-section { padding: 0.5rem 0.875rem; background: #f9fafb; border-top: 1px solid #f3f4f6; }
.pay-add-row { display: flex; gap: 0.3rem; margin-bottom: 0.3rem; align-items: center; }
.pay-select { flex: 1; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.35rem; font-size: 0.78rem; background: white; outline: none; }
.pay-select-sm { flex: 0 0 54px; }
.pay-input-wrap { flex: 1; display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; background: white; }
.pay-amount-input { flex: 1; border: none; outline: none; padding: 0.35rem; font-size: 0.85rem; min-width: 0; }
.pay-btn-total { background: #1d4ed8; color: white; border: none; border-radius: 0.4rem; padding: 0.35rem 0.45rem; font-weight: 700; cursor: pointer; font-size: 0.72rem; white-space: nowrap; flex-shrink: 0; }
.pay-btn-total:hover { background: #1e40af; }
.pay-ref-input { flex: 1; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.35rem; font-size: 0.78rem; outline: none; min-width: 0; }
.pay-btn-add { background: #111827; color: white; border: none; border-radius: 0.4rem; padding: 0.35rem 0.55rem; font-weight: 700; cursor: pointer; font-size: 0.78rem; white-space: nowrap; }
.pay-btn-add:disabled { opacity: 0.5; cursor: not-allowed; }
.pay-rate-row { display: flex; align-items: center; gap: 0.35rem; font-size: 0.7rem; color: #6b7280; margin-top: 0.2rem; }
.pay-rate-input { width: 65px; border: 1px solid #e5e7eb; border-radius: 0.3rem; padding: 0.15rem 0.3rem; font-size: 0.75rem; outline: none; }
.pay-converted { font-weight: 700; color: #059669; }

.pay-summary-inline { padding: 0.375rem 0.875rem 0.5rem; border-top: 1px solid #f3f4f6; }
.pay-sum-row { display: flex; justify-content: space-between; font-size: 0.85rem; padding: 0.1rem 0; color: #374151; }
.pay-ok { color: #059669; font-weight: 700; }
.pay-short { color: #dc2626; font-weight: 700; }
.pay-troco-row { font-weight: 700; color: #059669; border-top: 1px solid #e5e7eb; margin-top: 0.15rem; padding-top: 0.25rem; }
.pay-troco { color: #059669; }
.pay-remaining-row { font-weight: 700; color: #dc2626; border-top: 1px solid #e5e7eb; margin-top: 0.15rem; padding-top: 0.25rem; }
.pay-remaining { color: #dc2626; }

/* Sticky confirm button */
.pdv-pay-area { padding: 0.625rem 0.75rem; flex-shrink: 0; border-top: 2px solid #e5e7eb; background: white; }
.pay-confirm-btn { width: 100%; padding: 0.8rem; border: none; border-radius: 0.75rem; background: linear-gradient(135deg, #16a34a, #15803d); color: white; font-size: 0.95rem; font-weight: 800; cursor: pointer; transition: opacity 0.15s; }
.pay-confirm-btn:hover:not(:disabled) { opacity: 0.9; }
.pay-confirm-btn:disabled { opacity: 0.45; cursor: not-allowed; background: #6b7280; }

/* ── Exchange Rate Modal ───────────────────────────────────────────────────── */
.er-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.55); display: flex; align-items: center; justify-content: center; z-index: 3000; padding: 1rem; box-sizing: border-box; }
.er-modal { background: white; border-radius: 0.75rem; width: 100%; max-width: 400px; box-shadow: 0 20px 60px rgba(0,0,0,0.2); }
.er-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.25rem; border-bottom: 1px solid #e5e7eb; }
.er-header h2 { margin: 0; font-size: 1.1rem; font-weight: 700; color: #111827; }
.er-close { background: none; border: none; color: #6b7280; cursor: pointer; display: flex; align-items: center; justify-content: center; padding: 0.25rem; border-radius: 0.375rem; }
.er-close:hover { background: #f3f4f6; color: #374151; }
.er-body { padding: 1.25rem; }
.er-error { background: #fee2e2; color: #991b1b; padding: 0.625rem 0.875rem; border-radius: 0.5rem; font-size: 0.85rem; margin-bottom: 1rem; }
.er-form { display: grid; grid-template-columns: 1fr 1fr; gap: 0.875rem; }
.er-group { display: flex; flex-direction: column; gap: 0.35rem; }
.er-group label { font-size: 0.78rem; font-weight: 600; color: #374151; }
.er-input { border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.5rem 0.625rem; font-size: 0.9rem; outline: none; transition: border-color 0.15s; }
.er-input:focus { border-color: #f97316; }
.er-input:disabled { background: #f9fafb; color: #9ca3af; cursor: not-allowed; }
.er-footer { display: flex; justify-content: flex-end; gap: 0.75rem; padding: 0.875rem 1.25rem; border-top: 1px solid #e5e7eb; }
.er-btn-cancel { padding: 0.5rem 1rem; border: 1.5px solid #e5e7eb; border-radius: 0.5rem; background: white; color: #6b7280; font-weight: 600; cursor: pointer; }
.er-btn-save { padding: 0.5rem 1.25rem; border: none; border-radius: 0.5rem; background: #f97316; color: white; font-weight: 700; cursor: pointer; }
.er-btn-save:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Toast ────────────────────────────────────────────────────────────────── */
.pdv-toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.6rem 1.25rem; border-radius: 2rem; font-size: 0.85rem; font-weight: 600; z-index: 9999; pointer-events: none; white-space: nowrap; box-shadow: 0 4px 16px rgba(0,0,0,0.15); }
.toast-success { background: #111827; color: white; }
.toast-error   { background: #dc2626; color: white; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: all 0.25s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

/* ── Mobile ───────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .mobile-only { display: flex; }
  .pdv-layout { grid-template-columns: 1fr; }
  .pdv-panel-products, .pdv-panel-cart { height: calc(100dvh - 100px); height: calc(100vh - 100px); }
  .mobile-hidden { display: none !important; }
  .pdv-panel-products, .pdv-panel-cart { border-right: none; }
  .pdv-header-title { font-size: 0.85rem; }
  .pdv-rate-btn { padding: 0.25rem 0.4rem; }
  .pdv-rate-pill { font-size: 0.65rem; }
}
</style>
