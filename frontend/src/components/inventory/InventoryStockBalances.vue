<template>
  <span class="stock-balances" role="group" :aria-label="label" :title="label">
    <span aria-hidden="true">{{ displayStock(loja) }} {{ tr('L') }}</span>
    <span class="balance-separator" aria-hidden="true">{{ ' | ' }}</span>
    <span aria-hidden="true">{{ displayStock(deposito) }} {{ tr('D') }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { displayStock } from '@/services/inventoryStock'
import { useInventoryI18n } from './i18n'

const props = defineProps<{ loja: number | null | undefined; deposito: number | null | undefined }>()
const { tr } = useInventoryI18n()
const label = computed(() => tr('Loja: {loja} · Depósito: {deposito}', {
  loja: displayStock(props.loja) === '—' ? tr('Não informado') : displayStock(props.loja),
  deposito: displayStock(props.deposito) === '—' ? tr('Não informado') : displayStock(props.deposito),
}))
</script>

<style scoped>
.stock-balances { display:inline-flex; flex-wrap:wrap; align-items:baseline; column-gap:3px; font-variant-numeric:tabular-nums; line-height:1.3; }
.stock-balances > span { white-space:nowrap; }
.balance-separator { opacity:.5; font-weight:400; }
</style>
