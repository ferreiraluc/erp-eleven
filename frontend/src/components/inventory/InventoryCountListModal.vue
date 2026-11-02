<template>
  <Teleport to="body">
    <div class="count-backdrop erp-dialog-backdrop" @click.self="close">
      <section v-erp-dialog class="erp-dialog erp-dialog--lg count-dialog">
        <header class="erp-dialog__header">
          <h2>{{ t('title') }}</h2>
          <button type="button" data-dialog-close class="erp-button erp-button--secondary erp-button--icon" :aria-label="t('close')" :disabled="sending" @click="close">×</button>
        </header>
        <div class="erp-dialog__body">
          <p class="count-hint">{{ t('hint') }}</p>
          <p v-if="loading" role="status">{{ t('loading') }}</p>
          <div v-if="error" role="alert" class="count-error">{{ error }}</div>
          <div v-if="invalidPending" class="count-warning">
            <p>{{ t('invalidPending') }}</p>
            <label class="count-confirm"><input v-model="checkedRecovery" type="checkbox" />{{ t('confirmClear') }}</label>
            <button class="erp-button erp-button--secondary" type="button" :disabled="!checkedRecovery" @click="clearRecovery">{{ t('clearRecovery') }}</button>
          </div>
          <div v-else-if="attempt && !job" class="count-warning" role="status">
            {{ t('pending') }}
          </div>
          <template v-if="report">
            <div class="count-summary">
              <strong>{{ t('count', { count: format(report.snapshot.totals.items) }) }}</strong>
              <small>{{ t('captured', { date: date(report.snapshot.created_at) }) }}</small>
            </div>
            <div class="count-totals">
              <div><span>{{ t('store') }}</span><strong>{{ format(report.snapshot.totals.stock_loja) }}</strong><small v-if="report.snapshot.totals.unknown_loja">{{ t('partial', { count: format(report.snapshot.totals.unknown_loja) }) }}</small></div>
              <div><span>{{ t('warehouse') }}</span><strong>{{ format(report.snapshot.totals.stock_deposito) }}</strong><small v-if="report.snapshot.totals.unknown_deposito">{{ t('partial', { count: format(report.snapshot.totals.unknown_deposito) }) }}</small></div>
            </div>
            <p v-if="report.snapshot.totals.unknown_loja || report.snapshot.totals.unknown_deposito" class="count-hint">{{ t('partialHint') }}</p>
            <table class="count-table">
              <thead><tr><th scope="col">{{ t('product') }}</th><th scope="col">{{ t('store') }}</th><th scope="col">{{ t('warehouse') }}</th></tr></thead>
              <tbody><tr v-for="item in pageItems" :key="item.id">
                <td><strong>{{ item.name }}</strong><small>{{ item.code }}</small><small>{{ [item.color, item.size, item.location].filter(Boolean).join(' · ') }}</small></td>
                <td :class="{ 'count-unknown': item.stock_loja === null }">{{ item.stock_loja === null ? t('unknown') : format(item.stock_loja) }}</td>
                <td :class="{ 'count-unknown': item.stock_deposito === null }">{{ item.stock_deposito === null ? t('unknown') : format(item.stock_deposito) }}</td>
              </tr></tbody>
            </table>
            <nav v-if="pages > 1" class="count-pages" :aria-label="t('product')">
              <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="page === 1" @click="page--">{{ t('previous') }}</button>
              <small>{{ t('page', { current: page, total: pages }) }}</small>
              <button type="button" class="erp-button erp-button--secondary erp-button--sm" :disabled="page === pages" @click="page++">{{ t('next') }}</button>
            </nav>
            <div v-if="!attempt && !job" class="count-destination">
              <template v-if="devices.length">
                <label for="count-list-printer">{{ t('printer') }}</label>
                <ErpSelect id="count-list-printer" v-model="deviceId" :label="t('printer')" :disabled="sending">
                  <option value="">{{ t('choose') }}</option>
                  <option v-for="device in devices" :key="device.id" :value="device.id">{{ device.name }}</option>
                </ErpSelect>
                <small v-if="selectedDevice">{{ selectedDevice.last_seen_at ? t('lastSeen', { date: date(selectedDevice.last_seen_at) }) : t('neverSeen') }}</small>
                <label class="count-confirm"><input v-model="reviewed" type="checkbox" :disabled="sending" />{{ t('confirm') }}</label>
              </template>
              <p v-else class="count-hint">{{ t('noPrinter') }}</p>
            </div>
          </template>
          <div v-if="job" class="count-job" role="status">
            <strong>{{ job.device_name }}</strong><p>{{ jobStatus }}</p>
            <small v-if="job.diagnostic_message">{{ job.diagnostic_message }}</small>
          </div>
        </div>
        <footer class="erp-dialog__footer">
          <button v-if="!attempt && !job && !invalidPending" class="erp-button erp-button--secondary" type="button" :disabled="loading || downloading" @click="loadPreview">{{ report ? t('refresh') : t('retry') }}</button>
          <button v-if="report" class="erp-button erp-button--secondary" type="button" :disabled="loading || downloading" @click="download">{{ downloading ? t('downloading') : t('download') }}</button>
          <button v-if="job" class="erp-button erp-button--secondary" type="button" :disabled="refreshing" @click="refreshJob">{{ t('status') }}</button>
          <button v-else-if="attempt" class="erp-button erp-button--primary" type="button" :disabled="sending" @click="send">{{ sending ? t('printing') : t('recover') }}</button>
          <button v-else-if="report" class="erp-button erp-button--primary" type="button" :disabled="!canPrint" @click="confirmPrint">{{ sending ? t('printing') : t('print') }}</button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { vErpDialog } from '@/directives/erpDialog'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { inventoryCountListMessages } from './inventoryCountListMessages'
import { countListDefinitelyNotQueued, countListError, inventoryCountList, restoreCountListRequest, type SignedCountList, type CountListDevice, type CountListJob, type CountListRequest } from '@/services/inventoryCountList'

const props = defineProps<{ itemIds: string[] }>()
const emit = defineEmits<{ close: [] }>()
const auth = useAuthStore()
const { locale } = useI18n({ useScope: 'global' })
type MessageKey = keyof typeof inventoryCountListMessages.pt
function t(key: MessageKey, params: Record<string, string | number> = {}) {
  const language = locale.value === 'en' ? 'en' : locale.value === 'es' ? 'es' : 'pt'
  return inventoryCountListMessages[language][key].replace(/\{(\w+)\}/g, (original, name) => String(params[name] ?? original))
}
const numberLocale = computed(() => locale.value === 'en' ? 'en-US' : locale.value === 'es' ? 'es-PY' : 'pt-BR')
const format = (n: number) => n.toLocaleString(numberLocale.value)
const date = (value: string) => new Date(value).toLocaleString(numberLocale.value)
const owner = auth.user?.id
const token = auth.token
const storageKey = `eleven:inventory-count-list:pending:${owner}`
let alive = true
let generation = 0
const report = ref<SignedCountList | null>(null)
const devices = ref<CountListDevice[]>([])
const deviceId = ref('')
const filename = ref('eleven-conferencia-estoque.pdf')
const page = ref(1)
const pages = computed(() => Math.max(1, Math.ceil((report.value?.snapshot.items.length || 0) / 25)))
const pageItems = computed(() => report.value?.snapshot.items.slice((page.value - 1) * 25, page.value * 25) || [])
const selectedDevice = computed(() => devices.value.find(device => device.id === deviceId.value))
const reviewed = ref(false)
const loading = ref(false), sending = ref(false), downloading = ref(false), refreshing = ref(false)
const error = ref('')
const attempt = ref<CountListRequest | null>(null)
const invalidPending = ref(false), checkedRecovery = ref(false), storageUnavailable = ref(false)
const job = ref<CountListJob | null>(null)
const current = (id: number) => alive && generation === id && auth.user?.id === owner && auth.token === token
const authorized = () => !!owner && ['ADMIN', 'GERENTE'].includes(auth.userRole)
const canPrint = computed(() => !!report.value && !!selectedDevice.value && reviewed.value && !loading.value && !sending.value && !attempt.value && !invalidPending.value && !storageUnavailable.value && authorized())
const jobStatus = computed(() => {
  const status: Record<string, MessageKey> = { pending: 'queued', queued: 'queued', claimed: 'claimed', printing: 'claimed', printed: 'submitted', completed: 'submitted', submitted: 'submitted', failed: 'failed', uncertain: 'uncertain', cancelled: 'cancelled', expired: 'expired' }
  return t(status[job.value?.status || ''] || 'uncertain')
})
watch(deviceId, () => { reviewed.value = false })
watch(() => [auth.user?.id, auth.token], () => {
  if (auth.user?.id === owner && auth.token === token) return
  generation++; report.value = null; attempt.value = null; job.value = null; devices.value = []
  error.value = t('wrongSession'); emit('close')
})
function close() { if (!sending.value) emit('close') }

async function loadPreview() {
  if (!authorized() || attempt.value || invalidPending.value || loading.value) return
  const ids = [...new Set(props.itemIds)]
  if (!ids.length || ids.length > 5000) { error.value = t('invalidSelection'); return }
  const id = ++generation
  loading.value = true; error.value = storageUnavailable.value ? t('storageError') : ''; report.value = null; reviewed.value = false; page.value = 1
  try {
    const result = await inventoryCountList.preview(ids)
    if (!current(id)) return
    if (result.snapshot.user_id !== owner) throw new Error('wrong-snapshot-owner')
    report.value = { snapshot: result.snapshot, signature: result.signature }
    devices.value = result.devices; filename.value = result.filename
    deviceId.value = result.devices.some(device => device.id === result.suggested_device_id) ? result.suggested_device_id! : ''
  } catch (cause) {
    const message = await countListError(cause, t('loadError'))
    if (current(id)) error.value = message
  } finally { if (current(id)) loading.value = false }
}

function clearRecovery() {
  if (!checkedRecovery.value) return
  try {
    sessionStorage.removeItem(storageKey)
    invalidPending.value = false; checkedRecovery.value = false
    void loadPreview()
  } catch { error.value = t('storageError') }
}
async function confirmPrint() {
  if (!canPrint.value || !report.value) return
  try {
    const request: CountListRequest = JSON.parse(JSON.stringify({ ...report.value, device_id: deviceId.value, request_key: crypto.randomUUID(), confirm: true }))
    // Persist before sending: a lost response, reload or closed modal must retry this exact request.
    sessionStorage.setItem(storageKey, JSON.stringify(request))
    attempt.value = request
  } catch { error.value = t('storageError'); return }
  await send()
}
async function send() {
  if (!attempt.value || sending.value || !authorized() || job.value) return
  const id = generation
  sending.value = true; error.value = ''
  try {
    const result = await inventoryCountList.print(attempt.value)
    if (!current(id)) return
    job.value = result
    try { sessionStorage.removeItem(storageKey) } catch { /* The retained request still replays idempotently. */ }
  } catch (cause) {
    const message = await countListError(cause, t('printError'))
    if (current(id)) {
      error.value = message
      if (countListDefinitelyNotQueued(cause)) {
        try {
          sessionStorage.removeItem(storageKey)
          attempt.value = null; reviewed.value = false
          // A fresh preview is required before another explicit confirmation.
          report.value = null; devices.value = []; deviceId.value = ''
        } catch { /* Keep recovery if the prior request cannot be removed safely. */ }
      }
    }
  } finally { if (current(id)) sending.value = false }
}
async function refreshJob() {
  if (!job.value || refreshing.value) return
  const id = generation
  refreshing.value = true; error.value = ''
  try {
    const result = await inventoryCountList.job(job.value.id)
    if (current(id)) job.value = result
  } catch (cause) {
    const message = await countListError(cause, t('statusError'))
    if (current(id)) error.value = message
  } finally { if (current(id)) refreshing.value = false }
}
async function download() {
  if (!report.value || downloading.value) return
  const id = generation
  downloading.value = true; error.value = ''
  try {
    const blob = job.value ? await inventoryCountList.jobPdf(job.value.id) : await inventoryCountList.pdf(report.value)
    if (!current(id)) return
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = filename.value; anchor.hidden = true
    document.body.append(anchor)
    try { anchor.click() } finally {
      anchor.remove()
      // Safari may consume the object URL asynchronously; closing the modal must not cancel the download.
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
    }
  } catch (cause) {
    const message = await countListError(cause, t('pdfError'))
    if (current(id)) error.value = message
  } finally { if (current(id)) downloading.value = false }
}
onMounted(() => {
  if (!authorized()) { emit('close'); return }
  let saved: string | null = null
  try { saved = sessionStorage.getItem(storageKey) }
  catch { storageUnavailable.value = true }
  try {
    if (saved) {
      attempt.value = restoreCountListRequest(saved, owner!)
      report.value = { snapshot: attempt.value.snapshot, signature: attempt.value.signature }
      return
    }
  } catch { invalidPending.value = true; return }
  void loadPreview()
})
onBeforeUnmount(() => { alive = false; generation++ })
</script>

<style scoped>
.count-backdrop { position: fixed; inset: 0; z-index: 1200; display: flex; align-items: center; justify-content: center; }
.count-hint, .count-summary small, .count-destination small { color: #64748b; font-size: 13px; }
.count-hint { margin: 0 0 14px; }
.count-summary { display: flex; flex-direction: column; gap: 4px; margin: 16px 0; }
.count-totals { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.count-totals > div { display: flex; flex-direction: column; padding: 10px 14px; border-radius: 12px; background: #f1f5f9; }
.count-totals strong { font-size: 22px; }.count-totals small { color: #92400e; }
.count-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 13px; }
.count-table th { text-align: left; color: #64748b; font-weight: 500; }
.count-table th:first-child { width: 60%; }
.count-table td, .count-table th { padding: 10px 6px; border-bottom: 1px solid #e2e8f0; overflow-wrap: anywhere; vertical-align: top; }
.count-table td:not(:first-child), .count-table th:not(:first-child) { text-align: right; }
.count-table strong, .count-table small { display: block; }.count-table small { color: #64748b; }
.count-table .count-unknown { font-size: 12px; }
.count-pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 12px 0; }
.count-destination { display: flex; flex-direction: column; gap: 8px; margin-top: 20px; }
.count-confirm { display: flex; align-items: flex-start; gap: 10px; margin: 10px 0; font-size: 14px; }
.count-confirm input { flex: 0 0 auto; width: 18px; height: 18px; margin-top: 2px; accent-color: #2563eb; }
.count-warning, .count-error, .count-job { padding: 12px; border-radius: 12px; margin: 12px 0; font-size: 14px; }
.count-warning { background: #fffbeb; color: #92400e; }.count-error { background: #fef2f2; color: #b91c1c; }
.count-job { background: #eff6ff; color: #1e40af; }.count-job p { margin: 6px 0; }
@media (max-width: 600px) { .count-table th:first-child { width: 56%; }.count-table td, .count-table th { padding: 9px 4px; }.count-dialog .erp-dialog__footer > button { flex: 1 1 auto; } }
</style>
