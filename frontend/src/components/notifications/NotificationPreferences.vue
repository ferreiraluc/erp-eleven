<template>
  <details class="notification-preferences">
    <summary>{{ n('preferences') }}</summary>
    <div class="notification-preferences__body">
      <strong>{{ n('push') }}</strong>
      <p v-if="center.pushActive" class="notification-ok">{{ n('enabled') }}</p>
      <p v-else>{{ n(center.support === 'ready' ? 'inviteHelp' : center.support) }}</p>
      <p v-if="center.pushError" class="notification-error" role="alert">{{ center.pushError }}</p>
      <button
        v-if="!center.pushActive && center.support === 'ready'"
        type="button"
        class="erp-button erp-button--primary"
        :disabled="center.pushBusy"
        @click="center.enablePush"
      >
        {{ n(center.pushBusy ? 'loading' : 'enable') }}
      </button>
      <button
        v-if="center.pushActive"
        type="button"
        class="erp-button erp-button--secondary"
        :disabled="center.pushBusy"
        @click="center.disablePush"
      >
        {{ n('disable') }}
      </button>
      <p class="muted">{{ n('deliveryHelp') }}</p>
      <label class="check"
        ><input
          type="checkbox"
          :checked="center.prefs.sound_enabled"
          :disabled="center.preferencesBusy"
          @change="
            center.preferences({
              ...center.prefs,
              sound_enabled: ($event.target as HTMLInputElement).checked,
            })
          "
        />{{ n('sound') }}</label
      >
      <p class="muted">{{ n('soundHelp') }}</p>
      <button
        type="button"
        class="erp-button erp-button--secondary erp-button--sm"
        @click="testSound"
      >
        {{ n('testSound') }}
      </button>
      <fieldset :disabled="center.preferencesBusy">
        <legend>{{ n('categories') }}</legend>
        <label v-for="category in notificationCategories" :key="category" class="check"
          ><input
            type="checkbox"
            :checked="center.prefs.categories.includes(category)"
            @change="toggle(category, ($event.target as HTMLInputElement).checked)"
          />{{ n(category) }}</label
        >
      </fieldset>
    </div>
  </details>
</template>
<script setup lang="ts">
import { useNotificationCenter } from '@/stores/notificationCenter'
import { notificationCategories, type NotificationCategory } from '@/services/notifications'
import { allowNotificationSound, playNotificationSound } from '@/services/notificationPush'
import { notificationText as n } from '@/services/notificationText'
const center = useNotificationCenter()
function toggle(category: NotificationCategory, checked: boolean) {
  void center.preferences({
    ...center.prefs,
    categories: checked
      ? [...center.prefs.categories, category]
      : center.prefs.categories.filter((value) => value !== category),
  })
}
function testSound() {
  allowNotificationSound()
  window.setTimeout(playNotificationSound, 100)
}
</script>
<style scoped>
.notification-preferences {
  border: 1px solid #dbe4ef;
  border-radius: 14px;
  background: #fff;
}
.notification-preferences > summary {
  padding: 16px;
  font-weight: 650;
  cursor: pointer;
}
.notification-preferences__body {
  padding: 0 16px 16px;
  display: grid;
  justify-items: start;
  gap: 10px;
}
.notification-preferences p {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
}
.muted {
  color: #64748b;
}
.check {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
}
.check input {
  width: 19px;
  height: 19px;
  accent-color: #2563eb;
}
.notification-preferences fieldset {
  border: 0;
  padding: 12px 0 0;
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
}
.notification-preferences legend {
  font-size: 14px;
  font-weight: 650;
  margin-bottom: 12px;
}
.notification-error {
  color: #b91c1c;
}
.notification-ok {
  color: #047857;
}
</style>
