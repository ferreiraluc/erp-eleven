<template>
  <RouterLink
    v-if="auth?.isAuthenticated && !auth.user?.must_change_password"
    to="/notificacoes"
    class="notification-bell"
    :aria-label="label"
    :title="label"
  >
    <Bell :size="18" aria-hidden="true" />
    <span v-if="center && center.unread > 0" class="notification-bell__count">{{
      center.unread > 99 ? '99+' : center.unread
    }}</span>
  </RouterLink>
</template>
<script setup lang="ts">
import { computed } from 'vue'
import { getActivePinia } from 'pinia'
import { RouterLink } from 'vue-router'
import { Bell } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useNotificationCenter } from '@/stores/notificationCenter'
import { notificationText as n } from '@/services/notificationText'
const auth = getActivePinia() ? useAuthStore() : null
const center = auth ? useNotificationCenter() : null
const label = computed(
  () => `${n('title')}${center?.unread ? ` · ${n('unread', { count: center.unread })}` : ''}`,
)
</script>
<style scoped>
.notification-bell {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 34px;
  min-width: 34px;
  min-height: 34px;
  border: 1px solid #dbe4ef;
  border-radius: 50%;
  color: #475569;
  background: white;
  text-decoration: none;
}
.notification-bell:hover,
.notification-bell.router-link-active {
  color: #1d4ed8;
  background: #eff6ff;
  border-color: #bfdbfe;
}
.notification-bell:focus-visible {
  outline: 2px solid #2563eb;
  outline-offset: 3px;
}
.notification-bell__count {
  position: absolute;
  right: -5px;
  top: -6px;
  min-width: 18px;
  height: 18px;
  padding: 0 3px;
  display: grid;
  place-items: center;
  border: 2px solid #fff;
  border-radius: 12px;
  background: #dc2626;
  color: white;
  font-size: 10px;
  font-weight: 800;
  line-height: 1;
}
</style>
