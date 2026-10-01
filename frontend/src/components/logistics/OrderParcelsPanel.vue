<template>
  <section class="logistics-panel" :aria-label="t('parcels')">
    <h4>{{ t('parcels') }}</h4>
    <p v-if="loading" role="status">{{ t('loading') }}</p>
    <div v-if="loadError" role="alert" class="link-error">{{ t('error') }} <button @click="load()">{{ t('retry') }}</button></div>
    <p v-else-if="!loading && !parcels.length" class="muted">{{ t('emptyParcels') }}</p>
    <article v-for="parcel in parcels" :key="parcel.id" class="logistics-row">
      <div class="row-top"><RouterLink class="tracking-code" :to="{ path: '/rastreamento', query: { search: parcel.codigo_rastreio } }">{{ parcel.codigo_rastreio }}</RouterLink><span class="state">{{ parcel.ativo ? t(`states.${parcel.status}`) : t('archived') }}</span></div>
      <p>{{ parcel.destinatario || t('noName') }}</p><small>{{ new Date(parcel.created_at).toLocaleDateString(locale) }}</small>
    </article>
    <button v-if="hasMore" :disabled="loading" @click="load(true)">{{ t('more') }}</button>
    <details class="link-form">
      <summary>{{ t('addParcel') }}</summary><p class="muted">{{ t('hint') }}</p>
      <form @submit.prevent="find"><label class="identifier">{{ t('code') }}<input v-model="code" required maxlength="100" :disabled="saving" @input="candidate = null" /></label><button :disabled="finding || saving || !code.trim()">{{ t('find') }}</button></form>
      <div v-if="candidate" class="link-preview">
        <strong class="tracking-code">{{ candidate.codigo_rastreio }}</strong><p>{{ candidate.destinatario || t('noName') }}</p><p>{{ t('confirmOrder', { number: order.numero_pedido }) }}</p>
        <button class="primary" :disabled="saving" @click="confirmLink">{{ t('confirm') }}</button><button :disabled="saving" @click="candidate = null">{{ t('cancel') }}</button>
      </div>
      <p v-if="feedback" :class="feedbackError ? 'link-error' : 'link-success'" role="status">{{ feedback }}</p>
    </details>
  </section>
</template>
<script setup lang="ts">
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { isAxiosError } from 'axios'
import type { Pedido } from '@/services/api'
import { customerLogisticsAPI, type CustomerParcel } from '@/services/customerLogistics'
import { messages } from './messages'
const props = defineProps<{ order: Pedido }>()
const emit = defineEmits<{ linked: [] }>()
const { t, locale } = useI18n({ useScope: 'local', messages })
const parcels = ref<CustomerParcel[]>([]), candidate = ref<CustomerParcel | null>(null)
const loading = ref(false), loadError = ref(false), hasMore = ref(false), saving = ref(false), finding = ref(false)
const code = ref(''), feedback = ref(''), feedbackError = ref(false)
let generation = 0
async function load(more = false) {
  const request = ++generation, orderId = props.order.id
  loading.value = true; loadError.value = false
  try {
    const rows = await customerLogisticsAPI.orderParcels(orderId, more ? parcels.value.length : 0)
    if (request !== generation || orderId !== props.order.id) return
    parcels.value = more ? [...parcels.value, ...rows] : rows; hasMore.value = rows.length === 50
  } catch { if (request === generation) loadError.value = true }
  finally { if (request === generation) loading.value = false }
}
async function find() {
  candidate.value = null; feedback.value = ''; finding.value = true
  const orderId = props.order.id, search = code.value
  try {
    const row = await customerLogisticsAPI.findParcel(search)
    if (orderId !== props.order.id || search !== code.value) return
    if ((row.pedido_id && row.pedido_id !== orderId) || (row.cliente_id && props.order.cliente_id && row.cliente_id !== props.order.cliente_id)) { feedbackError.value = true; feedback.value = t('conflict'); return }
    candidate.value = row
  } catch { feedbackError.value = true; feedback.value = t('findError') }
  finally { finding.value = false }
}
async function confirmLink() {
  if (!candidate.value || saving.value) return
  saving.value = true; feedback.value = ''
  try {
    await customerLogisticsAPI.linkParcelToOrder(candidate.value.id, props.order.id)
    candidate.value = null; code.value = ''; feedbackError.value = false; feedback.value = t('linked'); await load(); emit('linked')
  } catch (error) { feedbackError.value = true; feedback.value = t(isAxiosError(error) && error.response?.status === 409 ? 'conflict' : 'saveError') }
  finally { saving.value = false }
}
watch(() => props.order.id, () => { parcels.value = []; candidate.value = null; feedback.value = ''; void load() }, { immediate: true })
</script>
<style scoped src="./logistics.css"></style>
