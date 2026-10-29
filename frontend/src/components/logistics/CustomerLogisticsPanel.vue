<template>
  <section class="logistics-panel" :aria-label="t('customerHistory')">
    <CustomerHistoryAssociation v-if="auth.isOwner && customer.ativo" :customer-id="customer.id" @changed="refreshHistory" />
    <div class="history-tabs" role="group" :aria-label="t('customerHistory')">
      <button v-for="item in tabs" :key="item.value" type="button" class="erp-control" :aria-pressed="tab === item.value" @click="selectTab(item.value)">{{ t(item.label) }}</button>
    </div>
    <CustomerPurchasesHistory v-if="visited.purchases" v-show="tab === 'purchases'" :key="'purchases-' + historyVersion" :customer-id="customer.id" />
    <div v-show="tab === 'shipments'">
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
    </div>
    <AddressUsageHistory v-if="visited.prints" v-show="tab === 'prints'" :key="'prints-' + historyVersion" :customer="customer" compact @freight="openFreight" @print="openPrint" />
    <p v-if="pdfError && tab === 'prints'" role="alert" class="link-error">{{ t('error') }}</p>
    <details v-if="customer.ativo && tab === 'shipments'" class="link-form">
      <summary>{{ t('link') }}</summary><p class="muted">{{ t('hint') }}</p>
      <form @submit.prevent="find">
        <label>{{ t('kind') }}<ErpSelect :label="(t('kind'))" v-model="kind" :disabled="saving" @change="candidate = null"><option value="rastreamento">{{ t('parcel') }}</option><option value="pedido">{{ t('order') }}</option></ErpSelect></label>
        <label class="identifier">{{ t('identifier') }}<input v-model="identifier" required maxlength="100" :disabled="saving" @input="candidate = null" /></label>
        <button class="erp-button erp-button--secondary erp-button--sm" :disabled="finding || saving || !identifier.trim()" type="submit">{{ t('find') }}</button>
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
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { ref, watch, onUnmounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import CustomerHistoryAssociation from '@/components/clientes/CustomerHistoryAssociation.vue'
import { useI18n } from 'vue-i18n'
import { isAxiosError } from 'axios'
import api, { pedidosAPI, type Cliente, type Pedido } from '@/services/api'
import { customerLogisticsAPI, type CustomerLogistics, type CustomerParcel } from '@/services/customerLogistics'
import { useRouter } from 'vue-router'
import AddressUsageHistory from '@/components/addresses/AddressUsageHistory.vue'
import CustomerPurchasesHistory from './CustomerPurchasesHistory.vue'
import { messages } from './messages'
const router=useRouter()
const auth = useAuthStore()
const emit = defineEmits<{ changed: [] }>()
type HistoryTab = 'purchases' | 'shipments' | 'prints'
const tabs = [{ value: 'purchases', label: 'purchases' }, { value: 'shipments', label: 'title' }, { value: 'prints', label: 'prints' }] as const
const tab = ref<HistoryTab>('purchases')
const visited = ref({ purchases: true, shipments: false, prints: false })
const historyVersion = ref(0)
function selectTab(value: HistoryTab) {
  tab.value = value
  visited.value[value] = true
  if (value === 'shipments' && !data.value && !loading.value) void load()
}
function refreshHistory() {
  historyVersion.value++
  if (visited.value.shipments) void load()
  emit('changed')
}
const pdfError=ref(false)
const openFreight=(id:string)=>router.push({path:'/enderecos',query:{tab:'freight',freight_id:id}})
async function openPrint(id: string) {
  const request = contextVersion, token = auth.token
  pdfError.value = false
  try {
    const result = await api.get('/api/address-manager/history/' + id + '/pdf', { responseType: 'blob' })
    if (request !== contextVersion || token !== auth.token) return
    const url = URL.createObjectURL(result.data)
    window.open(url, '_blank', 'noopener')
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch { if (request === contextVersion && token === auth.token) pdfError.value = true }
}
const props = defineProps<{ customer: Cliente }>()
const { t, locale } = useI18n({ useScope: 'local', messages })
const data = ref<CustomerLogistics | null>(null)
const orders = ref<Pedido[]>([]), parcels = ref<CustomerParcel[]>([])
const loading = ref(false), loadError = ref(false), finding = ref(false), saving = ref(false)
const kind = ref<'pedido' | 'rastreamento'>('rastreamento'), identifier = ref('')
const candidate = ref<{ id: string; kind: 'pedido' | 'rastreamento'; title: string; description: string } | null>(null)
const feedback = ref(''), feedbackError = ref(false)
let generation = 0, contextVersion = 0
const date = (value: string) => new Date(value).toLocaleString(locale.value, { timeZone: 'America/Sao_Paulo', dateStyle: 'short', timeStyle: 'short' })
async function load(more?: 'orders' | 'parcels') {
  const request = ++generation
  const customerId = props.customer.id, token = auth.token
  loading.value = true; loadError.value = false
  try {
    const result = await customerLogisticsAPI.get(customerId, more === 'orders' ? orders.value.length : 0, more === 'parcels' ? parcels.value.length : 0)
    if (request !== generation || customerId !== props.customer.id || token !== auth.token) return
    data.value = result
    if (more !== 'parcels') orders.value = more === 'orders' ? [...orders.value, ...result.orders] : result.orders
    if (more !== 'orders') parcels.value = more === 'parcels' ? [...parcels.value, ...result.shipments] : result.shipments
  } catch { if (request === generation) loadError.value = true }
  finally { if (request === generation) loading.value = false }
}
async function find() {
  candidate.value = null; feedback.value = ''; finding.value = true
  const request = contextVersion, token = auth.token
  const customerId = props.customer.id, selectedKind = kind.value, search = identifier.value
  try {
    const row = selectedKind === 'pedido' ? await pedidosAPI.getByNumber(search.trim()) : await customerLogisticsAPI.findParcel(search)
    if (request !== contextVersion || token !== auth.token || customerId !== props.customer.id || selectedKind !== kind.value || search !== identifier.value) return
    if (row.cliente_id && row.cliente_id !== customerId) { feedbackError.value = true; feedback.value = t('conflict'); return }
    candidate.value = { id: row.id, kind: selectedKind, title: 'numero_pedido' in row && selectedKind === 'pedido' ? `#${row.numero_pedido}` : (row as CustomerParcel).codigo_rastreio, description: ('descricao' in row ? row.descricao : (row as CustomerParcel).destinatario) || '' }
  } catch { if (request === contextVersion && token === auth.token) { feedbackError.value = true; feedback.value = t('findError') } }
  finally { if (request === contextVersion && token === auth.token) finding.value = false }
}
async function confirmLink() {
  if (!candidate.value || saving.value) return
  saving.value = true; feedback.value = ''
  const request = contextVersion, token = auth.token, customerId = props.customer.id
  try {
    await customerLogisticsAPI.link(customerId, candidate.value.kind, candidate.value.id)
    if (request !== contextVersion || token !== auth.token || customerId !== props.customer.id) return
    candidate.value = null; identifier.value = ''; feedbackError.value = false; feedback.value = t('linked'); await load(); emit('changed')
  } catch (error) { if (request === contextVersion && token === auth.token) { feedbackError.value = true; feedback.value = t(isAxiosError(error) && error.response?.status === 409 ? 'conflict' : 'saveError') } }
  finally { if (request === contextVersion && token === auth.token) saving.value = false }
}
watch(() => [props.customer.id, auth.token], () => {
  contextVersion++; historyVersion.value++; finding.value = false; saving.value = false
  generation++; data.value = null; orders.value = []; parcels.value = []; candidate.value = null; feedback.value = ''
  loading.value = false; loadError.value = false; pdfError.value = false
  tab.value = 'purchases'; visited.value = { purchases: true, shipments: false, prints: false }
}, { immediate: true })
onUnmounted(() => { generation++; contextVersion++ })
</script>
<style scoped src="./logistics.css"></style>

<style scoped>
.customer-association + .history-tabs { margin-top: 1rem; }
.history-tabs { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; margin-bottom: 1rem; }
.history-tabs button { border: 1px solid #d5deeb; border-radius: 9px; padding: .6rem .8rem; background: white; color: #64748b; cursor: pointer; font: inherit; font-size: .78rem; }
.history-tabs button[aria-pressed="true"] { color: #1d4ed8; background: #eaf2ff; border-color: #91b7ef; font-weight: 650; }
.history-tabs button:focus-visible { outline: 2px solid #1d4ed8; outline-offset: 2px; }
</style>
