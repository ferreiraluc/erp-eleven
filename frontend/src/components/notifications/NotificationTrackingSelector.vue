<template>
  <div class="notification-tracking">
    <label>{{ n('trackingCode') }}<input :value="code" type="search" maxlength="80" autocomplete="off" :disabled="disabled" @input="setCode(($event.target as HTMLInputElement).value)" /></label>
    <p v-if="loading" role="status">{{ n('loading') }}</p>
    <p v-else-if="tracking" class="tracking-reference"><strong>{{ tracking.cliente_username }}</strong> · {{ tracking.code }} · {{ tracking.status }}</p>
    <p v-else-if="error" class="tracking-error" role="alert">{{ n('trackingLookupError') }}</p>
    <p v-else>{{ n('trackingCodeHelp') }}</p>
  </div>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { notificationsAPI, type NotificationTrackingDetail } from '@/services/notifications'
import { trackingCodeFromPath } from '@/services/notificationAuthoring'
import { notificationText as n } from '@/services/notificationText'
const props = defineProps<{ modelValue: string; token: string | null; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string]; loaded: [value: NotificationTrackingDetail | null]; validity: [message: string] }>()
const code = computed(() => trackingCodeFromPath(props.modelValue))
const tracking = ref<NotificationTrackingDetail | null>(null), loading = ref(false), error = ref(false)
let epoch = 0, timer: ReturnType<typeof setTimeout> | undefined, controller: AbortController | undefined
function setCode(value: string) {
  const normalized = value.trim().replace(/[\s-]+/g, '').toUpperCase()
  emit('update:modelValue', normalized ? `/rastreamento?search=${encodeURIComponent(normalized)}` : '/rastreamento')
}
watch([code, () => props.token], ([value, token]) => {
  const own = ++epoch
  clearTimeout(timer); controller?.abort(); tracking.value = null; loading.value = false; error.value = false; emit('loaded', null)
  if (!value || !token) return
  if (!/^[A-Z0-9]{5,80}$/.test(value)) { error.value = true; return }
  loading.value = true
  timer = setTimeout(async () => {
    controller = new AbortController()
    try {
      const result = await notificationsAPI.contextTracking(value, token, controller.signal)
      if (own !== epoch || token !== props.token) return
      tracking.value = result; emit('loaded', result)
    } catch { if (own === epoch) error.value = true }
    finally { if (own === epoch) loading.value = false }
  }, 300)
}, { immediate: true, flush: 'sync' })
watch([loading, error], () => emit('validity', loading.value ? n('loading') : error.value ? n('trackingLookupError') : ''), { immediate: true, flush: 'sync' })
onBeforeUnmount(() => { epoch++; clearTimeout(timer); controller?.abort(); emit('loaded', null); emit('validity', '') })
</script>
<style scoped>
.notification-tracking{padding:14px;display:grid;gap:10px;border:1px solid #dbe4ef;border-radius:12px;background:#f8fafc}
.notification-tracking label{display:grid;gap:7px;font-size:13px;font-weight:600;color:#475569}
.notification-tracking input{width:100%;min-width:0;box-sizing:border-box;padding:11px 12px;border:1px solid #cbd5e1;border-radius:10px;font:inherit;background:#fff}
.notification-tracking p{margin:0;font-size:12px;line-height:1.5;overflow-wrap:anywhere;color:#64748b}.tracking-error{color:#b91c1c!important}.tracking-reference strong{color:#1d4ed8}
</style>
