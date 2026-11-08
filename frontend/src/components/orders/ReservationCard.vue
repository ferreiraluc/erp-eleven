<template>
  <article class="reservation-card" :class="pedido.commerce_status">
    <button class="reservation-card-main" @click="emit('view', pedido)">
      <div class="card-top"><span class="number">{{ pedido.numero_pedido }}</span><span class="state">{{ reservationStatusLabel(pedido.commerce_status, paid, balance) }}</span></div>
      <div class="customer-row"><span class="bag-symbol"><ShoppingBag :size="22" /></span><div><h3>{{ pedido.cliente_nome || uiText('Cliente') }}</h3><p>{{ pedido.descricao }}</p></div><ChevronRight :size="18" class="chevron" /></div>
      <div class="amount-row"><strong>{{ saleUsd(pedido.total_gs || 0, pedido.usd_rate_gs) }}</strong><span v-if="pedido.commerce_status === 'reserved'">{{ uiText('Falta') }} <b>{{ saleUsd(balance, pedido.usd_rate_gs) }}</b></span><span v-else-if="pedido.sale_id">{{ uiText('Vinculado à venda') }}</span></div>
      <div v-if="paid > 0 && pedido.commerce_status === 'reserved'" class="payment-progress" :aria-label="uiText('{0}% pago', { 0: percentage })"><span :style="{ width: `${percentage}%` }" /></div>
    </button>
    <footer><span><Clock3 :size="12" />{{ formatDateTime(pedido.reserved_at || pedido.created_at, { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) }}</span><button class="erp-button erp-button--ghost erp-button--sm" @click="emit('view', pedido)">{{ uiText(pedido.commerce_status === 'reserved' ? 'Abrir separação' : 'Ver detalhes') }}</button></footer>
  </article>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { ShoppingBag, ChevronRight, Clock3 } from 'lucide-vue-next'
import type { Pedido } from '@/services/api'
import { reservationStatusLabel } from '@/services/orderReservations'
import { saleUsd } from '@/services/saleUsd'
import { formatDateTime } from '@/utils/datetime'
import { uiText } from '@/i18n/uiText'
const props = defineProps<{ pedido: Pedido }>()
const emit = defineEmits<{ view: [pedido: Pedido] }>()
const paid = computed(() => Number(props.pedido.paid_gs || 0)), balance = computed(() => Math.max(0, Number(props.pedido.total_gs || 0) - paid.value))
const percentage = computed(() => Math.min(100, Math.round(paid.value / Math.max(Number(props.pedido.total_gs || 0), 1) * 100)))
</script>
<style scoped>
.reservation-card{border:1px solid #dce5f0;border-radius:16px;background:white;box-shadow:0 2px 6px #0f172a04;overflow:hidden;transition:border-color .15s,box-shadow .15s}.reservation-card:hover{border-color:#b8cdf5;box-shadow:0 5px 18px #2563eb09}.reservation-card-main{display:block;width:100%;text-align:left;border:0;background:none;padding:18px;cursor:pointer;font:inherit;color:inherit}.reservation-card-main:focus-visible{outline:2px solid #2563eb;outline-offset:-3px;border-radius:14px}.card-top{display:flex;gap:8px;align-items:center;justify-content:space-between;margin-bottom:17px}.number{font-size:.73rem;font-weight:600;letter-spacing:.025em;color:#64748b}.state{font-size:.64rem;font-weight:650;border-radius:20px;background:#fff7ed;color:#9a3412;padding:4px 8px;line-height:1.3;text-align:right}.completed .state{background:#ecfdf5;color:#047857}.cancelled .state{background:#f1f5f9;color:#64748b}.customer-row{display:flex;gap:11px;align-items:center;min-height:54px}.bag-symbol{display:flex;width:43px;height:47px;align-items:center;justify-content:center;background:#eff6ff;color:#3b82f6;border-radius:12px;flex-shrink:0}.customer-row>div{min-width:0;flex:1}.customer-row h3{margin:0 0 5px;font-size:.96rem;color:#0f172a;overflow-wrap:anywhere}.customer-row p{margin:0;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;font-size:.72rem;color:#64748b;line-height:1.5}.chevron{flex-shrink:0;color:#94a3b8}.amount-row{display:flex;gap:8px;align-items:baseline;justify-content:space-between;margin-top:19px}.amount-row>strong{font-size:1.07rem;color:#1e3a5f}.amount-row>span{font-size:.7rem;color:#64748b}.amount-row b{font-weight:600;color:#334155}.payment-progress{height:4px;background:#e2e8f0;border-radius:5px;overflow:hidden;margin-top:13px}.payment-progress>span{display:block;height:100%;background:#10b981;border-radius:5px}.reservation-card footer{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 14px;border-top:1px solid #edf1f6;background:#fbfcfe}.reservation-card footer>span{display:flex;gap:4px;align-items:center;font-size:.66rem;color:#64748b}.reservation-card footer button{color:#2563eb;font-size:.72rem}.cancelled .bag-symbol{background:#f1f5f9;color:#94a3b8}
</style>
