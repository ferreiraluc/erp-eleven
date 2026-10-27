<template>
  <div class="notifications-page">
    <ModuleHeader :title="n('title')">
      <button
        class="erp-button erp-button--secondary"
        :disabled="center.loading"
        @click="center.load()"
      >
        {{ n('refresh') }}
      </button>
    </ModuleHeader>
    <NotificationInbox />
  </div>
</template>
<script setup lang="ts">
import ModuleHeader from '@/components/ModuleHeader.vue'
import NotificationInbox from '@/components/notifications/NotificationInbox.vue'
import { useNotificationCenter } from '@/stores/notificationCenter'
import { notificationText as n } from '@/services/notificationText'
const center = useNotificationCenter()
</script>
<style scoped>
.notifications-page {
  min-height: 100vh;
  background: #f8fafc;
}
</style>
