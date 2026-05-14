<template>
  <div class="pay-overlay" @click.self="$emit('close')">
    <div class="pay-modal">
      <!-- Header -->
      <div class="pay-header">
        <div>
          <h2 class="pay-title">Pagamento</h2>
          <p class="pay-total-label">Total a pagar</p>
          <p class="pay-total">{{ fmtGs(total) }}</p>
        </div>
        <button class="pay-close" @click="$emit('close')">×</button>
      </div>

      <!-- Discount row -->
      <div class="pay-discount-row">
        <span class="pay-discount-label">Desconto global</span>
        <div class="pay-discount-input-wrap">
          <span class="pay-currency-prefix">G$</span>
          <input
            v-model.number="localDiscount"
            type="number" min="0" class="pay-discount-input"
            placeholder="0"
            @input="$emit('update:discount', localDiscount)"
          />
        </div>
        <span class="pay-subtotal-hint">Subtotal: {{ fmtGs(subtotal) }}</span>
      </div>

      <!-- Payment entries -->
      <div class="pay-entries">
        <div v-for="p in localPayments" :key="p.id" class="pay-entry">
          <div class="pay-entry-method">
            <span class="pay-method-badge" :class="`method-${p.method}`">{{ methodLabel(p.method) }}</span>
            <span v-if="p.reference" class="pay-entry-ref">{{ p.reference }}</span>
          </div>
          <div class="pay-entry-amounts">
            <span v-if="p.currency !== 'GS'" class="pay-orig-amount">
              {{ p.currency }} {{ fmtNum(p.amount_original) }}
            </span>
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
            <option value="GS">G$</option>
            <option value="BRL">R$</option>
            <option value="USD">U$</option>
            <option value="EUR">€</option>
          </select>
        </div>
        <div class="pay-add-row">
          <div class="pay-input-wrap">
            <span class="pay-currency-prefix">{{ currencySymbol }}</span>
            <input
              v-model.number="newAmount"
              ref="amountInput"
              type="number" min="0" class="pay-amount-input"
              :placeholder="remaining > 0 ? fmtNum(remainingInCurrency) : '0'"
              @keydown.enter="addPayment"
            />
          </div>
          <input
            v-if="showReference"
            v-model="newReference"
            type="text" class="pay-ref-input"
            :placeholder="referencePlaceholder"
          />
          <button class="pay-btn-add" @click="addPayment" :disabled="!newAmount">
            + Adicionar
          </button>
        </div>
        <div v-if="newCurrency !== 'GS'" class="pay-rate-row">
          <span>Taxa:</span>
          <input v-model.number="newRate" type="number" min="0" step="0.01" class="pay-rate-input" />
          <span>{{ newCurrency }}/G$</span>
          <span class="pay-converted">= {{ fmtGs(newAmount * newRate) }}</span>
        </div>
      </div>

      <!-- Summary -->
      <div class="pay-summary">
        <div class="pay-sum-row">
          <span>Total</span>
          <span>{{ fmtGs(total) }}</span>
        </div>
        <div class="pay-sum-row">
          <span>Pago</span>
          <span :class="totalPaid >= total ? 'pay-ok' : 'pay-short'">{{ fmtGs(totalPaid) }}</span>
        </div>
        <div v-if="troco > 0" class="pay-sum-row pay-troco-row">
          <span>Troco</span>
          <span class="pay-troco">{{ fmtGs(troco) }}</span>
        </div>
        <div v-if="remaining > 0" class="pay-sum-row pay-remaining-row">
          <span>Faltando</span>
          <span class="pay-remaining">{{ fmtGs(remaining) }}</span>
        </div>
      </div>

      <!-- Footer -->
      <div class="pay-footer">
        <button class="pay-btn-cancel" @click="$emit('close')">Cancelar</button>
        <button
          class="pay-btn-confirm"
          :disabled="!canConfirm || loading"
          @click="confirm"
        >
          <span v-if="loading">Processando…</span>
          <span v-else>Confirmar pagamento ✓</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import type { CartPayment } from '@/stores/pdv'

const props = defineProps<{
  total: number
  subtotal: number
  discount: number
  payments: CartPayment[]
  loading: boolean
  exchangeRates?: { brl: number; usd: number; eur: number }
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'confirm', payments: CartPayment[], discount: number): void
  (e: 'update:discount', val: number): void
}>()

const PAYMENT_METHODS = [
  { value: 'cash_gs',      label: '💵 Dinheiro G$' },
  { value: 'cash_brl',     label: '💵 Dinheiro R$' },
  { value: 'cash_usd',     label: '💵 Dinheiro U$' },
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

const localPayments = ref<CartPayment[]>([...props.payments])
const localDiscount = ref(props.discount)
const newMethod = ref('cash_gs')
const newCurrency = ref('GS')
const newAmount = ref<number>(0)
const newRate = ref(1)
const newReference = ref('')
const amountInput = ref<HTMLInputElement>()

watch(() => props.payments, (v) => { localPayments.value = [...v] })
watch(() => props.discount, (v) => { localDiscount.value = v })
watch(newMethod, (m) => {
  newCurrency.value = methodCurrency(m)
  newRate.value = defaultRate(newCurrency.value)
  newReference.value = ''
})
watch(newCurrency, (c) => { newRate.value = defaultRate(c) })

function methodCurrency(m: string) {
  if (m === 'cash_brl' || m === 'pix' || m === 'transfer_br' || m === 'pix_cambista' || m === 'mercadopago') return 'BRL'
  if (m === 'cash_usd') return 'USD'
  if (m === 'cash_eur') return 'EUR'
  return 'GS'
}
function defaultRate(c: string) {
  if (!props.exchangeRates) return 1
  if (c === 'BRL') return props.exchangeRates.brl
  if (c === 'USD') return props.exchangeRates.usd
  if (c === 'EUR') return props.exchangeRates.eur
  return 1
}
function methodLabel(m: string) {
  return PAYMENT_METHODS.find(x => x.value === m)?.label.replace(/^.{2}/, '').trim() || m
}

const currencySymbol = computed(() => ({ GS: 'G$', BRL: 'R$', USD: 'U$', EUR: '€' }[newCurrency.value] ?? newCurrency.value))
const showReference = computed(() => ['card', 'pix', 'transfer_br', 'transfer_py', 'pix_cambista', 'mercadopago'].includes(newMethod.value))
const referencePlaceholder = computed(() => {
  if (newMethod.value === 'card') return 'Últimos 4 dígitos'
  if (['pix', 'pix_cambista', 'mercadopago'].includes(newMethod.value)) return 'Chave / referência'
  return 'Referência'
})

const totalPaid = computed(() => localPayments.value.reduce((s, p) => s + p.amount_gs, 0))
const remaining = computed(() => Math.max(0, props.total - totalPaid.value))
const troco = computed(() => Math.max(0, totalPaid.value - props.total))
const remainingInCurrency = computed(() =>
  newCurrency.value === 'GS' ? remaining.value : remaining.value / (newRate.value || 1)
)
const canConfirm = computed(() => totalPaid.value >= props.total && localPayments.value.length > 0)

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

function confirm() {
  emit('confirm', localPayments.value, localDiscount.value)
}

function fmtGs(v: number) {
  return 'G$ ' + Math.round(v).toLocaleString('es-PY')
}
function fmtNum(v: number) {
  return v.toLocaleString('es-PY', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}
</script>

<style scoped>
.pay-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.55);
  display: flex; align-items: center; justify-content: center;
  z-index: 1500; padding: 1rem; box-sizing: border-box;
}
.pay-modal {
  background: white; border-radius: 1rem;
  width: 100%; max-width: 480px;
  max-height: 95dvh; max-height: 95vh;
  overflow-y: auto; display: flex; flex-direction: column;
  box-shadow: 0 25px 70px rgba(0,0,0,0.2);
}
.pay-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  padding: 1.25rem 1.25rem 0.75rem; background: #f97316; color: white;
  border-radius: 1rem 1rem 0 0;
}
.pay-title { margin: 0; font-size: 1.1rem; font-weight: 700; }
.pay-total-label { margin: 0.2rem 0 0; font-size: 0.72rem; opacity: 0.85; }
.pay-total { margin: 0.1rem 0 0; font-size: 1.8rem; font-weight: 800; line-height: 1; }
.pay-close { background: rgba(255,255,255,0.2); border: none; color: white; font-size: 1.4rem; border-radius: 50%; width: 2rem; height: 2rem; cursor: pointer; display: flex; align-items: center; justify-content: center; }

.pay-discount-row {
  display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
  padding: 0.75rem 1.25rem; border-bottom: 1px solid #f3f4f6; background: #fff7ed;
}
.pay-discount-label { font-size: 0.78rem; font-weight: 600; color: #92400e; flex-shrink: 0; }
.pay-discount-input-wrap { display: flex; align-items: center; border: 1.5px solid #fed7aa; border-radius: 0.4rem; overflow: hidden; background: white; }
.pay-currency-prefix { padding: 0.3rem 0.4rem; font-size: 0.75rem; color: #9ca3af; background: #f9fafb; border-right: 1px solid #e5e7eb; }
.pay-discount-input { border: none; outline: none; width: 90px; padding: 0.3rem 0.4rem; font-size: 0.9rem; }
.pay-subtotal-hint { font-size: 0.72rem; color: #9ca3af; }

.pay-entries { padding: 0.75rem 1.25rem; min-height: 3rem; }
.pay-entry { display: flex; align-items: center; gap: 0.5rem; padding: 0.4rem 0.5rem; border-radius: 0.4rem; margin-bottom: 0.35rem; background: #f9fafb; }
.pay-entry-method { flex: 1; display: flex; align-items: center; gap: 0.4rem; }
.pay-method-badge { font-size: 0.72rem; font-weight: 700; padding: 0.15rem 0.4rem; border-radius: 0.3rem; background: #e5e7eb; color: #374151; }
.method-cash_gs  { background: #d1fae5; color: #065f46; }
.method-cash_brl { background: #dbeafe; color: #1e40af; }
.method-cash_usd { background: #fef9c3; color: #713f12; }
.method-cash_eur { background: #ede9fe; color: #4c1d95; }
.method-card     { background: #f0fdf4; color: #166534; }
.method-pix      { background: #ecfdf5; color: #065f46; }
.method-fiado    { background: #fef3c7; color: #92400e; }
.pay-entry-ref { font-size: 0.7rem; color: #9ca3af; }
.pay-entry-amounts { display: flex; flex-direction: column; align-items: flex-end; }
.pay-orig-amount { font-size: 0.7rem; color: #9ca3af; }
.pay-gs-amount { font-size: 0.85rem; font-weight: 700; color: #111827; }
.pay-entry-remove { background: none; border: none; color: #dc2626; cursor: pointer; font-size: 1.1rem; padding: 0; }
.pay-empty { font-size: 0.8rem; color: #9ca3af; text-align: center; padding: 0.75rem 0; }

.pay-add-section { padding: 0.75rem 1.25rem; border-top: 1px solid #f3f4f6; border-bottom: 1px solid #f3f4f6; background: #f9fafb; }
.pay-add-row { display: flex; gap: 0.4rem; margin-bottom: 0.4rem; }
.pay-select { flex: 1; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.45rem 0.5rem; font-size: 0.82rem; background: white; outline: none; }
.pay-select-sm { flex: 0 0 70px; }
.pay-input-wrap { flex: 1; display: flex; align-items: center; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; overflow: hidden; background: white; }
.pay-amount-input { flex: 1; border: none; outline: none; padding: 0.45rem 0.5rem; font-size: 0.9rem; min-width: 0; }
.pay-ref-input { flex: 1; border: 1.5px solid #e5e7eb; border-radius: 0.4rem; padding: 0.45rem 0.5rem; font-size: 0.82rem; outline: none; }
.pay-btn-add { background: #111827; color: white; border: none; border-radius: 0.4rem; padding: 0.45rem 0.75rem; font-weight: 600; cursor: pointer; white-space: nowrap; font-size: 0.82rem; }
.pay-btn-add:disabled { opacity: 0.5; cursor: not-allowed; }
.pay-rate-row { display: flex; align-items: center; gap: 0.4rem; font-size: 0.75rem; color: #6b7280; }
.pay-rate-input { width: 80px; border: 1px solid #e5e7eb; border-radius: 0.3rem; padding: 0.2rem 0.4rem; font-size: 0.8rem; outline: none; }
.pay-converted { font-weight: 600; color: #059669; }

.pay-summary { padding: 0.75rem 1.25rem; }
.pay-sum-row { display: flex; justify-content: space-between; font-size: 0.9rem; padding: 0.2rem 0; color: #374151; }
.pay-ok { color: #059669; font-weight: 700; }
.pay-short { color: #dc2626; font-weight: 700; }
.pay-troco-row { font-weight: 700; color: #059669; border-top: 1px solid #e5e7eb; margin-top: 0.25rem; padding-top: 0.4rem; }
.pay-troco { color: #059669; }
.pay-remaining-row { font-weight: 700; color: #dc2626; border-top: 1px solid #e5e7eb; margin-top: 0.25rem; padding-top: 0.4rem; }
.pay-remaining { color: #dc2626; }

.pay-footer { display: flex; gap: 0.75rem; padding: 1rem 1.25rem; border-top: 1px solid #f3f4f6; }
.pay-btn-cancel { flex: 1; padding: 0.7rem; border: 1.5px solid #e5e7eb; border-radius: 0.5rem; background: white; color: #6b7280; font-weight: 600; cursor: pointer; }
.pay-btn-confirm { flex: 2; padding: 0.7rem; border: none; border-radius: 0.5rem; background: #16a34a; color: white; font-weight: 700; font-size: 0.95rem; cursor: pointer; }
.pay-btn-confirm:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
