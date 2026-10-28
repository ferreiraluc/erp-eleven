<template>
  <div class="notification-composer">
    <NotificationContextSelector v-if="!isTemplate && (form.context || lockedSale || form.category === 'sales')" :model-value="form.context" :token="token" :initial-sale="initialSale" :locked-sale="lockedSale" :disabled="disabled" @update:model-value="setContext" @loaded="sale = $event" @selected="selectSeller" @validity="contextIssue = $event" />
    <label v-if="isTemplate"
      >{{ n('name') }}<input v-model="form.name" maxlength="100" required
    /></label>
    <label v-if="!isTemplate && templates.length"
      >{{ n('chooseTemplate')
      }}<ErpDropdown
        :model-value="templateId"
        :options="templateOptions"
        :label="n('chooseTemplate')"
        @update:model-value="applyTemplate(String($event))"
    /></label>
    <label>{{ n('titleLabel') }}<input v-model="form.title" maxlength="120" required /></label>
    <label
      >{{ n('bodyLabel') }}<textarea v-model="form.body" rows="4" maxlength="2000" required />
    </label>
    <p v-if="isTemplate" class="muted">{{ n('templateHelp') }}</p>
    <div class="notification-form-grid">
      <label
        >{{ n('category')
        }}<ErpDropdown
          v-model="form.category"
          :options="categoryOptions"
          :label="n('category')" /></label
      ><label
        >{{ n('severity')
        }}<ErpDropdown v-model="form.severity" :options="severityOptions" :label="n('severity')"
      /></label>
    </div>
    <label>{{ n('contextDestination') }}<ErpDropdown :model-value="destination" :options="destinationOptions" :label="n('contextDestination')" :disabled="disabled" @update:model-value="setDestination(String($event))" /></label>
    <NotificationTrackingSelector v-if="!isTemplate && destination === '/rastreamento'" v-model="form.action_path" :token="token" :disabled="disabled" @loaded="tracking = $event" @validity="trackingIssue = $event" />
    <label class="check"
      ><input
        v-model="form.requires_ack"
        type="checkbox"
        @change="!form.requires_ack && (form.requires_response = false)"
      />{{ n('requiresAck') }}</label
    >
    <label class="check"
      ><input
        v-model="form.requires_response"
        type="checkbox"
        @change="form.requires_response && (form.requires_ack = true)"
      />{{ n('requiresResponse') }}</label
    >
    <template v-if="!isTemplate">
      <fieldset>
        <legend>{{ n('recipients') }}</legend>
        <button
          type="button"
          class="erp-button erp-button--ghost erp-button--sm"
          @click="form.user_ids = users.map((user) => user.id)"
        >
          {{ n('selectAll') }}
        </button>
        <div class="notification-users">
          <label v-for="user in users" :key="user.id" class="check"
            ><input v-model="form.user_ids" type="checkbox" :value="user.id" />{{
              user.nome
            }}</label
          >
        </div>
      </fieldset>
      <label>{{ n('schedule') }}<input v-model="form.scheduled_at" type="datetime-local" /></label>
      <p class="muted">{{ n('scheduleHelp') }}</p>
      <section v-if="form.title || form.body" class="notification-preview" aria-live="polite">
        <h4>{{ n('contextPreview') }}</h4><strong>{{ preview.title }}</strong><p>{{ preview.body }}</p>
        <small v-if="destinationLabel">{{ n('contextDestination') }}: {{ destinationLabel }}</small>
        <p v-if="preview.problem" class="notification-preview__error" role="alert">{{ n(preview.problem) }}</p>
        <small>{{ n('contextPreviewHelp') }}</small>
      </section>
    </template>
  </div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import ErpDropdown from '@/components/ui/ErpDropdown.vue'
import {
  notificationCategories,
  notificationSeverities,
  type NotificationCategory,
  type NotificationSeverity,
  type NotificationTemplate,
  type NotificationContext,
  type NotificationSaleDetail,
  type NotificationSaleSummary,
  type NotificationTrackingDetail,
} from '@/services/notifications'
import { notificationText as n } from '@/services/notificationText'
import { notificationPreview } from '@/services/notificationAuthoring'
import NotificationContextSelector from './NotificationContextSelector.vue'
import NotificationTrackingSelector from './NotificationTrackingSelector.vue'
export interface NotificationForm {
  name: string
  title: string
  body: string
  category: NotificationCategory
  severity: NotificationSeverity
  action_path: string
  requires_ack: boolean
  requires_response: boolean
  user_ids: string[]
  scheduled_at: string
  context?: NotificationContext | null
}
const form = defineModel<NotificationForm>({ required: true })
const props = withDefaults(
  defineProps<{
    isTemplate?: boolean
    templates?: NotificationTemplate[]
    users?: { id: string; nome: string }[]
    token?: string | null
    initialSale?: NotificationSaleDetail | null
    lockedSale?: boolean
    disabled?: boolean
  }>(),
  { isTemplate: false, templates: () => [], users: () => [], token: null, initialSale: null, lockedSale: false, disabled: false },
)
const emit = defineEmits<{ validity: [message: string] }>()
const sale = ref<NotificationSaleDetail | null>(props.initialSale)
const contextIssue = ref('')
const trackingIssue = ref(''), tracking = ref<NotificationTrackingDetail | null>(null)
watch(() => form.value.context, value => { if (!value) contextIssue.value = '' })
const templateId = ref('')
const categoryOptions = computed(() =>
  notificationCategories.map((value) => ({ value, label: n(value) })),
)
const severityOptions = computed(() =>
  notificationSeverities.map((value) => ({ value, label: n(value) })),
)
const templateOptions = computed(() => [
  { value: '', label: n('none') },
  ...props.templates.map((template) => ({ value: template.id, label: template.name })),
])
const destination = computed(() => form.value.context?.target || (form.value.action_path.startsWith('/rastreamento?') ? '/rastreamento' : form.value.action_path))
const destinationOptions = computed(() => {
  if (props.lockedSale && !props.isTemplate) return [{ value: 'sale', label: n('contextSale') }, { value: 'product', label: n('contextProduct') }]
  const options = [{ value: '', label: n('contextNoDestination') }, { value: '/notificacoes', label: n('title') },
    ...(props.isTemplate ? [{ value: '/vendas-pdv', label: n('sales') }] : [{ value: 'sale', label: n('contextSale') }, { value: 'product', label: n('contextProduct') }]),
    { value: '/inventory', label: n('contextInventory') }, { value: '/rastreamento', label: n('tracking') }]
  if (form.value.action_path && !options.some(option => option.value === form.value.action_path)) options.push({ value: form.value.action_path, label: n('contextCurrentDestination') })
  return options
})
const destinationLabel = computed(() => destinationOptions.value.find(option => option.value === destination.value)?.label || '')
const preview = computed(() => notificationPreview(form.value, props.users, sale.value, new Date(), tracking.value))
watch(() => props.isTemplate ? '' : contextIssue.value || trackingIssue.value || (preview.value.problem ? n(preview.value.problem) : ''), value => emit('validity', value), { immediate: true, flush: 'sync' })
function setContext(value: NotificationContext | null) { form.value.context = value; form.value.action_path = '' }
function selectSeller(value: NotificationSaleSummary) {
  if (value.seller_id && props.users.some(user => user.id === value.seller_id)) form.value.user_ids = [value.seller_id]
}
function setDestination(value: string) {
  if (value === 'sale' || value === 'product') setContext({ ...form.value.context, target: value })
  else { form.value.context = null; form.value.action_path = value }
}
function applyTemplate(id: string) {
  templateId.value = id
  const template = props.templates.find((item) => item.id === id)
  if (template)
    Object.assign(form.value, {
      title: template.title,
      body: template.body,
      category: template.category,
      severity: template.severity,
      action_path: template.action_path || '',
      requires_ack: template.requires_ack,
      requires_response: template.requires_response,
    })
}
</script>
<style scoped>
.notification-composer {
  display: grid;
  gap: 14px;
}
.notification-composer label:not(.check) {
  display: grid;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.notification-composer input:not([type='checkbox']),
.notification-composer textarea {
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
  padding: 11px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  background: #fff;
  color: #0f172a;
  font: inherit;
  font-weight: 400;
}
.notification-composer textarea {
  resize: vertical;
  min-height: 100px;
}
.notification-composer .muted {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
  margin: -5px 0 0;
  overflow-wrap: anywhere;
}
.notification-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.check input {
  width: 19px;
  height: 19px;
  accent-color: #2563eb;
  flex-shrink: 0;
}
.notification-composer fieldset {
  min-width: 0;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 12px;
}
.notification-composer legend {
  font-size: 13px;
  font-weight: 650;
  padding: 0 5px;
}
.notification-users {
  display: flex;
  gap: 12px 20px;
  flex-wrap: wrap;
  margin-top: 8px;
}
.notification-preview{display:grid;gap:9px;padding:14px;background:#eff6ff;border:1px solid #dbeafe;border-radius:12px;overflow-wrap:anywhere}.notification-preview h4{margin:0;font-size:12px;color:#1d4ed8}.notification-preview>strong{font-size:15px;color:#0f172a}.notification-preview p{margin:0;white-space:pre-wrap;line-height:1.55;font-size:14px}.notification-preview small{font-size:12px;color:#64748b;line-height:1.5}.notification-preview .notification-preview__error{color:#b91c1c;font-size:13px}
@media (max-width: 500px) {
  .notification-form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
