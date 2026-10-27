<template>
  <div class="notifications-content" :class="{ 'notifications-content--compact': compact }">
    <NotificationPreferences />
    <div class="notifications-toolbar">
      <div class="notifications-tabs">
        <button
          class="erp-control"
          :class="{ active: !center.unreadOnly }"
          :aria-pressed="!center.unreadOnly"
          @click="center.unreadOnly = false"
        >
          {{ n('all') }}</button
        ><button
          class="erp-control"
          :class="{ active: center.unreadOnly }"
          :aria-pressed="center.unreadOnly"
          @click="center.unreadOnly = true"
        >
          {{ n('unread', { count: center.unread }) }}
        </button>
      </div>
      <button
        class="erp-button erp-button--ghost erp-button--sm"
        :disabled="!center.unread || center.pending.includes('all')"
        @click="center.act('all', 'all')"
      >
        {{ n('readAll') }}
      </button>
    </div>
    <p v-if="!center.online" class="notifications-message" role="status">{{ n('offline') }}</p>
    <p v-if="center.error" class="notifications-message notifications-error" role="alert">
      {{ center.error }}
    </p>
    <p v-if="center.loading && !center.items.length" class="notifications-message" role="status">
      {{ n('loading') }}
    </p>
    <p v-else-if="!center.items.length && !center.error" class="notifications-empty">
      {{ n('empty') }}
    </p>
    <article
      v-for="item in center.items"
      :key="item.id"
      class="notification-card"
      :class="[`notification-card--${item.severity}`, { 'is-unread': !item.read_at }]"
    >
      <div class="notification-card__heading">
        <span class="notification-card__kind">{{ n(item.category) }} · {{ n(item.severity) }}</span
        ><time :datetime="item.published_at || item.created_at">{{
          date(item.published_at || item.created_at)
        }}</time>
      </div>
      <h2>{{ item.title }}</h2>
      <p class="notification-card__body">{{ item.body }}</p>
      <p v-if="item.acknowledged_at" class="notification-ack">
        ✓ {{ n('acknowledged') }} · {{ date(item.acknowledged_at)
        }}<span v-if="item.acknowledged_version && item.acknowledged_version !== item.version">
          · {{ n('revision', { version: item.acknowledged_version }) }}</span
        >
      </p>
      <p v-if="item.acknowledgement_note" class="notification-card__body">
        {{ item.acknowledgement_note }}
      </p>
      <label v-if="item.requires_response && !item.acknowledged_at" class="notification-response"
        >{{ n('response')
        }}<textarea
          v-model="responses[item.id]"
          rows="2"
          maxlength="1000"
          :disabled="center.pending.includes(item.id)"
        />
      </label>
      <p v-if="responseError === item.id" class="notifications-error" role="alert">
        {{ n('responseRequired') }}
      </p>
      <div class="notification-card__actions">
        <RouterLink
          v-if="safeNotificationPath(item.action_path)"
          :to="safeNotificationPath(item.action_path)!"
          class="erp-button erp-button--secondary erp-button--sm"
          @click="openItem(item.id)"
          >{{ n('open') }} <ArrowUpRight :size="15" aria-hidden="true"
        /></RouterLink>
        <button
          v-if="!item.read_at"
          class="erp-button erp-button--ghost erp-button--sm"
          :disabled="center.pending.includes(item.id)"
          @click="center.act(item.id, 'read')"
        >
          {{ n('read') }}
        </button>
        <button
          v-if="item.requires_ack && !item.acknowledged_at"
          class="erp-button erp-button--primary erp-button--sm"
          :disabled="center.pending.includes(item.id)"
          @click="acknowledge(item)"
        >
          {{ n(item.requires_response ? 'respond' : 'acknowledge') }}
        </button>
      </div>
    </article>
    <button
      v-if="center.items.length < center.total"
      class="erp-button erp-button--secondary notifications-more"
      :disabled="center.loading"
      @click="center.load(true)"
    >
      {{ n('more') }}
    </button>
  </div>
</template>
<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { getActivePinia } from 'pinia'
import { RouterLink } from 'vue-router'
import { ArrowUpRight } from 'lucide-vue-next'
import NotificationPreferences from '@/components/notifications/NotificationPreferences.vue'
import { useNotificationCenter } from '@/stores/notificationCenter'
import { useAuthStore } from '@/stores/auth'
import { type NotificationItem, safeNotificationPath } from '@/services/notifications'
import { notificationText as n } from '@/services/notificationText'
import { uiLocale } from '@/i18n/uiText'
defineProps<{ compact?: boolean }>()
const emit = defineEmits<{ navigate: [] }>()
const center = useNotificationCenter(),
  responses = reactive<Record<string, string>>({}),
  responseError = ref('')
const auth = getActivePinia() ? useAuthStore() : null
watch(
  () => JSON.stringify([auth?.user?.id, auth?.token, auth?.status]),
  () => {
    for (const id of Object.keys(responses)) delete responses[id]
    responseError.value = ''
  },
  { flush: 'sync' },
)
const date = (value: string) =>
  new Date(value).toLocaleString(uiLocale(), { dateStyle: 'short', timeStyle: 'short' })
function openItem(id: string) {
  void center.act(id, 'read')
  emit('navigate')
}
async function acknowledge(item: NotificationItem) {
  if (item.requires_response && !responses[item.id]?.trim()) {
    responseError.value = item.id
    return
  }
  responseError.value = ''
  if (await center.act(item.id, 'ack', responses[item.id]?.trim(), item.version))
    delete responses[item.id]
}
</script>
<style scoped>
.notifications-content {
  max-width: 900px;
  margin: 0 auto;
  padding: 4px 20px 40px;
  display: grid;
  gap: 16px;
}
.notifications-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.notifications-tabs {
  display: flex;
  gap: 6px;
}
.notifications-tabs button {
  padding: 8px 12px;
  border: 1px solid #dbe4ef;
  background: white;
  border-radius: 20px;
  color: #475569;
  font-size: 13px;
}
.notifications-tabs .active {
  background: #eff6ff;
  border-color: #93c5fd;
  color: #1d4ed8;
  font-weight: 700;
}
.notification-card {
  padding: 20px;
  border: 1px solid #e2e8f0;
  border-left: 4px solid #94a3b8;
  border-radius: 14px;
  background: #fff;
  min-width: 0;
}
.notification-card.is-unread {
  box-shadow: 0 2px 7px #0f172a08;
}
.notification-card--info {
  border-left-color: #3b82f6;
}
.notification-card--success {
  border-left-color: #10b981;
}
.notification-card--warning {
  border-left-color: #f59e0b;
}
.notification-card--urgent {
  border-left-color: #ef4444;
}
.notification-card__heading {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #64748b;
}
.notification-card__kind {
  font-weight: 650;
}
.notification-card h2 {
  font-size: 17px;
  margin: 12px 0 8px;
  overflow-wrap: anywhere;
}
.notification-card__body {
  font-size: 14px;
  white-space: pre-wrap;
  line-height: 1.6;
  margin: 0;
  overflow-wrap: anywhere;
}
.notification-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}
.notification-card__actions a {
  text-decoration: none;
}
.notification-response {
  display: grid;
  gap: 6px;
  margin-top: 16px;
  font-size: 13px;
  color: #475569;
  font-weight: 600;
}
.notification-response textarea {
  resize: vertical;
  min-height: 70px;
  max-width: 100%;
  padding: 10px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  font: inherit;
  background: #fff;
}
.notification-ack {
  font-size: 12px;
  color: #047857;
  margin: 14px 0 0;
}
.notifications-message,
.notifications-empty {
  padding: 18px;
  border-radius: 12px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 14px;
}
.notifications-empty {
  text-align: center;
  padding: 40px 20px;
}
.notifications-error {
  color: #b91c1c;
  font-size: 13px;
}
.notifications-more {
  justify-self: center;
}
@media (max-width: 600px) {
  .notifications-content {
    padding: 0 12px 30px;
    gap: 12px;
  }
  .notification-card {
    padding: 14px;
  }
  .notification-response textarea {
    font-size: 16px;
  }
  .notification-card h2 {
    font-size: 16px;
  }
  .notification-card__actions {
    gap: 6px;
  }
  .notifications-toolbar > .erp-button {
    padding-inline: 4px;
  }
}
.notifications-content--compact {
  max-width: none;
  padding: 12px;
  gap: 10px;
}
.notifications-content--compact .notification-card {
  padding: 14px;
  border-radius: 12px;
}
.notifications-content--compact .notification-card h2 {
  font-size: 15px;
  margin-top: 10px;
}
.notifications-content--compact .notification-card__heading {
  font-size: 11px;
}
.notifications-content--compact .notification-card__body {
  font-size: 13px;
  line-height: 1.5;
}
.notifications-content--compact .notification-card__actions {
  margin-top: 12px;
  gap: 6px;
}
.notifications-content--compact .notifications-empty {
  margin: 0;
  padding: 24px 12px;
}
.notifications-content--compact :deep(.notification-preferences > summary) {
  padding: 12px;
  font-size: 13px;
}
.notifications-content--compact .notifications-toolbar {
  gap: 6px;
}
.notifications-content--compact .notifications-tabs button {
  padding: 7px 10px;
  font-size: 12px;
}
.notifications-content--compact .notifications-toolbar > .erp-button {
  font-size: 12px;
  padding-inline: 4px;
}
</style>
