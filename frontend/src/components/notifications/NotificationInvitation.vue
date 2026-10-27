<template>
  <aside
    v-if="center.invitation && auth.isAuthenticated"
    class="notification-invitation"
    :aria-label="n('invitation')"
  >
    <BellRing :size="22" aria-hidden="true" />
    <div class="notification-invitation__copy">
      <strong>{{ n('invitation') }}</strong>
      <p>{{ n(center.support === 'ready' ? 'inviteHelp' : center.support) }}</p>
      <p v-if="center.pushError" role="alert">{{ center.pushError }}</p>
    </div>
    <div class="notification-invitation__actions">
      <button
        v-if="center.support === 'ready'"
        type="button"
        class="erp-button erp-button--primary erp-button--sm"
        :disabled="center.pushBusy"
        @click="center.enablePush"
      >
        {{ n(center.pushBusy ? 'loading' : 'enable') }}
      </button>
      <button
        type="button"
        class="erp-button erp-button--ghost erp-button--sm"
        :disabled="center.pushBusy"
        @click="center.deferInvitation"
      >
        {{ n('later') }}
      </button>
    </div>
  </aside>
</template>
<script setup lang="ts">
import { BellRing } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useNotificationCenter } from '@/stores/notificationCenter'
import { notificationText as n } from '@/services/notificationText'
const auth = useAuthStore(),
  center = useNotificationCenter()
</script>
<style scoped>
.notification-invitation {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 20px;
  background: #eff6ff;
  border-bottom: 1px solid #bfdbfe;
  color: #1e3a8a;
}
.notification-invitation > svg {
  flex-shrink: 0;
  margin-top: 2px;
}
.notification-invitation__copy {
  flex: 1;
  min-width: 0;
}
.notification-invitation strong {
  font-size: 14px;
}
.notification-invitation p {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.5;
  max-width: 75ch;
}
.notification-invitation__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
@media (max-width: 600px) {
  .notification-invitation {
    padding: 12px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .notification-invitation__copy {
    flex-basis: calc(100% - 34px);
  }
  .notification-invitation__actions {
    margin-left: 30px;
    flex-shrink: 1;
  }
}
</style>
