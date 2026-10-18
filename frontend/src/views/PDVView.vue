<template>
  <div class="pdv-root" v-pdv-action-keyboard>

    <!-- PDV Header -->
    <ModuleHeader title="PDV">
      <button
        :disabled="pdv.loading || pdv.checkoutUncertain"
        class="pdv-rate-btn erp-button erp-button--secondary erp-button--sm"
        @click="openRateModal"
        :title="canEditRates ? uiText(`Editar taxas de câmbio`) : uiText(`Taxas de câmbio`)"
      >
        <span class="pdv-rate-pill">🇺🇸 U$→G$ {{ uiNumber(rateUsd, 0) }}</span>
        <span class="pdv-rate-pill">🇧🇷 U$→R$ {{ uiNumber(currencyStore.exchangeRates["R$"], 2) }}</span>
        <svg
          v-if="canEditRates"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          width="13"
          height="13"
          class="pdv-rate-edit-icon"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
          />
        </svg>
      </button>
      <button v-if="auth.isOwner" class="erp-button erp-button--secondary erp-button--sm" :disabled="pdv.loading" @click="showPrinterModal=true" :aria-label="uiText('Impressora de tickets')">🖨 {{ uiText('Tickets') }}</button>
    </ModuleHeader>
    <div v-if="!ratesReady" class="pdv-rates-status" role="status">
      {{ uiText(currencyStore.error ? 'Erro ao carregar taxas de câmbio' : currencyStore.currentRates ? 'Câmbio incompleto. Confira as taxas.' : 'Carregando taxas…') }}
      <button v-if="currencyStore.error" class="erp-button erp-button--sm" @click="currencyStore.loadCurrentRates()">{{ uiText('Tentar novamente') }}</button>
    </div>

    <!-- Mobile tab bar -->
    <div class="pdv-tab-bar mobile-only">
      <button class="erp-control" :class="['pdv-tab', { active: mobileTab === 'products' }]" @click="mobileTab = 'products'">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
        {{ $tr("Produtos") }}
      </button>
      <button class="erp-control" :class="['pdv-tab', { active: mobileTab === 'cart' }]" @click="mobileTab = 'cart'">
        <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="18" height="18"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"/></svg>
        {{ $tr("Carrinho") }}
        <span v-if="pdv.cartCount > 0" class="pdv-tab-badge">{{ pdv.cartCount }}</span>
      </button>
    </div>

    <!-- Main layout -->
    <div class="pdv-layout">
      <fieldset class="pdv-checkout-lock" :disabled="pdv.loading">

      <!-- LEFT: Product search panel -->
      <div class="pdv-panel-products" :class="{ 'mobile-hidden': mobileTab !== 'products' }">
        <div class="pdv-search-bar">
          <div class="pdv-search-input-wrap">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" class="pdv-search-icon"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
            <input ref="searchInput" v-model="searchQuery" type="text"
              :placeholder='$tr("Buscar produto, SKU ou código de barras… (F2)")'
              class="pdv-search-input" @keydown.enter="onSearchEnter" @input="onSearchInput" />
            <button v-if="searchQuery" class="pdv-search-clear erp-button erp-button--ghost erp-button--icon" @click="clearSearch">×</button>
          </div>
          <button class="pdv-scan-btn erp-button erp-button--primary erp-button--icon" @click="showScanner = true" :title='$tr("Escanear código")' :aria-label='$tr("Escanear código com a câmera")'>
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 7h4l2-3h6l2 3h4v13H3V7zm13 6a4 4 0 11-8 0 4 4 0 018 0z"/></svg>
          </button>
        </div>

        <p v-if="!searchQuery.trim() && !loadingSearch && !searchError" class="pdv-results-label">{{ uiText('Produtos recentes') }}</p>
        <p v-if="loadingSearch" class="pdv-search-loading" role="status">{{ uiText('Carregando produtos…') }}</p>
        <div v-if="visibleProducts.length" class="pdv-results" :aria-busy="loadingSearch">
          <div v-for="item in visibleProducts" :key="item.id" class="pdv-result-row" :class="{ 'is-unavailable': !canAddProduct(item) }" @click="addToCart(item)">
            <div class="pdv-result-thumb">
              <ProductThumbnail v-if="item.image_data || item.has_image" :item="item" :alt="item.name" class="pdv-result-img" />
              <div v-else class="pdv-result-no-img">{{ item.name.charAt(0).toUpperCase() }}</div>
            </div>
            <div class="pdv-result-left">
              <div class="pdv-result-name">{{ item.name }}</div>
              <div class="pdv-result-meta">{{ [item.category, item.size, item.color].filter(Boolean).join(' · ') }}</div>
              <div class="pdv-result-sku">{{ item.sku_internal }}</div>
            </div>
            <div class="pdv-result-right">
              <div class="pdv-result-stock" :class="productAvailable(item) === null ? 'stock-unknown' : productAvailable(item) === 0 ? 'stock-out' : 'stock-ok'">
                {{ cartText('available', { quantity: displayStock(productAvailable(item)) }) }} {{ $tr("un") }}
                <span v-if="productAvailable(item) === null"> · {{ inventoryText('Revisar estoque') }}</span>
              </div>
              <label class="pdv-stock-location" @click.stop>
                {{ cartText('location') }}
                <ErpSelect compact :label="(cartText('location'))" :value="productLocation(item)" @change="selectedLocations[item.id] = $event as StockLocation">
                  <option value="loja">{{ cartText('loja') }}: {{ displayStock(item.stock_loja) }}</option>
                  <option value="deposito">{{ cartText('deposito') }}: {{ displayStock(item.stock_deposito) }}</option>
                </ErpSelect>
              </label>
              <div class="pdv-result-price">
                <span class="pdv-price-orig">{{ currencyLabel(item.sale_currency) }} {{ fmtNum(catalogPrice(item.sale_price)) }}</span>
                <span v-for="price in productEquivalents(catalogPrice(item.sale_price), item.sale_currency)" :key="price.currency" class="pdv-price-gs">≈ {{ currencyLabel(price.currency) }} {{ fmtNum(price.amount) }}</span>
              </div>
              <button class="pdv-result-add erp-button erp-button--primary erp-button--icon" :disabled="!canAddProduct(item)">+</button>
            </div>
          </div>
          <div v-if="searchQuery && !loadingSearch && !searchError" class="pdv-result-avulso" @click="openAvulso()">
            <span>⚠</span> {{ $tr("Produto não encontrado? Adicionar manualmente") }}
          </div>
        </div>

        <div v-else-if="!searchQuery && !loadingSearch && !searchError" class="pdv-search-hint">
          <div class="pdv-search-hint-icon">🔍</div>
          <p>{{ $tr("Digite o nome, SKU ou escaneie o código de barras para adicionar produtos") }}</p>
          <p class="pdv-shortcut-hint">{{ $tr("Atalho:") }} <kbd>F2</kbd> {{ $tr("busca ·") }} <kbd>F5</kbd> {{ $tr("pagar ·") }} <kbd>Esc</kbd> {{ $tr("voltar") }}</p>
        </div>
        <div v-else-if="loadingSearch"></div>
        <div v-else-if="searchError" class="pdv-search-error" role="alert">{{ cartText('searchFailed') }} <button class="erp-button erp-button--sm" @click="doSearch">{{ uiText('Tentar novamente') }}</button></div>
        <div v-else class="pdv-no-results">
          <p>{{ $tr("Nenhum produto encontrado para \"") }}{{ searchQuery }}"</p>
          <button class="pdv-btn-avulso erp-button erp-button--primary" @click="openAvulso(searchQuery)">{{ $tr("+ Adicionar como item avulso") }}</button>
        </div>
      </div>

      <!-- RIGHT: Cart + Payment (unified panel) -->
      <div class="pdv-panel-cart" :class="{ 'mobile-hidden': mobileTab !== 'cart' }">

        <!-- Fixed header -->
        <div class="pdv-cart-header">
          <span class="pdv-cart-title">{{ $tr("Carrinho") }}</span>
          <span class="pdv-cart-count">{{ pdv.cartCount }} {{ $tr("item") }}{{ pdv.cartCount !== 1 ? 's' : '' }}</span>
          <button v-if="pdv.cart.length" class="pdv-cart-clear erp-button erp-button--danger erp-button--icon" :aria-label="uiText('Limpar carrinho')" :disabled="customerBusy" @click="confirmClear">🗑</button>
        </div>

        <!-- Scrollable body -->
        <div class="pdv-cart-scroll">

          <!-- Client -->
          <PDVCustomerPicker v-model:customer-id="pdv.clienteId" v-model:customer-name="pdv.clienteNome"
            :disabled="pdv.loading || pdv.checkoutUncertain" @busy="customerBusy = $event" />

          <p v-if="pdv.checkoutUncertain" role="alert" class="pdv-checkout-error">{{ cartText('uncertain') }}</p>
          <p v-else-if="checkoutError" role="alert" class="pdv-checkout-error">{{ cartErrorText(checkoutError) }}</p>
          <!-- Cart items -->
          <div v-if="pdv.cart.length" class="pdv-cart-items">
            <div v-for="item in pdv.cart" :key="item.id" class="pdv-cart-item" :class="{ 'item-avulso': item.is_avulso }">
              <div class="pdv-ci-thumb">
                <ProductThumbnail v-if="item.image_data || item.has_image" :item="{ id: item.item_id || item.id, image_data: item.image_data, has_image: item.has_image, updated_at: item.updated_at || '' }" :alt="item.item_name" class="pdv-ci-img" />
                <div v-else class="pdv-ci-no-img">{{ item.item_name.charAt(0).toUpperCase() }}</div>
              </div>
              <div class="pdv-ci-body">
                <div class="pdv-ci-info">
                  <div class="pdv-ci-name">
                    <span v-if="item.is_avulso" class="ci-avulso-badge">{{ $tr("avulso") }}</span>
                    {{ item.item_name }}
                  </div>
                  <div v-if="!item.is_avulso" class="pdv-ci-stock">
                    {{ cartText(item.location) }} · {{ cartText('available', { quantity: displayStock(pdv.availableStock(item.item_id!, item.location)) }) }}
                  </div>
                  <div class="pdv-ci-meta">
                    <span v-if="item.item_size || item.item_color">{{ [item.item_size, item.item_color].filter(Boolean).join(' · ') }}</span>
                    <span class="ci-gs-equiv">{{ fmtGs(item.unit_price_gs) }} · U$ {{ fmtNum(item.unit_price_gs / rateUsd) }} · R$ {{ fmtNum(item.unit_price_gs / rateBrl) }}</span>
                  </div>
                </div>
                <div class="pdv-ci-controls">
                  <div class="pdv-qty-stepper">
                    <button class="qty-btn erp-control" :aria-label="uiText('Diminuir quantidade')" @click="changeQuantity(item, item.quantity - 1)" :disabled="item.quantity <= 1">−</button>
                    <input type="number" :value="quantityDrafts[item.id] ?? item.quantity" :min="item.is_avulso ? 0.001 : 1" :step="item.is_avulso ? 0.001 : 1" class="qty-input" :aria-label="uiText('Quantidade')" inputmode="numeric" @focus="($event.target as HTMLInputElement).select()"
                      :aria-invalid="!!quantityErrors[item.id]"
                      @input="quantityDrafts[item.id] = ($event.target as HTMLInputElement).value"
                      @change="changeQuantity(item, Number(($event.target as HTMLInputElement).value))" />
                    <button class="qty-btn erp-control" :aria-label="uiText('Aumentar quantidade')" @click="changeQuantity(item, item.quantity + 1)" :disabled="!canIncrease(item)">+</button>
                  </div>
                  <div class="pdv-ci-price-wrap">
                    <ErpSelect compact class="pdv-ci-currency" :value="item.sale_currency === 'GS' ? 'PYG' : item.sale_currency" :aria-label="uiText('Moeda do item')" @change="changeItemCurrency(item, $event)">
                      <option v-for="currency in itemCurrencies" :key="currency" :value="currency">{{ currencyLabel(currency) }}</option>
                    </ErpSelect>
                    <DecimalInput :model-value="item.original_price" class="pdv-ci-price" :aria-label="uiText('Preço unitário')" :aria-invalid="!!priceErrors[item.id]"
                      @update:model-value="changeItemPrice(item, $event)" />
                  </div>
                  <button class="pdv-ci-remove erp-button erp-button--danger erp-button--icon" :aria-label="uiText('Remover item')" @click="removeCartItem(item.id)">×</button>
                </div>
                <div class="pdv-ci-line-summary">
                  <span v-if="quantityErrors[item.id]" class="pdv-quantity-error" role="alert">{{ cartErrorText(quantityErrors[item.id]) }}</span>
                  <span v-if="priceErrors[item.id]" class="pdv-quantity-error" role="alert">{{ uiText('Informe um preço válido.') }}</span>
                  <span class="pdv-ci-total" aria-live="polite">{{ fmtGs(item.quantity * item.unit_price_gs - item.discount_gs) }}</span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="pdv-cart-empty">
            <div class="pdv-cart-empty-icon">🛒</div>
            <p>{{ $tr("Carrinho vazio") }}</p>
          </div>

          <!-- Totals -->
          <div class="pdv-totals" v-if="pdv.cart.length">
            <div class="pdv-total-row"><span>{{ $tr("Subtotal") }}</span><span>{{ fmtGs(pdv.subtotal) }}</span></div>
            <div v-if="pdv.discountGs > 0" class="pdv-total-row pdv-discount-row">
              <span>{{ $tr("Desconto") }}</span><span>-{{ fmtGs(pdv.discountGs) }}</span>
            </div>
            <div class="pdv-total-row pdv-grand-total">
              <span>{{ $tr("TOTAL") }}</span><span>{{ fmtGs(pdv.total) }}</span>
            </div>
            <div class="pdv-total-usd">≈ U$ {{ fmtNum(pdv.total / rateUsd) }} · R$ {{ fmtNum(pdv.total / rateBrl) }}</div>
          </div>

          <!-- ── Payment section ── -->
          <div class="pdv-payment-section" v-if="pdv.cart.length">

            <div class="pdv-payment-divider">{{ $tr("💳 Pagamento") }}</div>

            <!-- Discount -->
            <div class="pay-discount-row">
              <span class="pay-discount-label">{{ $tr("Desconto (G$)") }}</span>
              <div class="pay-discount-input-wrap">
                <span class="pay-currency-prefix">G$</span>
                <DecimalInput :model-value="pdv.discountGs" @update:model-value="pdv.discountGs = $event ?? 0" class="pay-discount-input" :aria-label="uiText('Desconto (G$)')" />
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
                  <span class="pay-gs-amount">{{ paymentSymbol(p.currency) }} {{ fmtNum(p.amount_original) }}</span>
                  <span v-if="p.currency !== 'GS'" class="pay-orig-amount">≈ {{ fmtGs(p.amount_gs) }}</span>
                </div>
                <button class="pay-entry-remove erp-button erp-button--danger erp-button--icon" @click="removePayment(p.id)">×</button>
              </div>
              <div v-if="!localPayments.length" class="pay-empty">{{ $tr("Nenhum pagamento adicionado") }}</div>
            </div>

            <!-- Add payment form -->
            <div class="pay-add-section">
              <div class="pay-add-row">
                <ErpSelect v-model="newMethod" class="pay-select" :aria-label="uiText('Método de pagamento')">
                  <option v-for="m in PAYMENT_METHODS" :key="m.value" :value="m.value">{{ m.label }}</option>
                </ErpSelect>
                <ErpSelect compact v-if="newMethod.startsWith('cash_')" class="pay-cash-currency" :value="newCurrency" :aria-label="uiText('Moeda do pagamento')" @change="changeCashCurrency($event)">
                  <option v-for="method in cashMethods" :key="method.value" :value="method.currency">{{ paymentSymbol(method.currency) }}</option>
                </ErpSelect>
                <span v-else class="pay-fixed-currency" :aria-label="uiText('Moeda do pagamento')">{{ currencySymbol }}</span>
              </div>
              <div class="pay-add-row">
                <div class="pay-input-wrap">
                  <span class="pay-currency-prefix">{{ currencySymbol }}</span>
                  <DecimalInput v-model="newAmount" ref="amountInput" :aria-label="uiText('Valor em {0}', {0: currencySymbol})"
                    class="pay-amount-input" @keydown.enter="addPayment" />
                </div>
                <button class="pay-btn-total erp-button erp-button--secondary erp-button--sm" :disabled="!validRate" @click="fillTotal" :title='$tr("Preencher valor restante")'>{{ $tr("Total") }}</button>
                <input v-if="showReference" v-model="newReference" type="text" class="pay-ref-input" :placeholder="referencePlaceholder" />
                <button class="pay-btn-add erp-button erp-button--primary erp-button--sm" @click="addPayment" :disabled="!canAddPayment">{{ $tr("+ Add") }}</button>
              </div>
              <div v-if="newCurrency !== 'GS'" class="pay-rate-row">
                <span>{{ $tr("Taxa:") }}</span>
                <DecimalInput v-model="newRate" class="pay-rate-input" :aria-label="uiText('Câmbio para G$')" />
                <span>G$ / {{ currencySymbol }}</span>
                <span class="pay-converted" aria-live="polite">= {{ fmtGs(Number(newAmount) * Number(newRate)) }}</span>
              </div>
            </div>
            <p v-if="!validRate" class="pay-validation" role="alert">{{ uiText('Informe um câmbio válido para este pagamento.') }}</p>
            <p v-if="newMethod === 'fiado' && !pdv.clienteId" class="pay-validation" role="status">{{ uiText('Selecione o cliente para lançar fiado.') }}</p>

            <!-- Payment summary -->
            <div class="pay-summary-inline">
              <div class="pay-sum-row">
                <span>{{ $tr("Pago") }}</span>
                <span :class="payTotalPaid >= pdv.total ? 'pay-ok' : 'pay-short'">{{ fmtGs(payTotalPaid) }}</span>
              </div>
              <div v-if="payTroco > 0" class="pay-sum-row pay-troco-row">
                <span>{{ $tr("Troco") }}</span><span class="pay-troco">{{ fmtGs(payTroco) }}</span>
              </div>
              <div v-if="payRemaining > 0" class="pay-sum-row pay-remaining-row">
                <span>{{ $tr("Faltando") }}</span><span class="pay-remaining">{{ fmtGs(payRemaining) }}</span>
              </div>
            </div>

          </div>

        </div><!-- end pdv-cart-scroll -->

        <!-- Sticky confirm button -->
        <div class="pdv-pay-area">
          <button class="pay-confirm-btn erp-button erp-button--primary"
            :disabled="!canConfirmPayment || pdv.loading || pdv.checkoutUncertain || invalidQuantityDraft || invalidPriceDraft || !ratesReady || !pdv.cart.length"
            @click="confirmPayment">
            <span v-if="pdv.loading">{{ $tr("Processando…") }}</span>
            <span v-else-if="!pdv.cart.length">{{ $tr("Carrinho vazio") }}</span>
            <span v-else-if="payRemaining > 0">{{ $tr("Faltando") }} {{ fmtGs(payRemaining) }}</span>
            <span v-else>{{ $tr("✓ Confirmar e imprimir") }}</span>
          </button>
        </div>

      </div>
      </fieldset>
    </div>

    <!-- Modals -->
    <BarcodeScanner v-if="showScanner" @barcode-detected="onBarcodeDetected" @close="showScanner = false" />
    <PDVAvulsoModal v-if="showAvulso" :scanned-code="avulsoCode" :rates="{ PYG: 1, USD: rateUsd, BRL: rateBrl, EUR: rateEur }" @add="onAvulsoAdd" @close="showAvulso = false" />
    <PDVPrinterModal v-if="showPrinterModal" @close="showPrinterModal=false" />
    <PDVReceiptModal v-if="showReceipt && pdv.lastSale" :sale="pdv.lastSale" @close="showReceipt = false" />

    <ExchangeRateModal v-if="showRateModal" @close="showRateModal = false" @saved="showToast(uiText('Taxas atualizadas'))" />

    <!-- Toast -->
    <transition name="toast-fade">
      <div v-if="toast" class="pdv-toast" :class="`toast-${toast.type}`">{{ toast.msg }}</div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import ErpSelect from '@/components/ui/ErpSelect.vue'
import ExchangeRateModal from '@/components/currency/ExchangeRateModal.vue'
import DecimalInput from '@/components/forms/DecimalInput.vue'
import ProductThumbnail from '@/components/inventory/ProductThumbnail.vue'
import { useAuthStore } from '@/stores/auth'
import PDVPrinterModal from '@/components/pdv/PDVPrinterModal.vue'
import ModuleHeader from '@/components/ModuleHeader.vue'
import { uiText, uiLocale, uiNumber } from '@/i18n/uiText'
import { ref, reactive, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { usePdvStore } from '@/stores/pdv'
import { useCurrencyStore } from '@/stores/currency'
import { inventoryAPI, type InventoryItem } from '@/services/api'
import { displayStock } from '@/services/inventoryStock'
import { paymentMethods, paymentCurrency, paymentLabel, paymentSymbol, paymentRate, validPaymentAmount } from '@/services/pdvPayments'
import { useInventoryI18n } from '@/components/inventory/i18n'
const { tr: inventoryText } = useInventoryI18n()
import BarcodeScanner from '@/components/inventory/BarcodeScanner.vue'
import PDVAvulsoModal from '@/components/pdv/PDVAvulsoModal.vue'
import PDVCustomerPicker from '@/components/pdv/PDVCustomerPicker.vue'
import PDVReceiptModal from '@/components/pdv/PDVReceiptModal.vue'
import type { CartItem, CartPayment } from '@/stores/pdv'
import { catalogPrice, PdvCartError, type StockLocation } from '@/services/pdvCart'
import { vPdvActionKeyboard } from '@/directives/pdvKeyboard'
import { usePdvCartText } from '@/components/pdv/cartMessages'
const { cartText, cartErrorText } = usePdvCartText()

const auth = useAuthStore()
const showPrinterModal = ref(false)
const pdv = usePdvStore()
const currencyStore = useCurrencyStore()

// ── Panel / tab state ─────────────────────────────────────────────────────────
const mobileTab = ref<'products' | 'cart'>('products')

// ── Search ────────────────────────────────────────────────────────────────────
const searchQuery = ref('')
const searchResults = ref<InventoryItem[]>([])
const recentProducts = ref<InventoryItem[]>([])
const visibleProducts = computed(() => searchQuery.value.trim() ? searchResults.value : recentProducts.value)
let searchGeneration = 0, disposed = false
let searchController: AbortController | undefined
const loadingSearch = ref(false)
const barcodePending = ref(false)
const searchError = ref(false)
const selectedLocations = reactive<Record<string, StockLocation>>({})
const quantityDrafts = reactive<Record<string, string>>({})
const priceErrors = reactive<Record<string, boolean>>({})
const invalidPriceDraft = computed(() => pdv.cart.some(item => priceErrors[item.id]))
const quantityErrors = reactive<Record<string, unknown>>({})
const checkoutError = ref<unknown>(null)
const invalidQuantityDraft = computed(() => pdv.cart.some(item => quantityErrors[item.id] ||
  (quantityDrafts[item.id] !== undefined && Number(quantityDrafts[item.id]) !== item.quantity)))
const showScanner = ref(false)
const showAvulso = ref(false)
const showReceipt = ref(false)
const avulsoCode = ref<string | null>(null)
const searchInput = ref<HTMLInputElement>()
const customerBusy = ref(false)

// ── Exchange rates (from shared currency store) ───────────────────────────────
// G$ per 1 USD
const rateUsd = computed(() => currencyStore.exchangeRates['G$'])
// G$ per 1 BRL
const rateBrl = computed(() => paymentRate('BRL', currencyStore.exchangeRates))
// G$ per 1 EUR  (store['EUR'] = EUR per USD, so G$/EUR = G$/USD / EUR/USD)
const rateEur = computed(() => paymentRate('EUR', currencyStore.exchangeRates))

// ── Exchange rate modal ───────────────────────────────────────────────────────
const showRateModal = ref(false)
const canEditRates = computed(() => currencyStore.canEdit)
const ratesReady = computed(() => !!currencyStore.currentRates && !currencyStore.error && rateUsd.value > 0 && rateBrl.value > 0)
function openRateModal() { showRateModal.value = true }

// ── Payment state ────────────────────────────────────────────────────────────
const localPayments = ref<CartPayment[]>(pdv.payments.map(payment => ({ ...payment })))
const newMethod = ref('cash_usd')
const newCurrency = computed(() => paymentCurrency(newMethod.value) || 'USD')
const newAmount = ref<number | null>(null)
const newRate = ref<number | null>(0)
const newReference = ref('')
const amountInput = ref<InstanceType<typeof DecimalInput>>()

const PAYMENT_METHODS = computed(() => paymentMethods.map(m => ({ ...m, label: paymentLabel(m.value) })))
const defaultRate = (currency: string) => paymentRate(currency, currencyStore.exchangeRates)
const methodLabel = paymentLabel
const cashMethods = paymentMethods.filter(m => m.value.startsWith('cash_'))
function changeCashCurrency(currency: string) { const method = cashMethods.find(m => m.currency === currency); if (method) newMethod.value = method.value }

watch(newMethod, () => {
  newRate.value = defaultRate(newCurrency.value)
  newAmount.value = null
  newReference.value = ''
})
watch([rateUsd, rateBrl, rateEur], () => {
  newRate.value = defaultRate(newCurrency.value)
  // Reprice the open cart using its original amounts; saved payments keep their agreed rate.
  if (!pdv.loading && !pdv.checkoutUncertain) {
    for (const item of pdv.cart) {
      const rate = getRate(item.sale_currency)
      if (rate > 0) pdv.updateItemOriginalPrice(item.id, item.original_price, rate)
    }
  }
})
watch(() => pdv.cart.length, (len) => { if (len === 0) { resetPayment(); checkoutError.value = null; Object.keys(quantityDrafts).forEach(key => delete quantityDrafts[key]); Object.keys(quantityErrors).forEach(key => delete quantityErrors[key]) } })

const currencySymbol = computed(() => paymentSymbol(newCurrency.value))
const showReference = computed(() => !newMethod.value.startsWith('cash_') && newMethod.value !== 'fiado')
const referencePlaceholder = computed(() => newMethod.value.startsWith('card_') ? uiText('Últimos 4 dígitos') : uiText('Referência'))
const validRate = computed(() => Number.isFinite(newRate.value) && Number(newRate.value) > 0 && Number(newRate.value) <= 999999999)
const canAddPayment = computed(() => validPaymentAmount(Number(newAmount.value), Number(newRate.value)) && (newMethod.value !== 'fiado' || !!pdv.clienteId))

const payTotalPaid = computed(() => localPayments.value.reduce((s, p) => s + p.amount_gs, 0))
const payRemaining = computed(() => Math.max(0, pdv.total - payTotalPaid.value))
const payTroco = computed(() => Math.max(0, payTotalPaid.value - pdv.total))
const remainingInCurrency = computed(() =>
  validRate.value ? payRemaining.value / Number(newRate.value) : 0
)
const canConfirmPayment = computed(() => !customerBusy.value && !barcodePending.value && payTotalPaid.value >= pdv.total && localPayments.value.length > 0 && (!localPayments.value.some(p => p.method === 'fiado') || !!pdv.clienteId))

function fillTotal() {
  if (!validRate.value) return
  const rounded = Math.round(remainingInCurrency.value * 100) / 100
  // Avoid adding a cent solely because a six-decimal rate has a tiny fraction.
  const covers = Math.round(rounded * Number(newRate.value) * 100) / 100 >= payRemaining.value - 1e-7
  newAmount.value = covers ? rounded : Math.ceil(remainingInCurrency.value * 100) / 100
}

function addPayment() {
  if (!canAddPayment.value) return
  const rate = newCurrency.value === 'GS' ? 1 : Math.round(Number(newRate.value) * 1e6) / 1e6
  const amountGs = newCurrency.value === 'GS' ? Number(newAmount.value) : Number(newAmount.value) * rate
  localPayments.value.push({
    id: crypto.randomUUID(),
    method: newMethod.value,
    currency: newCurrency.value,
    amount_original: Number(newAmount.value),
    exchange_rate: rate,
    amount_gs: Math.round(amountGs * 100) / 100,
    cambista_id: null,
    reference: newReference.value || null,
    label: methodLabel(newMethod.value),
  })
  newAmount.value = null
  newReference.value = ''
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
function currencyLabel(currency: string): string { return paymentSymbol((currency || 'PYG').toUpperCase()) }
function productEquivalents(value: number | null | undefined, currency: string) {
  const native = (currency || 'PYG').toUpperCase()
  const gs = convertKnownPrice(value, getRate(native))
  return ['GS', 'USD', 'BRL'].filter(c => c !== (native === 'PYG' ? 'GS' : native)).map(c => ({
    currency: c, amount: gs !== null && defaultRate(c) > 0 ? gs / defaultRate(c) : null,
  }))
}
function fmtGs(v: number | null | undefined) { return typeof v === 'number' && Number.isFinite(v) ? 'G$ ' + Math.round(v).toLocaleString(uiLocale()) : '—' }
function fmtNum(v: number | null | undefined) { return typeof v === 'number' && Number.isFinite(v) ? v.toLocaleString(uiLocale(), { minimumFractionDigits: 0, maximumFractionDigits: 2 }) : '—' }
function convertKnownPrice(value: number | null | undefined, rate: number): number | null {
  return typeof value === 'number' && Number.isFinite(value) && Number.isFinite(rate) ? Math.round(value * rate) : null
}

// ── Search ────────────────────────────────────────────────────────────────────
function invalidateProductSearch() {
  searchGeneration++; searchController?.abort(); clearTimeout(searchTimer)
  loadingSearch.value = false; barcodePending.value = false
}
function onSearchInput() {
  invalidateProductSearch()
  searchResults.value = []; searchError.value = false
  if (!searchQuery.value.trim()) { loadingSearch.value = false; if (!recentProducts.value.length) void doSearch(); return }
  loadingSearch.value = true
  searchTimer = setTimeout(doSearch, 280)
}
async function doSearch() {
  invalidateProductSearch()
  const request = searchGeneration, query = searchQuery.value.trim()
  searchController = new AbortController()
  loadingSearch.value = true; searchError.value = false
  try {
    const res = await inventoryAPI.getItems({ search: query || undefined, page_size: query ? 20 : 8, status: 'active', sort_by: query ? undefined : 'created_at', include_images: false }, searchController.signal)
    if (disposed || request !== searchGeneration) return
    pdv.rememberStock(res.items)
    if (query) searchResults.value = res.items
    else recentProducts.value = res.items
  } catch {
    if (!disposed && request === searchGeneration) { searchResults.value = []; searchError.value = true }
  } finally { if (!disposed && request === searchGeneration) loadingSearch.value = false }
}
function onSearchEnter() {
  if (!loadingSearch.value && searchQuery.value.trim() && searchResults.value.length === 1) addToCart(searchResults.value[0])
}
function clearSearch() {
  invalidateProductSearch()
  searchQuery.value = ''; searchResults.value = []; searchError.value = false; loadingSearch.value = false
  if (!recentProducts.value.length) void doSearch()
}

// ── Cart ──────────────────────────────────────────────────────────────────────
function productLocation(item: InventoryItem): StockLocation {
  return selectedLocations[item.id] || (item.stock_loja !== null && item.stock_loja > 0 ? 'loja' : 'deposito')
}
function productAvailable(item: InventoryItem) { return pdv.availableStock(item.id, productLocation(item)) }
function canAddProduct(item: InventoryItem) { const available = productAvailable(item); return catalogPrice(item.sale_price) !== null && ratesReady.value && getRate(item.sale_currency) > 0 && !pdv.loading && available !== null && available >= 1 }
function canIncrease(item: CartItem) {
  if (item.is_avulso) return item.quantity + 1 <= 9_999_999.999
  const available = item.item_id ? pdv.availableStock(item.item_id, item.location, item.id) : null
  return available !== null && item.quantity + 1 <= Math.min(available, 9_999_999)
}
function changeQuantity(item: CartItem, quantity: number) {
  try {
    pdv.updateItemQty(item.id, quantity)
    delete quantityDrafts[item.id]; delete quantityErrors[item.id]
  } catch (error) { quantityErrors[item.id] = error }
}
const itemCurrencies = ['USD', 'BRL', 'PYG', 'EUR']
function changeItemPrice(item: CartItem, value: number | null) {
  const valid = value !== null && Number.isFinite(value) && value >= 0 && value <= 999999999 && Number.isFinite(getRate(item.sale_currency)) && getRate(item.sale_currency) > 0
  priceErrors[item.id] = !valid
  if (valid) pdv.updateItemOriginalPrice(item.id, value!, getRate(item.sale_currency))
}
function changeItemCurrency(item: CartItem, currency: string) {
  if (!itemCurrencies.includes(currency) || pdv.loading || pdv.checkoutUncertain || getRate(currency) <= 0) return
  // Preserve the negotiated total when changing its display unit; do not edit the catalog.
  const price = Math.round(item.unit_price_gs / getRate(currency) * 100) / 100
  item.sale_currency = currency
  changeItemPrice(item, price)
}
function removeCartItem(id: string) {
  delete priceErrors[id]
  pdv.removeItem(id); delete quantityDrafts[id]; delete quantityErrors[id]
}
function addToCart(item: InventoryItem) {
  if (!ratesReady.value) return
  try {
    const price = catalogPrice(item.sale_price)
    if (price === null) throw new PdvCartError('invalidPrice')
    const saleCurrency = item.sale_currency || 'PYG'
    const rate = getRate(saleCurrency)
    const priceGs = Math.round(price * rate)
    // Lookups already stored the latest stock. A cached recent card must not replace it.
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
      original_price: price,
      sale_currency: saleCurrency,
      image_data: item.image_data || null,
      has_image: item.has_image, updated_at: item.updated_at,
      discount_gs: 0,
      is_avulso: false,
      location: productLocation(item),
    })
    showToast(uiText(`{0} adicionado`,{0:item.name}))
    clearSearch()
    mobileTab.value = 'cart'
  } catch (error) { checkoutError.value = error; showToast(cartErrorText(error), 'error') }
}
function openAvulso(prefill?: string) { avulsoCode.value = prefill || null; showAvulso.value = true }
function onAvulsoAdd(item: any) {
  try { pdv.addItem(item) } catch (error) { checkoutError.value = error; showToast(cartErrorText(error), 'error'); return }
  showAvulso.value = false
  showToast(uiText(`{0} adicionado`,{0:item.item_name}))
  mobileTab.value = 'cart'
}
function refreshProductsAfterCheckout() {
  // A sale may have changed stock: never reuse the visible list's old snapshots.
  recentProducts.value = []
  clearSearch()
}
function confirmClear() {
  if (!confirm(uiText(`Limpar o carrinho?`))) return
  const uncertain = pdv.checkoutUncertain
  pdv.clearCart()
  if (uncertain) refreshProductsAfterCheckout()
  else clearSearch()
}

// ── Barcode ───────────────────────────────────────────────────────────────────
async function onBarcodeDetected(code: string) {
  showScanner.value = false
  if (pdv.loading || pdv.checkoutUncertain) return
  invalidateProductSearch()
  const request = searchGeneration
  searchQuery.value = code; searchResults.value = []; searchError.value = false
  loadingSearch.value = true; barcodePending.value = true
  try {
    const results = await inventoryAPI.getByBarcode(code, false)
    if (disposed || request !== searchGeneration) return
    pdv.rememberStock(results)
    searchError.value = false
    if (results.length === 1) addToCart(results[0])
    else if (results.length > 1) { searchQuery.value = code; searchResults.value = results }
    else openAvulso(code)
  } catch { if (disposed || request !== searchGeneration) return; searchQuery.value = code; searchResults.value = []; searchError.value = true; showToast(cartText('searchFailed'), 'error') }
  finally { if (!disposed && request === searchGeneration) { loadingSearch.value = false; barcodePending.value = false } }
}

// ── Payment ───────────────────────────────────────────────────────────────────
function resetPayment() {
  localPayments.value = []
  newAmount.value = null
  newReference.value = ''
}

async function confirmPayment() {
  if (pdv.loading || pdv.checkoutUncertain || invalidQuantityDraft.value || invalidPriceDraft.value || !ratesReady.value || !canConfirmPayment.value) return
  checkoutError.value = null
  pdv.payments.splice(0, pdv.payments.length, ...localPayments.value)
  try {
    const sale = await pdv.completeSale()
    if (disposed || pdv.lastSale?.id !== sale.id) return
    refreshProductsAfterCheckout()
    resetPayment()
    showReceipt.value = true
    showToast(uiText(`Venda concluída!`), 'success')
  } catch (e: any) {
    checkoutError.value = e
  }
}

// ── Keyboard ──────────────────────────────────────────────────────────────────
function onKeydown(e: KeyboardEvent) {
  if (document.querySelector('[aria-modal="true"]')) return
  if (e.key === 'F2' || (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as Element).tagName))) {
    e.preventDefault(); searchInput.value?.focus(); mobileTab.value = 'products'
  }
  if (e.key === 'F5') { e.preventDefault(); nextTick(() => amountInput.value?.focus()); mobileTab.value = 'cart' }
  if (e.key === 'Escape') { if (showRateModal.value) showRateModal.value = false }
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  void currencyStore.loadCurrentRates()
  void doSearch()
  // Read the shared rates; network completion updates the reactive defaults.
  newRate.value = defaultRate(newCurrency.value)
})
onUnmounted(() => { disposed = true; searchGeneration++; searchController?.abort(); document.removeEventListener('keydown', onKeydown); clearTimeout(toastTimer); clearTimeout(searchTimer) })
</script>

<style scoped>
.pdv-checkout-lock { display: contents; }
.pdv-stock-location { min-width: 0; display: flex; flex-direction: column; gap: .15rem; font-size: .65rem; color: #6b7280; }
.pdv-stock-location .erp-dropdown { max-width: 140px; }
.pdv-stock-note, .pdv-ci-stock { font-size: .72rem; color: #6b7280; padding: .3rem 0; }
.pdv-checkout-error, .pdv-search-error { margin: .5rem; padding: .75rem; border-radius: 8px; background: #fff7ed; color: #9a3412; font-size: .8rem; }
.pdv-quantity-error { color: #b91c1c; font-size: .7rem; }
.qty-input[aria-invalid="true"] { border-color: #b91c1c; }

/* ── Root ─────────────────────────────────────────────────────────────────── */
.pdv-root { display: flex; flex-direction: column; height: 100vh; height: 100dvh; background: #f3f4f6; overflow: hidden; }

/* ── Header ───────────────────────────────────────────────────────────────── */

/* Exchange rate button */
.pdv-rate-pill { font-size: 0.72rem; color: #475569; font-family: monospace; white-space: nowrap; }
.pdv-rate-edit-icon { color: #9ca3af; flex-shrink: 0; }

/* ── Mobile tabs ──────────────────────────────────────────────────────────── */
.pdv-tab-bar { display: flex; background: white; border-bottom: 2px solid #e5e7eb; flex-shrink: 0; }
.pdv-tab { flex: 1; display: flex; align-items: center; justify-content: center; gap: 0.4rem; padding: 0.75rem 0.5rem; border: none; background: none; font-size: 0.85rem; font-weight: 600; color: #6b7280; cursor: pointer; position: relative; transition: color 0.15s; }
.pdv-tab.active { color: #f97316; border-bottom: 2px solid #f97316; margin-bottom: -2px; }
.pdv-tab-badge { position: absolute; top: 6px; right: calc(50% - 28px); background: #f97316; color: white; border-radius: 9999px; font-size: 0.6rem; font-weight: 800; min-width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; padding: 0 3px; }
.mobile-only { display: none; }

/* ── Layout ───────────────────────────────────────────────────────────────── */
.pdv-layout { display: grid; grid-template-columns: minmax(0, 60fr) minmax(0, 40fr); flex: 1; min-height: 0; overflow: hidden; }

/* ── Products panel ───────────────────────────────────────────────────────── */
.pdv-panel-products { display: flex; flex-direction: column; overflow: hidden; border-right: 1px solid #e5e7eb; background: white; }
.pdv-search-bar { display: flex; gap: 0.5rem; padding: 0.75rem; border-bottom: 1px solid #f3f4f6; background: white; flex-shrink: 0; }
.pdv-search-input-wrap { flex: 1; min-width: 0; display: flex; align-items: center; border: 2px solid #e5e7eb; border-radius: 0.625rem; overflow: hidden; transition: border-color 0.15s; background: #f9fafb; }
.pdv-search-input-wrap:focus-within { border-color: #f97316; background: white; }
.pdv-search-icon { width: 18px; height: 18px; color: #9ca3af; margin: 0 0.5rem; flex-shrink: 0; }
.pdv-search-input { flex: 1; min-width: 0; border: none; outline: none; padding: 0.625rem 0.5rem 0.625rem 0; font-size: 0.9rem; background: transparent; }
.pdv-search-clear { background: none; border: none; color: #9ca3af; cursor: pointer; padding: 0 0.5rem; font-size: 1.2rem; }
.pdv-scan-btn { width: 44px; height: 44px; border-radius: 0.625rem; border: 2px solid #e5e7eb; background: white; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #374151; flex-shrink: 0; }
.pdv-scan-btn:hover { border-color: #f97316; color: #f97316; }

.pdv-results { flex: 1; overflow-y: auto; }
.pdv-result-row { display: grid; grid-template-columns: 46px minmax(0, 1fr); align-items: center; gap: 0.625rem; padding: 0.5rem 0.75rem; border-bottom: 1px solid #f3f4f6; cursor: pointer; transition: background 0.1s; }
.pdv-result-row:hover { background: #fff7ed; }
.pdv-result-thumb { width: 46px; height: 46px; border-radius: 0.375rem; overflow: hidden; flex-shrink: 0; background: #f3f4f6; border: 1px solid #e5e7eb; }
.pdv-result-img { width: 100%; height: 100%; object-fit: cover; }
.pdv-result-no-img { width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; font-weight: 800; color: #9ca3af; }
.pdv-result-left { flex: 1; min-width: 0; }
.pdv-result-name { font-weight: 600; font-size: 0.85rem; color: #111827; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.pdv-result-meta { overflow-wrap: anywhere; font-size: 0.72rem; color: #9ca3af; }
.pdv-result-sku { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.65rem; color: #d1d5db; font-family: monospace; }
.pdv-result-right { grid-column: 1 / -1; min-width: 0; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto 36px; align-items: center; gap: 0.5rem; }
.pdv-result-stock { min-width: 0; overflow-wrap: anywhere; font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.375rem; border-radius: 0.3rem; }
.stock-ok  { background: #d1fae5; color: #065f46; }
.stock-low { background: #fef3c7; color: #92400e; }
.stock-unknown { background: #fffbeb; color: #92400e; }
.pdv-result-row.is-unavailable { cursor: not-allowed; }
.pdv-result-add:disabled { opacity: .4; cursor: not-allowed; }
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

/* Keep a full-width identity row on phones and split-screen tablets. */
@media (max-width: 420px) {
  .pdv-result-right { grid-template-columns: minmax(0, 1fr) auto 36px; gap: .375rem .5rem; }
  .pdv-result-stock { grid-column: 1; grid-row: 1; justify-self: start; }
  .pdv-stock-location { grid-column: 1; grid-row: 2; }
  .pdv-result-price { grid-column: 2; grid-row: 1 / 3; }
  .pdv-result-add { grid-column: 3; grid-row: 1 / 3; }
}
@media (min-width: 1240px) {
  .pdv-result-row { grid-template-columns: 46px minmax(0, 1fr) auto; }
  .pdv-result-right { grid-column: auto; grid-template-columns: minmax(0, 140px) 110px auto 36px; }
}

/* ── Cart panel (unified) ─────────────────────────────────────────────────── */
.pdv-panel-cart { display: flex; flex-direction: column; overflow: hidden; background: white; }
.pdv-cart-header { display: flex; align-items: center; gap: 0.5rem; padding: 0.75rem 0.875rem; border-bottom: 2px solid #f3f4f6; flex-shrink: 0; }
.pdv-cart-title { font-size: 0.95rem; font-weight: 700; color: #111827; }
.pdv-cart-count { font-size: 0.75rem; color: #9ca3af; flex: 1; }
.pdv-cart-clear { background: none; border: none; cursor: pointer; color: #dc2626; font-size: 1rem; padding: 0.2rem; }

/* Scrollable body */
.pdv-cart-scroll { flex: 1; overflow-y: auto; display: flex; flex-direction: column; }


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
.pdv-ci-controls { display: grid; grid-template-columns: 94px minmax(0,1fr) 32px; align-items: center; gap: 6px; }
.pdv-qty-stepper { display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; }
.qty-btn { width: 30px; min-width: 30px; height: 36px; padding: 0; border: none; background: #f9fafb; cursor: pointer; font-size: 1rem; color: #374151; }
.qty-btn:hover:not(:disabled) { background: #f3f4f6; }
.qty-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.qty-input { width: 32px; min-width: 0; border: none; outline: none; text-align: center; font-size: 0.85rem; font-weight: 600; padding: 0; height: 36px; }
.pdv-ci-price-wrap { display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; min-width: 0; height: 36px; }
.pdv-ci-currency { padding: 0 0.3rem; font-size: 0.68rem; color: #9ca3af; background: #f9fafb; border: 0; border-right: 1px solid #e5e7eb; white-space: nowrap; width: 62px; min-width: 0; height: 36px; font-size: 13px; }
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
.pay-fixed-currency { flex-shrink:0; border-radius:999px; padding:6px 10px; font-size:.78rem; font-weight:700; color:#1d4ed8; background:#eff6ff; align-self:center; }
.pay-validation { margin:4px 14px 8px; color:#b45309; font-size:.75rem; }
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
.pay-select { flex: 1; min-width: 0; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.35rem; font-size: 0.78rem; background: white; outline: none; }
.pay-select-sm { flex: 0 0 54px; }
.pay-input-wrap { flex: 1; min-width: 0; display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; background: white; }
.pay-amount-input { flex: 1; border: none; outline: none; padding: 0.35rem; font-size: 0.85rem; min-width: 0; }
.pay-btn-total { background: #1d4ed8; color: white; border: none; border-radius: 0.4rem; padding: 0.35rem 0.45rem; font-weight: 700; cursor: pointer; font-size: 0.72rem; white-space: nowrap; flex-shrink: 0; }
.pay-btn-total:hover { background: #1e40af; }
.pay-ref-input { flex: 1; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.35rem; font-size: 0.78rem; outline: none; min-width: 0; }
.pay-btn-add { background: #111827; color: white; border: none; border-radius: 0.4rem; padding: 0.35rem 0.55rem; font-weight: 700; cursor: pointer; font-size: 0.78rem; white-space: nowrap; }
.pay-btn-add:disabled { opacity: 0.5; cursor: not-allowed; }
.pay-rate-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; font-size: 0.7rem; color: #6b7280; margin-top: 0.2rem; }
.pay-rate-input { width: 95px; min-width: 0; border: 1px solid #e5e7eb; border-radius: 0.3rem; padding: 0.15rem 0.3rem; font-size: 0.75rem; outline: none; }
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

/* ── Toast ────────────────────────────────────────────────────────────────── */
.pdv-toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%); padding: 0.6rem 1.25rem; border-radius: 2rem; font-size: 0.85rem; font-weight: 600; z-index: 9999; pointer-events: none; white-space: nowrap; box-shadow: 0 4px 16px rgba(0,0,0,0.15); }
.toast-success { background: #111827; color: white; }
.toast-error   { background: #dc2626; color: white; }
.toast-fade-enter-active, .toast-fade-leave-active { transition: all 0.25s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(8px); }

/* ── Mobile ───────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
  .mobile-only { display: flex; }
  .pdv-layout { grid-template-columns: minmax(0,1fr); grid-template-rows: minmax(0,1fr); }
  .pdv-panel-products, .pdv-panel-cart { min-height: 0; }
  .mobile-hidden { display: none !important; }
  .pdv-panel-products, .pdv-panel-cart { border-right: none; }
  .pdv-result-stock { white-space: normal; }
  .pdv-stock-location { cursor: pointer; }
  .pdv-rate-btn { padding: 0.25rem 0.4rem; }
  .pdv-rate-pill { font-size: 0.65rem; }
}
.pdv-ci-line-summary { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pdv-ci-line-summary .pdv-ci-total { font-size: .78rem; }
.pdv-ci-price { width: 100%; height: 36px; box-sizing: border-box; }
.pdv-qty-stepper input::-webkit-inner-spin-button { -webkit-appearance: none; }
.pdv-qty-stepper input { appearance: textfield; -moz-appearance: textfield; }
.pdv-results-label { font-size: .75rem; color: #64748b; margin: 0; padding: 10px 12px 4px; }
.pay-cash-currency { border: 1px solid #cbd5e1; border-radius: 8px; padding: 6px; background: #fff; color: #1d4ed8; max-width: 90px; }
.pay-add-row { flex-wrap: wrap; }
.pay-ref-input { flex-basis: 100%; order: 2; }
.pdv-ci-controls .pdv-ci-remove { align-self: center; }
@media (max-width: 380px) {
  .pdv-ci-thumb { width: 30px; height: 30px; }
  .pdv-cart-item { padding-inline: 8px; gap: 6px; }
  .pdv-ci-controls { grid-template-columns: 86px minmax(0,1fr) 32px; gap: 4px; }
  .qty-btn { width: 28px; min-width: 28px; }
  .qty-input { width: 28px; }
  .pdv-ci-currency { width: 57px; }
}
.pdv-rates-status { padding: 6px 12px; font-size: 12px; color: #92400e; background: #fffbeb; display: flex; align-items: center; gap: 8px; }
</style>
