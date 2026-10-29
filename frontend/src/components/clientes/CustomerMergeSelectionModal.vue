<template>
  <Teleport to="body">
    <div class="erp-dialog-backdrop customer-merge-backdrop" @click.self="!busy && emit('close')">
      <section v-erp-dialog class="erp-dialog erp-dialog--lg customer-merge-dialog" :aria-label="t('title')">
        <header class="erp-dialog__header">
          <h2>{{ t('title') }}</h2>
          <button type="button" data-dialog-close class="erp-button erp-button--ghost erp-button--icon" :disabled="busy" :aria-label="t('close')" @click="emit('close')">×</button>
        </header>
        <main class="erp-dialog__body">
          <label class="principal-field"><span>{{ t('principal') }}</span>
            <ErpSelect v-model="targetId" :label="t('principal')" :disabled="busy">
              <option v-for="customer in customers" :key="customer.id" :value="customer.id">{{ customer.nome }}</option>
            </ErpSelect>
          </label>
          <p class="merge-help">{{ t('principalHelp') }}</p>
          <div class="merge-identities">
            <article v-for="customer in identities" :key="customer.id" class="merge-identity" :class="{ 'is-principal': customer.id === targetId }">
              <div class="merge-identity-heading"><strong>{{ customer.name }}</strong><span>{{ t(customer.id === targetId ? 'main' : 'source') }}</span></div>
              <p v-if="customer.documents?.length" class="merge-documents"><span v-for="(document, index) in customer.documents" :key="index">{{ document.tipo }} · {{ document.pais }}: {{ document.numero }}<template v-if="document.emissor"> · {{ document.emissor }}</template></span></p>
              <p v-else-if="customer.cpf">CPF: {{ customer.cpf }}</p>
              <p>{{ [customer.telefone, customer.email].filter(Boolean).join(' · ') || t('noContact') }}</p>
              <p>{{ customer.endereco || t('noAddress') }}</p>
            </article>
          </div>
          <p v-if="error" role="alert" class="merge-error">{{ error }}</p>
          <p v-if="busy" role="status" class="merge-help">{{ t(saving ? 'saving' : 'checking') }}</p>
          <template v-if="plan">
            <section class="merge-summary" :aria-label="t('totals')">
              <h3>{{ t('totals') }}</h3>
              <dl><div v-for="key in countKeys" :key="key"><dt>{{ t(key) }}</dt><dd>{{ plan.history?.[key] ?? 0 }}</dd></div></dl>
              <p>{{ t('moving') }}: {{ countKeys.map(key => `${t(key)}: ${plan?.links_to_move?.[key] ?? 0}`).join(' · ') }}</p>
            </section>
            <div v-if="plan.conflicting_fields?.length" class="merge-conflicts">
              <strong>{{ t('conflicts') }}</strong>
              <ul><li v-for="conflict in plan.conflicts" :key="conflict.source_id">{{ identityName(conflict.source_id) }}: {{ conflict.fields.map(fieldLabel).join(', ') }}</li></ul>
            </div>
            <p v-if="plan.fields_added?.length" class="merge-help">{{ t('added') }}: {{ plan.fields_added.map(fieldLabel).join(', ') }}</p>
            <p class="merge-help">{{ t('preserved') }}</p>
            <label class="merge-check"><input v-model="identityConfirmed" type="checkbox" :disabled="busy" /><span>{{ t('identity') }}</span></label>
            <label v-if="plan.requires_reviewed_conflicts" class="merge-check merge-check--conflicts"><input v-model="conflictsConfirmed" type="checkbox" :disabled="busy" /><span>{{ t('conflictReview') }}</span></label>
          </template>
        </main>
        <footer class="erp-dialog__footer">
          <button type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="emit('close')">{{ t('cancel') }}</button>
          <button v-if="!plan" type="button" class="erp-button erp-button--primary" :disabled="busy || !validSelection" @click="preview">{{ t('preview') }}</button>
          <button v-else type="button" class="erp-button erp-button--primary" :disabled="busy || !identityConfirmed || (plan.requires_reviewed_conflicts && !conflictsConfirmed)" @click="confirmMerge">{{ t('confirm') }}</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { vErpDialog } from '@/directives/erpDialog'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { useAuthStore } from '@/stores/auth'
import type { Cliente } from '@/services/api'
import { customerMergeAPI, type CustomerMergeIdentity, type CustomerMergePlan, type CustomerMergeCounts } from '@/services/customerMerge'
import { customerMergeMessages } from './customerMergeMessages'

const props = defineProps<{ customers: Cliente[] }>()
const emit = defineEmits<{ close: []; changed: [targetId: string, sourceIds: string[]] }>()
const auth = useAuthStore()
const { t, te } = useI18n({ useScope: 'local', messages: customerMergeMessages })
const targetId = ref(props.customers[0]?.id || '')
const plan = ref<CustomerMergePlan | null>(null)
const identityConfirmed = ref(false), conflictsConfirmed = ref(false)
const busy = ref(false), saving = ref(false), error = ref('')
const countKeys: Array<keyof CustomerMergeCounts> = ['orders', 'tracking', 'addresses', 'pdv_customers']
const validSelection = computed(() => props.customers.length >= 2 && props.customers.length <= 20 && new Set(props.customers.map(customer => customer.id)).size === props.customers.length && props.customers.some(customer => customer.id === targetId.value))
const sourceIds = computed(() => props.customers.filter(customer => customer.id !== targetId.value).map(customer => customer.id))
const identities = computed<CustomerMergeIdentity[]>(() => plan.value?.customers || props.customers.map(customer => ({
  id: customer.id, name: customer.nome, cpf: customer.cpf, telefone: customer.telefone,
  email: customer.email, endereco: customer.endereco, documents: customer.documentos,
})))
const identityName = (id: string) => identities.value.find(customer => customer.id === id)?.name || id
const fieldLabel = (field: string) => te(field) ? t(field) : field
let generation = 0, controller: AbortController | undefined
function invalidate() {
  generation++; controller?.abort(); controller = undefined
  plan.value = null; identityConfirmed.value = false; conflictsConfirmed.value = false
  busy.value = false; saving.value = false
}
watch(targetId, () => { invalidate(); error.value = '' }, { flush: 'sync' })
watch(() => props.customers.map(customer => customer.id).join('|'), () => {
  invalidate(); error.value = ''
  if (!props.customers.some(customer => customer.id === targetId.value)) targetId.value = props.customers[0]?.id || ''
}, { flush: 'sync' })
watch(() => [auth.token, auth.isOwner], () => { invalidate(); error.value = ''; emit('close') }, { flush: 'sync' })
function detail(errorValue: unknown, fallback: string) {
  const detail = (errorValue as { response?: { status?: number; data?: { detail?: unknown } } })?.response
  return detail?.status === 409 ? t('stale') : typeof detail?.data?.detail === 'string' ? detail.data.detail : t(fallback)
}
async function preview() {
  if (busy.value || !validSelection.value || !auth.token || !auth.isOwner) return
  const token = auth.token, current = ++generation
  controller = new AbortController(); busy.value = true; error.value = ''
  try {
    const result = await customerMergeAPI.preview(targetId.value, sourceIds.value, token, controller.signal)
    if (current !== generation || token !== auth.token || !auth.isOwner) return
    if (result.state === 'already_merged') { emit('changed', result.target_id, result.source_ids); return }
    plan.value = result; identityConfirmed.value = false; conflictsConfirmed.value = false
  } catch (errorValue) {
    if (current === generation && token === auth.token) error.value = detail(errorValue, 'error')
  } finally { if (current === generation) busy.value = false }
}
async function confirmMerge() {
  const reviewed = plan.value
  if (busy.value || !reviewed || !identityConfirmed.value || (reviewed.requires_reviewed_conflicts && !conflictsConfirmed.value) || !auth.token || !auth.isOwner) return
  const token = auth.token, current = ++generation
  controller = new AbortController(); busy.value = true; saving.value = true; error.value = ''
  try {
    const result = await customerMergeAPI.confirm(reviewed, conflictsConfirmed.value, token, controller.signal)
    if (current !== generation || token !== auth.token || !auth.isOwner) return
    emit('changed', result.target_id, result.source_ids)
  } catch (errorValue) {
    if (current !== generation || token !== auth.token) return
    plan.value = null; identityConfirmed.value = false; conflictsConfirmed.value = false
    error.value = detail(errorValue, 'saveError')
  } finally { if (current === generation) { busy.value = false; saving.value = false } }
}
onBeforeUnmount(invalidate)
</script>

<style scoped>
.customer-merge-backdrop { position: fixed; inset: 0; z-index: 1500; display: grid; place-items: center; padding: 1rem; background: #0f172a66; }
.customer-merge-dialog { width: min(100%, 780px); background: #fff; border-radius: 16px; }
.customer-merge-dialog h2 { font-size: 1.05rem; margin: 0; }
.principal-field { display: flex; flex-direction: column; gap: .5rem; color: #334155; font-size: .85rem; font-weight: 600; }
.merge-help { font-size: .8rem; color: #64748b; line-height: 1.6; }
.merge-identities { display: grid; gap: .65rem; }
.merge-identity { padding: .85rem; border: 1px solid #e2e8f0; border-radius: 10px; background: #f8fafc; min-width: 0; }
.merge-identity.is-principal { border-color: #93b4e5; background: #eff6ff; }
.merge-identity-heading { display: flex; flex-wrap: wrap; gap: .4rem; justify-content: space-between; align-items: center; }
.merge-identity-heading strong { font-size: .85rem; color: #1e293b; overflow-wrap: anywhere; }
.merge-identity-heading > span { font-size: .68rem; color: #64748b; }
.merge-identity p { font-size: .77rem; color: #475569; line-height: 1.5; margin: .35rem 0 0; overflow-wrap: anywhere; }
.merge-documents { display: flex; flex-direction: column; }
.merge-summary { border: 1px solid #cfe1fb; background: #f2f7ff; padding: .9rem; margin-top: 1rem; border-radius: 10px; }
.merge-summary h3 { margin: 0 0 .7rem; font-size: .85rem; color: #334155; }
.merge-summary dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .6rem; margin: 0; }
.merge-summary dt { font-size: .7rem; color: #64748b; }
.merge-summary dd { margin: .2rem 0 0; font-size: 1rem; color: #1d4ed8; font-weight: 700; }
.merge-summary p { font-size: .72rem; color: #64748b; line-height: 1.5; margin-bottom: 0; }
.merge-conflicts { margin-top: 1rem; padding: .85rem; background: #fffbeb; border: 1px solid #f5d597; border-radius: 10px; color: #92400e; font-size: .8rem; }
.merge-conflicts ul { margin-bottom: 0; padding-left: 1.2rem; overflow-wrap: anywhere; }
.merge-check { display: flex; gap: .65rem; align-items: start; margin-top: .85rem; font-size: .8rem; line-height: 1.5; color: #334155; }
.merge-check input { flex: 0 0 18px; width: 18px; height: 18px; margin: .15rem 0 0; accent-color: #2563eb; }
.merge-check--conflicts { color: #92400e; }
.merge-error { color: #b91c1c; font-size: .82rem; overflow-wrap: anywhere; }
@media (max-width: 600px) { .customer-merge-backdrop { padding: .6rem; } .merge-summary dl { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
