<template>
  <article class="notification-rule">
    <div class="notification-rule__heading">
      <h4>{{ ruleLabel }}</h4>
      <label class="check"
        ><input v-model="enabled" type="checkbox" :disabled="busy" />{{ n('enabledRule') }}</label
      >
    </div>
    <div class="notification-rule__fields">
      <label
        >{{ n('chooseTemplate')
        }}<ErpDropdown
          v-model="templateId"
          :options="templateOptions"
          :label="n('chooseTemplate')"
          :disabled="busy" /></label
      ><label v-if="timed"
        >{{ n('time') }}<input v-model="localTime" type="time" :disabled="busy" required
      /></label>
    </div>
    <fieldset v-if="timed" :disabled="busy">
      <legend>{{ n('weekdays') }}</legend>
      <label v-for="day in days" :key="day" class="check"
        ><input v-model="weekdays" type="checkbox" :value="day" />{{
          n(`weekday${day}` as NotificationCopyKey)
        }}</label
      >
    </fieldset>
    <details>
      <summary>{{ n('recipients') }} · {{ userIds.length || n('defaultRecipients') }}</summary>
      <p>{{ n('automaticRecipients') }}</p>
      <p>{{ n(defaultRecipientsHelp) }}</p>
      <p v-if="salesEvent">{{ n('salesRecipientsScope') }}</p>
      <div class="notification-rule__users">
        <label v-for="user in users" :key="user.id" class="check"
          ><input v-model="userIds" type="checkbox" :value="user.id" :disabled="busy" />{{
            user.nome
          }}</label
        >
      </div>
    </details>
    <p v-if="error" class="notification-error" role="alert">{{ error }}</p>
    <button
      type="button"
      class="erp-button erp-button--secondary erp-button--sm"
      :disabled="busy || !changed"
      @click="save"
    >
      {{ n('save') }}
    </button>
  </article>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import {
  notificationsAPI,
  type NotificationRule,
  type NotificationTemplate,
} from '@/services/notifications'
import { notificationText as n, type NotificationCopyKey } from '@/services/notificationText'
import { useAuthStore } from '@/stores/auth'
const props = defineProps<{
    rule: NotificationRule
    templates: NotificationTemplate[]
    users: { id: string; nome: string }[]
  }>(),
  emit = defineEmits<{ saved: [] }>()
const auth = useAuthStore(),
  enabled = ref(false),
  templateId = ref(''),
  localTime = ref('09:00'),
  weekdays = ref<number[]>([]),
  userIds = ref<string[]>([]),
  busy = ref(false),
  error = ref(''),
  days = [0, 1, 2, 3, 4, 5, 6]
let generation = 0
watch(
  () => props.rule,
  (rule) => {
    generation++
    enabled.value = rule.enabled
    templateId.value = rule.template_id || ''
    localTime.value = rule.local_time?.slice(0, 5) || '09:00'
    weekdays.value = [...rule.weekdays]
    userIds.value = [...rule.user_ids]
    error.value = ''
    busy.value = false
  },
  { immediate: true },
)
const timed = computed(() =>
  ['daily_greeting', 'morning_greeting', 'afternoon_greeting'].includes(props.rule.event_key),
)
const salesEvent = computed(() =>
  ['sale_completed', 'sale_avulso_without_reason', 'sale_receipt_problem'].includes(props.rule.event_key),
)
const defaultRecipientsHelp = computed<NotificationCopyKey>(() => {
  if (props.rule.event_key === 'sale_completed') return 'defaultSaleRecipients'
  if (salesEvent.value) return 'defaultSaleProblemRecipients'
  if (props.rule.event_key === 'tracking_status_changed') return 'defaultTrackingRecipients'
  return 'defaultGreetingRecipients'
})
const ruleLabel = computed(() => n(props.rule.event_key as NotificationCopyKey))
const templateOptions = computed(() =>
  props.templates.map((template) => ({ value: template.id, label: template.name })),
)
const changed = computed(
  () =>
    enabled.value !== props.rule.enabled ||
    templateId.value !== (props.rule.template_id || '') ||
    localTime.value !== (props.rule.local_time?.slice(0, 5) || '09:00') ||
    JSON.stringify([...weekdays.value].sort()) !==
      JSON.stringify([...props.rule.weekdays].sort()) ||
    JSON.stringify([...userIds.value].sort()) !== JSON.stringify([...props.rule.user_ids].sort()),
)
async function save() {
  if (!auth.isOwner || !auth.token || busy.value) return
  if (!templateId.value || !/^\d{2}:\d{2}$/.test(localTime.value) || !weekdays.value.length) {
    error.value = n('ruleValidation')
    return
  }
  const owner = auth.token,
    current = ++generation
  busy.value = true
  error.value = ''
  try {
    await notificationsAPI.rule(
      props.rule.event_key,
      {
        expected_version: props.rule.version,
        enabled: enabled.value,
        template_id: templateId.value,
        local_time: localTime.value,
        weekdays: weekdays.value,
        user_ids: userIds.value,
      },
      owner,
    )
    if (owner === auth.token && current === generation) emit('saved')
  } catch (reason) {
    if (owner === auth.token && current === generation)
      error.value = n(
        (reason as { response?: { status?: number } }).response?.status === 409
          ? 'conflict'
          : 'saveError',
      )
  } finally {
    if (owner === auth.token && current === generation) busy.value = false
  }
}
</script>
<style scoped>
.notification-rule {
  display: grid;
  gap: 14px;
  border: 1px solid #dbe4ef;
  padding: 16px;
  border-radius: 12px;
  background: #fff;
}
.notification-rule__heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.notification-rule h4 {
  margin: 0;
  font-size: 15px;
}
.notification-rule__fields {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 180px);
  gap: 14px;
}
.notification-rule__fields > label {
  display: grid;
  gap: 7px;
  font-size: 13px;
  color: #475569;
  font-weight: 600;
}
.notification-rule input[type='time'] {
  padding: 11px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  font: inherit;
  background: #fff;
  width: 100%;
  box-sizing: border-box;
  min-width: 0;
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.check input {
  width: 18px;
  height: 18px;
  accent-color: #2563eb;
}
.notification-rule fieldset {
  border: 0;
  padding: 0;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.notification-rule legend {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 8px;
}
.notification-rule details summary {
  font-size: 13px;
  cursor: pointer;
  color: #475569;
}
.notification-rule details p {
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}
.notification-rule__users {
  display: flex;
  gap: 12px 20px;
  flex-wrap: wrap;
}
.notification-rule > .erp-button {
  justify-self: start;
}
.notification-error {
  font-size: 13px;
  color: #b91c1c;
  margin: 0;
}
@media (max-width: 500px) {
  .notification-rule__fields {
    grid-template-columns: 1fr;
  }
}
</style>
