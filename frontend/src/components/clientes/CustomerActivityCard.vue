<template>
  <article class="cliente-wrap tracking-surface" data-tracking-status="" :class="{ 'is-expanded': expanded, 'is-inactive': !customer.ativo }">
    <div class="cliente-card" :class="{ inactive: !customer.ativo }">
      <button type="button" class="customer-expand" :aria-expanded="expanded" :aria-controls="panelId" :aria-label="t(expanded ? 'collapse' : 'expand', { name: customer.nome })" @click="$emit('toggle')">
        <span class="cliente-avatar" aria-hidden="true">{{ initials }}</span>
        <span class="customer-heading">
          <span class="cliente-name-row"><span class="cliente-name">{{ customer.nome }}</span><span v-if="!customer.ativo" class="badge-inactive">{{ t('inactive') }}</span></span>
          <span class="customer-contact">{{ customer.telefone || customer.email || t('noContact') }}</span>
        </span>
        <svg class="expand-chevron" :class="{ rotated: expanded }" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="20" height="20" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m6 9 6 6 6-6" /></svg>
      </button>

      <div class="customer-overview">
        <div v-if="customer.activity" class="customer-movements">
          <span class="movement" :title="customer.activity.own_sales_only ? t('own') : undefined">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M3 3h2l2 12h12l2-8H6M9 20h.01M18 20h.01" /></svg>
            <strong>{{ number(customer.activity.purchase_count) }}</strong> {{ t('purchases') }}
          </span>
          <span class="movement">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M3 7h11v11H3zM14 11h4l3 4v3h-7M6 20a2 2 0 1 0 0-4 2 2 0 0 0 0 4m12 0a2 2 0 1 0 0-4 2 2 0 0 0 0 4" /></svg>
            <strong>{{ number(customer.activity.shipment_count) }}</strong> {{ t('shipments') }}
          </span>
          <span class="movement" :title="t('printHelp')">
            <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.7" d="M7 8V3h10v5M7 17H4V9h16v8h-3M7 14h10v7H7zM17 11h.01" /></svg>
            <strong>{{ number(customer.activity.print_count) }}</strong> {{ t('prints') }}
          </span>
          <span v-if="customer.activity.order_count" class="movement customer-order-count">{{ number(customer.activity.order_count) }} {{ t(customer.activity.order_count === 1 ? 'order' : 'orders') }}</span>
        </div>
        <p v-else class="customer-summary-unavailable">{{ t('summaryUnavailable') }}</p>
        <div v-if="customer.activity" class="customer-dates">
          <span><span class="date-label">{{ t('lastPurchase') }}</span><time v-if="customer.activity.last_purchase_at" :datetime="customer.activity.last_purchase_at">{{ date(customer.activity.last_purchase_at) }}</time><span v-else>{{ t('noPurchase') }}</span></span>
          <span><span class="date-label">{{ t('lastPrint') }}</span><time v-if="customer.activity.last_print_at" :datetime="customer.activity.last_print_at">{{ date(customer.activity.last_print_at) }}</time><span v-else>{{ t('noPrint') }}</span></span>
        </div>
        <div v-if="customer.activity && (customer.activity.pending_print_count || customer.activity.uncertain_print_count)" class="customer-queue-status">
          <span v-if="customer.activity.pending_print_count">{{ t('pending', { count: customer.activity.pending_print_count }) }}</span>
          <span v-if="customer.activity.uncertain_print_count" class="needs-review">{{ t('uncertain', { count: customer.activity.uncertain_print_count }) }}</span>
        </div>
      </div>
    </div>

    <section v-if="expanded" :id="panelId" class="historico-section" :aria-label="t('history')">
      <div class="customer-expanded-top">
        <dl class="customer-identity"><dt>{{ t('contact') }}</dt><dd v-if="customer.telefone">{{ customer.telefone }}</dd><dd v-if="customer.email">{{ customer.email }}</dd><dd v-if="customer.cpf">{{ customer.cpf }}</dd><dd v-if="customer.endereco">{{ customer.endereco }}</dd><dd v-if="!customer.telefone && !customer.email && !customer.cpf && !customer.endereco">—</dd></dl>
        <div class="cliente-actions">
          <RouterLink :to="{ path: '/enderecos', query: { customer_id: customer.id } }" class="erp-button erp-button--secondary erp-button--sm">{{ t('addresses') }}</RouterLink>
          <button type="button" class="erp-button erp-button--secondary erp-button--sm" :title="t('edit')" @click="$emit('edit')">{{ uiText('Editar') }}</button>
          <button v-if="customer.ativo" type="button" class="erp-button erp-button--danger erp-button--sm" :title="t('deactivate')" @click="$emit('deactivate')">{{ t('deactivate') }}</button>
        </div>
      </div>
      <slot />
    </section>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'
import type { CustomerWithActivity } from '@/services/customerLogistics'
import { uiText } from '@/i18n/uiText'
import { customerMessages } from './customerMessages'
import '@/assets/trackingCards.css'
const props = defineProps<{ customer: CustomerWithActivity; expanded: boolean }>()
defineEmits<{ toggle: []; edit: []; deactivate: [] }>()
const { t, locale } = useI18n({ useScope: 'local', messages: customerMessages })
const panelId = computed(() => `customer-history-${props.customer.id}`)
const initials = computed(() => props.customer.nome.trim().split(/\s+/).slice(0, 2).map(word => word.charAt(0)).join('').toLocaleUpperCase())
const number = (value: number) => value.toLocaleString(locale.value)
const date = (value: string) => new Date(value).toLocaleString(locale.value, { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' })
</script>

<style scoped>
.cliente-wrap { border-radius: 14px; overflow: hidden; --tracking-tint: #f2f7ff; --tracking-edge: #a5bad6; --tracking-accent: #2563eb; }
.cliente-card { padding: 1rem 1.1rem; }
.customer-expand { width: 100%; display: flex; align-items: center; gap: .8rem; border: 0; background: transparent; text-align: left; padding: 0; color: #0f172a; font: inherit; cursor: pointer; }
.customer-expand:focus-visible { outline: 2px solid #1d4ed8; outline-offset: 5px; border-radius: 6px; }
.cliente-avatar { flex: 0 0 42px; height: 42px; display: grid; place-items: center; border: 1px solid #bfdbfe; border-radius: 12px; color: #1d4ed8; background: #eaf2ff; font-weight: 700; font-size: .85rem; }
.customer-heading { flex: 1; min-width: 0; }
.cliente-name-row { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; }
.cliente-name { color: #172033; font-size: .95rem; font-weight: 700; overflow-wrap: anywhere; }
.badge-inactive { background: #e2e8f0; color: #475569; font-size: .7rem; border-radius: 5px; padding: .1rem .35rem; }
.customer-contact { display: block; font-size: .77rem; color: #64748b; margin-top: .25rem; overflow-wrap: anywhere; }
.expand-chevron { flex-shrink: 0; color: #64748b; transition: transform .15s; }
.expand-chevron.rotated { transform: rotate(180deg); }
.customer-overview { margin-top: .85rem; padding-left: 3.45rem; }
.customer-movements { display: flex; gap: .5rem 1rem; align-items: center; flex-wrap: wrap; }
.movement { display: inline-flex; align-items: center; gap: .3rem; color: #64748b; font-size: .74rem; }
.movement svg { height: 15px; width: 15px; color: #64748b; flex-shrink: 0; }
.movement strong { color: #334155; font-size: .82rem; font-weight: 650; }
.customer-order-count { border-left: 1px solid #cbd5e1; padding-left: .85rem; }
.customer-dates { display: flex; flex-wrap: wrap; gap: .45rem 1.8rem; margin-top: .8rem; color: #475569; font-size: .72rem; line-height: 1.6; }
.customer-dates > span { display: flex; flex-direction: column; }
.date-label { color: #64748b; font-size: .68rem; }
.customer-summary-unavailable { color: #64748b; font-size: .75rem; margin: 0; }
.customer-queue-status { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .65rem; color: #64748b; font-size: .7rem; }
.customer-queue-status > span { background: #eef2f6; border-radius: 6px; padding: .15rem .4rem; }
.customer-queue-status .needs-review { color: #92400e; background: #fef3c7; }
.historico-section { padding: 1rem 1.1rem 1.1rem; background: #f8fafc; border-top: 1px solid #d6e0ed; }
.customer-expanded-top { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: start; gap: .85rem; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #e2e8f0; }
.customer-identity { flex: 1; min-width: min(100%, 220px); margin: 0; font-size: .78rem; line-height: 1.6; overflow-wrap: anywhere; }
.customer-identity dt { color: #64748b; font-size: .7rem; margin-bottom: .25rem; }
.customer-identity dd { margin: 0; color: #334155; }
.cliente-actions { display: flex; gap: .4rem; flex-wrap: wrap; }
.cliente-actions a { text-decoration: none; }
.is-inactive { --tracking-tint: #f1f5f9; --tracking-edge: #c1cbd8; --tracking-accent: #94a3b8; }
.is-inactive .cliente-avatar { background: #f1f5f9; color: #64748b; border-color: #cbd5e1; }
@media (max-width: 600px) {
  .cliente-card { padding: .85rem .8rem; }
  .customer-overview { padding-left: 0; }
  .customer-movements { gap: .45rem .75rem; }
  .movement { font-size: .7rem; }
  .customer-dates { gap: .45rem 1rem; }
  .historico-section { padding: .8rem; }
  .customer-expanded-top { flex-direction: column; }
  .customer-order-count { border-left: 0; padding-left: 0; }
}
@media (prefers-reduced-motion: reduce) { .expand-chevron { transition: none; } }
</style>
