<template>
  <section class="logistics-panel" :aria-label="t('title')">
    <p v-if="loading" role="status">{{ t('loading') }}</p>
    <div v-if="loadError" role="alert" class="link-error">{{ t('error') }} <button class="erp-button erp-button--secondary erp-button--sm" @click="load()">{{ t('retry') }}</button></div>
    <template v-if="data">
      <div class="logistics-stats">
        <div><strong>{{ data.order_total }}</strong><span>{{ t('orders') }}</span></div>
        <div><strong>{{ data.shipment_total }}</strong><span>{{ t('parcels') }}</span></div>
        <div><strong>{{ data.in_transit }}</strong><span>{{ t('transit') }}</span></div>
        <div><strong>{{ data.delivered }}</strong><span>{{ t('delivered') }}</span></div>
      </div>
      <div class="logistics-columns">
        <section>
          <h4>{{ t('orders') }}</h4><p v-if="!orders.length" class="muted">{{ t('emptyOrders') }}</p>
          <article v-for="order in orders" :key="order.id" class="logistics-row">
            <div class="row-top"><RouterLink :to="{ path: '/pedidos', query: { pedido_id: order.id } }">#{{ order.numero_pedido }}</RouterLink><span class="state">{{ t(`states.${order.status}`) }}</span></div>
            <p>{{ order.descricao }}</p><small>{{ order.moeda || 'G$' }} {{ Number(order.valor_total).toLocaleString(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }} · {{ date(order.created_at) }}</small>
          </article>
          <button class="erp-button erp-button--secondary erp-button--sm" v-if="orders.length < data.order_total" :disabled="loading" @click="load('orders')">{{ t('more') }}</button>
        </section>
        <section>
          <h4>{{ t('parcels') }}</h4><p v-if="!parcels.length" class="muted">{{ t('emptyParcels') }}</p>
          <article v-for="parcel in parcels" :key="parcel.id" class="logistics-row">
            <div class="row-top"><RouterLink class="tracking-code" :to="{ path: '/rastreamento', query: { search: parcel.codigo_rastreio } }">{{ parcel.codigo_rastreio }}</RouterLink><span class="state">{{ parcel.ativo ? t(`states.${parcel.status}`) : t('archived') }}</span></div>
            <p>{{ parcel.destinatario || t('noName') }}</p><small>{{ parcel.numero_pedido ? `#${parcel.numero_pedido}` : t('noOrder') }} · {{ date(parcel.created_at) }}</small>
          </article>
          <button class="erp-button erp-button--secondary erp-button--sm" v-if="parcels.length < data.shipment_total" :disabled="loading" @click="load('parcels')">{{ t('more') }}</button>
        </section>
      </div>
    </template>
    <AddressUsageHistory :customer="customer" @freight="openFreight" @print="openPrint" />
    <p v-if="pdfError" role="alert" class="link-error">{{ t('error') }}</p>
    <details v-if="customer.ativo" class="link-form">
      <summary>{{ t('link') }}</summary><p class="muted">{{ t('hint') }}</p>
      <form @submit.prevent="find">
        <label>{{ t('kind') }}<select v-model="kind" :disabled="saving" @change="candidate = null"><option value="rastreamento">{{ t('parcel') }}</option><option value="pedido">{{ t('order') }}</option></select></label>
        <label class="identifier">{{ t('identifier') }}<input v-model="identifier" required maxlength="100" :disabled="saving" @input="candidate = null" /></label>
        <button class="erp-button erp-button--secondary erp-button--sm" :disabled="finding || saving || !identifier.trim()">{{ t('find') }}</button>
      </form>
      <div v-if="candidate" class="link-preview">
        <strong>{{ candidate.title }}</strong><p>{{ candidate.description }}</p><p>{{ t('confirmTo', { name: customer.nome }) }}</p>
        <button class="primary erp-button erp-button--primary erp-button--sm" :disabled="saving" @click="confirmLink">{{ t('confirm') }}</button>
        <button class="erp-button erp-button--secondary erp-button--sm" :disabled="saving" @click="candidate = null">{{ t('cancel') }}</button>
      </div>
      <p v-if="feedback" :class="feedbackError ? 'link-error' : 'link-success'" role="status">{{ feedback }}</p>
    </details>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { isAxiosError } from 'axios'
import api, { pedidosAPI, type Cliente, type Pedido } from '@/services/api'
import { customerLogisticsAPI, type CustomerLogistics, type CustomerParcel } from '@/services/customerLogistics'
import { useRouter } from 'vue-router'
import AddressUsageHistory from '@/components/addresses/AddressUsageHistory.vue'
import { messages } from './messages'
const router=useRouter()
const pdfError=ref(false)
const openFreight=(id:string)=>router.push({path:'/enderecos',query:{tab:'freight',freight_id:id}})
async function openPrint(id:string){pdfError.value=false;try{const r=await api.get('/api/address-manager/history/'+id+'/pdf',{responseType:'blob'});const url=URL.createObjectURL(r.data);window.open(url,'_blank','noopener');setTimeout(()=>URL.revokeObjectURL(url),60000)}catch{pdfError.value=true}}
const props = defineProps<{ customer: Cliente }>()
const { t, locale } = useI18n({ useScope: 'local', messages })
const data = ref<CustomerLogistics | null>(null)
const orders = ref<Pedido[]>([]), parcels = ref<CustomerParcel[]>([])
const loading = ref(false), loadError = ref(false), finding = ref(false), saving = ref(false)
const kind = ref<'pedido' | 'rastreamento'>('rastreamento'), identifier = ref('')
const candidate = ref<{ id: string; kind: 'pedido' | 'rastreamento'; title: string; description: string } | null>(null)
const feedback = ref(''), feedbackError = ref(false)
let generation = 0
const date = (value: string) => new Date(value).toLocaleDateString(locale.value)
async function load(more?: 'orders' | 'parcels') {
  const request = ++generation
  const customerId = props.customer.id
  loading.value = true; loadError.value = false
  try {
    const result = await customerLogisticsAPI.get(customerId, more === 'orders' ? orders.value.length : 0, more === 'parcels' ? parcels.value.length : 0)
    if (request !== generation || customerId !== props.customer.id) return
    data.value = result
    if (more !== 'parcels') orders.value = more === 'orders' ? [...orders.value, ...result.orders] : result.orders
    if (more !== 'orders') parcels.value = more === 'parcels' ? [...parcels.value, ...result.shipments] : result.shipments
  } catch { if (request === generation) loadError.value = true }
  finally { if (request === generation) loading.value = false }
}
async function find() {
  candidate.value = null; feedback.value = ''; finding.value = true
  const customerId = props.customer.id, selectedKind = kind.value, search = identifier.value
  try {
    const row = selectedKind === 'pedido' ? await pedidosAPI.getByNumber(search.trim()) : await customerLogisticsAPI.findParcel(search)
    if (customerId !== props.customer.id || selectedKind !== kind.value || search !== identifier.value) return
    if (row.cliente_id && row.cliente_id !== customerId) { feedbackError.value = true; feedback.value = t('conflict'); return }
    candidate.value = { id: row.id, kind: selectedKind, title: 'numero_pedido' in row && selectedKind === 'pedido' ? `#${row.numero_pedido}` : (row as CustomerParcel).codigo_rastreio, description: ('descricao' in row ? row.descricao : (row as CustomerParcel).destinatario) || '' }
  } catch { feedbackError.value = true; feedback.value = t('findError') }
  finally { finding.value = false }
}
async function confirmLink() {
  if (!candidate.value || saving.value) return
  saving.value = true; feedback.value = ''
  try {
    await customerLogisticsAPI.link(props.customer.id, candidate.value.kind, candidate.value.id)
    candidate.value = null; identifier.value = ''; feedbackError.value = false; feedback.value = t('linked'); await load()
  } catch (error) { feedbackError.value = true; feedback.value = t(isAxiosError(error) && error.response?.status === 409 ? 'conflict' : 'saveError') }
  finally { saving.value = false }
}
watch(() => props.customer.id, () => { data.value = null; orders.value = []; parcels.value = []; candidate.value = null; feedback.value = ''; void load() }, { immediate: true })
</script>
<style scoped src="./logistics.css"></style>
