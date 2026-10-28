<template>
  <section v-if="auth.isOwner" class="customer-association" :aria-label="t('title')">
    <div class="association-heading">
      <div><h4>{{ t('title') }}</h4><p class="association-hint">{{ t('hint') }}</p></div>
      <button class="erp-button erp-button--secondary erp-button--sm" :disabled="!!busy || !auth.token" @click="preview">
        {{ busy === 'preview' ? t('checking') : plan ? t('again') : t('check') }}
      </button>
    </div>
    <p v-if="error" role="alert" class="association-error">{{ error }}</p>
    <p v-if="notice" role="status" class="association-success">{{ notice }}</p>
    <template v-if="plan">
      <p v-if="plan.limited" class="association-warning" role="status">{{ t('partial') }}</p>
      <p v-if="!plan.items.length" class="association-hint">{{ t('empty') }}</p>
      <template v-else>
        <div class="association-counts">
          <span v-for="[kind, count] in counts" :key="kind">{{ t(kind) }} <strong>{{ count }}</strong></span>
        </div>
        <ul class="association-records">
          <li v-for="row in plan.items" :key="`${row.kind}:${row.id}`">
            <span class="association-record-type">{{ t(kindLabels[row.kind]) }}</span>
            <strong>{{ row.label }}</strong><small>{{ t(row.reason) }}</small>
          </li>
        </ul>
        <label class="association-confirm"><input v-model="confirmed" type="checkbox" :disabled="!!busy" />{{ t('reviewed') }}</label>
        <button class="erp-button erp-button--primary erp-button--sm" :disabled="!confirmed || !!busy" @click="apply">
          {{ busy === 'apply' ? t('applying') : t('confirm') }}
        </button>
      </template>
      <p class="association-hint association-preserved">{{ t('preserved') }}</p>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { customerAssociationAPI, type CustomerAssociationPreview } from '@/services/customerAssociation'
import { customerAssociationMessages } from './customerAssociationMessages'

const props = defineProps<{ customerId: string }>()
const emit = defineEmits<{ changed: [] }>()
const auth = useAuthStore()
const { t } = useI18n({ useScope: 'local', messages: customerAssociationMessages })
const plan = ref<CustomerAssociationPreview | null>(null)
const busy = ref<'preview' | 'apply' | null>(null)
const confirmed = ref(false), error = ref(''), notice = ref('')
const kindLabels = { address: 'addresses', order: 'orders', tracking: 'tracking', pdv_account: 'pdv_accounts' } as const
const counts = computed(() => Object.entries(plan.value?.counts || {}).filter(([, count]) => count > 0))
let generation = 0
let controller: AbortController | null = null

function reset() {
  generation++
  controller?.abort()
  controller = null
  plan.value = null; busy.value = null; confirmed.value = false; error.value = ''; notice.value = ''
}
function failure(cause: unknown) {
  const status = (cause as { response?: { status?: number } })?.response?.status
  error.value = t(status === 409 ? 'changed' : 'error')
}
async function preview() {
  if (busy.value || !auth.isOwner || !auth.token) return
  reset()
  const request = generation, id = props.customerId, token = auth.token
  controller = new AbortController()
  busy.value = 'preview'
  try {
    const result = await customerAssociationAPI.preview(id, token, controller.signal)
    if (request !== generation || id !== props.customerId || token !== auth.token) return
    plan.value = result
  } catch (cause) { if (request === generation) failure(cause) }
  finally { if (request === generation) busy.value = null }
}
async function apply() {
  if (busy.value || !confirmed.value || !plan.value?.token || !auth.isOwner || !auth.token) return
  const request = ++generation, id = props.customerId, token = auth.token, expectedToken = plan.value.token
  controller?.abort()
  controller = new AbortController()
  busy.value = 'apply'; error.value = ''; notice.value = ''
  try {
    const result = await customerAssociationAPI.apply(id, expectedToken, token, controller.signal)
    if (request !== generation || id !== props.customerId || token !== auth.token) return
    plan.value = null; confirmed.value = false
    notice.value = t(result.already_applied ? 'already' : 'success') + (result.limited ? ` ${t('partial')}` : '')
    emit('changed')
  } catch (cause) {
    if (request !== generation) return
    failure(cause)
    plan.value = null; confirmed.value = false
  } finally { if (request === generation) busy.value = null }
}
watch(() => [props.customerId, auth.token, auth.isOwner], reset, { flush: 'sync' })
onBeforeUnmount(reset)
</script>
<style scoped>
.customer-association { border: 1px solid #d9e3f1; border-radius: 12px; padding: 14px; background: #fff; }
.association-heading { display: flex; align-items: start; gap: 12px; justify-content: space-between; }
.association-heading > div { min-width: 0; }
.association-heading button { flex-shrink: 0; }
h4 { margin: 0; font-size: 14px; color: #1e293b; }
.association-hint { color: #64748b; font-size: 12px; line-height: 1.5; margin: 6px 0 0; }
.association-counts { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.association-counts span { padding: 4px 8px; border-radius: 7px; background: #eff6ff; color: #475569; font-size: 12px; }
.association-counts strong { color: #1d4ed8; padding-left: 4px; }
.association-records { list-style: none; padding: 0; margin: 12px 0; max-height: 280px; overflow: auto; overscroll-behavior: contain; }
.association-records li { display: grid; gap: 4px; padding: 10px 0; border-bottom: 1px solid #edf2f7; overflow-wrap: anywhere; }
.association-records strong { font-size: 13px; font-weight: 600; color: #334155; }
.association-records small { font-size: 12px; color: #64748b; }
.association-record-type { color: #2563eb; font-size: 11px; }
.association-confirm { display: flex; gap: 8px; align-items: start; font-size: 13px; color: #334155; margin: 14px 0; line-height: 1.5; }
.association-confirm input { margin-top: 3px; accent-color: #2563eb; }
.association-error, .association-success, .association-warning { font-size: 13px; line-height: 1.5; }
.association-error { color: #b91c1c; }
.association-success { color: #047857; }
.association-warning { color: #92400e; background: #fffbeb; padding: 8px; border-radius: 8px; }
.association-preserved { margin-top: 12px; }
@media (max-width: 600px) { .association-heading { flex-direction: column; } }
</style>
