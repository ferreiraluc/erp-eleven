<template>
  <div class="avulso-overlay erp-dialog-backdrop" @click.self="$emit('close')">
    <div v-erp-dialog class="avulso-modal erp-dialog erp-dialog--sm" role="dialog" aria-modal="true" aria-labelledby="avulso-title">
      <div class="avulso-header erp-dialog__header">
        <div class="avulso-icon">⚠</div>
        <div>
          <h3 id="avulso-title">{{ uiText(`Produto não encontrado`) }}</h3>
          <p>{{ uiText(`Adicione manualmente ao carrinho`) }}</p>
        </div>
        <button data-dialog-close :aria-label="uiText('Fechar')" class="avulso-close erp-button erp-button--secondary erp-button--icon" @click="$emit('close')">×</button>
      </div>

      <div class="avulso-body erp-dialog__body">
        <div v-if="scannedCode" class="avulso-code-hint"> {{ uiText(`Código escaneado:`) }} <strong>{{ scannedCode }}</strong>
        </div>

        <div class="avulso-field">
          <label>{{ uiText(`Descrição do produto *`) }}</label>
          <input
            ref="nameInput"
            v-model="form.item_name"
            type="text"
            :placeholder="uiText(`Ex: Camiseta azul M`)"
            class="avulso-input"
            @keydown.enter="focusPrice"
          />
        </div>

        <div class="avulso-field">
          <label for="avulso-currency">{{ text('currency') }}</label>
          <select id="avulso-currency" v-model="form.currency" class="avulso-input">
            <option value="PYG">🇵🇾 G$</option>
            <option value="BRL">🇧🇷 R$</option>
            <option value="USD">🇺🇸 U$</option>
            <option value="EUR">🇪🇺 EUR (€)</option>
          </select>
        </div>
        <div class="avulso-row">
          <div class="avulso-field">
            <label for="avulso-price">{{ text('price') }} ({{ currencySymbol }}) *</label>
            <input
              id="avulso-price"
              ref="priceInput"
              v-model.number="form.price"
              type="number"
              min="0"
              :step="form.currency === 'PYG' ? 1 : 0.01"
              inputmode="decimal"
              placeholder="0"
              class="avulso-input"
              @keydown.enter="focusQty"
            />
          </div>
          <div class="avulso-field avulso-field-sm">
            <label>{{ uiText(`Qtd`) }}</label>
            <input
              ref="qtyInput"
              v-model.number="form.quantity"
              type="number"
              min="0.001"
              step="0.001"
              max="9999999.999"
              class="avulso-input"
              @keydown.enter="submit"
            />
          </div>
        </div>

        <div v-if="validRate && form.currency !== 'PYG'" class="avulso-conversion" aria-live="polite">
          <strong>{{ text('conversion') }}: G$ {{ formatNumber(priceGs) }}</strong>
          <small>{{ text('rate') }}: 1 {{ currencySymbol }} = G$ {{ formatNumber(rate) }}</small>
        </div>
        <div v-if="!validRate" class="avulso-error" role="alert">{{ text('invalidRate') }}</div>

        <div v-if="error" class="avulso-error">{{ error }}</div>
        <div v-if="quantityError" class="avulso-error" role="alert">{{ cartErrorText(quantityError) }}</div>
      </div>

      <div class="avulso-footer erp-dialog__footer">
        <button class="avulso-btn-cancel erp-button erp-button--secondary" @click="$emit('close')">{{ uiText(`Cancelar`) }}</button>
        <button class="avulso-btn-add erp-button erp-button--primary" @click="submit" :disabled="!canSubmit"> {{ uiText(`+ Adicionar ao carrinho`) }} </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { vErpDialog } from '@/directives/erpDialog'
import { uiText, uiLocale } from '@/i18n/uiText'
import { usePdvEntryText } from './entryMessages'
import { validateQuantity } from '@/services/pdvCart'
import { usePdvCartText } from './cartMessages'
const { cartErrorText } = usePdvCartText()
import { ref, computed, nextTick, onMounted } from 'vue'

type ItemCurrency = 'PYG' | 'BRL' | 'USD' | 'EUR'
const props = withDefaults(defineProps<{
  scannedCode?: string | null
  rates?: Record<ItemCurrency, number>
}>(), { rates: () => ({ PYG: 1, BRL: 0, USD: 0, EUR: 0 }) })
const text = usePdvEntryText()

const emit = defineEmits<{
  (e: 'add', item: {
    item_name: string
    quantity: number
    unit_price_gs: number
    original_price: number
    sale_currency: string
    image_data: null
    is_avulso: true
    item_id: null
    item_sku: null
    item_category: null
    item_size: null
    item_color: null
    original_price_gs: null
    discount_gs: number
    location: string
  }): void
  (e: 'close'): void
}>()

const nameInput = ref<HTMLInputElement>()
const priceInput = ref<HTMLInputElement>()
const qtyInput = ref<HTMLInputElement>()

const form = ref({
  item_name: '',
  price: 0,
  currency: 'PYG' as ItemCurrency,
  quantity: 1,
})
const error = ref('')
const quantityError = ref<unknown>(null)
const rate = computed(() => form.value.currency === 'PYG' ? 1 : props.rates[form.value.currency])
const validRate = computed(() => Number.isFinite(rate.value) && rate.value > 0)
const priceGs = computed(() => Math.round(form.value.price * rate.value))
const currencySymbol = computed(() => ({ PYG: 'G$', BRL: 'R$', USD: 'U$', EUR: 'EUR' }[form.value.currency]))
const formatNumber = (value: number) => Number.isFinite(value) ? value.toLocaleString(uiLocale(), { maximumFractionDigits: 2 }) : '—'

const canSubmit = computed(() =>
  form.value.item_name.trim().length >= 2 && Number.isFinite(form.value.price) && form.value.price > 0 &&
  validRate.value && Number.isFinite(priceGs.value) && priceGs.value > 0
)

onMounted(() => nextTick(() => nameInput.value?.focus()))

function focusPrice() { priceInput.value?.focus() }
function focusQty() { qtyInput.value?.focus() }

function submit() {
  if (!form.value.item_name.trim()) { error.value = uiText(`Informe a descrição`); return }
  if (!validRate.value) { error.value = text('invalidRate'); return }
  if (!canSubmit.value) { error.value = uiText(`Informe o preço`); return }
  quantityError.value = null
  try { validateQuantity(form.value.quantity, false) } catch (error) { quantityError.value = error; return }
  error.value = ''
  emit('add', {
    item_id: null,
    item_name: form.value.item_name.trim(),
    item_sku: null,
    item_category: null,
    item_size: null,
    item_color: null,
    quantity: form.value.quantity,
    unit_price_gs: priceGs.value,
    original_price_gs: null,
    original_price: form.value.price,
    sale_currency: form.value.currency,
    image_data: null,
    discount_gs: 0,
    is_avulso: true,
    location: 'loja',
  })
}
</script>

<style scoped>
.avulso-overlay {
  position: fixed; inset: 0;
  background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 2000; padding: 1rem;
}
.avulso-modal {
  background: white; border-radius: 1rem;
  width: 100%; max-width: 420px;
  max-height: calc(100dvh - 2rem); overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,0.2);
}
.avulso-header {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 1.25rem 1.25rem 0.75rem;
  border-bottom: 1px solid #f3f4f6;
}
.avulso-icon { font-size: 1.75rem; line-height: 1; }
.avulso-header h3 { margin: 0; font-size: 1rem; font-weight: 700; color: #111827; }
.avulso-header p  { margin: 0; font-size: 0.75rem; color: #9ca3af; }
.avulso-close {
  margin-left: auto; background: none; border: none;
  font-size: 1.5rem; color: #6b7280; cursor: pointer; line-height: 1;
}
.avulso-body { padding: 1rem 1.25rem; }
.avulso-code-hint {
  background: #f0fdf4; border: 1px solid #bbf7d0;
  border-radius: 0.5rem; padding: 0.5rem 0.75rem;
  font-size: 0.8rem; color: #166534; margin-bottom: 1rem;
}
.avulso-field { display: flex; flex-direction: column; min-width: 0; gap: 0.3rem; margin-bottom: 0.75rem; }
.avulso-field label { font-size: 0.78rem; font-weight: 600; color: #374151; }
.avulso-row { display: grid; grid-template-columns: minmax(0, 1fr) 90px; gap: 0.75rem; }
.avulso-field-sm { min-width: 80px; }
.avulso-input {
  width: 100%; min-width: 0; box-sizing: border-box;
  border: 1.5px solid #e5e7eb; border-radius: 0.5rem;
  padding: 0.6rem 0.75rem; font-size: 0.95rem;
  outline: none; transition: border-color 0.15s;
}
.avulso-conversion { display: flex; flex-direction: column; gap: .25rem; padding: .6rem .75rem; border-radius: .5rem; background: #eff6ff; color: #1e40af; font-size: .8rem; margin-bottom: .75rem; }
.avulso-conversion small { font-size: .72rem; }
.avulso-input:focus { border-color: #f97316; }
.avulso-error { color: #dc2626; font-size: 0.8rem; margin-top: 0.25rem; }
.avulso-footer {
  display: flex; gap: 0.75rem;
  padding: 0.875rem 1.25rem;
  border-top: 1px solid #f3f4f6;
}
.avulso-btn-cancel {
  flex: 1; padding: 0.6rem; border: 1.5px solid #e5e7eb;
  border-radius: 0.5rem; background: white; color: #6b7280;
  font-weight: 600; cursor: pointer;
}
.avulso-btn-add {
  flex: 2; padding: 0.6rem; border: none;
  border-radius: 0.5rem; background: #f97316; color: white;
  font-weight: 700; cursor: pointer; font-size: 0.9rem;
}
.avulso-btn-add:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
