<template>
  <section class="monitoring-card">
    <h2>{{ text('title') }}</h2><p>{{ text('intro') }}</p>
    <p v-if="loading" role="status">{{ text('loading') }}</p>
    <p v-if="error" role="alert" class="monitoring-error">{{ error }}</p>
    <template v-if="status">
      <p v-if="!status.api_key_configured" class="monitoring-error">{{ text('noKey') }}</p>
      <dl class="monitoring-counts"><div v-for="(value, key) in counts" :key="key"><dt>{{ text(key) }}</dt><dd>{{ value }}</dd></div></dl>
      <form @submit.prevent="save">
        <fieldset :disabled="busy || loading">
          <label>{{ text('endpoint') }}<input v-model="form.endpoint_id" required maxlength="36" /></label>
          <label>{{ text('profile') }}<input v-model="form.profile_id" required maxlength="36" /></label>
          <label>{{ text('secret') }}<input v-model="signingSecret" type="password" autocomplete="new-password" maxlength="500" :required="!status.configured" /><small v-if="status.configured">{{ text('keep') }}</small></label>
          <label>{{ text('interval') }}<ErpSelect v-model="form.interval_hours" :label="text('interval')" :disabled="busy"><option v-for="hours in [1, 2, 4, 6, 12]" :key="hours" :value="hours">{{ text('hours', { count: hours }) }}</option></ErpSelect></label>
          <label class="monitoring-check"><input v-model="form.enabled" type="checkbox" />{{ text('enabled') }}</label>
          <label class="monitoring-check"><input v-model="form.daytime_only" type="checkbox" />{{ text('night') }}</label>
          <p>{{ text('usage', { count: 24 / Number(form.interval_hours) }) }}</p>
          <label v-if="form.enabled" class="monitoring-check"><input v-model="consent" type="checkbox" required />{{ text('consent') }}</label>
          <small>{{ text('cleanup') }}</small><p v-if="!form.enabled">{{ text('paused') }}</p>
          <div class="monitoring-actions"><button class="erp-button erp-button--primary" :disabled="busy || (form.enabled && !consent)" type="submit">{{ text('save') }}</button><button type="button" class="erp-button erp-button--secondary" :disabled="busy" @click="load">{{ text('refresh') }}</button></div>
        </fieldset>
      </form>
      <label>{{ text('address') }}<input readonly :value="webhookUrl" /></label>
      <p v-if="saved" role="status">{{ text('saved') }}</p>
    </template>
  </section>
</template>
<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import api from '@/services/api'
import { useAuthStore } from '@/stores/auth'
import ErpSelect from '@/components/ui/ErpSelect.vue'
import { monitoringMessages } from './monitoringMessages'
interface Status { configured: boolean; enabled: boolean; api_key_configured: boolean; endpoint_id: string; profile_id: string; interval_hours: number; daytime_only: boolean; subscriptions: Record<string, number>; failed_subscriptions: number; failed_events: number }
const { t: text } = useI18n({ useScope: 'local', messages: monitoringMessages })
const auth = useAuthStore(), status = ref<Status | null>(null)
const form = ref({ endpoint_id: '', profile_id: '', interval_hours: 2, enabled: false, daytime_only: true })
const signingSecret = ref(''), consent = ref(false), error = ref(''), saved = ref(false), busy = ref(false), loading = ref(false)
const webhookUrl = `${String(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')}/api/tracking-monitor/webhook`
const counts = computed(() => ({ active: status.value?.subscriptions.active || 0, pending: status.value?.subscriptions.pending || 0, nightPaused: status.value?.subscriptions.paused || 0, stopped: (status.value?.subscriptions.stopped || 0) + (status.value?.subscriptions.expired || 0), errors: (status.value?.failed_subscriptions || 0) + (status.value?.failed_events || 0) }))
let generation = 0
function headers(token: string | null) { return { Authorization: token ? `Bearer ${token}` : null } }
function message(value: unknown) { const detail = (value as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail; return typeof detail === 'string' ? detail : text('error') }
async function load() {
  const current = ++generation, token = auth.token
  loading.value = true; error.value = ''
  try { const { data } = await api.get<Status>('/api/tracking-monitor/config', { headers: headers(token) }); if (current !== generation || token !== auth.token) return; status.value = data; form.value = { endpoint_id: data.endpoint_id, profile_id: data.profile_id, interval_hours: data.interval_hours, enabled: data.enabled, daytime_only: data.daytime_only }; signingSecret.value = ''; consent.value = false }
  catch (value) { if (current === generation) error.value = message(value) }
  finally { if (current === generation) loading.value = false }
}
async function save() {
  if (busy.value || !auth.isOwner || form.value.enabled && !consent.value) return
  const current = ++generation, token = auth.token
  busy.value = true; error.value = ''; saved.value = false
  try { const { data } = await api.put<Status>('/api/tracking-monitor/config', { ...form.value, interval_hours: Number(form.value.interval_hours), monitor_days: 30, confirm_monitoring: consent.value, ...(signingSecret.value.trim() ? { signing_secret: signingSecret.value.trim() } : {}) }, { headers: headers(token) }); if (current !== generation || token !== auth.token) return; status.value = data; signingSecret.value = ''; consent.value = false; saved.value = true }
  catch (value) { if (current === generation) error.value = message(value) }
  finally { if (current === generation) busy.value = false }
}
watch(() => auth.token, () => { generation++; status.value = null; signingSecret.value = ''; error.value = ''; busy.value = false; loading.value = false })
onBeforeUnmount(() => { generation++; signingSecret.value = '' })
onMounted(load)
</script>
<style scoped>
.monitoring-card { padding: 24px; border: 1px solid #e2e8f0; border-radius: 14px; background: #fff; }
h2 { margin: 0 0 8px; font-size: 18px; } p, small, dt { color: #64748b; line-height: 1.5; font-size: .85rem; }
fieldset { display: grid; gap: 16px; border: 0; padding: 0; min-width: 0; } label { display: flex; flex-direction: column; gap: 6px; color: #334155; font-size: .85rem; }
input:not([type=checkbox]) { border: 1px solid #cbd5e1; padding: 10px; border-radius: 8px; width: 100%; min-width: 0; box-sizing: border-box; font: inherit; }
.monitoring-check { flex-direction: row; align-items: start; line-height: 1.6; } .monitoring-check input { margin-top: 4px; flex: none; accent-color: #2563eb; }
.monitoring-counts { display: flex; flex-wrap: wrap; gap: 20px; } dd { margin: 4px 0 0; font-weight: 700; color: #1d4ed8; } .monitoring-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 18px; }
.monitoring-error { color: #b91c1c; } @media(max-width:600px) { .monitoring-card { padding: 18px; } }
</style>
