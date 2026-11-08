<template>
  <span class="stock-balances" role="group" :aria-label="label" :title="label">
    <span aria-hidden="true">{{ displayStock(availableLoja) }} {{ tr('L') }}</span>
    <span class="balance-separator" aria-hidden="true">{{ ' | ' }}</span>
    <span aria-hidden="true">{{ displayStock(availableDeposito) }} {{ tr('D') }}</span>
    <a v-if="reservedTotal && orderQuery" class="reserved-count" :href="`#/pedidos?q=${encodeURIComponent(orderQuery)}`"
      :title="tr('Ver pedidos com este produto')" @click.stop @pointerdown.stop>{{ tr('{count} reservado(s)', { count: reservedTotal }) }}</a>
    <span v-else-if="reservedTotal" class="reserved-count">{{ tr('{count} reservado(s)', { count: reservedTotal }) }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { displayStock } from '@/services/inventoryStock'
import { useInventoryI18n } from './i18n'

const props = defineProps<{ loja: number | null | undefined; deposito: number | null | undefined;
  reservedLoja?: number; reservedDeposito?: number; orderQuery?: string }>()
const { tr } = useInventoryI18n()
const reservedTotal = computed(() => (props.reservedLoja || 0) + (props.reservedDeposito || 0))
const availableLoja = computed(() => typeof props.loja === 'number' ? props.loja - (props.reservedLoja || 0) : props.loja)
const availableDeposito = computed(() => typeof props.deposito === 'number' ? props.deposito - (props.reservedDeposito || 0) : props.deposito)
const label = computed(() => reservedTotal.value ? tr('Disponível: {loja} na loja · {deposito} no depósito. Reservado: {reservedLoja} na loja · {reservedDeposito} no depósito.', {
  loja: displayStock(availableLoja.value), deposito: displayStock(availableDeposito.value),
  reservedLoja: props.reservedLoja || 0, reservedDeposito: props.reservedDeposito || 0,
}) : tr('Loja: {loja} · Depósito: {deposito}', {
  loja: displayStock(props.loja) === '—' ? tr('Não informado') : displayStock(props.loja),
  deposito: displayStock(props.deposito) === '—' ? tr('Não informado') : displayStock(props.deposito),
}))
</script>

<style scoped>
.stock-balances { display:inline-flex; flex-wrap:wrap; align-items:baseline; column-gap:3px; font-variant-numeric:tabular-nums; line-height:1.3; }
.stock-balances > span { white-space:nowrap; }
.balance-separator { opacity:.5; font-weight:400; }
.reserved-count { color:#92400e; background:#fffbeb; padding:1px 4px; border-radius:4px; font-size:.8em; font-weight:500; }
a.reserved-count { text-underline-offset:2px; }
a.reserved-count:focus-visible { outline:2px solid #2563eb; outline-offset:2px; }
</style>
