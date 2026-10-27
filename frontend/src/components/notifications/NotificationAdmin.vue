<template>
  <section v-if="auth.isOwner" class="notification-admin" :aria-label="n('admin')">
    <div class="notification-admin__heading">
      <div>
        <h2 v-if="!embedded">{{ n('admin') }}</h2>
        <p>{{ n('adminHelp') }}</p>
      </div>
      <button
        class="erp-button erp-button--secondary erp-button--sm"
        :disabled="loading || busy"
        @click="load()"
      >
        {{ n('refresh') }}
      </button>
    </div>
    <div class="notification-admin__tabs" role="tablist" :aria-label="n('admin')">
      <button
        v-for="key in tabs"
        :key="key"
        role="tab"
        class="erp-control"
        :aria-selected="tab === key"
        :class="{ active: tab === key }"
        :disabled="busy"
        @click="changeTab(key)"
      >
        {{ n(key) }}
      </button>
    </div>
    <p v-if="error" class="notification-admin__error" role="alert">{{ error }}</p>
    <p v-if="success" role="status" class="notification-admin__success">{{ success }}</p>
    <p v-if="loading && !data" role="status">{{ n('loading') }}</p>
    <template v-if="data">
      <button
        v-if="tab !== 'rules' && !formMode"
        class="erp-button erp-button--primary erp-button--sm"
        :disabled="busy"
        @click="newForm()"
      >
        ＋ {{ n(tab === 'messages' ? 'newMessage' : 'newTemplate') }}
      </button>
      <form v-if="formMode" class="notification-admin__form" @submit.prevent="save">
        <h3>{{ n(editId ? 'edit' : formMode === 'template' ? 'newTemplate' : 'newMessage') }}</h3>
        <fieldset :disabled="busy">
          <NotificationComposer
            v-model="form"
            :key="formKey"
            :is-template="formMode === 'template'"
            :templates="data.templates"
            :users="data.users"
            :token="auth.token"
            :disabled="busy"
            @validity="composerError = $event"
          />
        </fieldset>
        <p v-if="formError" class="notification-admin__error" role="alert">{{ formError }}</p>
        <div class="notification-admin__actions">
          <button
            class="erp-button erp-button--secondary"
            type="button"
            :disabled="busy"
            @click="formMode = null"
          >
            {{ n('cancel') }}</button
          ><button class="erp-button erp-button--primary" type="submit" :disabled="busy || !!composerError">
            {{ n(busy ? 'loading' : editId || formMode === 'template' ? 'save' : 'send') }}
          </button>
        </div>
      </form>
      <div v-if="tab === 'messages'" class="notification-admin__list">
        <article v-for="item in data.items" :key="item.id" class="notification-admin__item">
          <div class="notification-admin__item-heading">
            <h3>{{ item.title }}</h3>
            <span :class="{ 'is-cancelled': item.cancelled_at }"
              >{{
                n(item.cancelled_at ? 'cancelled' : !item.published_at ? 'scheduled' : 'published')
              }}
              · {{ date(item.published_at || item.scheduled_at || item.created_at) }}</span
            >
          </div>
          <p class="notification-admin__body">{{ item.body }}</p>
          <small
            >{{
              n('readCount', { count: item.receipts.filter((receipt) => receipt.read_at).length })
            }}
            ·
            {{
              n('acknowledgedCount', {
                count: item.receipts.filter((receipt) => receipt.acknowledged_at).length,
              })
            }}</small
          >
          <details>
            <summary>{{ n('receipts') }}</summary>
            <ul>
              <li v-for="receipt in item.receipts" :key="receipt.user_id">
                <strong>{{ receipt.user_name }}</strong
                ><span>{{
                  receipt.removed_at
                    ? n('removed')
                    : receipt.acknowledged_at
                      ? n('acknowledged')
                      : receipt.read_at
                        ? n('readCount', { count: 1 })
                        : n('pending')
                }}</span>
                <p v-if="receipt.acknowledgement_note" class="notification-admin__body">
                  {{ receipt.acknowledgement_note }}
                </p>
                <small
                  >{{ n('pushStatus') }}: {{ n(receipt.push_status as NotificationCopyKey) }}</small
                ><small v-if="receipt.acknowledged_at"
                  >{{ n('revision', { version: receipt.acknowledged_version || 1 }) }} ·
                  {{ date(receipt.acknowledged_at) }}</small
                >
              </li>
            </ul>
          </details>
          <div v-if="!item.cancelled_at" class="notification-admin__actions">
            <button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy"
              @click="editMessage(item)"
            >
              {{ n('edit') }}</button
            ><button
              type="button"
              class="erp-button erp-button--ghost erp-button--sm"
              :disabled="busy"
              @click="cancelId = item.id"
            >
              {{ n('cancel') }}
            </button>
          </div>
          <div v-if="cancelId === item.id" class="notification-admin__cancel">
            <p>{{ n('confirmCancel') }}</p>
            <button
              type="button"
              class="erp-button erp-button--secondary erp-button--sm"
              :disabled="busy"
              @click="cancelId = ''"
            >
              {{ n('close') }}</button
            ><button
              type="button"
              class="erp-button erp-button--danger erp-button--sm"
              :disabled="busy"
              @click="cancelMessage(item)"
            >
              {{ n('cancel') }}
            </button>
          </div>
        </article>
        <p v-if="!data.items.length">{{ n('empty') }}</p>
        <div class="notification-admin__actions">
          <button
            v-if="offset"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || busy"
            @click="paginate(-20)"
          >
            ←</button
          ><button
            v-if="offset + data.items.length < data.total"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="loading || busy"
            @click="paginate(20)"
          >
            {{ n('more') }}
          </button>
        </div>
      </div>
      <div v-else-if="tab === 'templates'" class="notification-admin__list">
        <article
          v-for="template in data.templates"
          :key="template.id"
          class="notification-admin__item"
        >
          <h3>{{ template.name }}</h3>
          <strong>{{ template.title }}</strong>
          <p class="notification-admin__body">{{ template.body }}</p>
          <button
            type="button"
            class="erp-button erp-button--secondary erp-button--sm"
            :disabled="busy"
            @click="editTemplate(template)"
          >
            {{ n('edit') }}
          </button>
        </article>
      </div>
      <div v-else class="notification-admin__list">
        <NotificationRuleEditor
          v-for="rule in data.rules"
          :key="rule.event_key"
          :rule="rule"
          :templates="data.templates"
          :users="data.users"
          @saved="load()"
        />
      </div>
    </template>
  </section>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  notificationsAPI,
  safeNotificationPath,
  type AdminNotification,
  type NotificationAdminResult,
  type NotificationContent,
  type NotificationTemplate,
} from '@/services/notifications'
import { notificationText as n, type NotificationCopyKey } from '@/services/notificationText'
import { uiLocale } from '@/i18n/uiText'
import NotificationComposer, { type NotificationForm } from './NotificationComposer.vue'
import NotificationRuleEditor from './NotificationRuleEditor.vue'
defineProps<{embedded?:boolean}>()
const auth = useAuthStore(),
  tabs = ['messages', 'templates', 'rules'] as const,
  tab = ref<(typeof tabs)[number]>('messages')
const data = ref<NotificationAdminResult | null>(null),
  loading = ref(false),
  busy = ref(false),
  error = ref(''),
  formError = ref(''),
  composerError = ref(''),
  success = ref(''),
  offset = ref(0),
  cancelId = ref('')
const formMode = ref<'message' | 'template' | null>(null),
  editId = ref(''),
  version = ref(0),
  formKey = ref(0),
  requestId = ref(crypto.randomUUID())
const blank = (): NotificationForm => ({
  name: '',
  title: '',
  body: '',
  category: 'manual',
  severity: 'info',
  action_path: '',
  requires_ack: false,
  requires_response: false,
  user_ids: [],
  scheduled_at: '',
  context: null,
})
const form = ref<NotificationForm>(blank())
function changeTab(value: typeof tabs[number]) { if (busy.value) return; tab.value = value; formMode.value = null }
function paginate(change: number) { if (busy.value) return; offset.value = Math.max(0, offset.value + change); void load() }
let generation = 0,
  read = 0,
  saveEpoch = 0
const date = (value: string) =>
  new Date(value).toLocaleString(uiLocale(), { dateStyle: 'short', timeStyle: 'short' })
watch(
  form,
  () => {
    requestId.value = crypto.randomUUID()
  },
  { deep: true, flush: 'sync' },
)
watch(
  () => (auth.isAuthenticated && auth.isOwner ? auth.token : null),
  (token) => {
    generation++
    read++
    saveEpoch++
    data.value = null
    formMode.value = null
    error.value = ''
    success.value = ''
    busy.value = false
    offset.value = 0
    if (token) void load()
  },
  { immediate: true, flush: 'sync' },
)
onBeforeUnmount(() => {
  generation++
  read++
  saveEpoch++
})
async function load() {
  if (!auth.isOwner || !auth.token) return
  const own = generation,
    current = ++read,
    token = auth.token
  loading.value = true
  error.value = ''
  try {
    const result = await notificationsAPI.admin(offset.value, token)
    if (own === generation && current === read && token === auth.token) data.value = result
  } catch {
    if (own === generation && current === read) error.value = n('error')
  } finally {
    if (own === generation && current === read) loading.value = false
  }
}
function newForm() {
  if (busy.value) return
  editId.value = ''
  version.value = 0
  form.value = blank()
  formMode.value = tab.value === 'templates' ? 'template' : 'message'
  formError.value = ''
  composerError.value = ''
  success.value = ''
  formKey.value++
}
function localDate(value: string | null) {
  if (!value) return ''
  const date = new Date(value)
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
}
function editMessage(item: AdminNotification) {
  if (busy.value) return
  form.value = {
    ...blank(),
    ...item,
    title: item.authored_title ?? item.title,
    body: item.authored_body ?? item.body,
    action_path: item.action_path || '',
    user_ids: [...item.user_ids],
    scheduled_at: localDate(item.scheduled_at),
  }
  editId.value = item.id
  version.value = item.version
  formMode.value = 'message'
  formError.value = ''
  formKey.value++
}
function editTemplate(template: NotificationTemplate) {
  if (busy.value) return
  form.value = { ...blank(), ...template, action_path: template.action_path || '' }
  editId.value = template.id
  version.value = template.version
  formMode.value = 'template'
  formError.value = ''
  formKey.value++
}
async function save() {
  if (!auth.isOwner || !auth.token || busy.value || !formMode.value) return
  const value = form.value
  if (formMode.value === 'message' && composerError.value) { formError.value = composerError.value; return }
  if (
    !value.title.trim() ||
    !value.body.trim() ||
    (formMode.value === 'message' && !value.user_ids.length) ||
    (formMode.value === 'template' && !value.name.trim())
  ) {
    formError.value = n('validation')
    return
  }
  if (!value.context && value.action_path && !safeNotificationPath(value.action_path)) {
    formError.value = n('invalidPath')
    return
  }
  const schedule = value.scheduled_at ? new Date(value.scheduled_at) : null
  if (
    schedule &&
    (!Number.isFinite(schedule.getTime()) || (!editId.value && schedule.getTime() <= Date.now()))
  ) {
    formError.value = n('invalidSchedule')
    return
  }
  const content: NotificationContent = {
    title: value.title.trim(),
    body: value.body.trim(),
    category: value.category,
    severity: value.severity,
    requires_ack: value.requires_ack || value.requires_response,
    requires_response: value.requires_response,
    action_path: value.context ? null : value.action_path || null,
  }
  const own = generation,
    current = ++saveEpoch,
    token = auth.token
  busy.value = true
  formError.value = ''
  success.value = ''
  try {
    if (formMode.value === 'template')
      await notificationsAPI.template(
        { ...content, name: value.name.trim() },
        editId.value || undefined,
        version.value,
        token,
      )
    else if (editId.value)
      await notificationsAPI.update(
        editId.value,
        {
          ...content,
          expected_version: version.value,
          user_ids: [...value.user_ids],
          scheduled_at: schedule?.toISOString() || null,
          context: value.context || null,
        },
        token,
      )
    else
      await notificationsAPI.create(
        {
          ...content,
          request_id: requestId.value,
          user_ids: [...value.user_ids],
          scheduled_at: schedule?.toISOString() || null,
          context: value.context || null,
        },
        token,
      )
    if (own !== generation || current !== saveEpoch || token !== auth.token) return
    formMode.value = null
    success.value = n('saved')
    await load()
  } catch (reason) {
    if (own === generation && current === saveEpoch) {
      const detail = (reason as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
      formError.value = typeof detail === 'string' ? detail.slice(0, 400) : n(
        (reason as { response?: { status?: number } }).response?.status === 409
          ? 'conflict'
          : 'saveError',
      )
    }
  } finally {
    if (own === generation && current === saveEpoch) busy.value = false
  }
}
async function cancelMessage(item: AdminNotification) {
  if (!auth.isOwner || !auth.token || busy.value) return
  const own = generation,
    current = ++saveEpoch,
    token = auth.token
  busy.value = true
  error.value = ''
  try {
    await notificationsAPI.cancel(item.id, item.version, token)
    if (own === generation && current === saveEpoch) {
      cancelId.value = ''
      await load()
    }
  } catch (reason) {
    if (own === generation && current === saveEpoch)
      error.value = n(
        (reason as { response?: { status?: number } }).response?.status === 409
          ? 'conflict'
          : 'saveError',
      )
  } finally {
    if (own === generation && current === saveEpoch) busy.value = false
  }
}
</script>
<style scoped>
.notification-admin {
  min-width: 0;
  display: grid;
  gap: 16px;
}
.notification-admin__heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
}
.notification-admin h2 {
  font-size: 18px;
  margin: 0;
}
.notification-admin__heading p {
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  margin: 6px 0 0;
  max-width: 65ch;
}
.notification-admin__tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.notification-admin__tabs button {
  border: 1px solid #dbe4ef;
  border-radius: 20px;
  padding: 8px 12px;
  background: white;
  color: #475569;
  font-size: 13px;
}
.notification-admin__tabs .active {
  background: #eff6ff;
  color: #1d4ed8;
  border-color: #93c5fd;
  font-weight: 700;
}
.notification-admin > .erp-button {
  justify-self: start;
}
.notification-admin__form {
  display: grid;
  gap: 14px;
  border: 1px solid #bfdbfe;
  background: #f8fbff;
  border-radius: 12px;
  padding: 18px;
}
.notification-admin__form h3 {
  margin: 0;
  font-size: 16px;
}
.notification-admin__form > fieldset {
  border: 0;
  padding: 0;
  margin: 0;
  min-width: 0;
}
.notification-admin__list {
  display: grid;
  gap: 12px;
}
.notification-admin__item {
  border: 1px solid #dbe4ef;
  border-radius: 12px;
  padding: 16px;
  background: white;
  min-width: 0;
}
.notification-admin__item-heading {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.notification-admin__item h3 {
  font-size: 15px;
  margin: 0 0 8px;
  overflow-wrap: anywhere;
}
.notification-admin__item-heading > span,
.notification-admin__item small {
  font-size: 12px;
  color: #64748b;
}
.notification-admin__body {
  font-size: 13px;
  white-space: pre-wrap;
  line-height: 1.5;
  overflow-wrap: anywhere;
  margin: 8px 0 12px;
}
.notification-admin__item details {
  margin: 14px 0;
  font-size: 13px;
}
.notification-admin__item summary {
  cursor: pointer;
  font-weight: 600;
  color: #475569;
}
.notification-admin__item ul {
  list-style: none;
  padding: 0;
  margin: 12px 0;
}
.notification-admin__item li {
  padding: 10px 0;
  border-top: 1px solid #edf2f7;
}
.notification-admin__item li > span {
  margin-left: 8px;
  color: #64748b;
  font-size: 12px;
}
.notification-admin__item li small {
  display: block;
  margin-top: 5px;
}
.notification-admin__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.notification-admin__error {
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
}
.notification-admin__success {
  color: #047857;
  font-size: 13px;
  margin: 0;
}
.notification-admin__cancel {
  border: 1px solid #fecaca;
  border-radius: 10px;
  background: #fff7f7;
  padding: 12px;
  margin-top: 12px;
  font-size: 13px;
}
.notification-admin__cancel .erp-button {
  margin-right: 8px;
}
.is-cancelled {
  color: #b91c1c !important;
}
@media (max-width: 500px) {
  .notification-admin__form {
    padding: 12px;
  }
}
</style>
