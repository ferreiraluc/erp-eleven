<template>
  <Teleport to="body">
    <div
      v-if="auth.isOwner"
      class="sale-notification-backdrop erp-dialog-backdrop"
      @click.self="!busy && emit('close')"
    >
      <section v-erp-dialog class="erp-dialog erp-dialog--lg sale-notification-dialog">
        <header class="erp-dialog__header">
          <h2>
            {{ n('contextNotifySeller') }}<span v-if="sale"> · #{{ sale.code }}</span>
          </h2>
          <button
            type="button"
            data-dialog-close
            class="erp-button erp-button--secondary erp-button--icon"
            :aria-label="n('close')"
            :disabled="busy"
            @click="emit('close')"
          >
            ×
          </button>
        </header>
        <form class="sale-notification-form" @submit.prevent="send">
          <div class="erp-dialog__body">
            <p v-if="loading" role="status">{{ n('loading') }}</p>
            <p v-if="error" class="sale-notification-error" role="alert">{{ error }}</p>
            <button
              v-if="!loading && !sale"
              type="button"
              class="erp-button erp-button--secondary"
              @click="load"
            >
              {{ n('refresh') }}
            </button>
            <fieldset v-if="sale && data && !sent" :disabled="busy">
              <NotificationComposer
                v-model="form"
                :templates="data.templates"
                :users="data.users"
                :token="auth.token"
                :initial-sale="sale"
                :locked-sale="true"
                :disabled="busy"
                @validity="validity = $event"
              />
            </fieldset>
            <p v-if="sent" class="sale-notification-success" role="status">{{ n('saved') }}</p>
          </div>
          <footer class="erp-dialog__footer">
            <button
              type="button"
              class="erp-button erp-button--secondary"
              :disabled="busy"
              @click="emit('close')"
            >
              {{ n(sent ? 'close' : 'cancel') }}</button
            ><button
              v-if="!sent"
              type="submit"
              class="erp-button erp-button--primary"
              :disabled="busy || loading || !sale || !!validity"
            >
              {{ n(busy ? 'loading' : 'send') }}
            </button>
          </footer>
        </form>
      </section>
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { vErpDialog } from '@/directives/erpDialog'
import {
  notificationsAPI,
  type NotificationAdminResult,
  type NotificationSaleDetail,
} from '@/services/notifications'
import { notificationText as n } from '@/services/notificationText'
import NotificationComposer, { type NotificationForm } from './NotificationComposer.vue'
const props = defineProps<{ saleId: string; itemId?: string | null }>()
const emit = defineEmits<{ close: []; sent: [] }>()
const auth = useAuthStore(),
  loading = ref(false),
  busy = ref(false),
  error = ref(''),
  validity = ref(''),
  sent = ref(false)
const data = ref<NotificationAdminResult | null>(null),
  sale = ref<NotificationSaleDetail | null>(null)
const blank = (): NotificationForm => ({
  name: '',
  title: '',
  body: '',
  category: 'sales',
  severity: 'warning',
  action_path: '',
  requires_ack: true,
  requires_response: true,
  user_ids: [],
  scheduled_at: '',
  context: null,
})
const form = ref<NotificationForm>(blank()),
  requestId = ref(crypto.randomUUID())
let epoch = 0,
  controller: AbortController | undefined
watch(
  form,
  () => {
    requestId.value = crypto.randomUUID()
  },
  { deep: true, flush: 'sync' },
)
watch(
  () =>
    [auth.isOwner && auth.isAuthenticated ? auth.token : null, props.saleId, props.itemId] as const,
  () => {
    void load()
  },
  { immediate: true },
)
async function load() {
  const own = ++epoch,
    token = auth.token
  controller?.abort()
  sale.value = null
  data.value = null
  form.value = blank()
  error.value = ''
  validity.value = ''
  sent.value = false
  busy.value = false
  loading.value = false
  if (!auth.isOwner || !auth.isAuthenticated || !token) return
  loading.value = true
  controller = new AbortController()
  try {
    const [metadata, selected] = await Promise.all([
      notificationsAPI.admin(0, token),
      notificationsAPI.contextSale(props.saleId, token, controller.signal),
    ])
    if (own !== epoch || token !== auth.token || !auth.isOwner) return
    data.value = metadata
    sale.value = selected
    form.value = {
      ...blank(),
      title: n('contextDefaultTitle'),
      body: n('contextDefaultBody'),
      user_ids:
        selected.seller_id && metadata.users.some((user) => user.id === selected.seller_id)
          ? [selected.seller_id]
          : [],
      context: {
        sale_id: selected.id,
        ...(props.itemId ? { item_id: props.itemId } : {}),
        target: props.itemId ? 'product' : 'sale',
      },
    }
  } catch {
    if (own === epoch) error.value = n('error')
  } finally {
    if (own === epoch) loading.value = false
  }
}
async function send() {
  if (
    !auth.isOwner ||
    !auth.token ||
    loading.value ||
    busy.value ||
    sent.value ||
    !sale.value ||
    validity.value
  )
    return
  if (!form.value.title.trim() || !form.value.body.trim() || !form.value.user_ids.length) {
    error.value = n('validation')
    return
  }
  const scheduled = form.value.scheduled_at ? new Date(form.value.scheduled_at) : null
  if (scheduled && (!Number.isFinite(scheduled.getTime()) || scheduled.getTime() <= Date.now())) {
    error.value = n('invalidSchedule')
    return
  }
  const token = auth.token,
    own = epoch
  busy.value = true
  error.value = ''
  try {
    await notificationsAPI.create(
      {
        title: form.value.title.trim(),
        body: form.value.body.trim(),
        category: form.value.category,
        severity: form.value.severity,
        requires_ack: form.value.requires_ack || form.value.requires_response,
        requires_response: form.value.requires_response,
        user_ids: [...form.value.user_ids],
        scheduled_at: scheduled?.toISOString() || null,
        action_path: null,
        context: form.value.context || null,
        request_id: requestId.value,
      },
      token,
    )
    if (own === epoch && token === auth.token && auth.isOwner) {
      sent.value = true
      emit('sent')
    }
  } catch (reason) {
    if (own === epoch && token === auth.token) {
      const detail = (reason as { response?: { data?: { detail?: unknown } } }).response?.data
        ?.detail
      error.value = typeof detail === 'string' ? detail.slice(0, 400) : n('saveError')
    }
  } finally {
    if (own === epoch) busy.value = false
  }
}
onBeforeUnmount(() => {
  epoch++
  controller?.abort()
})
</script>
<style scoped>
.sale-notification-backdrop {
  position: fixed;
  inset: 0;
  z-index: 13000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: #0f172a80;
}
.sale-notification-dialog {
  width: min(720px, 100%);
  max-height: calc(100dvh - 32px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: #fff;
}
.sale-notification-dialog h2 {
  font-size: 18px;
  margin: 0;
}
.sale-notification-dialog h2 span {
  color: #64748b;
  font-size: 14px;
}
.sale-notification-form {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}
.sale-notification-form > .erp-dialog__body {
  overflow: auto;
  overscroll-behavior: contain;
}
.sale-notification-form fieldset {
  border: 0;
  margin: 0;
  padding: 0;
  min-width: 0;
}
.sale-notification-error {
  font-size: 13px;
  color: #b91c1c;
  line-height: 1.5;
}
.sale-notification-success {
  color: #047857;
  font-size: 14px;
}
@media (max-width: 600px) {
  .sale-notification-backdrop {
    padding: 8px;
  }
  .sale-notification-dialog {
    max-height: calc(100dvh - 16px);
  }
  .sale-notification-dialog h2 {
    font-size: 16px;
  }
}
</style>
