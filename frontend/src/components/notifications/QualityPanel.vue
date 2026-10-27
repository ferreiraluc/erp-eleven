<template>
  <details
    v-if="auth.isOwner"
    class="quality-panel"
    :open="open"
    @toggle="toggle(($event.target as HTMLDetailsElement).open)"
  >
    <summary>{{ q('title') }}</summary>
    <div v-if="open" class="quality-panel__body">
      <div class="quality-panel__intro">
        <p>{{ q('intro') }}</p>
        <button
          type="button"
          class="erp-button erp-button--secondary erp-button--sm"
          :disabled="loading || busy"
          @click="load(true)"
        >
          {{ q('refresh') }}
        </button>
      </div>
      <p v-if="error" class="quality-error" role="alert">{{ error }}</p>
      <p v-if="feedback" class="quality-feedback" role="status">
        {{ feedback }}
      </p>
      <p v-if="!online" class="quality-muted" role="status">
        {{ q('offline') }}
      </p>
      <p v-if="loading && !overview" role="status">{{ q('loading') }}</p>
      <template v-if="overview">
        <form class="quality-config" @submit.prevent="saveConfig">
          <fieldset :disabled="busy">
            <label class="quality-check"
              ><input v-model="settings.enabled" type="checkbox" />{{ q('enabled') }}</label
            ><label class="quality-time"
              >{{ q('time') }}<input v-model="settings.local_time" type="time" required /></label
            ><label class="quality-check"
              ><input v-model="settings.ai_enabled" type="checkbox" />{{ q('aiEnabled') }}</label
            >
          </fieldset>
          <p class="quality-muted">{{ q('aiHelp') }}</p>
          <p class="quality-muted">
            {{
              q('limits', {
                manual: overview.limits.manual_scans_per_day || 3,
                calls: overview.limits.max_provider_calls_per_day || 2,
              })
            }}
          </p>
          <p class="quality-muted">
            {{ q('scheduleHelp') }}
            {{ q('firstRun', { date: day(overview.config.first_run_on) }) }}
          </p>
          <button
            type="submit"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="busy || !dirty"
          >
            {{ q('save') }}
          </button>
        </form>
        <div class="quality-panel__scan">
          <button
            type="button"
            class="erp-button erp-button--primary erp-button--sm"
            :disabled="busy || loading || !overview.config.enabled || active || !online"
            @click="scan"
          >
            {{ q('scan') }}</button
          ><span v-if="!overview.config.enabled" class="quality-muted">{{ q('paused') }}</span
          ><span v-else-if="active" class="quality-muted" role="status">{{ q('queuedHelp') }}</span>
        </div>
        <p v-if="detailError" class="quality-error" role="alert">
          {{ detailError }}
        </p>
        <QualityReport
          v-if="selected"
          :run="selected"
          :loading="detailLoading"
          @page="loadDetail(selected.id, $event)"
        />
        <p v-else-if="!detailLoading" class="quality-empty">{{ q('empty') }}</p>
        <section class="quality-history">
          <h3>{{ q('history') }}</h3>
          <p v-if="!overview.runs.length" class="quality-muted">
            {{ q('historyEmpty') }}
          </p>
          <ul v-else>
            <li v-for="run in overview.runs" :key="run.id">
              <div>
                <strong>{{ date(run.created_at) }}</strong
                ><small>{{ q(run.kind) }} · {{ q(run.status) }}</small>
              </div>
              <button
                type="button"
                class="erp-button erp-button--secondary erp-button--sm"
                :disabled="detailLoading"
                @click="loadDetail(run.id)"
              >
                {{ q('view') }}
              </button>
            </li>
          </ul>
          <div v-if="overview.total > overview.limit" class="quality-pagination">
            <span
              >{{ overview.offset + 1 }}–{{
                Math.min(overview.offset + overview.runs.length, overview.total)
              }}
              / {{ overview.total }}</span
            ><button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="loading || !offset"
              @click="page(-overview.limit)"
            >
              {{ q('previous') }}</button
            ><button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="loading || overview.offset + overview.limit >= overview.total"
              @click="page(overview.limit)"
            >
              {{ q('next') }}
            </button>
          </div>
        </section>
      </template>
    </div>
  </details>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  systemQualityAPI,
  isQualityRunId,
  type QualityOverview,
  type QualityRunDetail,
} from '@/services/systemQuality'
import { qualityText as q } from '@/services/systemQualityText'
import { uiLocale } from '@/i18n/uiText'
import QualityReport from './QualityReport.vue'
const props = defineProps<{ runId?: string | null }>(),
  auth = useAuthStore()
const open = ref(false),
  overview = ref<QualityOverview | null>(null),
  selected = ref<QualityRunDetail | null>(null),
  loading = ref(false),
  detailLoading = ref(false),
  busy = ref(false),
  error = ref(''),
  detailError = ref(''),
  feedback = ref(''),
  offset = ref(0),
  online = ref(navigator.onLine)
const settings = ref({ enabled: true, ai_enabled: true, local_time: '08:30' }),
  settingsVersion = ref(0),
  scanRequest = ref(crypto.randomUUID())
let generation = 0,
  request = 0,
  detailRequest = 0,
  timer: ReturnType<typeof setInterval> | undefined
const dirty = computed(
  () =>
    !!overview.value &&
    (settings.value.enabled !== overview.value.config.enabled ||
      settings.value.ai_enabled !== overview.value.config.ai_enabled ||
      settings.value.local_time !== overview.value.config.local_time),
)
const active = computed(() =>
  [overview.value?.latest, selected.value, ...(overview.value?.runs || [])].some(
    (run) =>
      run &&
      ['queued', 'running'].includes(run.status) &&
      Date.now() - new Date(run.created_at).getTime() < 86400000,
  ),
)
const day = (value: string) => new Date(value + 'T12:00:00').toLocaleDateString(uiLocale())
const date = (value: string) =>
  new Date(value).toLocaleString(uiLocale(), {
    dateStyle: 'short',
    timeStyle: 'short',
  })
function own(current: number, token: string | null) {
  return current === generation && auth.isOwner && auth.isAuthenticated && token === auth.token
}
function toggle(value: boolean) {
  if (open.value === value) return
  open.value = value
  if (value && !overview.value) void load()
  schedulePoll()
}
function applySettings(value: QualityOverview['config']) {
  settings.value = {
    enabled: value.enabled,
    ai_enabled: value.ai_enabled,
    local_time: value.local_time,
  }
  settingsVersion.value = value.version
}
async function load(resetSettings = false) {
  if (!auth.isOwner || !auth.isAuthenticated || !auth.token || !open.value || !online.value) return
  const current = generation,
    id = ++request,
    token = auth.token
  loading.value = true
  error.value = ''
  try {
    const result = await systemQualityAPI.overview(offset.value, token)
    if (!own(current, token) || id !== request) return
    if (!overview.value || !dirty.value || resetSettings) applySettings(result.config)
    overview.value = result
    if (!selected.value || selected.value.id === result.latest?.id) selected.value = result.latest
    if (isQualityRunId(props.runId) && selected.value?.id !== props.runId)
      await loadDetail(props.runId)
    else if (
      selected.value &&
      ['queued', 'running'].includes(selected.value.status) &&
      selected.value.id !== result.latest?.id
    )
      await loadDetail(selected.value.id, selected.value.findings_offset)
  } catch {
    if (own(current, token) && id === request) error.value = q('error')
  } finally {
    if (own(current, token) && id === request) {
      loading.value = false
      schedulePoll()
    }
  }
}
async function loadDetail(id: string, findingsOffset = 0) {
  if (!auth.isOwner || !auth.token || !isQualityRunId(id)) return
  const current = generation,
    next = ++detailRequest,
    token = auth.token
  detailLoading.value = true
  detailError.value = ''
  try {
    const result = await systemQualityAPI.detail(id, findingsOffset, token)
    if (own(current, token) && next === detailRequest) selected.value = result
  } catch {
    if (own(current, token) && next === detailRequest) detailError.value = q('error')
  } finally {
    if (own(current, token) && next === detailRequest) {
      detailLoading.value = false
      schedulePoll()
    }
  }
}
async function saveConfig() {
  if (!auth.isOwner || !auth.token || busy.value || !overview.value) return
  if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(settings.value.local_time)) {
    error.value = q('invalidTime')
    return
  }
  const current = generation,
    token = auth.token
  busy.value = true
  error.value = ''
  feedback.value = ''
  try {
    const result = await systemQualityAPI.configure(
      { ...settings.value, expected_version: settingsVersion.value },
      token,
    )
    if (own(current, token)) {
      overview.value = { ...overview.value!, config: result }
      applySettings(result)
      feedback.value = q('saved')
    }
  } catch (reason) {
    if (own(current, token))
      error.value = q(
        (reason as { response?: { status?: number } }).response?.status === 409
          ? 'conflict'
          : 'saveError',
      )
  } finally {
    if (own(current, token)) busy.value = false
  }
}
async function scan() {
  if (!auth.isOwner || !auth.token || busy.value || active.value || !overview.value?.config.enabled)
    return
  const current = generation,
    token = auth.token
  busy.value = true
  error.value = ''
  feedback.value = ''
  try {
    const run = await systemQualityAPI.scan(scanRequest.value, token)
    if (!own(current, token)) return
    scanRequest.value = crypto.randomUUID()
    feedback.value = q('queuedHelp')
    selected.value = {
      ...run,
      findings: [],
      findings_total: 0,
      findings_offset: 0,
      findings_limit: 30,
    }
    await load()
  } catch (reason) {
    if (own(current, token)) {
      const status = (reason as { response?: { status?: number } }).response?.status
      error.value = q(
        status === 429 ? 'dailyLimit' : status === 409 ? 'activeConflict' : 'scanError',
      )
    }
  } finally {
    if (own(current, token)) {
      busy.value = false
      schedulePoll()
    }
  }
}
function page(delta: number) {
  offset.value = Math.max(0, offset.value + delta)
  void load()
}
function schedulePoll() {
  if (timer) clearInterval(timer)
  timer = undefined
  if (
    open.value &&
    auth.isOwner &&
    active.value &&
    online.value &&
    document.visibilityState !== 'hidden'
  )
    timer = setInterval(() => {
      if (!loading.value && !busy.value) void load()
    }, 15000)
}
function environmentChanged() {
  online.value = navigator.onLine
  schedulePoll()
  if (
    open.value &&
    online.value &&
    document.visibilityState !== 'hidden' &&
    active.value &&
    !loading.value
  )
    void load()
}
watch(
  () => (auth.isAuthenticated && auth.isOwner ? auth.token : null),
  (token) => {
    generation++
    request++
    detailRequest++
    overview.value = null
    selected.value = null
    error.value = ''
    detailError.value = ''
    feedback.value = ''
    loading.value = false
    busy.value = false
    detailLoading.value = false
    offset.value = 0
    scanRequest.value = crypto.randomUUID()
    if (!token) open.value = false
    if (token && isQualityRunId(props.runId)) {
      open.value = true
      void load()
    }
    schedulePoll()
  },
  { immediate: true, flush: 'sync' },
)
watch(
  () => props.runId,
  (id) => {
    if (isQualityRunId(id) && auth.isOwner) {
      open.value = true
      if (overview.value) void loadDetail(id)
      else void load()
    }
  },
)
onMounted(() => {
  document.addEventListener('visibilitychange', environmentChanged)
  window.addEventListener('online', environmentChanged)
  window.addEventListener('offline', environmentChanged)
})
onBeforeUnmount(() => {
  generation++
  request++
  detailRequest++
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', environmentChanged)
  window.removeEventListener('online', environmentChanged)
  window.removeEventListener('offline', environmentChanged)
})
</script>
<style scoped>
.quality-panel {
  margin-bottom: 20px;
  max-width: none;
  min-width: 0;
  padding: 20px;
  border: 1px solid #dbe4ef;
  border-radius: 14px;
  background: white;
}
.quality-panel > summary {
  font-size: 16px;
  font-weight: 700;
  color: #1d4ed8;
  cursor: pointer;
}
.quality-panel[open] > summary {
  margin-bottom: 18px;
}
.quality-panel__body {
  display: grid;
  gap: 16px;
  min-width: 0;
}
.quality-panel__intro {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}
.quality-panel__intro p {
  margin: 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  max-width: 70ch;
}
.quality-panel__intro .erp-button {
  flex-shrink: 0;
}
.quality-config {
  display: grid;
  gap: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
  background: #f8fafc;
}
.quality-config fieldset {
  display: flex;
  gap: 14px 20px;
  align-items: center;
  flex-wrap: wrap;
  min-width: 0;
  padding: 0;
  border: 0;
  margin: 0;
}
.quality-check {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.quality-check input {
  width: 18px;
  height: 18px;
  accent-color: #2563eb;
  flex-shrink: 0;
}
.quality-time {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #475569;
}
.quality-time input {
  min-width: 0;
  padding: 9px;
  border: 1px solid #cbd5e1;
  border-radius: 9px;
  font: inherit;
  background: white;
  color: #0f172a;
}
.quality-config > .erp-button {
  justify-self: start;
}
.quality-panel__scan {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.quality-muted {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  margin: 0;
}
.quality-error {
  font-size: 13px;
  line-height: 1.5;
  color: #b91c1c;
  background: #fff1f2;
  border-radius: 9px;
  padding: 12px;
  margin: 0;
}
.quality-feedback {
  font-size: 13px;
  line-height: 1.5;
  color: #047857;
  background: #ecfdf5;
  border-radius: 9px;
  padding: 12px;
  margin: 0;
}
.quality-empty {
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
  padding: 24px;
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
  margin: 0;
}
.quality-history {
  display: grid;
  gap: 12px;
}
.quality-history h3 {
  font-size: 14px;
  margin: 0;
}
.quality-history ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}
.quality-history li {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
}
.quality-history li > div {
  display: grid;
  gap: 5px;
  min-width: 0;
}
.quality-history strong {
  font-size: 13px;
}
.quality-history small {
  font-size: 11px;
  color: #64748b;
}
.quality-history .erp-button {
  flex-shrink: 0;
}
.quality-pagination {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #64748b;
}
.quality-pagination > span {
  margin-right: auto;
}
@media (max-width: 500px) {
  .quality-panel {
    padding: 14px;
  }
  .quality-panel__intro {
    flex-wrap: wrap;
  }
  .quality-config {
    padding: 12px;
  }
  .quality-history li {
    flex-wrap: wrap;
  }
  .quality-time {
    flex-wrap: wrap;
  }
}
</style>
