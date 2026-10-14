<template>
  <section class="purchase-history" :aria-label="t('title')">
    <div class="row-top purchase-heading">
      <h4>{{ t('title') }}</h4>
      <button class="erp-button erp-button--secondary erp-button--sm" :disabled="loading" @click="load(data?.page || 1)">{{ t('refresh') }}</button>
    </div>
    <p class="muted">{{ t('intro') }}</p>
    <p v-if="loading" role="status">{{ t('loading') }}</p>
    <div v-else-if="error" role="alert" class="link-error">
      {{ t('error') }}
      <button class="erp-button erp-button--secondary erp-button--sm" @click="load(requestedPage)">{{ t('retry') }}</button>
    </div>
    <template v-else-if="data">
      <p v-if="data.own_sales_only" class="muted">{{ t('own') }}</p>
      <div class="logistics-stats purchase-stats">
        <div><strong>{{ data.total }}</strong><span>{{ t('sales') }}</span></div>
        <div><strong>{{ money(data.summary.net_gs) }}</strong><span>{{ t('net') }}</span></div>
        <div><strong>{{ money(data.summary.refunded_gs) }}</strong><span>{{ t('refunds') }}</span></div>
        <div><strong>{{ data.summary.cancelled }}</strong><span>{{ t('cancelled') }}</span></div>
      </div>
      <p v-if="!data.total" class="muted">{{ t('empty') }}</p>
      <article v-for="sale in data.items" :key="sale.id" class="logistics-row purchase-row">
        <div class="row-top"><strong>{{ date(sale.created_at) }} · #{{ sale.id.slice(0, 8) }}</strong><span class="state">{{ status(sale.status) }}</span></div>
        <p>{{ t('account') }}: {{ sale.account_name }} · #{{ sale.account_id.slice(0, 8) }}</p>
        <small>{{ t('seller') }}: {{ sale.seller || '—' }}<template v-if="sale.customer_name"> · {{ t('snapshot') }}: {{ sale.customer_name }}</template></small>
        <p><strong>{{ t('net') }}: {{ money(sale.net_gs) }}</strong><small> · {{ t('original') }}: {{ money(sale.total_gs) }}<template v-if="Number(sale.refunded_gs)"> · {{ t('refund') }}: {{ money(sale.refunded_gs) }}</template></small></p>
        <details v-if="sale.lines.length">
          <summary>{{ t('items', { count: sale.lines.length }) }}</summary>
          <ul><li v-for="line in sale.lines" :key="line.id">{{ quantity(line.quantity) }} × {{ line.name }}<span v-if="Number(line.returned_quantity)" class="muted"> · {{ t('returned', { count: quantity(line.returned_quantity) }) }}</span></li></ul>
        </details>
      </article>
      <footer v-if="data.total > data.page_size" class="row-top">
        <button class="erp-button erp-button--secondary erp-button--sm" :disabled="data.page === 1" @click="load(data.page - 1)">{{ t('previous') }}</button>
        <span>{{ data.page }} / {{ Math.ceil(data.total / data.page_size) }}</span>
        <button class="erp-button erp-button--secondary erp-button--sm" :disabled="data.page * data.page_size >= data.total" @click="load(data.page + 1)">{{ t('next') }}</button>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { customerLogisticsAPI, type CustomerPurchases } from '@/services/customerLogistics'
import { purchaseMessages } from './purchaseMessages'

const props = defineProps<{ customerId: string }>()
const { t, te, locale } = useI18n({ useScope: 'local', messages: purchaseMessages })
const data = ref<CustomerPurchases | null>(null)
const loading = ref(false), error = ref(false), requestedPage = ref(1)
let sequence = 0
const money = (value: string) => `G$ ${Number(value).toLocaleString(locale.value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
const quantity = (value: string) => Number(value).toLocaleString(locale.value, { maximumFractionDigits: 3 })
const date = (value: string) => new Date(value).toLocaleString(locale.value, { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' })
const status = (value: string) => te(`states.${value}`) ? t(`states.${value}`) : value

async function load(page = 1) {
  const current = ++sequence, customerId = props.customerId
  requestedPage.value = page; loading.value = true; error.value = false
  try {
    const result = await customerLogisticsAPI.purchases(customerId, page)
    if (current === sequence && customerId === props.customerId) data.value = result
  } catch { if (current === sequence) error.value = true }
  finally { if (current === sequence) loading.value = false }
}
watch(() => props.customerId, () => { data.value = null; void load() }, { immediate: true })
onUnmounted(() => { sequence++ })
</script>

<style scoped src="./logistics.css"></style>
<style scoped>
.purchase-history { margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #e2e8f0; }
.purchase-heading h4 { margin: 0; }
.purchase-stats strong { font-size: 1.05rem; overflow-wrap: anywhere; }
.purchase-stats { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.purchase-row { overflow-wrap: anywhere; }
.purchase-row summary { cursor: pointer; color: #2563eb; margin-top: .6rem; }
.purchase-row ul { margin-bottom: 0; padding-left: 1.2rem; line-height: 1.6; }
@media(max-width:800px) { .purchase-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
